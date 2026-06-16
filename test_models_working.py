#!/usr/bin/env python3
"""Quick test to verify all models are working"""

import numpy as np
import joblib
import json
import sys

print("=" * 60)
print("🧪 TESTING CIDRS MODELS")
print("=" * 60)

# Test 1: Load Random Forest
try:
    rf_model = joblib.load('models/random_forest/rf_model.pkl')
    with open('models/random_forest/metrics.json', 'r') as f:
        rf_metrics = json.load(f)
    print("✅ Random Forest: LOADED")
    print(f"   - Accuracy: {rf_metrics['accuracy']*100:.2f}%")
except Exception as e:
    print(f"❌ Random Forest: FAILED - {e}")
    sys.exit(1)

# Test 2: Load LSTM
try:
    import tensorflow as tf
    lstm_model = tf.keras.models.load_model('models/lstm/lstm_model.h5')
    with open('models/lstm/metrics.json', 'r') as f:
        lstm_metrics = json.load(f)
    print("✅ LSTM: LOADED")
    print(f"   - Accuracy: {lstm_metrics['accuracy']*100:.2f}%")
except Exception as e:
    print(f"❌ LSTM: FAILED - {e}")
    sys.exit(1)

# Test 3: Load Autoencoder
try:
    ae_model = tf.keras.models.load_model('models/autoencoder/autoencoder.h5')
    with open('models/autoencoder/metrics.json', 'r') as f:
        ae_metrics = json.load(f)
    print("✅ Autoencoder: LOADED")
    print(f"   - Accuracy: {ae_metrics['accuracy']*100:.2f}%")
except Exception as e:
    print(f"❌ Autoencoder: FAILED - {e}")
    sys.exit(1)

# Test 4: Make a prediction
print("\n" + "=" * 60)
print("📊 MAKING TEST PREDICTION")
print("=" * 60)

# Create sample network traffic data (41 features)
sample = np.random.rand(1, 41)

# Random Forest prediction
rf_pred = rf_model.predict(sample)[0]
rf_prob = rf_model.predict_proba(sample)[0][1]

# LSTM prediction
lstm_prob = float(lstm_model.predict(sample, verbose=0)[0][0])
lstm_pred = 1 if lstm_prob > 0.5 else 0

# Autoencoder prediction (anomaly detection)
ae_recon = ae_model.predict(sample, verbose=0)
ae_error = np.mean((sample - ae_recon) ** 2)
threshold = 0.1
ae_pred = 1 if ae_error > threshold else 0

# Ensemble voting (2 out of 3)
votes = [rf_pred, lstm_pred, ae_pred]
ensemble_pred = 1 if sum(votes) >= 2 else 0

print(f"\n📊 Sample prediction results:")
print(f"  Random Forest:  {'🔴 ATTACK' if rf_pred == 1 else '🟢 NORMAL'} (confidence: {rf_prob:.2%})")
print(f"  LSTM:           {'🔴 ATTACK' if lstm_pred == 1 else '🟢 NORMAL'} (confidence: {lstm_prob:.2%})")
print(f"  Autoencoder:    {'🔴 ATTACK' if ae_pred == 1 else '🟢 NORMAL'} (error: {ae_error:.4f})")
print(f"\n🎯 Ensemble prediction: {'🔴 ATTACK' if ensemble_pred == 1 else '🟢 NORMAL'} ({sum(votes)}/3 models agree)")

print("\n" + "=" * 60)
print("✅ ALL MODELS WORKING CORRECTLY!")
print("=" * 60)
