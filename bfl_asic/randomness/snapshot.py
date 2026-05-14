"""JSON-serializable snapshot of a randomness test battery run."""

from __future__ import annotations

import datetime
import json
from dataclasses import dataclass, field
from pathlib import Path

from bfl_asic.randomness.tests import TestResult


@dataclass
class RandomnessSnapshot:
    """Serializable result of a :class:`RandomnessBattery` run."""

    timestamp: str  # ISO 8601 UTC
    sample_count: int  # number of hashes consumed
    bit_count: int  # number of bits the tests saw
    engine_name: str
    duration_seconds: float
    alpha: float
    results: list[dict] = field(default_factory=list)

    @classmethod
    def from_results(
        cls,
        engine_name: str,
        sample_count: int,
        bit_count: int,
        duration_seconds: float,
        alpha: float,
        results: list[TestResult],
    ) -> "RandomnessSnapshot":
        return cls(
            timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            sample_count=sample_count,
            bit_count=bit_count,
            engine_name=engine_name,
            duration_seconds=duration_seconds,
            alpha=alpha,
            results=[
                {
                    "name": r.name,
                    "statistic": r.statistic,
                    "p_value": r.p_value,
                    "passed": r.passed,
                    "n": r.n,
                    "details": r.details,
                }
                for r in results
            ],
        )

    @property
    def pass_count(self) -> int:
        return sum(1 for r in self.results if r["passed"])

    @property
    def fail_count(self) -> int:
        return sum(1 for r in self.results if not r["passed"])

    def to_json(self) -> str:
        return json.dumps(self.__dict__, indent=2, default=_safe_default)

    def save(self, path: Path) -> None:
        Path(path).write_text(self.to_json())

    @classmethod
    def from_json(cls, text: str) -> "RandomnessSnapshot":
        return cls(**json.loads(text))

    @classmethod
    def load(cls, path: Path) -> "RandomnessSnapshot":
        return cls.from_json(Path(path).read_text())


def _safe_default(obj):
    # Catches numpy floats/ints that may leak through TestResult.details
    try:
        return float(obj)
    except (TypeError, ValueError):
        return str(obj)
