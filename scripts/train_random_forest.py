"""Train the CIDRS Random Forest from the checked-in NSL-KDD training data."""

import json
from pathlib import Path

import joblib
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score, precision_score, recall_score, roc_auc_score
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / 'data' / 'raw' / 'NSL-KDD' / 'KDDTrain+.txt'
TEST_PATH = ROOT / 'data' / 'raw' / 'NSL-KDD' / 'KDDTest+.txt'
MODEL_DIR = ROOT / 'models' / 'random_forest'
CATEGORICAL_COLUMNS = [1, 2, 3]
FEATURE_NAMES = [
    'duration', 'protocol_type', 'service', 'flag', 'src_bytes', 'dst_bytes', 'land',
    'wrong_fragment', 'urgent', 'hot', 'num_failed_logins', 'logged_in', 'num_compromised',
    'root_shell', 'su_attempted', 'num_root', 'num_file_creations', 'num_shells',
    'num_access_files', 'num_outbound_cmds', 'is_host_login', 'is_guest_login', 'count',
    'srv_count', 'serror_rate', 'srv_serror_rate', 'rerror_rate', 'srv_rerror_rate',
    'same_srv_rate', 'diff_srv_rate', 'srv_diff_host_rate', 'dst_host_count',
    'dst_host_srv_count', 'dst_host_same_srv_rate', 'dst_host_diff_srv_rate',
    'dst_host_same_src_port_rate', 'dst_host_srv_diff_host_rate', 'dst_host_serror_rate',
    'dst_host_srv_serror_rate', 'dst_host_rerror_rate', 'dst_host_srv_rerror_rate',
]


def load_dataset(path):
    frame = pd.read_csv(path, header=None, sep='\t', skipinitialspace=True)
    frame = frame.apply(lambda column: column.map(lambda value: value.strip() if isinstance(value, str) else value))
    features = frame.iloc[:, :41].copy()
    labels = (frame.iloc[:, 41].astype(str).str.lower() != 'normal').astype(int)
    return features, labels


def encode_features(features, categories=None):
    encoded = features.copy()
    categories = categories or {}
    for column in CATEGORICAL_COLUMNS:
        if column not in categories:
            categories[column] = sorted(encoded[column].dropna().unique().tolist())
        mapping = {value: index for index, value in enumerate(categories[column])}
        encoded[column] = encoded[column].map(mapping).fillna(-1)
    return encoded.astype(float), categories


def main():
    train_features, train_y = load_dataset(DATA_PATH)
    test_features, test_y = load_dataset(TEST_PATH)
    train_x, categories = encode_features(train_features)
    test_x, _ = encode_features(test_features, categories)
    model = RandomForestClassifier(n_estimators=200, random_state=42, n_jobs=-1, class_weight='balanced')
    model.fit(train_x, train_y)
    started = perf_counter()
    predictions = model.predict(test_x)
    probabilities = model.predict_proba(test_x)[:, 1]
    inference_ms = (perf_counter() - started) * 1000 / len(test_x)
    tn, fp, fn, tp = confusion_matrix(test_y, predictions, labels=[0, 1]).ravel()
    metrics = {
        'accuracy': accuracy_score(test_y, predictions),
        'precision': precision_score(test_y, predictions, zero_division=0),
        'recall': recall_score(test_y, predictions, zero_division=0),
        'f1_score': f1_score(test_y, predictions, zero_division=0),
        'roc_auc': roc_auc_score(test_y, probabilities),
        'false_positive_rate': fp / (fp + tn),
        'false_negative_rate': fn / (fn + tp),
        'true_positive': int(tp),
        'true_negative': int(tn),
        'false_positive': int(fp),
        'false_negative': int(fn),
        'inference_ms': inference_ms,
        'training_samples': len(train_x),
        'test_samples': len(test_x),
        'feature_count': train_x.shape[1],
        'feature_names': FEATURE_NAMES,
        'categorical_categories': categories,
        'dataset': 'NSL-KDD official train/test split',
    }
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, MODEL_DIR / 'rf_model.pkl')
    (MODEL_DIR / 'metrics.json').write_text(json.dumps(metrics, indent=2))
    print(json.dumps(metrics, indent=2))


if __name__ == '__main__':
    main()
