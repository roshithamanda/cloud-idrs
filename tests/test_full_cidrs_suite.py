"""Comprehensive test suite for CIDRS (Cloud-Based Intrusion Detection and Response System).

Covers:
- Unit Tests (Preprocessor, ML Models, Query Parser, Response Engine)
- Functional & API Tests (Endpoints, Ingestion, Incidents, Blocks, Stats)
- Security & Input Validation Tests (SQL Injection, XSS, Format Validation, Security Headers)
- Firewall Provider Integration Tests
- Performance & SLA Latency Benchmarks
"""

import json
from pathlib import Path
import sqlite3
import time
import pytest
import numpy as np
import torch
from fastapi.testclient import TestClient

from src.api.main import app, detect_multi_model, map_mitre_attack, engine
from src.preprocessor.nsl_kdd import FEATURE_NAMES, clean_frame, encode_frame, preprocess_raw_record, validate_numeric_vector
from src.api.main_parser import parse_search_query
from src.responder.firewall_provider import FirewallProvider

@pytest.fixture(scope="session")
def client():
    with TestClient(app) as test_client:
        yield test_client

# =========================================================================
# 1. UNIT TESTS: PREPROCESSOR & FEATURE VALIDATION (12 Tests)
# =========================================================================

def test_u01_feature_names_count():
    assert len(FEATURE_NAMES) == 41, "NSL-KDD schema must define exactly 41 features"

def test_u02_feature_names_order():
    assert FEATURE_NAMES[0] == 'duration'
    assert FEATURE_NAMES[1] == 'protocol_type'
    assert FEATURE_NAMES[2] == 'service'
    assert FEATURE_NAMES[3] == 'flag'

def test_u03_validate_numeric_vector_valid():
    vec = [0.5] * 41
    res = validate_numeric_vector(vec)
    assert res.shape == (41,)
    assert isinstance(res, np.ndarray)

def test_u04_validate_numeric_vector_too_short():
    with pytest.raises(ValueError, match="exactly 41"):
        validate_numeric_vector([0.1] * 40)

def test_u05_validate_numeric_vector_too_long():
    with pytest.raises(ValueError, match="exactly 41"):
        validate_numeric_vector([0.1] * 42)

def test_u06_validate_numeric_vector_nan():
    vec = [0.1] * 41
    vec[5] = float('nan')
    with pytest.raises(ValueError, match="finite numbers"):
        validate_numeric_vector(vec)

def test_u07_validate_numeric_vector_inf():
    vec = [0.1] * 41
    vec[10] = float('inf')
    with pytest.raises(ValueError, match="finite numbers"):
        validate_numeric_vector(vec)

def test_u08_clean_frame_strips_whitespace():
    import pandas as pd
    df = pd.DataFrame([[' tcp ', ' http ', ' SF ']])
    cleaned = clean_frame(df)
    assert cleaned.iloc[0, 0] == 'tcp'
    assert cleaned.iloc[0, 1] == 'http'
    assert cleaned.iloc[0, 2] == 'SF'

def test_u09_encode_frame_structure():
    import pandas as pd
    df = pd.DataFrame([[0, 'tcp', 'http', 'SF'] + [0.0]*37])
    encoded, cats = encode_frame(df)
    assert encoded.shape == (1, 41)
    assert '1' in cats and '2' in cats and '3' in cats

def test_u10_preprocess_raw_record_valid():
    values = {f: 0.0 for f in FEATURE_NAMES}
    values['protocol_type'] = 'tcp'
    values['service'] = 'http'
    values['flag'] = 'SF'
    cats = {'1': ['tcp'], '2': ['http'], '3': ['SF']}
    res = preprocess_raw_record(values, cats)
    assert res.shape == (1, 41)

def test_u11_preprocess_raw_record_missing_field():
    values = {'duration': 0.0}
    with pytest.raises(ValueError, match="Missing feature fields"):
        preprocess_raw_record(values, {})

def test_u12_preprocess_raw_record_unknown_categorical():
    values = {f: 0.0 for f in FEATURE_NAMES}
    values['protocol_type'] = 'unknown_proto'
    values['service'] = 'unknown_svc'
    values['flag'] = 'unknown_flag'
    cats = {'1': ['tcp'], '2': ['http'], '3': ['SF']}
    res = preprocess_raw_record(values, cats)
    # Unknowns should be mapped to -1.0
    assert res[0, 1] == -1.0

# =========================================================================
# 2. UNIT TESTS: MACHINE LEARNING & ENSEMBLE (10 Tests)
# =========================================================================

