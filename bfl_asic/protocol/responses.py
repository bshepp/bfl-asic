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
class VoltageReading:
    """On-board voltage readings from ZTX command.

    SC firmware returns three voltages as millivolt integers.

    Attributes
    ----------
    vcc1:
        Core voltage in volts (typically ~3.3V).
    vcc2:
        Secondary voltage in volts (typically ~1.0V).
    vmain:
        Main supply voltage in volts (typically ~12V).
    raw:
        Original raw millivolt integers for debugging.
    """

    vcc1: float
    vcc2: float
    vmain: float
    raw: list[int]


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

_TEMP_LABELLED_RE = re.compile(r"TEMP\d+:\s*([\d.]+)\s*C", re.IGNORECASE)
_TEMP_SC_RE = re.compile(r"Temp\d+:\s*(\d+)", re.IGNORECASE)
_RAW_CSV_RE = re.compile(r"^[\d,\s]+$")


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
    """Parse a temperature (ZLX) response.

    Handles two firmware formats:

    1. SC firmware: ``Temp1: 30, Temp2: 30`` — integer °C values.
    2. Older labelled: ``TEMP0:45C`` or ``TEMP0:45C\\nTEMP1:43C``

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

    # Try labelled format first — more specific (has trailing "C")
    matches = _TEMP_LABELLED_RE.findall(text)
    if matches:
        return TemperatureReading(sensors=[float(m) for m in matches])

    # Try SC format (e.g. "Temp1: 30, Temp2: 30") — integer values
    matches = _TEMP_SC_RE.findall(text)
    if matches:
        return TemperatureReading(sensors=[float(m) for m in matches])

    raise BFLProtocolError(
        f"No temperature data found in response: {text!r}"
    )


def parse_voltage(raw: bytes) -> VoltageReading:
    """Parse a voltage (ZTX) response.

    SC firmware returns three comma-separated millivolt integers::

        3564,1011,11420

    These represent VCC1, VCC2, and VMAIN respectively.

    Parameters
    ----------
    raw:
        Raw bytes received from the device.

    Raises
    ------
    BFLProtocolError
        If the response cannot be parsed as voltage data.
    """
    text = raw.decode("ascii", errors="replace").strip()
    if not _RAW_CSV_RE.match(text):
        raise BFLProtocolError(
            f"Unrecognised voltage response: {text!r}"
        )
    values = [v.strip() for v in text.split(",") if v.strip()]
    if len(values) < 3:
        raise BFLProtocolError(
            f"Expected 3 voltage values, got {len(values)}: {text!r}"
        )
    raw_mv = [int(v) for v in values[:3]]
    return VoltageReading(
        vcc1=raw_mv[0] / 1000.0,
        vcc2=raw_mv[1] / 1000.0,
        vmain=raw_mv[2] / 1000.0,
        raw=raw_mv,
    )


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
