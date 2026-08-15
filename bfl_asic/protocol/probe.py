"""Builders + parsers for the undocumented BFL probe commands.

``ZJX`` (FIRMWARE), ``ZUX`` (LOADSTR) and ``ZSX`` (SAVESTR) are defined
in cgminer's ``driver-bflsc.h`` but that driver never actually sends
them, so **their reply formats are unverified against real hardware.**
The builders are grounded in the header: ``ZJX``/``ZUX`` are bare
3-byte queries; ``ZSX`` carries a ``SaveString`` struct
(``payloadSize`` byte followed by up to 255 payload bytes).

The parsers are intentionally lenient and always preserve the raw reply
so a real device's undocumented output is never silently dropped. Refine
them only once a real capture (see ``scripts/hw/probe_commands.py``)
tells us what the firmware actually returns.

No I/O happens here.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from bfl_asic.protocol.constants import (
    CMD_FIRMWARE, CMD_LOADSTR, CMD_SAVESTR, SAVESTR_MAX,
)


def build_firmware() -> bytes:
    """`ZJX` — firmware-info query (bare 3-byte command)."""
    return CMD_FIRMWARE


def build_loadstr() -> bytes:
    """`ZUX` — read back the NVRAM scratch string (bare 3-byte command)."""
    return CMD_LOADSTR


def build_savestr(payload: bytes | str) -> bytes:
    """`ZSX` + SaveString(payloadSize, payloadData).

    WRITES device non-volatile storage. The wire framing (a single
    length byte then the payload) is grounded in the header struct, but
    the device's handling is unverified — treat with care and prefer a
    write-then-``ZUX``-read-back round-trip to confirm.
    """
    if isinstance(payload, str):
        payload = payload.encode("ascii")
    if len(payload) > SAVESTR_MAX:
        raise ValueError(
            f"savestr payload must be <= {SAVESTR_MAX} bytes, "
            f"got {len(payload)}")
    return CMD_SAVESTR + bytes([len(payload)]) + payload


@dataclass
class FirmwareInfo:
    """Lenient parse of a `ZJX` reply. Format unverified; raw preserved."""

    raw: bytes = b""
    fields: dict[str, str] = field(default_factory=dict)

    @property
    def text(self) -> str:
        """The reply decoded as text (framing/OK not stripped)."""
        return self.raw.decode("ascii", errors="replace")

    @property
    def version(self) -> str | None:
        """Firmware version string.

        Real hardware answers ``ZJX`` with a bare version (e.g.
        ``1.0.0``); some builds may instead use a ``FIRMWARE: <ver>``
        line. Prefer the labelled field, else fall back to the first
        payload line.
        """
        for k, v in self.fields.items():
            if k.strip().upper() == "FIRMWARE":
                return v
        lines = _payload_lines(self.raw)
        return lines[0] if lines else None


def _payload_lines(raw: bytes) -> list[str]:
    """Text lines with framing / OK / SUCCESS / empty lines removed."""
    out: list[str] = []
    for line in raw.decode("ascii", errors="replace").splitlines():
        s = line.strip()
        if not s or s in ("OK", "SUCCESS") or s.startswith(">>>>>>>>"):
            continue
        out.append(s)
    return out


def parse_firmware(raw: bytes) -> FirmwareInfo:
    """Parse a `ZJX` firmware reply leniently.

    Any ``KEY: VALUE`` lines are captured into ``fields``; the full raw
    reply is always retained for inspection.
    """
    fields: dict[str, str] = {}
    for s in _payload_lines(raw):
        if ":" in s:
            key, _, val = s.partition(":")
            fields[key.strip()] = val.strip()
    return FirmwareInfo(raw=raw, fields=fields)


def parse_loadstr(raw: bytes) -> str:
    """Parse a `ZUX` reply into the stored scratch string.

    Returns the payload with framing/OK stripped; empty string if the
    device stored nothing. Real hardware reports an empty scratchpad with
    the sentinel ``MEMORY EMPTY`` (observed on firmware 1.0.0), which is
    mapped to ``""``.
    """
    payload = "\n".join(_payload_lines(raw))
    if payload.strip().upper() == "MEMORY EMPTY":
        return ""
    return payload


def parse_savestr_ack(raw: bytes) -> bool:
    """True if a `ZSX` reply acknowledges (OK/SUCCESS), False otherwise."""
    for s in raw.decode("ascii", errors="replace").splitlines():
        t = s.strip()
        if t in ("OK", "SUCCESS"):
            return True
        if t.startswith("ERR:"):
            return False
    return False
