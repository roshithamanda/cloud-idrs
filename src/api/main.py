"""CIDRS detection and response API."""

import ipaddress
import json
import os
import re
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional

import joblib
import numpy as np
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from src.responder.response_engine import ResponseEngine

BASE_DIR = Path(__file__).resolve().parents[2]
MODEL_PATH = BASE_DIR / 'models' / 'random_forest' / 'rf_model.pkl'
METRICS_PATH = BASE_DIR / 'models' / 'random_forest' / 'metrics.json'
DB_PATH = BASE_DIR / 'data' / 'incidents.db'

app = FastAPI(title='CIDRS Detection API', description='Cloud-Based Intrusion Detection and Response System', version='4.0.0')
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv('CIDRS_ALLOWED_ORIGINS', '*').split(','),
    allow_credentials=False,
    allow_methods=['GET', 'POST', 'DELETE'],
    allow_headers=['Content-Type'],
)

rf_model = None
engine = ResponseEngine(db_path=DB_PATH, use_aws=os.getenv('CIDRS_USE_AWS', 'false').lower() == 'true')


class TrafficData(BaseModel):
    features: List[float] = Field(min_length=41, max_length=41)
    source_ip: str
    timestamp: Optional[str] = None


class BlockRequest(BaseModel):
    ip: str
    risk: str = 'HIGH'
    reason: str = 'Manual block'


class QueryRequest(BaseModel):
    query: str = Field(min_length=1, max_length=500)


class NotificationRequest(BaseModel):
    channel: str
    severity: str = 'HIGH'
    message: str = Field(min_length=1, max_length=500)


def parse_search_query(query):
    filters = []
    group_by = None
    sort_field = None
    descending = False
    limit = 100
    parts = [part.strip() for part in query.split('|') if part.strip()]
    if not parts:
        raise ValueError('Query is empty')
    filter_text = parts[0]
    if filter_text.startswith('search '):
        filter_text = filter_text[7:].strip()
    for match in re.finditer(r'([a-z_]+)\s*(=|!=|>=|<=|>|<)\s*(?:"([^"]*)"|([^\s]+))', filter_text, re.IGNORECASE):
        field, operator, quoted, plain = match.groups()
        value = quoted if quoted is not None else plain
        field = field.lower()
        if field == 'is_attack':
            if value.lower() in {'true', 'attack', '1'}:
                value = 1
            elif value.lower() in {'false', 'normal', '0'}:
                value = 0
            else:
                raise ValueError('is_attack must be true or false')
        elif field == 'confidence':
            value = float(value)
        elif field == 'source_ip' and value == '*':
            continue
        filters.append((field, operator, value))
    wildcard_query = bool(re.fullmatch(r'source_ip\s*=\s*"\*"', filter_text, re.IGNORECASE))
    if filter_text and not filters and filter_text != '*' and not wildcard_query:
        raise ValueError('Use supported filters such as source_ip="203.0.113.5" or risk_level="HIGH"')
    for part in parts[1:]:
        tokens = part.split()
        command = tokens[0].lower()
        if command == 'stats' and len(tokens) == 4 and tokens[1].lower() == 'count' and tokens[2].lower() == 'by':
            group_by = tokens[3].lower()
        elif command == 'sort' and len(tokens) == 2:
            sort_token = tokens[1]
            descending = sort_token.startswith('-')
            sort_field = sort_token.lstrip('-+')
        elif command in {'head', 'limit'} and len(tokens) == 2:
            limit = int(tokens[1])
        else:
            raise ValueError(f'Unsupported query command: {part}')
    return filters, group_by, sort_field, descending, max(1, min(limit, 1000))


@asynccontextmanager
async def lifespan(_app):
    global rf_model
    if MODEL_PATH.exists():
        rf_model = joblib.load(MODEL_PATH)
    yield


app.router.lifespan_context = lifespan


def _valid_ip(value: str) -> str:
    try:
        return str(ipaddress.ip_address(value))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail='IP address is invalid') from exc


def _since(minutes: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(minutes=minutes)).isoformat()


def detect_attack(features: List[float]) -> Dict:
    values = np.asarray(features, dtype=float).reshape(1, -1)
    if rf_model is None:
        raise HTTPException(status_code=503, detail='Random Forest model is not loaded')
    prediction = int(rf_model.predict(values)[0])
    probabilities = rf_model.predict_proba(values)[0]
    classes = list(rf_model.classes_)
    attack_probability = float(probabilities[classes.index(1)]) if 1 in classes else 0.0
    is_attack = prediction == 1
    confidence = attack_probability if is_attack else 1.0 - attack_probability
    risk = 'CRITICAL' if is_attack and confidence >= 0.9 else 'HIGH' if is_attack and confidence >= 0.7 else 'MEDIUM' if is_attack else 'LOW'
    return {
        'is_attack': is_attack,
        'confidence': round(confidence, 6),
        'risk_level': risk,
        'votes': {'random_forest': 'attack' if is_attack else 'normal'},
    }


