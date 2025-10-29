import os
import datetime
import json
import requests
import pandas as pd
import numpy as np
import face_recognition
from sklearn.ensemble import IsolationForest
from flask import render_template, redirect, request, flash, session, jsonify
from app import app

# ======================================================
# ⚙️ Basic Configurations
# ======================================================
CONNECTED_SERVICE_ADDRESS = "http://127.0.0.1:8000"

POLITICAL_PARTIES = [
    "Democratic Party",
    "Republican Party",
    "Socialist Party"
]

VOTER_IDS = [
    'VOID001', 'VOID002', 'VOID003',
    'VOID004', 'VOID005'
]

# Demo login fallback (used if no face data)
VOTER_CREDENTIALS = {
    'VOID001': 'pass001',
    'VOID002': 'pass002',
    'VOID003': 'pass003',
    'VOID004': 'pass004',
    'VOID005': 'pass005'
}

# ======================================================
# 🧠 Global Variables
# ======================================================
vote_check = []         # Track voters who already voted
posts = []              # Blockchain data
votes_data = []         # All voting data (AI analysis)
fraud_attempts = []     # Store suspicious activity

# ======================================================
# 👁️ Face Recognition Setup
# ======================================================
KNOWN_FACES_DIR = os.path.join(app.root_path, 'static', 'faces')
known_face_encodings = []
known_face_ids = []

def load_known_faces():
    """Load all known voter faces from static/faces folder."""
    global known_face_encodings, known_face_ids
    known_face_encodings = []
    known_face_ids = []
    os.makedirs(KNOWN_FACES_DIR, exist_ok=True)
    
    for fname in os.listdir(KNOWN_FACES_DIR):
        if fname.lower().endswith(('.jpg', '.jpeg', '.png')):
            voter_id = os.path.splitext(fname)[0]
            path = os.path.join(KNOWN_FACES_DIR, fname)
            try:
                img = face_recognition.load_image_file(path)
                encs = face_recognition.face_encodings(img)
                if len(encs) > 0:
                    known_face_encodings.append(encs[0])
                    known_face_ids.append(voter_id)
                else:
                    app.logger.warning(f"No face found in {path}; skipping.")
            except Exception as e:
                app.logger.error(f"Failed to load {path}: {e}")

# Initial load
load_known_faces()

# ======================================================
# ⛓️ Fetch Blockchain Data
# ======================================================
def fetch_posts():
    """Fetch blockchain data from connected service."""
    try:
        response = requests.get(f"{CONNECTED_SERVICE_ADDRESS}/chain", timeout=5)
        if response.status_code == 200:
            chain = response.json()["chain"]
            content = []
            for block in chain:
                for tx in block["transactions"]:
                    tx["index"] = block["index"]
                    tx["hash"] = block["previous_hash"]
                    content.append(tx)
            global posts
            posts = sorted(content, key=lambda k: k['timestamp'], reverse=True)
    except Exception as e:
        app.logger.error(f"Error fetching blockchain data: {e}")

# ======================================================
# 🏠 Home Page
# ======================================================
@app.route('/')
def index():
    fetch_posts()
    vote_gain = [post["party"] for post in posts]
    return render_template(
        'index.html',
        title='Blockchain + AI Secure Voting System',
        posts=posts,
        vote_gain=vote_gain,
        node_address=CONNECTED_SERVICE_ADDRESS,
        readable_time=timestamp_to_string,
        political_parties=POLITICAL_PARTIES,
        voter_ids=VOTER_IDS
    )

# ======================================================
# 🔐 Password Login
# ======================================================
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        voter_id = request.form.get('voter_id')
        password = request.form.get('password')

        if voter_id in VOTER_CREDENTIALS and VOTER_CREDENTIALS[voter_id] == password:
            session['voter_id'] = voter_id
            flash(f'✅ Login successful! Welcome, {voter_id}', 'success')
            return redirect('/')
        else:
            flash('❌ Invalid Voter ID or Password!', 'error')
            return redirect('/login')
    return render_template('login.html', title='Voter Login')

# ======================================================
# 👁️ Face Login Routes
# ======================================================
@app.route('/face_login')
def face_login():
    load_known_faces()
    return render_template('face_login.html', title='Face Recognition Login')

