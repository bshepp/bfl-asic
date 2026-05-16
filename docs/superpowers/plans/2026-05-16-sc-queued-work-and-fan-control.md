# SC Queued-Work + Fan-Control Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an additive, opt-in BFL "SC" queued-work device path (no more 42-submission stall) plus an honest `NonceSource` and manual fan control with thermal-safety guards — without touching the naive work path or any existing command.

**Architecture:** New pure `protocol/queued.py` + `protocol/fan.py`; append-only `protocol/constants.py`; additive simulator branches (job queue, opt-in naive-42 wall, fan state, `ZCX` details); a new `QueuedWorkSession` and additive `set_fan_*` methods on `BFLDevice`; a `NonceSource` ABC sibling to `HashSource`; an additive `fan` CLI command; an opt-in hardware proof script. cgminer at `F:\experimental-projects\cgminer-ref\` is the byte-level reference (GPLv3 — facts only, never copied).

**Tech Stack:** Python ≥3.10, stdlib + existing deps; pytest. No new dependencies.

**Spec:** `docs/superpowers/specs/2026-05-16-sc-queued-work-design.md`

**Reference resolution (already determined):** `driver-bflsc.c` `drv_ver()` maps firmware `"1.0.0"`/`"1.0."`/`"1.1."` → `BFLSC_DRV1` (**V1** result-line format), `"1.2."` → `BFLSC_DRV2` (V2). The target identifies as "BitForce SHA256 SC 1.0" ⇒ **V1**. Implement V1 as default; provide V2 parsing as a selectable fallback.

**Plan-vs-spec reconciliation (deliberate):** Spec §4 says the simulator's naive-42 counter is "default on". The stronger hard constraint — *full existing suite stays green, no existing test perturbed* — requires it to **default OFF** (existing tests submit work through the simulator and must be unaffected). Therefore: `SimulatedDevice(naive_work_limit: int | None = None)`, default `None` (no wall); the contrast regression test opts in explicitly with `naive_work_limit=42`. This is the correct resolution and is reflected throughout this plan.

**Conventions:** pure builders return `bytes` (mirror `bfl_asic/protocol/commands.py`); the repo commits directly to `master`; a repository `PreToolUse` hook flags Python's dynamic code-execution builtin — not relevant to this work (none is used; do not introduce one). Every commit ends with the `Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>` trailer. Stage only the files each task lists (the working tree has unrelated untracked artifacts — never `git add -A`).

---

## File Structure

**Create**
- `bfl_asic/protocol/queued.py` — SC queued builders + parsers + `QueuedResult`/`DeviceDetails` dataclasses. Pure, no I/O.
- `bfl_asic/protocol/fan.py` — fan command builders + tolerant ack parser. Pure.
- `bfl_asic/nonce_source.py` — `NonceSource` ABC, `DeviceNonceSource`, `SimulatedNonceSource`.
- `scripts/hw/prove_queued.py` — opt-in real-hardware proof (excluded from pytest).
- `tests/test_queued_protocol.py`, `tests/test_fan_protocol.py`, `tests/test_queued_simulator.py`, `tests/test_nonce_source.py`, `tests/test_fan_cli.py`.

**Modify (additive only — no existing function/behavior changed)**
- `bfl_asic/protocol/constants.py` — append new command/framing constants.
- `bfl_asic/transport/simulator.py` — add queue/fan/details handlers + opt-in `naive_work_limit`.
- `bfl_asic/device.py` — add `QueuedWorkSession` class + `set_fan_auto`/`set_fan` methods.
- `bfl_asic/cli.py` — add a `fan` command.
- `README.md`, `CLAUDE.md`, `DEVLOG.md` — docs bookkeeping (final task).

---

## Task 1: Append protocol constants

**Files:** Modify `bfl_asic/protocol/constants.py`; Test `tests/test_queued_protocol.py`

- [ ] **Step 1: Write the failing test** — create `tests/test_queued_protocol.py`:

```python
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
```

- [ ] **Step 2: Run — expect FAIL**

Run: `python -m pytest tests/test_queued_protocol.py::test_new_constants_present_and_additive -q`
Expected: FAIL (`AttributeError: module ... has no attribute 'CMD_QJOB'`).

- [ ] **Step 3: Append to `bfl_asic/protocol/constants.py`** (add at end, change nothing above):

```python

# ---------------------------------------------------------------------------
# SC queued-work protocol (additive; naive ZDX/ZFX path is unchanged)
# Byte facts from cgminer driver-bflsc.h (GPLv3 reference; not copied).
# ---------------------------------------------------------------------------
CMD_QJOB: bytes = b"ZNX"        # queue one job
CMD_QJOBS: bytes = b"ZWX"       # queue a job pack (<=5)
CMD_QRESULTS: bytes = b"ZOX"    # query/drain results (frees queue slots)
CMD_QFLUSH: bytes = b"ZQX"      # flush the queue
CMD_DETAILS: bytes = b"ZCX"     # device details (incl. JOBS IN QUEUE)

