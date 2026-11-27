"""Generate publication-grade technical and architectural diagrams for CIDRS.

Produces 18 distinct diagrams required for the final project report:
1. High-Level System Architecture
2. Physical and Logical Network Topology
3. AWS Cloud Infrastructure Architecture
4. Machine Learning Training Pipeline
5. Dataset Preprocessing Workflow
6. Intrusion Detection & Threat Scoring Workflow
7. Multi-Model Ensemble Voting Architecture
8. Automated Response & Mitigation Workflow
9. Data Flow Diagram Level 0 (Context Diagram)
10. Data Flow Diagram Level 1 (Decomposition)
11. Database Entity-Relationship (ER) Diagram
12. System Use Case Diagram
13. Detection & Response Sequence Diagram
14. REST API Modular Architecture
15. Multi-Layer Security Architecture
16. Container & Production Deployment Architecture
17. Initial Project Gantt Chart (Proposal Plan)
18. Actual Project Gantt Chart (As-Built Execution)
"""

import os
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import numpy as np

OUT_DIR = Path('assesments/final-submission/diagrams')
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Common styling constants
BG_COLOR = '#0f172a'       # Slate 900
PANEL_BG = '#1e293b'       # Slate 800
BORDER_COL = '#334155'     # Slate 700
TEXT_MAIN = '#f8fafc'      # Slate 50
TEXT_MUTED = '#94a3b8'     # Slate 400
ACCENT_BLUE = '#38bdf8'    # Sky 400
ACCENT_CYAN = '#2dd4bf'    # Teal 400
ACCENT_GREEN = '#4ade80'   # Green 400
ACCENT_RED = '#f87171'     # Red 400
ACCENT_PURPLE = '#c084fc'  # Purple 400
ACCENT_GOLD = '#fbbf24'    # Amber 400

plt.rcParams['font.sans-serif'] = 'DejaVu Sans'
plt.rcParams['font.family'] = 'sans-serif'


def create_base_canvas(figsize=(12, 7), title="", subtitle=""):
    fig, ax = plt.subplots(figsize=figsize, dpi=300)
    fig.patch.set_facecolor(BG_COLOR)
    ax.set_facecolor(BG_COLOR)
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.axis('off')
    
    # Title
    if title:
        ax.text(50, 95, title, color=TEXT_MAIN, fontsize=14, fontweight='bold', ha='center', va='center')
    if subtitle:
        ax.text(50, 91.5, subtitle, color=TEXT_MUTED, fontsize=10, ha='center', va='center')
    return fig, ax


def draw_box(ax, x, y, w, h, title, lines=None, color=ACCENT_BLUE, bg=PANEL_BG, fontsize=10):
    rect = patches.FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.6,rounding_size=1.2",
                                  facecolor=bg, edgecolor=color, linewidth=1.5, zorder=2)
    ax.add_patch(rect)
    ax.text(x + w/2, y + h - 3, title, color=color, fontsize=fontsize, fontweight='bold', ha='center', va='top', zorder=3)
    if lines:
        for idx, line in enumerate(lines):
            ax.text(x + w/2, y + h - 7 - (idx * 3.2), line, color=TEXT_MAIN, fontsize=fontsize-1.5, ha='center', va='top', zorder=3)


def draw_arrow(ax, x1, y1, x2, y2, color=TEXT_MUTED, label="", lw=1.5):
    ax.annotate("", xy=(x2, y2), xytext=(x1, y1),
                arrowprops=dict(arrowstyle="->", color=color, lw=lw, shrinkA=5, shrinkB=5), zorder=4)
    if label:
        mx, my = (x1 + x2)/2, (y1 + y2)/2
        ax.text(mx, my + 1.5, label, color=color, fontsize=8, ha='center', va='bottom',
                bbox=dict(boxstyle="round,pad=0.2", facecolor=BG_COLOR, edgecolor='none', alpha=0.8), zorder=5)


