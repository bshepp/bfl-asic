"""Simulator queued model + the naive-vs-queued contrast regression."""
from __future__ import annotations

from bfl_asic.transport.simulator import SimulatedDevice


def _job(i: int) -> bytes:
    from bfl_asic.protocol.queued import build_queue_job
    return build_queue_job(bytes([i % 256]) * 32, bytes([i % 256]) * 12)


def _cold() -> SimulatedDevice:
    """Return a SimulatedDevice with thermal effects disabled (heat_per_work=0)
    so thermal state never interferes with wall / queued-path tests."""
    return SimulatedDevice(heat_per_work=0.0)


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
    assert parse_details(blob).jobs_in_queue >= 1
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
