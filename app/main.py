"""
FastAPI application entrypoint.
Handles startup/shutdown lifecycle: DB init, model loading, config loading.
"""

import logging
import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import experiments, metrics, rules, transactions
from app.core.ab_testing import ab_testing
from app.core.feature_flags import feature_flags
from app.core.rule_engine import rule_engine
from app.db.database import create_tables
from app.services.model_registry import model_registry

logging.basicConfig(
    level=getattr(logging, os.getenv("LOG_LEVEL", "INFO")),
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Startup and shutdown lifecycle events."""
    logger.info("Starting up fraud detection service...")

    # Initialize database tables
    await create_tables()
    logger.info("Database tables initialized")

    # Load configs
    rule_engine.load()
    logger.info(f"Rules loaded: {len(rule_engine._rules)} rules")

    feature_flags.load()
    logger.info(f"Feature flags loaded: {len(feature_flags._flags)} flags")

    ab_testing.load()
    logger.info(f"A/B experiments loaded")

    # Load ML models
    model_registry.load_all()
    if model_registry._models:
        logger.info(f"ML models loaded: versions {list(model_registry._models.keys())}")
    else:
        logger.warning("No ML models found — ML scoring will be disabled")
        # Disable ML flag to prevent scoring errors
        if "ml_scoring_enabled" in feature_flags._flags:
            feature_flags._flags["ml_scoring_enabled"].enabled = False

    logger.info("Fraud detection service ready")
    yield

    logger.info("Shutting down fraud detection service...")


app = FastAPI(
    title="Fraud Detection API",
    description="""
## Fraud Detection API

A production-grade fraud detection service combining rule-based scoring and ML anomaly detection.

### Key Features
- **Hybrid scoring**: Rule engine (tunable via YAML) + Isolation Forest ML model
- **Full explainability**: Every verdict includes which rules fired and why
- **A/B testing**: Safe model rollout with deterministic variant assignment
- **Feature flags**: Control ML scoring, rollout percentages, and pipeline behavior
- **Audit logging**: Immutable record of every decision for regulatory compliance
- **KPI dashboard**: Real-time metrics across 1h, 24h, 7d windows

### Verdict Thresholds (configurable in config/rules.yaml)
- **ALLOW**: score < 40
- **REVIEW**: 40 ≤ score < 70
- **BLOCK**: score ≥ 70
    """,
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(transactions.router)
app.include_router(rules.router)
app.include_router(experiments.router)
app.include_router(metrics.router)


@app.get("/health", tags=["Health"])
async def health_check() -> JSONResponse:
    """Health check endpoint for load balancers and monitoring."""
    return JSONResponse({
        "status": "healthy",
        "models_loaded": list(model_registry._models.keys()),
        "rules_enabled": sum(1 for r in rule_engine._rules if r.get("enabled")),
        "flags_active": sum(1 for f in feature_flags._flags.values() if f.enabled),
    })


@app.get("/", tags=["Health"])
async def root() -> JSONResponse:
    return JSONResponse({
        "service": "Fraud Detection API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health",
    })
