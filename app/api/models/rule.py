from pydantic import BaseModel


class RuleSummary(BaseModel):
    id: str
    description: str
    enabled: bool
    score_contribution: float
    owner: str


class RulesResponse(BaseModel):
    version: str
    rule_blend_weight: float
    thresholds: dict
    rules: list[RuleSummary]
    total_rules: int
    enabled_rules: int


class ReloadResponse(BaseModel):
    success: bool
    message: str
    rules_loaded: int
