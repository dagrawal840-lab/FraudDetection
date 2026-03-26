"""
Feature flag evaluator.
Deterministic hash-based assignment — no database call needed.
Flags are loaded from config/feature_flags.yaml and cached in memory.
Call reload() after editing the YAML to apply changes without restart.
"""

import hashlib
import os
from dataclasses import dataclass, field
from typing import Any

import yaml


@dataclass
class FlagDefinition:
    name: str
    description: str
    enabled: bool
    rollout_percentage: int  # 0–100
    owner: str
    rationale: str = ""


@dataclass
class FeatureFlagService:
    _flags: dict[str, FlagDefinition] = field(default_factory=dict)
    _config_path: str = "config/feature_flags.yaml"

    def load(self, path: str | None = None) -> None:
        config_path = path or os.getenv("FEATURE_FLAGS_PATH", self._config_path)
        with open(config_path) as f:
            raw = yaml.safe_load(f)
        self._flags = {}
        for name, cfg in raw.get("flags", {}).items():
            self._flags[name] = FlagDefinition(
                name=name,
                description=cfg.get("description", ""),
                enabled=cfg.get("enabled", False),
                rollout_percentage=cfg.get("rollout_percentage", 0),
                owner=cfg.get("owner", ""),
                rationale=cfg.get("rationale", ""),
            )

    def reload(self) -> None:
        self.load()

    def is_enabled(self, flag_name: str, user_id: str = "") -> bool:
        """
        Returns True if the flag is enabled for the given user_id.
        Uses a deterministic hash so the same user always gets the same result.
        """
        flag = self._flags.get(flag_name)
        if flag is None or not flag.enabled:
            return False
        if flag.rollout_percentage >= 100:
            return True
        if flag.rollout_percentage <= 0:
            return False
        # Deterministic bucket assignment: hash(user_id + flag_name) % 100
        key = f"{user_id}:{flag_name}"
        bucket = int(hashlib.md5(key.encode()).hexdigest(), 16) % 100
        return bucket < flag.rollout_percentage

    def get_all(self) -> dict[str, dict[str, Any]]:
        return {
            name: {
                "enabled": f.enabled,
                "rollout_percentage": f.rollout_percentage,
                "description": f.description,
                "owner": f.owner,
            }
            for name, f in self._flags.items()
        }


# Module-level singleton — loaded once at startup, reloaded on demand
feature_flags = FeatureFlagService()
