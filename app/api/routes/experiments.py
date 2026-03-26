"""
A/B experiment endpoints.
GET  /v1/experiments                           — list all experiments
GET  /v1/experiments/{id}/assign/{user_id}     — get variant assignment for user
"""

from fastapi import APIRouter, HTTPException

from app.api.models.experiment import (
    ExperimentInfo,
    ExperimentVariantInfo,
    ExperimentsResponse,
    VariantAssignment,
)
from app.core.ab_testing import ab_testing

router = APIRouter(prefix="/v1/experiments", tags=["Experiments"])


@router.get("", response_model=ExperimentsResponse)
async def list_experiments() -> ExperimentsResponse:
    """List all experiments with their current status and variant weights."""
    all_exps = ab_testing.get_all_experiments()
    experiments = [
        ExperimentInfo(
            id=e["id"],
            name=e["name"],
            status=e["status"],
            description=e["description"],
            variants={
                k: ExperimentVariantInfo(name=v["name"], weight=v["weight"])
                for k, v in e["variants"].items()
            },
            primary_metric=e["primary_metric"],
            guardrail_metrics=e["guardrail_metrics"],
        )
        for e in all_exps
    ]
    return ExperimentsResponse(experiments=experiments, total=len(experiments))


@router.get("/{experiment_id}/assign/{user_id}", response_model=VariantAssignment)
async def get_variant_assignment(experiment_id: str, user_id: str) -> VariantAssignment:
    """
    Get the deterministic variant assignment for a user in an experiment.
    Useful for debugging and pre-flight checks before a transaction.
    """
    variant, config = ab_testing.assign_variant(user_id, experiment_id)
    return VariantAssignment(
        user_id=user_id,
        experiment_id=experiment_id,
        variant=variant,
        variant_config=config,
    )
