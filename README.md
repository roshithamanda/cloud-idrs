🛡️ CIDRS
Cloud-Based Intrusion Detection & Response System
A machine learning-powered IDS/IPS platform for real-time threat detection and automated response in cloud environments.
Overview • Features • Architecture • Installation • Usage • Datasets • Roadmap • Contributing

</div>
📌 Overview
CIDRS is a final-year research project that builds an intelligent, cloud-native Intrusion Detection and Response System. It leverages machine learning to detect both known and zero-day network threats, and automatically responds to contain them — reducing response time from hours to seconds.

Problem: Traditional rule-based IDS tools suffer from high false-positive rates, cannot detect novel attacks, and require manual intervention. Cloud environments need smarter, faster, autonomous protection.


Solution: CIDRS uses ML models (Random Forest, LSTM, Autoencoder) trained on benchmark network traffic datasets to classify malicious activity, and triggers automated response playbooks via cloud APIs.


✨ Features

🔍 Real-Time Traffic Monitoring — Captures and analyzes network flow data continuously
🤖 ML-Powered Detection — Classifies 15+ attack types (DoS, PortScan, Brute Force, etc.)
⚡ Automated Response Engine — Auto-blocks IPs, isolates instances, alerts admins (<5 sec)
☁️ Cloud-Native — Integrates with AWS VPC, Security Groups, CloudWatch
📊 Security Dashboard — Real-time visualization of threats, incidents, and system health
🧠 Anomaly Detection — Autoencoder-based zero-day threat identification
📝 Audit Logging — Full incident timeline and response history


🏗️ Architecture
┌─────────────────────────────────────────────────────────────┐
│                        CIDRS Architecture                    │
├──────────────┬──────────────────┬─────────────┬─────────────┤
│  Data Layer  │  Detection Layer │ Response    │  Dashboard  │
│              │                  │ Engine      │  Layer      │
│  • VPC Flow  │  • Feature Eng.  │             │             │
│    Logs      │  • Random Forest │  • Block IP │  • React.js │
│  • Packet    │  • LSTM Model    │  • Isolate  │  • FastAPI  │
│    Capture   │  • Autoencoder   │    Instance │  • InfluxDB │
│  • Scapy /   │  • Inference API │  • Alert    │  • Chart.js │
│    tcpdump   │    (Flask)       │    Admin    │             │
└──────────────┴──────────────────┴─────────────┴─────────────┘

🛠️ Tech Stack
LayerTechnologyLanguagePython 3.11, JavaScript (ES6+)ML / AIScikit-learn, TensorFlow/Keras, Pandas, NumPyBackend APIFastAPI, FlaskFrontendReact.js, Chart.jsDatabasePostgreSQL, InfluxDBCloudAWS (EC2, VPC, CloudWatch, WAF)ContainersDocker, KubernetesPacket AnalysisScapy, tsharkCI/CDGitHub Actions

📁 Project Structure
CIDRS/
├── data/
│   ├── raw/                  # Raw datasets (NSL-KDD, CICIDS2017)
│   ├── processed/            # Cleaned & feature-engineered data
│   └── synthetic/            # Self-generated cloud traffic samples
│
├── models/
│   ├── random_forest/        # Baseline RF classifier
│   ├── lstm/                 # Sequential LSTM model
│   └── autoencoder/          # Anomaly detection model
│
├── src/
│   ├── collector/            # Network traffic capture agents
│   ├── preprocessor/         # Feature extraction pipeline
│   ├── detector/             # ML inference engine
│   ├── responder/            # Automated response playbooks
│   └── api/                  # FastAPI backend
│
├── dashboard/
│   └── frontend/             # React.js security dashboard
│
├── cloud/
│   └── aws/                  # AWS deployment configs (Terraform/CDK)
│
├── notebooks/
│   ├── 01_eda.ipynb          # Exploratory data analysis
│   ├── 02_preprocessing.ipynb
│   ├── 03_model_training.ipynb
│   └── 04_evaluation.ipynb
│
├── tests/                    # Unit & integration tests
├── docs/                     # Project documentation
├── requirements.txt
├── docker-compose.yml
└── README.md

🚀 Installation
Prerequisites

Python 3.11+
Node.js 18+
Docker & Docker Compose
AWS CLI (configured)

1. Clone the Repository
bashgit clone https://github.com/YOUR_USERNAME/CIDRS.git
cd CIDRS
2. Set Up Python Environment
bashpython -m venv cidrs-env
source cidrs-env/bin/activate        # Linux/Mac
# cidrs-env\Scripts\activate         # Windows

pip install -r requirements.txt
3. Set Up Environment Variables
bashcp .env.example .env
# Edit .env with your AWS credentials and config
4. Run with Docker Compose
bashdocker-compose up --build
5. Run Dashboard (Development)
bashcd dashboard/frontend
npm install
npm start

💻 Usage
Train the ML Model
bash# Download and prepare NSL-KDD dataset
python src/preprocessor/prepare_data.py --dataset nsl-kdd

# Train the Random Forest baseline
python models/random_forest/train.py --data data/processed/nsl_kdd_train.csv

# Train the LSTM model
python models/lstm/train.py --epochs 50 --batch-size 64
Run the Detection Engine
bash# Start the detection API server
uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload

# Start live traffic monitoring (requires sudo)
sudo python src/collector/capture.py --interface eth0
Access the Dashboard
http://localhost:3000

📊 Datasets
DatasetAttacks CoveredSizeSourceNSL-KDDDoS, Probe, R2L, U2R~150k recordsUNBCICIDS 2017DoS, PortScan, Brute Force, Web Attacks~2.8M recordsUNBUNSW-NB15Fuzzers, Analysis, Backdoors, DoS~2.5M recordsUNSW

⚠️ Datasets are not included in this repository due to size. Download them from the links above and place in data/raw/.


📈 Model Performance (Target)
ModelAccuracyFalse Positive RateInference TimeRandom Forest (Baseline)>95%<5%<100msLSTM>97%<3%<200msAutoencoder (Anomaly)TBDTBD<150ms

📝 Results will be updated as experiments progress.


🗺️ Roadmap

 Project documentation & architecture design
 Dataset collection & EDA
 Data preprocessing pipeline
 Random Forest baseline model
 LSTM sequential model
 Autoencoder anomaly detection
 Detection API (FastAPI)
 Automated response engine
 React dashboard
 AWS cloud deployment
 Final evaluation & thesis


📚 Key References

Tavallaee et al. (2009) — A Detailed Analysis of the KDD CUP 99 Data Set
Sharafaldin et al. (2018) — Toward Generating a New Intrusion Detection Dataset and Intrusion Traffic Characterization
Mirsky et al. (2018) — Kitsune: An Ensemble of Autoencoders for Online Network Intrusion Detection


🤝 Contributing
This is an academic final-year project. Feedback and suggestions are welcome!

Fork the repository
Create a feature branch: git checkout -b feature/your-idea
Commit your changes: git commit -m 'Add some feature'
Push to the branch: git push origin feature/your-idea
Open a Pull Request


📄 License
This project is licensed under the MIT License — see the LICENSE file for details.