@app.route('/verify_face', methods=['POST'])
def verify_face():
    """Verify voter using webcam image."""
    if 'image' not in request.files:
        return jsonify({"status": "fail", "message": "No image uploaded"}), 400
    
    file = request.files['image']
    try:
        img = face_recognition.load_image_file(file)
        encodings = face_recognition.face_encodings(img)
        if not encodings:
            return jsonify({"status": "fail", "message": "No face detected"}), 200

        encoding = encodings[0]
        if not known_face_encodings:
            return jsonify({"status": "fail", "message": "No registered faces found"}), 200

        distances = face_recognition.face_distance(known_face_encodings, encoding)
        best_idx = int(np.argmin(distances))
        match = distances[best_idx] < 0.5

        if match:
            voter_id = known_face_ids[best_idx]
            session['voter_id'] = voter_id
            return jsonify({"status": "success", "voter_id": voter_id}), 200
        else:
            return jsonify({"status": "fail", "message": "Face not recognized"}), 200
    except Exception as e:
        app.logger.error(f"Face verification error: {e}")
        return jsonify({"status": "fail", "message": "Server error"}), 500

# ======================================================
# 🚪 Logout
# ======================================================
@app.route('/logout')
def logout():
    session.pop('voter_id', None)
    flash('✅ You have been logged out successfully.', 'success')
    return redirect('/login')

# ======================================================
# 🗳️ Submit Vote (Auto-Mining Enabled)
# ======================================================
@app.route('/submit', methods=['POST'])
def submit_textarea():
    """Submit a vote, run fraud detection, auto-mine block."""
    if 'voter_id' not in session:
        flash('❌ Please log in before voting!', 'error')
        return redirect('/login')

    party = request.form.get("party")
    voter_id = request.form.get("voter_id")
    ip_address = request.remote_addr
    timestamp = datetime.datetime.now().timestamp()

    # Basic validation
    if voter_id != session['voter_id']:
        flash('❌ You can only vote using your own Voter ID.', 'error')
        return redirect('/')
    if voter_id not in VOTER_IDS:
        flash('❌ Invalid Voter ID.', 'error')
        return redirect('/')
    if voter_id in vote_check:
        flash(f'⚠️ {voter_id} has already voted!', 'error')
        return redirect('/')

    # 🧠 AI Fraud Detection
    ip_count = sum(1 for v in votes_data if v['ip_address'] == ip_address)
    same_voter = sum(1 for v in votes_data if v['voter_id'] == voter_id)
    time_gap = 9999
    if ip_count > 0:
        last_vote = max(v for v in votes_data if v['ip_address'] == ip_address)['timestamp']
        time_gap = timestamp - last_vote

    votes_data.append({
        'ip_address': ip_address,
        'timestamp': timestamp,
        'voter_id': voter_id,
        'party': party
    })

    df = pd.DataFrame([{
        'ip_count': ip_count,
        'time_gap': time_gap,
        'same_voter': same_voter
    }])

    model = IsolationForest(contamination=0.1, random_state=42)
    model.fit(df)
    result = model.predict(df)[0]

    if result == -1:
        fraud_attempts.append({
            'voter_id': voter_id,
            'ip_address': ip_address,
            'timestamp': timestamp_to_string(timestamp),
            'reason': f'Anomalous behavior detected (IP count={ip_count}, time_gap={time_gap:.2f}s)'
        })
        flash('⚠️ Suspicious activity detected! Vote under review.', 'error')
        return redirect('/')

    # ✅ Safe Vote
    vote_check.append(voter_id)

    post_object = {
        'voter_id': voter_id,
        'party': party,
        'ip_address': ip_address,
        'timestamp': timestamp
    }

    try:
        # Send vote to blockchain
        requests.post(f"{CONNECTED_SERVICE_ADDRESS}/new_transaction", json=post_object, headers={'Content-type': 'application/json'}, timeout=5)
        # Auto-mine
        requests.get(f"{CONNECTED_SERVICE_ADDRESS}/mine", timeout=10)
    except Exception as e:
        app.logger.error(f"Blockchain transaction failed: {e}")

    flash(f'✅ Vote successfully cast for {party}!', 'success')
    return redirect('/')

# ======================================================
# 🚨 Fraud Dashboard
# ======================================================
@app.route('/fraud')
def fraud_dashboard():
    if not fraud_attempts:
        flash('✅ No suspicious activity detected so far.', 'success')
    return render_template('fraud.html', title='AI Fraud Detection Dashboard', fraud_attempts=fraud_attempts)

# ======================================================
# ⏰ Utility: Timestamp to String
# ======================================================
def timestamp_to_string(epoch_time):
    return datetime.datetime.fromtimestamp(epoch_time).strftime('%Y-%m-%d %H:%M:%S')
