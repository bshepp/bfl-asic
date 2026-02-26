"""High-level asynchronous interface to a BFL ASIC device.

Combines the transport and protocol layers into a clean async API for
applications.  Use :class:`AsyncBFLDevice` as an async context manager
to automatically open and close the underlying transport.
"""

from __future__ import annotations

import asyncio
import struct
from typing import AsyncIterator

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


class AsyncBFLDevice:
    """High-level asynchronous interface to a BFL ASIC device."""

    def __init__(self, transport: BaseTransport) -> None:
        self._transport = transport

    async def identify(self) -> DeviceInfo:
        """Query device identification (ZGX command)."""
        await self._transport.awrite(build_identify())
        raw = await self._transport.areadline()
        return parse_identify(raw)

    async def get_temperature(self) -> TemperatureReading:
        """Query device temperature (ZTX command)."""
        await self._transport.awrite(build_temperature())
        raw = await self._transport.areadline()
        return parse_temperature(raw)

    async def submit_work(self, midstate: bytes, tail: bytes) -> None:
        """Submit a work unit to the device (ZDX command).

        Reads and discards the 'OK' acknowledgment.
        """
        await self._transport.awrite(build_work(midstate, tail))
        await self._transport.areadline()  # OK response

    async def poll_result(self) -> WorkResult:
        """Poll for work results (ZFX command)."""
        await self._transport.awrite(build_poll())
        raw = await self._transport.areadline()
        return parse_work_result(raw)

    async def submit_and_wait(
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
        await self.submit_work(midstate, tail)
        loop = asyncio.get_event_loop()
        deadline = loop.time() + timeout

        while loop.time() < deadline:
            result = await self.poll_result()
            if result.status != WorkStatus.BUSY:
                return result
            await asyncio.sleep(poll_interval)

        raise BFLTimeoutError(f"No result within {timeout}s")

    async def hash_stream(
        self,
        count: int | None = None,
    ) -> AsyncIterator[WorkResult]:
        """Continuously submit work and yield results.

        Args:
            count: Number of work units to process (None = infinite)

        Yields:
            WorkResult for each completed work unit
        """
        i = 0
        while count is None or i < count:
            seed = struct.pack(">Q", i)
            midstate, tail = build_synthetic_work(seed.ljust(64, b"\x00"))
            result = await self.submit_and_wait(midstate, tail)
            yield result
            i += 1

    async def entropy_stream(self, chunk_size: int = 32) -> AsyncIterator[bytes]:
        """Continuously generate entropy bytes.

        Args:
            chunk_size: Number of bytes per yielded chunk

        Yields:
            bytes chunks of entropy
        """
        buffer = b""
        counter = 0
        while True:
            seed = struct.pack(">Q", counter)
            midstate, tail = build_synthetic_work(seed.ljust(64, b"\x00"))
            result = await self.submit_and_wait(midstate, tail)
            for nonce in result.nonces:
                buffer += nonce.to_bytes(4, "big")
            if not result.nonces:
                buffer += tail
            counter += 1

            while len(buffer) >= chunk_size:
                yield buffer[:chunk_size]
                buffer = buffer[chunk_size:]

    async def __aenter__(self) -> AsyncBFLDevice:
        await self._transport.aopen()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> bool:  # noqa: ANN001
        await self._transport.aclose()
        return False

    @property
    def transport(self) -> BaseTransport:
        """Access the underlying transport."""
        return self._transport