CMD_FAN_AUTO: bytes = b"Z9X"
CMD_FAN_LEVELS: tuple[bytes, ...] = (b"Z0X", b"Z1X", b"Z2X", b"Z3X", b"Z4X")

EOB: int = 0xAA          # end-of-block marker in a queued job
SIGNATURE: int = 0xC1    # job-pack signature byte
EOW: int = 0xFE          # end-of-wrapper marker in a job pack
QUE_MAX_RESULTS: int = 8           # max results returned per ZOX read
QJOB_PAYLOAD_SIZE: int = 45        # midstate(32)+blockdata(12)+EOB(1)

RESP_SUCCESS: bytes = b"SUCCESS"
RESP_COUNT: bytes = b"COUNT:"
RESP_ERR: bytes = b"ERR:"
```

- [ ] **Step 4: Run — expect PASS**

Run: `python -m pytest tests/test_queued_protocol.py::test_new_constants_present_and_additive -q`
Expected: PASS.

- [ ] **Step 5: Confirm no regression**

Run: `python -m pytest -q`
Expected: full suite still green (constants are additive).

- [ ] **Step 6: Commit**

```bash
git add bfl_asic/protocol/constants.py tests/test_queued_protocol.py
git commit -m "ml/hw: append SC queued + fan protocol constants (additive)

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 2: `protocol/queued.py` builders

**Files:** Create `bfl_asic/protocol/queued.py`; Test `tests/test_queued_protocol.py`

- [ ] **Step 1: Add failing tests** (append to `tests/test_queued_protocol.py`):

```python
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
```

- [ ] **Step 2: Run — expect FAIL**

Run: `python -m pytest tests/test_queued_protocol.py -q -k "queue_job or simple_commands"`
Expected: FAIL (`ModuleNotFoundError: bfl_asic.protocol.queued`).

- [ ] **Step 3: Create `bfl_asic/protocol/queued.py`** (builders portion):

```python
"""Pure builders/parsers for the BFL 'SC' queued-work protocol.

Byte layout facts are taken from cgminer's driver-bflsc.h/.c (GPLv3
reference at F:\\experimental-projects\\cgminer-ref\\); no code is copied.
No I/O happens here.
"""
from __future__ import annotations

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
```

- [ ] **Step 4: Run — expect PASS**

Run: `python -m pytest tests/test_queued_protocol.py -q -k "queue_job or simple_commands"`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add bfl_asic/protocol/queued.py tests/test_queued_protocol.py
git commit -m "ml/hw: SC queued-work command builders (ZNX/ZWX/ZOX/ZQX/ZCX)

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 3: `protocol/queued.py` parsers (V1 default, V2 fallback)

**Files:** Modify `bfl_asic/protocol/queued.py`; Test `tests/test_queued_protocol.py`

> Reference confirmation step (the implementer MUST do this): open `F:\experimental-projects\cgminer-ref\driver-bflsc.c`, find the QRES/result parsing and `getinfo()`/details parsing. Confirm (a) the result block begins with a `COUNT:` line, (b) per-result fields are comma-separated, (c) V1 field order is `UID, CC, NONCECOUNT, nonce, nonce, ...` (header: `QUE_UID=0, QUE_CC=1, QUE_NONCECOUNT_V1=2, QUE_FLD_MIN_V1=3`), V2 inserts `CHIP` at index 2 (`QUE_NONCECOUNT_V2=3, QUE_FLD_MIN_V2=4`), (d) details lines are `KEY : VALUE`. Transcribe one real V1 result block and one details block from comments/log strings in the .c as the verbatim fixtures used below; if the .c shows the separator is not a comma, adjust the parser and fixtures together to match what the .c actually does (do not guess — match the reference).

- [ ] **Step 1: Add failing tests** (append to `tests/test_queued_protocol.py`):

```python
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
    # V2 inserts CHIP at index 2; noncecount at 3; nonces from 4
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
```

- [ ] **Step 2: Run — expect FAIL**

Run: `python -m pytest tests/test_queued_protocol.py -q -k "parse_"`
Expected: FAIL (`ImportError: cannot import name 'parse_queue_results'`).

- [ ] **Step 3: Append parsers + dataclasses to `bfl_asic/protocol/queued.py`:**

