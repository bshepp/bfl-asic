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