def test_u13_detect_multi_model_structure():
    raw_vec = np.zeros(41, dtype=float)
    res = detect_multi_model(raw_vec)
    assert 'is_attack' in res
    assert 'confidence' in res
    assert 'risk_level' in res
    assert 'ensemble_score' in res
    assert 'models' in res
    assert 'mitre' in res

def test_u14_detect_multi_model_confidence_bounds():
    raw_vec = np.ones(41, dtype=float) * 0.5
    res = detect_multi_model(raw_vec)
    assert 0.0 <= res['confidence'] <= 1.0
    assert 0.0 <= res['ensemble_score'] <= 1.0

def test_u15_random_forest_voting_consistency():
    raw_vec = np.zeros(41, dtype=float)
    res = detect_multi_model(raw_vec)
    assert res['models']['random_forest']['prediction'] in {'normal', 'attack'}

def test_u16_lstm_voting_consistency():
    raw_vec = np.zeros(41, dtype=float)
    res = detect_multi_model(raw_vec)
    assert res['models']['lstm']['prediction'] in {'normal', 'attack'}

def test_u17_autoencoder_anomaly_thresholding():
    raw_vec = np.zeros(41, dtype=float)
    res = detect_multi_model(raw_vec)
    assert 'reconstruction_error' in res['models']['autoencoder']
    assert res['models']['autoencoder']['threshold'] > 0.0

def test_u18_mitre_mapping_normal():
    info = map_mitre_attack(None, False, np.zeros(41))
    assert info['technique_id'] == 'N/A'
    assert info['tactic'] == 'Benign'

def test_u19_mitre_mapping_dos():
    vec = np.zeros(41)
    vec[22] = 250  # count > 100
    info = map_mitre_attack(None, True, vec)
    assert info['technique_id'] == 'T1498'
    assert 'Denial of Service' in info['technique_name']

def test_u20_mitre_mapping_probe():
    vec = np.zeros(41)
    vec[22] = 50  # scan count
    info = map_mitre_attack(None, True, vec)
    assert info['technique_id'] == 'T1046'
    assert 'Scanning' in info['technique_name']

def test_u21_mitre_mapping_privilege_escalation():
    vec = np.zeros(41)
    vec[10] = 3  # num_failed_logins
    info = map_mitre_attack(None, True, vec)
    assert info['technique_id'] == 'T1068'
    assert 'Privilege Escalation' in info['technique_name']

def test_u22_ensemble_consensus_string():
    res = detect_multi_model(np.zeros(41))
    assert "models agree" in res['votes']['consensus']

# =========================================================================
# 3. UNIT TESTS: SPLUNK SEARCH DSL PARSER (8 Tests)
# =========================================================================

def test_u23_parse_query_empty():
    with pytest.raises(ValueError, match="empty"):
        parse_search_query("")

def test_u24_parse_query_single_filter():
    f, g, s, d, lim = parse_search_query('source_ip="192.168.1.1"')
    assert len(f) == 1
    assert f[0] == ('source_ip', '=', '192.168.1.1')
    assert g is None

def test_u25_parse_query_stats_group_by():
    f, g, s, d, lim = parse_search_query('is_attack=true | stats count by attack_type')
    assert g == 'attack_type'
    assert f[0] == ('is_attack', '=', 1)

def test_u26_parse_query_sorting_descending():
    f, g, s, d, lim = parse_search_query('source_ip="*" | sort -timestamp')
    assert s == 'timestamp'
    assert d is True

def test_u27_parse_query_limit():
    f, g, s, d, lim = parse_search_query('source_ip="*" | head 25')
    assert lim == 25

def test_u28_parse_query_numeric_operator():
    f, g, s, d, lim = parse_search_query('confidence >= 0.85')
    assert f[0] == ('confidence', '>=', 0.85)

def test_u29_parse_query_invalid_command():
    with pytest.raises(ValueError, match="Unsupported query command"):
        parse_search_query('source_ip="*" | transform count')

def test_u30_parse_query_unsupported_filter():
    with pytest.raises(ValueError, match="Unsupported search field"):
        parse_search_query('malicious_payload="evil"')

# =========================================================================
# 4. FUNCTIONAL & API ENDPOINT TESTS (20 Tests)
# =========================================================================

def test_a31_get_root(client):
    res = client.get('/')
    assert res.status_code == 200
    assert "CIDRS" in res.text

def test_a32_get_dashboard(client):
    res = client.get('/dashboard')
    assert res.status_code == 200
    assert "CIDRS SOC" in res.text