```python


@dataclass
class QueuedResult:
    """One completed job's result from a `ZOX` drain."""

    uid: str
    nonces: list[int] = field(default_factory=list)
    raw: bytes = b""


@dataclass
class DeviceDetails:
    """Parsed `ZCX` details."""

    fields: dict[str, str] = field(default_factory=dict)

    @property
    def jobs_in_queue(self) -> int:
        v = self.fields.get("JOBS IN QUEUE", "0").strip()
        try:
            return int(v)
        except ValueError:
            return 0


def _result_lines(raw: bytes) -> list[str]:
    text = raw.decode("ascii", errors="replace")
    out: list[str] = []
    for line in text.splitlines():
        s = line.strip()
        if not s or s in ("OK", "SUCCESS") or s.startswith("COUNT:"):
            continue
        out.append(s)
    return out


def parse_queue_results(raw: bytes, version: str = "v1") -> list[QueuedResult]:
    """Parse a `ZOX` result block.

    V1 fields: ``UID, CC, NONCECOUNT, nonce, ...``
    V2 fields: ``UID, CC, CHIP, NONCECOUNT, nonce, ...``
    Firmware "SC 1.0" is V1 (driver-bflsc.c drv_ver()).
    """
    nonce_start = 3 if version == "v1" else 4
    results: list[QueuedResult] = []
    for line in _result_lines(raw):
        parts = [p.strip() for p in line.split(",") if p.strip() != ""]
        if len(parts) < nonce_start:
            continue
        uid = parts[0]
        nonces = [int(p, 16) for p in parts[nonce_start:]]
        results.append(QueuedResult(uid=uid, nonces=nonces,
                                     raw=line.encode("ascii")))
    return results


def parse_details(raw: bytes) -> DeviceDetails:
    text = raw.decode("ascii", errors="replace")
    fields: dict[str, str] = {}
    for line in text.splitlines():
        s = line.strip()
        if not s or s in ("OK", "SUCCESS") or ":" not in s:
            continue
        key, _, val = s.partition(":")
        fields[key.strip()] = val.strip()
    return DeviceDetails(fields=fields)
```

- [ ] **Step 4: Run — expect PASS**

Run: `python -m pytest tests/test_queued_protocol.py -q`
Expected: all PASS. (If the reference-confirmation step found a non-comma separator, the fixtures + `split(",")` were adjusted together to match the .c and still pass.)

- [ ] **Step 5: Commit**

```bash
git add bfl_asic/protocol/queued.py tests/test_queued_protocol.py
git commit -m "ml/hw: SC result/details parsers (V1 default, V2 fallback)

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 4: `protocol/fan.py`

**Files:** Create `bfl_asic/protocol/fan.py`; Test `tests/test_fan_protocol.py`

- [ ] **Step 1: Create `tests/test_fan_protocol.py`:**

```python
"""Fan-control protocol: pure builders/ack. No hardware."""
from __future__ import annotations

import pytest

from bfl_asic.protocol.fan import build_fan_auto, build_fan_level, parse_fan_ack


def test_build_fan_auto():
    assert build_fan_auto() == b"Z9X"


@pytest.mark.parametrize("level,expected",
                         [(0, b"Z0X"), (1, b"Z1X"), (2, b"Z2X"),
                          (3, b"Z3X"), (4, b"Z4X")])
def test_build_fan_level(level, expected):
    assert build_fan_level(level) == expected


@pytest.mark.parametrize("bad", [-1, 5, 99])
def test_build_fan_level_rejects_out_of_range(bad):
    with pytest.raises(ValueError):
        build_fan_level(bad)


def test_parse_fan_ack_tolerant():
    # cgminer just READ_NLs the reply; exact token is unconfirmed.
    assert parse_fan_ack(b"OK\n") is True
    assert parse_fan_ack(b"SUCCESS\n") is True
    assert parse_fan_ack(b"anything\n") is True
    assert parse_fan_ack(b"ERR:INVALID DATA\n") is False
    assert parse_fan_ack(b"") is False
```

- [ ] **Step 2: Run — expect FAIL**

Run: `python -m pytest tests/test_fan_protocol.py -q`
Expected: FAIL (`ModuleNotFoundError: bfl_asic.protocol.fan`).

- [ ] **Step 3: Create `bfl_asic/protocol/fan.py`:**

```python
"""Pure fan-control command builders for the BFL SC firmware.

cgminer driver-bflsc only ever sends Z9X (auto) and Z4X (max) in
practice; Z0X-Z3X are firmware-defined but their per-level behavior is
hardware-unconfirmed. The ack token is not pinned by the reference
(cgminer just reads one line) — parse_fan_ack is deliberately tolerant.
"""
from __future__ import annotations

from bfl_asic.protocol.constants import CMD_FAN_AUTO, CMD_FAN_LEVELS, RESP_ERR


def build_fan_auto() -> bytes:
    """`Z9X` — hand the fan back to firmware thermal management."""
    return CMD_FAN_AUTO


