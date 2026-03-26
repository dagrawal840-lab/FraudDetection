"""
Rules management endpoints.
GET  /v1/rules         — view current rules config
PUT  /v1/rules/reload  — hot-reload rules from YAML (no restart needed)

This is the "no-code interface" for risk analysts:
edit config/rules.yaml → call reload → changes are live immediately.
"""

import logging

from fastapi import APIRouter

from app.api.models.rule import ReloadResponse, RuleSummary, RulesResponse
from app.core.rule_engine import rule_engine

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/v1/rules", tags=["Rules"])


@router.get("", response_model=RulesResponse)
async def list_rules() -> RulesResponse:
    """Return the current rules configuration including thresholds and blend weight."""
    rules = rule_engine.get_rules_summary()
    return RulesResponse(
        version="current",
        rule_blend_weight=rule_engine.rule_blend_weight,
        thresholds=rule_engine.thresholds,
        rules=[RuleSummary(**r) for r in rules],
        total_rules=len(rules),
        enabled_rules=sum(1 for r in rules if r["enabled"]),
    )


@router.put("/reload", response_model=ReloadResponse)
async def reload_rules() -> ReloadResponse:
    """
    Hot-reload rules from config/rules.yaml.
    Call this after editing the config to apply changes without restarting the server.
    Access should be restricted to fraud analysts and on-call engineers.
    """
    try:
        rule_engine.reload()
        rules = rule_engine.get_rules_summary()
        enabled = sum(1 for r in rules if r["enabled"])
        logger.info(f"Rules reloaded: {len(rules)} rules, {enabled} enabled")
        return ReloadResponse(
            success=True,
            message=f"Rules reloaded successfully. {len(rules)} rules loaded, {enabled} enabled.",
            rules_loaded=len(rules),
        )
    except Exception as e:
        logger.error(f"Rule reload failed: {e}")
        return ReloadResponse(success=False, message=str(e), rules_loaded=0)
