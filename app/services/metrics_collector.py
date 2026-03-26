"""
KPI metrics collector.
Aggregates fraud detection metrics from the audit log for the dashboard.
Windows: 1h, 24h, 7d — aligned to PM reporting cadences.

Key metrics:
  - fraud_block_rate: primary success metric
  - review_queue_depth: operational health
  - rule_hit_rates: identify dead or over-firing rules
  - score_percentiles: distribution health check
  - p99_latency_ms: SLO compliance
"""

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

import numpy as np
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AuditLog

logger = logging.getLogger(__name__)

WINDOWS = {
    "1h": timedelta(hours=1),
    "24h": timedelta(hours=24),
    "7d": timedelta(days=7),
}


async def get_dashboard_metrics(db: AsyncSession) -> dict[str, Any]:
    """
    Returns the full KPI dashboard payload.
    Designed for PM reporting — metrics are named for business meaning.
    """
    now = datetime.now(timezone.utc)
    metrics: dict[str, Any] = {"generated_at": now.isoformat(), "windows": {}}

    for window_name, delta in WINDOWS.items():
        since = now - delta
        metrics["windows"][window_name] = await _compute_window_metrics(db, since, window_name)

    # Per-experiment metrics (across all windows)
    metrics["experiments"] = await _compute_experiment_metrics(db, now - timedelta(days=7))

    return metrics


async def _compute_window_metrics(
    db: AsyncSession, since: datetime, window: str
) -> dict[str, Any]:
    stmt = select(AuditLog).where(AuditLog.timestamp >= since)
    result = await db.execute(stmt)
    rows = result.scalars().all()

    if not rows:
        return {
            "total_evaluated": 0,
            "blocked": 0,
            "reviewed": 0,
            "allowed": 0,
            "fraud_block_rate": 0.0,
            "review_rate": 0.0,
            "avg_final_score": 0.0,
            "score_percentiles": {},
            "p99_latency_ms": 0.0,
            "rule_hit_rates": {},
        }

    total = len(rows)
    blocked = sum(1 for r in rows if r.verdict == "BLOCK")
    reviewed = sum(1 for r in rows if r.verdict == "REVIEW")
    allowed = sum(1 for r in rows if r.verdict == "ALLOW")

    scores = [r.final_score for r in rows]
    latencies = [r.latency_ms for r in rows]

    # Rule hit rates — identify dead rules or over-firing rules
    rule_hits: dict[str, int] = {}
    for row in rows:
        for rule in json.loads(row.triggered_rules):
            rule_id = rule["id"]
            rule_hits[rule_id] = rule_hits.get(rule_id, 0) + 1
    rule_hit_rates = {k: round(v / total, 4) for k, v in rule_hits.items()}

    return {
        "total_evaluated": total,
        "blocked": blocked,
        "reviewed": reviewed,
        "allowed": allowed,
        "fraud_block_rate": round(blocked / total, 4),
        "review_rate": round(reviewed / total, 4),
        "avg_final_score": round(float(np.mean(scores)), 2),
        "score_percentiles": {
            "p50": round(float(np.percentile(scores, 50)), 2),
            "p90": round(float(np.percentile(scores, 90)), 2),
            "p99": round(float(np.percentile(scores, 99)), 2),
        },
        "p99_latency_ms": round(float(np.percentile(latencies, 99)), 2),
        "rule_hit_rates": rule_hit_rates,
    }


async def _compute_experiment_metrics(
    db: AsyncSession, since: datetime
) -> dict[str, Any]:
    stmt = select(AuditLog).where(
        AuditLog.timestamp >= since,
        AuditLog.experiment_id.isnot(None),
    )
    result = await db.execute(stmt)
    rows = result.scalars().all()

    experiments: dict[str, dict[str, Any]] = {}
    for row in rows:
        exp_id = row.experiment_id or "unknown"
        variant = row.experiment_variant or "control"
        key = f"{exp_id}:{variant}"

        if key not in experiments:
            experiments[key] = {
                "experiment_id": exp_id,
                "variant": variant,
                "total": 0,
                "blocked": 0,
                "reviewed": 0,
                "scores": [],
                "latencies": [],
            }

        e = experiments[key]
        e["total"] += 1
        if row.verdict == "BLOCK":
            e["blocked"] += 1
        elif row.verdict == "REVIEW":
            e["reviewed"] += 1
        e["scores"].append(row.final_score)
        e["latencies"].append(row.latency_ms)

    # Summarize
    summary = {}
    for key, e in experiments.items():
        t = e["total"]
        summary[key] = {
            "experiment_id": e["experiment_id"],
            "variant": e["variant"],
            "total_evaluated": t,
            "fraud_block_rate": round(e["blocked"] / t, 4) if t else 0,
            "review_rate": round(e["reviewed"] / t, 4) if t else 0,
            "avg_score": round(float(np.mean(e["scores"])), 2) if e["scores"] else 0,
            "p99_latency_ms": round(float(np.percentile(e["latencies"], 99)), 2)
            if e["latencies"]
            else 0,
        }

    return summary
