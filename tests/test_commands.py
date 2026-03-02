"""Tests for bfl_asic.protocol.commands."""

import struct

import pytest

from bfl_asic.protocol.commands import (
    build_identify,
    build_nonce_range,
    build_poll,
    build_temperature,
    build_voltage,
    build_work,
)
from bfl_asic.protocol.constants import DELIMITER


# -------------------------------------------------------------------
# Simple command builders
# -------------------------------------------------------------------

class TestBuildIdentify:
    def test_returns_zgx(self):
        assert build_identify() == b"ZGX"

    def test_type_is_bytes(self):
        assert isinstance(build_identify(), bytes)


class TestBuildTemperature:
    def test_returns_zlx(self):
        assert build_temperature() == b"ZLX"


class TestBuildVoltage:
    def test_returns_ztx(self):
        assert build_voltage() == b"ZTX"


class TestBuildPoll:
    def test_returns_zfx(self):
        assert build_poll() == b"ZFX"


# -------------------------------------------------------------------
# build_work
# -------------------------------------------------------------------

class TestBuildWork:
    def setup_method(self):
        self.midstate = bytes(range(32))
        self.tail = bytes(range(12))

    def test_length_is_60(self):
        pkt = build_work(self.midstate, self.tail)
        assert len(pkt) == 60

    def test_starts_with_delimiter(self):
        pkt = build_work(self.midstate, self.tail)
        assert pkt[:8] == DELIMITER

    def test_ends_with_delimiter(self):
        pkt = build_work(self.midstate, self.tail)
        assert pkt[52:60] == DELIMITER

    def test_midstate_in_correct_position(self):
        pkt = build_work(self.midstate, self.tail)
        assert pkt[8:40] == self.midstate

    def test_tail_in_correct_position(self):
        pkt = build_work(self.midstate, self.tail)
        assert pkt[40:52] == self.tail

    def test_rejects_short_midstate(self):
        with pytest.raises(ValueError, match="midstate"):
            build_work(b"\x00" * 31, self.tail)

    def test_rejects_long_midstate(self):
        with pytest.raises(ValueError, match="midstate"):
            build_work(b"\x00" * 33, self.tail)

    def test_rejects_short_tail(self):
        with pytest.raises(ValueError, match="tail"):
            build_work(self.midstate, b"\x00" * 11)

    def test_rejects_long_tail(self):
        with pytest.raises(ValueError, match="tail"):
            build_work(self.midstate, b"\x00" * 13)

    def test_rejects_empty_midstate(self):
        with pytest.raises(ValueError, match="midstate"):
            build_work(b"", self.tail)

    def test_rejects_empty_tail(self):
        with pytest.raises(ValueError, match="tail"):
            build_work(self.midstate, b"")


# -------------------------------------------------------------------
# build_nonce_range
# -------------------------------------------------------------------

class TestBuildNonceRange:
    def setup_method(self):
        self.midstate = bytes(range(32))
        self.tail = bytes(range(12))

    def test_length_is_68(self):
        pkt = build_nonce_range(self.midstate, self.tail, 0, 0xFFFFFFFF)
        assert len(pkt) == 68

    def test_first_60_bytes_match_build_work(self):
        pkt = build_nonce_range(self.midstate, self.tail, 0, 0xFFFFFFFF)
        work = build_work(self.midstate, self.tail)
        assert pkt[:60] == work

    def test_start_nonce_encoded_big_endian(self):
        pkt = build_nonce_range(self.midstate, self.tail, 0x01020304, 0)
        assert pkt[60:64] == b"\x01\x02\x03\x04"

    def test_end_nonce_encoded_big_endian(self):
        pkt = build_nonce_range(self.midstate, self.tail, 0, 0xAABBCCDD)
        assert pkt[64:68] == b"\xAA\xBB\xCC\xDD"

    def test_zero_nonces(self):
        pkt = build_nonce_range(self.midstate, self.tail, 0, 0)
        assert pkt[60:64] == b"\x00\x00\x00\x00"
        assert pkt[64:68] == b"\x00\x00\x00\x00"

    def test_max_nonces(self):
        pkt = build_nonce_range(self.midstate, self.tail, 0xFFFFFFFF, 0xFFFFFFFF)
        assert pkt[60:64] == b"\xFF\xFF\xFF\xFF"
        assert pkt[64:68] == b"\xFF\xFF\xFF\xFF"

    def test_rejects_negative_start(self):
        with pytest.raises(ValueError, match="start nonce"):
            build_nonce_range(self.midstate, self.tail, -1, 0)

    def test_rejects_start_too_large(self):
        with pytest.raises(ValueError, match="start nonce"):
            build_nonce_range(self.midstate, self.tail, 0x100000000, 0)

    def test_rejects_negative_end(self):
        with pytest.raises(ValueError, match="end nonce"):
            build_nonce_range(self.midstate, self.tail, 0, -1)

    def test_rejects_end_too_large(self):
        with pytest.raises(ValueError, match="end nonce"):
            build_nonce_range(self.midstate, self.tail, 0, 0x100000000)

    def test_validates_midstate_length(self):
        with pytest.raises(ValueError, match="midstate"):
            build_nonce_range(b"\x00" * 31, self.tail, 0, 0)

    def test_validates_tail_length(self):
        with pytest.raises(ValueError, match="tail"):
            build_nonce_range(self.midstate, b"\x00" * 11, 0, 0)
