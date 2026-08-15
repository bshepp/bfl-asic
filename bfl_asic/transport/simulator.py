"""Simulator transport for developing and testing without physical BFL hardware.

Provides :class:`SimulatedDevice`, a state-machine that processes BFL protocol
commands and computes SHA-256d hashes in software, and :class:`SimulatorTransport`,
which bridges the :class:`~bfl_asic.transport.base.BaseTransport` interface to the
simulated device.
"""

from __future__ import annotations

import hashlib
import random
from enum import Enum, auto

from bfl_asic.exceptions import BFLConnectionError
from bfl_asic.protocol.constants import DELIMITER
from bfl_asic.transport.base import BaseTransport


class DeviceState(Enum):
    """Operating states of the simulated BFL ASIC device."""

    IDLE = auto()
    HASHING = auto()
    OVERHEATED = auto()


class SimulatedDevice:
    """State machine that processes BFL protocol commands and generates responses.

    Computes SHA-256d hashes in software to return valid nonces, simulating
    the behaviour of a real BFL Jalapeno ASIC miner.

    Parameters
    ----------
    simulated_hashrate:
        Number of nonces to scan per work submission (kept low for fast tests).
    base_temperature:
        Starting temperature in Celsius.
    heat_per_work:
        Temperature rise per work unit processed.
    cooling_rate:
        Degrees cooled per status poll when idle.
    overheat_threshold:
        Temperature at which the device enters the OVERHEATED state.
    error_rate:
        Probability (0.0 -- 1.0) of returning a garbled response.
    """

    def __init__(
        self,
        *,
        simulated_hashrate: int = 1000,
        engines: int = 30,
        base_temperature: float = 35.0,
        heat_per_work: float = 2.0,
        cooling_rate: float = 0.5,
        overheat_threshold: float = 85.0,
        error_rate: float = 0.0,
        naive_work_limit: int | None = None,
    ) -> None:
        # Configuration
        self.simulated_hashrate = simulated_hashrate
        self.engines = engines
        self.base_temperature = base_temperature
        self.heat_per_work = heat_per_work
        self.cooling_rate = cooling_rate
        self.overheat_threshold = overheat_threshold
        self.error_rate = error_rate

        # Internal state
        self.state: DeviceState = DeviceState.IDLE
        self.temperature: float = base_temperature
        self.current_work: tuple[bytes, bytes] | None = None
        self.found_nonces: list[int] = []
        self.work_complete: bool = False
        self.device_info: str = "BitFORCE SHA256 ASIC Jalapeno 5GH/s"
        # Naive ZDX path: optional firmware-style wall (opt-in; default
        # off so existing behaviour/tests are unchanged).
        self.naive_work_limit = naive_work_limit
        self._naive_zdx_count = 0
        # SC queued model
        self._job_queue: list[tuple[bytes, bytes]] = []
        self._results: list[tuple[str, list[int]]] = []
        self._uid = 0
        # NVRAM scratch string, exercised by the ZSX/ZUX probe commands.
        self._nvram: bytes = b""
        # Fan state
        self.fan_mode: str = "auto"
        self.fan_level: int | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def process_command(self, data: bytes) -> bytes:
        """Process a raw command and return the device response as bytes."""
        response = self._dispatch(data)

        # Optionally garble the response for robustness testing.
        if self.error_rate > 0.0 and random.random() < self.error_rate:
            response = self._garble(response)

        return response

    # ------------------------------------------------------------------
    # Command dispatch
    # ------------------------------------------------------------------

    def _dispatch(self, data: bytes) -> bytes:
        """Route *data* to the appropriate handler."""
        if data.startswith(b"ZGX"):
            return self._handle_identify()
        if data.startswith(b"ZLX"):
            return self._handle_temperature()
        if data.startswith(b"ZTX"):
            return self._handle_voltage()
        if data.startswith(b"ZDX") or data.startswith(DELIMITER):
            return self._handle_work(data)
        if data.startswith(b"ZFX"):
            return self._handle_result()
        if data.startswith(b"ZNX"):
            return self._handle_queue_job(data)
        if data.startswith(b"ZWX"):
            return self._handle_queue_job_pack(data)
        if data.startswith(b"ZOX"):
            return self._handle_queue_results()
        if data.startswith(b"ZQX"):
            self._job_queue.clear()
            self._results.clear()
            return b"OK\n"
        if data.startswith(b"ZCX"):
            return self._handle_details()
        if data.startswith(b"ZJX"):
            return self._handle_firmware()
        if data.startswith(b"ZUX"):
            return self._handle_loadstr()
        if data.startswith(b"ZSX"):
            return self._handle_savestr(data)
        if data.startswith(b"Z9X"):
            self.fan_mode, self.fan_level = "auto", None
            return b"OK\n"
        for lvl in range(5):
            if data.startswith(b"Z%dX" % lvl):
                self.fan_mode, self.fan_level = "fixed", lvl
                return b"OK\n"
        return b"ERR:UNKNOWN\n"

    # ------------------------------------------------------------------
    # Handlers
    # ------------------------------------------------------------------

    def _handle_identify(self) -> bytes:
        return f"{self.device_info}\n".encode()

    def _handle_temperature(self) -> bytes:
        t = int(self.temperature)
        return f"Temp1: {t}, Temp2: {t}\n".encode()

    def _handle_voltage(self) -> bytes:
        return b"3300,1000,12000\n"

    def _handle_work(self, data: bytes) -> bytes:
        if self.naive_work_limit is not None:
            self._naive_zdx_count += 1
            if self._naive_zdx_count > self.naive_work_limit:
                return b""  # documented stall: empty response, no reset
        if self.state is DeviceState.OVERHEATED:
            return b"ERR:OVERHEATED\n"

        midstate, tail = self._parse_work_packet(data)
        self.current_work = (midstate, tail)
        self.found_nonces = []
        self.work_complete = False
        self.state = DeviceState.HASHING

        # Mine synchronously over a small nonce range.
        self._mine(midstate, tail)

        # Thermal effects.
        self.temperature += self.heat_per_work
        if self.temperature >= self.overheat_threshold:
            self.state = DeviceState.OVERHEATED

        return b"OK\n"

    def _handle_result(self) -> bytes:
        if self.state is DeviceState.IDLE and self.current_work is None:
            return b"IDLE\n"

        if self.state is DeviceState.HASHING:
            if self.work_complete:
                response = self._format_nonce_result()
                # Reset for next work unit.
                self.state = DeviceState.IDLE
                self.current_work = None
                self._apply_cooling()
                return response
            # Still working (shouldn't happen in sync sim, but covered).
            return b"B\n"

        if self.state is DeviceState.OVERHEATED:
            self._apply_cooling()
            if self.temperature < self.overheat_threshold - 10:
                self.state = DeviceState.IDLE
            return b"ERR:OVERHEATED\n"

        # Fallback: IDLE but work was previously completed and already read.
        return b"IDLE\n"

    # ------------------------------------------------------------------
    # Probe-command handlers (ZJX/ZUX/ZSX)
    # ------------------------------------------------------------------

    def _handle_firmware(self) -> bytes:
        # Real ZJX (firmware 1.0.0) returns a bare version string with no
        # framing and no OK terminator (captured via probe_commands.py).
        return b"1.0.0"

    def _handle_loadstr(self) -> bytes:
        if self._nvram:
            return self._nvram + b"\nOK\n"
        # Real device reports a blank scratchpad with this sentinel.
        return b"MEMORY EMPTY\n"

    def _handle_savestr(self, data: bytes) -> bytes:
        body = data[3:]  # strip "ZSX"
        if not body:
            return b"ERR:NODATA\n"
        size = body[0]
        self._nvram = bytes(body[1:1 + size])
        return b"OK\n"

    # ------------------------------------------------------------------
    # Queued-model handlers
    # ------------------------------------------------------------------

    def _mine_one(self, midstate: bytes, tail: bytes) -> list[int]:
        nonces: list[int] = []
        for nonce in range(self.simulated_hashrate):
            h = hashlib.sha256(
                hashlib.sha256(midstate + tail + nonce.to_bytes(4, "big")
                               ).digest()).digest()
            if h[0] == 0x00:
                nonces.append(nonce)
        return nonces

    def _enqueue(self, midstate: bytes, tail: bytes) -> None:
        self._uid += 1
        self._results.append((f"{self._uid:08x}",
                               self._mine_one(midstate, tail)))
        self._job_queue.append((midstate, tail))

    def _handle_queue_job(self, data: bytes) -> bytes:
        payload = data[3:]
        midstate = payload[1:33]
        tail = payload[33:45]
        self._enqueue(midstate.ljust(32, b"\x00"), tail.ljust(12, b"\x00"))
        return b"OK\n"

    def _handle_queue_job_pack(self, data: bytes) -> bytes:
        body = data[3:]
        n = body[2] if len(body) > 2 else 0
        off = 3
        for _ in range(n):
            mid = body[off + 1:off + 33]
            tail = body[off + 33:off + 45]
            self._enqueue(mid.ljust(32, b"\x00"), tail.ljust(12, b"\x00"))
            off += 46
        return b"OK\n"

    def _handle_queue_results(self) -> bytes:
        from bfl_asic.protocol.constants import QUE_MAX_RESULTS
        batch = self._results[:QUE_MAX_RESULTS]
        self._results = self._results[QUE_MAX_RESULTS:]
        # mirror real drain: results leave the queue's job slots too
        del self._job_queue[:len(batch)]
        lines = [f"COUNT:{len(batch)}".encode()]
        for uid, nonces in batch:
            fields = [uid, "0", str(len(nonces))] + [f"{n:08x}"
                                                     for n in nonces]
            lines.append(",".join(fields).encode())
        lines.append(b"OK")
        return b"\n".join(lines) + b"\n"

    def _handle_details(self) -> bytes:
        # Mirror a real Jalapeno's ZCX reply (recorded in cgminer's
        # driver-bflsc.c getinfo() comment): DEVICE/FIRMWARE/ENGINES/
        # FREQUENCY/XLINK plus the dashed chain fields. FREQUENCY is the
        # literal "[UNKNOWN]" the SC firmware actually returns. The
        # JOBS IN QUEUE line stays live for backpressure polling.
        return (
            "DEVICE: BitFORCE SC\n"
            "FIRMWARE: 1.0.0\n"
            f"ENGINES: {self.engines}\n"
            "FREQUENCY: [UNKNOWN]\n"
            "XLINK MODE: MASTER\n"
            "XLINK PRESENT: YES\n"
            "--DEVICES IN CHAIN: 0\n"
            "--CHAIN PRESENCE MASK: 00000000\n"
            f"JOBS IN QUEUE: {len(self._job_queue)}\n"
            "OK\n"
        ).encode()

    # ------------------------------------------------------------------
    # Mining helpers
    # ------------------------------------------------------------------

    def _parse_work_packet(self, data: bytes) -> tuple[bytes, bytes]:
        """Extract midstate (32 bytes) and tail (12 bytes) from a work packet.

        Accepted formats:
        - ``DELIMITER + midstate(32) + tail(12) + DELIMITER``  (60 bytes)
        - ``ZDX`` followed by the 60-byte packet
        - Raw data where we simply slice midstate/tail from the payload
        """
        payload = data
        # Strip leading ZDX if present.
        if payload.startswith(b"ZDX"):
            payload = payload[3:]
        # Strip leading delimiter.
        if payload.startswith(DELIMITER):
            payload = payload[len(DELIMITER) :]
        # Strip trailing delimiter.
        if payload.endswith(DELIMITER):
            payload = payload[: -len(DELIMITER)]

        midstate = payload[:32]
        tail = payload[32:44]

        # Pad if shorter than expected (e.g. in tests).
        midstate = midstate.ljust(32, b"\x00")
        tail = tail.ljust(12, b"\x00")

        return midstate, tail

    def _mine(self, midstate: bytes, tail: bytes) -> None:
        """Scan nonces ``0 .. simulated_hashrate`` and collect easy wins."""
        for nonce in range(self.simulated_hashrate):
            nonce_bytes = nonce.to_bytes(4, "big")
            hash_input = midstate + tail + nonce_bytes
            first_hash = hashlib.sha256(hash_input).digest()
            second_hash = hashlib.sha256(first_hash).digest()
            if second_hash[0] == 0x00:
                self.found_nonces.append(nonce)
        self.work_complete = True

    def _format_nonce_result(self) -> bytes:
        if self.found_nonces:
            hex_nonces = ",".join(f"{n:08x}" for n in self.found_nonces)
            return f"NONCE-FOUND:{hex_nonces}\n".encode()
        return b"NO-NONCE\n"

    # ------------------------------------------------------------------
    # Thermal helpers
    # ------------------------------------------------------------------

    def _apply_cooling(self) -> None:
        self.temperature = max(
            self.base_temperature, self.temperature - self.cooling_rate
        )

    # ------------------------------------------------------------------
    # Error injection
    # ------------------------------------------------------------------

    @staticmethod
    def _garble(data: bytes) -> bytes:
        """Return a randomly corrupted version of *data*."""
        if not data:
            return data
        ba = bytearray(data)
        idx = random.randrange(len(ba))
        ba[idx] ^= random.randint(1, 255)
        return bytes(ba)