# 1. High-Level System Architecture
def gen_01():
    fig, ax = create_base_canvas(title="Figure 5.1: CIDRS High-Level System Architecture (4-Layer Model)",
                                subtitle="End-to-End Ingestion, Detection, Response, and Presentation Architecture")
    # Layer 1
    draw_box(ax, 4, 15, 20, 68, "Layer 1: Ingestion",
             ["AWS VPC Flow Logs", "PCAP / Scapy Sniffer", "Raw Socket Listener", "JSON Traffic Telemetry", "Feature Extraction (41)"],
             ACCENT_CYAN)
    # Layer 2
    draw_box(ax, 27, 15, 22, 68, "Layer 2: ML Analytics",
             ["StandardScaler Scaling", "Categorical Encoders", "Random Forest (Known)", "LSTM (Temporal)", "Autoencoder (Zero-Day)", "Ensemble Voting Logic"],
             ACCENT_PURPLE)
    # Layer 3
    draw_box(ax, 52, 15, 20, 68, "Layer 3: Core & Response",
             ["FastAPI Microservice", "SQLite Incidents DB", "Automated Mitigation", "Local nftables Provider", "AWS SecGroup Provider", "Threat Risk Scoring"],
             ACCENT_RED)
    # Layer 4
    draw_box(ax, 75, 15, 21, 68, "Layer 4: SOC Dashboard",
             ["Enterprise SOC Portal", "Real-time KPI Feed", "MITRE ATT&CK Matrix", "Threat Map & Analytics", "Manual Block Actions", "Splunk Search Engine"],
             ACCENT_GREEN)

    draw_arrow(ax, 24, 50, 27, 50, ACCENT_CYAN, "Extracted Vectors")
    draw_arrow(ax, 49, 50, 52, 50, ACCENT_PURPLE, "Ensemble Decisions")
    draw_arrow(ax, 72, 50, 75, 50, ACCENT_GREEN, "REST / WebSockets")
    plt.tight_layout()
    plt.savefig(OUT_DIR / '01_high_level_architecture.png')
    plt.close()


# 2. Network Topology
def gen_02():
    fig, ax = create_base_canvas(title="Figure 5.2: CIDRS Physical & Logical Network Topology",
                                subtitle="Network Ingress, Edge Security, Demilitarized Zone (DMZ), and Internal Enclave")
    draw_box(ax, 5, 40, 18, 30, "Public Internet", ["Remote Clients", "Adversaries / Scanners", "External Telemetry"], ACCENT_RED)
    draw_box(ax, 28, 35, 18, 40, "Perimeter Firewall", ["AWS WAF / NAT", "Ingress Filtering", "Port Inspection (80/443)", "Rate Limiting"], ACCENT_GOLD)
    draw_box(ax, 51, 30, 22, 50, "CIDRS Gateway / DMZ", ["Reverse Proxy (NGINX)", "FastAPI Backend (:8000)", "Local nftables Enforcer", "Raw Sniffer (Scapy)"], ACCENT_BLUE)
    draw_box(ax, 78, 35, 18, 40, "Protected Enclave", ["Private Cloud Subnet", "Database (SQLite/Aurora)", "Production Workloads", "Storage & Backups"], ACCENT_GREEN)

    draw_arrow(ax, 23, 55, 28, 55, ACCENT_RED, "Incoming Traffic")
    draw_arrow(ax, 46, 55, 51, 55, ACCENT_GOLD, "Clean Forwarding")
    draw_arrow(ax, 73, 55, 78, 55, ACCENT_BLUE, "Authorized Flow")
    plt.tight_layout()
    plt.savefig(OUT_DIR / '02_network_topology.png')
    plt.close()


# 3. AWS Cloud Architecture
def gen_03():
    fig, ax = create_base_canvas(title="Figure 5.3: CIDRS AWS Cloud Infrastructure Deployment Architecture",
                                subtitle="VPC, Public/Private Subnets, Security Groups, IAM Roles, and CloudWatch Integration")
    # Outer VPC boundary
    rect = patches.FancyBboxPatch((4, 10), 92, 76, boxstyle="round,pad=0.8,rounding_size=1.5",
                                  facecolor='#0b1329', edgecolor=ACCENT_BLUE, linewidth=1.8, linestyle='--', zorder=1)
    ax.add_patch(rect)
    ax.text(6, 83, "AWS Virtual Private Cloud (VPC: 10.0.0.0/16)", color=ACCENT_BLUE, fontsize=10, fontweight='bold', zorder=2)

    draw_box(ax, 8, 20, 24, 55, "Public Subnet (10.0.1.0/24)",
             ["Internet Gateway (IGW)", "Application Load Balancer", "Elastic IP: 3.238.x.x", "Port 80/443 Ingress"], ACCENT_CYAN)
    draw_box(ax, 37, 20, 28, 55, "CIDRS Compute (10.0.2.0/24)",
             ["EC2 Instance (t3.medium)", "Docker Engine Container", "FastAPI Daemon (Uvicorn)", "Ensemble ML In-Memory", "SQLite Persistent Volume"], ACCENT_PURPLE)
    draw_box(ax, 70, 20, 23, 55, "Security & Management",
             ["AWS Security Group Deny", "IAM Role (Least Priv)", "CloudWatch Log Stream", "SNS Alert Topics"], ACCENT_GOLD)

    draw_arrow(ax, 32, 48, 37, 48, ACCENT_CYAN, "Proxy Forward")
    draw_arrow(ax, 65, 48, 70, 48, ACCENT_GOLD, "API Block Dispatch")
    plt.tight_layout()
    plt.savefig(OUT_DIR / '03_aws_cloud_architecture.png')
    plt.close()