def build_fan_level(level: int) -> bytes:
    """`Z0X`..`Z4X` — set a fixed fan level (0..4)."""
    if not isinstance(level, int) or not 0 <= level <= 4:
        raise ValueError(f"fan level must be an int in 0..4, got {level!r}")
    return CMD_FAN_LEVELS[level]


def parse_fan_ack(raw: bytes) -> bool:
    """True if the device acked; False on empty or an ERR: reply."""
    s = raw.strip()
    if not s:
        return False
    return not s.startswith(RESP_ERR)
```

- [ ] **Step 4: Run — expect PASS**

Run: `python -m pytest tests/test_fan_protocol.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add bfl_asic/protocol/fan.py tests/test_fan_protocol.py
git commit -m "hw: fan-control protocol builders + tolerant ack parser

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 5: Simulator — queue model, opt-in 42-wall, fan state, ZCX

**Files:** Modify `bfl_asic/transport/simulator.py`; Test `tests/test_queued_simulator.py`

- [ ] **Step 1: Create `tests/test_queued_simulator.py`:**

```python
"""Simulator queued model + the naive-vs-queued contrast regression."""
from __future__ import annotations

from bfl_asic.transport.simulator import SimulatedDevice


def _job(i: int) -> bytes:
    from bfl_asic.protocol.queued import build_queue_job
    return build_queue_job(bytes([i % 256]) * 32, bytes([i % 256]) * 12)


def test_naive_wall_off_by_default():
    # Default sim has NO wall: existing behaviour preserved.
    d = SimulatedDevice()
    from bfl_asic.protocol.commands import build_work
    for _ in range(60):
        assert d.process_command(build_work(bytes(32), bytes(12))) == b"OK\n"


def test_naive_wall_when_opted_in():
    d = SimulatedDevice(naive_work_limit=42)
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
```

- [ ] **Step 2: Run — expect FAIL**

Run: `python -m pytest tests/test_queued_simulator.py -q`
Expected: FAIL (`TypeError: ... unexpected keyword 'naive_work_limit'` / queued commands unhandled).

- [ ] **Step 3: Modify `bfl_asic/transport/simulator.py`** — three additive changes (do not alter existing handlers):

(a) Extend `__init__` signature and state (add the new keyword **after** existing ones with a default; add new attributes at the end of `__init__`):

```python
        error_rate: float = 0.0,
        naive_work_limit: int | None = None,
    ) -> None:
```
and at the end of `__init__` (after `self.device_info = ...`):
```python
        # Naive ZDX path: optional firmware-style wall (opt-in; default
        # off so existing behaviour/tests are unchanged).
        self.naive_work_limit = naive_work_limit
        self._naive_zdx_count = 0
        # SC queued model
        self._job_queue: list[tuple[bytes, bytes]] = []
        self._results: list[tuple[str, list[int]]] = []
        self._uid = 0
        # Fan state
        self.fan_mode: str = "auto"
        self.fan_level: int | None = None
```

(b) Extend `_dispatch` — add these branches **before** the final `return b"ERR:UNKNOWN\n"` (leave all existing branches exactly as they are; note ZNX/ZWX/ZOX/ZQX/ZCX/Z9X/Z0X.. are distinct prefixes from ZDX/ZFX/ZGX/ZLX/ZTX so ordering is safe):

```python
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
        if data.startswith(b"Z9X"):
            self.fan_mode, self.fan_level = "auto", None
            return b"OK\n"
        for lvl in range(5):
            if data.startswith(b"Z%dX" % lvl):
                self.fan_mode, self.fan_level = "fixed", lvl
                return b"OK\n"
```

(c) Guard the naive `_handle_work` with the opt-in wall — change the **first lines** of `_handle_work` only (existing logic below is untouched):

```python
    def _handle_work(self, data: bytes) -> bytes:
        if self.naive_work_limit is not None:
            self._naive_zdx_count += 1
            if self._naive_zdx_count > self.naive_work_limit:
                return b""  # documented stall: empty response, no reset
        if self.state is DeviceState.OVERHEATED:
            return b"ERR:OVERHEATED\n"
        ...  # rest unchanged
```

(d) Add the new handler methods (anywhere in the class body, e.g. after `_handle_result`):

```python
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
        return (b"FIRMWARE: 1.0.0\nENGINES: 1\n"
                b"JOBS IN QUEUE: %d\nCHIP PARALLELIZATION: NO\nOK\n"
                % len(self._job_queue))
```

- [ ] **Step 4: Run — expect PASS**

Run: `python -m pytest tests/test_queued_simulator.py -q`
Expected: all PASS — including the headline `test_queued_path_sustains_well_past_42` (500 ≫ 42) and `test_naive_wall_when_opted_in` (stall at 43).

- [ ] **Step 5: Full-suite no-regression (critical — naive default off)**

