"""
Seed script — generates synthetic transaction evaluations to populate the dashboard.
Useful for demos and development.

Usage:
    python scripts/seed_data.py
    python scripts/seed_data.py --count 500
"""

import argparse
import asyncio
import os
import random
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./fraud_detection.db")

from app.core.ab_testing import ab_testing
from app.core.decision_engine import evaluate
from app.core.feature_flags import feature_flags
from app.core.rule_engine import rule_engine
from app.db.database import AsyncSessionLocal, create_tables
from app.services import audit_logger
from app.services.model_registry import model_registry

rng = random.Random(42)

MERCHANT_NAMES = [
    "Whole Foods Market", "Amazon", "Shell Gas Station", "Starbucks",
    "Best Buy", "Target", "International Wire Transfer", "Crypto Exchange",
    "Online Casino", "Foreign Currency Exchange", "Apple Store", "Uber",
]


def make_transaction(fraud_probability: float = 0.05) -> dict:
    is_fraud = rng.random() < fraud_probability
    if is_fraud:
        return {
            "transaction_id": f"txn_{uuid.uuid4().hex[:12]}",
            "user_id": f"usr_{rng.randint(1, 100):04d}",
            "amount": round(rng.uniform(3000, 12000), 2),
            "currency": "USD",
            "merchant_id": f"merch_{rng.randint(1, 20):03d}",
            "merchant_name": rng.choice(MERCHANT_NAMES[-4:]),
            "hour_of_day": rng.randint(0, 4),
            "tx_count_1h": rng.randint(6, 20),
            "tx_count_24h": rng.randint(20, 50),
            "avg_amount_30d": round(rng.uniform(50, 300), 2),
            "amount_vs_avg_ratio": round(rng.uniform(10, 50), 2),
            "is_new_device": rng.random() > 0.3,
            "geo_mismatch": rng.random() > 0.4,
            "is_high_risk_mcc": rng.random() > 0.3,
        }
    else:
        avg = round(rng.uniform(30, 500), 2)
        amount = round(avg * rng.uniform(0.5, 2.5), 2)
        return {
            "transaction_id": f"txn_{uuid.uuid4().hex[:12]}",
            "user_id": f"usr_{rng.randint(1, 500):04d}",
            "amount": amount,
            "currency": "USD",
            "merchant_id": f"merch_{rng.randint(1, 50):03d}",
            "merchant_name": rng.choice(MERCHANT_NAMES[:8]),
            "hour_of_day": rng.randint(8, 21),
            "tx_count_1h": rng.randint(0, 3),
            "tx_count_24h": rng.randint(0, 8),
            "avg_amount_30d": avg,
            "amount_vs_avg_ratio": round(amount / avg, 2),
            "is_new_device": rng.random() > 0.9,
            "geo_mismatch": rng.random() > 0.95,
            "is_high_risk_mcc": rng.random() > 0.85,
        }


async def seed(count: int = 200) -> None:
    print("Loading configs...")
    rule_engine.load()
    feature_flags.load()
    ab_testing.load()
    model_registry.load_all()
    await create_tables()

    verdicts = {"ALLOW": 0, "REVIEW": 0, "BLOCK": 0}
    print(f"Seeding {count} transactions...")

    async with AsyncSessionLocal() as db:
        for i in range(count):
            tx = make_transaction(fraud_probability=0.08)
            result = evaluate(tx, tx["user_id"])
            verdicts[result.verdict] += 1
            await audit_logger.log_evaluation(result, db, request_payload=tx)
            if (i + 1) % 50 == 0:
                print(f"  {i + 1}/{count} done...")

    print(f"\n✓ Seeded {count} transactions:")
    for verdict, count_v in verdicts.items():
        pct = count_v / count * 100
        print(f"  {verdict}: {count_v} ({pct:.1f}%)")
    print("\nRun the API and visit GET /v1/metrics/dashboard to see results.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed demo transaction data")
    parser.add_argument("--count", type=int, default=200, help="Number of transactions to generate")
    args = parser.parse_args()
    asyncio.run(seed(args.count))


if __name__ == "__main__":
    main()
