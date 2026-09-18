# CIDRS

**Cloud Intrusion Detection and Response System**

CIDRS is an academic intrusion detection and response platform built around a reproducible machine-learning pipeline, a FastAPI inference service, persistent SQLite audit state, and an operational security dashboard.

## What Is Implemented

- Binary attack detection using a Random Forest trained on the official NSL-KDD train split.
- Evaluation against the official NSL-KDD test split, with accuracy, precision, recall, F1, ROC-AUC, FPR, FNR, confusion-matrix counts, and inference latency.
- FastAPI endpoints for detection, health, incidents, statistics, blocklist operations, saved queries, notifications, model metrics, and host metrics.
- SQLite persistence for incidents, blocked IPs, and notification events.
- Automatic blocking for CRITICAL model decisions and manual operator blocking.
- Standalone Chart.js dashboard backed by the API rather than browser-only mock state.
- Database migration for older incident databases.

## Capabilities and Functions

### Machine Learning Detection

- Accepts a 41-feature NSL-KDD network-flow vector through `/detect`.
- Also accepts named raw NSL-KDD fields through `feature_values`, using the same categorical mappings as training.
- Classifies the event as `NORMAL` or `ATTACK` using the trained Random Forest.
- Returns a confidence score, risk level, model vote, timestamp, and incident ID.
- Assigns `LOW`, `MEDIUM`, `HIGH`, or `CRITICAL` risk from the attack prediction confidence.
- Stores every prediction in SQLite for later investigation and reporting.
- Exposes feature importance and evaluation metrics through `/model/metrics`.

The shared preprocessing code is in `src/preprocessor/nsl_kdd.py`. It defines the 41-field schema, strips dataset values consistently, encodes `protocol_type`, `service`, and `flag`, and rejects missing or non-finite values. This module is used by both `scripts/train_random_forest.py` and the API.

### Incident Monitoring

- Lists persisted incidents through `/alerts`.
- Filters incident history by time window and result count.
- Reports total incidents, detected attacks, and active blocked IPs through `/stats`.
- Shows attack rate, confidence, risk distribution, top source IPs, and incident timeline in the dashboard.
- Provides a live API health state through `/health` and automatic dashboard refresh.

### Splunk-Style Investigation

- Searches persisted incident data from the dashboard search bar.
- Supports field filters for source IP, attack state, risk level, confidence, and timestamp.
- Supports aggregation with `stats count by`.
- Supports ordering with `sort` and result limits with `head` or `limit`.
- Rejects unsupported commands and arbitrary SQL; search values are passed as SQLite parameters.
- Displays returned events or grouped counts in the dashboard query panel.

### Automated Response

- Automatically adds CRITICAL detections to the persistent blocklist.
- Allows analysts to manually block a validated IP address.
- Allows analysts to unblock one IP or clear the complete blocklist.
- Records block time, risk, reason, and whether the action was automatic.
- Persists notification events for audit history.
- Provides response-rule controls in the dashboard, with AWS WAF clearly marked as not configured in this local release.

### Security Operations Dashboard

- Overview page with KPIs, traffic charts, threat classification, incidents, risk levels, and system health.
- ML Insights page with accuracy, precision, recall, inference latency, feature importance, and confusion matrix.
- Auto-Response page with active blocks, manual blocking, response rules, and audit state.
- Alerts and Notifications page with notification channels and persisted notification history.
- System page with API host metrics, memory, CPU, uptime, and ingestion rate.
- MITRE ATT&CK reference view for organizing detection coverage and investigation context.

### API and Persistence

- FastAPI provides typed request validation and JSON responses.
- SQLite stores incidents, blocked IPs, and notifications across service restarts.
- Existing incident databases are migrated automatically when new columns are required.
- CORS origins can be restricted with `CIDRS_ALLOWED_ORIGINS`.
- IP addresses are validated with Python's standard `ipaddress` module.

### Deliberate Limitations

- The active model is a binary Random Forest classifier; LSTM and autoencoder artifacts are not active API models yet.
- The service expects engineered 41-feature vectors, not raw packets or live network interfaces.
- The local response engine records blocks but does not change an external firewall or AWS WAF.
- SQLite is suitable for demonstration and a single-node project deployment, not high-volume SOC production.
- Authentication, HTTPS termination, email delivery, Slack delivery, and cloud enforcement require deployment-specific configuration.

## Architecture

```text
NSL-KDD data -> training script -> Random Forest artifact + metrics
                                      |
Traffic features -> FastAPI /detect -> SQLite incidents
                                      |             |
                                      +-> response engine -> blocklist
                                      |
                                      +-> dashboard API clients
```

The current release is a binary classifier. The LSTM and autoencoder folders are retained as research artifacts, but they are not presented as active production inference paths until they have reproducible training scripts, evaluation results, and API integration.

## Measured Baseline

The checked-in model is regenerated with:

```bash
venv/bin/python scripts/train_random_forest.py
```

The current official NSL-KDD test-split results are written to `models/random_forest/metrics.json`. They should be regenerated after any data, preprocessing, or model change. The dashboard reads the same artifact for its ML view.

Current baseline results:

