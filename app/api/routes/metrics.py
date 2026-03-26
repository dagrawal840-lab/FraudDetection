"""
KPI metrics dashboard endpoint.
GET /v1/metrics/dashboard

Returns fraud detection KPIs across 1h, 24h, and 7d windows.
Designed for PM reporting cadences and operational monitoring.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.services.metrics_collector import get_dashboard_metrics

router = APIRouter(prefix="/v1/metrics", tags=["Metrics"])


@router.get("/dashboard")
async def get_metrics_dashboard(db: AsyncSession = Depends(get_db)) -> dict:
    """
    Returns the full KPI dashboard.

    Key metrics:
    - fraud_block_rate: fraction of transactions blocked (primary success metric)
    - review_rate: fraction sent to human review (proxy for false positive load)
    - rule_hit_rates: per-rule fire rate (identify dead or over-firing rules)
    - score_percentiles: p50/p90/p99 score distribution
    - p99_latency_ms: SLO compliance (target <200ms)
    - experiment metrics: per-variant comparison for active A/B tests
    """
    return await get_dashboard_metrics(db)
