from typing import Any

from pydantic import BaseModel


class ExperimentVariantInfo(BaseModel):
    name: str
    weight: float


class ExperimentInfo(BaseModel):
    id: str
    name: str
    status: str
    description: str
    variants: dict[str, ExperimentVariantInfo]
    primary_metric: str
    guardrail_metrics: list[str]


class ExperimentsResponse(BaseModel):
    experiments: list[ExperimentInfo]
    total: int


class VariantAssignment(BaseModel):
    user_id: str
    experiment_id: str
    variant: str
    variant_config: dict[str, Any]
