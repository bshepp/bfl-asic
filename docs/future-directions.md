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

## Environmental coupling — the milieu joint study

The one direction here that is **more than speculative**: an intended joint run
with the sibling [milieu](https://github.com/bshepp/milieu) project — the fleet's
ambient-telemetry instrument layer (passive-BLE Govee/RuuviTag decoders). It
answers question 3 directly: *a measurement we cannot make yet.*

Put a milieu **ambient sensor** (an offset-calibrated Govee H5075) **right next to
a unit** and log it against the unit's own thermal telemetry. Here "unit sensor"
means the Jalapeño's `ZLX` reading (`bfl-asic temperature`) — but the point is to
**record the whole device surface**, timestamp-aligned with ambient, not just
temperature:

- `ZLX` temperature, `ZTX` voltage / VCC1 (mind the post-`ZTX` ~1.2 V settling
  artifact);
- the *live* `ZCX` census — engine-count wobble (26 ↔ 27), per-processor
  frequency (198–199 MHz), self-reported MINIG SPEED (5.15–5.34 GH/s);
- health / nonce yield, throughput, error count, nonce-set determinism, fan state.

Two questions fall out. The **expected** one: quantify self-heating — how far the
die runs above true ambient, idle vs. under load, now that ambient is a
*calibrated* number rather than a guess. The **interesting** one: does ambient
move anything *other* than die temp — voltage, the engine/frequency wobble, yield,
determinism? Any such coupling would be a genuinely novel readout, and the whole
reason to log everything is that you cannot find a linkage you did not record.

**Sequence:** ambient sensor next to the unit first (baseline), then repeated
across other ranges. Two items are intentionally still open: the cross-project run
**coordination** with milieu (milieu owns the sensor schedule and runs concurrently
with its consumers when it can), and whether "other ranges" means *temperature*
ranges (drive the pair hot/cold) or *spatial* ranges (sensors stepped away to map
the unit's heat plume) — probably both, in time. The instrument side is tracked
from [milieu's roadmap](https://github.com/bshepp/milieu#roadmap).

---

*Speculative directions only. The trunk stays the BFL Jalapeño; everything here
is a branch off it, to be taken (or not) purely for the fun of the question.*

## Build quality as evidence — examining the shells

An open question this project is unusually well placed to answer: **what does
the hardware itself say about how BFL spent its money?** This is currently a
qualitative impression, and it deserves to be made quantitative.

The impression is that these machines are **over-engineered**, and three of our
own measurements support it:

- **Thermal headroom is enormous.** A supervised sweep stepped the fan down to
  *off* under sustained load; the unit topped out around **41 °C** and never
  erred. The fan is close to decorative on a desk — the part is wildly
  over-provisioned for its own workload.
- **The controller is over-specified.** An Atmel **AT32UC3A1256** — a 32-bit
  AVR32 with JTAG — to shuttle 60-byte work packets over a 115200-baud serial
  link. A cheap 8-bit part would do.
- **The enclosures are machined aluminium**, not folded sheet or moulded
  plastic.

One observation cuts the other way: the **Single chassis is shared across at
least three SKUs** (`BF0050G`, `SGL300G`, `SGL600G` — externally identical,
distinguished only by how many 6-pin connectors are populated). Listing photos
show the 300G panel carries **both apertures**, identical in shape and spacing;
the second is simply left unpopulated. So it is a **common panel, populated to
order** — the second port is not cut in later.

Resist reading that as foresight. "Deliberate tooling amortisation" assumes
planning we cannot demonstrate, and an equally good explanation is mundane:
**order a batch of shells, then adapt them as the product changes or
undersells.** A common panel is consistent with both, so on its own it
discriminates nothing.

**Why it matters.** A pure take-the-money operation optimises for minimum unit
cost; it does not tool up machined aluminium or specify an AVR32. So build
quality is evidence about **where the money went**, and about whether hardware
was genuinely being built.

**What it is not evidence of.** It says nothing about **delivery**. BFL
demonstrably failed to ship to 20,000+ paying customers; a well-built machine
that never arrives is still a machine that never arrived. Keep the two questions
separate — this bears on "was anything real being made", not on "were customers
defrauded".

### What to actually measure

- **Process:** CNC-machined from billet vs. extruded-and-cut vs. stamped/folded
  vs. cast — the cost spread across those is very large. Look for tool paths,
  witness marks, extrusion die lines, wall-thickness uniformity.
- **Finish:** anodising, bead-blast, brushing — each is a separate paid step.
- **Fasteners and inserts:** heat-set/threaded inserts vs. self-tapping screws
  straight into aluminium.
- **Thermal integration:** is the enclosure also the heatsink, or is it merely a
  box around one?
- **Parts sharing:** which panels are common across the Jalapeño cube, the
  Single chassis and the Monarch card bracket.
- **Anodising as a record of process order.** Anodising is a *conversion
  coating*: it exists only where the surface was present in the tank. So any
  machining done afterwards leaves **bare aluminium**. Inspect the interior
  edges of the second power-supply aperture under a loupe — **anodised edges**
  mean the aperture predates the tank (built that way); **bright, bare edges**
  mean it was cut into an already-finished shell (surplus stock adapted). This
  is a direct, physical record of which happened, and no listing photo can
  resolve it — the recess is in shadow either way.
- **Population vs. provision.** Behind an unpopulated aperture, check whether
  the **PCB carries unpopulated footprints** for the missing connector, and
  whether **mounting bosses/standoffs** for it exist in the shell. A common PCB
  and common shell differentiated only by population is a very different story
  from a board revision that never had the second supply.
- **The payoff number:** an estimated **per-unit enclosure cost**, compared with
  the retail price and with what a cost-optimised 2013 product would have used.

Three chassis families are already available to inspect: the Jalapeño cube (two
in hand), the Single/SGL box (photographed in `research/ebay-survey/`), and the
Monarch bare card.

A cheap way in: the survey shows **SGL300G units clear at $40–60**, so a
decisive teardown specimen costs less than a night out. We own Jalapeños but no
Single, so this is a "when one is acquired" item.
