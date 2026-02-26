"""High-level synchronous interface to a BFL ASIC device.

Combines the transport and protocol layers into a clean API for
applications.  Use :class:`BFLDevice` as a context manager to
automatically open and close the underlying transport.
"""

from __future__ import annotations

import struct
import time

from bfl_asic.exceptions import BFLTimeoutError
from bfl_asic.protocol.commands import (
    build_identify,
    build_poll,
    build_temperature,
    build_work,
)
from bfl_asic.protocol.constants import POLL_INTERVAL, WORK_TIMEOUT
from bfl_asic.protocol.responses import (
    DeviceInfo,
    TemperatureReading,
    WorkResult,
    WorkStatus,
    parse_identify,
    parse_temperature,
    parse_work_result,
)
from bfl_asic.protocol.work import build_synthetic_work
from bfl_asic.transport.base import BaseTransport


class BFLDevice:
    """High-level synchronous interface to a BFL ASIC device."""

    def __init__(self, transport: BaseTransport) -> None:
        self._transport = transport

    def identify(self) -> DeviceInfo:
        """Query device identification (ZGX command)."""
        self._transport.write(build_identify())
        raw = self._transport.readline()
        return parse_identify(raw)

    def get_temperature(self) -> TemperatureReading:
        """Query device temperature (ZTX command)."""
        self._transport.write(build_temperature())
        raw = self._transport.readline()
        return parse_temperature(raw)

    def submit_work(self, midstate: bytes, tail: bytes) -> None:
        """Submit a work unit to the device (ZDX command).

        Reads and discards the 'OK' acknowledgment.
        """
        self._transport.write(build_work(midstate, tail))
        self._transport.readline()  # Read OK response

    def poll_result(self) -> WorkResult:
        """Poll for work results (ZFX command)."""
        self._transport.write(build_poll())
        raw = self._transport.readline()
        return parse_work_result(raw)

    def submit_and_wait(
        self,
        midstate: bytes,
        tail: bytes,
        timeout: float = WORK_TIMEOUT,
        poll_interval: float = POLL_INTERVAL,
    ) -> WorkResult:
        """Submit work and poll until a result is ready.

        Args:
            midstate: 32-byte SHA-256 midstate
            tail: 12-byte block tail
            timeout: Maximum time to wait in seconds
            poll_interval: Time between polls in seconds

        Returns:
            WorkResult with status NONCE_FOUND or NO_NONCE

        Raises:
            BFLTimeoutError: If no result within timeout
        """
        self.submit_work(midstate, tail)
        deadline = time.monotonic() + timeout

        while time.monotonic() < deadline:
            result = self.poll_result()
            if result.status != WorkStatus.BUSY:
                return result
            time.sleep(poll_interval)

        raise BFLTimeoutError(f"No result within {timeout}s")

    def hash_data(self, data: bytes) -> list[int]:
        """Submit synthetic work derived from data and return found nonces.

        This is a convenience method for non-mining applications.
        Constructs a work unit from the input data and returns any nonces found.
        """
        midstate, tail = build_synthetic_work(
            data[:64].ljust(64, b"\x00") if data else None
        )
        result = self.submit_and_wait(midstate, tail)
        return result.nonces

    def generate_entropy(self, num_bytes: int) -> bytes:
        """Generate random bytes by collecting nonces from multiple work units.

        Submits work units and collects found nonces as entropy.
        Each nonce provides 4 bytes of entropy.

        Args:
            num_bytes: Number of random bytes to generate

        Returns:
            bytes of length num_bytes
        """
        entropy = b""
        counter = 0
        while len(entropy) < num_bytes:
            seed = struct.pack(">Q", counter)
            midstate, tail = build_synthetic_work(seed.ljust(64, b"\x00"))
            result = self.submit_and_wait(midstate, tail)
            for nonce in result.nonces:
                entropy += nonce.to_bytes(4, "big")
            # Even if no nonces found, use the tail bytes as fallback entropy
            if not result.nonces:
                entropy += tail
            counter += 1

        return entropy[:num_bytes]

    # Context manager
    def __enter__(self) -> BFLDevice:
        self._transport.open()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:  # noqa: ANN001
        self._transport.close()
        return False

    @property
    def transport(self) -> BaseTransport:
        """Access the underlying transport."""
        return self._transport
