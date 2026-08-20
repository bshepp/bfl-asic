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

    def extra_metrics(self) -> dict:
        """Device-specific metrics from the consumed stream (default: none).

        The Option-B hook: the common characteriser computes device-agnostic
        metrics (throughput, nonce histogram, dead-core health); a source
        overrides this to add its own natural numbers -- e.g. an Icarus
        source's linear-scan hashrate. Meaningful only after ``results()``
        has been consumed.
        """
        return {}


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


class IcarusNonceSource(NonceSource):
    """Nonce stream from an Icarus device (Block Erupter class) over
    *transport*, driving the write-64-byte-work / read-4-byte-nonce loop.

    ``work_iter`` yields ``(midstate, data)`` pairs (32 B, 12 B); each is
    turned into a 64-byte Icarus work unit. The caller owns *transport* (this
    class opens it if needed but does not close it). The linear-scan hashrate
    is accumulated as the stream is consumed and exposed via
    :meth:`extra_metrics`.
    """

    def __init__(self, transport, work_iter) -> None:
        self._transport = transport
        self._work = work_iter
        self._pairs: list[tuple[int, float]] = []  # (nonce, arrival dt)

    def results(self, count: int | None = None,
                duration: float | None = None) -> Iterator[QueuedResult]:
        import time
        from bfl_asic.protocol.icarus import (
            NONCE_SIZE, build_work, parse_nonce)
        t = self._transport
        if not t.is_open:
            t.open()
        start = time.monotonic()
        n = 0
        for midstate, data in self._work:
            if count is not None and n >= count:
                break
            if duration is not None and time.monotonic() - start >= duration:
                break
            work = build_work(midstate, data)
            t.flush_input()
            w0 = time.monotonic()
            t.write(work)
            raw = t.read(NONCE_SIZE)
            dt = time.monotonic() - w0
            nonces: list[int] = []
            if len(raw) == NONCE_SIZE:
                nonce = parse_nonce(raw)
                nonces.append(nonce)
                self._pairs.append((nonce, dt))
            n += 1
            yield QueuedResult(uid="icarus", nonces=nonces, raw=raw)

    def extra_metrics(self) -> dict:
        from bfl_asic.protocol.icarus import linear_scan_hashrate
        hr = linear_scan_hashrate(self._pairs)
        return {
            "hashrate_mhps": (hr / 1e6) if hr is not None else None,
            "samples": len(self._pairs),
            "linear_scan": True,
        }

    def name(self) -> str:
        return "icarus-nonce-source"
