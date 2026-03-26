"""
Train the Isolation Forest model on real PaySim data.

PaySim has ground-truth `isFraud` labels, so we use contamination derived
from the actual fraud rate rather than guessing — a big improvement over
synthetic training data.

Usage:
    python ml/train_paysim.py --csv data/paysim.csv --version 3
    python ml/train_paysim.py --csv data/paysim.csv --version 3 --sample 200000
    python ml/train_paysim.py --csv data/paysim.csv --version 3 --evaluate

After training, update the default in .env or restart the API to load the new version.
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.metrics import classification_report, roc_auc_score

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.ml_scorer import FEATURE_COLUMNS
from scripts.ingest_paysim import HIGH_RISK_TYPES, engineer_features

ARTIFACTS_DIR = Path("ml/artifacts")
RANDOM_SEED = 42


def build_feature_matrix(df: pd.DataFrame) -> np.ndarray:
    """
    Convert a PaySim DataFrame (with engineered features) to the numpy
    feature matrix expected by the ML scorer.

    PaySim → FEATURE_COLUMNS mapping:
      amount              → amount
      hour_of_day         → hour_of_day          (step % 24)
      tx_count_1h         → tx_count_1h
      tx_count_24h        → tx_count_24h
      avg_amount_30d      → avg_amount_30d
      amount_vs_avg_ratio → amount_vs_avg_ratio
      is_new_device       → is_new_device         (new orig→dest pair)
      geo_mismatch        → geo_mismatch           (dest is customer account)
      is_high_risk_mcc    → is_high_risk_mcc       (TRANSFER / CASH-OUT)
    """
    col_map = {
        "amount": "amount",
        "hour_of_day": "hour_of_day",
        "tx_count_1h": "tx_count_1h",
        "tx_count_24h": "tx_count_24h",
        "avg_amount_30d": "avg_amount_30d",
        "amount_vs_avg_ratio": "amount_vs_avg_ratio",
        "is_new_device": "is_new_device",
        "geo_mismatch": "geo_mismatch",
        "is_high_risk_mcc": "is_high_risk_mcc",
    }
    X = np.column_stack([
        df[col_map[feat]].astype(float).values
        for feat in FEATURE_COLUMNS
    ])
    return X


def train(csv_path: str, version: int, sample: int | None, evaluate: bool) -> None:
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)

    path = Path(csv_path)
    if not path.exists():
        print(f"ERROR: {csv_path} not found. See data/README.md.")
        sys.exit(1)

    print(f"Loading {csv_path}...")
    df = pd.read_csv(csv_path)
    total_rows = len(df)
    fraud_count = df["isFraud"].sum()
    actual_fraud_rate = fraud_count / total_rows
    print(f"  {total_rows:,} rows — {fraud_count:,} fraud ({actual_fraud_rate:.3%})")

    if sample and sample < total_rows:
        # Stratified sample: keep fraud ratio
        fraud_df = df[df["isFraud"] == 1]
        normal_df = df[df["isFraud"] == 0]
        fraud_n = min(len(fraud_df), int(sample * actual_fraud_rate))
        normal_n = sample - fraud_n
        df = pd.concat([
            fraud_df.sample(fraud_n, random_state=RANDOM_SEED),
            normal_df.sample(normal_n, random_state=RANDOM_SEED),
        ]).sample(frac=1, random_state=RANDOM_SEED).reset_index(drop=True)
        fraud_count = df["isFraud"].sum()
        actual_fraud_rate = fraud_count / len(df)
        print(f"  Sampled to {len(df):,} rows — {fraud_count} fraud ({actual_fraud_rate:.3%})")

    print("Engineering features...")
    df = engineer_features(df)

    labels = df["isFraud"].values
    X = build_feature_matrix(df)
    print(f"  Feature matrix: {X.shape}")

    # Use actual fraud rate as contamination — grounded in real data
    contamination = float(np.clip(actual_fraud_rate, 0.001, 0.5))
    print(f"\nTraining Isolation Forest v{version} (contamination={contamination:.4f})...")

    model = IsolationForest(
        n_estimators=200,
        contamination=contamination,
        max_features=len(FEATURE_COLUMNS),
        random_state=RANDOM_SEED,
        n_jobs=-1,
    )
    model.fit(X)

    # Save model
    model_path = ARTIFACTS_DIR / f"model_v{version}.pkl"
    joblib.dump(model, model_path)
    print(f"Model saved → {model_path}")

    # Update manifest
    manifest_path = ARTIFACTS_DIR / "manifest.json"
    manifest: dict = {"models": []}
    if manifest_path.exists():
        with open(manifest_path) as f:
            manifest = json.load(f)
    manifest["models"] = [m for m in manifest["models"] if m["version"] != version]
    manifest["models"].append({
        "version": version,
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "trained_on": "paysim",
        "features": FEATURE_COLUMNS,
        "hyperparameters": {
            "n_estimators": 200,
            "contamination": contamination,
        },
        "training_samples": len(df),
        "contamination": contamination,
        "actual_fraud_rate": float(actual_fraud_rate),
    })
    manifest["models"].sort(key=lambda m: m["version"])
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)
    print(f"Manifest updated → {manifest_path}")

    if evaluate:
        print("\n--- Offline Evaluation (held-out 20%) ---")
        from sklearn.model_selection import train_test_split
        _, X_test, _, y_test = train_test_split(
            X, labels, test_size=0.2, random_state=RANDOM_SEED, stratify=labels
        )
        scores = model.decision_function(X_test)
        # Invert: lower decision_function = more anomalous = higher fraud score
        fraud_scores = -scores

        # Use block threshold from config (default 0.0 on decision_function = anomaly)
        predictions = (scores < 0).astype(int)

        print(classification_report(y_test, predictions, target_names=["normal", "fraud"]))
        try:
            auc = roc_auc_score(y_test, fraud_scores)
            print(f"ROC-AUC: {auc:.4f}")
        except Exception:
            pass

    print(f"\n✓ Model v{version} trained on PaySim data successfully.")
    print(f"  Restart the API (or call PUT /rules/reload) to load the new model.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Train Isolation Forest on PaySim data")
    parser.add_argument("--csv", default="data/paysim.csv")
    parser.add_argument("--version", type=int, default=3, help="Model version to save as")
    parser.add_argument("--sample", type=int, default=None, help="Max training rows (stratified)")
    parser.add_argument("--evaluate", action="store_true", help="Run offline eval after training")
    args = parser.parse_args()

    train(
        csv_path=args.csv,
        version=args.version,
        sample=args.sample,
        evaluate=args.evaluate,
    )


if __name__ == "__main__":
    main()
