"""
Decision engine — the central orchestrator.
Combines rule-based scoring and ML anomaly scoring into a single verdict.
Every decision is fully explainable and audit-logged.

Verdict thresholds (configurable in config/rules.yaml):
  ALLOW  → final_score < review_threshold
  REVIEW → review_threshold <= final_score < block_threshold
  BLOCK  → final_score >= block_threshold
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from app.core.ab_testing import ab_testing
from app.core.feature_flags import feature_flags
from app.core.ml_scorer import score_transaction
from app.core.rule_engine import RuleResult, rule_engine
from app.services.model_registry import model_registry

# Primary experiment ID used to test model versions
PRIMARY_EXPERIMENT = "exp_ml_model_v2"


@dataclass
class EvaluationResult:
    event_id: str
    transaction_id: str
    user_id: str
    verdict: str  # ALLOW / REVIEW / BLOCK
    final_score: float
    rule_score: float
    ml_score: float
    rule_blend_weight: float
    triggered_rules: list[dict[str, Any]]
    review_threshold: float
    block_threshold: float
    model_version: int
    experiment_id: str | None
    experiment_variant: str | None
    latency_ms: float
    ml_enabled: bool
    flags_applied: list[str] = field(default_factory=list)


def evaluate(transaction: dict[str, Any], user_id: str) -> EvaluationResult:
    """
    Evaluate a transaction and return a verdict with full explainability.
    This is the core hot path — keep it fast.
    """
    start = time.perf_counter()
    event_id = str(uuid.uuid4())
    transaction_id = transaction.get("transaction_id", event_id)

    # --- Feature flag checks ---
    ml_enabled = feature_flags.is_enabled("ml_scoring_enabled", user_id)
    flags_applied = []
    if ml_enabled:
        flags_applied.append("ml_scoring_enabled")

    # --- A/B experiment assignment ---
    experiment_variant, experiment_config = ab_testing.assign_variant(
        user_id, PRIMARY_EXPERIMENT
    )
    experiment_id = PRIMARY_EXPERIMENT if experiment_variant != "control" else None

    # Determine model version from experiment config or default
    model_version = int(experiment_config.get("model_version", model_registry.default_version))

    # Determine rule blend weight from experiment config or rules.yaml
    rule_blend_weight = float(
        experiment_config.get("rule_blend_weight", rule_engine.rule_blend_weight)
    )

    # --- Rule engine scoring ---
    rule_result: RuleResult = rule_engine.score(transaction)

    # --- ML scoring (gated by feature flag) ---
    ml_score = 0.0
    if ml_enabled:
        model = model_registry.get(model_version)
        if model is not None:
            ml_score = score_transaction(model, transaction)

    # --- Score blending ---
    if ml_enabled and ml_score > 0:
        final_score = (rule_blend_weight * rule_result.score) + (
            (1 - rule_blend_weight) * ml_score
        )
    else:
        final_score = rule_result.score

    final_score = round(min(final_score, 100.0), 2)

    # --- Verdict determination ---
    thresholds = rule_engine.thresholds
    review_threshold = float(thresholds.get("review", 40))
    block_threshold = float(thresholds.get("block", 70))

    if final_score >= block_threshold:
        verdict = "BLOCK"
    elif final_score >= review_threshold:
        verdict = "REVIEW"
    else:
        verdict = "ALLOW"

    latency_ms = round((time.perf_counter() - start) * 1000, 2)

    return EvaluationResult(
        event_id=event_id,
        transaction_id=transaction_id,
        user_id=user_id,
        verdict=verdict,
        final_score=final_score,
        rule_score=round(rule_result.score, 2),
        ml_score=round(ml_score, 2),
        rule_blend_weight=rule_blend_weight,
        triggered_rules=[
            {
                "id": r.id,
                "description": r.description,
                "score_contribution": r.score_contribution,
                "field": r.field,
                "actual_value": r.actual_value,
            }
            for r in rule_result.triggered_rules
        ],
        review_threshold=review_threshold,
        block_threshold=block_threshold,
        model_version=model_version,
        experiment_id=experiment_id,
        experiment_variant=experiment_variant,
        latency_ms=latency_ms,
        ml_enabled=ml_enabled,
        flags_applied=flags_applied,
    )
