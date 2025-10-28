import datetime
import json
import requests
import pandas as pd
from sklearn.ensemble import IsolationForest
from flask import render_template, redirect, request, flash, session
from app import app

# ======================================================
# Node and Configuration
# ======================================================
CONNECTED_SERVICE_ADDRESS = "http://127.0.0.1:8000"

POLITICAL_PARTIES = [
    "Democratic Party",
    "Republican Party",
    "Socialist Party"
]

VOTER_IDS = [
    'VOID001', 'VOID002', 'VOID003',
    'VOID004', 'VOID005', 'VOID006',
    'VOID007', 'VOID008', 'VOID009',
    'VOID010', 'VOID011', 'VOID012',
    'VOID013', 'VOID014', 'VOID015'
]

# ✅ Demo voter credentials
VOTER_CREDENTIALS = {
    'VOID001': 'pass001',
    'VOID002': 'pass002',
    'VOID003': 'pass003',
    'VOID004': 'pass004',
    'VOID005': 'pass005'
}

# ======================================================
# Global Variables
# ======================================================
vote_check = []        # Track voters who already voted
posts = []             # Blockchain data
votes_data = []        # All voting data
fraud_attempts = []    # 🧠 Store suspicious activity


# ======================================================
# Utility: Fetch Blockchain Posts
# ======================================================
def fetch_posts():
    """Fetch blockchain data."""
    get_chain_address = f"{CONNECTED_SERVICE_ADDRESS}/chain"
    response = requests.get(get_chain_address)

    if response.status_code == 200:
        content = []
        chain = json.loads(response.content)
        for block in chain["chain"]:
            for tx in block["transactions"]:
                tx["index"] = block["index"]
                tx["hash"] = block["previous_hash"]
                content.append(tx)

        global posts
        posts = sorted(content, key=lambda k: k['timestamp'], reverse=True)


# ======================================================
# Route: Home / Voting Page
# ======================================================
@app.route('/')
def index():
    fetch_posts()
    vote_gain = [post["party"] for post in posts]

    return render_template(
        'index.html',
        title='E-voting System using Blockchain and AI Security',
        posts=posts,
        vote_gain=vote_gain,
        node_address=CONNECTED_SERVICE_ADDRESS,
        readable_time=timestamp_to_string,
        political_parties=POLITICAL_PARTIES,
        voter_ids=VOTER_IDS
    )


# ======================================================
# Route: Login
# ======================================================
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        voter_id = request.form['voter_id']
        password = request.form['password']

        if voter_id in VOTER_CREDENTIALS and VOTER_CREDENTIALS[voter_id] == password:
            session['voter_id'] = voter_id
            flash(f'✅ Login successful! Welcome, {voter_id}', 'success')
            return redirect('/')
        else:
            flash('❌ Invalid Voter ID or Password!', 'error')
            return redirect('/login')

    return render_template('login.html', title='Voter Login')


# ======================================================
# Route: Logout
# ======================================================
@app.route('/logout')
def logout():
    session.pop('voter_id', None)
    flash('✅ You have been logged out successfully.', 'success')
    return redirect('/login')


# ======================================================
# Route: Submit Vote
# ======================================================
@app.route('/submit', methods=['POST'])
def submit_textarea():
    """Submit vote and run AI-based fraud detection."""
    if 'voter_id' not in session:
        flash('❌ You must log in before voting!', 'error')
        return redirect('/login')

    party = request.form["party"]
    voter_id = request.form["voter_id"]
    ip_address = request.remote_addr
    timestamp = datetime.datetime.now().timestamp()

    if voter_id != session['voter_id']:
        flash('❌ You can only vote using your own Voter ID.', 'error')
        return redirect('/')

    if voter_id not in VOTER_IDS:
        flash('❌ Invalid Voter ID. Please select from the sample list.', 'error')
        return redirect('/')

    if voter_id in vote_check:
        flash(f'⚠️ Voter ID ({voter_id}) already voted! Each voter can vote only once.', 'error')
        return redirect('/')

    # ======================================================
    # 🧠 AI-BASED FRAUD DETECTION SECTION
    # ======================================================
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
    result = model.predict(df)[0]  # -1 means anomaly

    if result == -1:
        flash('⚠️ Suspicious activity detected! Your vote is under review.', 'error')
        fraud_attempts.append({
            'voter_id': voter_id,
            'ip_address': ip_address,
            'timestamp': timestamp_to_string(timestamp),
            'reason': f'Anomalous behavior detected (IP count: {ip_count}, Time gap: {time_gap:.2f}s)'
        })
        print(f"⚠️ FRAUD ALERT: Suspicious vote by {voter_id} from IP {ip_address}")
        return redirect('/')

    # ======================================================
    # END FRAUD CHECK — proceed if safe
    # ======================================================
    vote_check.append(voter_id)

    post_object = {
        'voter_id': voter_id,
        'party': party,
        'ip_address': ip_address,
        'timestamp': timestamp
    }

    new_tx_address = f"{CONNECTED_SERVICE_ADDRESS}/new_transaction"
    requests.post(new_tx_address, json=post_object, headers={'Content-type': 'application/json'})

    flash(f'✅ Vote successfully cast for {party}!', 'success')
    return redirect('/')


# ======================================================
# Route: Fraud Dashboard
# ======================================================
@app.route('/fraud')
def fraud_dashboard():
    """Admin dashboard to review suspicious votes."""
    if len(fraud_attempts) == 0:
        flash('✅ No suspicious activity detected so far.', 'success')
    return render_template('fraud.html', title='AI Fraud Detection Dashboard', fraud_attempts=fraud_attempts)


# ======================================================
# Utility: Convert Epoch Time to Readable Time
# ======================================================
def timestamp_to_string(epoch_time):
    return datetime.datetime.fromtimestamp(epoch_time).strftime('%Y-%m-%d %H:%M')
