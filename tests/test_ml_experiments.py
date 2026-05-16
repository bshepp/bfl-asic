# tests/test_ml_experiments.py
"""The bounded-null verdict must be gated on the controls (spec rigor)."""
from __future__ import annotations

import bfl_asic.ml.experiments as experiments
from bfl_asic.ml.harness import RunConfig, RunResult


def _fake_result(accuracy: float) -> RunResult:
    return RunResult(
        config=RunConfig(seed=0, rounds=64),
        accuracy=accuracy,
        advantage=2 * accuracy - 1,
        auc=float("nan"),
        accuracy_ci=(0.45, 0.55),  # brackets 0.5 -> negative_ok True
        min_detectable_advantage=0.06,
        n_val=100,
        train_curve=[1.0],
    )


def test_bounded_null_flags_instrument_failure_when_controls_fail(monkeypatch):
    # Force every run to ~chance: the positive control (rounds=2, must
    # exceed 0.70) FAILS -> a null must NOT be emitted.
    monkeypatch.setattr(
        experiments, "run_training", lambda cfg: _fake_result(0.50)
    )
    points, controls, bnull = experiments.run_full_structure(
        seed=0, n=64, epochs=1
    )
    assert controls["positive_ok"] is False
    assert bnull["controls_ok"] is False
    assert bnull["conclusion"].startswith("INSTRUMENT FAILURE")
    assert "no structure detected" not in bnull["conclusion"]


def test_bounded_null_emits_when_controls_pass(monkeypatch):
    # Positive control passes (rounds=2 -> 0.95 > 0.70); negative control
    # (~chance, CI brackets 0.5) fails as required; R=64 best ~0.5 -> a
    # valid "no structure" null is allowed.
    def fake(cfg):
        if getattr(cfg, "negative_control", False):
            return _fake_result(0.50)
        return _fake_result(0.95 if cfg.rounds == 2 else 0.50)

    monkeypatch.setattr(experiments, "run_training", fake)
    points, controls, bnull = experiments.run_full_structure(
        seed=0, n=64, epochs=1
    )
    assert controls["positive_ok"] is True
    assert controls["negative_ok"] is True
    assert bnull["controls_ok"] is True
    assert (
        bnull["conclusion"]
        == "no structure detected above the detection floor"
    )
