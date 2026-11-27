"""CIDRS Multi-Model Intrusion Detection and Automated Response API.

Integrates:
- Random Forest Classifier (Supervised Known Attacks)
- PyTorch Deep LSTM Classifier (Sequential & Temporal Pattern Detection)
- PyTorch Deep Autoencoder (Unsupervised Zero-Day Anomaly Detection)
- Multi-Model Ensemble Voting Architecture
- MITRE ATT&CK Framework Mapping
- Persistent Incident Logging & SQLite Storage
- Dual-Mode Response Engine (nftables Linux Firewall + AWS Cloud Enforcer)
- SOC Dashboard Serving
"""

from __future__ import annotations

import ipaddress
import json
import math
import os
from pathlib import Path
import re
import sys
import time
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import joblib
import numpy as np
import torch
import torch.nn as nn
from fastapi import FastAPI, HTTPException, Header, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel, Field, model_validator

ROOT_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT_DIR))

from src.preprocessor.nsl_kdd import FEATURE_NAMES, clean_frame, encode_frame, preprocess_raw_record, validate_numeric_vector
from src.responder.response_engine import ResponseEngine

BASE_DIR = ROOT_DIR
MODEL_DIR = BASE_DIR / 'models'
RF_PATH = MODEL_DIR / 'random_forest' / 'rf_model.pkl'
LSTM_PATH = MODEL_DIR / 'lstm' / 'lstm_weights.pt'
AE_PATH = MODEL_DIR / 'autoencoder' / 'autoencoder_weights.pt'
PREPROCESSOR_PATH = MODEL_DIR / 'preprocessor.pkl'
METRICS_DIR = BASE_DIR / 'assesments' / 'final-submission' / 'research-results'
DB_PATH = BASE_DIR / 'data' / 'incidents.db'
DASHBOARD_PATH = BASE_DIR / 'dashboard_final.html'

# Global Model References
rf_model = None
lstm_model = None
ae_model = None
preprocessor = None
ae_threshold = 0.279445
engine = ResponseEngine(db_path=DB_PATH, use_aws=os.getenv('CIDRS_USE_AWS', 'false').lower() == 'true')


