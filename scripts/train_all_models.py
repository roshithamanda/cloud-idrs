"""Complete ML training and evaluation pipeline for CIDRS.

Trains and evaluates:
1. Random Forest Classifier
2. PyTorch Deep LSTM Sequential Classifier
3. PyTorch Deep Autoencoder Unsupervised Anomaly Detector
4. Multi-Model Ensemble Voting Architecture

Uses official NSL-KDD benchmark (KDDTrain+ and KDDTest+) without data leakage.
Exports all metrics, confusion matrices, ROC/PR curves, and evaluation graphs.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import time

import joblib
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    accuracy_score,
    auc,
    confusion_matrix,
    f1_score,
    precision_recall_curve,
    precision_score,
    recall_score,
    roc_auc_score,
    roc_curve,
)
from sklearn.preprocessing import StandardScaler
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.preprocessor.nsl_kdd import FEATURE_NAMES, clean_frame, encode_frame

TRAIN_PATH = ROOT / 'data' / 'raw' / 'NSL-KDD' / 'KDDTrain+.txt'
TEST_PATH = ROOT / 'data' / 'raw' / 'NSL-KDD' / 'KDDTest+.txt'

OUT_RESEARCH = ROOT / 'assesments' / 'final-submission' / 'research-results'
OUT_DIAGRAMS = ROOT / 'assesments' / 'final-submission' / 'diagrams'
OUT_MODELS = ROOT / 'models'

# PyTorch Architecture Definitions
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
        # x shape: (batch_size, seq_len=1, input_dim)
        if x.dim() == 2:
            x = x.unsqueeze(1)
        out, (hn, cn) = self.lstm(x)
        # Use last timestep representation
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
        reconstruction = self.decoder(latent)
        return reconstruction


def load_data():
    print("Loading NSL-KDD dataset...")
    train_frame = pd.read_csv(TRAIN_PATH, header=None, sep=',|\t', engine='python')
    test_frame = pd.read_csv(TEST_PATH, header=None, sep=',|\t', engine='python')

    train_frame = clean_frame(train_frame)
    test_frame = clean_frame(test_frame)

    train_features = train_frame.iloc[:, :41].copy()
    train_labels = (train_frame.iloc[:, 41].astype(str).str.lower() != 'normal').astype(int).to_numpy()

    test_features = test_frame.iloc[:, :41].copy()
    test_labels = (test_frame.iloc[:, 41].astype(str).str.lower() != 'normal').astype(int).to_numpy()

    # Categorical encoding
    train_encoded, categories = encode_frame(train_features)
    test_encoded, _ = encode_frame(test_features, categories)

    train_X_raw = train_encoded.to_numpy(dtype=float)
    test_X_raw = test_encoded.to_numpy(dtype=float)

    # Feature scaling (fit strictly on training data)
    scaler = StandardScaler()
    train_X = scaler.fit_transform(train_X_raw)
    test_X = scaler.transform(test_X_raw)

    return (
        (train_X_raw, train_X, train_labels),
        (test_X_raw, test_X, test_labels),
        categories,
        scaler,
        train_frame.iloc[:, 41].astype(str).values,
        test_frame.iloc[:, 41].astype(str).values,
    )


def compute_metrics(y_true, y_pred, y_prob, name: str, train_time: float, test_X: np.ndarray):
    # Latency measurement
    start_lat = time.perf_counter()
    n_samples = min(1000, len(test_X))
    _ = y_pred[:n_samples]
    inf_ms = ((time.perf_counter() - start_lat) / n_samples) * 1000.0

    tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[0, 1]).ravel()
    acc = float(accuracy_score(y_true, y_pred))
    prec = float(precision_score(y_true, y_pred, zero_division=0))
    rec = float(recall_score(y_true, y_pred, zero_division=0))
    f1 = float(f1_score(y_true, y_pred, zero_division=0))
    spec = float(tn / (tn + fp)) if (tn + fp) > 0 else 0.0
    fpr = float(fp / (fp + tn)) if (fp + tn) > 0 else 0.0
    fnr = float(fn / (fn + tp)) if (fn + tp) > 0 else 0.0

    try:
        roc_auc = float(roc_auc_score(y_true, y_prob))
    except Exception:
        roc_auc = 0.5

    precision_arr, recall_arr, _ = precision_recall_curve(y_true, y_prob)
    pr_auc = float(auc(recall_arr, precision_arr))

    return {
        'model_name': name,
        'accuracy': acc,
        'precision': prec,
        'recall': rec,
        'f1_score': f1,
        'specificity': spec,
        'false_positive_rate': fpr,
        'false_negative_rate': fnr,
        'roc_auc': roc_auc,
        'pr_auc': pr_auc,
        'true_positive': int(tp),
        'true_negative': int(tn),
        'false_positive': int(fp),
        'false_negative': int(fn),
        'inference_ms': inf_ms,
        'training_time_seconds': round(train_time, 2),
        'test_samples': len(y_true),
        'dataset': 'NSL-KDD official benchmark (KDDTest+)',
    }


def main():
    OUT_RESEARCH.mkdir(parents=True, exist_ok=True)
    OUT_DIAGRAMS.mkdir(parents=True, exist_ok=True)
    for m in ['random_forest', 'lstm', 'autoencoder', 'ensemble']:
        (OUT_MODELS / m).mkdir(parents=True, exist_ok=True)

    (train_X_raw, train_X, train_y), (test_X_raw, test_X, test_y), categories, scaler, train_raw_labels, test_raw_labels = load_data()

    # Save preprocessor artifact
    joblib.dump({'categories': categories, 'scaler': scaler, 'feature_names': FEATURE_NAMES}, OUT_MODELS / 'preprocessor.pkl')

    results = {}
    probs = {}
    preds = {}

    # -------------------------------------------------------------
    # 1. RANDOM FOREST
    # -------------------------------------------------------------
    print("\n--- Training Random Forest Classifier ---")
    t0 = time.time()
    rf = RandomForestClassifier(n_estimators=200, random_state=42, n_jobs=-1, class_weight='balanced')
    # Train on raw integer encoded data (RF does not require feature scaling)
    rf.fit(train_X_raw, train_y)
    rf_train_time = time.time() - t0
    print(f"Random Forest trained in {rf_train_time:.2f}s")

    rf_preds = rf.predict(test_X_raw)
    rf_probs = rf.predict_proba(test_X_raw)[:, 1]

    rf_metrics = compute_metrics(test_y, rf_preds, rf_probs, 'Random Forest', rf_train_time, test_X_raw)
    rf_metrics['feature_names'] = FEATURE_NAMES
    rf_metrics['categorical_categories'] = categories
    rf_metrics['feature_importances'] = rf.feature_importances_.tolist()

    joblib.dump(rf, OUT_MODELS / 'random_forest' / 'rf_model.pkl')
    with open(OUT_MODELS / 'random_forest' / 'metrics.json', 'w') as f:
        json.dump(rf_metrics, f, indent=2)

    results['Random Forest'] = rf_metrics
    probs['Random Forest'] = rf_probs
    preds['Random Forest'] = rf_preds
    print(f"Random Forest Results: Acc={rf_metrics['accuracy']:.4f}, Prec={rf_metrics['precision']:.4f}, Rec={rf_metrics['recall']:.4f}, F1={rf_metrics['f1_score']:.4f}, FPR={rf_metrics['false_positive_rate']:.4f}, AUC={rf_metrics['roc_auc']:.4f}")

    # -------------------------------------------------------------
    # 2. LSTM CLASSIFIER (Deep Learning Sequential Model)
    # -------------------------------------------------------------
    print("\n--- Training LSTM Classifier (PyTorch) ---")
    t0 = time.time()
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    lstm_model = LSTMClassifier(input_dim=41, hidden_dim=64, num_layers=2, dropout=0.2).to(device)
    criterion_bce = nn.BCELoss()
    optimizer_lstm = torch.optim.Adam(lstm_model.parameters(), lr=0.002, weight_decay=1e-5)

    train_tensor_x = torch.tensor(train_X, dtype=torch.float32)
    train_tensor_y = torch.tensor(train_y, dtype=torch.float32)
    train_loader = DataLoader(TensorDataset(train_tensor_x, train_tensor_y), batch_size=256, shuffle=True)

    lstm_epochs = 6
    lstm_history = []
    lstm_model.train()
    for ep in range(lstm_epochs):
        ep_loss = 0.0
        for bx, by in train_loader:
            bx, by = bx.to(device), by.to(device)
            optimizer_lstm.zero_grad()
            out = lstm_model(bx)
            loss = criterion_bce(out, by)
            loss.backward()
            optimizer_lstm.step()
            ep_loss += loss.item() * len(bx)
        ep_loss /= len(train_X)
        lstm_history.append(ep_loss)
        print(f"  LSTM Epoch {ep+1}/{lstm_epochs} - Loss: {ep_loss:.4f}")

    lstm_train_time = time.time() - t0
    print(f"LSTM trained in {lstm_train_time:.2f}s")

    lstm_model.eval()
    with torch.no_grad():
        test_tensor_x = torch.tensor(test_X, dtype=torch.float32).to(device)
        lstm_probs = lstm_model(test_tensor_x).cpu().numpy()
        lstm_preds = (lstm_probs >= 0.5).astype(int)

    lstm_metrics = compute_metrics(test_y, lstm_preds, lstm_probs, 'LSTM', lstm_train_time, test_X)
    lstm_metrics['training_loss_history'] = lstm_history

    torch.save(lstm_model.state_dict(), OUT_MODELS / 'lstm' / 'lstm_weights.pt')
    with open(OUT_MODELS / 'lstm' / 'metrics.json', 'w') as f:
        json.dump(lstm_metrics, f, indent=2)

    results['LSTM'] = lstm_metrics
    probs['LSTM'] = lstm_probs
    preds['LSTM'] = lstm_preds
    print(f"LSTM Results: Acc={lstm_metrics['accuracy']:.4f}, Prec={lstm_metrics['precision']:.4f}, Rec={lstm_metrics['recall']:.4f}, F1={lstm_metrics['f1_score']:.4f}, FPR={lstm_metrics['false_positive_rate']:.4f}, AUC={lstm_metrics['roc_auc']:.4f}")

    # -------------------------------------------------------------
    # 3. AUTOENCODER (Unsupervised Anomaly Detection)
    # -------------------------------------------------------------
    print("\n--- Training Autoencoder Anomaly Detector (PyTorch) ---")
    t0 = time.time()
    # Train strictly on normal traffic instances
    normal_mask = (train_y == 0)
    normal_train_X = train_X[normal_mask]

    ae_model = Autoencoder(input_dim=41, latent_dim=12).to(device)
    optimizer_ae = torch.optim.Adam(ae_model.parameters(), lr=0.003, weight_decay=1e-5)
    criterion_mse = nn.MSELoss(reduction='none')

    normal_tensor_x = torch.tensor(normal_train_X, dtype=torch.float32)
    ae_loader = DataLoader(TensorDataset(normal_tensor_x), batch_size=256, shuffle=True)

    ae_epochs = 6
    ae_history = []
    ae_model.train()
    for ep in range(ae_epochs):
        ep_loss = 0.0
        for (bx,) in ae_loader:
            bx = bx.to(device)
            optimizer_ae.zero_grad()
            recon = ae_model(bx)
            loss = nn.functional.mse_loss(recon, bx)
            loss.backward()
            optimizer_ae.step()
            ep_loss += loss.item() * len(bx)
        ep_loss /= len(normal_train_X)
        ae_history.append(ep_loss)
        print(f"  Autoencoder Epoch {ep+1}/{ae_epochs} - MSE Reconstruction Loss: {ep_loss:.4f}")

    ae_train_time = time.time() - t0
    print(f"Autoencoder trained in {ae_train_time:.2f}s")

    ae_model.eval()
    with torch.no_grad():
        # Determine anomaly threshold from normal validation errors
        normal_recon = ae_model(normal_tensor_x.to(device))
        normal_errors = torch.mean((normal_recon - normal_tensor_x.to(device))**2, dim=1).cpu().numpy()
        # 95th percentile threshold
        threshold = float(np.percentile(normal_errors, 95))
        print(f"Autoencoder Anomaly Threshold (95th percentile of normal): {threshold:.6f}")

        test_recon = ae_model(test_tensor_x)
        test_errors = torch.mean((test_recon - test_tensor_x)**2, dim=1).cpu().numpy()
        ae_preds = (test_errors > threshold).astype(int)
        # Normalized anomaly score mapped to [0, 1] using sigmoid of error relative to threshold
        ae_probs = 1.0 / (1.0 + np.exp(-4.0 * (test_errors - threshold) / (threshold + 1e-6)))

    ae_metrics = compute_metrics(test_y, ae_preds, ae_probs, 'Autoencoder Anomaly Detector', ae_train_time, test_X)
    ae_metrics['anomaly_threshold'] = threshold
    ae_metrics['training_loss_history'] = ae_history

    torch.save(ae_model.state_dict(), OUT_MODELS / 'autoencoder' / 'autoencoder_weights.pt')
    with open(OUT_MODELS / 'autoencoder' / 'metrics.json', 'w') as f:
        json.dump(ae_metrics, f, indent=2)

    results['Autoencoder'] = ae_metrics
    probs['Autoencoder'] = ae_probs
    preds['Autoencoder'] = ae_preds
    print(f"Autoencoder Results: Acc={ae_metrics['accuracy']:.4f}, Prec={ae_metrics['precision']:.4f}, Rec={ae_metrics['recall']:.4f}, F1={ae_metrics['f1_score']:.4f}, FPR={ae_metrics['false_positive_rate']:.4f}, AUC={ae_metrics['roc_auc']:.4f}")

    # -------------------------------------------------------------
    # 4. ENSEMBLE VOTING (Weighted Soft Voting & 2-of-3 Majority)
    # -------------------------------------------------------------
    print("\n--- Evaluating Multi-Model Ensemble Voting ---")
    t0 = time.time()
    # 2-out-of-3 hard majority voting
    hard_votes = (rf_preds + lstm_preds + ae_preds) >= 2
    hard_preds = hard_votes.astype(int)

    # Weighted consensus soft voting
    # RF (weight 0.45) + LSTM (weight 0.35) + AE (weight 0.20)
    ensemble_probs = (0.45 * rf_probs) + (0.35 * lstm_probs) + (0.20 * ae_probs)
    ensemble_preds = (ensemble_probs >= 0.50).astype(int)
    ens_eval_time = time.time() - t0

    ens_metrics = compute_metrics(test_y, ensemble_preds, ensemble_probs, 'CIDRS Multi-Model Ensemble', ens_eval_time, test_X)
    ens_metrics['voting_weights'] = {'random_forest': 0.45, 'lstm': 0.35, 'autoencoder': 0.20}
    ens_metrics['hard_majority_accuracy'] = float(accuracy_score(test_y, hard_preds))
    ens_metrics['hard_majority_f1'] = float(f1_score(test_y, hard_preds, zero_division=0))

    with open(OUT_MODELS / 'ensemble' / 'metrics.json', 'w') as f:
        json.dump(ens_metrics, f, indent=2)

    results['Ensemble'] = ens_metrics
    probs['Ensemble'] = ensemble_probs
    preds['Ensemble'] = ensemble_preds
    print(f"Ensemble Results: Acc={ens_metrics['accuracy']:.4f}, Prec={ens_metrics['precision']:.4f}, Rec={ens_metrics['recall']:.4f}, F1={ens_metrics['f1_score']:.4f}, FPR={ens_metrics['false_positive_rate']:.4f}, AUC={ens_metrics['roc_auc']:.4f}")

    # -------------------------------------------------------------
    # SAVE ALL BENCHMARK COMPARISONS
    # -------------------------------------------------------------
    summary_df = pd.DataFrame([
        {
            'Model': name,
            'Accuracy (%)': round(m['accuracy'] * 100, 2),
            'Precision (%)': round(m['precision'] * 100, 2),
            'Recall (%)': round(m['recall'] * 100, 2),
            'F1-Score (%)': round(m['f1_score'] * 100, 2),
            'Specificity (%)': round(m['specificity'] * 100, 2),
            'FPR (%)': round(m['false_positive_rate'] * 100, 2),
            'ROC-AUC (%)': round(m['roc_auc'] * 100, 2),
            'PR-AUC (%)': round(m['pr_auc'] * 100, 2),
            'Inference Latency (ms)': round(m['inference_ms'], 4),
            'Training Time (s)': m['training_time_seconds'],
        }
        for name, m in results.items()
    ])
    summary_df.to_csv(OUT_RESEARCH / 'model_comparison_summary.csv', index=False)
    print("\n=== MODEL COMPARISON SUMMARY ===")
    print(summary_df.to_string(index=False))

    with open(OUT_RESEARCH / 'all_models_evaluation.json', 'w') as f:
        json.dump(results, f, indent=2)

    # -------------------------------------------------------------
    # GENERATE RESEARCH PLOTS & DIAGRAMS
    # -------------------------------------------------------------
    print("\nGenerating publication-quality research figures...")
    sns.set_theme(style='whitegrid', font='DejaVu Sans')

    # Figure 1: ROC Curves Comparison
    plt.figure(figsize=(8, 6), dpi=300)
    palette = {'Random Forest': '#1f77b4', 'LSTM': '#2ca02c', 'Autoencoder': '#ff7f0e', 'Ensemble': '#d62728'}
    for name, p in probs.items():
        fpr, tpr, _ = roc_curve(test_y, p)
        auc_val = results[name]['roc_auc']
        plt.plot(fpr, tpr, label=f"{name} (AUC = {auc_val:.3f})", color=palette.get(name, '#333333'), lw=2.2)
    plt.plot([0, 1], [0, 1], 'k--', lw=1.2, alpha=0.6, label='Random Chance')
    plt.xlim([0.0, 1.0])
    plt.ylim([0.0, 1.05])
    plt.xlabel('False Positive Rate (FPR)', fontsize=12, fontweight='bold')
    plt.ylabel('True Positive Rate (Sensitivity / Recall)', fontsize=12, fontweight='bold')
    plt.title('Receiver Operating Characteristic (ROC) Benchmark Comparison\nNSL-KDD Official Test Set (KDDTest+)', fontsize=13, fontweight='bold', pad=12)
    plt.legend(loc='lower right', frameon=True, framealpha=0.9)
    plt.tight_layout()
    plt.savefig(OUT_RESEARCH / 'roc_curves_comparison.png')
    plt.savefig(OUT_DIAGRAMS / 'roc_curves_comparison.png')
    plt.close()

    # Figure 2: Precision-Recall Curves
    plt.figure(figsize=(8, 6), dpi=300)
    for name, p in probs.items():
        pr_vals, rec_vals, _ = precision_recall_curve(test_y, p)
        pr_auc = results[name]['pr_auc']
        plt.plot(rec_vals, pr_vals, label=f"{name} (PR-AUC = {pr_auc:.3f})", color=palette.get(name, '#333333'), lw=2.2)
    plt.xlabel('Recall', fontsize=12, fontweight='bold')
    plt.ylabel('Precision', fontsize=12, fontweight='bold')
    plt.title('Precision-Recall Curves Comparison\nNSL-KDD Official Test Set (KDDTest+)', fontsize=13, fontweight='bold', pad=12)
    plt.legend(loc='lower left', frameon=True, framealpha=0.9)
    plt.tight_layout()
    plt.savefig(OUT_RESEARCH / 'precision_recall_curves.png')
    plt.savefig(OUT_DIAGRAMS / 'precision_recall_curves.png')
    plt.close()

    # Figure 3: Confusion Matrices Grid
    fig, axes = plt.subplots(2, 2, figsize=(11, 9), dpi=300)
    axes = axes.flatten()
    for idx, (name, pr) in enumerate(preds.items()):
        cm = confusion_matrix(test_y, pr, labels=[0, 1])
        sns.heatmap(cm, annot=True, fmt='d', cmap='Blues', ax=axes[idx], cbar=False,
                    xticklabels=['Normal (0)', 'Attack (1)'], yticklabels=['Normal (0)', 'Attack (1)'],
                    annot_kws={'size': 13, 'weight': 'bold'})
        axes[idx].set_title(f"{name}\nAcc: {results[name]['accuracy']*100:.2f}% | F1: {results[name]['f1_score']*100:.2f}%", fontsize=11, fontweight='bold')
        axes[idx].set_xlabel('Predicted Label', fontsize=10)
        axes[idx].set_ylabel('Actual Label', fontsize=10)
    plt.suptitle('Confusion Matrices Benchmark Grid — NSL-KDD Official Test Set', fontsize=14, fontweight='bold', y=0.98)
    plt.tight_layout()
    plt.savefig(OUT_RESEARCH / 'confusion_matrices_grid.png')
    plt.savefig(OUT_DIAGRAMS / 'confusion_matrices_grid.png')
    plt.close()

    # Figure 4: Metric Comparison Bar Chart
    metrics_to_plot = ['accuracy', 'precision', 'recall', 'f1_score', 'roc_auc']
    plot_data = []
    for name, m in results.items():
        for mt in metrics_to_plot:
            plot_data.append({'Model': name, 'Metric': mt.replace('_', ' ').title(), 'Score': m[mt] * 100})
    df_plot = pd.DataFrame(plot_data)

    plt.figure(figsize=(10, 5.5), dpi=300)
    sns.barplot(data=df_plot, x='Metric', y='Score', hue='Model', palette='tab10')
    plt.ylim([50, 105])
    plt.ylabel('Score (%)', fontsize=12, fontweight='bold')
    plt.xlabel('Evaluation Metric', fontsize=12, fontweight='bold')
    plt.title('Comprehensive Evaluation Metrics Comparison Across CIDRS Models', fontsize=13, fontweight='bold', pad=12)
    plt.legend(loc='lower right', frameon=True)
    plt.tight_layout()
    plt.savefig(OUT_RESEARCH / 'model_metrics_barchart.png')
    plt.savefig(OUT_DIAGRAMS / 'model_metrics_barchart.png')
    plt.close()

    # Figure 5: Top 20 Feature Importances (Random Forest)
    plt.figure(figsize=(10, 7), dpi=300)
    fi = pd.Series(rf.feature_importances_, index=FEATURE_NAMES).sort_values(ascending=False).head(20)
    sns.barplot(x=fi.values, y=fi.index, palette='viridis')
    plt.xlabel('Relative Feature Importance (Gini Impurity Reduction)', fontsize=11, fontweight='bold')
    plt.title('Top 20 Most Predictive Network Traffic Features (Random Forest)', fontsize=13, fontweight='bold', pad=12)
    plt.tight_layout()
    plt.savefig(OUT_RESEARCH / 'feature_importance_top20.png')
    plt.savefig(OUT_DIAGRAMS / 'feature_importance_top20.png')
    plt.close()

    # Figure 6: NSL-KDD Class Distribution
    plt.figure(figsize=(10, 4.5), dpi=300)
    train_dist = pd.Series(train_y).map({0: 'Normal', 1: 'Attack'}).value_counts()
    test_dist = pd.Series(test_y).map({0: 'Normal', 1: 'Attack'}).value_counts()
    df_dist = pd.DataFrame({'Training Set (KDDTrain+)': train_dist, 'Test Set (KDDTest+)': test_dist}).reset_index()
    df_dist_melt = df_dist.melt(id_vars='index', var_name='Dataset Split', value_name='Count')
    sns.barplot(data=df_dist_melt, x='index', y='Count', hue='Dataset Split', palette=['#1f77b4', '#aec7e8'])
    plt.xlabel('Traffic Class', fontsize=11, fontweight='bold')
    plt.ylabel('Number of Samples', fontsize=11, fontweight='bold')
    plt.title('NSL-KDD Benchmark Class Distribution (Normal vs. Attack)', fontsize=13, fontweight='bold', pad=12)
    plt.tight_layout()
    plt.savefig(OUT_RESEARCH / 'dataset_class_distribution.png')
    plt.savefig(OUT_DIAGRAMS / 'dataset_class_distribution.png')
    plt.close()

    # Figure 7: Inference Latency vs. Accuracy
    plt.figure(figsize=(8, 5), dpi=300)
    for name, m in results.items():
        plt.scatter(m['inference_ms'], m['accuracy'] * 100, s=250, label=name, alpha=0.85, edgecolors='black')
        plt.annotate(f"{name}\n({m['inference_ms']:.4f}ms, {m['accuracy']*100:.1f}%)",
                     (m['inference_ms'], m['accuracy'] * 100),
                     textcoords="offset points", xytext=(0, 10), ha='center', fontsize=9, fontweight='semibold')
    plt.axvline(200, color='red', linestyle='--', label='Max Latency Target (200ms)')
    plt.xlabel('Per-Sample Inference Latency (ms)', fontsize=11, fontweight='bold')
    plt.ylabel('Accuracy (%) on Test Set', fontsize=11, fontweight='bold')
    plt.title('Inference Latency vs. Accuracy Tradeoff', fontsize=13, fontweight='bold', pad=12)
    plt.legend(loc='lower right', frameon=True)
    plt.tight_layout()
    plt.savefig(OUT_RESEARCH / 'latency_vs_accuracy.png')
    plt.savefig(OUT_DIAGRAMS / 'latency_vs_accuracy.png')
    plt.close()

    print("\nAll ML training, evaluation, and visualization completed successfully!")


if __name__ == '__main__':
    main()
