"""Data classes and parser functions for BFL ASIC responses.

Every parser takes raw ``bytes`` from the device and returns a typed
data class.  No I/O happens here.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum

from bfl_asic.exceptions import BFLProtocolError


# -------------------------------------------------------------------
# Data classes
# -------------------------------------------------------------------

class WorkStatus(Enum):
    """Possible states returned when polling for work results."""

    BUSY = "busy"
    NO_NONCE = "no_nonce"
    NONCE_FOUND = "nonce_found"
    IDLE = "idle"


@dataclass
class DeviceInfo:
    """Parsed identity response from the device.

    Attributes
    ----------
    model:
        Human-readable model string, e.g.
        ``"BitFORCE SHA256 ASIC Jalapeno 5GH/s"``.
    sha256:
        ``True`` when the response contains ``"SHA256"``.
    raw:
        The original response string (for debugging / logging).
    """

    model: str
    sha256: bool
    raw: str


@dataclass
class TemperatureReading:
    """One or more on-board temperature sensors.

    Attributes
    ----------
    sensors:
        Temperature values in degrees Celsius, ordered by sensor index.
    """

    sensors: list[float]


@dataclass
class WorkResult:
    """Parsed result of a work-poll (ZFX) response.

    Attributes
    ----------
    status:
        One of the :class:`WorkStatus` variants.
    nonces:
        List of 32-bit nonce integers found by the device.  Empty unless
        *status* is :attr:`WorkStatus.NONCE_FOUND`.
    """

    status: WorkStatus
    nonces: list[int] = field(default_factory=list)


# -------------------------------------------------------------------
# Parsers
# -------------------------------------------------------------------

_TEMP_RE = re.compile(r"TEMP\d+:\s*([\d.]+)\s*C", re.IGNORECASE)


def parse_identify(raw: bytes) -> DeviceInfo:
    """Decode an identify (ZGX) response into a :class:`DeviceInfo`.

    Parameters
    ----------
    raw:
        Raw bytes received from the device after sending ZGX.
    """
    text = raw.decode("ascii", errors="replace").strip()
    return DeviceInfo(
        model=text,
        sha256="SHA256" in text.upper(),
        raw=text,
    )


def parse_temperature(raw: bytes) -> TemperatureReading:
    """Parse a temperature (ZTX) response.

    Expected formats::

        TEMP0:45C
        TEMP0:45C\\nTEMP1:43C

    Parameters
    ----------
    raw:
        Raw bytes received from the device.

    Raises
    ------
    BFLProtocolError
        If the response contains no recognisable temperature data.
    """
    text = raw.decode("ascii", errors="replace")
    matches = _TEMP_RE.findall(text)
    if not matches:
        raise BFLProtocolError(
            f"No temperature data found in response: {text!r}"
        )
    return TemperatureReading(sensors=[float(m) for m in matches])


def parse_work_result(raw: bytes) -> WorkResult:
    """Parse a work-poll (ZFX) response.

    Recognised formats:

    * ``B`` or starts with ``B``  -- BUSY
    * ``NO-NONCE``                -- hash space exhausted, no valid nonce
    * ``IDLE``                    -- device is idle
    * ``NONCE-FOUND:<hex>[,<hex>...]`` -- one or more nonces found

    Parameters
    ----------
    raw:
        Raw bytes received from the device.

    Raises
    ------
    BFLProtocolError
        If the response does not match any known format.
    """
    stripped = raw.strip()

    # BUSY -- single 'B' or starts with 'B' (some firmware variants
    # append extra info after the B).
    if stripped == b"B" or stripped.startswith(b"B"):
        # Make sure it isn't accidentally matching "BUSY" text that
        # might be confused with other tokens -- but the BFL firmware
        # sends a literal single 'B' for busy.  We also accept any
        # response starting with 'B' that is NOT one of the other
        # recognised tokens.
        if not stripped.startswith(b"NO-NONCE") and not stripped.startswith(b"NONCE-FOUND") and not stripped.startswith(b"IDLE"):
            return WorkResult(status=WorkStatus.BUSY)

    if stripped == b"NO-NONCE":
        return WorkResult(status=WorkStatus.NO_NONCE)

    if stripped == b"IDLE":
        return WorkResult(status=WorkStatus.IDLE)

    if stripped.startswith(b"NONCE-FOUND"):
        text = stripped.decode("ascii", errors="replace")
        # Format: NONCE-FOUND:<hex>[,<hex>...]
        # The separator between the label and the nonces is ':'
        parts = text.split(":", 1)
        nonces: list[int] = []
        if len(parts) == 2 and parts[1]:
            for hex_str in parts[1].split(","):
                hex_str = hex_str.strip()
                if hex_str:
                    nonces.append(int(hex_str, 16))
        return WorkResult(status=WorkStatus.NONCE_FOUND, nonces=nonces)

    raise BFLProtocolError(
        f"Unrecognised work-result response: {stripped!r}"
    )
