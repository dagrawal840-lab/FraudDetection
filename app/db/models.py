"""
SQLAlchemy ORM models.
All tables are append-only for regulatory audit-trail compliance.
"""

import json
from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class AuditLog(Base):
    """Immutable record of every fraud evaluation decision."""

    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)
    transaction_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    verdict: Mapped[str] = mapped_column(String(16), nullable=False)  # ALLOW / REVIEW / BLOCK
    rule_score: Mapped[float] = mapped_column(Float, nullable=False)
    ml_score: Mapped[float] = mapped_column(Float, nullable=False)
    final_score: Mapped[float] = mapped_column(Float, nullable=False)
    rule_blend_weight: Mapped[float] = mapped_column(Float, nullable=False)
    triggered_rules: Mapped[str] = mapped_column(Text, nullable=False)  # JSON list
    experiment_id: Mapped[str] = mapped_column(String(64), nullable=True)
    experiment_variant: Mapped[str] = mapped_column(String(32), nullable=True)
    model_version: Mapped[int] = mapped_column(Integer, nullable=False)
    latency_ms: Mapped[float] = mapped_column(Float, nullable=False)
    api_version: Mapped[str] = mapped_column(String(16), nullable=False, default="v1")
    request_payload: Mapped[str] = mapped_column(Text, nullable=True)  # JSON blob

    def triggered_rules_list(self) -> list:
        return json.loads(self.triggered_rules)


class ExperimentAssignment(Base):
    """Tracks which variant each user is assigned to per experiment."""

    __tablename__ = "experiment_assignments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    experiment_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    variant: Mapped[str] = mapped_column(String(32), nullable=False)
    assigned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class MetricsSnapshot(Base):
    """Periodic KPI rollups for the dashboard endpoint."""

    __tablename__ = "metrics_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    snapshot_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)
    window: Mapped[str] = mapped_column(String(8), nullable=False)  # 1h / 24h / 7d
    total_evaluated: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_blocked: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_reviewed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_allowed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    fraud_block_rate: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    avg_final_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    p99_latency_ms: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    rule_hit_rates: Mapped[str] = mapped_column(Text, nullable=True)  # JSON dict
    score_percentiles: Mapped[str] = mapped_column(Text, nullable=True)  # JSON dict
