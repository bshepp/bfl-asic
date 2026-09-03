"""Pure builders/parsers for the BFL 'SC' queued-work protocol.

Byte layout facts are taken from cgminer's driver-bflsc.h/.c (GPLv3
reference at cgminer-ref/); no code is copied.
No I/O happens here.
"""
from __future__ import annotations

import re

# dataclass/field (and RESP_COUNT below) are consumed by the parsers
# added to this module in the next task; intentionally imported now.
from dataclasses import dataclass, field
from typing import NamedTuple

from bfl_asic.protocol.constants import (
    CMD_DETAILS, CMD_QFLUSH, CMD_QJOB, CMD_QJOBS, CMD_QRESULTS,
    EOB, EOW, QJOB_PAYLOAD_SIZE, RESP_COUNT, SIGNATURE,
)

_MAX_PACK = 5  # QueueJobPackStructure.jobs[5] — firmware-fixed cap


def _job_struct(midstate: bytes, tail: bytes) -> bytes:
    if len(midstate) != 32:
        raise ValueError(f"midstate must be 32 bytes, got {len(midstate)}")
    if len(tail) != 12:
        raise ValueError(f"tail must be 12 bytes, got {len(tail)}")
    return bytes([QJOB_PAYLOAD_SIZE]) + midstate + tail + bytes([EOB])


def build_queue_job(midstate: bytes, tail: bytes) -> bytes:
    """`ZNX` + QueueJobStructure(payloadSize, midstate, blockdata, EOB)."""
    return CMD_QJOB + _job_struct(midstate, tail)


def build_queue_job_pack(jobs: list[tuple[bytes, bytes]]) -> bytes:
    """`ZWX` + QueueJobPackStructure (<=5 jobs)."""
    if not 1 <= len(jobs) <= _MAX_PACK:
        raise ValueError(f"job pack must hold 1..{_MAX_PACK} jobs, "
                         f"got {len(jobs)}")
    body = bytearray()
    body.append(SIGNATURE)
    body.append(len(jobs))
    for mid, tail in jobs:
        body += _job_struct(mid, tail)
    body.append(EOW)
    return CMD_QJOBS + bytes([len(body)]) + bytes(body)


def build_queue_results() -> bytes:
    """`ZOX` — read & free completed results."""
    return CMD_QRESULTS


def build_queue_flush() -> bytes:
    """`ZQX` — flush the device job queue."""
    return CMD_QFLUSH


def build_details() -> bytes:
    """`ZCX` — request device details (incl. JOBS IN QUEUE)."""
    return CMD_DETAILS


@dataclass
class QueuedResult:
    """One completed job's result from a `ZOX` drain.

    ``chip`` is the reporting die/processor id, present only in the v2
    result row (``UID, blockdata, CHIP, NONCECOUNT, nonce...``); ``None``
    for v1, which carries no per-chip column.
    """

    uid: str
    nonces: list[int] = field(default_factory=list)
    raw: bytes = b""
    chip: int | None = None


class Processor(NamedTuple):
    """One on-chip processor from a ZCX ``PROCESSOR N:`` line.

    Real Jalapeno firmware enumerates active processors individually,
    e.g. ``PROCESSOR 3: 12 engines @ 199 MHz`` -- exposing the internal
    engine/clock topology that the aggregate ``ENGINES:`` field hides.
    Processor indices can be sparse (fused-off cores are omitted).
    """

    index: int
    engines: int
    mhz: int


_PROC_KEY_RE = re.compile(r"PROCESSOR\s+(\d+)", re.IGNORECASE)
_PROC_VAL_RE = re.compile(
    r"(\d+)\s+engines?\s*@\s*(\d+)\s*MHz", re.IGNORECASE)
_LEADING_INT_RE = re.compile(r"(\d+)")