# 4. ML Training Pipeline
def gen_04():
    fig, ax = create_base_canvas(title="Figure 5.4: Machine Learning Model Training & Validation Pipeline",
                                subtitle="Data Ingestion, Split, Preprocessing, Cross-Validation, and Weight Serialization")
    draw_box(ax, 4, 38, 16, 35, "Raw Datasets", ["NSL-KDD Official", "KDDTrain+ (125,973)", "KDDTest+ (22,544)", "41 Protocol Features"], ACCENT_CYAN)
    draw_box(ax, 24, 38, 18, 35, "Preprocessing", ["Categorical Encoding", "StandardScaler (Train)", "Zero Leakage Shield", "Normal Partition (AE)"], ACCENT_BLUE)
    draw_box(ax, 46, 15, 24, 70, "Model Training Phase",
             ["Random Forest (200 Trees)", "Balanced Class Weights", "PyTorch LSTM (2 Layers)", "Adam Opt (LR=0.002)", "Autoencoder (Normal)", "MSE Reconstruction", "Threshold Tuning (95%)"], ACCENT_PURPLE)
    draw_box(ax, 74, 38, 22, 35, "Evaluation & Export",
             ["KDDTest+ Evaluation", "Confusion Matrix Grid", "ROC & PR Curves", "Weight Serialization (.pt/.pkl)", "Metrics JSON Manifest"], ACCENT_GREEN)

    draw_arrow(ax, 20, 55, 24, 55, ACCENT_CYAN, "Raw CSV")
    draw_arrow(ax, 42, 55, 46, 55, ACCENT_BLUE, "Tensors")
    draw_arrow(ax, 70, 55, 74, 55, ACCENT_PURPLE, "Artifacts")
    plt.tight_layout()
    plt.savefig(OUT_DIR / '04_ml_training_pipeline.png')
    plt.close()


# 5. Preprocessing Workflow
def gen_05():
    fig, ax = create_base_canvas(title="Figure 5.5: Feature Preprocessing and Dimensional Normalization Workflow",
                                subtitle="String Sanitation, Categorical Encoding, Numerical Normalization, and Verification")
    draw_box(ax, 4, 40, 16, 30, "Raw Network Record", ["41 NSL-KDD Fields", "duration, protocol", "service, flag, src_bytes...", "dst_host counters"], ACCENT_GOLD)
    draw_box(ax, 24, 40, 18, 30, "Categorical Mapping", ["protocol_type (3 vals)", "service (70 vals)", "flag (11 vals)", "Integer Mapping Table"], ACCENT_BLUE)
    draw_box(ax, 46, 40, 20, 30, "Standard Scaling", ["Zero Mean (μ = 0)", "Unit Variance (σ = 1)", "StandardScaler Transform", "Fitted on Train Only"], ACCENT_CYAN)
    draw_box(ax, 70, 40, 25, 30, "Engineered Tensor", ["Normalized Float32 [41]", "Shape (1, 41) or (B, 1, 41)", "Finite Value Validation", "Direct Ingestion Ready"], ACCENT_GREEN)

    draw_arrow(ax, 20, 55, 24, 55, TEXT_MUTED)
    draw_arrow(ax, 42, 55, 46, 55, TEXT_MUTED)
    draw_arrow(ax, 66, 55, 70, 55, TEXT_MUTED)
    plt.tight_layout()
    plt.savefig(OUT_DIR / '05_dataset_preprocessing_workflow.png')
    plt.close()


# 6. Intrusion Detection Workflow
def gen_06():
    fig, ax = create_base_canvas(title="Figure 5.6: Real-Time Intrusion Detection & Threat Scoring Workflow",
                                subtitle="Ingress Packet Parsing, Multi-Model Inferencing, Risk Categorization, and Incident Logging")
    draw_box(ax, 4, 38, 16, 35, "Packet Arrival", ["IP Packet Capture", "Tuple: Src/Dst IP/Port", "Flow Stats Assembled", "Feature Validation"], ACCENT_CYAN)
    draw_box(ax, 24, 38, 22, 35, "Parallel Inference", ["Random Forest -> P(atk)", "LSTM -> P(temporal)", "Autoencoder -> MSE error", "Error > Thresh -> P(ano)"], ACCENT_PURPLE)
    draw_box(ax, 50, 38, 22, 35, "Ensemble & Risk Engine", ["Weighted Soft Voting", "P_ens = 0.45RF+0.35L+0.2A", "CRITICAL (P >= 0.90)", "HIGH / MED / LOW"], ACCENT_GOLD)
    draw_box(ax, 76, 38, 20, 35, "Action Dispatch", ["SQLite Persistence", "Firewall IP Drop", "Dashboard Live Stream", "SNS Alert Trigger"], ACCENT_RED)

    draw_arrow(ax, 20, 55, 24, 55, ACCENT_CYAN)
    draw_arrow(ax, 46, 55, 50, 55, ACCENT_PURPLE)
    draw_arrow(ax, 72, 55, 76, 55, ACCENT_GOLD)
    plt.tight_layout()
    plt.savefig(OUT_DIR / '06_intrusion_detection_workflow.png')
    plt.close()


