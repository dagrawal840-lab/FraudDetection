"""
A/B experiment assignment and result tagging.
Experiments are defined in config/ab_experiments.yaml.
Assignment is deterministic per (user_id, experiment_id) — no DB needed for assignment,
but assignments are persisted to the audit log for analysis.
"""

import hashlib
import os
from dataclasses import dataclass, field
from typing import Any

import yaml


@dataclass
class ExperimentVariant:
    name: str
    weight: float
    extra: dict[str, Any] = field(default_factory=dict)  # model_version, rule_blend_weight, etc.


@dataclass
class Experiment:
    id: str
    name: str
    description: str
    status: str  # draft / active / paused / graduated
    variants: dict[str, ExperimentVariant]
    primary_metric: str
    guardrail_metrics: list[str]


@dataclass
class ABTestingService:
    _experiments: dict[str, Experiment] = field(default_factory=dict)
    _config_path: str = "config/ab_experiments.yaml"

    def load(self, path: str | None = None) -> None:
        config_path = path or os.getenv("AB_EXPERIMENTS_PATH", self._config_path)
        with open(config_path) as f:
            raw = yaml.safe_load(f)
        self._experiments = {}
        for exp_cfg in raw.get("experiments", []):
            variants = {}
            for variant_id, v_cfg in exp_cfg.get("variants", {}).items():
                extra = {k: v for k, v in v_cfg.items() if k not in ("name", "weight")}
                variants[variant_id] = ExperimentVariant(
                    name=v_cfg["name"],
                    weight=v_cfg["weight"],
                    extra=extra,
                )
            self._experiments[exp_cfg["id"]] = Experiment(
                id=exp_cfg["id"],
                name=exp_cfg["name"],
                description=exp_cfg.get("description", ""),
                status=exp_cfg.get("status", "draft"),
                variants=variants,
                primary_metric=exp_cfg.get("primary_metric", ""),
                guardrail_metrics=exp_cfg.get("guardrail_metrics", []),
            )

    def reload(self) -> None:
        self.load()

    def assign_variant(self, user_id: str, experiment_id: str) -> tuple[str, dict[str, Any]]:
        """
        Returns (variant_id, variant_config) for the user.
        Returns ("control", {}) if the experiment doesn't exist or is not active.
        """
        exp = self._experiments.get(experiment_id)
        if exp is None or exp.status != "active":
            return "control", {}

        # Deterministic bucket: hash(user_id + experiment_id) → 0.0–1.0
        key = f"{user_id}:{experiment_id}"
        bucket = int(hashlib.md5(key.encode()).hexdigest(), 16) / (2**128)

        cumulative = 0.0
        for variant_id, variant in exp.variants.items():
            cumulative += variant.weight
            if bucket < cumulative:
                return variant_id, variant.extra

        # Fallback to last variant
        last_id = list(exp.variants.keys())[-1]
        return last_id, exp.variants[last_id].extra

    def get_active_experiments(self) -> list[dict[str, Any]]:
        return [
            {
                "id": exp.id,
                "name": exp.name,
                "status": exp.status,
                "variants": {
                    k: {"name": v.name, "weight": v.weight} for k, v in exp.variants.items()
                },
                "primary_metric": exp.primary_metric,
            }
            for exp in self._experiments.values()
            if exp.status == "active"
        ]

    def get_all_experiments(self) -> list[dict[str, Any]]:
        return [
            {
                "id": exp.id,
                "name": exp.name,
                "status": exp.status,
                "description": exp.description,
                "variants": {
                    k: {"name": v.name, "weight": v.weight} for k, v in exp.variants.items()
                },
                "primary_metric": exp.primary_metric,
                "guardrail_metrics": exp.guardrail_metrics,
            }
            for exp in self._experiments.values()
        ]


ab_testing = ABTestingService()
