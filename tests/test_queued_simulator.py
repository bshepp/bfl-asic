"""Simulator queued model + the naive-vs-queued contrast regression."""
from __future__ import annotations

import pytest

from bfl_asic.transport.simulator import SimulatedDevice


def _job(i: int) -> bytes:
    from bfl_asic.protocol.queued import build_queue_job
    return build_queue_job(bytes([i % 256]) * 32, bytes([i % 256]) * 12)


def _cold() -> SimulatedDevice:
    """Return a SimulatedDevice with thermal effects disabled (heat_per_work=0)
    so thermal state never interferes with wall / queued-path tests."""
    return SimulatedDevice(heat_per_work=0.0)


def test_simulator_details_census_is_realistic():
    # ZCX should look like a real Jalapeno, not the old ENGINES:1 stub.
    from bfl_asic.protocol.queued import parse_details
    det = parse_details(SimulatedDevice().process_command(b"ZCX"))
    assert det.device == "BitFORCE SC"
    assert det.firmware == "1.0.0"
    assert det.engines == 30
    assert det.frequency == "[UNKNOWN]"
    assert det.jobs_in_queue == 0


def test_simulator_details_engines_configurable():
    # Phase-2 nonce mapping needs a knowable engine count.
    from bfl_asic.protocol.queued import parse_details
    d = SimulatedDevice(engines=16)
    assert parse_details(d.process_command(b"ZCX")).engines == 16


def test_simulator_details_jobs_in_queue_still_tracks():
    # The census upgrade must not break the JOBS IN QUEUE backpressure line.
    from bfl_asic.protocol.queued import parse_details
    d = SimulatedDevice()
    d.process_command(_job(0))
    d.process_command(_job(1))
    assert parse_details(d.process_command(b"ZCX")).jobs_in_queue == 2


class _AckStub:
    """Minimal transport stub returning a fixed line to readline()."""

    def __init__(self, ack: bytes) -> None:
        self.ack = ack
        self.written: list[bytes] = []

    def write(self, data: bytes) -> None:
        self.written.append(data)

    def readline(self, timeout=None) -> bytes:  # noqa: ANN001
        return self.ack


def test_submit_accepts_inprocess_ack():
    # Real firmware answers ZNX with "INPROCESS:<n>" (n jobs in process)
    # as a valid ACCEPT. cgminer's isokerr treats anything without
    # "ERR:" as OK, so this must not raise.
    from bfl_asic.device import QueuedWorkSession
    s = QueuedWorkSession(_AckStub(b"INPROCESS:1\n"))
    s.submit(bytes(32), bytes(12))  # must not raise


def test_submit_rejects_err_ack():
    from bfl_asic.device import QueuedWorkSession
    from bfl_asic.exceptions import BFLProtocolError
    s = QueuedWorkSession(_AckStub(b"ERR:QUEUE FULL\n"))
    with pytest.raises(BFLProtocolError):
        s.submit(bytes(32), bytes(12))


def test_simulator_firmware_query_returns_reply():
    from bfl_asic.protocol.probe import parse_firmware
    fw = parse_firmware(SimulatedDevice().process_command(b"ZJX"))
    assert fw.version == "1.0.0"  # bare version, matching real hardware
    assert fw.raw  # raw reply always preserved


def test_simulator_nvram_savestr_loadstr_roundtrip():
    from bfl_asic.protocol.probe import (
        build_savestr, parse_loadstr, parse_savestr_ack)
    d = SimulatedDevice()
    # Empty scratch initially.
    assert parse_loadstr(d.process_command(b"ZUX")) == ""
    # Write, then read it back.
    ack = parse_savestr_ack(d.process_command(build_savestr(b"hello silicon")))
    assert ack is True
    assert parse_loadstr(d.process_command(b"ZUX")) == "hello silicon"


def test_naive_wall_off_by_default():
    # Default sim has NO wall: existing behaviour preserved.
    d = _cold()
    from bfl_asic.protocol.commands import build_work
    for _ in range(60):
        assert d.process_command(build_work(bytes(32), bytes(12))) == b"OK\n"


def test_naive_wall_when_opted_in():
    d = SimulatedDevice(naive_work_limit=42, heat_per_work=0.0)
    from bfl_asic.protocol.commands import build_work
    for _ in range(42):
        assert d.process_command(build_work(bytes(32), bytes(12))) == b"OK\n"
    # 43rd ZDX: documented stall signature = empty response
    assert d.process_command(build_work(bytes(32), bytes(12))) == b""
    # non-work commands still work after the wall
    assert d.process_command(b"ZGX").endswith(b"\n")


