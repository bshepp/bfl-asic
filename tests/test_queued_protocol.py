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
    assert C.EOB == 0xAA and C.SIGNATURE == 0xC1 and C.EOW == 0xFE
    assert C.QUE_MAX_RESULTS == 8
    assert C.QJOB_PAYLOAD_SIZE == 45  # midstate(32)+blockdata(12)+EOB(1)
    # existing tokens untouched
    assert C.CMD_WORK == b"ZDX" and C.CMD_RESULT == b"ZFX"
    assert C.DELIMITER == b">>>>>>>>"