| Metric | Result |
| --- | ---: |
| Accuracy | 77.32% |
| Precision | 96.71% |
| Recall | 62.28% |
| F1 score | 75.77% |
| ROC-AUC | 96.42% |
| False-positive rate | 2.80% |
| Inference latency | 0.0065 ms/sample |

Recall is reported alongside precision because missed attacks are a significant IDS risk. These results are benchmark measurements on NSL-KDD, not a claim of production-cloud performance.

## Setup

```bash
python3 -m venv venv
venv/bin/pip install -r requirements.txt
```

The repository includes the NSL-KDD files under `data/raw/NSL-KDD/`. If they are absent in another checkout, download the official dataset and place `KDDTrain+.txt` and `KDDTest+.txt` there.

## Train and Run

```bash
venv/bin/python scripts/train_random_forest.py
venv/bin/uvicorn src.api.main:app --host 127.0.0.1 --port 8000
```

Open `dashboard_final.html` directly for a local dashboard. When served from another origin, set the API URL before loading the page:

```html
<script>window.CIDRS_API_URL = 'http://127.0.0.1:8000';</script>
```

For a deployed environment, set `CIDRS_ALLOWED_ORIGINS` to an explicit comma-separated allowlist. Do not expose the development API directly to the public internet without authentication, HTTPS, and network controls.

## API Surface

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `GET` | `/health` | Service and model readiness |
| `POST` | `/detect` | Validate and classify 41 numeric features |
| `GET` | `/alerts` | Read persisted incidents |
| `GET` | `/stats` | Time-windowed incident statistics |
| `GET/POST/DELETE` | `/blocks` | Manage the persistent blocklist |
| `GET/POST` | `/notifications` | Persist notification events |
| `POST` | `/query` | Run the supported incident query syntax |
| `GET` | `/model/metrics` | Read model metrics and feature importance |
| `GET` | `/system` | Read host and ingestion metrics |

### Search Examples

The dashboard search bar supports a safe incident-search subset inspired by Splunk SPL:

```text
source_ip="203.0.113.5"
is_attack=true | sort -confidence | head 20
risk_level="HIGH" | stats count by source_ip | sort -count
source_ip="*" | stats count by attack_type
```

Supported filter fields are `source_ip`, `is_attack`, `risk_level`, `confidence`, and `timestamp`. Supported pipeline commands are `stats count by`, `sort`, and `head`/`limit`. Queries are parsed into parameterized SQLite statements; arbitrary SQL is rejected.

Example detection request:

```bash
curl -X POST http://127.0.0.1:8000/detect \
  -H 'Content-Type: application/json' \
  -d '{"features":[0.1,0.1,0.1,0.1,0.1,0.1,0.1,0.1,0.1,0.1,0.1,0.1,0.1,0.1,0.1,0.1,0.1,0.1,0.1,0.1,0.1,0.1,0.1,0.1,0.1,0.1,0.1,0.1,0.1,0.1,0.1,0.1,0.1,0.1,0.1,0.1,0.1,0.1,0.1,0.1,0.1],"source_ip":"192.0.2.10"}'
```

## Tests and Validation

Run the API and persistence tests:

```bash
venv/bin/pip install -r requirements.txt
venv/bin/python -m pytest -q
```

The four tests use temporary SQLite databases and verify detection persistence, blocklist operations, notifications, invalid-input rejection, grouped searches, and arbitrary-query rejection.

## Demonstration Workflow

1. Start the API and open `dashboard_final.html`.
2. Use **Simulate Attack** or **Normal Traffic** to create real model decisions.
3. Open **Incidents** and verify the persisted event and risk level.
4. Search with `is_attack=true | sort -confidence | head 20`.
5. Open **Auto-Response** to review or manually block an IP.
6. Use `risk_level="HIGH" | stats count by source_ip` to summarize attack sources.
7. Open **ML Insights** to show the model metrics and confusion matrix.

## Security Notes

- Input IP addresses are validated with Python's `ipaddress` module.
- Feature vectors must contain exactly 41 numeric values.
- SQL operations use parameterized queries.
- CORS can be restricted with `CIDRS_ALLOWED_ORIGINS`.
- Secrets are not required by the local implementation and must not be committed.
- AWS blocking is intentionally not claimed as implemented; the local response engine is the active response provider.

## Academic Presentation Structure

1. Explain the threat model and why NSL-KDD is a benchmark rather than live cloud telemetry.
2. Show the preprocessing and official train/test evaluation protocol.
3. Present the confusion matrix, ROC-AUC, false-positive rate, and false-negative rate rather than accuracy alone.
4. Demonstrate a real `/detect` request, persisted incident, automatic critical response, manual block, and dashboard refresh.
5. State limitations clearly: binary classification, engineered feature input, SQLite single-node persistence, and no production AWS enforcement yet.

## Project Layout

```text
src/api/main.py                    FastAPI service and model inference
src/responder/response_engine.py   SQLite incident and response state
scripts/train_random_forest.py     Reproducible NSL-KDD training/evaluation
models/random_forest/              Model artifact and measured metrics
data/raw/NSL-KDD/                  Training and official test data
tests/test_cidrs_api.py            API and persistence tests
dashboard_final.html               API-backed security dashboard
```
