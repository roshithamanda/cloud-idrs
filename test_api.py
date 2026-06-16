#!/usr/bin/env python3
"""Test FastAPI with loaded models"""

from fastapi import FastAPI
from pydantic import BaseModel
import numpy as np
import joblib
import tensorflow as tf
import uvicorn
from threading import Thread
import requests
import time

app = FastAPI()

# Load models on startup
print("Loading models...")
rf_model = joblib.load('models/random_forest/rf_model.pkl')
lstm_model = tf.keras.models.load_model('models/lstm/lstm_model.h5')
print("✅ Models loaded")

class TrafficSample(BaseModel):
    features: list
    source_ip: str = "test-ip"

@app.get("/health")
async def health():
    return {"status": "ok", "models_loaded": True}

@app.post("/predict")
async def predict(sample: TrafficSample):
    X = np.array(sample.features).reshape(1, -1)
    
    # Random Forest
    rf_pred = int(rf_model.predict(X)[0])
    rf_prob = float(rf_model.predict_proba(X)[0][1])
    
    # LSTM
    lstm_prob = float(lstm_model.predict(X, verbose=0)[0][0])
    lstm_pred = 1 if lstm_prob > 0.5 else 0
    
    # Ensemble
    is_attack = (rf_pred == 1 and lstm_pred == 1)
    confidence = (rf_prob + lstm_prob) / 2
    
    return {
        "is_attack": is_attack,
        "confidence": confidence,
        "rf_pred": rf_pred,
        "lstm_pred": lstm_pred
    }

def run_server():
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="error")

# Start server in background
server_thread = Thread(target=run_server, daemon=True)
server_thread.start()
time.sleep(2)

# Test the API
print("=" * 60)
print("🧪 TESTING API ENDPOINT")
print("=" * 60)

# Test health endpoint
response = requests.get("http://127.0.0.1:8000/health")
print(f"✅ Health check: {response.json()}")

# Test prediction
sample_features = np.random.rand(41).tolist()
response = requests.post(
    "http://127.0.0.1:8000/predict",
    json={"features": sample_features, "source_ip": "192.168.1.100"}
)
print(f"✅ Prediction: {response.json()}")

print("\n✅ API is working correctly!")
