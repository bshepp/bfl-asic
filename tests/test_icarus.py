"""Tests for the Icarus / Block-Erupter protocol (work-in / nonce-out).

Anchored to cgminer's driver-icarus.c golden self-test: the 64-byte
``golden_ob`` yields nonce 0x000187a2 (big-endian on the wire). Byte order
was confirmed on real hardware (ASICMiner Block Erupter, 2026-08-19).

Pure functions, no I/O.
"""
from __future__ import annotations

import pytest

from bfl_asic.protocol.icarus import (
    GOLDEN_WORK, GOLDEN_NONCE, build_work, parse_nonce,
)


def test_golden_constants_match_cgminer():
    assert len(GOLDEN_WORK) == 64
    assert GOLDEN_WORK.hex() == (
        "4679ba4ec99876bf4bfe086082b40025"
        "4df6c356451471139a3afa71e48f544a"
        "00000000000000000000000000000000"
        "0000000087320b1a1426674f2fa722ce")
    assert GOLDEN_NONCE == 0x000187A2


def test_parse_nonce_is_big_endian():
    assert parse_nonce(bytes.fromhex("000187a2")) == 0x000187A2
    assert parse_nonce(b"\x00\x00\x00\x01") == 1


def test_parse_nonce_rejects_wrong_length():
    with pytest.raises(ValueError):
        parse_nonce(b"\x00\x00\x00")  # 3 bytes, not 4


def test_build_work_layout():
    # cgminer sends rev(midstate,32) + 20-byte fill + rev(data,12).
    midstate = bytes(range(32))
    data = bytes(range(100, 112))  # 12 bytes
    w = build_work(midstate, data)
    assert len(w) == 64
    assert w[:32] == midstate[::-1]
    assert w[32:52] == b"\x00" * 20
    assert w[52:] == data[::-1]


def test_build_work_validates_lengths():
    with pytest.raises(ValueError):
        build_work(bytes(31), bytes(12))
    with pytest.raises(ValueError):
        build_work(bytes(32), bytes(11))


# --- simulated Icarus transport (headless testing, no hardware) ---------

def test_simulated_icarus_transport_golden_roundtrip():
    from bfl_asic.transport.icarus_simulator import SimulatedIcarusTransport
    t = SimulatedIcarusTransport()
    t.open()
    t.write(GOLDEN_WORK)
    assert parse_nonce(t.read(4)) == GOLDEN_NONCE
    t.close()


def test_simulated_icarus_transport_nonce_is_deterministic():
    from bfl_asic.transport.icarus_simulator import SimulatedIcarusTransport
    t = SimulatedIcarusTransport()
    t.open()
    work = build_work(bytes(range(32)), bytes(range(100, 112)))
    t.write(work)
    n1 = parse_nonce(t.read(4))
    t.write(work)
    n2 = parse_nonce(t.read(4))
    assert n1 == n2
    assert 0 <= n1 < (1 << 32)


def test_simulated_icarus_transport_accumulates_partial_writes():
    from bfl_asic.transport.icarus_simulator import SimulatedIcarusTransport
    t = SimulatedIcarusTransport()
    t.open()
    # split the 64-byte work across two writes; nonce only after all 64 arrive
    t.write(GOLDEN_WORK[:40])
    assert t.read(4) == b""
    t.write(GOLDEN_WORK[40:])
    assert parse_nonce(t.read(4)) == GOLDEN_NONCE


# --- linear-scan hashrate (the Erupter's natural metric) ----------------

def test_linear_scan_hashrate_from_position_over_time():
    from bfl_asic.protocol.icarus import linear_scan_hashrate
    # The Erupter scans nonces linearly from 0, so position / arrival-time
    # is the hashrate directly. These three all imply 335 MH/s.
    pairs = [(335_000_000, 1.0), (670_000_000, 2.0), (1_005_000_000, 3.0)]
    hr = linear_scan_hashrate(pairs)
    assert abs(hr - 335_000_000) < 1_000


def test_linear_scan_hashrate_ignores_nonpositive_time():
    from bfl_asic.protocol.icarus import linear_scan_hashrate
    pairs = [(100, 0.0), (335_000_000, 1.0)]  # first is unusable
    assert abs(linear_scan_hashrate(pairs) - 335_000_000) < 1_000


def test_linear_scan_hashrate_empty_is_none():
    from bfl_asic.protocol.icarus import linear_scan_hashrate
    assert linear_scan_hashrate([]) is None


# --- IcarusNonceSource + the extra_metrics() hook -----------------------

def _work(n):
    for i in range(n):
        yield (bytes([i % 256]) * 32, bytes([i % 256]) * 12)


def test_icarus_nonce_source_yields_a_result_per_work():
    from bfl_asic.transport.icarus_simulator import SimulatedIcarusTransport
    from bfl_asic.nonce_source import IcarusNonceSource
    src = IcarusNonceSource(SimulatedIcarusTransport(), _work(10))
    out = list(src.results(count=10))
    assert len(out) == 10
    assert all(r.nonces for r in out)  # sim returns one nonce per work
    assert src.name() == "icarus-nonce-source"