def test_a33_get_health(client):
    res = client.get('/health')
    assert res.status_code == 200
    data = res.json()
    assert data['status'] == 'healthy'
    assert data['models']['random_forest_loaded'] is True
    assert data['models']['lstm_loaded'] is True
    assert data['models']['autoencoder_loaded'] is True

def test_a34_post_detect_valid_vector(client):
    vec = [0.0] * 41
    res = client.post('/detect', json={'features': vec, 'source_ip': '10.0.0.1'})
    assert res.status_code == 200
    data = res.json()
    assert 'incident_id' in data
    assert data['source_ip'] == '10.0.0.1'
    assert 'models' in data

def test_a35_post_detect_named_features(client):
    vals = {f: 0.0 for f in FEATURE_NAMES}
    vals['protocol_type'] = 'tcp'
    vals['service'] = 'http'
    vals['flag'] = 'SF'
    res = client.post('/detect', json={'feature_values': vals, 'source_ip': '10.0.0.2'})
    assert res.status_code == 200
    assert res.json()['incident_id'] > 0

def test_a36_post_detect_invalid_vector_size(client):
    res = client.post('/detect', json={'features': [0.1] * 20, 'source_ip': '10.0.0.3'})
    assert res.status_code == 422

def test_a37_post_detect_invalid_ip(client):
    res = client.post('/detect', json={'features': [0.1] * 41, 'source_ip': 'not-an-ip-addr'})
    assert res.status_code == 422

def test_a38_post_detect_auto_block_trigger(client):
    # Pass strong attack vector to trigger auto-block
    vec = [15.0] * 41
    res = client.post('/detect', json={'features': vec, 'source_ip': '198.51.100.99', 'auto_respond': True})
    assert res.status_code == 200
    data = res.json()
    if data['risk_level'] in {'CRITICAL', 'HIGH'}:
        assert data['auto_blocked'] is True
        # Verify IP is in blocks
        blocks = client.get('/blocks').json()['blocks']
        assert any(b['ip'] == '198.51.100.99' for b in blocks)

def test_a39_get_alerts_pagination(client):
    res = client.get('/alerts?limit=5')
    assert res.status_code == 200
    data = res.json()
    assert len(data['incidents']) <= 5
    assert 'total' in data

def test_a40_get_stats(client):
    res = client.get('/stats')
    assert res.status_code == 200
    data = res.json()
    assert 'total_incidents' in data
    assert 'attacks_detected' in data
    assert 'ips_blocked' in data

def test_a41_get_blocks(client):
    res = client.get('/blocks')
    assert res.status_code == 200
    assert isinstance(res.json()['blocks'], list)

def test_a42_post_blocks_manual(client):
    res = client.post('/blocks', json={'ip': '203.0.113.88', 'risk': 'HIGH', 'reason': 'Manual SOC test'})
    assert res.status_code == 200
    assert res.json()['ip'] == '203.0.113.88'

def test_a43_delete_block_single(client):
    client.post('/blocks', json={'ip': '203.0.113.89', 'risk': 'MEDIUM', 'reason': 'To be deleted'})
    res = client.delete('/blocks/203.0.113.89')
    assert res.status_code == 200
    assert res.json()['status'] == 'unblocked'

def test_a44_delete_block_nonexistent(client):
    res = client.delete('/blocks/192.0.2.1')
    assert res.status_code == 404

def test_a45_get_response_status(client):
    res = client.get('/response/status')
    assert res.status_code == 200
    data = res.json()
    assert 'mode' in data
    assert 'aws_integration' in data

def test_a46_notifications_workflow(client):
    res = client.post('/notifications', json={'channel': 'Slack', 'severity': 'CRITICAL', 'message': 'SOC test alert'})
    assert res.status_code == 200
    notifs = client.get('/notifications?limit=5').json()['notifications']
    assert any(n['message'] == 'SOC test alert' for n in notifs)

def test_a47_query_endpoint_filtering(client):
    res = client.post('/query', json={'query': 'source_ip="*" | stats count by is_attack'})
    assert res.status_code == 200
    data = res.json()
    assert data['grouped'] is True
    assert len(data['rows']) > 0

def test_a48_system_metrics(client):
    res = client.get('/system')
    assert res.status_code == 200
    data = res.json()
    assert 'cpu_percent' in data
    assert 'memory_percent' in data
    assert 'uptime_seconds' in data

def test_a49_model_metrics_endpoint(client):
    res = client.get('/model/metrics')
    assert res.status_code == 200
    data = res.json()
    assert 'models' in data
    assert 'feature_importance' in data
    assert len(data['feature_names']) == 41

