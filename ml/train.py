"""
Isolation Forest training script.
Generates synthetic transaction data, trains the model, and saves it with a manifest.

Usage:
    python ml/train.py                    # Train default v1
    python ml/train.py --version 2        # Train and save as v2
    python ml/train.py --contamination 0.08  # Higher fraud assumption

The `contamination` parameter is a direct business lever:
it represents the expected fraction of fraudulent transactions.
Tune it based on your observed fraud rate from the operations team.

Output:
    ml/artifacts/model_v{N}.pkl
    ml/artifacts/manifest.json (updated with new version entry)
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
from sklearn.ensemble import IsolationForest

# Ensure project root is on path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.ml_scorer import FEATURE_COLUMNS

ARTIFACTS_DIR = Path(os.getenv("ML_ARTIFACTS_DIR", "ml/artifacts"))
RANDOM_SEED = 42


def generate_synthetic_data(n_samples: int = 50000, fraud_rate: float = 0.05) -> np.ndarray:
    """
    Generate synthetic transaction feature vectors.
    Normal transactions cluster around typical consumer behavior.
    Fraudulent transactions have extreme values on key signals.
    """
    rng = np.random.default_rng(RANDOM_SEED)
    n_fraud = int(n_samples * fraud_rate)
    n_normal = n_samples - n_fraud

    # --- Normal transactions ---
    normal = np.column_stack([
        rng.lognormal(mean=5.0, sigma=1.2, size=n_normal),       # amount: ~$150 avg
        rng.integers(6, 22, size=n_normal),                        # hour_of_day: business hours
        rng.integers(0, 3, size=n_normal),                         # tx_count_1h: low velocity
        rng.integers(0, 8, size=n_normal),                         # tx_count_24h
        rng.lognormal(mean=5.0, sigma=0.8, size=n_normal),        # avg_amount_30d
        rng.uniform(0.5, 2.5, size=n_normal),                      # amount_vs_avg_ratio
        rng.choice([0, 1], p=[0.9, 0.1], size=n_normal),          # is_new_device
        rng.choice([0, 1], p=[0.95, 0.05], size=n_normal),        # geo_mismatch
        rng.choice([0, 1], p=[0.85, 0.15], size=n_normal),        # is_high_risk_mcc
    ])

    # --- Fraudulent transactions (anomalous patterns) ---
    fraud = np.column_stack([
        rng.lognormal(mean=8.0, sigma=1.5, size=n_fraud),         # amount: very high
        rng.integers(0, 5, size=n_fraud),                          # hour_of_day: odd hours
        rng.integers(5, 20, size=n_fraud),                         # tx_count_1h: high velocity
        rng.integers(15, 50, size=n_fraud),                        # tx_count_24h
        rng.lognormal(mean=4.5, sigma=0.8, size=n_fraud),         # avg_amount_30d: lower baseline
        rng.uniform(5.0, 40.0, size=n_fraud),                      # amount_vs_avg_ratio: extreme
        rng.choice([0, 1], p=[0.3, 0.7], size=n_fraud),           # is_new_device: usually new
        rng.choice([0, 1], p=[0.4, 0.6], size=n_fraud),           # geo_mismatch: usually mismatch
        rng.choice([0, 1], p=[0.3, 0.7], size=n_fraud),           # is_high_risk_mcc: usually high-risk
    ])

    data = np.vstack([normal, fraud])
    # Shuffle
    idx = rng.permutation(len(data))
    return data[idx]


def train(version: int, contamination: float, n_samples: int) -> None:
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)

    print(f"Generating {n_samples:,} synthetic transactions (fraud rate: {contamination:.1%})...")
    X = generate_synthetic_data(n_samples=n_samples, fraud_rate=contamination)

    print(f"Training Isolation Forest v{version}...")
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
    print(f"Model saved to {model_path}")

    # Update manifest
    manifest_path = ARTIFACTS_DIR / "manifest.json"
    manifest: dict = {"models": []}
    if manifest_path.exists():
        with open(manifest_path) as f:
            manifest = json.load(f)

    # Remove existing entry for this version
    manifest["models"] = [m for m in manifest["models"] if m["version"] != version]
    manifest["models"].append({
        "version": version,
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "features": FEATURE_COLUMNS,
        "hyperparameters": {
            "n_estimators": 200,
            "contamination": contamination,
            "max_features": len(FEATURE_COLUMNS),
        },
        "training_samples": n_samples,
        "contamination": contamination,
    })
    manifest["models"].sort(key=lambda m: m["version"])

    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)
    print(f"Manifest updated at {manifest_path}")
    print(f"\n✓ Model v{version} trained successfully.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Train fraud detection Isolation Forest model")
    parser.add_argument("--version", type=int, default=1, help="Model version number")
    parser.add_argument(
        "--contamination",
        type=float,
        default=float(os.getenv("CONTAMINATION_RATE", "0.05")),
        help="Expected fraction of anomalies (fraud rate)",
    )
    parser.add_argument("--samples", type=int, default=50000, help="Training dataset size")
    args = parser.parse_args()

    train(version=args.version, contamination=args.contamination, n_samples=args.samples)


if __name__ == "__main__":
    main()
