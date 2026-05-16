"""SC queued-work + details protocol: pure builders/parsers. No hardware."""
from __future__ import annotations

from bfl_asic.protocol import constants as C


def test_new_constants_present_and_additive():
    assert C.CMD_QJOB == b"ZNX"
    assert C.CMD_QJOBS == b"ZWX"
    assert C.CMD_QRESULTS == b"ZOX"
    assert C.CMD_QFLUSH == b"ZQX"
    assert C.CMD_DETAILS == b"ZCX"
    assert C.CMD_FAN_AUTO == b"Z9X"
    assert C.CMD_FAN_LEVELS == (b"Z0X", b"Z1X", b"Z2X", b"Z3X", b"Z4X")
    assert C.EOB == 0xAA
    assert C.SIGNATURE == 0xC1
    assert C.EOW == 0xFE
    assert C.QUE_MAX_RESULTS == 8
    assert C.QJOB_PAYLOAD_SIZE == 45  # midstate(32)+blockdata(12)+EOB(1)
    # existing tokens untouched
    assert C.CMD_WORK == b"ZDX" and C.CMD_RESULT == b"ZFX"
    assert C.DELIMITER == b">>>>>>>>"


import pytest
from bfl_asic.protocol.queued import (
    build_queue_job, build_queue_job_pack,
    build_queue_results, build_queue_flush, build_details,
)


def test_build_queue_job_exact_bytes():
    mid = bytes(range(32)); tail = bytes(range(12))
    out = build_queue_job(mid, tail)
    assert out[:3] == b"ZNX"
    assert out[3] == 45               # payloadSize
    assert out[4:36] == mid
    assert out[36:48] == tail
    assert out[48] == 0xAA            # EOB
    assert len(out) == 3 + 1 + 32 + 12 + 1


@pytest.mark.parametrize("bad", [(b"\x00" * 31, b"\x00" * 12),
                                  (b"\x00" * 32, b"\x00" * 11)])
def test_build_queue_job_validates_lengths(bad):
    with pytest.raises(ValueError):
        build_queue_job(*bad)


def test_build_queue_job_pack_framing_and_cap():
    jobs = [(bytes(32), bytes(12))] * 3
    out = build_queue_job_pack(jobs)
    assert out[:3] == b"ZWX"
    body = out[3:]
    assert body[0] == len(body) - 1   # payloadSize counts bytes after itself
    assert body[1] == 0xC1            # signature
    assert body[2] == 3               # jobsInArray
    assert body[-1] == 0xFE           # endOfWrapper
    with pytest.raises(ValueError):
        build_queue_job_pack([(bytes(32), bytes(12))] * 6)  # cap is 5
    with pytest.raises(ValueError):
        build_queue_job_pack([])


def test_simple_commands():
    assert build_queue_results() == b"ZOX"
    assert build_queue_flush() == b"ZQX"
    assert build_details() == b"ZCX"
