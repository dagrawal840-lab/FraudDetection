"""
ML-based anomaly scorer using Isolation Forest.
The model is loaded from ml/artifacts/ via the model registry.
Returns an anomaly score normalized to 0–100 (100 = most anomalous).
"""

from __future__ import annotations

import numpy as np


# Feature schema — must match ml/train.py feature list
FEATURE_COLUMNS = [
    "amount",
    "hour_of_day",
    "tx_count_1h",
    "tx_count_24h",
    "avg_amount_30d",
    "amount_vs_avg_ratio",
    "is_new_device",
    "geo_mismatch",
    "is_high_risk_mcc",
]


def extract_features(transaction: dict) -> np.ndarray:
    """Convert transaction dict to numpy feature vector."""
    row = []
    for col in FEATURE_COLUMNS:
        val = transaction.get(col, 0)
        # Convert booleans to int
        if isinstance(val, bool):
            val = int(val)
        row.append(float(val))
    return np.array(row).reshape(1, -1)


def score_transaction(model: object, transaction: dict) -> float:
    """
    Returns an anomaly score in [0, 100].
    Isolation Forest decision_function returns more negative values for anomalies.
    We invert and normalize: score 100 = highly anomalous.
    """
    features = extract_features(transaction)
    # decision_function: lower (more negative) = more anomalous
    raw_score = float(model.decision_function(features)[0])  # type: ignore[union-attr]
    # Normalize: typical range is roughly [-0.5, 0.5]
    # Clamp to [-0.5, 0.5] then rescale to [0, 100], inverted
    clamped = max(-0.5, min(0.5, raw_score))
    normalized = (0.5 - clamped) * 100  # 0 = normal, 100 = anomalous
    return round(normalized, 2)
