# Hardware Wishlist — extending the characterization fleet

Gear to grow this project from a single-device toolkit into a
multi-generation "characterize retro mining silicon, model-free" instrument.
Ranked by **what experiment each unlocks**, not by hashrate or collectibility.

Open experiments driving the list:

1. **Frequency sweep** (clock-vs-error-rate cliff) — the Phase-3 experiment the
   Jalapeño's stock firmware denied us (its `ZVX` clock-set doesn't take — a
   masked broadcast + no PLL relatch; real control needs a reflash). Needs a
   device whose clock control actually *takes* out of the box.
2. **Per-chip nonce attribution** — ground truth to validate the dead-core
   detector, turning its histogram *inference* into a *measurement*. Needs a
   chip chain that tags which chip found each nonce.
3. **Protocol diversity** — each new chip family is a new protocol module
   (`icarus` → `gekko` → `bitfury`/SPI).
4. **Physical-RE victims** — cheap single-die sticks to decap / glitch.

## Current fleet & order status

| Device | Role | Chip / protocol | Status |
|---|---|---|---|
| BFL Jalapeño ×2 | device #1 | BF0005G / BFL SC | ✅ reference `002659` + sacrificial `005794` (arrived + characterized 2026-08) |
| Block Erupter USB | device #2 | BE100 / Icarus | ✅ owned (`berbil-14`); **more on the way (mixed colors)** |
| GekkoScience NewPac | per-chip attribution + sweep | BM1387 (gekko) | 🛒 ordered — ETA 2026-08-29 |
| Antminer U1 / U2 | the sweep, cheaply | BM1380 / Icarus | 🛒 U1 on the way; U2 next month |

Legend: ✅ owned · 🛒 on order · ⭐ future target

## Tiers (by experiment unlocked)

### S — unlocks something the Jalapeño and Erupter can't

- **GekkoScience NewPac** · 2× BM1387 · ~$40–100 · *still sold new* — the only
  device that does the sweep **and** per-chip ground truth **and** the richest
  new protocol (`gekko` driver, module #2). Per-chip attribution validates the
  dead-core detector. Needs a powered hub + fan; 2 chips = modest 2-way map.
  **→ if your owned Gekko is a NewPac, you already have this.**
- **Antminer U1 / U2** · BM1380 · ~$10–40 used · *eBay-only relic* — the
  frequency sweep directly, via the exact `[0x82, freq_word, crc5]` command.
  Icarus protocol → the `icarus` module already covers it. 🛒 on the next list.

### A — new protocol lineage, cheap-ish

- **GekkoScience Compac / 2Pac** · BM1384 · ~$20–50 — sweep-capable via the
  same icarus `set_anu_freq` path as the Antminer U; cleaner/more orderable.
  A BM1380→BM1384→BM1387 stepping stone. **→ if your owned Gekko is one of
  these, the sweep is doable on it now (simpler than a NewPac).**
- **NanoFury NF1 / NF2** · BitFury BF1 · ~$15–40 used — the most
  *architecturally different* add: **MCP2210 USB→SPI** (not UART) + the
  `bitfury` driver + adjustable clock (`osc6_bits`). Best for protocol/RE
  diversity.

### B — diversity & the "N generations" comparative story

- **Bi·Fury / Red / Blue Fury** · BitFury BF1 · ~$20–60 — rounds out the
  BitFury lineage; some clock control.
- **GridSeed GC3355** · ~$20–50 — the oddity: SHA-256 **and** Scrypt on one
  chip, adjustable freq. A great "characterize *this*" curiosity.

### C — collector / minimal new science

- **More Block Erupters** — device #2 is fully characterized; extras earn
  their keep as **cheap decap/glitch victims** (ideal single-die 130 nm target)
  or a multi-unit dead-core farm. 🛒 a couple more coming — see the color note.
- **FutureBit MoonLander 2** (Scrypt) — different algorithm, adjustable
  clock+voltage, but Scrypt is a memory-hard rabbit hole off the SHA-256 focus.

### Skip

Antminer U3 (box, 12 V, fussier), anything Ethernet/rackmount, PinIdea DU-1
(X11 — a curiosity too far afield). Not "USB-dongle" class. (These are
near-term, SHA-256-focus calls; the broader multi-algorithm case — X11 and
Scrypt included — is made in [`future-directions.md`](future-directions.md).)

## Notes

- **Block Erupter color is cosmetic — buy a mix on purpose.** Every genuine
  Block Erupter USB is the same BE100 / ~336 MH/s / CP2102 / Icarus stick
  regardless of color. But they **all report the same default serial `0001`**
  (no unique ID — that's why `berbil-14` says "label physically"), so a mix of
  colors is a **free built-in bench label**. Avoid "for parts / untested"
  listings unless you *want* a decap victim.
- **GekkoScience: NewPac ordered (BM1387, ETA 2026-08-29).** The prior "owned"
  Gekko was lost in a move; the NewPac was chosen over a Compac because BM1387's
  per-chip nonce attribution is the dead-core *ground truth* (its `gekko`
  protocol spec is already researched and ready to build).
- Priorities respect a tight budget: none of this is urgent. The Erupter and
  both Jalapeños are fully characterized; the NewPac and the Antminer U (for the
  frequency sweep) are the next real steps as they arrive.

*See also: [`usb-miner-field-guide.md`](usb-miner-field-guide.md) — the full
catalog of this hardware generation — and
[`future-directions.md`](future-directions.md) — the speculative expansion map
(algorithm coverage, BFL Single/Double + XLINK, the living catalog).*
