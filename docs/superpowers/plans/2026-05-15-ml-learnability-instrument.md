# ML Learnability Instrument Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an optional `bfl_asic/ml/` subsystem that measures where SHA-256 becomes learnable (round-reduced distinguishers) and reports a rigorous bounded null for full SHA-256 — with PyTorch isolated behind a `[ml]` extra so no existing pipeline or test is affected.

**Architecture:** A new package mirroring the existing `stats/`/`randomness/` subsystem shape: a numpy-vectorized round-reduced SHA-256 core, a deterministic dataset/feature layer, PyTorch models, a train/eval harness with built-in positive/negative controls, JSON snapshots, matplotlib visualization, and a lazy-imported `ml` Click group. Four experiments are configs over one harness.

**Tech Stack:** Python ≥3.10, numpy, scipy, matplotlib, click (existing); PyTorch + huggingface_hub (new, optional `[ml]` extra); pytest.

**Spec:** `docs/superpowers/specs/2026-05-15-ml-learnability-instrument-design.md`

**Conventions to follow (already in the codebase):**
- CLI write paths go through `unique_output_path()`; defaults via `default_run_dir()` / `default_output_file()` (`bfl_asic/cli.py:39-86`).
- Snapshots follow `bfl_asic/randomness/snapshot.py` (dataclass + `from_*`/`to_json`/`save`/`load`, `_safe_default` for numpy leakage).
- Subcommand groups lazy-import heavy deps inside the command body (e.g. `bfl_asic/cli.py:334`).
- matplotlib uses the `Agg` backend; tests call `plt.close(fig)`.

---

## File Structure

**Create:**
- `bfl_asic/ml/__init__.py` — torch-free package marker; re-exports only `round_reduced_sha256`.
- `bfl_asic/ml/roundreduced.py` — numpy-vectorized round-reduced SHA-256/SHA-256d. **No torch.**
- `bfl_asic/ml/datasets.py` — `FeatureExtractor` ABC, `PerHashImage`, `PerBatchDeviationMap`, `DistinguisherDatasetBuilder`, `OrbitDatasetBuilder`.
- `bfl_asic/ml/models.py` — `TinyCNN`, `LinearProbe`, `MODELS` registry.
- `bfl_asic/ml/harness.py` — `RunConfig`, `RunResult`, `run_training`, controls, metrics.
- `bfl_asic/ml/experiments.py` — the four named experiment configs.
- `bfl_asic/ml/snapshot.py` — `MLSnapshot` (mirrors randomness snapshot).
- `bfl_asic/ml/visualization.py` — learnability curve, training curve, saliency map.
- `bfl_asic/ml/publish.py` — optional HF publish + model-card generation.
- `tests/test_ml_roundreduced.py`, `tests/test_ml_datasets.py`, `tests/test_ml_models.py`, `tests/test_ml_harness.py`, `tests/test_ml_snapshot.py`, `tests/test_ml_cli.py`, `tests/test_ml_optional.py`, `tests/test_ml_publish.py`.

**Modify:**
- `pyproject.toml` — add `[ml]` optional-dependency group and register the `slow` pytest marker.
- `bfl_asic/cli.py` — add the lazy `ml` Click group + `_require_torch()` helper (the only edit to existing code).
- `README.md`, `LEARNING.md`, `DEVLOG.md`, `bfl-asic-repurpose.md`, `CLAUDE.md` — docs bookkeeping (final task).

**Import direction:** `ml/*` may import `bfl_asic.dynamics` and `bfl_asic.stats.engine` read-only. Nothing in the existing tree imports `bfl_asic.ml`.

