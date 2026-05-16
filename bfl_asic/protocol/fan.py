"""Pure fan-control command builders for the BFL SC firmware.

cgminer driver-bflsc only ever sends Z9X (auto) and Z4X (max) in
practice; Z0X-Z3X are firmware-defined but their per-level behavior is
hardware-unconfirmed. The ack token is not pinned by the reference
(cgminer just reads one line) — parse_fan_ack is deliberately tolerant.
"""
from __future__ import annotations

from bfl_asic.protocol.constants import CMD_FAN_AUTO, CMD_FAN_LEVELS, RESP_ERR


def build_fan_auto() -> bytes:
    """`Z9X` — hand the fan back to firmware thermal management."""
    return CMD_FAN_AUTO


def build_fan_level(level: int) -> bytes:
    """`Z0X`..`Z4X` — set a fixed fan level (0..4)."""
    if not isinstance(level, int) or not 0 <= level <= 4:
        raise ValueError(f"fan level must be an int in 0..4, got {level!r}")
    return CMD_FAN_LEVELS[level]


def parse_fan_ack(raw: bytes) -> bool:
    """True if the device acked; False on empty or an ERR: reply."""
    s = raw.strip()
    if not s:
        return False
    return not s.startswith(RESP_ERR)
