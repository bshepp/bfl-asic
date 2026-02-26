"""Protocol constants for BFL ASIC communication.

Covers serial-port parameters, the wire-level delimiter, command codes,
timing values, and well-known response tokens used by the BF0005G Jalapeno.
"""

# ---------------------------------------------------------------------------
# Serial port configuration
# ---------------------------------------------------------------------------
BAUD_RATE: int = 115200
DATA_BITS: int = 8
STOP_BITS: int = 1
PARITY: str = "N"

# ---------------------------------------------------------------------------
# Wire-level framing
# ---------------------------------------------------------------------------
#: Eight 0x3E bytes ('>') that separate every response from the device.
DELIMITER: bytes = b">>>>>>>>"

# ---------------------------------------------------------------------------
# Command codes  (all 3-byte, leading 'Z')
# ---------------------------------------------------------------------------
CMD_IDENTIFY: bytes = b"ZGX"
CMD_WORK: bytes = b"ZDX"
CMD_RESULT: bytes = b"ZFX"
CMD_TEMP: bytes = b"ZTX"
CMD_NONCE_RANGE: bytes = b"ZPX"

# ---------------------------------------------------------------------------
# Timing (seconds)
# ---------------------------------------------------------------------------
POLL_INTERVAL: float = 0.5
WORK_TIMEOUT: float = 7.0
THROTTLE_DELAY: float = 2.5

# ---------------------------------------------------------------------------
# Response tokens
# ---------------------------------------------------------------------------
RESP_BUSY: bytes = b"B"
RESP_NO_NONCE: bytes = b"NO-NONCE"
RESP_NONCE_FOUND: bytes = b"NONCE-FOUND"
RESP_OK: bytes = b"OK"
RESP_IDLE: bytes = b"IDLE"
