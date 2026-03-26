"""Tests for the decision engine."""

import pytest

from app.core.ab_testing import ab_testing
from app.core.decision_engine import evaluate
from app.core.feature_flags import feature_flags
from app.core.rule_engine import rule_engine


@pytest.fixture(autouse=True)
def load_configs() -> None:
    rule_engine.load()
    feature_flags.load()
    ab_testing.load()


def test_low_risk_returns_allow(sample_transaction: dict) -> None:
    result = evaluate(sample_transaction, sample_transaction["user_id"])
    assert result.verdict == "ALLOW"
    assert result.final_score < 40


def test_high_risk_returns_block(high_risk_transaction: dict) -> None:
    result = evaluate(high_risk_transaction, high_risk_transaction["user_id"])
    assert result.verdict == "BLOCK"
    assert result.final_score >= 70


def test_result_has_event_id(sample_transaction: dict) -> None:
    result = evaluate(sample_transaction, "user_1")
    assert result.event_id != ""
    assert len(result.event_id) == 36  # UUID format


def test_result_has_triggered_rules(high_risk_transaction: dict) -> None:
    result = evaluate(high_risk_transaction, "user_1")
    assert len(result.triggered_rules) > 0
    for rule in result.triggered_rules:
        assert "id" in rule
        assert "score_contribution" in rule


def test_latency_is_measured(sample_transaction: dict) -> None:
    result = evaluate(sample_transaction, "user_1")
    assert result.latency_ms >= 0
    assert result.latency_ms < 5000  # Should be fast


def test_model_version_is_set(sample_transaction: dict) -> None:
    result = evaluate(sample_transaction, "user_1")
    assert result.model_version >= 1


def test_rule_blend_weight_is_between_0_and_1(sample_transaction: dict) -> None:
    result = evaluate(sample_transaction, "user_1")
    assert 0.0 <= result.rule_blend_weight <= 1.0


def test_scores_are_within_range(high_risk_transaction: dict) -> None:
    result = evaluate(high_risk_transaction, "user_1")
    assert 0 <= result.rule_score <= 100
    assert 0 <= result.ml_score <= 100
    assert 0 <= result.final_score <= 100


def test_verdict_thresholds_consistent(sample_transaction: dict) -> None:
    result = evaluate(sample_transaction, "user_1")
    if result.verdict == "ALLOW":
        assert result.final_score < result.review_threshold
    elif result.verdict == "REVIEW":
        assert result.review_threshold <= result.final_score < result.block_threshold
    elif result.verdict == "BLOCK":
        assert result.final_score >= result.block_threshold
