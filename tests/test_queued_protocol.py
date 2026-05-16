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
    # exact total length + per-struct payloadSize offsets lock the framing
    assert len(out) == 3 + 1 + 1 + 1 + 3 * 46 + 1  # == 145
    assert out[6] == 45    # 1st job struct payloadSize
    assert out[52] == 45   # 2nd job struct payloadSize (6 + 46)
    assert out[98] == 45   # 3rd job struct payloadSize (52 + 46)
    with pytest.raises(ValueError):
        build_queue_job_pack([(bytes(32), bytes(12))] * 6)  # cap is 5
    with pytest.raises(ValueError):
        build_queue_job_pack([])


def test_simple_commands():
    assert build_queue_results() == b"ZOX"
    assert build_queue_flush() == b"ZQX"
    assert build_details() == b"ZCX"


def test_build_queue_job_rejects_non_bytes():
    # len("x"*32)==32 passes the length guard; bytes+str then raises.
    with pytest.raises((TypeError, ValueError)):
        build_queue_job("x" * 32, bytes(12))


from bfl_asic.protocol.queued import (
    parse_queue_results, parse_details, QueuedResult, DeviceDetails,
)

# V1 block: COUNT line, then "<uid>,<cc>,<noncecount>,<nonce>,..."
V1_BLOCK = b"COUNT:1\n0a1b2c3d,0,2,12345678,9abcdef0\nOK\n"


def test_parse_queue_results_v1():
    res = parse_queue_results(V1_BLOCK)  # default version="v1"
    assert isinstance(res, list) and len(res) == 1
    r = res[0]
    assert isinstance(r, QueuedResult)
    assert r.uid == "0a1b2c3d"
    assert r.nonces == [0x12345678, 0x9ABCDEF0]


def test_parse_queue_results_empty():
    assert parse_queue_results(b"COUNT:0\nOK\n") == []


def test_parse_queue_results_v2_chip_field():
    block = b"COUNT:1\nfeedface,0,7,1,deadbeef\nOK\n"
    res = parse_queue_results(block, version="v2")
    assert res[0].uid == "feedface"
    assert res[0].nonces == [0xDEADBEEF]


def test_parse_details_jobs_in_queue():
    blob = (b"FIRMWARE: 1.0.0\nENGINES: 1\nJOBS IN QUEUE: 5\n"
            b"CHIP PARALLELIZATION: NO\nOK\n")
    d = parse_details(blob)
    assert isinstance(d, DeviceDetails)
    assert d.jobs_in_queue == 5
    assert d.fields["FIRMWARE"] == "1.0.0"
    assert d.fields["ENGINES"] == "1"


def test_parse_queue_results_skips_non_hex_nonce_keeps_draining():
    # C1: a bad row must NOT abort the drain — later rows still parse.
    block = b"COUNT:2\nAA,0,1,ZZZZZZZZ\nBB,0,1,deadbeef\nOK\n"
    res = parse_queue_results(block)
    assert [r.uid for r in res] == ["BB"]
    assert res[0].nonces == [0xDEADBEEF]


def test_parse_queue_results_non_ascii_in_uid_does_not_crash_raw():
    # I2: a stray non-ASCII wire byte in a parsed line must not crash
    # the .raw encode.
    res = parse_queue_results(b"COUNT:1\nA\xaaA,0,1,deadbeef\nOK\n")
    assert len(res) == 1 and res[0].nonces == [0xDEADBEEF]


def test_parse_queue_results_crlf():
    res = parse_queue_results(b"COUNT:1\r\nAA,0,1,deadbeef\r\nOK\r\n")
    assert res[0].uid == "AA" and res[0].nonces == [0xDEADBEEF]


def test_parse_queue_results_multi_result_mixed_counts():
    block = b"COUNT:3\nA,0,1,11\nB,0,2,22,33\nC,0,0\nOK\n"
    res = parse_queue_results(block)
    assert [(r.uid, r.nonces) for r in res] == [
        ("A", [0x11]), ("B", [0x22, 0x33]), ("C", [])]


def test_parse_queue_results_unknown_version_raises():
    with pytest.raises(ValueError):
        parse_queue_results(b"COUNT:0\nOK\n", version="V1")


def test_parse_queue_results_drops_err_line():
    assert parse_queue_results(b"COUNT:1\nERR:TIMEOUT\nOK\n") == []


def test_device_details_jobs_in_queue_edge_cases():
    assert parse_details(b"FIRMWARE: 1.0.0\nOK\n").jobs_in_queue == 0
    assert parse_details(b"JOBS IN QUEUE: junk\nOK\n").jobs_in_queue == 0
    assert parse_details(b"JOBS IN QUEUE: -1\nOK\n").jobs_in_queue == -1


def test_parse_details_value_with_colon():
    d = parse_details(b"FIRMWARE: 1.0.0:beta\nOK\n")
    assert d.fields["FIRMWARE"] == "1.0.0:beta"
