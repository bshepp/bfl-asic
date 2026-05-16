# BFL SC Queued-Work + Fan-Control Path — Design Spec

- **Date:** 2026-05-16
- **Status:** Approved (brainstorming complete; pending written-spec review)
- **Author:** Brian Sheppard + Claude
- **Scope:** One new additive subsystem — SC queued-work protocol + sustained session + honest `NonceSource` + **manual fan control** — plus append-only edits to `protocol/constants.py`, `transport/simulator.py`, and additive new methods/CLI/scripts. No existing pipeline, command, or the naive work path is modified.
- **Reference:** cgminer `driver-bflsc.h` / `driver-bflsc.c` at `F:\experimental-projects\cgminer-ref\` (GPLv3 — protocol facts only, **no code vendored or copied**; clean reimplementation).

---

## 1. Context and motivation

`bfl-asic`'s device path is a naive single-job model: `ZDX` submit → `ZFX` poll, one unit at a time. The DEVLOG documents (4× reproduced) the SC firmware refusing `ZDX` after 42 cumulative submissions per power cycle, over-stated there as a hardware ceiling. It is not: the owner mined for days/thousands of submissions with zero power cycles. cgminer (`driver-bflsc.c`) drives the device's **queued** protocol and **continuously drains results**, freeing the firmware's queue bookkeeping, so it never approaches 42. The 42-wall is a naive-path artifact (never draining), not a firmware limit.

This spec adds, additively and opt-in: the queued path (sustained work like a real miner), an honest toolkit surface, and **manual fan control** — the latter being the enabling capability for the device's genuine hardware-physics research lane (thermal vs. hashrate), which the user pulled into this build.

## 2. Goals and non-goals

**Goals**
- Opt-in SC queued-work path (`ZNX`/`ZWX`/`ZOX`/`ZQX`/`ZCX`) with continuous result-drain and `JOBS IN QUEUE` backpressure — the real-miner pattern that does not hit 42.
- A sustained `QueuedWorkSession` (run for N jobs or T seconds; yields results) with an optional in-loop temp/voltage telemetry hook.
- An honest `NonceSource` abstraction (sibling to `HashSource`) — yields device-found nonces; explicitly **not** a digest source.
- **Manual fan control**: `set_fan_auto()` / `set_fan(level 0..4)` device methods + CLI, with thermal-safety guards.
- CI proves the fix **without hardware**: the simulator models the naive 42-wall, the queued drain, and fan state; a regression test asserts naive stalls at 43 while queued sustains ≫42.
- Guarded hardware proof script on the real Jalapeno (COM3, confirmed alive), which also exercises and safely restores the fan.
- Correct the DEVLOG §4 conclusion.

**Non-goals**
- The naive `submit_work`/`submit_and_wait`/`poll_result`/`hash_data` path is **not modified** (it stays the honest demonstration of the 42-wall).
- **No** `ZMX` firmware-flash (bricking-capable; excluded).
- **No** XLINK daisy-chain support (single-device only).
- **No** device-backed `HashSource` (device yields nonces, never digests — physically impossible; documented).
- `ZJX` firmware string, `ZUX`/`ZSX` load/save strings: out of scope, recorded as future (§8).
- **Not** a thermal-vs-hashrate *experiment* — this delivers the fan *control capability*; the characterization study is a later use of it.

## 3. Protocol facts (from the reference; reimplemented cleanly)

**Queued work**
- Commands: `ZNX` queue one job; `ZWX` queue a job pack (**max 5 jobs/write**, `QueueJobPackStructure`: payloadSize, signature `0xc1`, jobsInArray, jobs[5], endOfWrapper `0xfe`); `ZOX` query/drain results; `ZQX` flush; `ZCX` device details.
- Queued job packet (`ZNX`): `payloadSize` + 32-byte midstate + 12-byte blockData(tail) + EOB `0xaa` (`BFLSC_QJOBSIZ = 32+12+1 = 45`).
- Result block (`ZOX` reply): starts `COUNT:`; ≥3 lines; per-result fields — V1: `UID, CC, NONCECOUNT, nonce…`; V2 inserts a `CHIP` field (V1 nonce-count at field 2, V2 at field 3). `QUE_MAX_RESULTS = 8` is the max results returned **per `ZOX` read** (drain batch size), *not* the job-queue depth — distinct. SC 1.0's variant: determined from `.c` logic, confirmed on hardware.
- Details (`ZCX` reply): keyed lines incl. `FIRMWARE`, `ENGINES`, `JOBS IN QUEUE`, `CHIP PARALLELIZATION`, XLINK fields.
- Tokens: `OK\n`, `SUCCESS\n`, `COUNT:`, error family `ERR:` (`ERR:TIMEOUT`, `ERR:INVALID DATA`, `ERR:SIGNATURE`). Existing `>>>>>>>>` delimiter and `RESP_*` unchanged.

**Fan control**
- `Z9X` = fan AUTO (firmware thermal management). `Z0X`..`Z4X` = five fixed fan levels (firmware command table defines all five).
- Single-stage command: send 3 bytes, read **one newline-terminated reply line**. cgminer reads it with `READ_NL` and does **not** assert a specific token — so the exact ack string (`OK`/`SUCCESS`/other) is **not pinned by the reference**; the parser must accept any single-line ack and the precise token is hardware-confirmed.
- **Reference only validates `Z9X` and `Z4X` in practice** (`bflsc_set_fanspeed`: force `Z4X` max when temp > `BFLSC_OVER_TEMP` or temp unknown, else `Z9X` auto). `Z0X`–`Z3X` are defined-but-unexercised even in cgminer → exposed, but per-level behavior is hardware-unconfirmed and documented as such.

## 4. Architecture (additive only)

Mirrors the existing protocol / transport / device / application layering and the `HashSource`/`get_temperature` precedents.

- **`bfl_asic/protocol/queued.py`** (new, pure) — builders `build_queue_job`, `build_queue_job_pack` (≤5), `build_queue_results`, `build_queue_flush`, `build_details`; parsers `parse_queue_results(raw)->list[QueuedResult]` (V1 **and** V2), `parse_details(raw)->DeviceDetails` (`.jobs_in_queue:int`). Dataclasses `QueuedResult{uid,nonces,raw}`, `DeviceDetails`.
- **`bfl_asic/protocol/fan.py`** (new, pure) — `build_fan_auto()->bytes` (`Z9X`), `build_fan_level(level:int)->bytes` (`Z0X..Z4X`; raises `ValueError` if not 0..4), `parse_fan_ack(raw)->bool` (tolerant: any non-`ERR:` single line is success).
- **`bfl_asic/protocol/constants.py`** (append-only) — add `CMD_QJOB=b"ZNX"`, `CMD_QJOBS=b"ZWX"`, `CMD_QRESULTS=b"ZOX"`, `CMD_QFLUSH=b"ZQX"`, `CMD_DETAILS=b"ZCX"`, `CMD_FAN_AUTO=b"Z9X"`, `CMD_FAN_LEVEL=(b"Z0X",b"Z1X",b"Z2X",b"Z3X",b"Z4X")`, framing `EOB=0xAA`/`SIGNATURE=0xC1`/`EOW=0xFE`, `QUE_MAX_RESULTS=8`, `QJOB_PAYLOAD_SIZE=45`, `RESP_SUCCESS=b"SUCCESS"`, `RESP_COUNT=b"COUNT:"`, `RESP_ERR=b"ERR:"`. Existing names untouched.
- **`bfl_asic/transport/simulator.py`** (additive branches) — (a) finite job queue: `ZNX`/`ZWX` enqueue, internal SHA-256d compute (reusing existing logic) into a results buffer, `ZOX` drain+free, `ZCX` reports `JOBS IN QUEUE`, `ZQX` flush; (b) a naive-path cumulative-`ZDX` counter that stalls on the 43rd (configurable, default on) so the contrast is regression-testable; (c) fan state: `Z9X`/`Z0X..Z4X` set an internal `fan_mode`/`fan_level`, return an `OK\n` ack. Existing ZGX/ZLX/ZTX/ZFX/ZDX(≤42) behavior unchanged.
- **`bfl_asic/device.py`** (additive — new members only; existing methods byte-for-byte untouched)
  - `QueuedWorkSession(transport)` context manager: `submit(midstate,tail)`; drain loop issuing `ZOX` on a cadence (each returns ≤`QUE_MAX_RESULTS`=8 results, freeing those slots); submission backpressure throttles on `ZCX` `JOBS IN QUEUE` < a configured `max_queue_depth` (default from the device's reported capacity, not the 8 results-batch); `run(max_jobs=None,duration=None,work_iter=None)->Iterator[QueuedResult]`; `flush()`; optional `telemetry_interval` reading temp/voltage from inside the loop; `ZQX` on close.
  - `BFLDevice.set_fan_auto()` and `BFLDevice.set_fan(level:int)` — new additive methods alongside `get_temperature`/`get_voltage`.
- **`bfl_asic/nonce_source.py`** (new) — `NonceSource` ABC (`results(count|duration)->Iterator[QueuedResult]`, `name()`), `DeviceNonceSource` (wraps `QueuedWorkSession`), `SimulatedNonceSource`. Docstring states plainly it is **not** a `HashSource` and why; not consumed by stats/ML/randomness.
- **`bfl_asic/cli.py`** (additive — new subcommand only) — `bfl-asic [-p PORT] fan (auto|0|1|2|3|4)`: sets the fan; prints temp before/after when available; emits the thermal-safety warning (§5) for non-auto levels.
- **`scripts/hw/prove_queued.py`** (new, opt-in, excluded from pytest) — real port (default COM3): submits >42 queued jobs, asserts no stall, prints sustained count/rate + `ZCX` details. **Always restores `Z9X` auto and `ZQX`-flushes on exit**, even on error.

## 5. Thermal safety (mandatory guards)

Manual fan control can physically damage the ASIC (low/off fan during hashing → overheat). This is hard-to-reverse, so the design enforces:
- Default and resting state is **auto (`Z9X`)**. Nothing leaves the fan in a fixed level unattended.
- `set_fan(level)` and the CLI emit an explicit warning that non-auto/low levels during active hashing risk thermal damage, and recommend monitoring temperature.
- Any code path that sets a fixed fan level (hardware script, future experiments) **must restore `Z9X` on exit including on exception** — same discipline as the `ZQX`-flush-on-close pattern.
- Mirror cgminer's rule in a helper: if temperature is unknown or above an over-temp threshold, force max (`Z4X`), never a low level.
- The simulator models fan state only; real thermal effect is hardware-only and untestable in CI (documented — no false safety claims).

## 6. Error handling

Reuses the `BFLError` hierarchy. Queue-full → backpressure (expected, not an exception). `ERR:TIMEOUT` → `BFLTimeoutError`. `ERR:INVALID DATA`/`ERR:SIGNATURE`/malformed → `BFLProtocolError` with raw bytes. Out-of-range fan level → `ValueError` (pure protocol layer). A naive-42-stall detector raises `BFLDeviceError` pointing to `QueuedWorkSession` (lives in new code; naive path still unmodified).

## 7. Testing (hardware-gated where it must be)

- `tests/test_queued_protocol.py` — builder/parser round-trips; **V1 and V2 result-line fixtures transcribed verbatim from the reference as regression anchors**; `parse_details` extracts `JOBS IN QUEUE`.
- `tests/test_fan_protocol.py` — `build_fan_auto`/`build_fan_level` exact bytes; level bounds (0..4 ok, −1/5 raise `ValueError`); `parse_fan_ack` accepts a generic ack line and rejects `ERR:`.
- `tests/test_queued_simulator.py` — **headline regression:** naive path stalls on the 43rd `ZDX`; `QueuedWorkSession` sustains ≥ 500 jobs and yields expected nonces; fan commands round-trip simulator state.
- `tests/test_nonce_source.py` — `SimulatedNonceSource` yields expected results; asserts `NonceSource` is **not** a `HashSource` subclass and is not registered with any digest pipeline.
- `tests/test_fan_cli.py` — `fan auto`/`fan 4` against the simulator exit 0 and emit the safety warning for fixed levels; CLI `--help` lists `fan`.
- Hardware-confirmed-only (documented, not CI-claimable): exact fan ack token, `Z0X`–`Z3X` per-level behavior, V1-vs-V2 selection on SC 1.0. Covered by `scripts/hw/prove_queued.py`.
- Full existing suite stays green and unchanged (no naive-path or existing test perturbed).

## 8. Surfaced commands — disposition

| Command | Meaning | Disposition |
|---|---|---|
| `ZNX`/`ZWX`/`ZOX`/`ZQX`/`ZCX` | queued work + details | **In scope** |
| `Z9X`,`Z0X`–`Z4X` | fan auto / 5 fixed levels | **In scope** — `Z9X`/`Z4X` reference-validated; `Z0X`–`Z3X` exposed, per-level behavior hardware-unconfirmed |
| `ZJX` | firmware version string | Future (cheap; not now) |
| `ZUX`/`ZSX` | load/save persistent string | Future, semantics under-specified even in cgminer |
| `ZMX` | firmware FLASH | **Excluded** — bricking-capable |
| XLINK (`@` chain) | multi-device daisy chain | **Excluded** — single-device toolkit |

## 9. Build order (one spec, incremental)
1. `protocol/queued.py` + constants + protocol tests (V1/V2 anchors).
2. Simulator: queue model + naive-42-wall model + the contrast regression test.
3. `QueuedWorkSession` (+ backpressure, drain, telemetry hook) + tests.
4. `NonceSource` ABC + Device/Simulated impls + tests.
5. `protocol/fan.py` + `BFLDevice.set_fan_auto/set_fan` + simulator fan state + `fan` CLI + thermal-safety guards + fan tests.
6. `scripts/hw/prove_queued.py` (queued proof + safe fan exercise/restore) + docs: DEVLOG §4 correction (42-wall = naive-path artifact, queued path is the fix, attributed to the owner's mining evidence), additive CLAUDE.md/README notes incl. fan-control + thermal-safety, surfaced-command inventory.

## 10. Risks and mitigations
- **Thermal damage from manual fan control** → §5 guards: default/restore auto, restore-on-exception, temp-aware force-max, explicit warnings; CI cannot prove thermal safety (stated honestly).
- **V1 vs V2 result format unknown for SC 1.0** → support both via field-count detection; pin with verbatim reference fixtures; confirm on hardware.
- **Fan ack token + `Z0X`–`Z3X` semantics unconfirmed by reference** → tolerant ack parser; expose levels but document the unknown; hardware script confirms.
- **Simulator fidelity vs real firmware** → simulator is an explicit contrast harness (naive-stall vs queued-sustain logic, fan state round-trip), not a firmware emulator; real proof is the hardware script.
- **Framing errors (signature/EOB) waste a work cycle** → exact constants pinned from the reference and unit-tested before any hardware run; hardware script `ZQX`-flushes and restores fan auto on start/exit.
- **Scope creep into flash/XLINK/thermal-experiment** → §2/§8 explicit exclusions; this delivers fan *control*, not the study.
