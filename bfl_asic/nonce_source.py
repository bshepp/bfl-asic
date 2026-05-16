"""Honest device-backed nonce stream.

This is deliberately NOT a `bfl_asic.stats.engine.HashSource`. The BFL
device only ever returns winning *nonces*, never SHA-256d digests, so it
cannot feed the digest pipelines (stats/randomness/ml). A NonceSource
yields work-results (nonces) at sustained hardware rate via the queued
path -- useful for proof-of-work / hashrate work, nothing dressed up.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Iterator

from bfl_asic.protocol.queued import QueuedResult


class NonceSource(ABC):
    """Anything that yields device-found nonce results."""

    @abstractmethod
    def results(self, count: int | None = None,
                duration: float | None = None) -> Iterator[QueuedResult]:
        """Yield device-found nonce results.

        Termination contract: at least one of *count*, *duration*, or a
        finite ``work_iter`` must bound the run. With *count* and
        *duration* both None over an infinite work iterator this
        generator never terminates.
        """
        ...

    @abstractmethod
    def name(self) -> str:
        ...


class SimulatedNonceSource(NonceSource):
    """In-process nonce stream backed by the simulator queued path."""

    def __init__(self, simulated_hashrate: int = 64) -> None:
        self._hr = simulated_hashrate

    def results(self, count: int | None = None,
                duration: float | None = None) -> Iterator[QueuedResult]:
        from bfl_asic.transport.simulator import (
            SimulatorTransport, SimulatedDevice)
        from bfl_asic.device import QueuedWorkSession
        n = count if count is not None else 100
        t = SimulatorTransport(SimulatedDevice(simulated_hashrate=self._hr))
        t.open()

        def work():
            for i in range(n):
                yield (bytes([i % 256]) * 32, bytes([i % 256]) * 12)

        try:
            with QueuedWorkSession(t) as s:
                yield from s.run(work_iter=work(), max_jobs=n,
                                 duration=duration)
        finally:
            t.close()

    def name(self) -> str:
        return "simulated-nonce-source"


class DeviceNonceSource(NonceSource):
    """Real-hardware nonce stream via a QueuedWorkSession over
    *transport*. The caller owns *transport* (this class does not close
    it). See NonceSource.results for the termination contract.
    """

    def __init__(self, transport, work_iter) -> None:
        self._transport = transport
        self._work = work_iter

    def results(self, count: int | None = None,
                duration: float | None = None) -> Iterator[QueuedResult]:
        from bfl_asic.device import QueuedWorkSession
        with QueuedWorkSession(self._transport) as s:
            yield from s.run(work_iter=self._work, max_jobs=count,
                             duration=duration)

    def name(self) -> str:
        return "device-nonce-source"
