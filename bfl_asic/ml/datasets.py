# bfl_asic/ml/datasets.py
"""Deterministic feature extraction and dataset construction.

Class A = round-reduced SHA-256 output; class B = true random bytes.
Everything is reproducible from a single integer seed.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

import numpy as np

from bfl_asic.ml.roundreduced import round_reduced_sha256


class FeatureExtractor(ABC):
    """Turn ``(M, 32)`` uint8 hash outputs into model-ready float images."""

    @abstractmethod
    def extract(self, outputs: np.ndarray) -> np.ndarray:
        """Return a float32 array of shape ``(K, 16, 16)``."""

    @abstractmethod
    def name(self) -> str:
        """Return a short, filesystem-safe identifier for this extractor."""
        ...


class PerHashImage(FeatureExtractor):
    """One hash -> one 16x16 binary image (256 output bits, MSB-first)."""

    def extract(self, outputs: np.ndarray) -> np.ndarray:
        outputs = np.asarray(outputs, dtype=np.uint8)
        bits = np.unpackbits(outputs, axis=1)  # (M, 256)
        return bits.reshape(-1, 16, 16).astype(np.float32)

    def name(self) -> str:
        return "per-hash-image"


class PerBatchDeviationMap(FeatureExtractor):
    """K hashes -> one 16x16 per-bit frequency-deviation map (freq - 0.5)."""

    def __init__(self, batch: int = 1024) -> None:
        if batch < 1:
            raise ValueError("batch must be >= 1")
        self._batch = batch

    def extract(self, outputs: np.ndarray) -> np.ndarray:
        outputs = np.asarray(outputs, dtype=np.uint8)
        m = (outputs.shape[0] // self._batch) * self._batch
        if m == 0:
            raise ValueError(
                f"need >= {self._batch} hashes, got {outputs.shape[0]}"
            )
        bits = np.unpackbits(outputs[:m], axis=1)  # (m, 256)
        groups = bits.reshape(-1, self._batch, 256).mean(axis=1)  # (K, 256)
        dev = (groups - 0.5).astype(np.float32)
        return dev.reshape(-1, 16, 16)

    def name(self) -> str:
        return f"per-batch-deviation-map-b{self._batch}"


@dataclass
class Dataset:
    """Torch tensors ready for the harness."""

    x_train: "object"  # torch.Tensor (N,1,16,16) float32
    y_train: "object"  # torch.Tensor (N,) int64
    x_val: "object"  # torch.Tensor (N,1,16,16) float32
    y_val: "object"  # torch.Tensor (N,) int64
    feature_name: str


def _random_inputs(rng: np.random.Generator, n: int) -> np.ndarray:
    """N independent uniform-random 32-byte inputs (a nonce-like stream)."""
    return rng.integers(0, 256, size=(n, 32), dtype=np.uint8)


class OrbitDatasetBuilder:
    """Seed -> binned iterated-orbit tail length, on a truncated SHA-256.

    Reuses bfl_asic.dynamics read-only.  Knob = truncation width
    ``trunc_bytes`` (state space == 256**trunc_bytes).
    """

    def __init__(
        self,
        seed: int,
        trunc_bytes: int = 2,
        n: int = 2048,
        *,
        n_bins: int = 4,
        max_steps: int = 200_000,
        val_fraction: float = 0.2,
    ) -> None:
        if not 1 <= trunc_bytes <= 4:
            raise ValueError("trunc_bytes must be 1..4 for reachable cycles")
        self.seed = seed
        self.trunc_bytes = trunc_bytes
        self.n = n
        self.n_bins = n_bins
        self.max_steps = max_steps
        self.val_fraction = val_fraction

    def _hash_fn(self):
        import hashlib

        t = self.trunc_bytes

        def fn(v: bytes) -> bytes:
            return hashlib.sha256(v).digest()[:t].ljust(32, b"\x00")

        return fn

    def build(self) -> Dataset:
        import torch

        from bfl_asic.dynamics import brent_detect

        rng = np.random.default_rng(self.seed)
        hash_fn = self._hash_fn()
        seeds = rng.integers(0, 256, size=(self.n, 32), dtype=np.uint8)

        tails: list[int] = []
        for i in range(self.n):
            info = brent_detect(
                bytes(seeds[i]), max_steps=self.max_steps, hash_fn=hash_fn
            )
            # -1 = no cycle within max_steps (rare for default widths
            # 1..3); it bins with the shortest tails -- acceptable noise.
            tails.append(info.tail_length if info is not None else -1)
        tarr = np.array(tails, dtype=np.float64)
        valid = tarr[tarr >= 0]
        edges = (
            np.quantile(valid, np.linspace(0, 1, self.n_bins + 1))
            if valid.size
            else np.linspace(0, 1, self.n_bins + 1)
        )
        edges[0], edges[-1] = -1.0, np.inf
        # Deduplicate inner edges: collapsed quantiles (low-variance
        # tail distributions) would feed non-monotone bins to
        # np.digitize (undefined behaviour). Fewer distinct edges just
        # yields fewer occupied classes, which CrossEntropy handles.
        inner = np.unique(edges[1:-1])
        y = np.clip(
            np.digitize(tarr, inner), 0, self.n_bins - 1
        ).astype(np.int64)

        bits = np.unpackbits(seeds, axis=1).reshape(-1, 16, 16)
        x = bits.astype(np.float32)[:, None, :, :]

        perm = rng.permutation(self.n)
        x, y = x[perm], y[perm]
        nv = int(self.n * self.val_fraction)
        return Dataset(
            torch.from_numpy(x[nv:].copy()).float(),
            torch.from_numpy(y[nv:].copy()).long(),
            torch.from_numpy(x[:nv].copy()).float(),
            torch.from_numpy(y[:nv].copy()).long(),
            f"orbit-tail(t={self.trunc_bytes},bins={self.n_bins})",
        )


class DistinguisherDatasetBuilder:
    """Build a balanced class-A (round-reduced SHA) vs class-B (random) set."""

    def __init__(
        self,
        seed: int,
        rounds: int,
        n: int = 8192,
        *,
        double: bool = False,
        extractor: FeatureExtractor | None = None,
        val_fraction: float = 0.2,
        class_b_random: bool = True,
    ) -> None:
        self.seed = seed
        self.rounds = rounds
        self.n = n
        self.double = double
        self.extractor = extractor or PerHashImage()
        self.val_fraction = val_fraction
        self.class_b_random = class_b_random

    def build(self) -> Dataset:
        import torch

        rng = np.random.default_rng(self.seed)
        half = self.n // 2

        a_in = _random_inputs(rng, half)
        a_out = round_reduced_sha256(
            a_in, rounds=self.rounds, double=self.double
        )

        if self.class_b_random:
            b_out = rng.integers(0, 256, size=(half, 32), dtype=np.uint8)
        else:
            b_in = _random_inputs(rng, half)
            b_out = round_reduced_sha256(b_in, rounds=64, double=self.double)

        feat_a = self.extractor.extract(a_out)
        feat_b = self.extractor.extract(b_out)
        x = np.concatenate([feat_a, feat_b], axis=0)[:, None, :, :]
        y = np.concatenate(
            [np.ones(len(feat_a)), np.zeros(len(feat_b))]
        ).astype(np.int64)

        perm = rng.permutation(len(y))
        x, y = x[perm], y[perm]

        n_val = int(len(y) * self.val_fraction)
        xt = torch.from_numpy(x[n_val:].copy()).float()
        yt = torch.from_numpy(y[n_val:].copy()).long()
        xv = torch.from_numpy(x[:n_val].copy()).float()
        yv = torch.from_numpy(y[:n_val].copy()).long()
        return Dataset(xt, yt, xv, yv, self.extractor.name())