Run: `python -m pytest -q`
Expected: entire pre-existing suite green (default `naive_work_limit=None` ⇒ zero behavior change). Report the total.

- [ ] **Step 6: Commit**

```bash
git add bfl_asic/transport/simulator.py tests/test_queued_simulator.py
git commit -m "hw: simulator queued model + opt-in naive-42 wall + fan state

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 6: `QueuedWorkSession` on `BFLDevice`

**Files:** Modify `bfl_asic/device.py` (additive class only); Test `tests/test_queued_simulator.py`

- [ ] **Step 1: Add failing test** (append to `tests/test_queued_simulator.py`):

```python
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
```

- [ ] **Step 2: Run — expect FAIL**

Run: `python -m pytest tests/test_queued_simulator.py::test_queued_work_session_runs_past_42 -q`
Expected: FAIL (`ImportError: cannot import name 'QueuedWorkSession'`).

- [ ] **Step 3: Append `QueuedWorkSession` to `bfl_asic/device.py`** (new class at end of file; do not modify `BFLDevice`):

```python


class QueuedWorkSession:
    """Sustained SC queued-work session (opt-in; the naive BFLDevice
    work path is unchanged). Continuously drains results so the
    firmware queue never saturates — the real-miner pattern.
    """

    def __init__(self, transport, *, max_queue_depth: int = 32) -> None:
        self._t = transport
        self._max_depth = max_queue_depth

    def __enter__(self) -> "QueuedWorkSession":
        if not self._t.is_open:
            self._t.open()
        return self

    def __exit__(self, *exc) -> None:
        from bfl_asic.protocol.queued import build_queue_flush
        try:
            self._t.write(build_queue_flush())
            self._t.readline()
        except Exception:
            pass

    def _jobs_in_queue(self) -> int:
        from bfl_asic.protocol.queued import build_details, parse_details
        self._t.write(build_details())
        raw = b""
        for _ in range(16):
            line = self._t.readline()
            raw += line
            if line.strip() in (b"OK", b"SUCCESS") or not line:
                break
        return parse_details(raw).jobs_in_queue

    def submit(self, midstate: bytes, tail: bytes) -> None:
        from bfl_asic.protocol.queued import build_queue_job
        self._t.write(build_queue_job(midstate, tail))
        self._t.readline()  # ack

    def drain(self) -> list:
        from bfl_asic.protocol.queued import (
            build_queue_results, parse_queue_results)
        self._t.write(build_queue_results())
        raw = b""
        for _ in range(64):
            line = self._t.readline()
            raw += line
            if line.strip() in (b"OK", b"SUCCESS") or not line:
                break
        return parse_queue_results(raw, version="v1")

    def run(self, *, work_iter, max_jobs=None, duration=None):
        """Submit from *work_iter*, draining continuously. Yields
        QueuedResult objects. Stops at max_jobs submitted or duration s.
        """
        import time
        submitted = 0
        deadline = (time.monotonic() + duration) if duration else None
        exhausted = False
        while True:
            while (not exhausted
                   and (max_jobs is None or submitted < max_jobs)
                   and self._jobs_in_queue() < self._max_depth):
                try:
                    mid, tail = next(work_iter)
                except StopIteration:
                    exhausted = True
                    break
                self.submit(mid, tail)
                submitted += 1
            for r in self.drain():
                yield r
            if deadline and time.monotonic() >= deadline:
                break
            if exhausted and self._jobs_in_queue() == 0:
                break
            if (max_jobs is not None and submitted >= max_jobs
                    and self._jobs_in_queue() == 0):
                break
```

- [ ] **Step 4: Run — expect PASS**

Run: `python -m pytest tests/test_queued_simulator.py -q`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add bfl_asic/device.py tests/test_queued_simulator.py
git commit -m "hw: QueuedWorkSession (continuous drain + backpressure)

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 7: `NonceSource`

**Files:** Create `bfl_asic/nonce_source.py`; Test `tests/test_nonce_source.py`

- [ ] **Step 1: Create `tests/test_nonce_source.py`:**

```python
"""NonceSource: honest device-as-nonce-stream surface (NOT a HashSource)."""
from __future__ import annotations

from bfl_asic.nonce_source import (
    NonceSource, SimulatedNonceSource, DeviceNonceSource)


def test_simulated_nonce_source_yields_results():
    src = SimulatedNonceSource()
    out = list(src.results(count=50))
    assert len(out) == 50
    assert src.name()


def test_nonce_source_is_not_a_hashsource():
    from bfl_asic.stats.engine import HashSource
    assert not issubclass(NonceSource, HashSource)
    assert not issubclass(SimulatedNonceSource, HashSource)
    assert not issubclass(DeviceNonceSource, HashSource)
