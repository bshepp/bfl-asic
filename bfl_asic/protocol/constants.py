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
CMD_TEMP: bytes = b"ZLX"       # SC firmware uses ZLX for temperature
CMD_VOLTAGE: bytes = b"ZTX"    # SC firmware uses ZTX for voltages
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

# ---------------------------------------------------------------------------
# SC queued-work protocol (additive; naive ZDX/ZFX path is unchanged)
# Byte facts from cgminer driver-bflsc.h (GPLv3 reference; not copied).
# ---------------------------------------------------------------------------
CMD_QJOB: bytes = b"ZNX"        # queue one job
CMD_QJOBS: bytes = b"ZWX"       # queue a job pack (<=5)
CMD_QRESULTS: bytes = b"ZOX"    # query/drain results (frees queue slots)
CMD_QFLUSH: bytes = b"ZQX"      # flush the queue
CMD_DETAILS: bytes = b"ZCX"     # device details (incl. JOBS IN QUEUE)

CMD_FAN_AUTO: bytes = b"Z9X"
CMD_FAN_LEVELS: tuple[bytes, ...] = (b"Z0X", b"Z1X", b"Z2X", b"Z3X", b"Z4X")

EOB: int = 0xAA          # end-of-block marker in a queued job
SIGNATURE: int = 0xC1    # job-pack signature byte
EOW: int = 0xFE          # end-of-wrapper marker in a job pack
QUE_MAX_RESULTS: int = 8           # max results returned per ZOX read
QJOB_PAYLOAD_SIZE: int = 45        # midstate(32)+blockdata(12)+EOB(1)

RESP_SUCCESS: bytes = b"SUCCESS"
RESP_COUNT: bytes = b"COUNT:"
RESP_ERR: bytes = b"ERR:"
