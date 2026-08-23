"""Tests for the Govee H5075 ambient-sensor decoder.

Pure decode only (no BLE): the ``bleak`` reader needs a real sensor, which
isn't in hand yet -- byte offsets get validated against hardware on arrival.
The packing is cgminer-independent, from the community H5075 decoder.
"""
from __future__ import annotations

import pytest

from bfl_asic.ambient import (
    H5075_COMPANY_ID, H5075Reading, decode_h5075, decode_h5075_from_mfg,
    decode_h5075_packet,
)


def test_company_id():
    assert H5075_COMPANY_ID == 0xEC88


def test_decode_packet_positive():
    # 250500 -> temp 25.05 C, humidity 50.0 %
    temp_c, humidity = decode_h5075_packet(250500)
    assert temp_c == pytest.approx(25.05)
    assert humidity == pytest.approx(50.0)


def test_decode_packet_negative_temp():
    # sign bit set over value 30400 -> -3.04 C, humidity 40.0 %
    packet = 0x800000 | 30400
    temp_c, humidity = decode_h5075_packet(packet)
    assert temp_c == pytest.approx(-3.04)
    assert humidity == pytest.approx(40.0)   # sign bit stripped first


def test_decode_mfg_payload():
    # bleak hands back [0x00, b1, b2, b3, battery, ...] for company 0xEC88.
    payload = b"\x00" + (250500).to_bytes(3, "big") + bytes([87])
    r = decode_h5075(payload)
    assert isinstance(r, H5075Reading)
    assert r.temp_c == pytest.approx(25.05)
    assert r.humidity == pytest.approx(50.0)
    assert r.battery == 87


def test_reading_temp_f():
    r = H5075Reading(temp_c=25.0, humidity=50.0, battery=90)
    assert r.temp_f == pytest.approx(77.0)


def test_decode_payload_too_short_raises():
    with pytest.raises(ValueError):
        decode_h5075(b"\x00\x01\x02")   # 3 bytes, need >= 5


def test_decode_from_mfg_dict_selects_company():
    payload = b"\x00" + (205304).to_bytes(3, "big") + bytes([55])
    r = decode_h5075_from_mfg({H5075_COMPANY_ID: payload})
    assert r is not None and r.battery == 55
    # An advertisement without the H5075 company id yields None.
    assert decode_h5075_from_mfg({0x004C: b"\xde\xad\xbe\xef\x00"}) is None
