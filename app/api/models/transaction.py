"""
Pydantic request/response models for the transaction evaluation endpoint.
Field descriptions double as API documentation in the Swagger UI.
"""

from typing import Any

from pydantic import BaseModel, Field


class TransactionRequest(BaseModel):
    """
    Input features for fraud evaluation.
    Enrichment fields (tx_count_1h, avg_amount_30d, etc.) are expected to be
    pre-computed by the calling service before hitting this API.
    """

    transaction_id: str = Field(..., description="Unique transaction identifier")
    user_id: str = Field(..., description="User/account identifier")
    amount: float = Field(..., gt=0, description="Transaction amount in USD")
    currency: str = Field(default="USD", description="ISO 4217 currency code")
    merchant_id: str = Field(..., description="Merchant identifier")
    merchant_name: str = Field(default="", description="Human-readable merchant name")
    hour_of_day: int = Field(..., ge=0, le=23, description="Hour of day in user's local timezone")

    # Velocity features (pre-computed by caller)
    tx_count_1h: int = Field(default=0, ge=0, description="Transactions by user in past 1 hour")
    tx_count_24h: int = Field(default=0, ge=0, description="Transactions by user in past 24 hours")

    # Historical baseline features
    avg_amount_30d: float = Field(
        default=0.0, ge=0, description="User's average transaction amount over past 30 days"
    )
    amount_vs_avg_ratio: float = Field(
        default=1.0,
        ge=0,
        description="Current amount / 30-day average (pre-compute or leave 1.0 if no history)",
    )

    # Device / geo signals
    is_new_device: bool = Field(
        default=False, description="True if device fingerprint not seen before for this user"
    )
    geo_mismatch: bool = Field(
        default=False, description="True if transaction country differs from user's profile country"
    )
    is_high_risk_mcc: bool = Field(
        default=False,
        description="True if merchant category code is in the high-risk MCC list",
    )

    model_config = {"json_schema_extra": {
        "example": {
            "transaction_id": "txn_abc123",
            "user_id": "usr_xyz789",
            "amount": 7500.00,
            "currency": "USD",
            "merchant_id": "merch_001",
            "merchant_name": "Global Wire Transfer",
            "hour_of_day": 2,
            "tx_count_1h": 8,
            "tx_count_24h": 25,
            "avg_amount_30d": 250.00,
            "amount_vs_avg_ratio": 30.0,
            "is_new_device": True,
            "geo_mismatch": True,
            "is_high_risk_mcc": True,
        }
    }}


class TriggeredRuleResponse(BaseModel):
    id: str
    description: str
    score_contribution: float
    field: str
    actual_value: Any


class EvaluationResponse(BaseModel):
    """
    Full evaluation result with explainability payload.
    Designed so downstream systems and analysts have everything they need.
    """

    event_id: str = Field(..., description="Unique ID for this evaluation event")
    transaction_id: str
    user_id: str
    verdict: str = Field(..., description="ALLOW | REVIEW | BLOCK")
    final_score: float = Field(..., description="Composite risk score 0–100")
    rule_score: float = Field(..., description="Score from rule engine 0–100")
    ml_score: float = Field(..., description="Score from ML model 0–100")
    rule_blend_weight: float = Field(..., description="Weight given to rule score in final blend")
    review_threshold: float
    block_threshold: float
    triggered_rules: list[TriggeredRuleResponse] = Field(
        ..., description="Rules that fired and their contributions"
    )
    model_version: int
    experiment_id: str | None = None
    experiment_variant: str | None = None
    ml_enabled: bool
    latency_ms: float = Field(..., description="End-to-end evaluation latency in milliseconds")