def test_icarus_nonce_source_reports_hashrate_extra_metric():
    from bfl_asic.transport.icarus_simulator import SimulatedIcarusTransport
    from bfl_asic.nonce_source import IcarusNonceSource
    src = IcarusNonceSource(SimulatedIcarusTransport(), _work(5))
    list(src.results(count=5))
    m = src.extra_metrics()
    assert "hashrate_mhps" in m and "samples" in m
    assert m["samples"] == 5


def test_base_nonce_source_extra_metrics_defaults_empty():
    from bfl_asic.nonce_source import SimulatedNonceSource
    assert SimulatedNonceSource().extra_metrics() == {}


# --- characterize_source: the common core over any NonceSource ----------

def test_characterize_source_common_core_on_icarus():
    from bfl_asic.transport.icarus_simulator import SimulatedIcarusTransport
    from bfl_asic.nonce_source import IcarusNonceSource
    from bfl_asic.characterization import characterize_source
    src = IcarusNonceSource(SimulatedIcarusTransport(), _work(30))
    rep = characterize_source(src, count=30, bins=16)
    assert rep["source"] == "icarus-nonce-source"
    assert rep["throughput"]["jobs_completed"] == 30
    assert rep["nonce_distribution"]["n"] == 30
    assert sum(rep["nonce_distribution"]["counts"]) == 30
    assert "hashrate_mhps" in rep["extras"]   # device-specific extra (Option B)
    assert "healthy" in rep["health"]


def test_characterize_source_generalises_to_a_bfl_source():
    from bfl_asic.nonce_source import SimulatedNonceSource
    from bfl_asic.characterization import characterize_source
    rep = characterize_source(SimulatedNonceSource(), count=20, bins=16)
    assert rep["source"] == "simulated-nonce-source"
    assert rep["throughput"]["jobs_completed"] == 20
    assert rep["extras"] == {}   # a BFL source exposes no device-specific extras


# --- Antminer U1/U2 (ANU) frequency control -----------------------------
# Ported from cgminer driver-icarus.c (set_anu_freq / crc5 / anu_find_freqhex).
# Verified by round-trip + structure; byte-exactness confirmed against the U1
# when it arrives.

def test_crc5_is_deterministic_and_5_bits():
    from bfl_asic.protocol.icarus import crc5
    a = crc5(bytes([0x82, 0x03, 0x80, 0x00]), 27)
    b = crc5(bytes([0x82, 0x03, 0x80, 0x00]), 27)
    assert a == b
    assert 0 <= a <= 0x1F           # 5-bit result


def test_crc5_changes_with_input():
    from bfl_asic.protocol.icarus import crc5
    assert crc5(bytes([0x82, 0x00, 0x00, 0]), 27) != \
        crc5(bytes([0x82, 0x0F, 0xF0, 0]), 27)


def test_anu_freq_reg_roundtrips():
    from bfl_asic.protocol.icarus import anu_freq_to_reg, anu_reg_to_freq
    for target in (150, 200, 250, 300, 400, 500):
        reg = anu_freq_to_reg(target)
        assert 0 <= reg <= 0xFFFF
        # PLL can't hit every MHz exactly, but should land within a few MHz.
        assert abs(anu_reg_to_freq(reg) - target) < 5


def test_anu_200mhz_is_exact():
    from bfl_asic.protocol.icarus import anu_freq_to_reg, anu_reg_to_freq
    reg = anu_freq_to_reg(200)
    assert reg == 0x0380           # od=0, n=0, m=7 -> 25*8/1 = 200
    assert anu_reg_to_freq(reg) == 200.0


def test_build_anu_set_freq_layout():
    from bfl_asic.protocol.icarus import build_anu_set_freq, crc5, anu_freq_to_reg
    cmd = build_anu_set_freq(250)
    assert len(cmd) == 4
    assert cmd[0] == 0x82          # write reg 2 (2 | 0x80)
    reg = anu_freq_to_reg(250)
    assert cmd[1] == (reg & 0xFF00) >> 8
    assert cmd[2] == reg & 0x00FF
    # CRC covers the three data bytes + a zero placeholder byte, 27 bits.
    assert cmd[3] == crc5(bytes([cmd[0], cmd[1], cmd[2], 0]), 27)


def test_build_anu_set_freq_defaults_to_u1_default():
    from bfl_asic.protocol.icarus import (
        build_anu_set_freq, anu_reg_to_freq, ANT_U1_DEFFREQ)
    cmd = build_anu_set_freq()     # no target -> ANT_U1_DEFFREQ (200)
    reg = (cmd[1] << 8) | cmd[2]
    assert anu_reg_to_freq(reg) == float(ANT_U1_DEFFREQ)


def test_build_anu_read_freq_layout():
    from bfl_asic.protocol.icarus import build_anu_read_freq, crc5
    cmd = build_anu_read_freq()
    assert len(cmd) == 4
    assert cmd[0] == 0x84          # read reg 4 (4 | 0x80)
    assert cmd[1] == 0x00
    assert cmd[2] == 0x04
    assert cmd[3] == crc5(bytes([0x84, 0x00, 0x04, 0]), 27)


def test_build_anu_set_freq_accepts_raw_reg():
    from bfl_asic.protocol.icarus import build_anu_set_freq
    cmd = build_anu_set_freq(reg=0x0380)
    assert cmd[0] == 0x82 and cmd[1] == 0x03 and cmd[2] == 0x80
