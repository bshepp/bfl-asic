# bfl_asic/ml/harness.py
"""Deterministic training/evaluation with built-in controls.

A null ("no structure") conclusion is only trustworthy when the
positive control learns and the negative control fails -- the harness
computes both alongside every real run.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from scipy.stats import beta

from bfl_asic.ml.datasets import (
    Dataset,
    DistinguisherDatasetBuilder,
    FeatureExtractor,
    PerHashImage,
)
from bfl_asic.ml.models import build_model


@dataclass
class RunConfig:
    """Everything needed to reproduce one training run."""

    seed: int
    rounds: int
    n: int = 8192
    epochs: int = 10
    batch_size: int = 128
    lr: float = 1e-3
    model: str = "tiny_cnn"
    double: bool = False
    negative_control: bool = False  # random-vs-random; must fail
    feature: str = "per-hash"  # or "per-batch"
    feature_batch: int = 1024


@dataclass
class RunResult:
    """Metrics from one run."""

    config: RunConfig
    accuracy: float
    advantage: float
    auc: float
    accuracy_ci: tuple[float, float]
    min_detectable_advantage: float
    n_val: int
    train_curve: list[float] = field(default_factory=list)


def accuracy_ci(correct: int, n: int, conf: float = 0.95) -> tuple[float, float]:
    """Clopper-Pearson exact binomial CI for an accuracy estimate."""
    if n == 0:
        return (0.0, 1.0)
    alpha = 1.0 - conf
    lo = 0.0 if correct == 0 else beta.ppf(alpha / 2, correct, n - correct + 1)
    hi = 1.0 if correct == n else beta.ppf(
        1 - alpha / 2, correct + 1, n - correct
    )
    return (float(lo), float(hi))


def _make_extractor(cfg: RunConfig) -> FeatureExtractor:
    if cfg.feature == "per-batch":
        from bfl_asic.ml.datasets import PerBatchDeviationMap

        return PerBatchDeviationMap(batch=cfg.feature_batch)
    return PerHashImage()


def _negative_control_dataset(cfg: RunConfig) -> Dataset:
    """Both classes are independent random bytes -> unlearnable by design."""
    import torch

    rng = np.random.default_rng(cfg.seed)
    half = cfg.n // 2
    a = rng.integers(0, 256, size=(half, 32), dtype=np.uint8)
    b = rng.integers(0, 256, size=(half, 32), dtype=np.uint8)
    ex = _make_extractor(cfg)
    fa, fb = ex.extract(a), ex.extract(b)
    x = np.concatenate([fa, fb])[:, None, :, :]
    y = np.concatenate(
        [np.ones(len(fa)), np.zeros(len(fb))]
    ).astype(np.int64)
    perm = rng.permutation(len(y))
    x, y = x[perm], y[perm]
    nv = int(len(y) * 0.2)
    return Dataset(
        torch.from_numpy(x[nv:].copy()).float(),
        torch.from_numpy(y[nv:].copy()).long(),
        torch.from_numpy(x[:nv].copy()).float(),
        torch.from_numpy(y[:nv].copy()).long(),
        ex.name(),
    )


def run_training(cfg: RunConfig) -> RunResult:
    """Train + evaluate one configuration deterministically (CPU default)."""
    import torch

    torch.manual_seed(cfg.seed)
    np.random.seed(cfg.seed)

    if cfg.negative_control:
        data = _negative_control_dataset(cfg)
    else:
        data = DistinguisherDatasetBuilder(
            seed=cfg.seed,
            rounds=cfg.rounds,
            n=cfg.n,
            double=cfg.double,
            extractor=_make_extractor(cfg),
        ).build()

    model = build_model(cfg.model)
    opt = torch.optim.Adam(model.parameters(), lr=cfg.lr)
    loss_fn = torch.nn.CrossEntropyLoss()

    n = len(data.y_train)
    curve: list[float] = []
    for _ in range(cfg.epochs):
        model.train(True)
        gen = torch.Generator().manual_seed(cfg.seed)
        perm = torch.randperm(n, generator=gen)
        epoch_loss = 0.0
        for s in range(0, n, cfg.batch_size):
            idx = perm[s : s + cfg.batch_size]
            opt.zero_grad()
            out = model(data.x_train[idx])
            loss = loss_fn(out, data.y_train[idx])
            loss.backward()
            opt.step()
            epoch_loss += float(loss.detach())
        curve.append(epoch_loss)

    model.train(False)  # eval/inference mode (see hook note in plan header)
    with torch.no_grad():
        logits = model(data.x_val)
        pred = logits.argmax(dim=1)
        correct = int((pred == data.y_val).sum())
        n_val = len(data.y_val)
        acc = correct / n_val if n_val else 0.0
        probs = torch.softmax(logits, dim=1)[:, 1].numpy()
    try:
        from sklearn.metrics import roc_auc_score

        auc = float(roc_auc_score(data.y_val.numpy(), probs))
    except Exception:
        auc = float("nan")

    ci = accuracy_ci(correct, n_val)
    z = 1.959963984540054
    mda = 2.0 * z * float(np.sqrt(0.25 / max(n_val, 1)))
    return RunResult(
        config=cfg,
        accuracy=acc,
        advantage=2.0 * acc - 1.0,
        auc=auc,
        accuracy_ci=ci,
        min_detectable_advantage=mda,
        n_val=n_val,
        train_curve=curve,
    )
