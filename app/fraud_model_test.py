import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score

# ============================================================
# Simulated Data for Testing
# ============================================================
# Columns: [ip_count, time_gap, same_voter]
# - Normal votes: low ip_count, large time_gap, not repeated voter
# - Fraud votes: repeated IP, very small time_gap, same voter ID reuse
data = [
    [1, 120, 0],  # Normal
    [2, 300, 0],  # Normal
    [1, 250, 0],  # Normal
    [10, 5, 1],   # Fraud
    [12, 3, 1],   # Fraud
    [8, 10, 1],   # Fraud
    [1, 600, 0],  # Normal
    [9, 2, 1],    # Fraud
    [1, 200, 0],  # Normal
    [2, 500, 0]   # Normal
]

# Labels:  1 = normal,  -1 = fraud
labels = [1, 1, 1, -1, -1, -1, 1, -1, 1, 1]

df = pd.DataFrame(data, columns=['ip_count', 'time_gap', 'same_voter'])

# ============================================================
# Train & Predict using Isolation Forest
# ============================================================
model = IsolationForest(contamination=0.3, random_state=42)
model.fit(df)

preds = model.predict(df)  # returns 1 (normal), -1 (fraud)

# ============================================================
# Evaluate Performance
# ============================================================
accuracy = accuracy_score(labels, preds)
precision = precision_score(labels, preds, pos_label=-1)
recall = recall_score(labels, preds, pos_label=-1)
f1 = f1_score(labels, preds, pos_label=-1)

print("=== 🧠 Fraud Detection Model Test ===")
print(f"Predictions: {preds}")
print(f"True Labels: {labels}")
print(f"Accuracy: {accuracy*100:.2f}%")
print(f"Precision: {precision*100:.2f}%")
print(f"Recall: {recall*100:.2f}%")
print(f"F1 Score: {f1*100:.2f}%")

# ============================================================
# Visualize detection results
# =========================================p===================
df['prediction'] = preds
df['true_label'] = labels
df['status'] = df['prediction'].apply(lambda x: 'FRAUD' if x == -1 else 'NORMAL')

print("\n=== Detailed Result Table ===")
print(df)