@app.get('/')
async def root():
    return {'system': 'CIDRS', 'status': 'operational', 'version': app.version}


@app.get('/health')
async def health_check():
    return {'status': 'healthy' if rf_model is not None else 'degraded', 'model_loaded': rf_model is not None}


@app.post('/detect')
async def detect(traffic: TrafficData):
    source_ip = _valid_ip(traffic.source_ip)
    detection = detect_attack(traffic.features)
    timestamp = traffic.timestamp or datetime.now(timezone.utc).isoformat()
    incident = {
        'timestamp': timestamp,
        'source_ip': source_ip,
        'is_attack': detection['is_attack'],
        'confidence': detection['confidence'],
        'risk_level': detection['risk_level'],
        'model_votes': json.dumps(detection['votes']),
    }
    saved = engine.log_incident(incident)
    auto_blocked = False
    if detection['is_attack'] and detection['risk_level'] == 'CRITICAL':
        engine.block_ip(source_ip, detection['risk_level'], 'Automatic critical-risk response', automatic=True)
        auto_blocked = True
    return {**incident, 'model_votes': detection['votes'], 'incident_id': saved['incident_id'], 'auto_blocked': auto_blocked}


@app.get('/alerts')
async def get_alerts(limit: int = Query(100, ge=1, le=1000), minutes: int = Query(10080, ge=1, le=525600)):
    incidents = engine.get_recent_incidents(limit=limit, since=_since(minutes))
    return {'incidents': incidents, 'total': len(incidents)}


@app.get('/stats')
async def get_stats(minutes: int = Query(60, ge=1, le=525600)):
    stats = engine.get_stats(since=_since(minutes))
    stats.update({'server': 'AWS' if engine.use_aws else 'LOCAL', 'model_loaded': rf_model is not None})
    return stats


@app.get('/blocks')
async def get_blocks():
    return {'blocks': engine.list_blocked()}


@app.post('/blocks')
async def create_block(request: BlockRequest):
    ip = _valid_ip(request.ip)
    risk = request.risk.upper()
    if risk not in {'MEDIUM', 'HIGH', 'CRITICAL'}:
        raise HTTPException(status_code=422, detail='risk must be MEDIUM, HIGH, or CRITICAL')
    return engine.block_ip(ip, risk, request.reason[:200])


@app.delete('/blocks/{ip}')
async def delete_block(ip: str):
    valid_ip = _valid_ip(ip)
    if not engine.unblock_ip(valid_ip):
        raise HTTPException(status_code=404, detail='IP is not blocked')
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
    try:
        filters, group_by, sort_field, descending, limit = parse_search_query(request.query)
        rows = engine.search_incidents(filters, group_by, sort_field, descending, limit)
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {'query': request.query, 'rows': rows, 'count': len(rows), 'grouped': bool(group_by)}


@app.get('/system')
async def system_metrics():
    load = os.getloadavg()[0] if hasattr(os, 'getloadavg') else 0.0
    cpu_count = os.cpu_count() or 1
    memory_percent = None
    meminfo = Path('/proc/meminfo')
    if meminfo.exists():
        values = {}
        for line in meminfo.read_text().splitlines():
            key, value = line.split(':', 1)
            values[key] = int(value.strip().split()[0])
        total = values.get('MemTotal', 0)
        available = values.get('MemAvailable', 0)
        memory_percent = round((1 - available / total) * 100, 1) if total else None
    uptime = 0.0
    uptime_file = Path('/proc/uptime')
    if uptime_file.exists():
        uptime = float(uptime_file.read_text().split()[0])
    recent = engine.get_recent_incidents(limit=1000, since=_since(1))
    return {
        'cpu_percent': round(min(load / cpu_count * 100, 100), 1),
        'memory_percent': memory_percent,
        'events_per_second': round(len(recent) / 60, 2),
        'uptime_seconds': uptime,
    }


@app.get('/model/metrics')
async def model_metrics():
    if not METRICS_PATH.exists():
        raise HTTPException(status_code=404, detail='Model metrics are unavailable')
    metrics = json.loads(METRICS_PATH.read_text())
    importance = rf_model.feature_importances_.tolist() if rf_model is not None and hasattr(rf_model, 'feature_importances_') else []
    return {
        'model': 'random_forest',
        'metrics': metrics,
        'feature_names': metrics.get('feature_names', []),
        'feature_importance': importance,
    }


if __name__ == '__main__':
    import uvicorn
    uvicorn.run('src.api.main:app', host='0.0.0.0', port=8000, reload=True)
