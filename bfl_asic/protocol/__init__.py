"""Protocol definitions for the BFL ASIC command set.

Submodules
----------
commands
    Pure functions that build command byte sequences.
responses
    Data classes and parser functions for device responses.
work
    Work-unit construction and SHA-256 midstate computation.
constants
    Wire-level constants (delimiter, command codes, timing, etc.).
"""

from bfl_asic.protocol.commands import (
    build_identify,
    build_nonce_range,
    build_poll,
    build_temperature,
    build_work,
)
from bfl_asic.protocol.responses import (
    DeviceInfo,
    TemperatureReading,
    WorkResult,
    WorkStatus,
    parse_identify,
    parse_temperature,
    parse_work_result,
)
from bfl_asic.protocol.work import (
    build_block_header,
    build_synthetic_work,
    compute_midstate,
)

__all__ = [
    # commands
    "build_identify",
    "build_nonce_range",
    "build_poll",
    "build_temperature",
    "build_work",
    # responses
    "DeviceInfo",
    "TemperatureReading",
    "WorkResult",
    "WorkStatus",
    "parse_identify",
    "parse_temperature",
    "parse_work_result",
    # work
    "build_block_header",
    "build_synthetic_work",
    "compute_midstate",
]