# 7. Ensemble Architecture
def gen_07():
    fig, ax = create_base_canvas(title="Figure 5.7: Multi-Model Ensemble Voting Architecture",
                                subtitle="Supervised Decision Forest, Sequential Recurrent Unit, and Unsupervised Anomaly Scoring")
    draw_box(ax, 5, 40, 18, 30, "Feature Vector", ["X in R^41 (Scaled)", "Connection Attributes", "Traffic Volume Ratios"], ACCENT_BLUE)
    
    draw_box(ax, 32, 70, 24, 22, "Random Forest (w=0.45)", ["200 Decision Trees", "High Precision (96.7%)", "Known Signature Expert"], ACCENT_CYAN)
    draw_box(ax, 32, 42, 24, 22, "PyTorch LSTM (w=0.35)", ["2-Layer Recurrent Cell", "Sequential Flow Tracking", "Temporal Pattern Expert"], ACCENT_PURPLE)
    draw_box(ax, 32, 14, 24, 22, "Autoencoder (w=0.20)", ["Latent Bottleneck (dim=12)", "Reconstruction Error", "Zero-Day Anomaly Expert"], ACCENT_GOLD)

    draw_box(ax, 66, 36, 28, 38, "Consensus Arbiter",
             ["Soft Probability Blending:", "P = 0.45(P_rf) + 0.35(P_lstm) + 0.20(P_ae)", "Hard Vote: 2-of-3 Agreement", "Output: Classification & Confidence"], ACCENT_GREEN)

    draw_arrow(ax, 23, 60, 32, 80, ACCENT_CYAN)
    draw_arrow(ax, 23, 55, 32, 53, ACCENT_PURPLE)
    draw_arrow(ax, 23, 50, 32, 25, ACCENT_GOLD)

    draw_arrow(ax, 56, 80, 66, 60, ACCENT_CYAN)
    draw_arrow(ax, 56, 53, 66, 55, ACCENT_PURPLE)
    draw_arrow(ax, 56, 25, 66, 45, ACCENT_GOLD)
    plt.tight_layout()
    plt.savefig(OUT_DIR / '07_ensemble_voting_architecture.png')
    plt.close()


# 8. Automated Response Workflow
def gen_08():
    fig, ax = create_base_canvas(title="Figure 5.8: Automated Incident Response & Mitigation Workflow",
                                subtitle="Threat Level Evaluation, Automatic Blocking, Local nftables, and AWS Cloud Enforcers")
    draw_box(ax, 4, 38, 18, 35, "Detected Incident", ["Source IP: 203.0.113.x", "Attack Flag: TRUE", "Risk: CRITICAL / HIGH", "Confidence > 90%"], ACCENT_RED)
    draw_box(ax, 26, 38, 22, 35, "Response Engine", ["Policy Evaluation", "Auto-Block Eligibility", "State Lock & Deduplication", "DB Persistence"], ACCENT_GOLD)
    draw_box(ax, 52, 58, 22, 30, "Local Enforcement", ["nftables Firewall Provider", "Table: cidrs_filter", "Chain: cidrs_input", "Drop rule immediate (<10ms)"], ACCENT_BLUE)
    draw_box(ax, 52, 15, 22, 30, "Cloud Enforcement", ["AWS Security Group", "Egress/Ingress Rule Revoke", "AWS WAF IP Set Block", "Audit Log Generation"], ACCENT_PURPLE)
    draw_box(ax, 78, 38, 18, 35, "SOC Notification", ["Live Dashboard Alert", "REST /notifications", "Telegram / Slack Webhook", "SOC Analyst Audit Trail"], ACCENT_GREEN)

    draw_arrow(ax, 22, 55, 26, 55, ACCENT_RED)
    draw_arrow(ax, 48, 60, 52, 73, ACCENT_BLUE, "Local Mode")
    draw_arrow(ax, 48, 50, 52, 30, ACCENT_PURPLE, "AWS Mode")
    draw_arrow(ax, 74, 73, 78, 58, ACCENT_BLUE)
    draw_arrow(ax, 74, 30, 78, 52, ACCENT_PURPLE)
    plt.tight_layout()
    plt.savefig(OUT_DIR / '08_automated_response_workflow.png')
    plt.close()


