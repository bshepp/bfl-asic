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
