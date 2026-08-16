"""Tests for the ZVX/ZKX frequency-factor commands.

Grounded in the open firmware (luke-jr/BitForce_SC): ZKX returns
`FREQ:<n>` (unimplemented there -> 0); ZVX is double-stage (command, then
4 payload bytes little-endian, masked to 16 bits) and writes ASIC osc
register 0x60. Only the firmware's 10 known-good words are treated as safe.
"""
from __future__ import annotations

import pytest

from bfl_asic.protocol.freq import (
    ASIC_FREQUENCY_WORDS,
    build_get_freq_factor,
    build_set_freq_factor,
    is_known_word,
    parse_freq_factor,
)


def test_get_freq_is_bare_zkx():
    assert build_get_freq_factor() == b"ZKX"


def test_set_freq_returns_command_and_length_prefixed_payload():
    cmd, payload = build_set_freq_factor(0xD555)
    assert cmd == b"ZVX"
    # length-prefixed: [0x04][4 bytes LE]; firmware masks to 16 bits
    assert payload == bytes([0x04, 0x55, 0xD5, 0x00, 0x00])
    assert len(payload) == 5
    assert payload[0] == 4  # length indicator


def test_set_freq_rejects_out_of_range_word():
    with pytest.raises(ValueError):
        build_set_freq_factor(0x1FFFF)
    with pytest.raises(ValueError):
        build_set_freq_factor(-1)


def test_known_word_table_matches_firmware():
    # Exact table from BitForce_SC std_defs.c, slow -> fast.
    assert ASIC_FREQUENCY_WORDS == (
        0x0000, 0xFFFF, 0xFFFD, 0xFFF5, 0xFFD5,
        0xFF55, 0xFD55, 0xF555, 0xD555, 0x5555)
    assert is_known_word(0xD555)
    assert not is_known_word(0x1234)


def test_parse_freq_factor():
    assert parse_freq_factor(b"FREQ:0\n") == 0
    assert parse_freq_factor(b"FREQ:227\n") == 227
    assert parse_freq_factor(b"OK\n") is None


def test_simulator_set_get_freq_roundtrip():
    from bfl_asic.transport.simulator import SimulatedDevice
    d = SimulatedDevice()
    assert parse_freq_factor(d.process_command(b"ZKX")) == 0     # default
    cmd, payload = build_set_freq_factor(0xD555)
    assert d.process_command(cmd) == b"OK\n"                     # stage 1
    assert d.process_command(payload) == b"OK\n"                 # stage 2
    assert parse_freq_factor(d.process_command(b"ZKX")) == 0xD555
