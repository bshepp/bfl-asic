"""Exception hierarchy for the bfl_asic package.

Every package-specific exception inherits from :class:`BFLError` so callers
can use a single ``except BFLError`` clause to catch all failures originating
from this library.
"""


class BFLError(Exception):
    """Base exception for all BFL ASIC errors."""


class BFLConnectionError(BFLError):
    """Transport-level failure (port not found, cable disconnected, etc.)."""


class BFLProtocolError(BFLError):
    """Unexpected response format from the device."""


class BFLTimeoutError(BFLError):
    """A work submission or response exceeded its deadline."""


class BFLDeviceError(BFLError):
    """Device-reported error (overheated, hardware fault, etc.)."""


class ThermalSafetyWarning(UserWarning):
    """A manual FIXED fan level was set, overriding firmware thermal
    management. A low/off fan during hashing can physically damage the
    ASIC. Subclasses UserWarning so it still matches broad capture, but
    is a named category so it cannot be silenced by an unrelated
    UserWarning filter.
    """


class NVRAMWriteWarning(UserWarning):
    """A ZSX (SAVESTR) command is about to write the device's persistent
    non-volatile scratch storage. Low-risk versus fan/flash, but it
    mutates on-device state and the command's handling is unverified
    against hardware, so the write is surfaced rather than silent.
    """
