"""
Structured audit logger.
Every fraud evaluation produces an immutable audit record.
This satisfies regulatory requirements (PCI-DSS, SOC2) for decision traceability.
"""

import asyncio
import json
import logging
from typing import TYPE_CHECKING, Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AuditLog

if TYPE_CHECKING:
    from app.core.decision_engine import EvaluationResult

logger = logging.getLogger(__name__)


async def log_evaluation(
    result: "EvaluationResult",
    db: AsyncSession,
    request_payload: dict[str, Any] | None = None,
) -> None:
    """Persist an evaluation result to the audit log."""
    record = AuditLog(
        event_id=result.event_id,
        transaction_id=result.transaction_id,
        user_id=result.user_id,
        verdict=result.verdict,
        rule_score=result.rule_score,
        ml_score=result.ml_score,
        final_score=result.final_score,
        rule_blend_weight=result.rule_blend_weight,
        triggered_rules=json.dumps(result.triggered_rules),
        experiment_id=result.experiment_id,
        experiment_variant=result.experiment_variant,
        model_version=result.model_version,
        latency_ms=result.latency_ms,
        api_version="v1",
        request_payload=json.dumps(request_payload) if request_payload else None,
    )
    try:
        db.add(record)
        await db.commit()
    except Exception as e:
        logger.error(f"Audit log write failed for event {result.event_id}: {e}")
        await db.rollback()


async def get_audit_trail(
    transaction_id: str,
    db: AsyncSession,
) -> list[dict[str, Any]]:
    """Retrieve the full audit trail for a transaction."""
    from sqlalchemy import select

    stmt = (
        select(AuditLog)
        .where(AuditLog.transaction_id == transaction_id)
        .order_by(AuditLog.timestamp.desc())
    )
    result = await db.execute(stmt)
    rows = result.scalars().all()
    return [
        {
            "event_id": r.event_id,
            "timestamp": r.timestamp.isoformat(),
            "verdict": r.verdict,
            "final_score": r.final_score,
            "rule_score": r.rule_score,
            "ml_score": r.ml_score,
            "triggered_rules": json.loads(r.triggered_rules),
            "experiment_variant": r.experiment_variant,
            "model_version": r.model_version,
            "latency_ms": r.latency_ms,
        }
        for r in rows
    ]