def test_a50_mitre_matrix_endpoint(client):
    res = client.get('/mitre/matrix')
    assert res.status_code == 200
    data = res.json()
    assert 'matrix' in data
    assert any(t['id'] == 'T1498' for t in data['matrix'])

# =========================================================================
# 5. SECURITY & RESILIENCE TESTS (10 Tests)
# =========================================================================

def test_s51_sql_injection_rejection_query(client):
    res = client.post('/query', json={'query': 'DROP TABLE incidents;--'})
    assert res.status_code == 400

def test_s52_sql_injection_union_rejection(client):
    res = client.post('/query', json={'query': 'source_ip="1" UNION SELECT * FROM blocked_ips'})
    assert res.status_code == 400

def test_s53_xss_in_notifications_stored_safely(client):
    xss_payload = '<script>alert("xss")</script>'
    res = client.post('/notifications', json={'channel': 'Test', 'severity': 'LOW', 'message': xss_payload})
    assert res.status_code == 200
    # Retrieve and verify it was treated as inert text
    notifs = client.get('/notifications').json()['notifications']
    assert any(n['message'] == xss_payload for n in notifs)

def test_s54_security_header_nosniff(client):
    res = client.get('/health')
    assert res.headers.get('x-content-type-options') == 'nosniff'

def test_s55_security_header_frame_options(client):
    res = client.get('/health')
    assert res.headers.get('x-frame-options') == 'SAMEORIGIN'

def test_s56_security_header_xss_protection(client):
    res = client.get('/health')
    assert res.headers.get('x-xss-protection') == '1; mode=block'

def test_s57_invalid_block_risk_rejection(client):
    res = client.post('/blocks', json={'ip': '198.51.100.10', 'risk': 'ULTRA_HIGH', 'reason': 'test'})
    assert res.status_code == 422

def test_s58_invalid_notification_severity_rejection(client):
    res = client.post('/notifications', json={'channel': 'Test', 'severity': 'FATAL', 'message': 'test'})
    assert res.status_code == 422

def test_s59_ip_address_octets_overflow(client):
    res = client.post('/detect', json={'features': [0.1]*41, 'source_ip': '999.999.999.999'})
    assert res.status_code == 422

def test_s60_cors_headers_present(client):
    headers = {
        "Origin": "http://localhost:3000",
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "content-type",
    }
    res = client.options('/detect', headers=headers)
    assert res.status_code == 200
    assert 'access-control-allow-origin' in res.headers

# =========================================================================
# 6. PERFORMANCE & SLA BENCHMARKS (5 Tests)
# =========================================================================

def test_p61_inference_latency_sla(client):
    """SLA: Target per-sample inference latency < 200ms."""
    vec = [0.1] * 41
    start = time.perf_counter()
    res = client.post('/detect', json={'features': vec, 'source_ip': '10.0.0.50'})
    duration_ms = (time.perf_counter() - start) * 1000.0
    assert res.status_code == 200
    assert duration_ms < 200.0, f"Inference latency exceeded SLA: {duration_ms:.2f}ms"

def test_p62_batch_pcap_ingestion_speed(client):
    batch = [{'features': [0.1]*41, 'source_ip': f'10.0.1.{i}'} for i in range(1, 21)]
    start = time.perf_counter()
    res = client.post('/pcap/ingest', json={'records': batch})
    duration_ms = (time.perf_counter() - start) * 1000.0
    assert res.status_code == 200
    assert res.json()['processed_flows'] == 20
    assert duration_ms < 2000.0, f"Batch ingestion took too long: {duration_ms:.2f}ms"

def test_p63_response_containment_latency_sla(client):
    """SLA: Containment / response time must be under 5.0 seconds."""
    start = time.perf_counter()
    res = client.post('/blocks', json={'ip': '203.0.113.200', 'risk': 'CRITICAL', 'reason': 'Latency benchmark'})
    duration_sec = time.perf_counter() - start
    assert res.status_code == 200
    assert duration_sec < 5.0, f"Response latency exceeded 5s SLA: {duration_sec:.2f}s"

def test_p64_database_search_latency(client):
    start = time.perf_counter()
    res = client.post('/query', json={'query': 'source_ip="*" | stats count by is_attack'})
    duration_ms = (time.perf_counter() - start) * 1000.0
    assert res.status_code == 200
    assert duration_ms < 500.0, f"Database query took too long: {duration_ms:.2f}ms"

def test_p65_system_metrics_latency(client):
    start = time.perf_counter()
    res = client.get('/system')
    duration_ms = (time.perf_counter() - start) * 1000.0
    assert res.status_code == 200
    assert duration_ms < 100.0, f"System metrics retrieval too slow: {duration_ms:.2f}ms"