@dataclass
class DeviceDetails:
    """Parsed `ZCX` details.

    The raw ``fields`` dict is preserved verbatim (keys exactly as the
    firmware spelled them, including any leading ``--``). The typed
    properties below are the census view: they look keys up case-
    insensitively and ignore leading dashes, so ``--DEVICES IN CHAIN``
    is reachable as :attr:`devices_in_chain`.
    """

    fields: dict[str, str] = field(default_factory=dict)

    def _get(self, key: str) -> str | None:
        """Case-insensitive, dash-insensitive field lookup."""
        want = key.lstrip("-").strip().upper()
        for k, v in self.fields.items():
            if k.lstrip("-").strip().upper() == want:
                return v
        return None

    def _get_int(self, key: str) -> int | None:
        v = self._get(key)
        if v is None:
            return None
        try:
            return int(v.strip())
        except ValueError:
            return None

    @property
    def jobs_in_queue(self) -> int:
        v = self.fields.get("JOBS IN QUEUE", "0").strip()
        try:
            return int(v)
        except ValueError:
            return 0

    @property
    def device(self) -> str | None:
        """Model string, e.g. ``BitFORCE SC``."""
        return self._get("DEVICE")

    @property
    def firmware(self) -> str | None:
        """Firmware version string, e.g. ``1.0.0``."""
        return self._get("FIRMWARE")

    @property
    def engines(self) -> int | None:
        """Hashing-engine count; ``None`` if absent or non-numeric."""
        return self._get_int("ENGINES")

    @property
    def frequency(self) -> str | None:
        """Reported clock; SC firmware returns the literal ``[UNKNOWN]``."""
        return self._get("FREQUENCY")

    @property
    def xlink_mode(self) -> str | None:
        return self._get("XLINK MODE")

    @property
    def xlink_present(self) -> str | None:
        return self._get("XLINK PRESENT")

    @property
    def devices_in_chain(self) -> int | None:
        return self._get_int("DEVICES IN CHAIN")

    @property
    def chain_presence_mask(self) -> str | None:
        return self._get("CHAIN PRESENCE MASK")

    @property
    def frequency_mhz(self) -> int | None:
        """Reported clock as an integer MHz; ``None`` if ``[UNKNOWN]``."""
        v = self._get("FREQUENCY")
        if v is None:
            return None
        m = _LEADING_INT_RE.search(v)
        return int(m.group(1)) if m else None

    @property
    def mining_speed(self) -> str | None:
        """Firmware-estimated hashrate string, e.g. ``5.15 GH/s``.

        Tolerates the firmware's real ``MINIG SPEED`` typo as well as a
        corrected ``MINING SPEED``.
        """
        return self._get("MINIG SPEED") or self._get("MINING SPEED")

    @property
    def critical_temperature(self) -> int | None:
        return self._get_int("CRITICAL TEMPERATURE")

    @property
    def processors(self) -> list[Processor]:
        """Per-processor engine/clock topology, sorted by index.

        Parsed from every ``PROCESSOR N: X engines @ Y MHz`` line; empty
        if the firmware does not report a breakdown.
        """
        procs: list[Processor] = []
        for key, val in self.fields.items():
            km = _PROC_KEY_RE.match(key.lstrip("-").strip())
            if not km:
                continue
            vm = _PROC_VAL_RE.search(val)
            if not vm:
                continue
            procs.append(Processor(
                int(km.group(1)), int(vm.group(1)), int(vm.group(2))))
        procs.sort(key=lambda p: p.index)
        return procs


def _result_lines(raw: bytes) -> list[str]:
    text = raw.decode("ascii", errors="replace")
    out: list[str] = []
    for line in text.splitlines():
        s = line.strip()
        if (not s or s in ("OK", "SUCCESS")
                or s.startswith(("COUNT:", "ERR:", "INPROCESS:"))):
            continue
        out.append(s)
    return out


def parse_queue_results(raw: bytes, version: str = "v1") -> list[QueuedResult]:
    """Parse a `ZOX` result block.

    V1 fields: ``UID, CC, NONCECOUNT, nonce, ...``
    V2 fields: ``UID, CC, CHIP, NONCECOUNT, nonce, ...``
    Firmware "SC 1.0" is V1 (driver-bflsc.c drv_ver()).

    Lenient by design: malformed / short / non-hex lines are skipped so
    a single bad row never aborts a drain (cgminer logs-and-continues
    too). The declared ``COUNT:`` is NOT enforced here; the session
    layer compares the returned length against expectations and is the
    place that may raise a protocol error.
    """
    if version not in ("v1", "v2"):
        raise ValueError(
            f"unknown version {version!r}; expected 'v1' or 'v2'"
        )
    nonce_start = 3 if version == "v1" else 4
    results: list[QueuedResult] = []
    for line in _result_lines(raw):
        parts = [p.strip() for p in line.split(",") if p.strip() != ""]
        if len(parts) < nonce_start:
            continue
        uid = parts[0]
        try:
            nonces = [int(p, 16) for p in parts[nonce_start:]]
        except ValueError:
            continue  # non-hex nonce token — skip line, keep draining
        chip = None
        if version == "v2":
            try:
                chip = int(parts[2])  # CHIP column (decimal die id)
            except (ValueError, IndexError):
                chip = None
        results.append(QueuedResult(
            uid=uid, nonces=nonces, chip=chip,
            raw=line.encode("ascii", errors="replace"),
        ))
    return results


def result_version(details: DeviceDetails) -> str:
    """Pick the `ZOX` result-row format (``"v1"``/``"v2"``) for a device.

    Firmware that parallelizes across chips (census ``CHIP PARALLELIZATION:
    YES``) emits the v2 row with a per-nonce ``CHIP`` column; older firmware
    (e.g. 1.0.0) emits v1. This is the census-readable analogue of cgminer's
    ``drv_ver`` selection — parsing a v2 device as v1 misreads the
    ``NONCECOUNT`` field as a nonce (a low-value artifact).
    """
    val = details._get("CHIP PARALLELIZATION")
    if val and "YES" in val.upper():
        return "v2"
    return "v1"


def parse_details(raw: bytes) -> DeviceDetails:
    """Parse a `ZCX` details reply into `DeviceDetails`.

    Each non-framing line is ``KEY : VALUE`` (split on the first colon);
    empty / OK / SUCCESS / colon-less lines are ignored.
    """
    text = raw.decode("ascii", errors="replace")
    fields: dict[str, str] = {}
    for line in text.splitlines():
        s = line.strip()
        if not s or s in ("OK", "SUCCESS") or ":" not in s:
            continue
        key, _, val = s.partition(":")
        fields[key.strip()] = val.strip()
    return DeviceDetails(fields=fields)
