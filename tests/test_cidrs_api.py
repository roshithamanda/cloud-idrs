import joblib
import numpy as np
from fastapi.testclient import TestClient

from src.api import main
from src.responder.response_engine import ResponseEngine


def make_client(tmp_path, monkeypatch):
    monkeypatch.setattr(main, 'engine', ResponseEngine(db_path=tmp_path / 'test.db'))
    monkeypatch.setattr(main, 'rf_model', joblib.load(main.MODEL_PATH))
    return TestClient(main.app)


def test_detection_is_persisted_and_reported(tmp_path, monkeypatch):
    client = make_client(tmp_path, monkeypatch)
    response = client.post('/detect', json={'features': np.full(41, 0.9).tolist(), 'source_ip': '198.51.100.10'})

    assert response.status_code == 200
    result = response.json()
    assert result['incident_id'] > 0
    assert result['model_votes']['random_forest'] in {'attack', 'normal'}

    alerts = client.get('/alerts?minutes=10080').json()
    assert alerts['total'] == 1
    assert alerts['incidents'][0]['source_ip'] == '198.51.100.10'


def test_blocklist_and_notifications_are_persistent(tmp_path, monkeypatch):
    client = make_client(tmp_path, monkeypatch)

    block = client.post('/blocks', json={'ip': '203.0.113.5', 'risk': 'HIGH', 'reason': 'test'} )
    assert block.status_code == 200
    assert client.get('/blocks').json()['blocks'][0]['ip'] == '203.0.113.5'

    notification = client.post('/notifications', json={'channel': 'Email', 'severity': 'HIGH', 'message': 'test alert'})
    assert notification.status_code == 200
    assert client.get('/notifications').json()['notifications'][0]['message'] == 'test alert'

    assert client.delete('/blocks/203.0.113.5').status_code == 200
    assert client.get('/blocks').json()['blocks'] == []


def test_invalid_detection_input_is_rejected(tmp_path, monkeypatch):
    client = make_client(tmp_path, monkeypatch)
    response = client.post('/detect', json={'features': [0.1], 'source_ip': 'not-an-ip'})
    assert response.status_code == 422


def test_splunk_style_filters_and_stats(tmp_path, monkeypatch):
    client = make_client(tmp_path, monkeypatch)
    for ip, values in [('198.51.100.20', 0.9), ('198.51.100.21', 0.1)]:
        assert client.post('/detect', json={'features': np.full(41, values).tolist(), 'source_ip': ip}).status_code == 200

    grouped = client.post('/query', json={'query': 'source_ip="*" | stats count by attack_type | sort -count'} )
    assert grouped.status_code == 200
    assert grouped.json()['grouped'] is True
    assert sum(row['count'] for row in grouped.json()['rows']) == 2

    invalid = client.post('/query', json={'query': 'DROP TABLE incidents'} )
    assert invalid.status_code == 400