```

- [ ] **Step 2: Run — expect FAIL**

Run: `python -m pytest tests/test_nonce_source.py -q`
Expected: FAIL (`ModuleNotFoundError: bfl_asic.nonce_source`).

- [ ] **Step 3: Create `bfl_asic/nonce_source.py`:**

```python
"""Honest device-backed nonce stream.

This is deliberately NOT a `bfl_asic.stats.engine.HashSource`. The BFL
device only ever returns winning *nonces*, never SHA-256d digests, so it
cannot feed the digest pipelines (stats/randomness/ml). A NonceSource
yields work-results (nonces) at sustained hardware rate via the queued
path — useful for proof-of-work / hashrate work, nothing dressed up.
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
        ...

    @abstractmethod
    def name(self) -> str:
        ...


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

        with QueuedWorkSession(t) as s:
            yield from s.run(work_iter=work(), max_jobs=n,
                             duration=duration)

    def name(self) -> str:
        return "simulated-nonce-source"


class DeviceNonceSource(NonceSource):
    """Real-hardware nonce stream via a QueuedWorkSession over *transport*."""

    def __init__(self, transport, work_iter) -> None:
        self._t = transport
        self._work = work_iter

    def results(self, count: int | None = None,
                duration: float | None = None) -> Iterator[QueuedResult]:
        from bfl_asic.device import QueuedWorkSession
        with QueuedWorkSession(self._t) as s:
            yield from s.run(work_iter=self._work, max_jobs=count,
                             duration=duration)

    def name(self) -> str:
        return "device-nonce-source"
```

- [ ] **Step 4: Run — expect PASS**

Run: `python -m pytest tests/test_nonce_source.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add bfl_asic/nonce_source.py tests/test_nonce_source.py
git commit -m "hw: honest NonceSource (device yields nonces, not digests)

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 8: `BFLDevice.set_fan_auto` / `set_fan` + thermal safety

**Files:** Modify `bfl_asic/device.py` (additive methods); Test `tests/test_fan_protocol.py`

- [ ] **Step 1: Add failing test** (append to `tests/test_fan_protocol.py`):

```python
def test_device_fan_methods_and_warning(recwarn):
    from bfl_asic.transport.simulator import SimulatorTransport
    from bfl_asic.device import BFLDevice

    with BFLDevice(SimulatorTransport()) as dev:
        assert dev.set_fan_auto() is True
        assert dev.set_fan(4) is True            # fixed level
    msgs = [str(w.message) for w in recwarn.list]
    assert any("thermal" in m.lower() for m in msgs)  # safety warning fired
```

- [ ] **Step 2: Run — expect FAIL**

Run: `python -m pytest tests/test_fan_protocol.py::test_device_fan_methods_and_warning -q`
Expected: FAIL (`AttributeError: 'BFLDevice' object has no attribute 'set_fan_auto'`).

- [ ] **Step 3: Add two methods to `BFLDevice` in `bfl_asic/device.py`** (new methods only — place near `get_temperature`/`get_voltage`; do not modify those):

```python
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
```

- [ ] **Step 4: Run — expect PASS**

Run: `python -m pytest tests/test_fan_protocol.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add bfl_asic/device.py tests/test_fan_protocol.py
git commit -m "hw: additive BFLDevice.set_fan_auto/set_fan with thermal warning

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 9: `fan` CLI command

**Files:** Modify `bfl_asic/cli.py` (additive command); Test `tests/test_fan_cli.py`

- [ ] **Step 1: Create `tests/test_fan_cli.py`:**

```python
"""fan CLI command (simulator-backed)."""
from __future__ import annotations

from click.testing import CliRunner

from bfl_asic.cli import main


def test_fan_auto_ok():
    r = CliRunner().invoke(main, ["--simulate", "fan", "auto"])
    assert r.exit_code == 0, r.output
    assert "auto" in r.output.lower()


def test_fan_fixed_level_warns():
    r = CliRunner().invoke(main, ["--simulate", "fan", "4"])
    assert r.exit_code == 0, r.output
    assert "thermal" in r.output.lower()  # safety warning surfaced


def test_fan_rejects_bad_arg():
    r = CliRunner().invoke(main, ["--simulate", "fan", "9"])
    assert r.exit_code != 0


def test_help_lists_fan():
    r = CliRunner().invoke(main, ["--help"])
    assert r.exit_code == 0 and "fan" in r.output
```

- [ ] **Step 2: Run — expect FAIL**

Run: `python -m pytest tests/test_fan_cli.py -q`
Expected: FAIL (no `fan` command).

- [ ] **Step 3: Append a `fan` command to `bfl_asic/cli.py`** (additive; place near the `temperature` command; do not modify existing commands):

```python
@main.command(name="fan")
@click.argument("setting")
@click.pass_context
def fan_cmd(ctx: click.Context, setting: str) -> None:
    """Set fan: 'auto' (Z9X) or a fixed level 0-4 (Z0X-Z4X).

    Fixed levels override firmware thermal management.
    """
    transport = get_transport(
        ctx.obj["port"], ctx.obj["simulate"], ctx.obj["baudrate"],
    )
    with BFLDevice(transport) as device:
        if setting == "auto":
            ok = device.set_fan_auto()
            click.echo(f"Fan set to auto (firmware-managed): {'OK' if ok else 'FAILED'}")
            return
        try:
            level = int(setting)
        except ValueError:
            raise click.BadParameter("setting must be 'auto' or 0-4")
        if not 0 <= level <= 4:
            raise click.BadParameter("fixed fan level must be 0-4")
        click.echo(
            "WARNING: fixed fan level overrides firmware thermal "
            "management; a low level during hashing can cause thermal "
            "damage. Restore with 'fan auto' when done."
        )
        try:
            temp = device.get_temperature()
            click.echo(f"  temp before: {temp.sensors}")
        except Exception:
            pass
        ok = device.set_fan(level)
        click.echo(f"Fan set to fixed level {level}: {'OK' if ok else 'FAILED'}")
```

> Note: `device.set_fan(level)` also emits a `warnings.warn`; the CLI prints its own explicit `WARNING:` line so the safety message is visible in `r.output` regardless of warning filters (the test asserts on stdout).

- [ ] **Step 4: Run — expect PASS**

Run: `python -m pytest tests/test_fan_cli.py -q`
Expected: PASS.

- [ ] **Step 5: Confirm torch-free / no regression**

Run: `python -m pytest -q -m "not slow"`
Expected: green; report total.

- [ ] **Step 6: Commit**

```bash
git add bfl_asic/cli.py tests/test_fan_cli.py
git commit -m "hw: additive 'fan' CLI command with thermal-safety warning

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 10: Opt-in hardware proof script

**Files:** Create `scripts/hw/prove_queued.py` (NOT under `tests/`, never collected by pytest)

- [ ] **Step 1: Create `scripts/hw/prove_queued.py`:**

```python
#!/usr/bin/env python3
"""OPT-IN hardware proof: the SC queued path defeats the 42-wall.

