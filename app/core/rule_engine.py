"""
Rule-based fraud scoring engine.
Rules are loaded from config/rules.yaml — no code change required to tune thresholds.
Risk analysts can edit the YAML and call PUT /rules/reload to apply live.
"""

import os
from dataclasses import dataclass, field
from typing import Any

import yaml


@dataclass
class TriggeredRule:
    id: str
    description: str
    score_contribution: float
    field: str
    operator: str
    threshold: Any
    actual_value: Any


@dataclass
class RuleResult:
    score: float  # 0–100
    triggered_rules: list[TriggeredRule]
    evaluated_rules: int
    enabled_rules: int


@dataclass
class RuleEngine:
    _rules: list[dict] = field(default_factory=list)
    _config: dict = field(default_factory=dict)
    _config_path: str = "config/rules.yaml"

    def load(self, path: str | None = None) -> None:
        config_path = path or os.getenv("RULES_CONFIG_PATH", self._config_path)
        with open(config_path) as f:
            self._config = yaml.safe_load(f)
        self._rules = self._config.get("rules", [])

    def reload(self) -> None:
        self.load()

    @property
    def thresholds(self) -> dict:
        return self._config.get("thresholds", {"review": 40, "block": 70})

    @property
    def rule_blend_weight(self) -> float:
        return float(self._config.get("rule_blend_weight", 0.6))

    def score(self, features: dict[str, Any]) -> RuleResult:
        """
        Evaluate all enabled rules against transaction features.
        Returns a RuleResult with a 0–100 score and list of triggered rules.
        Score is capped at 100 regardless of how many rules fire.
        """
        triggered: list[TriggeredRule] = []
        enabled_count = 0
        raw_score = 0.0

        for rule in self._rules:
            if not rule.get("enabled", False):
                continue
            enabled_count += 1

            field_name = rule["field"]
            operator = rule["operator"]
            threshold = rule["threshold"]
            actual = features.get(field_name)

            if actual is None:
                continue

            fired = self._evaluate(operator, actual, threshold)
            if fired:
                contribution = float(rule.get("score_contribution", 0))
                raw_score += contribution
                triggered.append(
                    TriggeredRule(
                        id=rule["id"],
                        description=rule.get("description", ""),
                        score_contribution=contribution,
                        field=field_name,
                        operator=operator,
                        threshold=threshold,
                        actual_value=actual,
                    )
                )

        return RuleResult(
            score=min(raw_score, 100.0),
            triggered_rules=triggered,
            evaluated_rules=len(triggered),
            enabled_rules=enabled_count,
        )

    @staticmethod
    def _evaluate(operator: str, actual: Any, threshold: Any) -> bool:
        try:
            if operator == "gt":
                return float(actual) > float(threshold)
            elif operator == "lt":
                return float(actual) < float(threshold)
            elif operator == "gte":
                return float(actual) >= float(threshold)
            elif operator == "lte":
                return float(actual) <= float(threshold)
            elif operator == "eq":
                return actual == threshold
            elif operator == "neq":
                return actual != threshold
            elif operator == "between":
                lo, hi = threshold[0], threshold[1]
                return float(lo) <= float(actual) <= float(hi)
            elif operator == "in":
                return actual in threshold
            else:
                return False
        except (TypeError, ValueError):
            return False

    def get_rules_summary(self) -> list[dict]:
        return [
            {
                "id": r["id"],
                "description": r.get("description", ""),
                "enabled": r.get("enabled", False),
                "score_contribution": r.get("score_contribution", 0),
                "owner": r.get("owner", ""),
            }
            for r in self._rules
        ]


rule_engine = RuleEngine()
