"""Train the CIDRS Random Forest from the checked-in NSL-KDD training data."""

import json
from pathlib import Path
import sys

import joblib
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score, precision_score, recall_score, roc_auc_score
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.preprocessor.nsl_kdd import FEATURE_NAMES, encode_frame, clean_frame

DATA_PATH = ROOT / 'data' / 'raw' / 'NSL-KDD' / 'KDDTrain+.txt'
TEST_PATH = ROOT / 'data' / 'raw' / 'NSL-KDD' / 'KDDTest+.txt'
MODEL_DIR = ROOT / 'models' / 'random_forest'


def load_dataset(path):
    frame = pd.read_csv(path, header=None, sep='\t', skipinitialspace=True)
    frame = clean_frame(frame)
    features = frame.iloc[:, :41].copy()
    labels = (frame.iloc[:, 41].astype(str).str.lower() != 'normal').astype(int)
    return features, labels


def encode_features(features, categories=None):
    encoded = features.copy()
    categories = categories or {}
    return encode_frame(encoded, categories)


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
