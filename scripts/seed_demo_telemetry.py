"""Seed genuine telemetry and detections from NSL-KDD benchmark data into the database."""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
import random
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pandas as pd
import numpy as np
import joblib

from src.preprocessor.nsl_kdd import clean_frame, encode_frame
from src.api.main import detect_multi_model, engine

def seed():
    print("Seeding genuine telemetry into CIDRS database...")
    prep = joblib.load('models/preprocessor.pkl')
    categories = prep['categories']

    train = pd.read_csv('data/raw/NSL-KDD/KDDTrain+.txt', header=None, sep=',|\t', engine='python')
    train = clean_frame(train)

    normal_df = train[train[41].str.lower() == 'normal'].head(30)
    neptune_df = train[train[41].str.lower() == 'neptune'].head(15)
    satan_df = train[train[41].str.lower() == 'satan'].head(10)
    ipsweep_df = train[train[41].str.lower() == 'ipsweep'].head(8)
    smurf_df = train[train[41].str.lower() == 'smurf'].head(6)

    combined = pd.concat([normal_df, neptune_df, satan_df, ipsweep_df, smurf_df]).sample(frac=1.0, random_state=42).reset_index(drop=True)
    features_raw = combined.iloc[:, :41].copy()
    encoded, _ = encode_frame(features_raw, categories)

    adversary_ips = [
        '198.51.100.23', '203.0.113.45', '192.0.2.89', '45.33.32.156', '185.220.101.5',
        '91.240.118.172', '194.26.29.112', '162.247.74.200', '198.51.100.114', '203.0.113.190',
        '172.16.0.4', '10.0.1.15', '10.0.1.28', '192.168.1.105', '192.168.1.140'
    ]

    base_time = datetime.now(timezone.utc) - timedelta(hours=2)

    for idx, row in encoded.iterrows():
        raw_vec = row.values.astype(float)
        det = detect_multi_model(raw_vec)
        
        is_atk = det['is_attack']
        ip = random.choice(adversary_ips[:10]) if is_atk else random.choice(adversary_ips[10:])
        ts = (base_time + timedelta(minutes=idx * 1.8)).isoformat()
        
        attack_type = det['mitre']['technique_name'] if is_atk else 'Normal'
        
        incident = {
            'timestamp': ts,
            'source_ip': ip,
            'is_attack': det['is_attack'],
            'confidence': det['confidence'],
            'risk_level': det['risk_level'],
            'model_votes': json.dumps(det['votes']),
            'mitre_technique': det['mitre']['technique_id'],
            'attack_type': attack_type,
        }
        engine.log_incident(incident)

        if is_atk and det['risk_level'] in {'CRITICAL', 'HIGH'} and idx % 3 == 0:
            engine.block_ip(ip, det['risk_level'], f"Automatic containment: {attack_type} detected", automatic=True)
            engine.log_notification('SOC Alert', det['risk_level'], f"Threat auto-contained: {ip} blocked ({attack_type})")

    # Add a manual block for demonstration
    engine.block_ip('203.0.113.250', 'HIGH', 'Manual quarantine requested by SOC Analyst', automatic=False)
    engine.log_notification('SOC Analyst', 'HIGH', 'Manual quarantine enforced for 203.0.113.250')

    stats = engine.get_stats()
    print("Seeding complete! Database stats:", stats)

if __name__ == '__main__':
    seed()