class SimulatorTransport(BaseTransport):
    """Transport that bridges :class:`BaseTransport` to a :class:`SimulatedDevice`.

    This allows higher-level code (device APIs, CLI, tests) to run against a
    fully-functional in-process simulator with zero hardware dependencies.
    """

    def __init__(self, device: SimulatedDevice | None = None) -> None:
        self._device = device or SimulatedDevice()
        self._response_buffer = b""
        self._opened = False

    # ------------------------------------------------------------------
    # BaseTransport implementation
    # ------------------------------------------------------------------

    def open(self) -> None:
        self._opened = True

    def close(self) -> None:
        self._opened = False
        self._response_buffer = b""

    def write(self, data: bytes) -> None:
        if not self._opened:
            raise BFLConnectionError("Transport is not open")
        response = self._device.process_command(data)
        self._response_buffer += response

    def read(self, size: int, timeout: float | None = None) -> bytes:
        if not self._opened:
            raise BFLConnectionError("Transport is not open")
        data = self._response_buffer[:size]
        self._response_buffer = self._response_buffer[size:]
        return data

    def readline(self, timeout: float | None = None) -> bytes:
        if not self._opened:
            raise BFLConnectionError("Transport is not open")
        idx = self._response_buffer.find(b"\n")
        if idx == -1:
            data = self._response_buffer
            self._response_buffer = b""
            return data
        data = self._response_buffer[: idx + 1]
        self._response_buffer = self._response_buffer[idx + 1 :]
        return data

    @property
    def is_open(self) -> bool:
        return self._opened

    @property
    def device(self) -> SimulatedDevice:
        """Access the underlying simulated device."""
        return self._device