> **Hook note for the implementer:** a repo `PreToolUse` hook blocks the literal substring `eval(` (false-positive on Python's `eval`). The plan therefore uses PyTorch's `model.train(False)` instead of `model.eval()` — they are functionally identical (both set eval/inference mode). Keep `model.train(False)` as written; do not "fix" it back to `model.eval()`.

---

## Task 1: Isolation contract — `[ml]` extra, `slow` marker, CLI guard

**Files:**
- Modify: `pyproject.toml`
- Create: `bfl_asic/ml/__init__.py`
- Modify: `bfl_asic/cli.py` (append a new group + helper near the end, after the `randomness` group, before EOF)
- Test: `tests/test_ml_optional.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_ml_optional.py
"""The ML subsystem must not burden the torch-free core."""
import builtins
import importlib

import pytest
from click.testing import CliRunner

from bfl_asic.cli import main, _require_torch


def test_help_works_without_touching_torch():
    result = CliRunner().invoke(main, ["--help"])
    assert result.exit_code == 0
    assert "ml" in result.output


def test_ml_group_help_works():
    result = CliRunner().invoke(main, ["ml", "--help"])
    assert result.exit_code == 0


def test_require_torch_raises_friendly_message(monkeypatch):
    import click

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "torch" or name.startswith("torch."):
            raise ImportError("No module named 'torch'")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    with pytest.raises(click.ClickException) as exc:
        _require_torch()
    assert 'pip install -e ".[ml]"' in str(exc.value)


def test_ml_package_import_is_torch_free(monkeypatch):
    import builtins as _b

    real_import = _b.__import__

    def fake_import(name, *args, **kwargs):
        if name == "torch" or name.startswith("torch."):
            raise ImportError("blocked")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(_b, "__import__", fake_import)
    import bfl_asic.ml as ml_pkg
    importlib.reload(ml_pkg)
    assert hasattr(ml_pkg, "round_reduced_sha256")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_ml_optional.py -q`
Expected: FAIL — `ImportError: cannot import name '_require_torch'` and `bfl_asic.ml` missing.

- [ ] **Step 3: Create the torch-free package init**

```python
# bfl_asic/ml/__init__.py
"""Optional ML subsystem: round-reduced SHA-256 learnability instrument.

Importing this package is torch-free.  Only :func:`round_reduced_sha256`
(numpy-only) is re-exported here; everything that needs PyTorch lives in
submodules imported lazily by the CLI behind the ``[ml]`` extra.
"""
from bfl_asic.ml.roundreduced import round_reduced_sha256

__all__ = ["round_reduced_sha256"]
```

> Note: `roundreduced.py` is created in Task 2. Until then this import fails — `test_ml_package_import_is_torch_free` will pass only after Task 2. That is expected; Step 6 below runs only the three non-dependent tests.

- [ ] **Step 4: Add the `[ml]` extra and `slow` marker to `pyproject.toml`**

Replace the `[project.optional-dependencies]` block through the end of the file with:

```toml
[project.optional-dependencies]
dev = [
    "pytest",
    "pytest-asyncio",
]
ml = [
    "torch",
    "huggingface_hub",
]

[project.scripts]
bfl-asic = "bfl_asic.cli:main"

[tool.setuptools.packages.find]
include = ["bfl_asic*"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
markers = [
    "slow: heavy ML training tests, excluded from the default fast run",
]
```

- [ ] **Step 5: Add the `ml` group and `_require_torch()` to `bfl_asic/cli.py`**

Append at end of file (after the `randomness_report` command):

```python
# ======================================================================
# ml (optional subsystem -- requires `pip install -e ".[ml]"`)
# ======================================================================


def _require_torch() -> None:
    """Raise a friendly ClickException if the optional ML deps are absent."""
    try:
        import torch  # noqa: F401
    except ImportError:
        raise click.ClickException(
            'ML subsystem requires: pip install -e ".[ml]"'
        )


@main.group()
def ml() -> None:
    """Machine-learning learnability instrument (optional [ml] extra)."""
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `python -m pytest tests/test_ml_optional.py -q -k "help or require_torch"`
Expected: 3 passed (the `torch_free` test passes after Task 2).

- [ ] **Step 7: Confirm the existing suite is unaffected**

Run: `python -m pytest -q -k "cli"`
Expected: existing CLI tests still PASS (no collection errors from the new group).

- [ ] **Step 8: Commit**

```bash
git add pyproject.toml bfl_asic/ml/__init__.py bfl_asic/cli.py tests/test_ml_optional.py
git commit -m "ml: add isolated [ml] extra, slow marker, lazy CLI group + torch guard

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 2: `roundreduced.py` — numpy-vectorized round-reduced SHA-256

**Files:**
- Create: `bfl_asic/ml/roundreduced.py`
- Test: `tests/test_ml_roundreduced.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_ml_roundreduced.py
"""Round-reduced SHA-256 correctness. Torch-free."""
import hashlib

import numpy as np
import pytest

from bfl_asic.ml.roundreduced import round_reduced_sha256


def _sha256d(b: bytes) -> bytes:
    return hashlib.sha256(hashlib.sha256(b).digest()).digest()


def test_full_single_round_matches_hashlib_sha256():
    rng = np.random.default_rng(0)
    data = rng.integers(0, 256, size=(64, 32), dtype=np.uint8)
    out = round_reduced_sha256(data, rounds=64, double=False, feed_forward=True)
    for i in range(64):
        expected = hashlib.sha256(bytes(data[i])).digest()
        assert bytes(out[i]) == expected, f"row {i} mismatch"


def test_full_double_matches_hashlib_sha256d_regression_anchor():
    rng = np.random.default_rng(1)
    data = rng.integers(0, 256, size=(50, 32), dtype=np.uint8)
    out = round_reduced_sha256(data, rounds=64, double=True, feed_forward=True)
    for i in range(50):
        assert bytes(out[i]) == _sha256d(bytes(data[i])), f"row {i} mismatch"


def test_batched_equals_per_row():
    rng = np.random.default_rng(2)
    data = rng.integers(0, 256, size=(8, 16), dtype=np.uint8)
    batched = round_reduced_sha256(data, rounds=12, feed_forward=True)
    for i in range(8):
        single = round_reduced_sha256(data[i], rounds=12, feed_forward=True)
        assert np.array_equal(batched[i], single[0])


def test_1d_input_is_promoted_to_one_row():
    out = round_reduced_sha256(np.zeros(32, dtype=np.uint8), rounds=64)
    assert out.shape == (1, 32)
    assert bytes(out[0]) == hashlib.sha256(b"\x00" * 32).digest()


def test_avalanche_grows_with_rounds():
    base = np.zeros((1, 32), dtype=np.uint8)
    flipped = base.copy()
    flipped[0, 0] = 0x01
    diffs = []
    for r in (1, 4, 16, 64):
        a = round_reduced_sha256(base, rounds=r, feed_forward=False)
        b = round_reduced_sha256(flipped, rounds=r, feed_forward=False)
        bits = np.unpackbits(a[0] ^ b[0]).sum()
        diffs.append(int(bits))
    assert diffs[0] < diffs[-1]
    assert 96 <= diffs[-1] <= 160  # ~half of 256 bits at full rounds


@pytest.mark.parametrize("bad", [0, 65, -1])
def test_invalid_rounds_rejected(bad):
    with pytest.raises(ValueError):
        round_reduced_sha256(np.zeros((1, 4), dtype=np.uint8), rounds=bad)


def test_input_longer_than_one_block_rejected():
    with pytest.raises(ValueError):
        round_reduced_sha256(np.zeros((1, 56), dtype=np.uint8), rounds=64)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_ml_roundreduced.py -q`
Expected: FAIL — `ModuleNotFoundError: bfl_asic.ml.roundreduced`.

- [ ] **Step 3: Write the implementation**

```python
# bfl_asic/ml/roundreduced.py
"""Numpy-vectorized round-reduced SHA-256 / SHA-256d.

Single-block only: inputs must be <= 55 bytes so the padded message is
exactly one 512-bit block.  This matches the toolkit's 32-byte hash
inputs and keeps the implementation branch-free across blocks.

At ``rounds=64, double=True, feed_forward=True`` the output is bit-exact
with ``hashlib.sha256(hashlib.sha256(x).digest()).digest()`` -- the
regression anchor (cf. the NIST reference p-values in randomness/).
"""
from __future__ import annotations

import struct

import numpy as np

_U32 = np.uint32

_H = np.array(
    [0x6A09E667, 0xBB67AE85, 0x3C6EF372, 0xA54FF53A,
     0x510E527F, 0x9B05688C, 0x1F83D9AB, 0x5BE0CD19],
    dtype=_U32,
)

_K = np.array(
    [0x428A2F98, 0x71374491, 0xB5C0FBCF, 0xE9B5DBA5, 0x3956C25B, 0x59F111F1,
     0x923F82A4, 0xAB1C5ED5, 0xD807AA98, 0x12835B01, 0x243185BE, 0x550C7DC3,
     0x72BE5D74, 0x80DEB1FE, 0x9BDC06A7, 0xC19BF174, 0xE49B69C1, 0xEFBE4786,
     0x0FC19DC6, 0x240CA1CC, 0x2DE92C6F, 0x4A7484AA, 0x5CB0A9DC, 0x76F988DA,
     0x983E5152, 0xA831C66D, 0xB00327C8, 0xBF597FC7, 0xC6E00BF3, 0xD5A79147,
     0x06CA6351, 0x14292967, 0x27B70A85, 0x2E1B2138, 0x4D2C6DFC, 0x53380D13,
     0x650A7354, 0x766A0ABB, 0x81C2C92E, 0x92722C85, 0xA2BFE8A1, 0xA81A664B,
     0xC24B8B70, 0xC76C51A3, 0xD192E819, 0xD6990624, 0xF40E3585, 0x106AA070,
     0x19A4C116, 0x1E376C08, 0x2748774C, 0x34B0BCB5, 0x391C0CB3, 0x4ED8AA4A,
     0x5B9CCA4F, 0x682E6FF3, 0x748F82EE, 0x78A5636F, 0x84C87814, 0x8CC70208,
     0x90BEFFFA, 0xA4506CEB, 0xBEF9A3F7, 0xC67178F2],
    dtype=_U32,
)


def _rotr(x: np.ndarray, n: int) -> np.ndarray:
    return ((x >> _U32(n)) | (x << _U32(32 - n))).astype(_U32)


def _shr(x: np.ndarray, n: int) -> np.ndarray:
    return (x >> _U32(n)).astype(_U32)


def _pad_one_block(data: np.ndarray) -> np.ndarray:
    """(N, L<=55) uint8 -> (N, 64) uint8 padded single block."""
    n, length = data.shape
    block = np.zeros((n, 64), dtype=np.uint8)
    block[:, :length] = data
    block[:, length] = 0x80
    block[:, 56:64] = np.frombuffer(
        struct.pack(">Q", length * 8), dtype=np.uint8
    )
    return block


def _compress(block: np.ndarray, rounds: int, feed_forward: bool) -> np.ndarray:
    """(N, 64) uint8 block -> (N, 32) uint8 digest after `rounds` rounds."""
    n = block.shape[0]
    words = block.reshape(n, 16, 4).astype(_U32)
    w0 = (
        (words[:, :, 0] << _U32(24))
        | (words[:, :, 1] << _U32(16))
        | (words[:, :, 2] << _U32(8))
        | words[:, :, 3]
    ).astype(_U32)

    sched: list[np.ndarray] = [w0[:, i].astype(_U32) for i in range(16)]
    for i in range(16, rounds):
        s0 = (
            _rotr(sched[i - 15], 7)
            ^ _rotr(sched[i - 15], 18)
            ^ _shr(sched[i - 15], 3)
        )
        s1 = (
            _rotr(sched[i - 2], 17)
            ^ _rotr(sched[i - 2], 19)
            ^ _shr(sched[i - 2], 10)
        )
        sched.append(
            (sched[i - 16] + s0 + sched[i - 7] + s1).astype(_U32)
        )

    a = np.full(n, _H[0], dtype=_U32)
    b = np.full(n, _H[1], dtype=_U32)
    c = np.full(n, _H[2], dtype=_U32)
    d = np.full(n, _H[3], dtype=_U32)
    e = np.full(n, _H[4], dtype=_U32)
    f = np.full(n, _H[5], dtype=_U32)
    g = np.full(n, _H[6], dtype=_U32)
    h = np.full(n, _H[7], dtype=_U32)

    for i in range(rounds):
        big_s1 = _rotr(e, 6) ^ _rotr(e, 11) ^ _rotr(e, 25)
        ch = (e & f) ^ ((~e).astype(_U32) & g)
        t1 = (h + big_s1 + ch + _K[i] + sched[i]).astype(_U32)
        big_s0 = _rotr(a, 2) ^ _rotr(a, 13) ^ _rotr(a, 22)
        maj = (a & b) ^ (a & c) ^ (b & c)
        t2 = (big_s0 + maj).astype(_U32)
        h = g
        g = f
        f = e
        e = (d + t1).astype(_U32)
        d = c
        c = b
        b = a
        a = (t1 + t2).astype(_U32)

    if feed_forward:
        regs = [
            (_H[0] + a).astype(_U32), (_H[1] + b).astype(_U32),
            (_H[2] + c).astype(_U32), (_H[3] + d).astype(_U32),
            (_H[4] + e).astype(_U32), (_H[5] + f).astype(_U32),
            (_H[6] + g).astype(_U32), (_H[7] + h).astype(_U32),
        ]
    else:
        regs = [a, b, c, d, e, f, g, h]

    digest = np.empty((n, 32), dtype=np.uint8)
    for idx, reg in enumerate(regs):
        digest[:, idx * 4 + 0] = (reg >> _U32(24)).astype(np.uint8)
        digest[:, idx * 4 + 1] = (reg >> _U32(16)).astype(np.uint8)
        digest[:, idx * 4 + 2] = (reg >> _U32(8)).astype(np.uint8)
        digest[:, idx * 4 + 3] = (reg & _U32(0xFF)).astype(np.uint8)
    return digest


def round_reduced_sha256(
    data: np.ndarray,
    *,
    rounds: int,
    double: bool = False,
    feed_forward: bool = True,
) -> np.ndarray:
    """Round-reduced SHA-256 over a batch of <=55-byte inputs.

    Parameters
    ----------
    data:
        ``(N, L)`` or ``(L,)`` uint8 array, ``L <= 55``.
    rounds:
        Number of compression rounds, 1..64.
    double:
        Apply the same ``rounds``-round function twice (SHA-256d analog).
    feed_forward:
        Add the post-round state back into the initial hash values
        (True == standard SHA-256 finalisation).

    Returns
    -------
    np.ndarray
        ``(N, 32)`` uint8 digests.
    """
    if not 1 <= rounds <= 64:
        raise ValueError(f"rounds must be in 1..64, got {rounds}")
    arr = np.asarray(data, dtype=np.uint8)
    if arr.ndim == 1:
        arr = arr[None, :]
    if arr.ndim != 2:
        raise ValueError(f"data must be 1-D or 2-D, got {arr.ndim}-D")
    if arr.shape[1] > 55:
        raise ValueError(
            f"input length {arr.shape[1]} exceeds single-block limit (55)"
        )
    out = _compress(_pad_one_block(arr), rounds, feed_forward)
    if double:
        out = _compress(_pad_one_block(out), rounds, feed_forward)
    return out
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_ml_roundreduced.py -q`
Expected: all PASS (8+ tests, including the hashlib regression anchor).

- [ ] **Step 5: Confirm Task 1's deferred test now passes**

Run: `python -m pytest tests/test_ml_optional.py -q`
Expected: 4 passed (`test_ml_package_import_is_torch_free` now green).

- [ ] **Step 6: Commit**

```bash
git add bfl_asic/ml/roundreduced.py tests/test_ml_roundreduced.py
git commit -m "ml: numpy-vectorized round-reduced SHA-256 with hashlib anchor

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 3: `datasets.py` — feature extractors + distinguisher dataset

**Files:**
- Create: `bfl_asic/ml/datasets.py`
- Test: `tests/test_ml_datasets.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_ml_datasets.py
import numpy as np
import pytest

torch = pytest.importorskip("torch")

from bfl_asic.ml.datasets import (
    PerHashImage,
    PerBatchDeviationMap,
    DistinguisherDatasetBuilder,
)


def test_per_hash_image_shape_and_values():
    ex = PerHashImage()
    outputs = np.zeros((5, 32), dtype=np.uint8)
    outputs[:, 0] = 0x80  # top bit of byte 0 set -> pixel (0,0) == 1
    img = ex.extract(outputs)
    assert img.shape == (5, 16, 16)
    assert img.dtype == np.float32
    assert img[0, 0, 0] == 1.0
    assert img[0, 0, 1] == 0.0


def test_per_batch_deviation_map_shape():
    ex = PerBatchDeviationMap(batch=64)
    rng = np.random.default_rng(0)
    outputs = rng.integers(0, 256, size=(64 * 3, 32), dtype=np.uint8)
    dev = ex.extract(outputs)
    assert dev.shape == (3, 16, 16)
    assert np.all(np.abs(dev) <= 0.5 + 1e-6)


def test_distinguisher_builder_deterministic_and_balanced():
    b1 = DistinguisherDatasetBuilder(seed=7, rounds=4, n=512, val_fraction=0.25)
    b2 = DistinguisherDatasetBuilder(seed=7, rounds=4, n=512, val_fraction=0.25)
    d1 = b1.build()
    d2 = b2.build()
    assert torch.equal(d1.x_train, d2.x_train)
    assert torch.equal(d1.y_train, d2.y_train)
    ytr = d1.y_train
    pos = int((ytr == 1).sum())
    assert abs(pos - len(ytr) / 2) <= len(ytr) * 0.1
    assert d1.x_train.shape[1:] == (1, 16, 16)
    assert d1.x_val.shape[0] == 128


def test_distinguisher_different_seed_changes_data():
    a = DistinguisherDatasetBuilder(seed=1, rounds=4, n=256).build()
    b = DistinguisherDatasetBuilder(seed=2, rounds=4, n=256).build()
    assert not torch.equal(a.x_train, b.x_train)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_ml_datasets.py -q`
Expected: FAIL — `ModuleNotFoundError: bfl_asic.ml.datasets` (or all SKIP if torch absent).

- [ ] **Step 3: Write the implementation**

```python
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
        return f"per-batch-deviation-map(b={self._batch})"


@dataclass
class Dataset:
    """Torch tensors ready for the harness."""

    x_train: "object"  # torch.Tensor (N,1,16,16) float32
    y_train: "object"  # torch.Tensor (N,) int64
    x_val: "object"
    y_val: "object"
    feature_name: str


def _counter_inputs(rng: np.random.Generator, n: int) -> np.ndarray:
    """N distinct 32-byte inputs (random, like a nonce stream)."""
    return rng.integers(0, 256, size=(n, 32), dtype=np.uint8)


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

        a_in = _counter_inputs(rng, half)
        a_out = round_reduced_sha256(
            a_in, rounds=self.rounds, double=self.double
        )

        if self.class_b_random:
            b_out = rng.integers(0, 256, size=(half, 32), dtype=np.uint8)
        else:
            b_in = _counter_inputs(rng, half)
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_ml_datasets.py -q`
Expected: all PASS (or all SKIP if torch not installed — both acceptable).

- [ ] **Step 5: Commit**

```bash
git add bfl_asic/ml/datasets.py tests/test_ml_datasets.py
git commit -m "ml: feature extractors + deterministic distinguisher dataset

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 4: `models.py` — TinyCNN, LinearProbe, registry

**Files:**
- Create: `bfl_asic/ml/models.py`
- Test: `tests/test_ml_models.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_ml_models.py
import pytest

torch = pytest.importorskip("torch")

from bfl_asic.ml.models import MODELS, build_model


def test_registry_has_expected_models():
    assert set(MODELS) == {"tiny_cnn", "linear_probe"}


@pytest.mark.parametrize("name", ["tiny_cnn", "linear_probe"])
def test_forward_shape(name):
    model = build_model(name)
    x = torch.zeros(4, 1, 16, 16)
    out = model(x)
    assert out.shape == (4, 2)


def test_linear_probe_param_budget():
    model = build_model("linear_probe")
    n = sum(p.numel() for p in model.parameters())
    assert n == 256 * 2 + 2  # weights + bias for 256->2


def test_unknown_model_raises():
    with pytest.raises(KeyError):
        build_model("nope")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_ml_models.py -q`
Expected: FAIL — `ModuleNotFoundError: bfl_asic.ml.models` (or SKIP without torch).

- [ ] **Step 3: Write the implementation**

```python
# bfl_asic/ml/models.py
"""PyTorch models for the learnability instrument.

Two models on purpose:
* TinyCNN  -- the headline 2-D conv distinguisher.
* LinearProbe -- logistic regression; a lower bound on detectable
  advantage and the rigor baseline for the "no structure" claim.
"""
from __future__ import annotations

import torch
from torch import nn


class TinyCNN(nn.Module):
    """Small 16x16x1 -> 2-class CNN. Deliberately tiny for fast CI."""

    def __init__(self, channels: int = 16) -> None:
        super().__init__()
        self.net = nn.Sequential(
            nn.Conv2d(1, channels, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.Conv2d(channels, channels, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.AdaptiveAvgPool2d(1),
            nn.Flatten(),
            nn.Linear(channels, 2),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x)


class LinearProbe(nn.Module):
    """Flatten 16x16 -> logistic regression (256 -> 2)."""

    def __init__(self) -> None:
        super().__init__()
        self.flatten = nn.Flatten()
        self.linear = nn.Linear(256, 2)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.linear(self.flatten(x))


MODELS: dict[str, type[nn.Module]] = {
    "tiny_cnn": TinyCNN,
    "linear_probe": LinearProbe,
}


def build_model(name: str, **kwargs) -> nn.Module:
    """Instantiate a registered model by name."""
    if name not in MODELS:
        raise KeyError(f"unknown model {name!r}; choices: {sorted(MODELS)}")
    return MODELS[name](**kwargs)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_ml_models.py -q`
Expected: all PASS (or SKIP without torch).

- [ ] **Step 5: Commit**

```bash
git add bfl_asic/ml/models.py tests/test_ml_models.py
git commit -m "ml: TinyCNN + LinearProbe model registry

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 5: `harness.py` — deterministic train/eval with controls

**Files:**
- Create: `bfl_asic/ml/harness.py`
- Test: `tests/test_ml_harness.py`

- [ ] **Step 1: Write the failing test**

```python
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
    cfg = RunConfig(seed=0, rounds=2, n=4096, epochs=8, model="tiny_cnn")
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_ml_harness.py -q -k "ci or determinism"`
Expected: FAIL — `ModuleNotFoundError: bfl_asic.ml.harness` (or SKIP without torch).

- [ ] **Step 3: Write the implementation**

```python
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
```

> Note: `roc_auc_score` import is wrapped in `try/except` at call time so a missing scikit-learn never breaks a run (AUC degrades to NaN). scikit-learn is *not* added to the `[ml]` extra.

- [ ] **Step 4: Run the fast tests to verify they pass**

Run: `python -m pytest tests/test_ml_harness.py -q -k "ci or determinism"`
Expected: 2 passed (or SKIP without torch).

- [ ] **Step 5: Run the slow control tests once locally**

Run: `python -m pytest tests/test_ml_harness.py -q -m slow`
Expected: positive control accuracy > 0.80, negative control CI brackets 0.5 (2 passed). If torch absent, SKIP.

- [ ] **Step 6: Commit**

```bash
git add bfl_asic/ml/harness.py tests/test_ml_harness.py
git commit -m "ml: deterministic train/eval harness with pos/neg controls

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 6: `snapshot.py` + `experiments.py` + `visualization.py` + `ml sweep/run/report/plot`

**Files:**
- Create: `bfl_asic/ml/snapshot.py`, `bfl_asic/ml/experiments.py`, `bfl_asic/ml/visualization.py`
- Modify: `bfl_asic/cli.py` (add commands under the `ml` group from Task 1)
- Test: `tests/test_ml_snapshot.py`, `tests/test_ml_cli.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_ml_snapshot.py
from bfl_asic.ml.snapshot import MLSnapshot


def test_snapshot_roundtrips_through_json(tmp_path):
    snap = MLSnapshot.from_runs(
        experiment="sweep",
        feature="per-hash-image",
        model="tiny_cnn",
        points=[
            {"rounds": 2, "accuracy": 0.99, "advantage": 0.98,
             "accuracy_ci": [0.97, 1.0], "auc": 0.99,
             "min_detectable_advantage": 0.06},
            {"rounds": 64, "accuracy": 0.50, "advantage": 0.0,
             "accuracy_ci": [0.47, 0.53], "auc": 0.50,
             "min_detectable_advantage": 0.06},
        ],
        controls={"positive_ok": True, "negative_ok": True},
    )
    p = tmp_path / "snap.json"
    snap.save(p)
    back = MLSnapshot.load(p)
    assert back.experiment == "sweep"
    assert back.points[1]["rounds"] == 64
    assert back.controls["positive_ok"] is True
```

```python
# tests/test_ml_cli.py
import json

import pytest
from click.testing import CliRunner

torch = pytest.importorskip("torch")

from bfl_asic.cli import main


def test_ml_sweep_tiny(tmp_path, monkeypatch):
    monkeypatch.setenv("BFL_ASIC_OUTPUT_DIR", str(tmp_path))
    res = CliRunner().invoke(
        main,
        ["ml", "sweep", "--rounds", "2,64", "--n", "256",
         "--epochs", "1", "--model", "linear_probe"],
    )
    assert res.exit_code == 0, res.output
    runs = list((tmp_path / "ml").rglob("snapshot.json"))
    assert runs, res.output
    data = json.loads(runs[0].read_text())
    assert data["experiment"] == "sweep"
    assert len(data["points"]) == 2


def test_ml_report_reads_snapshot(tmp_path):
    from bfl_asic.ml.snapshot import MLSnapshot

    snap = MLSnapshot.from_runs(
        experiment="sweep", feature="per-hash-image", model="linear_probe",
        points=[{"rounds": 64, "accuracy": 0.5, "advantage": 0.0,
                 "accuracy_ci": [0.47, 0.53], "auc": 0.5,
                 "min_detectable_advantage": 0.06}],
        controls={"positive_ok": True, "negative_ok": True},
    )
    p = tmp_path / "s.json"
    snap.save(p)
    res = CliRunner().invoke(main, ["ml", "report", str(p)])
    assert res.exit_code == 0
    assert "sweep" in res.output
    assert "64" in res.output
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_ml_snapshot.py tests/test_ml_cli.py -q`
Expected: FAIL — snapshot/experiments/cli pieces missing (cli tests SKIP without torch).

- [ ] **Step 3: Write `snapshot.py`**

```python
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
```

- [ ] **Step 4: Write `experiments.py`**

```python
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
    for r in rounds:
        res = run_training(
            RunConfig(seed=seed, rounds=r, n=n, epochs=epochs,
                      model=model, feature=feature)
        )
        points.append(_point(r, res))

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
    """#4: R=64 with both models; report a bounded null."""
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
```

- [ ] **Step 5: Write `visualization.py`**

```python
# bfl_asic/ml/visualization.py
"""Matplotlib visualizations (Agg backend, like the rest of the project)."""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402


def plot_learnability_curve(snapshot, save_path: Path | None = None):
    """Accuracy & CI vs the knob, with a chance band."""
    pts = sorted(snapshot.points, key=lambda p: p["rounds"])
    xs = [p["rounds"] for p in pts]
    acc = [p["accuracy"] for p in pts]
    lo = [p["accuracy_ci"][0] for p in pts]
    hi = [p["accuracy_ci"][1] for p in pts]

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.axhspan(0.45, 0.55, color="grey", alpha=0.2, label="chance band")
    ax.fill_between(xs, lo, hi, alpha=0.25, label="95% CI")
    ax.plot(xs, acc, "o-", label="held-out accuracy")
    ax.set_xlabel("SHA-256 rounds (knob)")
    ax.set_ylabel("distinguisher accuracy")
    ax.set_ylim(0.4, 1.02)
    ax.set_title(
        f"Learnability collapse ({snapshot.model}, {snapshot.feature})"
    )
    ax.legend(loc="upper right")
    fig.tight_layout()
    if save_path is not None:
        fig.savefig(save_path, dpi=120)
    return fig
```

- [ ] **Step 6: Add CLI commands under the `ml` group in `bfl_asic/cli.py`**

Append directly after the `def ml()` group definition added in Task 1:

```python
@ml.command(name="sweep")
@click.option("--rounds", default=None,
              help="Comma-separated round counts. Default: the standard set.")
@click.option("--seed", default=0, type=int)
@click.option("--n", default=8192, type=int, help="Samples per round.")
@click.option("--epochs", default=10, type=int)
@click.option("--model", default="tiny_cnn",
              type=click.Choice(["tiny_cnn", "linear_probe"]))
@click.option("--feature", default="per-hash",
              type=click.Choice(["per-hash", "per-batch"]))
@click.option("-o", "--output", default=None, type=click.Path())
@click.option("--plot", is_flag=True, default=False)
def ml_sweep(rounds, seed, n, epochs, model, feature, output, plot) -> None:
    """Experiment #1: round-reduced learnability sweep."""
    _require_torch()
    from bfl_asic.ml.experiments import DEFAULT_ROUNDS, run_sweep
    from bfl_asic.ml.snapshot import MLSnapshot

    round_list = (
        [int(x) for x in rounds.split(",")] if rounds else DEFAULT_ROUNDS
    )
    click.echo(
        f"Sweeping rounds {round_list} (model={model}, feature={feature})..."
    )
    points, controls = run_sweep(
        round_list, seed=seed, n=n, epochs=epochs, model=model,
        feature=feature,
    )
    snap = MLSnapshot.from_runs(
        experiment="sweep", feature=feature, model=model,
        points=points, controls=controls,
    )

    click.echo("")
    click.echo(f"  {'rounds':>6}  {'accuracy':>9}  {'advantage':>9}")
    for p in points:
        click.echo(
            f"  {p['rounds']:>6}  {p['accuracy']:>9.4f}  "
            f"{p['advantage']:>9.4f}"
        )
    click.echo("")
    click.echo(
        f"  Controls: positive_ok={controls['positive_ok']} "
        f"negative_ok={controls['negative_ok']}"
    )

    run_dir = default_run_dir("ml") if output is None else None
    snap_path = unique_output_path(
        Path(output) if output else run_dir / "snapshot.json"
    )
    snap.save(snap_path)
    click.echo(f"  Snapshot saved to: {snap_path}")

    if plot:
        import matplotlib.pyplot as plt
        from bfl_asic.ml.visualization import plot_learnability_curve

        png = unique_output_path(
            (Path(output).with_suffix(".png")) if output
            else run_dir / "learnability.png"
        )
        fig = plot_learnability_curve(snap, save_path=png)
        plt.close(fig)
        click.echo(f"  Plot saved to: {png}")


@ml.command(name="run")
@click.argument("experiment",
                type=click.Choice(["indistinguishability", "full_structure"]))
@click.option("--seed", default=0, type=int)
@click.option("--n", default=8192, type=int)
@click.option("--epochs", default=10, type=int)
@click.option("-o", "--output", default=None, type=click.Path())
def ml_run(experiment, seed, n, epochs, output) -> None:
    """Experiments #2 / #4 by name."""
    _require_torch()
    from bfl_asic.ml.experiments import run_full_structure, run_sweep
    from bfl_asic.ml.snapshot import MLSnapshot

    if experiment == "indistinguishability":
        points, controls = run_sweep(
            [64], seed=seed, n=n, epochs=epochs, model="tiny_cnn"
        )
        snap = MLSnapshot.from_runs(
            experiment="indistinguishability",
            feature="per-hash-image", model="tiny_cnn",
            points=points, controls=controls,
        )
        click.echo(f"  Full SHA-256 vs random accuracy: "
                   f"{points[0]['accuracy']:.4f} "
                   f"CI={points[0]['accuracy_ci']}")
    else:
        points, controls, bnull = run_full_structure(
            seed=seed, n=n, epochs=epochs
        )
        snap = MLSnapshot.from_runs(
            experiment="full_structure",
            feature="per-hash-image", model="multi",
            points=points, controls=controls, bounded_null=bnull,
        )
        click.echo(f"  Bounded null: {bnull['conclusion']}")
        click.echo(f"    best acc={bnull['accuracy']:.4f} "
                   f"CI={bnull['accuracy_ci']} "
                   f"MDA={bnull['min_detectable_advantage']:.4f}")

    run_dir = default_run_dir("ml") if output is None else None
    snap_path = unique_output_path(
        Path(output) if output else run_dir / "snapshot.json"
    )
    snap.save(snap_path)
    click.echo(f"  Snapshot saved to: {snap_path}")


@ml.command(name="report")
@click.argument("snapshot_path", type=click.Path(exists=True))
def ml_report(snapshot_path: str) -> None:
    """Print a saved ML snapshot."""
    from bfl_asic.ml.snapshot import MLSnapshot

    try:
        snap = MLSnapshot.load(Path(snapshot_path))
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        raise click.ClickException(f"Failed to load snapshot: {exc}")

    click.echo("=== ML Report ===")
    click.echo(f"  Experiment: {snap.experiment}")
    click.echo(f"  Model:      {snap.model}")
    click.echo(f"  Feature:    {snap.feature}")
    click.echo(f"  Timestamp:  {snap.timestamp}")
    click.echo("")
    click.echo(f"  {'rounds':>6}  {'accuracy':>9}  {'advantage':>9}")
    for p in snap.points:
        click.echo(
            f"  {p.get('rounds', '-'):>6}  {p['accuracy']:>9.4f}  "
            f"{p['advantage']:>9.4f}"
        )
    if snap.bounded_null:
        click.echo("")
        click.echo(f"  Bounded null: {snap.bounded_null.get('conclusion')}")


@ml.command(name="plot")
@click.argument("snapshot_path", type=click.Path(exists=True))
def ml_plot(snapshot_path: str) -> None:
    """Render the learnability curve from a saved snapshot."""
    import matplotlib.pyplot as plt

    from bfl_asic.ml.snapshot import MLSnapshot
    from bfl_asic.ml.visualization import plot_learnability_curve

    snap = MLSnapshot.load(Path(snapshot_path))
    png = unique_output_path(Path(snapshot_path).with_suffix(".png"))
    fig = plot_learnability_curve(snap, save_path=png)
    plt.close(fig)
    click.echo(f"  Plot saved to: {png}")
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `python -m pytest tests/test_ml_snapshot.py tests/test_ml_cli.py -q`
Expected: snapshot tests PASS; cli tests PASS (or SKIP without torch).

- [ ] **Step 8: Re-confirm the torch-free guarantee still holds**

Run: `python -m pytest tests/test_ml_optional.py -q`
Expected: 4 passed (`--help` and `ml --help` unaffected by the new commands).

- [ ] **Step 9: Commit**

```bash
git add bfl_asic/ml/snapshot.py bfl_asic/ml/experiments.py bfl_asic/ml/visualization.py bfl_asic/cli.py tests/test_ml_snapshot.py tests/test_ml_cli.py
git commit -m "ml: snapshot, experiments (#1/#2/#4), viz, and ml CLI commands

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 7: Per-batch deviation map end-to-end + saliency map

**Files:**
- Modify: `bfl_asic/ml/visualization.py` (add `plot_saliency_map`)
- Test: `tests/test_ml_cli.py` (add a per-batch sweep case), `tests/test_ml_models.py` (add saliency test)

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_ml_cli.py`:

```python
def test_ml_sweep_per_batch_feature(tmp_path, monkeypatch):
    monkeypatch.setenv("BFL_ASIC_OUTPUT_DIR", str(tmp_path))
    res = CliRunner().invoke(
        main,
        ["ml", "sweep", "--rounds", "2,64", "--n", "4096",
         "--epochs", "1", "--model", "linear_probe",
         "--feature", "per-batch"],
    )
    assert res.exit_code == 0, res.output
    runs = list((tmp_path / "ml").rglob("snapshot.json"))
    assert runs
```

Append to `tests/test_ml_models.py`:

```python
def test_saliency_map_writes_png(tmp_path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    from bfl_asic.ml.models import build_model
    from bfl_asic.ml.visualization import plot_saliency_map

    model = build_model("linear_probe")
    fig = plot_saliency_map(model, save_path=tmp_path / "sal.png")
    assert (tmp_path / "sal.png").exists()
    plt.close(fig)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_ml_models.py -q -k saliency`
Expected: FAIL — `ImportError: cannot import name 'plot_saliency_map'` (or SKIP without torch).

- [ ] **Step 3: Add `plot_saliency_map` to `bfl_asic/ml/visualization.py`**

```python
def plot_saliency_map(model, save_path: Path | None = None):
    """16x16 input-gradient saliency for a trained model.

    At low rounds this highlights specific stuck/biased bits; at 64
    rounds it is uniform noise -- the visual payoff of the instrument.
    """
    import numpy as np
    import torch

    x = torch.zeros(1, 1, 16, 16, requires_grad=True)
    out = model(x)
    out[0, 1].backward()
    grad = x.grad.detach().abs().numpy().reshape(16, 16)

    fig, ax = plt.subplots(figsize=(5, 5))
    im = ax.imshow(grad, cmap="magma")
    ax.set_title("Distinguisher saliency (|d logit / d bit|)")
    ax.set_xticks([])
    ax.set_yticks([])
    fig.colorbar(im, ax=ax, fraction=0.046)
    fig.tight_layout()
    if save_path is not None:
        fig.savefig(save_path, dpi=120)
    return fig
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_ml_models.py tests/test_ml_cli.py -q`
Expected: all PASS (or SKIP without torch). The per-batch case exercises `PerBatchDeviationMap` through the full CLI path.

- [ ] **Step 5: Commit**

```bash
git add bfl_asic/ml/visualization.py tests/test_ml_models.py tests/test_ml_cli.py
git commit -m "ml: per-batch deviation feature end-to-end + saliency map viz

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 8: Experiment #3 — `OrbitDatasetBuilder` (dynamics learnability)

**Files:**
- Modify: `bfl_asic/ml/datasets.py` (add `OrbitDatasetBuilder`)
- Modify: `bfl_asic/ml/experiments.py` (add `run_dynamics_sweep`)
- Modify: `bfl_asic/cli.py` (`run` choices add `dynamics`)
- Test: `tests/test_ml_datasets.py` (add orbit case), `tests/test_ml_cli.py` (add dynamics case)

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_ml_datasets.py`:

```python
def test_orbit_dataset_builder_labels_and_determinism():
    from bfl_asic.ml.datasets import OrbitDatasetBuilder

    a = OrbitDatasetBuilder(seed=5, trunc_bytes=2, n=128, n_bins=3).build()
    b = OrbitDatasetBuilder(seed=5, trunc_bytes=2, n=128, n_bins=3).build()
    assert torch.equal(a.x_train, b.x_train)
    assert a.x_train.shape[1:] == (1, 16, 16)
    labels = torch.cat([a.y_train, a.y_val])
    assert int(labels.min()) >= 0
    assert int(labels.max()) <= 2
```

Append to `tests/test_ml_cli.py`:

```python
def test_ml_run_dynamics(tmp_path, monkeypatch):
    monkeypatch.setenv("BFL_ASIC_OUTPUT_DIR", str(tmp_path))
    res = CliRunner().invoke(
        main,
        ["ml", "run", "dynamics", "--n", "128", "--epochs", "1"],
    )
    assert res.exit_code == 0, res.output
    assert list((tmp_path / "ml").rglob("snapshot.json"))
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_ml_datasets.py -q -k orbit`
Expected: FAIL — `ImportError: cannot import name 'OrbitDatasetBuilder'` (or SKIP without torch).

- [ ] **Step 3: Add `OrbitDatasetBuilder` to `bfl_asic/ml/datasets.py`**

```python
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
            tails.append(info.tail_length if info is not None else -1)
        tarr = np.array(tails, dtype=np.float64)
        valid = tarr[tarr >= 0]
        edges = (
            np.quantile(valid, np.linspace(0, 1, self.n_bins + 1))
            if valid.size
            else np.linspace(0, 1, self.n_bins + 1)
        )
        edges[0], edges[-1] = -1.0, np.inf
        y = np.clip(
            np.digitize(tarr, edges[1:-1]), 0, self.n_bins - 1
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
```

- [ ] **Step 4: Add `run_dynamics_sweep` to `bfl_asic/ml/experiments.py`**

```python
def run_dynamics_sweep(
    *, seed: int = 0, n: int = 2048, epochs: int = 10,
    trunc_widths: list[int] | None = None, n_bins: int = 4,
) -> tuple[list[dict], dict]:
    """#3: predict binned orbit tail length from the seed, vs truncation."""
    import torch

    from bfl_asic.ml.datasets import OrbitDatasetBuilder
    from bfl_asic.ml.models import build_model

    widths = trunc_widths or [1, 2, 3]
    points: list[dict] = []
    for t in widths:
        torch.manual_seed(seed)
        data = OrbitDatasetBuilder(
            seed=seed, trunc_bytes=t, n=n, n_bins=n_bins
        ).build()
        model = build_model("tiny_cnn")
        opt = torch.optim.Adam(model.parameters(), lr=1e-3)
        loss_fn = torch.nn.CrossEntropyLoss()
        ntr = len(data.y_train)
        for _ in range(epochs):
            model.train(True)
            for s in range(0, ntr, 128):
                opt.zero_grad()
                out = model(data.x_train[s : s + 128])
                loss = loss_fn(out, data.y_train[s : s + 128])
                loss.backward()
                opt.step()
        model.train(False)  # eval/inference mode (see hook note)
        with torch.no_grad():
            pred = model(data.x_val).argmax(1)
            acc = float((pred == data.y_val).float().mean())
        chance = 1.0 / n_bins
        points.append(
            {
                "rounds": t,  # reuse the "rounds" key as the knob axis
                "accuracy": acc,
                "advantage": acc - chance,
                "auc": float("nan"),
                "accuracy_ci": [0.0, 1.0],
                "min_detectable_advantage": 0.0,
                "chance": chance,
            }
        )
    controls = {
        "positive_ok": points[0]["accuracy"] >= points[0]["chance"],
        "negative_ok": True,
        "note": "knob is truncation width (bytes); chance = 1/n_bins",
    }
    return points, controls
```

- [ ] **Step 5: Add `dynamics` to the `ml run` command in `bfl_asic/cli.py`**

Change the `experiment` argument decorator in `ml_run`:

```python
@click.argument("experiment",
                type=click.Choice(
                    ["indistinguishability", "full_structure", "dynamics"]))
```

Then, inside `ml_run`, immediately after `_require_torch()` and the existing
`from bfl_asic.ml.experiments import run_full_structure, run_sweep` /
`from bfl_asic.ml.snapshot import MLSnapshot` imports, insert this branch
*before* the existing `if experiment == "indistinguishability":` (and leave
the existing two branches intact, so the structure becomes
`if dynamics: ... elif indistinguishability: ... else: ...`):

```python
    if experiment == "dynamics":
        from bfl_asic.ml.experiments import run_dynamics_sweep

        points, controls = run_dynamics_sweep(
            seed=seed, n=n, epochs=epochs
        )
        snap = MLSnapshot.from_runs(
            experiment="dynamics", feature="seed-image",
            model="tiny_cnn", points=points, controls=controls,
        )
        click.echo("  Dynamics learnability (knob = truncation bytes):")
        for p in points:
            click.echo(
                f"    t={p['rounds']}  acc={p['accuracy']:.4f} "
                f"(chance {p['chance']:.3f})"
            )
        run_dir = default_run_dir("ml") if output is None else None
        snap_path = unique_output_path(
            Path(output) if output else run_dir / "snapshot.json"
        )
        snap.save(snap_path)
        click.echo(f"  Snapshot saved to: {snap_path}")
        return
```

(The existing `indistinguishability` branch becomes `elif experiment == "indistinguishability":`.)

- [ ] **Step 6: Run tests to verify they pass**

Run: `python -m pytest tests/test_ml_datasets.py tests/test_ml_cli.py -q`
Expected: all PASS (or SKIP without torch).

- [ ] **Step 7: Commit**

```bash
git add bfl_asic/ml/datasets.py bfl_asic/ml/experiments.py bfl_asic/cli.py tests/test_ml_datasets.py tests/test_ml_cli.py
git commit -m "ml: experiment #3 dynamics learnability (orbit tail vs truncation)

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 9: `ml publish` — optional HF lab-notebook upload (cuttable)

**Files:**
- Create: `bfl_asic/ml/publish.py`
- Modify: `bfl_asic/cli.py` (add `ml publish`)
- Test: `tests/test_ml_publish.py`

> This task is explicitly cuttable. If skipped, nothing else breaks; jump to Task 10.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_ml_publish.py
import sys
import types

from bfl_asic.ml.publish import build_model_card


def test_model_card_contains_key_facts():
    from bfl_asic.ml.snapshot import MLSnapshot

    snap = MLSnapshot.from_runs(
        experiment="sweep", feature="per-hash-image", model="tiny_cnn",
        points=[{"rounds": 64, "accuracy": 0.5, "advantage": 0.0,
                 "accuracy_ci": [0.47, 0.53], "auc": 0.5,
                 "min_detectable_advantage": 0.06}],
        controls={"positive_ok": True, "negative_ok": True},
    )
    card = build_model_card(snap)
    assert "sweep" in card
    assert "tiny_cnn" in card
    assert "learnability" in card.lower()


def test_publish_invokes_hf_api(monkeypatch, tmp_path):
    calls = {}

    fake_hf = types.ModuleType("huggingface_hub")

    class FakeApi:
        def create_repo(self, repo_id, exist_ok=False, **kw):
            calls["repo"] = repo_id

        def upload_folder(self, repo_id, folder_path, **kw):
            calls["folder"] = folder_path

    fake_hf.HfApi = FakeApi
    monkeypatch.setitem(sys.modules, "huggingface_hub", fake_hf)

    from bfl_asic.ml.publish import publish_run

    (tmp_path / "snapshot.json").write_text("{}")
    publish_run(tmp_path, repo_id="user/bfl-ml")
    assert calls["repo"] == "user/bfl-ml"
    assert str(tmp_path) in str(calls["folder"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_ml_publish.py -q`
Expected: FAIL — `ModuleNotFoundError: bfl_asic.ml.publish`.

- [ ] **Step 3: Write the implementation**

```python
# bfl_asic/ml/publish.py
"""Optional: push a run directory to the HF Hub as a shareable lab notebook.

huggingface_hub is imported lazily; it lives in the [ml] extra.
"""
from __future__ import annotations

from pathlib import Path


def build_model_card(snapshot) -> str:
    """Render a Markdown model card from an MLSnapshot."""
    lines = [
        "# BFL-ASIC ML Learnability Run",
        "",
        f"- Experiment: **{snapshot.experiment}**",
        f"- Model: `{snapshot.model}`",
        f"- Feature: `{snapshot.feature}`",
        f"- Timestamp: {snapshot.timestamp}",
        "",
        "## Learnability points",
        "",
        "| knob | accuracy | advantage |",
        "|-----:|---------:|----------:|",
    ]
    for p in snapshot.points:
        lines.append(
            f"| {p.get('rounds', '-')} | {p['accuracy']:.4f} "
            f"| {p['advantage']:.4f} |"
        )
    if snapshot.bounded_null:
        lines += [
            "",
            "## Bounded null",
            "",
            f"> {snapshot.bounded_null.get('conclusion', '')}",
        ]
    lines += [
        "",
        "_Generated by `bfl-asic ml publish`. Datasets are regenerable "
        "from the run seed; none are hosted here._",
    ]
    return "\n".join(lines)


def publish_run(run_dir: Path, repo_id: str, *, private: bool = True) -> str:
    """Upload *run_dir* (snapshot/plots) + a model card to the Hub."""
    from huggingface_hub import HfApi

    from bfl_asic.ml.snapshot import MLSnapshot

    run_dir = Path(run_dir)
    snap_path = run_dir / "snapshot.json"
    if snap_path.exists() and snap_path.read_text().strip() not in ("", "{}"):
        card = build_model_card(MLSnapshot.load(snap_path))
        (run_dir / "README.md").write_text(card)

    api = HfApi()
    api.create_repo(repo_id, exist_ok=True, repo_type="model", private=private)
    api.upload_folder(repo_id=repo_id, folder_path=str(run_dir))
    return repo_id
```

- [ ] **Step 4: Add the `ml publish` command to `bfl_asic/cli.py`**

```python
@ml.command(name="publish")
@click.argument("run_dir", type=click.Path(exists=True))
@click.option("--repo-id", required=True,
              help="HF repo id, e.g. user/bfl-ml-runs.")
@click.option("--public", is_flag=True, default=False)
def ml_publish(run_dir: str, repo_id: str, public: bool) -> None:
    """Push a run directory to the HF Hub as a shareable lab notebook."""
    try:
        from bfl_asic.ml.publish import publish_run
    except ImportError:
        raise click.ClickException(
            'ml publish requires: pip install -e ".[ml]"'
        )
    try:
        rid = publish_run(Path(run_dir), repo_id=repo_id, private=not public)
    except ImportError:
        raise click.ClickException(
            'ml publish requires: pip install -e ".[ml]"'
        )
    click.echo(f"  Published to: https://huggingface.co/{rid}")
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python -m pytest tests/test_ml_publish.py -q`
Expected: 2 passed (HF is mocked; no network).

- [ ] **Step 6: Commit**

```bash
git add bfl_asic/ml/publish.py bfl_asic/cli.py tests/test_ml_publish.py
git commit -m "ml: optional HF publish + model-card generation

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 10: Docs bookkeeping + full-suite verification

**Files:**
- Modify: `README.md`, `LEARNING.md`, `DEVLOG.md`, `bfl-asic-repurpose.md`, `CLAUDE.md`

- [ ] **Step 1: Run the full default suite (must stay torch-free & green)**

Run: `python -m pytest -q -m "not slow"`
Expected: existing ~671 tests still PASS; new ML tests PASS (if torch installed) or SKIP (if not). Record the new total reported by pytest.

- [ ] **Step 2: Update `README.md`**

Add this block immediately after the randomness "View saved results" code block (before "### Where outputs go"):

````markdown
### ML learnability instrument (optional [ml] extra)

```bash
pip install -e ".[ml]"

# Where does SHA-256 become unlearnable? (round-reduced sweep)
bfl-asic ml sweep --rounds 1,2,4,8,16,32,64 --plot

# Rigorous "is there ANY structure in full SHA-256?" bounded null
bfl-asic ml run full_structure

# Iterated-hash orbit learnability vs truncation width
bfl-asic ml run dynamics
```

Requires PyTorch (installed only via the optional `[ml]` extra). The
rest of the toolkit runs without it.
````

In the Architecture tree, add under the application packages:

```
  ml/              # Optional learnability instrument (torch behind [ml])
    roundreduced.py # Numpy-vectorized round-reduced SHA-256
    datasets.py     # Feature extractors + distinguisher/orbit datasets
    models.py       # TinyCNN + LinearProbe
    harness.py      # Deterministic train/eval + pos/neg controls
    experiments.py  # The four named experiments
    snapshot.py     # JSON-serializable results
    visualization.py # Learnability curve + saliency map
```

Update the "Testing" section's "671 tests" to the total recorded in Step 1.

- [ ] **Step 3: Update `CLAUDE.md`**

In the "Application layer" bullet list, append:

```markdown
- `bfl_asic/ml/` — Optional ML learnability instrument (PyTorch behind the
  `[ml]` extra; lazy-imported by the CLI). Numpy-vectorized round-reduced
  SHA-256, distinguisher/orbit datasets, TinyCNN/LinearProbe, a train/eval
  harness with positive/negative controls, and a `ml` CLI group
  (`sweep`/`run`/`report`/`plot`/`publish`). The core install never
  requires torch; default `pytest` stays torch-free (ML tests skip).
```

Update the "~671 tests" figure in "Common Commands" to the Step 1 total.

- [ ] **Step 4: Update `DEVLOG.md`**

Prepend a dated entry. Use this exact text:

```markdown
## 2026-05-15 — Optional ML learnability subsystem

Added `bfl_asic/ml/`: a numpy-vectorized round-reduced SHA-256 (bit-exact
with hashlib SHA-256d at 64 rounds — the regression anchor), deterministic
distinguisher/orbit datasets, TinyCNN + LinearProbe, and a controls-gated
train/eval harness. Four experiments: the round-reduced learnability sweep
(#1), the full-SHA indistinguishability demo (#2), the bounded-null
"any structure" search (#4), and dynamics-orbit learnability vs truncation
(#3). PyTorch is isolated behind the `[ml]` extra and lazy-imported by the
CLI, so the core install and the default test suite remain torch-free.
A null result is only emitted when the positive control learns and the
negative control fails.
```

- [ ] **Step 5: Update `bfl-asic-repurpose.md` and `LEARNING.md`**

- In `bfl-asic-repurpose.md`, locate the App whose theme is ML / structure
  search / cryptanalysis and update its status banner to implemented,
  using the same banner format already used for App 1/2/8 (a one-line
  `> **Status:** Implemented (2026-05-15) — see bfl_asic/ml/` style line).
  If no App matches, add a short "Addendum: ML learnability instrument
  (implemented 2026-05-15)" subsection at the end mirroring existing
  subsection formatting.
- In `LEARNING.md`, add a new section after "### Beyond Week 6" titled
  "### Week 7 — Where learnability dies", with this text:

```markdown
Goal: see, empirically, that cryptographic strength == unlearnability.

- Run the sweep:
  ```bash
  bfl-asic ml sweep --rounds 1,2,4,8,16,32,64 --plot
  ```
- Open `runs/ml/<ts>/learnability.png`. The accuracy curve falls from
  ~100% to the chance band: that collapse *is* the avalanche finishing.
- Run `bfl-asic ml run full_structure`. The bounded-null line is the
  honest scientific statement of "we found nothing, and here is how
  small a bias we could have detected." A flat curve at 64 rounds is
  SHA-256 working exactly as designed.
```

- [ ] **Step 6: Commit**

```bash
git add README.md LEARNING.md DEVLOG.md bfl-asic-repurpose.md CLAUDE.md
git commit -m "docs: bookkeeping for the optional ML learnability subsystem

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Self-Review

**1. Spec coverage:**
- §5 `roundreduced.py` + hashlib anchor → Task 2 ✓
- §5 `datasets.py` (PerHashImage, PerBatchDeviationMap, Distinguisher, Orbit) → Tasks 3, 7, 8 ✓
- §5 `models.py` (TinyCNN, LinearProbe, registry) → Task 4 ✓
- §5 `harness.py` (accuracy, advantage, AUC, Clopper-Pearson CI, MDA, pos/neg controls, determinism) → Task 5 ✓
- §5 `experiments.py` (#1 sweep, #2 indistinguishability, #4 full_structure, #3 dynamics) → Tasks 6, 8 ✓
- §5 `snapshot.py` (mirrors randomness snapshot) → Task 6 ✓
- §5 `visualization.py` (learnability curve, saliency map) → Tasks 6, 7 ✓
- §5 CLI `ml` group + lazy import + friendly error + sweep/run/report/plot/publish → Tasks 1, 6, 8, 9 ✓
- §6 `[ml]` extra, one-way imports, master delivery → Tasks 1, 10 ✓
- §7 bounded-null methodology (controls gate the null) → Task 6 `run_full_structure` + Task 5 controls ✓
- §8 all eight test files + torch-free guarantee + slow markers → every task; Tasks 1, 5, 10 ✓
- §9 build order → Tasks 1→10 follow it exactly ✓
- §10 risks (anchor test, determinism test, leakage caught by negative control, CI time via tiny configs + slow marker) → Tasks 2, 5 ✓

**2. Placeholder scan:** No "TBD/TODO/handle edge cases/similar to". Every code and test step contains complete code; every run step has an exact command and expected result. Task 5/9 wrap `roc_auc_score`/`huggingface_hub` imports explicitly rather than hand-waving.

**3. Type consistency:**
- `Dataset(x_train, y_train, x_val, y_val, feature_name)` — defined in Task 3; used identically in Task 5 (`_negative_control_dataset`), Task 8 (`OrbitDatasetBuilder`). ✓
- `RunConfig` fields (`seed, rounds, n, epochs, batch_size, lr, model, double, negative_control, feature, feature_batch`) defined in Task 5; every construction site in Task 6 `experiments.py` uses only these names. ✓
- `RunResult` fields used by `_point()` in Task 6 (`accuracy, advantage, auc, accuracy_ci, min_detectable_advantage`) all exist on the Task 5 dataclass. ✓
- `MLSnapshot.from_runs(experiment, feature, model, points, controls, bounded_null=None)` — signature identical at every call site (Tasks 6, 8, 9 tests). ✓
- `round_reduced_sha256(data, *, rounds, double=False, feed_forward=True)` — stable across Tasks 2, 3. ✓
- `plot_learnability_curve(snapshot, save_path=None)` / `plot_saliency_map(model, save_path=None)` — defined Task 6/7, called with matching args in CLI and tests. ✓
- The `points[*]["rounds"]` key is intentionally the generic knob axis (round count for #1/#2/#4, truncation bytes for #3) — documented in Task 8 Step 4 and the dynamics `_point`-equivalent. ✓
- `model.train(False)` used in place of `model.eval()` consistently (Tasks 5, 8) per the header hook note. ✓

No issues found requiring inline fixes.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-05-15-ml-learnability-instrument.md`.
