"""
Transaction evaluation endpoint — the primary API surface.
POST /v1/transactions/evaluate
GET  /v1/transactions/{transaction_id}/audit
"""

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.models.transaction import EvaluationResponse, TransactionRequest, TriggeredRuleResponse
from app.core.decision_engine import evaluate
from app.db.database import get_db
from app.services import audit_logger

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/v1/transactions", tags=["Transactions"])


@router.post("/evaluate", response_model=EvaluationResponse, status_code=200)
async def evaluate_transaction(
    request: TransactionRequest,
    db: AsyncSession = Depends(get_db),
) -> EvaluationResponse:
    """
    Evaluate a transaction for fraud risk.

    Returns a verdict (ALLOW / REVIEW / BLOCK) with a full explainability payload
    including which rules fired, scores from each engine, and experiment variant info.
    """
    transaction_dict = request.model_dump()
    result = evaluate(transaction_dict, request.user_id)

    # Persist audit record (async, non-blocking on failure)
    try:
        await audit_logger.log_evaluation(result, db, request_payload=transaction_dict)
    except Exception as e:
        logger.warning(f"Audit log failed — evaluation still returned: {e}")

    return EvaluationResponse(
        event_id=result.event_id,
        transaction_id=result.transaction_id,
        user_id=result.user_id,
        verdict=result.verdict,
        final_score=result.final_score,
        rule_score=result.rule_score,
        ml_score=result.ml_score,
        rule_blend_weight=result.rule_blend_weight,
        review_threshold=result.review_threshold,
        block_threshold=result.block_threshold,
        triggered_rules=[
            TriggeredRuleResponse(
                id=r["id"],
                description=r["description"],
                score_contribution=r["score_contribution"],
                field=r["field"],
                actual_value=r["actual_value"],
            )
            for r in result.triggered_rules
        ],
        model_version=result.model_version,
        experiment_id=result.experiment_id,
        experiment_variant=result.experiment_variant,
        ml_enabled=result.ml_enabled,
        latency_ms=result.latency_ms,
    )


@router.get("/{transaction_id}/audit", status_code=200)
async def get_transaction_audit(
    transaction_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Retrieve the full audit trail for a transaction.
    Returns all evaluation events in reverse chronological order.
    Supports regulatory review and analyst investigation workflows.
    """
    trail = await audit_logger.get_audit_trail(transaction_id, db)
    if not trail:
        raise HTTPException(status_code=404, detail=f"No audit records found for {transaction_id}")
    return {"transaction_id": transaction_id, "events": trail, "total": len(trail)}
