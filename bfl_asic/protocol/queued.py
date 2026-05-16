"""Pure builders/parsers for the BFL 'SC' queued-work protocol.

Byte layout facts are taken from cgminer's driver-bflsc.h/.c (GPLv3
reference at F:\\experimental-projects\\cgminer-ref\\); no code is copied.
No I/O happens here.
"""
from __future__ import annotations

# dataclass/field (and RESP_COUNT below) are consumed by the parsers
# added to this module in the next task; intentionally imported now.
from dataclasses import dataclass, field

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
