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
    build_voltage,
    build_work,
)
from bfl_asic.protocol.constants import POLL_INTERVAL, WORK_TIMEOUT
from bfl_asic.protocol.responses import (
    DeviceInfo,
    TemperatureReading,
    VoltageReading,
    WorkResult,
    WorkStatus,
    parse_identify,
    parse_temperature,
    parse_voltage,
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
        """Query device temperature (ZLX command)."""
        self._transport.write(build_temperature())
        raw = self._transport.readline()
        return parse_temperature(raw)

    def get_voltage(self) -> VoltageReading:
        """Query device voltages (ZTX command).

        Returns VCC1, VCC2, and VMAIN in volts.
        """
        self._transport.write(build_voltage())
        raw = self._transport.readline()
        return parse_voltage(raw)

    def set_fan_auto(self) -> bool:
        """Hand the fan back to firmware thermal management (Z9X)."""
        from bfl_asic.protocol.fan import build_fan_auto, parse_fan_ack
        self._transport.write(build_fan_auto())
        return parse_fan_ack(self._transport.readline())

    def set_fan(self, level: int) -> bool:
        """Set a FIXED fan level 0..4 (Z0X..Z4X).

        WARNING: a low/off fixed fan during active hashing can overheat
        and physically damage the ASIC. Prefer set_fan_auto(); always
        restore auto when done. Levels 1..3 are firmware-defined but
        hardware-unconfirmed.
        """
        import warnings
        from bfl_asic.protocol.fan import build_fan_level, parse_fan_ack
        warnings.warn(
            f"set_fan({level}): manual fan level overrides firmware "
            f"thermal management; low levels during hashing risk thermal "
            f"damage. Restore set_fan_auto() when done.",
            stacklevel=2,
        )
        self._transport.write(build_fan_level(level))
        return parse_fan_ack(self._transport.readline())

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


class QueuedWorkSession:
    """Sustained SC queued-work session (opt-in; the naive BFLDevice
    work path is unchanged). Continuously drains results so the
    firmware queue never saturates -- the real-miner pattern.

    On real hardware a submitted job's result is not ready for ~0.8s,
    so ``run()`` backs off ``poll_interval`` seconds between empty
    drains rather than busy-polling the serial port, and never exits
    while jobs may still be in flight.
    """

    def __init__(self, transport, *, max_queue_depth: int = 32,
                 poll_interval: float = 0.1) -> None:
        self._transport = transport
        self._max_depth = max_queue_depth
        self._poll_interval = poll_interval

    def __enter__(self) -> "QueuedWorkSession":
        if not self._transport.is_open:
            self._transport.open()
        return self

    def __exit__(self, *exc) -> None:
        """Best-effort ZQX flush so the device is not left queued."""
        from bfl_asic.protocol.queued import build_queue_flush
        try:
            self._transport.write(build_queue_flush())
            self._transport.readline()
        except Exception:
            pass

    def _read_until_terminator(self, max_lines: int) -> bytes:
        """Read lines until OK/SUCCESS or an empty (timeout) line."""
        raw = b""
        for _ in range(max_lines):
            line = self._transport.readline()
            raw += line
            if line.strip() in (b"OK", b"SUCCESS") or not line:
                break
        return raw

    def _jobs_in_queue(self) -> int:
        """ZCX -> device-reported JOBS IN QUEUE (backpressure signal)."""
        from bfl_asic.protocol.queued import build_details, parse_details
        self._transport.write(build_details())
        return parse_details(self._read_until_terminator(16)).jobs_in_queue

    def submit(self, midstate: bytes, tail: bytes) -> None:
        """Send one ZNX job. Raise BFLProtocolError if the firmware
        rejects it (ERR:/INPROCESS:) so a job is never silently lost.
        """
        from bfl_asic.exceptions import BFLProtocolError
        from bfl_asic.protocol.queued import build_queue_job
        self._transport.write(build_queue_job(midstate, tail))
        ack = self._transport.readline().strip()
        if ack.startswith(b"ERR:") or ack.startswith(b"INPROCESS:"):
            raise BFLProtocolError(f"ZNX submit rejected: {ack!r}")

    def drain(self) -> list:
        """ZOX -> up to QUE_MAX_RESULTS completed results (frees slots).

        Returns a list of bfl_asic.protocol.queued.QueuedResult.
        """
        from bfl_asic.protocol.queued import (
            build_queue_results, parse_queue_results)
        self._transport.write(build_queue_results())
        return parse_queue_results(self._read_until_terminator(64),
                                   version="v1")

    def run(self, *, work_iter, max_jobs=None, duration=None):
        """Submit from *work_iter*, draining continuously; yields
        QueuedResult objects.

        Uses ONE ZCX per outer iteration (no TOCTOU race) and only
        terminates when there is no more work to submit, the device
        queue observed this iteration was empty, AND this iteration's
        drain was empty -- so in-flight results are never abandoned.
        Sleeps ``poll_interval`` between empty drains so real hardware
        (results ~0.8s late) is not busy-polled.
        """
        import time
        submitted = 0
        deadline = (time.monotonic() + duration
                    if duration is not None else None)
        exhausted = False
        while True:
            depth = self._jobs_in_queue()
            while (not exhausted
                   and (max_jobs is None or submitted < max_jobs)
                   and depth < self._max_depth):
                try:
                    mid, tail = next(work_iter)
                except StopIteration:
                    exhausted = True
                    break
                self.submit(mid, tail)
                submitted += 1
                depth += 1
            results = self.drain()
            for r in results:
                yield r
            if deadline is not None and time.monotonic() >= deadline:
                break
            no_more_to_submit = exhausted or (
                max_jobs is not None and submitted >= max_jobs)
            if no_more_to_submit and depth == 0 and not results:
                break
            if not results:
                time.sleep(self._poll_interval)
