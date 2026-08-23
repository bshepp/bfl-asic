# Future directions (speculative)

**Not a plan — a map.** Where this project *could* go, and how to think about
which retro miner is worth characterizing next. Curiosity-driven; nothing here
is committed, scheduled, or budgeted. For the concrete near-term gear list see
[`hardware-wishlist.md`](hardware-wishlist.md); for the full catalog of the era
see [`usb-miner-field-guide.md`](usb-miner-field-guide.md).

## How to evaluate a candidate device — three questions

1. **Protocol** — does it reuse one we already speak (BFL SC, Icarus) or need a
   new module (gekko, bitfury/SPI, Avalon, zeus)?
2. **Algorithm** — SHA-256 (feeds the *entire* analysis stack: stats,
   randomness, dynamics, ML) or Scrypt / X11 (characterization-only, see below)?
3. **What new *question* does it unlock?** — a device that only adds hashrate
   isn't interesting here; a device that adds a *measurement we can't make yet*
   is.

## The landscape, sorted by leverage

### Drop-in — protocols we already speak
- **BFL Single / Double** — the sleeper. **Same BitForce SC protocol as the
  Jalapeño**, so it works with the current device layer with *zero new code*.
  More engines → sharper dead-core / engine-map resolution, and two BFL boxes
  finally unlock **XLINK chaining** (protocol territory one unit can't reach).
  Often priced like a Jalapeño → the highest leverage per dollar, and it keeps
  the flagship lineage central.
- **GekkoScience Compac (BM1384)** — the `icarus` module + ANU-frequency command
  already cover it; one is how we *validate that code on real silicon*.
- **Fury family** (Red / Blue / Bi·Fury, BitFury BF1) — SHA-256, so they feed
  the full pipeline; a small new protocol module (bitfury / MCP2210 SPI).

### One module unlocks several — the GC3355 bridge
- **GridSeed 5-chip + DualMiner USB** share the **GC3355** chip → one protocol
  effort covers both. And the GC3355 is dual-mode **SHA-256 *and* Scrypt on one
  silicon** — which makes it a controlled experiment: *does the determinism /
  dead-core / thermal signature differ by algorithm on identical hardware?* The
  natural bridge into Scrypt without leaving SHA-256 behind.

### New frontiers — new protocol *and* new algorithm
- **Avalon Nano 3** — Canaan's Avalon protocol lineage; a different vendor's
  whole design philosophy to characterize.
- **Scrypt milestones** — FutureBit **Moonlander 2** (the first *true*
  single-stick Scrypt miner — the historically compelling one) and **ZeusMiner
  Blizzard**.
- **X11** — **PinIdea DU-1**, the rare USB-stick X11 miner (the "one device that
  reached X11" the field guide flags).

## The algorithm question (SHA-256 vs Scrypt / X11)

The **analysis** pipelines (stats, randomness, dynamics, ML) are SHA-256
specific — a Scrypt or X11 device will not feed them. But the **model-free
characterization core is algorithm-agnostic**: determinism, nonce yield,
Poisson winner counts, thermal profiling, dead-core detection, and per-chip
attribution all just count *nonces and timing* — they do not care which hash
function ran. So Scrypt / X11 devices are **full-value targets for protocol
re-derivation and characterization**; they simply don't extend the SHA-256 math.

Taking them on reframes the project's identity — from "a SHA-256 lab" into **a
retro mining-silicon characterization lab across the algorithm wars**: SHA-256
vs Scrypt vs X11, the whole 2013–2015 USB-stick era as hardware archaeology.
That is the "the name doesn't constrain us" direction, extended.

## The richest questions (beyond "more devices")

- **XLINK chaining** — needs two-plus BFL boxes; unexplored-by-us protocol
  territory, and pure protocol fun.
- **Dual-algorithm characterization on one chip** (GC3355) — nobody has framed
  that as a controlled experiment.
- **A living characterized catalog** — the field guide *plus* one
  characterization run per specimen = a reference archive of *measured* retro
  miners that does not exist anywhere else. Arguably what this project is
  quietly becoming.

---

*Speculative directions only. The trunk stays the BFL Jalapeño; everything here
is a branch off it, to be taken (or not) purely for the fun of the question.*
