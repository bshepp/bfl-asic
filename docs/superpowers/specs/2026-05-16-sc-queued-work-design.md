# BFL SC Queued-Work Path — Design Spec

- **Date:** 2026-05-16
- **Status:** Approved (brainstorming complete; pending written-spec review)
- **Author:** Brian Sheppard + Claude
- **Scope:** One new additive subsystem (SC queued-work protocol + sustained session + `NonceSource`), plus append-only edits to `protocol/constants.py` and `transport/simulator.py`, and a new opt-in hardware script. No existing pipeline, command, or naive work path is modified.
- **Reference:** cgminer `driver-bflsc.h` / `driver-bflsc.c` at `F:\experimental-projects\cgminer-ref\` (GPLv3 — protocol facts only, **no code vendored or copied**; clean reimplementation).

---

## 1. Context and motivation

`bfl-asic`'s device path uses a naive single-job model: `ZDX` submit → `ZFX` poll, one work unit at a time (`bfl_asic/device.py`). The DEVLOG documents (4× reproduced) that the SC firmware stops accepting `ZDX` after 42 cumulative submissions per power cycle. This was over-stated as a hardware ceiling. It is not: the device's owner ran it as a Bitcoin miner for days/thousands of submissions with zero power cycles. cgminer/bfgminer (`driver-bflsc.c`) drive the device through its **queued** protocol and **continuously drain results**, which frees the firmware's queue bookkeeping — so they never approach 42. The 42-wall is an artifact of the naive path never draining, not a firmware limit.

This spec adds the queued path as an **additive, opt-in** capability so the toolkit can sustain work like a real miner, plus an honest toolkit-facing surface.

## 2. Goals and non-goals

**Goals**
- An opt-in SC queued-work device path (`ZNX`/`ZWX`/`ZOX`/`ZQX`/`ZCX`) with continuous result-drain and `JOBS IN QUEUE` backpressure — the real-miner pattern that does not hit 42.
- A sustained `QueuedWorkSession` (run for N jobs or T seconds; yields results) with an optional periodic temp/voltage telemetry hook.
- An honest `NonceSource` abstraction (sibling to `HashSource`) — yields device-found nonces, explicitly **not** a digest source.
- CI proves the fix **without hardware**: the simulator models both the naive 42-wall and the queued drain; a regression test asserts naive stalls at 43 while queued sustains ≫42.
- A guarded hardware proof script the user runs on the real Jalapeno (COM3, confirmed alive).
- Correct the DEVLOG §4 conclusion.

**Non-goals**
- The naive `submit_work`/`submit_and_wait`/`poll_result`/`hash_data` path is **not modified** (it remains the honest demonstration of the 42-wall).
- **No** `ZMX` firmware-flash support (bricking-capable; explicitly excluded).
- **No** XLINK daisy-chain support (single-device only).
- **No** device-backed `HashSource` (the device yields nonces, never digests — physically impossible; documented).
- Fan control (`Z9X`/`Z0X..Z4X`), `ZJX` firmware string, `ZUX`/`ZSX` load/save strings: **out of scope here**, recorded as future capabilities (§8).

## 3. Protocol facts (from the reference; reimplemented cleanly)

- **Commands:** `ZNX` queue one job; `ZWX` queue a job pack (**max 5 jobs/write**, `QueueJobPackStructure`: payloadSize, signature `0xc1`, jobsInArray, jobs[5], endOfWrapper `0xfe`); `ZOX` query/drain results; `ZQX` flush queue; `ZCX` device details.
- **Queued job packet** (`ZNX`): `payloadSize` + 32-byte midstate + 12-byte blockData(tail) + EOB `0xaa` (`BFLSC_QJOBSIZ = 32+12+1 = 45`).
- **Result block** (`ZOX` reply): starts `COUNT:`; ≥3 lines; per-result fields — V1: `UID, CC, NONCECOUNT, nonce…`; V2 inserts a `CHIP` field (V1 nonce-count at field 2, V2 at field 3). `QUE_MAX_RESULTS = 8` is the max results returned **per `ZOX` read** (a drain batch size), *not* the job-queue depth — those are distinct. The Jalapeno SC 1.0's variant is determined from `.c` logic and confirmed on hardware.
- **Details** (`ZCX` reply): keyed lines incl. `FIRMWARE`, `ENGINES`, `JOBS IN QUEUE`, `XLINK MODE`, `XLINK PRESENT`, `DEVICES IN CHAIN`, `CHAIN PRESENCE MASK`, `CHIP PARALLELIZATION`.
- **Reply tokens:** `OK\n`, `SUCCESS\n`, `COUNT:`, error family `ERR:` (`ERR:TIMEOUT`, `ERR:INVALID DATA`, `ERR:SIGNATURE`). Existing `>>>>>>>>` delimiter and `RESP_*` tokens unchanged.

## 4. Architecture (additive only)

Mirrors the existing protocol / transport / device / application layering and the `HashSource` precedent.

- **`bfl_asic/protocol/queued.py`** (new, pure, no I/O)
  - Builders: `build_queue_job(midstate, tail) -> bytes` (`ZNX` + 45-byte payload), `build_queue_job_pack(jobs[≤5]) -> bytes` (`ZWX`), `build_queue_results() -> bytes` (`ZOX`), `build_queue_flush() -> bytes` (`ZQX`), `build_details() -> bytes` (`ZCX`).
  - Parsers: `parse_queue_results(raw) -> list[QueuedResult]` (handles `COUNT:` block, V1 **and** V2 field layouts), `parse_details(raw) -> DeviceDetails` (dict-like; `.jobs_in_queue: int`).
  - Dataclasses: `QueuedResult{uid:int, nonces:list[int], raw:bytes}`, `DeviceDetails`.
- **`bfl_asic/protocol/constants.py`** (append-only) — add `CMD_QJOB=b"ZNX"`, `CMD_QJOBS=b"ZWX"`, `CMD_QRESULTS=b"ZOX"`, `CMD_QFLUSH=b"ZQX"`, `CMD_DETAILS=b"ZCX"`, framing `EOB=0xAA`, `SIGNATURE=0xC1`, `EOW=0xFE`, `QUE_MAX_RESULTS=8`, `QJOB_PAYLOAD_SIZE=45`, `RESP_SUCCESS=b"SUCCESS"`, `RESP_COUNT=b"COUNT:"`, `RESP_ERR=b"ERR:"`. Existing names untouched.
- **`bfl_asic/transport/simulator.py`** (additive) — gains: (a) a finite job queue, `ZNX`/`ZWX` enqueue, internal SHA-256d compute (reusing existing logic) into a results buffer, `ZOX` drain that returns and frees results, `ZCX` reporting `JOBS IN QUEUE`, `ZQX` flush; (b) a **naive-path cumulative-`ZDX` counter that stalls on the 43rd** (configurable, default on) so the contrast is regression-testable. Existing simulator behavior for ZGX/ZLX/ZTX/ZFX/ZDX(≤42) unchanged.
- **`bfl_asic/device.py`** (additive — new class only, existing methods untouched)
  - `QueuedWorkSession(transport)` context manager: `submit(midstate, tail)`; internal drain loop that issues `ZOX` on a cadence (each read returns up to `QUE_MAX_RESULTS`=8 results and frees those slots); submission backpressure throttles on `ZCX` `JOBS IN QUEUE` staying under a configured `max_queue_depth` cap (default derived from the device's reported capacity, not hardcoded to the 8 results-batch); `run(max_jobs=None, duration=None, work_iter=None) -> Iterator[QueuedResult]`, `flush()`, optional `telemetry_interval` calling existing temp/voltage reads from inside the loop. `ZQX` on close.
- **`bfl_asic/nonce_source.py`** (new) — `NonceSource` ABC (`results(count|duration) -> Iterator[QueuedResult]`, `name()`), `DeviceNonceSource` (wraps `QueuedWorkSession`), `SimulatedNonceSource`. Module docstring states plainly it is **not** a `HashSource` and why (nonce-only hardware), and is intentionally not consumed by stats/ML/randomness.
- **`scripts/hw/prove_queued.py`** (new, opt-in, excluded from pytest) — opens a real port (default `COM3`), submits > 42 queued jobs via `QueuedWorkSession`, asserts no stall, prints sustained count/rate and `ZCX` details. The only real-silicon validation.

## 5. Non-interference guarantee

- Strictly additive: zero edits to existing functions; only new files + append-only constants + additive simulator branches.
- Software-analysis stack (stats/randomness/dynamics/ML, `SoftwareHashEngine`) never touches the device — categorically unaffected.
- `ZGX`/`ZLX`/`ZTX`/`ZCX` are single-stage firmware commands serviced independently of the work queue (work even after the naive 42-stall) — non-work info gathering is unaffected by either path.
- **Serial-concurrency caveat (documented, not a defect):** the port is a single half-duplex single-threaded stream; while a `QueuedWorkSession` loop runs it owns the port, so temp/voltage must be sampled from inside the session (the `telemetry_interval` hook), not a competing thread — exactly how cgminer does it. With no session running, behavior is identical to today.

## 6. Error handling

Reuses the `BFLError` hierarchy. Distinct signals:
- Queue full → backpressure (expected; wait/drain, **not** an exception).
- Drain/read timeout (`ERR:TIMEOUT`) → `BFLTimeoutError`.
- Malformed/`ERR:INVALID DATA`/`ERR:SIGNATURE` → `BFLProtocolError` carrying raw bytes.
- A **naive-42-stall detector**: when the existing naive path produces the empty-response stall signature, raise `BFLDeviceError` with a clear message pointing to `QueuedWorkSession` (turns the historical footgun into a guided path; lives in the new code/detector, naive path still unmodified).

## 7. Testing (hardware-gated)

- `tests/test_queued_protocol.py` — builder/parser round-trips; **V1 and V2 result-line fixtures transcribed verbatim from the cgminer reference as regression anchors** (same discipline as the NIST p-values / hashlib anchor); `parse_details` extracts `JOBS IN QUEUE`.
- `tests/test_queued_simulator.py` — **headline regression:** naive path stalls on the 43rd `ZDX`; `QueuedWorkSession` sustains ≥ 500 jobs against the same simulator and yields the expected nonces. Proves the fix in CI, no hardware.
- `tests/test_nonce_source.py` — `SimulatedNonceSource` yields expected results; asserts `NonceSource` is **not** a `HashSource` subclass and is not registered with any digest pipeline.
- Hardware proof: `scripts/hw/prove_queued.py` on the real Jalapeno (COM3); excluded from pytest; the documented sole real-silicon check.
- Full existing suite must stay green and unchanged (no naive-path test perturbed).

## 8. Surfaced commands — disposition

| Command | Meaning | Disposition |
|---|---|---|
| `ZNX`/`ZWX`/`ZOX`/`ZQX`/`ZCX` | queued work + details | **In scope** (this spec) |
| `ZJX` | firmware version string | Future (cheap; not now) |
| `Z9X`,`Z0X`–`Z4X` | fan auto / 5 fixed fan levels | **Future, high-value** — enables thermal-vs-hashrate "real silicon physics" research; recorded, not built here |
| `ZUX`/`ZSX` | load/save persistent string | Future, **semantics under-specified even in cgminer** (TODO there); needs hardware probing |
| `ZMX` | firmware FLASH | **Excluded** — bricking-capable; do not implement |
| XLINK (`@` chain) | multi-device daisy chain | **Excluded** — single-device toolkit |

## 9. Build order (one spec, incremental)
1. `protocol/queued.py` + constants + protocol tests (V1/V2 anchors).
2. Simulator: queue model + naive-42-wall model + the contrast regression test.
3. `QueuedWorkSession` (+ backpressure, drain, telemetry hook) + tests.
4. `NonceSource` ABC + Device/Simulated impls + tests.
5. `scripts/hw/prove_queued.py` + docs: DEVLOG §4 correction (42-wall is a naive-path artifact, queued path is the fix, attributed to the owner's mining evidence), additive CLAUDE.md/README notes, surfaced-command inventory.

## 10. Risks and mitigations
- **V1 vs V2 result format unknown for SC 1.0** → support both via field-count detection; pin with verbatim reference fixtures; final confirmation via the hardware script.
- **Simulator fidelity vs real firmware** → the simulator is explicitly a contrast harness (proves naive-stall vs queued-sustain logic), not a firmware emulator; real proof is the hardware script. Documented as such.
- **Signature/EOB framing errors brick a work cycle** → exact framing constants pinned from the reference and unit-tested before any hardware run; hardware script flushes (`ZQX`) on start/exit.
- **Scope creep into fan/flash/XLINK** → §2/§8 explicit exclusions.
