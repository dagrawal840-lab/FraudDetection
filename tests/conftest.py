"""
Pytest fixtures shared across all tests.
"""

import os
import sys
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

# Ensure we can import from project root
sys.path.insert(0, str(Path(__file__).parent.parent))

# Use in-memory SQLite for tests
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["APP_ENV"] = "test"
os.environ["API_KEY"] = "test-key"
os.environ["RULES_CONFIG_PATH"] = "config/rules.yaml"
os.environ["FEATURE_FLAGS_PATH"] = "config/feature_flags.yaml"
os.environ["AB_EXPERIMENTS_PATH"] = "config/ab_experiments.yaml"
os.environ["ML_ARTIFACTS_DIR"] = "ml/artifacts"


@pytest.fixture
def sample_transaction() -> dict:
    """A normal transaction that should be ALLOWed."""
    return {
        "transaction_id": "txn_test_001",
        "user_id": "usr_normal",
        "amount": 50.0,
        "currency": "USD",
        "merchant_id": "merch_grocery",
        "merchant_name": "Local Grocery",
        "hour_of_day": 14,
        "tx_count_1h": 1,
        "tx_count_24h": 3,
        "avg_amount_30d": 80.0,
        "amount_vs_avg_ratio": 0.625,
        "is_new_device": False,
        "geo_mismatch": False,
        "is_high_risk_mcc": False,
    }


@pytest.fixture
def high_risk_transaction() -> dict:
    """A high-risk transaction that should be BLOCKed by rules."""
    return {
        "transaction_id": "txn_test_002",
        "user_id": "usr_risky",
        "amount": 9500.0,
        "currency": "USD",
        "merchant_id": "merch_wire",
        "merchant_name": "International Wire",
        "hour_of_day": 2,
        "tx_count_1h": 12,
        "tx_count_24h": 30,
        "avg_amount_30d": 200.0,
        "amount_vs_avg_ratio": 47.5,
        "is_new_device": True,
        "geo_mismatch": True,
        "is_high_risk_mcc": True,
    }


@pytest.fixture
def medium_risk_transaction() -> dict:
    """A medium-risk transaction that should land in REVIEW."""
    return {
        "transaction_id": "txn_test_003",
        "user_id": "usr_medium",
        "amount": 6000.0,
        "currency": "USD",
        "merchant_id": "merch_electronics",
        "merchant_name": "Electronics Store",
        "hour_of_day": 10,
        "tx_count_1h": 2,
        "tx_count_24h": 5,
        "avg_amount_30d": 150.0,
        "amount_vs_avg_ratio": 40.0,
        "is_new_device": False,
        "geo_mismatch": False,
        "is_high_risk_mcc": False,
    }
