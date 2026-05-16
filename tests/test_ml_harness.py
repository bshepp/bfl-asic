# tests/test_ml_harness.py
import math

import pytest

torch = pytest.importorskip("torch")

from bfl_asic.ml.harness import RunConfig, run_training, accuracy_ci


def test_accuracy_ci_brackets_point_estimate():
    lo, hi = accuracy_ci(correct=90, n=100)
    assert lo < 0.90 < hi
    assert 0.0 <= lo <= hi <= 1.0


def test_determinism_two_identical_runs_match():
    cfg = RunConfig(seed=3, rounds=3, n=512, epochs=2, model="linear_probe")
    r1 = run_training(cfg)
    r2 = run_training(cfg)
    assert math.isclose(r1.accuracy, r2.accuracy, rel_tol=0, abs_tol=0.0)


@pytest.mark.slow
def test_positive_control_low_rounds_is_learnable():
    # 2-round SHA-256 is trivially distinguishable from random; the harness's
    # deterministic fixed-per-epoch batch order converges slowly, so 12 epochs
    # are needed to clear the strong >0.80 bar (8 epochs only reaches ~0.77).
    cfg = RunConfig(seed=0, rounds=2, n=4096, epochs=12, model="tiny_cnn")
    res = run_training(cfg)
    assert res.accuracy > 0.80, f"got {res.accuracy}"


@pytest.mark.slow
def test_negative_control_random_vs_random_is_chance():
    cfg = RunConfig(
        seed=0, rounds=64, n=4096, epochs=8, model="tiny_cnn",
        negative_control=True,
    )
    res = run_training(cfg)
    lo, hi = res.accuracy_ci
    assert lo <= 0.5 <= hi, f"CI {res.accuracy_ci} should bracket 0.5"
