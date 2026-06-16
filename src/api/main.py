"""
CIDRS - Detection API
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict
import numpy as np
import joblib
import json
from datetime import datetime
from collections import deque
import os

# Initialize FastAPI
app = FastAPI(
    title="CIDRS Detection API",
    description="Cloud-Based Intrusion Detection & Response System",
    version="3.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global variables
rf_model = None
recent_alerts = deque(maxlen=100)

# Models
class TrafficData(BaseModel):
    features: List[float]
    source_ip: str
    timestamp: Optional[str] = None

class DetectionResponse(BaseModel):
    timestamp: str
    source_ip: str
    is_attack: bool
    confidence: float
    risk_level: str
    model_votes: Dict[str, str]

@app.on_event("startup")
async def load_models():
    global rf_model
    
    print("=" * 50)
    print("CIDRS - Starting Up...")
    print("=" * 50)
    
    # Load Random Forest
    try:
        rf_model = joblib.load('models/random_forest/rf_model.pkl')
        print("✅ Random Forest loaded")
    except Exception as e:
        print(f"❌ Random Forest: {e}")
    
    print("=" * 50)
    print("CIDRS Ready!")
    print("=" * 50)

def detect_attack(features: List[float]) -> Dict:
    """Run detection using ML models"""
    
    X = np.array(features).reshape(1, -1)
    results = {}
    
    # Random Forest
    if rf_model:
        rf_pred = int(rf_model.predict(X)[0])
        rf_prob = float(rf_model.predict_proba(X)[0][1])
        results['random_forest'] = rf_pred
    else:
        results['random_forest'] = 0
    
    # Ensemble
    votes = list(results.values())
    is_attack = sum(votes) >= 1
    
    return {
        'is_attack': is_attack,
        'confidence': 0.75 if is_attack else 0.25,
        'risk_level': 'HIGH' if is_attack else 'LOW',
        'votes': {k: 'attack' if v == 1 else 'normal' for k, v in results.items()}
    }

@app.get("/")
async def root():
    return {"system": "CIDRS", "status": "operational"}

@app.get("/health")
async def health_check():
    return {"status": "healthy", "model_loaded": rf_model is not None}

@app.post("/detect", response_model=DetectionResponse)
async def detect(traffic: TrafficData):
    """Detect intrusion"""
    
    try:
        detection = detect_attack(traffic.features)
        
        # Store alert
        alert = {
            'timestamp': datetime.now().isoformat(),
            'source_ip': traffic.source_ip,
            'is_attack': detection['is_attack'],
            'risk_level': detection['risk_level'],
            'confidence': detection['confidence']
        }
        recent_alerts.append(alert)
        
        return DetectionResponse(
            timestamp=traffic.timestamp or datetime.now().isoformat(),
            source_ip=traffic.source_ip,
            is_attack=detection['is_attack'],
            confidence=detection['confidence'],
            risk_level=detection['risk_level'],
            model_votes=detection['votes']
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/alerts")
async def get_alerts():
    alerts_list = list(recent_alerts)
    return {"incidents": alerts_list, "total": len(alerts_list)}

@app.get("/stats")
async def get_stats():
    alerts_list = list(recent_alerts)
    attack_count = sum(1 for a in alerts_list if a['is_attack'])
    return {
        "total_incidents": len(alerts_list),
        "attacks_detected": attack_count,
        "ips_blocked": 0,
        "simulation_mode": True
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
