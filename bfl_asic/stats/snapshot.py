"""JSON-serializable snapshot of all accumulator state.

Captures the output of :class:`~bfl_asic.stats.accumulators.CompositeAccumulator`
together with metadata (timestamp, engine name, sample count, duration, hash rate)
so that a complete statistical report can be saved, loaded, and compared across runs.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np


class _NumpyEncoder(json.JSONEncoder):
    """JSON encoder that handles numpy arrays and types."""

    def default(self, obj):
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        if isinstance(obj, (np.integer,)):
            return int(obj)
        if isinstance(obj, (np.floating,)):
            return float(obj)
        return super().default(obj)


@dataclass
class StatsSnapshot:
    """Serializable snapshot of all accumulator state plus metadata."""

    timestamp: str  # ISO 8601
    sample_count: int
    engine_name: str
    duration_seconds: float
    hash_rate: float  # hashes/sec
    bit_frequency: dict  # from BitFrequencyAccumulator.report()
    avalanche: dict  # from AvalancheAccumulator.report()
    correlation: dict  # from BitCorrelationAccumulator.report()
    near_collision: dict  # from NearCollisionAccumulator.report()
    byte_distribution: dict  # from ByteDistributionAccumulator.report()
    entropy: dict  # from EntropyAccumulator.report()

    def to_json(self) -> str:
        """Serialize to JSON string, handling numpy arrays."""
        return json.dumps(self.__dict__, cls=_NumpyEncoder, indent=2)

    def save(self, path: Path) -> None:
        """Save snapshot to a JSON file."""
        Path(path).write_text(self.to_json())

    @classmethod
    def from_json(cls, text: str) -> StatsSnapshot:
        """Deserialize from JSON string."""
        data = json.loads(text)
        return cls(**data)

    @classmethod
    def load(cls, path: Path) -> StatsSnapshot:
        """Load snapshot from a JSON file."""
        return cls.from_json(Path(path).read_text())

    @classmethod
    def from_pipeline(
        cls,
        engine_name: str,
        sample_count: int,
        duration_seconds: float,
        report: dict,
    ) -> StatsSnapshot:
        """Create from a CompositeAccumulator report + metadata."""
        import datetime

        return cls(
            timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            sample_count=sample_count,
            engine_name=engine_name,
            duration_seconds=duration_seconds,
            hash_rate=sample_count / max(duration_seconds, 0.001),
            bit_frequency=report.get("bit_frequency", {}),
            avalanche=report.get("avalanche", {}),
            correlation=report.get("correlation", {}),
            near_collision=report.get("near_collision", {}),
            byte_distribution=report.get("byte_distribution", {}),
            entropy=report.get("entropy", {}),
        )
