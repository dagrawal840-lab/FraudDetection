"""
Integration tests for the FastAPI endpoints.
Uses an in-memory SQLite database.
"""

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.core.ab_testing import ab_testing
from app.core.feature_flags import feature_flags
from app.core.rule_engine import rule_engine
from app.db.database import create_tables, engine
from app.db.models import Base
from app.main import app
from app.services.model_registry import model_registry

HEADERS = {"x-api-key": "test-key"}


@pytest_asyncio.fixture(autouse=True)
async def setup_app() -> None:
    """Initialize configs and DB for each test."""
    rule_engine.load()
    feature_flags.load()
    ab_testing.load()
    model_registry.load_all()
    await create_tables()


@pytest_asyncio.fixture
async def client() -> AsyncClient:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac


@pytest.mark.asyncio
async def test_health_check(client: AsyncClient) -> None:
    resp = await client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"


@pytest.mark.asyncio
async def test_evaluate_normal_transaction(
    client: AsyncClient, sample_transaction: dict
) -> None:
    resp = await client.post("/v1/transactions/evaluate", json=sample_transaction)
    assert resp.status_code == 200
    data = resp.json()
    assert data["verdict"] in ("ALLOW", "REVIEW", "BLOCK")
    assert "final_score" in data
    assert "event_id" in data
    assert "triggered_rules" in data
    assert "latency_ms" in data


@pytest.mark.asyncio
async def test_evaluate_high_risk_returns_block(
    client: AsyncClient, high_risk_transaction: dict
) -> None:
    resp = await client.post("/v1/transactions/evaluate", json=high_risk_transaction)
    assert resp.status_code == 200
    data = resp.json()
    assert data["verdict"] == "BLOCK"
    assert data["final_score"] >= 70
    assert len(data["triggered_rules"]) > 0


@pytest.mark.asyncio
async def test_evaluate_response_has_explainability(
    client: AsyncClient, high_risk_transaction: dict
) -> None:
    resp = await client.post("/v1/transactions/evaluate", json=high_risk_transaction)
    data = resp.json()
    for rule in data["triggered_rules"]:
        assert "id" in rule
        assert "description" in rule
        assert "score_contribution" in rule
        assert "actual_value" in rule


@pytest.mark.asyncio
async def test_audit_trail_after_evaluation(
    client: AsyncClient, sample_transaction: dict
) -> None:
    # Evaluate first
    await client.post("/v1/transactions/evaluate", json=sample_transaction)
    # Then fetch audit trail
    txn_id = sample_transaction["transaction_id"]
    resp = await client.get(f"/v1/transactions/{txn_id}/audit")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    assert data["events"][0]["verdict"] in ("ALLOW", "REVIEW", "BLOCK")


@pytest.mark.asyncio
async def test_audit_trail_404_for_unknown(client: AsyncClient) -> None:
    resp = await client.get("/v1/transactions/nonexistent_txn_xyz/audit")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_list_rules(client: AsyncClient) -> None:
    resp = await client.get("/v1/rules")
    assert resp.status_code == 200
    data = resp.json()
    assert "rules" in data
    assert data["total_rules"] > 0
    assert data["enabled_rules"] > 0


@pytest.mark.asyncio
async def test_reload_rules(client: AsyncClient) -> None:
    resp = await client.put("/v1/rules/reload")
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["rules_loaded"] > 0


@pytest.mark.asyncio
async def test_list_experiments(client: AsyncClient) -> None:
    resp = await client.get("/v1/experiments")
    assert resp.status_code == 200
    data = resp.json()
    assert "experiments" in data
    assert isinstance(data["experiments"], list)


@pytest.mark.asyncio
async def test_experiment_variant_assignment(client: AsyncClient) -> None:
    resp = await client.get("/v1/experiments/exp_ml_model_v2/assign/user_test_123")
    assert resp.status_code == 200
    data = resp.json()
    assert "variant" in data
    assert data["variant"] in ("control", "treatment")


@pytest.mark.asyncio
async def test_experiment_assignment_is_deterministic(client: AsyncClient) -> None:
    resp1 = await client.get("/v1/experiments/exp_ml_model_v2/assign/user_stable_456")
    resp2 = await client.get("/v1/experiments/exp_ml_model_v2/assign/user_stable_456")
    assert resp1.json()["variant"] == resp2.json()["variant"]


@pytest.mark.asyncio
async def test_metrics_dashboard(client: AsyncClient, sample_transaction: dict) -> None:
    # Seed some data
    await client.post("/v1/transactions/evaluate", json=sample_transaction)
    resp = await client.get("/v1/metrics/dashboard")
    assert resp.status_code == 200
    data = resp.json()
    assert "windows" in data
    assert "1h" in data["windows"]
    assert "24h" in data["windows"]
    assert "7d" in data["windows"]
    assert "fraud_block_rate" in data["windows"]["1h"]


@pytest.mark.asyncio
async def test_invalid_transaction_returns_422(client: AsyncClient) -> None:
    resp = await client.post(
        "/v1/transactions/evaluate",
        json={"amount": -100},  # Missing required fields, negative amount
    )
    assert resp.status_code == 422
