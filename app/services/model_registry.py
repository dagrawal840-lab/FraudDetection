"""
Model registry — manages versioned ML model artifacts.
Models are stored as ml/artifacts/model_v{N}.pkl with a manifest.json.
This allows zero-downtime model swaps and A/B testing of model versions.
"""

import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import joblib

logger = logging.getLogger(__name__)


@dataclass
class ModelMetadata:
    version: int
    trained_at: str
    features: list[str]
    hyperparameters: dict[str, Any]
    training_samples: int
    contamination: float


@dataclass
class ModelRegistry:
    _models: dict[int, Any] = field(default_factory=dict)
    _metadata: dict[int, ModelMetadata] = field(default_factory=dict)
    _artifacts_dir: str = "ml/artifacts"
    default_version: int = 1

    def load_all(self, artifacts_dir: str | None = None) -> None:
        """Load all model versions found in the artifacts directory."""
        dir_path = Path(artifacts_dir or os.getenv("ML_ARTIFACTS_DIR", self._artifacts_dir))
        if not dir_path.exists():
            logger.warning(f"Artifacts directory {dir_path} does not exist — no models loaded")
            return

        manifest_path = dir_path / "manifest.json"
        metadata_by_version: dict[int, dict] = {}
        if manifest_path.exists():
            with open(manifest_path) as f:
                manifest = json.load(f)
            for entry in manifest.get("models", []):
                metadata_by_version[entry["version"]] = entry

        for model_file in sorted(dir_path.glob("model_v*.pkl")):
            try:
                version = int(model_file.stem.replace("model_v", ""))
                model = joblib.load(model_file)
                self._models[version] = model
                meta_raw = metadata_by_version.get(version, {})
                self._metadata[version] = ModelMetadata(
                    version=version,
                    trained_at=meta_raw.get("trained_at", "unknown"),
                    features=meta_raw.get("features", []),
                    hyperparameters=meta_raw.get("hyperparameters", {}),
                    training_samples=meta_raw.get("training_samples", 0),
                    contamination=meta_raw.get("contamination", 0.05),
                )
                logger.info(f"Loaded model v{version} from {model_file}")
            except Exception as e:
                logger.error(f"Failed to load {model_file}: {e}")

        if self._models:
            self.default_version = max(self._models.keys())
            logger.info(f"Default model version set to v{self.default_version}")

    def get(self, version: int | None = None) -> Any | None:
        v = version if version is not None else self.default_version
        model = self._models.get(v)
        if model is None and self._models:
            logger.warning(f"Model v{v} not found, falling back to v{self.default_version}")
            return self._models.get(self.default_version)
        return model

    def list_versions(self) -> list[dict[str, Any]]:
        return [
            {
                "version": v,
                "trained_at": m.trained_at,
                "training_samples": m.training_samples,
                "contamination": m.contamination,
                "features": m.features,
                "is_default": v == self.default_version,
            }
            for v, m in self._metadata.items()
        ]


model_registry = ModelRegistry()
