"""
PaySim CSV → Fraud Detection API ingestion pipeline.

Reads the PaySim dataset, engineers features that match our API schema,
evaluates each transaction, and writes a results CSV for analysis.

Usage:
    python scripts/ingest_paysim.py --csv data/paysim.csv
    python scripts/ingest_paysim.py --csv data/paysim.csv --sample 10000
    python scripts/ingest_paysim.py --csv data/paysim.csv --fraud-only
    python scripts/ingest_paysim.py --csv data/paysim.csv --output results/paysim_results.csv

PaySim column → API field mapping
----------------------------------
nameOrig             → user_id
nameDest             → merchant_id
amount               → amount
step % 24            → hour_of_day
type IN (TRANSFER,   → is_high_risk_mcc
         CASH-OUT)
isFraud              → ground_truth (not sent to API, used for evaluation)
velocity (computed)  → tx_count_1h, tx_count_24h
balance deviation    → amount_vs_avg_ratio
new dest account     → is_new_device (proxy)
dest is merchant (M) → geo_mismatch=False; dest is customer (C) → geo_mismatch=True
"""

import argparse
import csv
import sys
import time
import uuid
from collections import defaultdict
from pathlib import Path

import pandas as pd
import requests

sys.path.insert(0, str(Path(__file__).parent.parent))

API_BASE = "http://localhost:8080"
EVALUATE_URL = f"{API_BASE}/v1/transactions/evaluate"

# PaySim transaction types that are high-risk
HIGH_RISK_TYPES = {"TRANSFER", "CASH_OUT", "CASH-OUT"}


# ---------------------------------------------------------------------------
# Feature engineering
# ---------------------------------------------------------------------------

def engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add derived columns that map to our API schema.
    All computation is done upfront so the ingestion loop is fast.
    """
    print("Engineering features...")

    # Velocity: count transactions per user per step window
    # step = 1-hour unit, so tx_count_1h = count in same step
    step_user_counts = df.groupby(["step", "nameOrig"]).cumcount()
    df["tx_count_1h"] = step_user_counts + 1  # 1-indexed

    # tx_count_24h: count per user in 24-step window (approximate with day bucket)
    df["day"] = df["step"] // 24
    day_user_counts = df.groupby(["day", "nameOrig"]).cumcount()
    df["tx_count_24h"] = day_user_counts + 1

    # avg_amount_30d: approximate with global mean per user (full dataset proxy)
    user_avg = df.groupby("nameOrig")["amount"].transform("mean")
    df["avg_amount_30d"] = user_avg.round(2)

    # amount_vs_avg_ratio
    df["amount_vs_avg_ratio"] = (df["amount"] / df["avg_amount_30d"].replace(0, 1)).round(2)

    # hour_of_day from step
    df["hour_of_day"] = df["step"] % 24

    # is_high_risk_mcc: TRANSFER and CASH-OUT are high-risk transaction types
    df["is_high_risk_mcc"] = df["type"].isin(HIGH_RISK_TYPES)

    # is_new_device: proxy — first time this origin→destination pair appears
    pair_seen = set()
    is_new_device = []
    for _, row in df[["nameOrig", "nameDest"]].iterrows():
        pair = (row["nameOrig"], row["nameDest"])
        is_new_device.append(pair not in pair_seen)
        pair_seen.add(pair)
    df["is_new_device"] = is_new_device

    # geo_mismatch: proxy — destination is another customer account (C prefix)
    # In PaySim, merchants start with 'M', customers with 'C'
    df["geo_mismatch"] = df["nameDest"].str.startswith("C")

    print(f"  Features engineered on {len(df):,} rows")
    return df


def row_to_api_payload(row: pd.Series) -> dict:
    return {
        "transaction_id": f"paysim_{row['nameOrig']}_{row['step']}_{uuid.uuid4().hex[:6]}",
        "user_id": row["nameOrig"],
        "amount": float(row["amount"]),
        "currency": "USD",
        "merchant_id": row["nameDest"],
        "merchant_name": f"{row['type']} / {row['nameDest'][:8]}",
        "hour_of_day": int(row["hour_of_day"]),
        "tx_count_1h": int(row["tx_count_1h"]),
        "tx_count_24h": int(row["tx_count_24h"]),
        "avg_amount_30d": float(row["avg_amount_30d"]),
        "amount_vs_avg_ratio": float(row["amount_vs_avg_ratio"]),
        "is_new_device": bool(row["is_new_device"]),
        "geo_mismatch": bool(row["geo_mismatch"]),
        "is_high_risk_mcc": bool(row["is_high_risk_mcc"]),
    }


# ---------------------------------------------------------------------------
# Ingestion loop
# ---------------------------------------------------------------------------

def ingest(
    csv_path: str,
    sample: int | None,
    fraud_only: bool,
    output_path: str,
    batch_size: int = 100,
) -> None:
    path = Path(csv_path)
    if not path.exists():
        print(f"ERROR: {csv_path} not found.")
        print("See data/README.md for download instructions.")
        sys.exit(1)

    # Check API is reachable
    try:
        requests.get(f"{API_BASE}/health", timeout=3).raise_for_status()
    except Exception:
        print(f"ERROR: API not reachable at {API_BASE}. Run 'make run' first.")
        sys.exit(1)

    print(f"Loading {csv_path}...")
    df = pd.read_csv(csv_path)
    print(f"  Loaded {len(df):,} rows")

    if fraud_only:
        df = df[df["isFraud"] == 1]
        print(f"  Filtered to {len(df):,} fraud rows")

    if sample:
        # Stratified sample: preserve fraud ratio
        fraud_df = df[df["isFraud"] == 1]
        normal_df = df[df["isFraud"] == 0]
        fraud_n = min(len(fraud_df), int(sample * len(fraud_df) / len(df)))
        normal_n = sample - fraud_n
        df = pd.concat([
            fraud_df.sample(min(fraud_n, len(fraud_df)), random_state=42),
            normal_df.sample(min(normal_n, len(normal_df)), random_state=42),
        ]).sample(frac=1, random_state=42).reset_index(drop=True)
        print(f"  Sampled {len(df):,} rows ({fraud_n} fraud, {normal_n} normal)")

    df = engineer_features(df)

    # Results tracking
    results = []
    stats = {"ALLOW": 0, "REVIEW": 0, "BLOCK": 0, "ERROR": 0}
    confusion = {"TP": 0, "FP": 0, "TN": 0, "FN": 0}  # vs isFraud ground truth

    print(f"\nEvaluating {len(df):,} transactions against API...")
    start = time.time()

    for i, (_, row) in enumerate(df.iterrows()):
        payload = row_to_api_payload(row)
        ground_truth = int(row["isFraud"])

        try:
            resp = requests.post(EVALUATE_URL, json=payload, timeout=5)
            resp.raise_for_status()
            result = resp.json()
            verdict = result["verdict"]
            final_score = result["final_score"]
            triggered = [r["id"] for r in result["triggered_rules"]]
        except Exception as e:
            stats["ERROR"] += 1
            verdict, final_score, triggered = "ERROR", -1, []

        stats[verdict] = stats.get(verdict, 0) + 1

        # Confusion matrix: BLOCK = predicted fraud
        predicted_fraud = 1 if verdict == "BLOCK" else 0
        if predicted_fraud == 1 and ground_truth == 1:
            confusion["TP"] += 1
        elif predicted_fraud == 1 and ground_truth == 0:
            confusion["FP"] += 1
        elif predicted_fraud == 0 and ground_truth == 1:
            confusion["FN"] += 1
        else:
            confusion["TN"] += 1

        results.append({
            "transaction_id": payload["transaction_id"],
            "user_id": payload["user_id"],
            "amount": payload["amount"],
            "type": row["type"],
            "step": row["step"],
            "ground_truth_fraud": ground_truth,
            "verdict": verdict,
            "final_score": final_score,
            "rule_score": result.get("rule_score", -1),
            "ml_score": result.get("ml_score", -1),
            "triggered_rules": "|".join(triggered),
        })

        if (i + 1) % 500 == 0:
            elapsed = time.time() - start
            rate = (i + 1) / elapsed
            print(f"  {i+1:,}/{len(df):,} ({rate:.0f}/s) — "
                  f"BLOCK:{stats['BLOCK']} REVIEW:{stats['REVIEW']} ALLOW:{stats['ALLOW']}")

    elapsed = time.time() - start

    # Save results
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(results).to_csv(out, index=False)
    print(f"\nResults saved to {out}")

    # Print summary
    total = len(df)
    tp, fp, fn, tn = confusion["TP"], confusion["FP"], confusion["FN"], confusion["TN"]
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0

    print(f"""
=== PaySim Ingestion Summary ===
Rows processed:   {total:,}
Time elapsed:     {elapsed:.1f}s  ({total/elapsed:.0f} tx/s)

Verdict distribution:
  BLOCK:   {stats['BLOCK']:>6,}  ({stats['BLOCK']/total*100:.1f}%)
  REVIEW:  {stats['REVIEW']:>6,}  ({stats['REVIEW']/total*100:.1f}%)
  ALLOW:   {stats['ALLOW']:>6,}  ({stats['ALLOW']/total*100:.1f}%)

vs Ground Truth (isFraud):
  True Positives (correctly blocked fraud):  {tp:>6,}
  False Positives (legitimate → blocked):    {fp:>6,}
  True Negatives (legitimate → allowed):     {tn:>6,}
  False Negatives (fraud → allowed):         {fn:>6,}

  Precision: {precision:.3f}   (of what we blocked, how much was real fraud)
  Recall:    {recall:.3f}   (of all fraud, how much we caught)
  F1 Score:  {f1:.3f}
""")


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest PaySim CSV into Fraud Detection API")
    parser.add_argument("--csv", default="data/paysim.csv", help="Path to PaySim CSV")
    parser.add_argument("--sample", type=int, default=None, help="Stratified sample size")
    parser.add_argument("--fraud-only", action="store_true", help="Only evaluate fraud rows")
    parser.add_argument("--output", default="data/paysim_results.csv", help="Output CSV path")
    args = parser.parse_args()

    ingest(
        csv_path=args.csv,
        sample=args.sample,
        fraud_only=args.fraud_only,
        output_path=args.output,
    )


if __name__ == "__main__":
    main()
