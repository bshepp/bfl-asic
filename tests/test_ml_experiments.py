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


def test_dynamics_sweep_is_validated_to_project_standard():
    # The dynamics path must carry real Clopper-Pearson CI + a
    # CI-resolution floor, gate positive_ok on the CI lower bound, and
    # run a permuted-label negative control (no hardcoded negative_ok).
    pts, ctl = experiments.run_dynamics_sweep(
        seed=0, n=400, epochs=1, trunc_widths=[1, 2], n_bins=4
    )
    p = pts[0]
    assert p["accuracy_ci"] != [0.0, 1.0]            # real CI, not stub
    assert 0.0 <= p["accuracy_ci"][0] <= p["accuracy_ci"][1] <= 1.0
    assert p["min_detectable_advantage"] > 0.0       # real floor, not 0.0
    assert "permuted_label_accuracy" in ctl
    assert "permuted_label_ci" in ctl
    assert isinstance(ctl["positive_ok"], bool)
    assert isinstance(ctl["negative_ok"], bool)
    # positive_ok is the CI-lower-bound significance test, not bare mean
    assert ctl["positive_ok"] == (p["accuracy_ci"][0] > p["chance"])
    # negative_ok is derived from the permuted-label control
    assert ctl["negative_ok"] == (ctl["permuted_label_ci"][0] <= p["chance"])
