"""
Offline model evaluation script.
Generates a held-out test set and reports precision/recall proxies for the ML model.
Used to validate a new model before promoting it to production.

Usage:
    python ml/evaluate.py --version 1
    python ml/evaluate.py --version 2 --compare 1
"""

import argparse
import sys
from pathlib import Path

import numpy as np
from sklearn.metrics import classification_report, roc_auc_score

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.ml_scorer import FEATURE_COLUMNS, score_transaction
from app.services.model_registry import model_registry
from ml.train import generate_synthetic_data

RANDOM_SEED = 99  # Different from training seed


def evaluate_model(version: int) -> dict:
    print(f"\nEvaluating model v{version}...")
    model = model_registry.get(version)
    if model is None:
        print(f"Model v{version} not found. Run: python ml/train.py --version {version}")
        sys.exit(1)

    rng = np.random.default_rng(RANDOM_SEED)
    n_test = 10000
    fraud_rate = 0.05
    n_fraud = int(n_test * fraud_rate)
    n_normal = n_test - n_fraud

    # Generate labeled test data
    normal_data = _generate_split(rng, n_normal, fraud=False)
    fraud_data = _generate_split(rng, n_fraud, fraud=True)

    scores_normal = [
        score_transaction(model, dict(zip(FEATURE_COLUMNS, row))) for row in normal_data
    ]
    scores_fraud = [
        score_transaction(model, dict(zip(FEATURE_COLUMNS, row))) for row in fraud_data
    ]

    all_scores = scores_normal + scores_fraud
    all_labels = [0] * n_normal + [1] * n_fraud

    # Apply block threshold (70) as the decision boundary
    predictions = [1 if s >= 70 else 0 for s in all_scores]

    print(classification_report(all_labels, predictions, target_names=["normal", "fraud"]))

    try:
        auc = roc_auc_score(all_labels, all_scores)
        print(f"ROC-AUC: {auc:.4f}")
    except Exception:
        auc = 0.0

    return {
        "version": version,
        "auc": round(auc, 4),
        "avg_score_normal": round(float(np.mean(scores_normal)), 2),
        "avg_score_fraud": round(float(np.mean(scores_fraud)), 2),
        "p99_score_normal": round(float(np.percentile(scores_normal, 99)), 2),
        "p01_score_fraud": round(float(np.percentile(scores_fraud, 1)), 2),
    }


def _generate_split(rng: np.random.Generator, n: int, fraud: bool) -> np.ndarray:
    if not fraud:
        return np.column_stack([
            rng.lognormal(5.0, 1.2, n),
            rng.integers(6, 22, n),
            rng.integers(0, 3, n),
            rng.integers(0, 8, n),
            rng.lognormal(5.0, 0.8, n),
            rng.uniform(0.5, 2.5, n),
            rng.choice([0, 1], p=[0.9, 0.1], size=n),
            rng.choice([0, 1], p=[0.95, 0.05], size=n),
            rng.choice([0, 1], p=[0.85, 0.15], size=n),
        ])
    else:
        return np.column_stack([
            rng.lognormal(8.0, 1.5, n),
            rng.integers(0, 5, n),
            rng.integers(5, 20, n),
            rng.integers(15, 50, n),
            rng.lognormal(4.5, 0.8, n),
            rng.uniform(5.0, 40.0, n),
            rng.choice([0, 1], p=[0.3, 0.7], size=n),
            rng.choice([0, 1], p=[0.4, 0.6], size=n),
            rng.choice([0, 1], p=[0.3, 0.7], size=n),
        ])


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate fraud detection ML model")
    parser.add_argument("--version", type=int, default=1, help="Model version to evaluate")
    parser.add_argument("--compare", type=int, default=None, help="Compare against this version")
    args = parser.parse_args()

    model_registry.load_all()
    results_a = evaluate_model(args.version)

    if args.compare:
        results_b = evaluate_model(args.compare)
        print("\n--- Comparison ---")
        print(f"v{args.compare} AUC: {results_b['auc']} vs v{args.version} AUC: {results_a['auc']}")
        improvement = (results_a["auc"] - results_b["auc"]) / results_b["auc"] * 100
        print(f"AUC improvement: {improvement:+.1f}%")


if __name__ == "__main__":
    main()