# 9. DFD Level 0
def gen_09():
    fig, ax = create_base_canvas(title="Figure 5.9: Data Flow Diagram (DFD) Level 0 — Context Diagram",
                                subtitle="System Boundary, External Entities, and High-Level Ingress/Egress Flows")
    draw_box(ax, 5, 40, 20, 30, "External Network / Host", ["Traffic Generator", "Potential Adversary", "Client Packets"], ACCENT_CYAN)
    draw_box(ax, 38, 30, 26, 50, "CIDRS System (0.0)", ["Machine Learning Engine", "Intrusion Detection Core", "Automated Response Unit", "Central SQLite Datastore"], ACCENT_PURPLE)
    draw_box(ax, 75, 58, 20, 28, "Security Analyst (SOC)", ["Dashboard Inspection", "Query Filter Engine", "Manual Block Override"], ACCENT_GREEN)
    draw_box(ax, 75, 18, 20, 28, "Firewall Infrastructure", ["nftables Kernel Filter", "AWS Security Groups", "IP Drop Action Rules"], ACCENT_RED)

    draw_arrow(ax, 25, 55, 38, 55, ACCENT_CYAN, "Packet Telemetry")
    draw_arrow(ax, 64, 65, 75, 68, ACCENT_GREEN, "Incident Feeds")
    draw_arrow(ax, 75, 62, 64, 55, ACCENT_GREEN, "Operator Actions")
    draw_arrow(ax, 64, 40, 75, 32, ACCENT_RED, "Block IP Directives")
    plt.tight_layout()
    plt.savefig(OUT_DIR / '09_dfd_level_0.png')
    plt.close()


# 10. DFD Level 1
def gen_10():
    fig, ax = create_base_canvas(title="Figure 5.10: Data Flow Diagram (DFD) Level 1 — Process Decomposition",
                                subtitle="Functional Decomposition: Ingestion, Extraction, Classification, Decision, and Notification")
    draw_box(ax, 4, 60, 18, 25, "1.0 Ingest Packet", ["Scapy / Log Receiver", "Packet Dissection"], ACCENT_CYAN)
    draw_box(ax, 26, 60, 20, 25, "2.0 Preprocess Flow", ["Clean & Categorical Map", "Standard Normalization"], ACCENT_BLUE)
    draw_box(ax, 50, 60, 22, 25, "3.0 ML Inference", ["RF + LSTM + Autoencoder", "Ensemble Probability"], ACCENT_PURPLE)
    draw_box(ax, 76, 60, 20, 25, "4.0 Incident Logger", ["SQLite DB Storage", "MITRE Mapping"], ACCENT_GOLD)
    draw_box(ax, 50, 15, 22, 25, "5.0 Response Dispatch", ["nftables / AWS SG", "Automated Drop Rule"], ACCENT_RED)
    draw_box(ax, 76, 15, 20, 25, "6.0 SOC Broadcast", ["REST API Polling", "Dashboard Render"], ACCENT_GREEN)

    draw_arrow(ax, 22, 72, 26, 72, TEXT_MUTED)
    draw_arrow(ax, 46, 72, 50, 72, TEXT_MUTED)
    draw_arrow(ax, 72, 72, 76, 72, TEXT_MUTED)
    draw_arrow(ax, 61, 60, 61, 40, ACCENT_RED, "If Threat")
    draw_arrow(ax, 72, 27, 76, 27, TEXT_MUTED)
    plt.tight_layout()
    plt.savefig(OUT_DIR / '10_dfd_level_1.png')
    plt.close()


# 11. Database ER Diagram
def gen_11():
    fig, ax = create_base_canvas(title="Figure 5.11: CIDRS Relational Database Entity-Relationship (ER) Schema",
                                subtitle="SQLite Relational Schema: incidents, blocked_ips, notifications, and system_audit")
    draw_box(ax, 5, 45, 26, 42, "incidents",
             ["id: INTEGER PK AUTO", "timestamp: TEXT NOT NULL", "source_ip: TEXT NOT NULL", "is_attack: INTEGER (0/1)",
              "confidence: REAL", "risk_level: TEXT", "model_votes: TEXT (JSON)", "mitre_technique: TEXT", "attack_type: TEXT"], ACCENT_CYAN)
    draw_box(ax, 37, 45, 26, 42, "blocked_ips",
             ["ip: TEXT PRIMARY KEY", "blocked_at: TEXT NOT NULL", "risk: TEXT NOT NULL", "reason: TEXT NOT NULL",
              "automatic: INTEGER (0/1)", "enforced: INTEGER (0/1)", "enforcement_provider: TEXT"], ACCENT_RED)
    draw_box(ax, 69, 45, 26, 42, "notifications",
             ["id: INTEGER PK AUTO", "timestamp: TEXT NOT NULL", "channel: TEXT NOT NULL", "severity: TEXT NOT NULL",
              "message: TEXT NOT NULL", "delivered: INTEGER (0/1)"], ACCENT_GOLD)
    draw_box(ax, 37, 8, 26, 28, "system_audit_log",
             ["id: INTEGER PK AUTO", "timestamp: TEXT NOT NULL", "action: TEXT NOT NULL", "target_ip: TEXT", "operator: TEXT", "status: TEXT"], ACCENT_PURPLE)

    draw_arrow(ax, 31, 66, 37, 66, ACCENT_RED, "triggers block")
    draw_arrow(ax, 63, 66, 69, 66, ACCENT_GOLD, "emits alert")
    draw_arrow(ax, 50, 45, 50, 36, ACCENT_PURPLE, "records audit")
    plt.tight_layout()
    plt.savefig(OUT_DIR / '11_database_er_diagram.png')
    plt.close()


