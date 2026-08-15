"""Tests for the undocumented-command probe protocol (ZJX/ZUX/ZSX).

These three commands are defined in cgminer's driver-bflsc.h but never
sent by it, so their reply formats are UNVERIFIED against hardware. The
builders are grounded in the header (bare queries; ZSX uses the
SaveString struct = payloadSize byte + payload). The parsers are
deliberately lenient and preserve the raw reply.
"""
from __future__ import annotations

import pytest

from bfl_asic.protocol.probe import (
    FirmwareInfo,
    build_firmware,
    build_loadstr,
    build_savestr,
    parse_firmware,
    parse_loadstr,
    parse_savestr_ack,
)


def test_build_firmware_is_bare_zjx():
    assert build_firmware() == b"ZJX"


def test_build_loadstr_is_bare_zux():
    assert build_loadstr() == b"ZUX"


def test_build_savestr_length_prefixes_payload():
    # SaveString struct: ZSX + payloadSize(1) + payload
    assert build_savestr(b"hi") == b"ZSX" + bytes([2]) + b"hi"


def test_build_savestr_empty_payload():
    assert build_savestr(b"") == b"ZSX" + bytes([0])


def test_build_savestr_accepts_str():
    assert build_savestr("hi") == b"ZSX" + bytes([2]) + b"hi"


def test_build_savestr_rejects_overlong_payload():
    with pytest.raises(ValueError):
        build_savestr(b"x" * 256)


def test_parse_firmware_lenient_keyvalue():
    fw = parse_firmware(b"FIRMWARE: 1.0.0\nBOOTLOADER: 1.0\nOK\n")
    assert isinstance(fw, FirmwareInfo)
    assert fw.fields["FIRMWARE"] == "1.0.0"
    assert fw.fields["BOOTLOADER"] == "1.0"


def test_parse_firmware_preserves_unknown_text():
    # Unknown/undocumented reply must never be dropped.
    fw = parse_firmware(b"anything the firmware says\nOK\n")
    assert "anything the firmware says" in fw.text
    assert fw.raw == b"anything the firmware says\nOK\n"


def test_parse_loadstr_returns_stored_string():
    assert parse_loadstr(b"hello world\nOK\n") == "hello world"


def test_parse_loadstr_empty_when_no_payload():
    assert parse_loadstr(b"OK\n") == ""


def test_parse_loadstr_memory_empty_sentinel():
    # Real hardware returns "MEMORY EMPTY" for a blank scratchpad; that
    # sentinel means empty, not a stored value.
    assert parse_loadstr(b"MEMORY EMPTY\n") == ""
    assert parse_loadstr(b"memory empty") == ""


def test_firmware_version_from_bare_reply():
    # Real ZJX returns a bare version string, no KEY:VALUE, no OK.
    assert parse_firmware(b"1.0.0").version == "1.0.0"


def test_firmware_version_from_keyvalue_reply():
    assert parse_firmware(b"FIRMWARE: 1.0.0\nOK\n").version == "1.0.0"


def test_firmware_version_none_when_empty():
    assert parse_firmware(b"OK\n").version is None


def test_parse_savestr_ack_true_on_ok():
    assert parse_savestr_ack(b"OK\n") is True
    assert parse_savestr_ack(b"SUCCESS\n") is True


def test_parse_savestr_ack_false_on_err():
    assert parse_savestr_ack(b"ERR:whatever\n") is False
    assert parse_savestr_ack(b"") is False
