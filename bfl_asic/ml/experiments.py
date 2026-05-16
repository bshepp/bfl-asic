# bfl_asic/ml/experiments.py
"""The four named experiments as configs over the one harness.

* sweep                -- #1 round-reduced learnability sweep (the spine)
* indistinguishability -- #2 full SHA-256 vs random (sweep's R=64 point)
* full_structure       -- #4 widened bounded-null search at R=64
* dynamics             -- #3 iterated-hash orbit learnability (Task 8)
"""
from __future__ import annotations

from bfl_asic.ml.harness import RunConfig, RunResult, run_training

DEFAULT_ROUNDS = [1, 2, 3, 4, 6, 8, 12, 16, 24, 32, 48, 64]


def _point(rounds: int, res: RunResult) -> dict:
    return {
        "rounds": rounds,
        "accuracy": res.accuracy,
        "advantage": res.advantage,
        "auc": res.auc,
        "accuracy_ci": list(res.accuracy_ci),
        "min_detectable_advantage": res.min_detectable_advantage,
    }


def run_sweep(
    rounds: list[int],
    *,
    seed: int = 0,
    n: int = 8192,
    epochs: int = 10,
    model: str = "tiny_cnn",
    feature: str = "per-hash",
) -> tuple[list[dict], dict]:
    """Train one model per round count; return (points, controls)."""
    points: list[dict] = []
    results_by_round: dict[int, RunResult] = {}
    for r in rounds:
        res = run_training(
            RunConfig(seed=seed, rounds=r, n=n, epochs=epochs,
                      model=model, feature=feature)
        )
        results_by_round[r] = res
        points.append(_point(r, res))

    # Positive control: a low-round model must be learnable. The harness
    # is deterministic, so if rounds==2 was already swept we reuse that
    # exact result instead of re-training it (saves a full training run).
    if 2 in results_by_round:
        pos = results_by_round[2]
    else:
        pos = run_training(
            RunConfig(seed=seed, rounds=2, n=n, epochs=epochs, model=model,
                      feature=feature)
        )
    neg = run_training(
        RunConfig(seed=seed, rounds=64, n=n, epochs=epochs, model=model,
                  feature=feature, negative_control=True)
    )
    controls = {
        "positive_accuracy": pos.accuracy,
        "positive_ok": pos.accuracy > 0.70,
        "negative_ci": list(neg.accuracy_ci),
        "negative_ok": neg.accuracy_ci[0] <= 0.5 <= neg.accuracy_ci[1],
    }
    return points, controls


def run_full_structure(
    *, seed: int = 0, n: int = 8192, epochs: int = 10
) -> tuple[list[dict], dict, dict]:
    """#4: R=64 with both models; report a bounded null.

    NOTE: min_detectable_advantage is a CI-resolution floor (the 95% CI
    on accuracy still includes chance below it), NOT a power-based
    minimum detectable effect. The conclusion text is phrased as a
    detection *floor* accordingly -- do not claim power-based
    detectability here.
    """
    points: list[dict] = []
    for model in ("tiny_cnn", "linear_probe"):
        res = run_training(
            RunConfig(seed=seed, rounds=64, n=n, epochs=epochs, model=model)
        )
        p = _point(64, res)
        p["model"] = model
        points.append(p)
    _, controls = run_sweep([2], seed=seed, n=n, epochs=epochs)
    best = max(points, key=lambda p: p["accuracy"])
    bounded_null = {
        "best_model": best["model"],
        "accuracy": best["accuracy"],
        "accuracy_ci": best["accuracy_ci"],
        "advantage": best["advantage"],
        "min_detectable_advantage": best["min_detectable_advantage"],
        "conclusion": (
            "no structure detected above the detection floor"
            if best["accuracy_ci"][0] <= 0.5
            else "POSSIBLE structure -- investigate"
        ),
    }
    return points, controls, bounded_null