# 12. Use Case Diagram
def gen_12():
    fig, ax = create_base_canvas(title="Figure 5.12: System Use Case Diagram",
                                subtitle="Primary Actors: Network Traffic, SOC Security Analyst, System Administrator, and Firewall")
    draw_box(ax, 4, 35, 18, 40, "Actor: Traffic Stream", ["Sends Packets", "Port Probes", "DoS Inundation", "Payloads"], ACCENT_CYAN)
    draw_box(ax, 28, 12, 44, 75, "CIDRS System Boundary",
             ["UC1: Ingest & Parse Traffic", "UC2: Preprocess Features", "UC3: Execute Multi-Model ML",
              "UC4: Classify Risk & MITRE", "UC5: Automatically Block Threat", "UC6: Search & Filter Incidents",
              "UC7: Manual IP Block / Unblock", "UC8: View SOC Dashboard KPIs", "UC9: Export Audit Reports"], ACCENT_PURPLE)
    draw_box(ax, 78, 55, 18, 32, "Actor: SOC Analyst", ["Monitors Alerts", "Queries Events", "Triggers Manual Blocks"], ACCENT_GREEN)
    draw_box(ax, 78, 15, 18, 32, "Actor: Firewall Engine", ["nftables / AWS SG", "Enforces Drop Rules", "Syncs State"], ACCENT_RED)

    draw_arrow(ax, 22, 55, 28, 70, ACCENT_CYAN)
    draw_arrow(ax, 78, 70, 72, 55, ACCENT_GREEN)
    draw_arrow(ax, 72, 30, 78, 30, ACCENT_RED)
    plt.tight_layout()
    plt.savefig(OUT_DIR / '12_use_case_diagram.png')
    plt.close()


# 13. Sequence Diagram
def gen_13():
    fig, ax = create_base_canvas(title="Figure 5.13: Real-Time Detection and Automated Response Sequence Diagram",
                                subtitle="Chronological Message Interactions Between Ingestion, ML Models, DB, Firewall, and UI")
    actors = ["Traffic", "FastAPI /detect", "ML Ensemble", "SQLite DB", "Firewall Provider", "SOC Dashboard"]
    xs = [10, 26, 42, 58, 74, 90]
    for x, act in zip(xs, actors):
        draw_box(ax, x - 7, 78, 14, 10, act, color=ACCENT_BLUE, fontsize=8)
        ax.plot([x, x], [15, 78], color=BORDER_COL, linestyle='--', lw=1.2, zorder=1)

    steps = [
        (1, 0, 1, 70, "1. POST /detect (payload)", ACCENT_CYAN),
        (2, 1, 2, 63, "2. Infer(features[41])", ACCENT_PURPLE),
        (3, 2, 1, 56, "3. Ensemble score: CRITICAL", ACCENT_PURPLE),
        (4, 1, 3, 49, "4. INSERT incident record", ACCENT_GOLD),
        (5, 1, 4, 42, "5. Block(IP, nftables/AWS)", ACCENT_RED),
        (6, 4, 1, 35, "6. Enforced: OK", ACCENT_RED),
        (7, 1, 0, 28, "7. HTTP 200 (blocked: true)", ACCENT_CYAN),
        (8, 1, 5, 21, "8. Broadcast incident feed", ACCENT_GREEN),
    ]
    for num, src, dst, y, text, col in steps:
        draw_arrow(ax, xs[src], y, xs[dst], y, color=col, label=text)
    plt.tight_layout()
    plt.savefig(OUT_DIR / '13_sequence_diagram.png')
    plt.close()


