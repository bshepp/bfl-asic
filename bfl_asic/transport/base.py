"""Abstract base class defining the transport interface for BFL device communication.

Both sync and async methods are defined.  The async variants have default
implementations that wrap the sync methods via :func:`asyncio.to_thread`,
so concrete transports only *need* to implement the sync API.  Transports
with native async support (e.g. :class:`SimulatorTransport`) can override
the ``a*`` methods directly.
"""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod


class BaseTransport(ABC):
    """Abstract transport for BFL device communication."""

    # ------------------------------------------------------------------
    # Sync API (must be implemented by subclasses)
    # ------------------------------------------------------------------

    @abstractmethod
    def open(self) -> None:
        """Open the transport connection."""
        ...

    @abstractmethod
    def close(self) -> None:
        """Close the transport connection."""
        ...

    @abstractmethod
    def write(self, data: bytes) -> None:
        """Write *data* to the device."""
        ...

    @abstractmethod
    def read(self, size: int, timeout: float | None = None) -> bytes:
        """Read up to *size* bytes from the device.

        If *timeout* is given it overrides any default for this single call.
        """
        ...

    @abstractmethod
    def readline(self, timeout: float | None = None) -> bytes:
        """Read a line (terminated by newline) from the device.

        If *timeout* is given it overrides any default for this single call.
        """
        ...

    @property
    @abstractmethod
    def is_open(self) -> bool:
        """Whether the transport is currently open."""
        ...

    # ------------------------------------------------------------------
    # Async API (default: delegate to sync via asyncio.to_thread)
    # ------------------------------------------------------------------

    async def aopen(self) -> None:
        """Async variant of :meth:`open`."""
        await asyncio.to_thread(self.open)

    async def aclose(self) -> None:
        """Async variant of :meth:`close`."""
        await asyncio.to_thread(self.close)

    async def awrite(self, data: bytes) -> None:
        """Async variant of :meth:`write`."""
        await asyncio.to_thread(self.write, data)

    async def aread(self, size: int, timeout: float | None = None) -> bytes:
        """Async variant of :meth:`read`."""
        return await asyncio.to_thread(self.read, size, timeout)

    async def areadline(self, timeout: float | None = None) -> bytes:
        """Async variant of :meth:`readline`."""
        return await asyncio.to_thread(self.readline, timeout)

    # ------------------------------------------------------------------
    # Context managers
    # ------------------------------------------------------------------

    def __enter__(self) -> BaseTransport:
        self.open()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:  # noqa: ANN001
        self.close()
        return False

    async def __aenter__(self) -> BaseTransport:
        await self.aopen()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> bool:  # noqa: ANN001
        await self.aclose()
        return False