def test_queued_path_sustains_well_past_42():
    d = SimulatedDevice(naive_work_limit=42)  # wall on; queued must ignore it
    for i in range(500):
        assert d.process_command(_job(i)) == b"OK\n"          # ZNX accepted
    blob = d.process_command(b"ZCX")
    from bfl_asic.protocol.queued import parse_details, parse_queue_results
    assert parse_details(blob).jobs_in_queue == 500
    drained = 0
    for _ in range(200):
        res = parse_queue_results(d.process_command(b"ZOX"))
        drained += len(res)
        if parse_details(d.process_command(b"ZCX")).jobs_in_queue == 0:
            break
    assert drained == 500            # every queued job produced a result
    assert d.process_command(b"ZQX") == b"OK\n"


def test_fan_state_roundtrip():
    d = SimulatedDevice()
    assert d.process_command(b"Z9X") == b"OK\n"
    assert d.fan_mode == "auto"
    assert d.process_command(b"Z4X") == b"OK\n"
    assert d.fan_mode == "fixed" and d.fan_level == 4
    assert d.process_command(b"Z0X") == b"OK\n"
    assert d.fan_mode == "fixed" and d.fan_level == 0


def test_queue_job_pack_zwx_enqueues_all_jobs():
    from bfl_asic.protocol.queued import build_queue_job_pack, parse_details
    d = SimulatedDevice()
    jobs2 = [(bytes(32), bytes(12)),
             (bytes([0xAB]) * 32, bytes([0xCD]) * 12)]
    assert d.process_command(build_queue_job_pack(jobs2)) == b"OK\n"
    assert parse_details(d.process_command(b"ZCX")).jobs_in_queue == 2
    jobs5 = [(bytes([i]) * 32, bytes([i]) * 12) for i in range(5)]
    assert d.process_command(build_queue_job_pack(jobs5)) == b"OK\n"
    assert parse_details(d.process_command(b"ZCX")).jobs_in_queue == 7
    # drain everything; all 7 packed jobs must yield results
    from bfl_asic.protocol.queued import parse_queue_results
    drained = 0
    for _ in range(20):
        drained += len(parse_queue_results(d.process_command(b"ZOX")))
        if parse_details(d.process_command(b"ZCX")).jobs_in_queue == 0:
            break
    assert drained == 7


def test_queued_work_session_runs_past_42():
    from bfl_asic.transport.simulator import SimulatorTransport, SimulatedDevice
    from bfl_asic.device import QueuedWorkSession

    t = SimulatorTransport(SimulatedDevice(naive_work_limit=42,
                                           simulated_hashrate=64))
    t.open()
    seen = 0
    with QueuedWorkSession(t) as sess:
        def work():
            for i in range(120):
                yield (bytes([i % 256]) * 32, bytes([i % 256]) * 12)
        for _result in sess.run(work_iter=work(), max_jobs=120):
            seen += 1
    assert seen == 120  # > 42: the wall is gone via the queued path


def test_queued_session_no_busyspin_or_result_loss(monkeypatch):
    """Latched fake transport: results are NOT ready until a job has
    been ZOX-polled twice. Locks C1 (must back off, not busy-spin) and
    C2 (must not exit while jobs are in flight -> no result loss)."""
    import time as _time
    from bfl_asic.device import QueuedWorkSession

    sleeps: list = []
    monkeypatch.setattr(_time, "sleep", lambda s: sleeps.append(s))

    class LatchT:
        def __init__(self):
            self.jobs: list = []  # each {"ttl": int, "uid": str}
            self._out = b""
            self._n = 0
            self.is_open = True

        def open(self):
            self.is_open = True

        def write(self, data: bytes):
            if data[:3] == b"ZNX":
                self._n += 1
                self.jobs.append({"ttl": 2, "uid": f"{self._n:08x}"})
                self._out = b"OK\n"
            elif data[:3] == b"ZCX":
                self._out = b"JOBS IN QUEUE: %d\nOK\n" % len(self.jobs)
            elif data[:3] == b"ZOX":
                for j in self.jobs:
                    j["ttl"] -= 1
                ready = [j for j in self.jobs if j["ttl"] <= 0]
                self.jobs = [j for j in self.jobs if j["ttl"] > 0]
                lines = [b"COUNT:%d" % len(ready)]
                for j in ready:
                    lines.append(j["uid"].encode() + b",0,1,deadbeef")
                self._out = b"\n".join(lines) + b"\nOK\n"
            elif data[:3] == b"ZQX":
                self.jobs.clear()
                self._out = b"OK\n"
            else:
                self._out = b"ERR:UNKNOWN\n"

        def readline(self, timeout=None):
            i = self._out.find(b"\n")
            if i == -1:
                r, self._out = self._out, b""
                return r
            r, self._out = self._out[:i + 1], self._out[i + 1:]
            return r

    t = LatchT()
    seen = 0
    with QueuedWorkSession(t, max_queue_depth=4, poll_interval=0.01) as s:
        def work():
            for i in range(6):
                yield (bytes([i]) * 32, bytes([i]) * 12)
        for _r in s.run(work_iter=work(), max_jobs=6):
            seen += 1
    assert seen == 6           # C2: every in-flight result collected
    assert len(sleeps) >= 1    # C1: backed off instead of busy-spinning