# 14. API Architecture
def gen_14():
    fig, ax = create_base_canvas(title="Figure 5.14: Modular REST API Architecture (FastAPI)",
                                subtitle="Endpoints, Request Handlers, Pydantic Schema Validation, and Response Serializers")
    draw_box(ax, 4, 20, 22, 65, "Ingress Routing",
             ["GET /health", "GET /stats", "GET /alerts", "POST /detect", "GET /blocks", "POST /blocks", "DELETE /blocks/{ip}", "POST /query", "GET /system", "GET /model/metrics"], ACCENT_CYAN)
    draw_box(ax, 30, 20, 24, 65, "Middleware & Validation",
             ["CORSMiddleware", "API Key Auth Guard", "Pydantic V2 Models", "IP Address Validator", "Numeric Vector Validator", "Splunk DSL Parser"], ACCENT_PURPLE)
    draw_box(ax, 58, 20, 20, 65, "Core Services",
             ["Ensemble Predictor", "ResponseEngine", "SQLite Store", "Firewall Provider", "System Telemetry"], ACCENT_GOLD)
    draw_box(ax, 82, 20, 14, 65, "Subsystems",
             ["PyTorch Runtime", "Scikit-Learn", "nftables CLI", "AWS Boto3"], ACCENT_GREEN)

    draw_arrow(ax, 26, 52, 30, 52, TEXT_MUTED)
    draw_arrow(ax, 54, 52, 58, 52, TEXT_MUTED)
    draw_arrow(ax, 78, 52, 82, 52, TEXT_MUTED)
    plt.tight_layout()
    plt.savefig(OUT_DIR / '14_api_architecture.png')
    plt.close()


# 15. Security Architecture
def gen_15():
    fig, ax = create_base_canvas(title="Figure 5.15: Multi-Layer Defense-in-Depth Security Architecture",
                                subtitle="Edge Shielding, Transport Encryption, Application Security, Data Protection, and Host Hardening")
    layers = [
        ("Layer 5: Edge & Network", ["AWS VPC Isolation", "Security Groups (Strict Ingress)", "WAF Rate Limiting", "DDoS Mitigation"], ACCENT_CYAN, 8),
        ("Layer 4: Transport Layer", ["TLS 1.3 Encryption", "HTTPS Only Enforcement", "Secure REST Endpoints", "Certificate Pinning"], ACCENT_BLUE, 26),
        ("Layer 3: Application Layer", ["Pydantic Input Sanitization", "SQL Injection Parameterization", "CORS Restrictions", "Rate Limiter Throttling"], ACCENT_PURPLE, 44),
        ("Layer 2: Data Protection", ["SQLite at-rest Encryption", "Least-Privilege DB Access", "Automated Database Backups", "Audit Log Immutability"], ACCENT_GOLD, 62),
        ("Layer 1: Host & OS Layer", ["Linux nftables Kernel Defense", "Non-root Docker Container", "Zero Unneeded Ports", "CloudWatch Host Monitoring"], ACCENT_RED, 80),
    ]
    for title, items, col, x in layers:
        draw_box(ax, x, 25, 15, 55, title, items, col, fontsize=8)
    plt.tight_layout()
    plt.savefig(OUT_DIR / '15_security_architecture.png')
    plt.close()


# 16. Deployment Architecture
def gen_16():
    fig, ax = create_base_canvas(title="Figure 5.16: Containerized Production Deployment Architecture",
                                subtitle="Docker Container Orchestration, Systemd Process Management, and Cloud Host Integration")
    draw_box(ax, 5, 20, 24, 65, "Host Server (AWS EC2)",
             ["Ubuntu 22.04 LTS", "Linux Kernel 5.15+", "Systemd Supervisor", "nftables Kernel Module", "CloudWatch Agent"], ACCENT_CYAN)
    draw_box(ax, 33, 20, 34, 65, "Docker Container Runtime",
             ["Python 3.11 Base Image", "Uvicorn ASGI Engine (Workers=4)", "FastAPI CIDRS Application", "PyTorch & Scikit Models Loaded", "Mounted Volume (/data/incidents.db)"], ACCENT_PURPLE)
    draw_box(ax, 71, 20, 24, 65, "External Consumers",
             ["SOC Web Client (Port 8000)", "Prometheus / Monitoring", "Automated Test Harness", "Syslog Collector"], ACCENT_GREEN)

    draw_arrow(ax, 29, 52, 33, 52, ACCENT_CYAN, "Exec")
    draw_arrow(ax, 67, 52, 71, 52, ACCENT_PURPLE, "HTTP / WS")
    plt.tight_layout()
    plt.savefig(OUT_DIR / '16_deployment_architecture.png')
    plt.close()


