# bfl_asic/ml/snapshot.py
"""JSON-serializable snapshot of an ML learnability run.

Mirrors bfl_asic/randomness/snapshot.py conventions.
"""
from __future__ import annotations

import datetime
import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class MLSnapshot:
    timestamp: str
    experiment: str
    feature: str
    model: str
    points: list[dict] = field(default_factory=list)
    controls: dict = field(default_factory=dict)
    bounded_null: dict = field(default_factory=dict)

    @classmethod
    def from_runs(
        cls,
        experiment: str,
        feature: str,
        model: str,
        points: list[dict],
        controls: dict,
        bounded_null: dict | None = None,
    ) -> "MLSnapshot":
        return cls(
            timestamp=datetime.datetime.now(
                datetime.timezone.utc
            ).isoformat(),
            experiment=experiment,
            feature=feature,
            model=model,
            points=points,
            controls=controls,
            bounded_null=bounded_null or {},
        )

    def to_json(self) -> str:
        return json.dumps(self.__dict__, indent=2, default=_safe_default)

    def save(self, path: Path) -> None:
        Path(path).write_text(self.to_json())

    @classmethod
    def from_json(cls, text: str) -> "MLSnapshot":
        return cls(**json.loads(text))

    @classmethod
    def load(cls, path: Path) -> "MLSnapshot":
        return cls.from_json(Path(path).read_text())


def _safe_default(obj):
    try:
        return float(obj)
    except (TypeError, ValueError):
        return str(obj)
