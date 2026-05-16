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