# 17. Initial Project Gantt Chart
def gen_17():
    fig, ax = plt.subplots(figsize=(12, 6.5), dpi=300)
    fig.patch.set_facecolor(BG_COLOR)
    ax.set_facecolor(BG_COLOR)
    
    tasks = [
        "1. Literature Review & Proposal",
        "2. Tech Stack Evaluation & Design",
        "3. Dataset Collection & EDA",
        "4. ML Model Prototyping",
        "5. Backend API & Engine Build",
        "6. Dashboard Interface Build",
        "7. Cloud Deployment (AWS)",
        "8. Testing & Documentation",
    ]
    starts = [1, 2, 3, 4, 5, 6, 7, 8]
    durations = [2, 2, 2, 3, 3, 2, 2, 3]

    y_pos = np.arange(len(tasks))
    ax.barh(y_pos, durations, left=starts, height=0.55, align='center', color=ACCENT_BLUE, edgecolor='white', alpha=0.9)
    
    ax.set_yticks(y_pos)
    ax.set_yticklabels(tasks, color=TEXT_MAIN, fontsize=10, fontweight='bold')
    ax.invert_yaxis()
    ax.set_xlabel('Project Timeline (Month 1 to Month 10 — 2024)', color=TEXT_MAIN, fontsize=11, fontweight='bold')
    ax.set_xlim(0, 11)
    ax.set_xticks(range(1, 11))
    ax.set_xticklabels([f"Month {m}" for m in range(1, 11)], color=TEXT_MUTED)
    ax.tick_params(axis='x', colors=TEXT_MUTED)
    ax.tick_params(axis='y', colors=TEXT_MAIN)
    ax.grid(axis='x', color=BORDER_COL, linestyle='--', alpha=0.7)
    for spine in ax.spines.values():
        spine.set_color(BORDER_COL)
    plt.title('Figure 3.1: Initial Proposed Project Gantt Chart (Month 1 – Month 10)', color=TEXT_MAIN, fontsize=13, fontweight='bold', pad=15)
    plt.tight_layout()
    plt.savefig(OUT_DIR / '17_initial_gantt_chart.png')
    plt.close()


# 18. Actual Project Gantt Chart
def gen_18():
    fig, ax = plt.subplots(figsize=(12, 6.5), dpi=300)
    fig.patch.set_facecolor(BG_COLOR)
    ax.set_facecolor(BG_COLOR)
    
    tasks = [
        "1. Literature Review & Approved Proposal",
        "2. Environment & Pipeline Setup",
        "3. NSL-KDD Ingestion & Preprocessing",
        "4. Multi-Model ML Training (RF, LSTM, AE)",
        "5. FastAPI Backend & nftables Provider",
        "6. SOC Dashboard & Splunk DSL Engine",
        "7. AWS Cloud Testing & Verification",
        "8. Academic Report & Final Package",
    ]
    starts = [1, 2, 3, 4, 5, 6, 7, 8]
    durations = [2, 1.5, 2, 2.5, 2, 2, 1.5, 2.5]
    colors = [ACCENT_GREEN, ACCENT_GREEN, ACCENT_GREEN, ACCENT_GREEN, ACCENT_GREEN, ACCENT_GREEN, ACCENT_GREEN, ACCENT_GOLD]

    y_pos = np.arange(len(tasks))
    ax.barh(y_pos, durations, left=starts, height=0.55, align='center', color=colors, edgecolor='white', alpha=0.95)
    
    ax.set_yticks(y_pos)
    ax.set_yticklabels(tasks, color=TEXT_MAIN, fontsize=10, fontweight='bold')
    ax.invert_yaxis()
    ax.set_xlabel('Project Execution Timeline (Month 1 to Month 10 — As Built)', color=TEXT_MAIN, fontsize=11, fontweight='bold')
    ax.set_xlim(0, 11)
    ax.set_xticks(range(1, 11))
    ax.set_xticklabels([f"Month {m}" for m in range(1, 11)], color=TEXT_MUTED)
    ax.tick_params(axis='x', colors=TEXT_MUTED)
    ax.tick_params(axis='y', colors=TEXT_MAIN)
    ax.grid(axis='x', color=BORDER_COL, linestyle='--', alpha=0.7)
    for spine in ax.spines.values():
        spine.set_color(BORDER_COL)
    plt.title('Figure 3.2: Actual As-Built Project Gantt Chart (Reflecting Iterative Milestones)', color=TEXT_MAIN, fontsize=13, fontweight='bold', pad=15)
    plt.tight_layout()
    plt.savefig(OUT_DIR / '18_actual_gantt_chart.png')
    plt.close()


def main():
    print("Generating all 18 technical and architecture diagrams...")
    gen_01()
    gen_02()
    gen_03()
    gen_04()
    gen_05()
    gen_06()
    gen_07()
    gen_08()
    gen_09()
    gen_10()
    gen_11()
    gen_12()
    gen_13()
    gen_14()
    gen_15()
    gen_16()
    gen_17()
    gen_18()
    print("All 18 diagrams generated successfully in", OUT_DIR)


if __name__ == '__main__':
    main()