Run against a REAL Jalapeno (default COM3). Excluded from pytest.
Submits >42 jobs via QueuedWorkSession; the naive path stalls at 43,
this must not. Always flushes the queue and restores fan AUTO on exit,
including on exception.

Usage:  python scripts/hw/prove_queued.py --port COM3 --jobs 200
"""
from __future__ import annotations

import argparse
import sys
import time


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", default="COM3")
    ap.add_argument("--jobs", type=int, default=200)
    args = ap.parse_args()

    from bfl_asic.transport.serial import SerialTransport
    from bfl_asic.device import BFLDevice, QueuedWorkSession

    t = SerialTransport(port=args.port)
    t.open()
    try:
        with BFLDevice(t) as dev:
            info = dev.identify()
            print(f"[hw] {info.model}")
        n = 0
        with QueuedWorkSession(t) as s:
            def work():
                for i in range(args.jobs):
                    yield (bytes([i % 256]) * 32, bytes([i % 256]) * 12)
            t0 = time.monotonic()
            for _r in s.run(work_iter=work(), max_jobs=args.jobs):
                n += 1
            dt = time.monotonic() - t0
        ok = n >= args.jobs
        print(f"[hw] completed {n}/{args.jobs} queued jobs in {dt:.1f}s "
              f"-> {'PASS (42-wall defeated)' if ok else 'FAIL'}")
        return 0 if ok else 1
    finally:
        # Safety: never leave the device queued or the fan in a fixed level.
        try:
            from bfl_asic.protocol.queued import build_queue_flush
            t.write(build_queue_flush()); t.readline()
        except Exception:
            pass
        try:
            with BFLDevice(t) as dev:
                dev.set_fan_auto()
        except Exception:
            pass
        t.close()


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Verify it is NOT collected by pytest**

Run: `python -m pytest -q --collect-only 2>&1 | grep -c "prove_queued" || true`
Expected: `0` (scripts/ is outside `testpaths=["tests"]`).

- [ ] **Step 3: Syntax-check only (no hardware in CI)**

Run: `python -c "import ast; ast.parse(open('scripts/hw/prove_queued.py').read()); print('ok')"`
Expected: `ok`.

- [ ] **Step 4: Commit**

```bash
git add scripts/hw/prove_queued.py
git commit -m "hw: opt-in hardware proof script (queued >42, safe restore)

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 11: Docs bookkeeping + full verification

**Files:** Modify `DEVLOG.md`, `CLAUDE.md`, `README.md`

- [ ] **Step 1: Full suite green**

Run: `python -m pytest -q`
Expected: all green; record the new total (was 725 + new tests).

- [ ] **Step 2: Correct `DEVLOG.md` §4** — append a dated correction subsection immediately after the existing "#### 4. Firmware Work Limit — 42 Submissions Per Session" block (preserve the original observation; correct the conclusion):

```markdown

##### 2026-05-16 correction — the "42 limit" is a naive-path artifact

The original conclusion ("firmware-level counter ... only a power cycle
resets it ... apps must power-cycle") is **over-stated**. Empirical
disproof: this device was run as a Bitcoin miner for days / thousands of
submissions with zero power cycles. cgminer/bfgminer drive the SC
*queued* protocol (`ZNX`/`ZWX` + continuous `ZOX` result-drain +
`ZCX` `JOBS IN QUEUE` backpressure) and never approach 42. The 42 wall
is an artifact of the naive `ZDX`/`ZFX` path never draining the queue —
not a hardware ceiling. Fixed additively by `QueuedWorkSession`
(`bfl_asic/device.py`); the naive path is intentionally left unchanged
as the honest demonstration of the wall. See
`docs/superpowers/specs/2026-05-16-sc-queued-work-design.md`.
```

- [ ] **Step 3: Update `CLAUDE.md`** — under "Hardware Notes", replace the 42-limit bullet's claim with a corrected, cross-referenced version (keep the bullet; fix the content):

```markdown
- The naive `ZDX`/`ZFX` work path stalls after **42 submissions per power
  cycle** — but this is an artifact of never draining the firmware queue,
  **not** a hardware limit (the device mined for days via cgminer without
  power-cycling). Use `QueuedWorkSession` (SC queued `ZNX`/`ZOX`/`ZCX`
  path) for sustained work. Naive path left unchanged on purpose.
```
Also add to the Application-layer notes: `bfl_asic/nonce_source.py` (honest device nonce stream — not a HashSource) and the additive `fan` command / `set_fan*` (thermal-safety-guarded).

- [ ] **Step 4: Update `README.md`** — add a short "Sustained device work (SC queued path)" subsection after the protocol section, and a one-liner for `bfl-asic -p COM3 fan auto|0-4` with the thermal-safety caveat; refresh the test count to Step 1's number.

- [ ] **Step 5: Commit**

```bash
git add DEVLOG.md CLAUDE.md README.md
git commit -m "docs: correct the 42-limit conclusion; document queued path + fan

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Self-Review

**1. Spec coverage:**
- §3 queued commands/builders → Tasks 1–2. Parsers V1/V2 + details → Task 3. Fan protocol → Task 4. Simulator queue + opt-in 42-wall + fan state + ZCX → Task 5. `QueuedWorkSession` (drain, backpressure, telemetry-capable, flush-on-exit) → Task 6. `NonceSource` (+not-a-HashSource assertion) → Task 7. `set_fan_*` + thermal warning → Task 8. `fan` CLI → Task 9. Hardware proof script (safe restore) → Task 10. DEVLOG §4 correction + docs → Task 11. §5 thermal safety → Tasks 8/9/10 (warnings + restore-on-exit). §7 testing incl. headline contrast regression → Task 5. ✓ All spec sections mapped.
- Telemetry hook (`telemetry_interval`, spec §4): the `QueuedWorkSession.run` loop structure supports inserting periodic temp/voltage reads; this plan ships the loop without the optional hook wired to a parameter to keep Task 6 focused (YAGNI — no consumer needs it yet). **Documented divergence**, not a silent gap: the spec lists it as "optional"; add later if a consumer appears. No task depends on it.

**2. Placeholder scan:** No TBD/TODO/"handle errors"/"similar to". Every code step is complete; every run step has an exact command + expected result. The one reference-confirmation instruction (Task 3) is explicit and bounded (confirm separator from the .c; fixtures+parser adjusted together), not a placeholder.

**3. Type consistency:** `build_queue_job(midstate,tail)`, `QueuedResult{uid:str,nonces:list[int],raw:bytes}`, `DeviceDetails.jobs_in_queue:int`, `parse_queue_results(raw, version="v1")`, `QueuedWorkSession(transport, *, max_queue_depth=32)` with `.submit/.drain/.run(work_iter=,max_jobs=,duration=)`, `NonceSource.results(count=,duration=)`, `build_fan_level(level:int)`, `BFLDevice.set_fan_auto()->bool`/`set_fan(level)->bool` — names/signatures identical across every task that uses them. Simulator `naive_work_limit:int|None=None` consistent in Tasks 5/6/10. `SimulatedDevice(simulated_hashrate=...)` matches the existing ctor.

No issues requiring inline fixes beyond the documented telemetry-hook deferral.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-05-16-sc-queued-work-and-fan-control.md`.
