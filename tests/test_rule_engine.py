"""Tests for the rule engine."""

import pytest

from app.core.rule_engine import RuleEngine


@pytest.fixture
def engine() -> RuleEngine:
    e = RuleEngine()
    e.load()
    return e


def test_normal_transaction_scores_low(engine: RuleEngine, sample_transaction: dict) -> None:
    result = engine.score(sample_transaction)
    assert result.score < 40, f"Expected low score, got {result.score}"
    assert len(result.triggered_rules) == 0


def test_high_amount_rule_fires(engine: RuleEngine) -> None:
    tx = {"amount": 6000.0}
    result = engine.score(tx)
    triggered_ids = [r.id for r in result.triggered_rules]
    assert "high_amount" in triggered_ids


def test_velocity_rule_fires(engine: RuleEngine) -> None:
    tx = {"tx_count_1h": 10}
    result = engine.score(tx)
    triggered_ids = [r.id for r in result.triggered_rules]
    assert "velocity_1h" in triggered_ids


def test_geo_mismatch_rule_fires(engine: RuleEngine) -> None:
    tx = {"geo_mismatch": True}
    result = engine.score(tx)
    triggered_ids = [r.id for r in result.triggered_rules]
    assert "geo_mismatch" in triggered_ids


def test_new_device_rule_fires(engine: RuleEngine) -> None:
    tx = {"is_new_device": True}
    result = engine.score(tx)
    triggered_ids = [r.id for r in result.triggered_rules]
    assert "new_device" in triggered_ids


def test_high_risk_transaction_scores_high(engine: RuleEngine, high_risk_transaction: dict) -> None:
    result = engine.score(high_risk_transaction)
    assert result.score >= 70, f"Expected high score, got {result.score}"


def test_score_is_capped_at_100(engine: RuleEngine, high_risk_transaction: dict) -> None:
    result = engine.score(high_risk_transaction)
    assert result.score <= 100.0


def test_disabled_rule_does_not_fire(engine: RuleEngine) -> None:
    # odd_hour rule is disabled in config
    tx = {"hour_of_day": 2}
    result = engine.score(tx)
    triggered_ids = [r.id for r in result.triggered_rules]
    assert "odd_hour" not in triggered_ids


def test_between_operator(engine: RuleEngine) -> None:
    # Enable odd_hour temporarily to test between operator
    for rule in engine._rules:
        if rule["id"] == "odd_hour":
            rule["enabled"] = True
    tx = {"hour_of_day": 3}
    result = engine.score(tx)
    triggered_ids = [r.id for r in result.triggered_rules]
    assert "odd_hour" in triggered_ids
    # Restore
    for rule in engine._rules:
        if rule["id"] == "odd_hour":
            rule["enabled"] = False


def test_missing_field_does_not_crash(engine: RuleEngine) -> None:
    result = engine.score({})
    assert result.score == 0.0
    assert result.triggered_rules == []


def test_reload_does_not_change_behavior(engine: RuleEngine, sample_transaction: dict) -> None:
    score_before = engine.score(sample_transaction).score
    engine.reload()
    score_after = engine.score(sample_transaction).score
    assert score_before == score_after
