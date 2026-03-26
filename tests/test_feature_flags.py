"""Tests for feature flag service."""

import pytest

from app.core.feature_flags import FeatureFlagService


@pytest.fixture
def flags() -> FeatureFlagService:
    svc = FeatureFlagService()
    svc.load()
    return svc


def test_enabled_flag_returns_true(flags: FeatureFlagService) -> None:
    assert flags.is_enabled("ml_scoring_enabled", "user_1") is True


def test_disabled_flag_returns_false(flags: FeatureFlagService) -> None:
    assert flags.is_enabled("strict_geo_check", "user_1") is False


def test_unknown_flag_returns_false(flags: FeatureFlagService) -> None:
    assert flags.is_enabled("nonexistent_flag", "user_1") is False


def test_deterministic_assignment(flags: FeatureFlagService) -> None:
    """Same user always gets same assignment."""
    result1 = flags.is_enabled("new_velocity_model", "user_abc")
    result2 = flags.is_enabled("new_velocity_model", "user_abc")
    assert result1 == result2


def test_different_users_may_get_different_assignment(flags: FeatureFlagService) -> None:
    """With 20% rollout, not all users should be enabled."""
    results = [flags.is_enabled("new_velocity_model", f"user_{i}") for i in range(200)]
    # With 20% rollout, we expect roughly 20% True
    enabled_count = sum(results)
    # Allow generous range due to hash distribution
    assert 10 <= enabled_count <= 60, f"Expected ~40/200, got {enabled_count}"


def test_100_pct_rollout_always_enabled(flags: FeatureFlagService) -> None:
    for i in range(20):
        assert flags.is_enabled("ml_scoring_enabled", f"user_{i}") is True


def test_get_all_returns_dict(flags: FeatureFlagService) -> None:
    all_flags = flags.get_all()
    assert isinstance(all_flags, dict)
    assert "ml_scoring_enabled" in all_flags


def test_reload_preserves_state(flags: FeatureFlagService) -> None:
    before = flags.is_enabled("ml_scoring_enabled", "user_1")
    flags.reload()
    after = flags.is_enabled("ml_scoring_enabled", "user_1")
    assert before == after