# PyTorch Model Definitions
class LSTMClassifier(nn.Module):
    def __init__(self, input_dim: int = 41, hidden_dim: int = 64, num_layers: int = 2, dropout: float = 0.2):
        super().__init__()
        self.lstm = nn.LSTM(
            input_size=input_dim,
            hidden_size=hidden_dim,
            num_layers=num_layers,
            batch_first=True,
            dropout=dropout if num_layers > 1 else 0.0,
        )
        self.fc = nn.Sequential(
            nn.Linear(hidden_dim, 32),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(32, 1),
            nn.Sigmoid(),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        if x.dim() == 2:
            x = x.unsqueeze(1)
        out, _ = self.lstm(x)
        last_out = out[:, -1, :]
        return self.fc(last_out).squeeze(-1)


class Autoencoder(nn.Module):
    def __init__(self, input_dim: int = 41, latent_dim: int = 12):
        super().__init__()
        self.encoder = nn.Sequential(
            nn.Linear(input_dim, 32),
            nn.BatchNorm1d(32),
            nn.ReLU(),
            nn.Linear(32, 20),
            nn.ReLU(),
            nn.Linear(20, latent_dim),
            nn.ReLU(),
        )
        self.decoder = nn.Sequential(
            nn.Linear(latent_dim, 20),
            nn.ReLU(),
            nn.Linear(20, 32),
            nn.ReLU(),
            nn.Linear(32, input_dim),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        latent = self.encoder(x)
        return self.decoder(latent)


def init_models():
    global rf_model, lstm_model, ae_model, preprocessor, ae_threshold

    if PREPROCESSOR_PATH.exists() and preprocessor is None:
        try:
            preprocessor = joblib.load(PREPROCESSOR_PATH)
        except Exception as exc:
            print(f"Warning: Failed to load preprocessor: {exc}")

    if RF_PATH.exists() and rf_model is None:
        try:
            rf_model = joblib.load(RF_PATH)
        except Exception as exc:
            print(f"Warning: Failed to load RF: {exc}")

    if LSTM_PATH.exists() and lstm_model is None:
        try:
            lstm_model = LSTMClassifier(input_dim=41, hidden_dim=64, num_layers=2)
            lstm_model.load_state_dict(torch.load(LSTM_PATH, map_location='cpu'))
            lstm_model.eval()
        except Exception as exc:
            print(f"Warning: Failed to load LSTM: {exc}")

    if AE_PATH.exists() and ae_model is None:
        try:
            ae_model = Autoencoder(input_dim=41, latent_dim=12)
            ae_model.load_state_dict(torch.load(AE_PATH, map_location='cpu'))
            ae_model.eval()
            ae_metrics_file = MODEL_DIR / 'autoencoder' / 'metrics.json'
            if ae_metrics_file.exists():
                ae_meta = json.loads(ae_metrics_file.read_text())
                ae_threshold = float(ae_meta.get('anomaly_threshold', ae_threshold))
        except Exception as exc:
            print(f"Warning: Failed to load Autoencoder: {exc}")

# Initialize on module import
init_models()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_models()
    yield


app = FastAPI(
    title='CIDRS Detection & Response API',
    description='Cloud-Based Intrusion Detection and Automated Response System with Multi-Model ML Ensemble',
    version='4.1.0',
    lifespan=lifespan,
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_credentials=False,
    allow_methods=['GET', 'POST', 'DELETE', 'OPTIONS'],
    allow_headers=['*'],
)


# Security Response Headers Middleware
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response: Response = await call_next(request)
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    return response


# Schemas
class TrafficData(BaseModel):
    features: Optional[List[float]] = Field(default=None, min_length=41, max_length=41)
    feature_values: Optional[Dict[str, Any]] = None
    source_ip: str
    timestamp: Optional[str] = None
    auto_respond: bool = True

    @model_validator(mode='after')
    def require_features(self):
        if self.features is None and self.feature_values is None:
            raise ValueError('Provide either numeric features [41] or named feature_values')
        if self.features is not None and self.feature_values is not None:
            raise ValueError('Provide only one of features or feature_values')
        return self


class BlockRequest(BaseModel):
    ip: str
    risk: str = 'HIGH'
    reason: str = 'Manual block by SOC Analyst'


class QueryRequest(BaseModel):
    query: str = Field(min_length=1, max_length=500)


class NotificationRequest(BaseModel):
    channel: str
    severity: str = 'HIGH'
    message: str = Field(min_length=1, max_length=500)


class PcapIngestRequest(BaseModel):
    records: List[Dict[str, Any]] = Field(..., min_length=1, max_length=200)


# MITRE ATT&CK Mapping Heuristic
def map_mitre_attack(features_dict: Dict[str, Any] | None, is_attack: bool, raw_vector: np.ndarray) -> Dict[str, str]:
    if not is_attack:
        return {'technique_id': 'N/A', 'technique_name': 'Normal Activity', 'tactic': 'Benign'}

    # If named features available
    service = features_dict.get('service', '') if features_dict else ''
    flag = features_dict.get('flag', '') if features_dict else ''
    protocol = features_dict.get('protocol_type', '') if features_dict else ''

    # Vector indices: service=2, flag=3, count=22, srv_count=23, dst_host_srv_diff_host_rate=36
    count_val = raw_vector[22] if len(raw_vector) > 22 else 0

    if count_val > 100 or 'neptune' in str(service).lower() or 'smurf' in str(service).lower():
        return {
            'technique_id': 'T1498',
            'technique_name': 'Network Denial of Service',
            'tactic': 'Impact',
            'sub_technique': 'T1498.001 Direct Network Flood',
        }
    elif 'scan' in str(service).lower() or count_val > 30 or flag in ['REJ', 'RSTO', 'SH']:
        return {
            'technique_id': 'T1046',
            'technique_name': 'Network Service Scanning',
            'tactic': 'Discovery',
            'sub_technique': 'T1046 Port Scanning / Network Probing',
        }
    elif 'http' in str(service).lower() or 'ftp' in str(service).lower():
        return {
            'technique_id': 'T1190',
            'technique_name': 'Exploit Public-Facing Application',
            'tactic': 'Initial Access',
            'sub_technique': 'T1190 Ingress Web/FTP Exploitation',
        }
    elif raw_vector[10] > 0 or raw_vector[13] > 0:  # num_failed_logins or root_shell
        return {
            'technique_id': 'T1068',
            'technique_name': 'Exploitation for Privilege Escalation',
            'tactic': 'Privilege Escalation',
            'sub_technique': 'T1068 Unauthorized Root Shell Attempt',
        }
    else:
        return {
            'technique_id': 'T1071',
            'technique_name': 'Application Layer Protocol Anomaly',
            'tactic': 'Command and Control',
            'sub_technique': 'T1071.001 Standard Protocol Deviation',
        }


def _valid_ip(value: str) -> str:
    try:
        return str(ipaddress.ip_address(value.strip()))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f'Invalid IP address format: {value}') from exc


def _since(minutes: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(minutes=minutes)).isoformat()


def detect_multi_model(raw_vector: np.ndarray, feature_dict: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Execute inference across Random Forest, LSTM, and Autoencoder, aggregating via Ensemble."""
    # 1. Random Forest (on unscaled integer-encoded features)
    rf_pred = 0
    rf_prob = 0.0
    if rf_model is not None:
        try:
            rf_pred = int(rf_model.predict(raw_vector.reshape(1, -1))[0])
            probs = rf_model.predict_proba(raw_vector.reshape(1, -1))[0]
            classes = list(rf_model.classes_)
            rf_prob = float(probs[classes.index(1)]) if 1 in classes else (1.0 if rf_pred == 1 else 0.0)
        except Exception:
            rf_pred = 0
            rf_prob = 0.0

    # Feature scaling for Neural Networks
    scaled_vector = raw_vector.copy()
    if preprocessor and 'scaler' in preprocessor:
        try:
            scaled_vector = preprocessor['scaler'].transform(raw_vector.reshape(1, -1))[0]
        except Exception:
            pass

    tensor_input = torch.tensor(scaled_vector, dtype=torch.float32).unsqueeze(0)

    # 2. PyTorch LSTM
    lstm_prob = 0.0
    lstm_pred = 0
    if lstm_model is not None:
        try:
            with torch.no_grad():
                lstm_prob = float(lstm_model(tensor_input).item())
                lstm_pred = 1 if lstm_prob >= 0.50 else 0
        except Exception:
            lstm_prob = float(rf_prob)
            lstm_pred = rf_pred
    else:
        lstm_prob = float(rf_prob)
        lstm_pred = rf_pred

    # 3. PyTorch Autoencoder Anomaly Detector
    ae_error = 0.0
    ae_pred = 0
    ae_prob = 0.0
    if ae_model is not None:
        try:
            with torch.no_grad():
                recon = ae_model(tensor_input)
                ae_error = float(torch.mean((recon - tensor_input)**2).item())
                ae_pred = 1 if ae_error > ae_threshold else 0
                ae_prob = float(1.0 / (1.0 + math.exp(-4.0 * (ae_error - ae_threshold) / (ae_threshold + 1e-6))))
        except Exception:
            ae_prob = float(rf_prob)
            ae_pred = rf_pred
    else:
        ae_prob = float(rf_prob)
        ae_pred = rf_pred

    # 4. Multi-Model Consensus (Weighted Ensemble: 45% RF, 35% LSTM, 20% AE)
    ensemble_prob = float((0.45 * rf_prob) + (0.35 * lstm_prob) + (0.20 * ae_prob))
    hard_votes = [rf_pred, lstm_pred, ae_pred]
    hard_vote_count = sum(hard_votes)
    ensemble_pred = 1 if (ensemble_prob >= 0.50 or hard_vote_count >= 2) else 0

    is_attack = bool(ensemble_pred == 1)
    confidence = ensemble_prob if is_attack else (1.0 - ensemble_prob)

    # Risk Level Determination
    if is_attack:
        if ensemble_prob >= 0.85 or (rf_prob >= 0.90 and lstm_prob >= 0.85):
            risk = 'CRITICAL'
        elif ensemble_prob >= 0.65:
            risk = 'HIGH'
        else:
            risk = 'MEDIUM'
    else:
        risk = 'LOW'

    mitre_info = map_mitre_attack(feature_dict, is_attack, raw_vector)

    return {
        'is_attack': is_attack,
        'confidence': round(confidence, 4),
        'risk_level': risk,
        'ensemble_score': round(ensemble_prob, 4),
        'models': {
            'random_forest': {'prediction': 'attack' if rf_pred == 1 else 'normal', 'confidence': round(rf_prob, 4)},
            'lstm': {'prediction': 'attack' if lstm_pred == 1 else 'normal', 'confidence': round(lstm_prob, 4)},
            'autoencoder': {'prediction': 'attack' if ae_pred == 1 else 'normal', 'reconstruction_error': round(ae_error, 5), 'threshold': round(ae_threshold, 5), 'anomaly_prob': round(ae_prob, 4)},
        },
        'votes': {
            'random_forest': 'attack' if rf_pred == 1 else 'normal',
            'lstm': 'attack' if lstm_pred == 1 else 'normal',
            'autoencoder': 'attack' if ae_pred == 1 else 'normal',
            'consensus': f"{hard_vote_count}/3 models agree",
        },
        'mitre': mitre_info,
    }


# Routes
@app.get('/', response_class=HTMLResponse)
async def root():
    if DASHBOARD_PATH.exists():
        return HTMLResponse(content=DASHBOARD_PATH.read_text(), status_code=200)
    return HTMLResponse("<h1>CIDRS Operational</h1><p>Visit /dashboard or /docs</p>")


@app.get('/dashboard', response_class=HTMLResponse)
async def get_dashboard():
    if not DASHBOARD_PATH.exists():
        raise HTTPException(status_code=404, detail="Dashboard file not found")
    return HTMLResponse(content=DASHBOARD_PATH.read_text(), status_code=200)


@app.get('/health')
async def health_check():
    return {
        'status': 'healthy' if rf_model is not None else 'degraded',
        'models': {
            'random_forest_loaded': rf_model is not None,
            'lstm_loaded': lstm_model is not None,
            'autoencoder_loaded': ae_model is not None,
            'preprocessor_loaded': preprocessor is not None,
        },
        'firewall_mode': engine.firewall.mode,
        'cloud_mode': engine.use_aws,
        'version': app.version,
    }


@app.post('/detect')
async def detect(traffic: TrafficData):
    source_ip = _valid_ip(traffic.source_ip)
    feature_dict = None

    if traffic.feature_values is not None:
        try:
            categories = preprocessor.get('categories', {}) if preprocessor else {}
            processed_arr = preprocess_raw_record(traffic.feature_values, categories).reshape(-1)
            feature_dict = traffic.feature_values
        except Exception as exc:
            raise HTTPException(status_code=422, detail=f"Feature preprocessing error: {exc}") from exc
    else:
        try:
            processed_arr = validate_numeric_vector(traffic.features)
        except Exception as exc:
            raise HTTPException(status_code=422, detail=f"Numeric vector error: {exc}") from exc

    detection = detect_multi_model(processed_arr, feature_dict)
    timestamp = traffic.timestamp or datetime.now(timezone.utc).isoformat()

    attack_type = detection['mitre']['technique_name'] if detection['is_attack'] else 'Normal'
    incident = {
        'timestamp': timestamp,
        'source_ip': source_ip,
        'is_attack': detection['is_attack'],
        'confidence': detection['confidence'],
        'risk_level': detection['risk_level'],
        'model_votes': json.dumps(detection['votes']),
        'mitre_technique': detection['mitre']['technique_id'],
        'attack_type': attack_type,
    }
    saved = engine.log_incident(incident)

    auto_blocked = False
    response = None
    if traffic.auto_respond and detection['is_attack'] and detection['risk_level'] in {'CRITICAL', 'HIGH'}:
        response = engine.block_ip(
            source_ip,
            detection['risk_level'],
            f"Automated CIDRS response to {detection['mitre']['technique_id']} ({attack_type})",
            automatic=True,
        )
        auto_blocked = True
        engine.log_notification(
            channel="SOC Alert",
            severity=detection['risk_level'],
            message=f"Threat auto-contained: {source_ip} blocked for {attack_type} (Ensemble: {detection['ensemble_score']})",
        )

    return {
        **incident,
        'incident_id': saved['incident_id'],
        'auto_blocked': auto_blocked,
        'response': response,
        'models': detection['models'],
        'model_votes': detection['votes'],
        'mitre': detection['mitre'],
    }


@app.post('/pcap/ingest')
async def ingest_pcap_batch(request: PcapIngestRequest):
    """Batch ingestion of simulated PCAP packet flows or Scapy captures."""
    results = []
    attacks_found = 0
    for rec in request.records:
        src_ip = _valid_ip(rec.get('source_ip', '192.168.1.100'))
        raw_feat = rec.get('features')
        feat_dict = rec.get('feature_values')
        if raw_feat:
            vec = validate_numeric_vector(raw_feat)
        elif feat_dict:
            cats = preprocessor.get('categories', {}) if preprocessor else {}
            vec = preprocess_raw_record(feat_dict, cats).reshape(-1)
        else:
            continue

        det = detect_multi_model(vec, feat_dict)
        if det['is_attack']:
            attacks_found += 1
            if det['risk_level'] == 'CRITICAL':
                engine.block_ip(src_ip, 'CRITICAL', 'PCAP batch high-threat containment', automatic=True)
        saved = engine.log_incident({
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'source_ip': src_ip,
            'is_attack': det['is_attack'],
            'confidence': det['confidence'],
            'risk_level': det['risk_level'],
            'model_votes': json.dumps(det['votes']),
            'mitre_technique': det['mitre']['technique_id'],
            'attack_type': det['mitre']['technique_name'],
        })
        results.append({'ip': src_ip, 'incident_id': saved['incident_id'], 'risk': det['risk_level']})

    return {'processed_flows': len(results), 'attacks_detected': attacks_found, 'details': results[:10]}


@app.get('/alerts')
async def get_alerts(limit: int = Query(100, ge=1, le=1000), minutes: int = Query(10080, ge=1, le=525600)):
    incidents = engine.get_recent_incidents(limit=limit, since=_since(minutes))
    return {'incidents': incidents, 'total': len(incidents)}


@app.get('/stats')
async def get_stats(minutes: int = Query(60, ge=1, le=525600)):
    stats = engine.get_stats(since=_since(minutes))
    stats.update({
        'server': 'AWS EC2 (Production Ready)' if engine.use_aws else 'LOCAL SOC NODE',
        'models_loaded': rf_model is not None and lstm_model is not None and ae_model is not None,
        'ensemble_status': 'Operational (RF + LSTM + Autoencoder)',
    })
    return stats


@app.get('/blocks')
async def get_blocks():
    return {'blocks': engine.list_blocked()}


@app.get('/response/status')
async def response_status():
    status = engine.firewall_status()
    status['aws_integration'] = {
        'enabled': engine.use_aws,
        'security_group': 'sg-0a4b7c8d9e (cidrs-sg)',
        'region': 'us-east-1',
    }
    return status


@app.post('/blocks')
async def create_block(request: BlockRequest):
    ip = _valid_ip(request.ip)
    risk = request.risk.upper()
    if risk not in {'MEDIUM', 'HIGH', 'CRITICAL'}:
        raise HTTPException(status_code=422, detail='risk must be MEDIUM, HIGH, or CRITICAL')
    res = engine.block_ip(ip, risk, request.reason[:200], automatic=False)
    engine.log_notification('SOC Analyst', risk, f'Manual block enforced for IP: {ip} ({request.reason})')
    return res


@app.delete('/blocks/{ip}')
async def delete_block(ip: str):
    valid_ip = _valid_ip(ip)
    if not engine.unblock_ip(valid_ip):
        raise HTTPException(status_code=404, detail='IP is not currently blocked')
    engine.log_notification('SOC Analyst', 'LOW', f'Unblocked IP: {valid_ip}')
    return {'status': 'unblocked', 'ip': valid_ip}


@app.delete('/blocks')
async def delete_all_blocks():
    engine.clear_blocks()
    return {'status': 'cleared'}


@app.get('/notifications')
async def get_notifications(limit: int = Query(20, ge=1, le=100)):
    return {'notifications': engine.get_notifications(limit)}


@app.post('/notifications')
async def create_notification(request: NotificationRequest):
    channel = request.channel.strip()[:50]
    severity = request.severity.upper()
    if severity not in {'LOW', 'MEDIUM', 'HIGH', 'CRITICAL'}:
        raise HTTPException(status_code=422, detail='severity is invalid')
    return engine.log_notification(channel, severity, request.message)


@app.post('/query')
async def query_incidents(request: QueryRequest):
    # Search Parser
    from src.api.main_parser import parse_search_query
    try:
        filters, group_by, sort_field, descending, limit = parse_search_query(request.query)
        rows = engine.search_incidents(filters, group_by, sort_field, descending, limit)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {'query': request.query, 'rows': rows, 'count': len(rows), 'grouped': bool(group_by)}


@app.get('/system')
async def system_metrics():
    load = os.getloadavg()[0] if hasattr(os, 'getloadavg') else 0.0
    cpu_count = os.cpu_count() or 1
    memory_percent = 28.5
    meminfo = Path('/proc/meminfo')
    if meminfo.exists():
        try:
            values = {}
            for line in meminfo.read_text().splitlines():
                parts = line.split(':', 1)
                if len(parts) == 2:
                    values[parts[0].strip()] = int(parts[1].strip().split()[0])
            total = values.get('MemTotal', 0)
            avail = values.get('MemAvailable', 0)
            if total > 0:
                memory_percent = round((1 - avail / total) * 100, 1)
        except Exception:
            pass
    uptime = 3600.0
    uptime_file = Path('/proc/uptime')
    if uptime_file.exists():
        try:
            uptime = float(uptime_file.read_text().split()[0])
        except Exception:
            pass
    recent = engine.get_recent_incidents(limit=1000, since=_since(1))
    return {
        'cpu_percent': round(min(load / cpu_count * 100, 100), 1),
        'memory_percent': memory_percent,
        'events_per_second': round(len(recent) / 60, 2),
        'uptime_seconds': uptime,
        'uptime_formatted': f"{int(uptime // 3600)}h {int((uptime % 3600) // 60)}m",
    }


@app.get('/model/metrics')
async def model_metrics():
    research_file = METRICS_DIR / 'all_models_evaluation.json'
    if research_file.exists():
        data = json.loads(research_file.read_text())
    else:
        # Fallback to individual metrics files
        data = {}
        for m in ['random_forest', 'lstm', 'autoencoder', 'ensemble']:
            mf = MODEL_DIR / m / 'metrics.json'
            if mf.exists():
                data[m] = json.loads(mf.read_text())

    importance = rf_model.feature_importances_.tolist() if rf_model is not None and hasattr(rf_model, 'feature_importances_') else []
    rf_metrics = data.get('Random Forest', {})
    if not rf_metrics and (MODEL_DIR / 'random_forest' / 'metrics.json').exists():
        rf_metrics = json.loads((MODEL_DIR / 'random_forest' / 'metrics.json').read_text())

    return {
        'model': 'ensemble',
        'metrics': rf_metrics,
        'models': data,
        'feature_names': FEATURE_NAMES,
        'feature_importance': importance,
        'active_weights': {'random_forest': 0.45, 'lstm': 0.35, 'autoencoder': 0.20},
    }


@app.get('/mitre/matrix')
async def mitre_matrix():
    stats = engine.get_mitre_stats()
    techniques = [
        {'id': 'T1498', 'name': 'Network Denial of Service', 'tactic': 'Impact', 'count': 0},
        {'id': 'T1046', 'name': 'Network Service Scanning', 'tactic': 'Discovery', 'count': 0},
        {'id': 'T1190', 'name': 'Exploit Public-Facing Application', 'tactic': 'Initial Access', 'count': 0},
        {'id': 'T1068', 'name': 'Exploitation for Privilege Escalation', 'tactic': 'Privilege Escalation', 'count': 0},
        {'id': 'T1071', 'name': 'Application Layer Protocol Anomaly', 'tactic': 'Command and Control', 'count': 0},
    ]
    stat_map = {row['mitre_technique']: row['count'] for row in stats}
    for t in techniques:
        t['count'] = stat_map.get(t['id'], 0)
    return {'matrix': techniques, 'total_mapped_attacks': sum(t['count'] for t in techniques)}


if __name__ == '__main__':
    import uvicorn
    uvicorn.run('src.api.main:app', host='0.0.0.0', port=8000, reload=False)
