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
    controls_ok = bool(
        controls.get("positive_ok") and controls.get("negative_ok")
    )
    if not controls_ok:
        # Spec rigor: a "no structure" null is only trustworthy when the
        # positive control learned and the negative control failed. If
        # either control did not pass, the instrument is broken and no
        # null (or structure) claim is valid.
        conclusion = (
            "INSTRUMENT FAILURE -- controls did not pass "
            f"(positive_ok={controls.get('positive_ok')}, "
            f"negative_ok={controls.get('negative_ok')}); "
            "null result is NOT valid"
        )
    elif best["accuracy_ci"][0] <= 0.5:
        conclusion = "no structure detected above the detection floor"
    else:
        conclusion = "POSSIBLE structure -- investigate"
    bounded_null = {
        "best_model": best["model"],
        "accuracy": best["accuracy"],
        "accuracy_ci": best["accuracy_ci"],
        "advantage": best["advantage"],
        "min_detectable_advantage": best["min_detectable_advantage"],
        "controls_ok": controls_ok,
        "conclusion": conclusion,
    }
    return points, controls, bounded_null


def run_dynamics_sweep(
    *, seed: int = 0, n: int = 2048, epochs: int = 10,
    trunc_widths: list[int] | None = None, n_bins: int = 4,
) -> tuple[list[dict], dict]:
    """#3: predict binned orbit tail length from the seed, vs truncation.

    Validated to the project's standard: real Clopper-Pearson CI + a
    CI-resolution floor on every point, positive_ok gated on the CI
    lower bound exceeding chance, and a permuted-label negative control
    on the lead width (shuffled labels must NOT beat chance, else the
    apparent signal is a dataset/setup artifact, not orbit structure).
    """
    import numpy as np
    import torch

    from bfl_asic.ml.datasets import OrbitDatasetBuilder
    from bfl_asic.ml.harness import accuracy_ci
    from bfl_asic.ml.models import build_model

    _Z = 1.959963984540054  # 97.5th pct of N(0,1); matches the harness

    def _fit_and_score(x_tr, y_tr, x_val, y_val) -> tuple[int, int]:
        # Same seed -> same init for the real and permuted-label models,
        # so the only difference between them is the label mapping.
        torch.manual_seed(seed)
        model = build_model("tiny_cnn", num_classes=n_bins)
        opt = torch.optim.Adam(model.parameters(), lr=1e-3)
        loss_fn = torch.nn.CrossEntropyLoss()
        ntr = len(y_tr)
        for _ in range(epochs):
            model.train(True)
            for s in range(0, ntr, 128):
                opt.zero_grad()
                loss = loss_fn(model(x_tr[s : s + 128]), y_tr[s : s + 128])
                loss.backward()
                opt.step()
        model.train(False)  # inference mode (see hook note)
        with torch.no_grad():
            pred = model(x_val).argmax(1)
            correct = int((pred == y_val).sum())
        return correct, int(len(y_val))

    widths = trunc_widths or [1, 2, 3]
    chance = 1.0 / n_bins
    points: list[dict] = []
    lead_data = None
    for i, t in enumerate(widths):
        data = OrbitDatasetBuilder(
            seed=seed, trunc_bytes=t, n=n, n_bins=n_bins
        ).build()
        if i == 0:
            lead_data = data
        correct, n_val = _fit_and_score(
            data.x_train, data.y_train, data.x_val, data.y_val
        )
        acc = correct / n_val if n_val else 0.0
        ci = list(accuracy_ci(correct, n_val))
        # CI-resolution floor: smallest above-chance gain whose 95%
        # accuracy CI excludes chance at this n. NOT a power-based MDE
        # -- same honest convention as the distinguisher path.
        mda = _Z * float(np.sqrt(chance * (1.0 - chance) / max(n_val, 1)))
        points.append(
            {
                "rounds": t,  # generic knob axis (truncation bytes here)
                "accuracy": acc,
                # For dynamics "advantage" is gain over chance
                # (acc - 1/n_bins), NOT the harness's 2*acc-1.
                "advantage": acc - chance,
                "auc": None,  # AUC undefined for multi-class dynamics
                "accuracy_ci": ci,
                "min_detectable_advantage": mda,
                "chance": chance,
            }
        )

    # Permuted-label negative control on the LEAD width: shuffle the
    # training labels (break X->y), train the same model, evaluate on
    # the real val set. If a shuffled-label model still beats chance,
    # the apparent orbit signal is a dataset/setup artifact, not orbit
    # structure -- the dynamics analog of the random-vs-random control.
    g = torch.Generator().manual_seed(seed + 1)
    perm = torch.randperm(len(lead_data.y_train), generator=g)
    nc_correct, nc_n = _fit_and_score(
        lead_data.x_train, lead_data.y_train[perm],
        lead_data.x_val, lead_data.y_val,
    )
    nc_acc = nc_correct / nc_n if nc_n else 0.0
    nc_ci = list(accuracy_ci(nc_correct, nc_n))

    lead = points[0]
    controls = {
        "positive_accuracy": lead["accuracy"],
        "positive_ci": lead["accuracy_ci"],
        # Significance test: CI lower bound must exceed chance (not a
        # bare point estimate / arbitrary margin).
        "positive_ok": lead["accuracy_ci"][0] > lead["chance"],
        "permuted_label_accuracy": nc_acc,
        "permuted_label_ci": nc_ci,
        # Trustworthy only if the shuffled-label model does NOT beat
        # chance (its CI lower bound stays at/below chance).
        "negative_ok": nc_ci[0] <= chance,
        "note": (
            "knob=truncation width (bytes); chance=1/n_bins; "
            "advantage=accuracy-chance; positive_ok = CI lower bound > "
            "chance; negative_ok = permuted-label model CI lower bound "
            "<= chance (no setup/dataset artifact)."
        ),
    }
    return points, controls
