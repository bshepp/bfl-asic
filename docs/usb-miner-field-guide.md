# USB Miner Field Guide (2011–2018)

A catalog of the thumb-drive-sized cryptocurrency miners of the pocket-ASIC era —
the FPGA boards that came first, the SHA-256 dongles that defined it, the
dual-algorithm oddities, and the one lonely stick that mined anything else.

An **interactive version** of this catalog (grouped, themeable, easier to scan)
is published as an artifact:
<https://claude.ai/code/artifact/88cde082-9b3c-4368-aa14-eb2097b52950>

This began as a companion to the reverse-engineering work on the 2013 Butterfly
Labs *Jalapeño* in this repo. The BitForce `Z_X` protocol that project revolves
around traces directly back to the **BFL BitForce Single (FPGA)** — the very
first row of the FPGA section below.

## How to read this guide

- **Category** — each device's algorithm: FPGA precursor, SHA-256, dual-algo,
  Scrypt, or X11.
- **Form** — devices are USB *sticks* unless tagged `[box]`, `[board]`, or
  `[blade]`, which are externally powered (USB is the control plane, not the
  power).
- **OC** — `(OC …)` in the hashrate column means the clock is user-adjustable.
- **†** — a spec I could **not** confirm from two independent sources. It is a
  flag, not a fact: I did not invent any numbers.

Specs are cross-checked against the **cgminer** and **bfgminer** driver sources
(`ASIC-README`, `README.ASIC`, individual `driver-*.c`), the **bitcoin.it**
mining-hardware comparison, ZTEX / FPGA-Mining vendor pages, and period
bitcointalk support threads.

---

## 00 · The FPGA precursors (2011–2012)

The generation before ASICs: reconfigurable Xilinx Spartan-6 (and a few Altera)
boards running open Verilog SHA-256 cores over USB. Slow by later standards, but
the only mining silicon you can *reprogram*. The `icarus` serial protocol born
here became the de-facto standard that half the later sticks reused.

| Device | FPGA | Hashrate | USB bridge | Year | Driver | Notes |
|---|---|---|---|---|---|---|
| **Icarus** (ngzhang, reference) | 2× Spartan-6 LX150 | ~380 MH/s | serial † | 2012 | `icarus` | The reference board; its Rev3 serial protocol became the industry default. |
| **Lancelot** | 2× Spartan-6 LX150 | ~400 MH/s | FT2232H † | 2012 | `icarus` | Icarus-compatible; later popular for scrypt bitstreams. |
| **X6500** | 2× Spartan-6 LX150 | ~400 MH/s | FTDI (D2XX) | 2011–12 | `x6500` | First polished consumer FPGA board; Molex/barrel power. |
| **ModMiner Quad** (BTCFPGA) | 4× Spartan-6 LX150 | ~800 MH/s | ARM M3 → USB-CDC | 2012 | `modminer` | MCU handles bitstream upload — no FTDI. Field-modular 1–4 cards. |
| **Cairnsmore1** (Enterpoint, UK) | 4× Spartan-6 LX150 | ~800 MH/s | 2× FT2232H | 2012 | `cairnsmore` | Presents 4 serial ports; per-FPGA power/clock/temp control. |
| **ZTEX 1.15b** | 1× Spartan-6 LX75 | ~90 MH/s | Cypress EZ-USB FX2 | 2011 | `ztex` (OC) | BTCMiner SDK auto-overclocks by error rate. |
| **ZTEX 1.15x** | 1× Spartan-6 LX150 | ~215 MH/s | Cypress EZ-USB FX2 | 2012 | `ztex` (OC) | Single-FPGA workhorse of the ZTEX line. |
| **ZTEX 1.15y** | 4× Spartan-6 LX150 | ~860 MH/s | Cypress EZ-USB FX2 | 2012 | `ztex` (OC) | Quad-FPGA flagship module. |
| **BFL BitForce Single** (pre-ASIC) | 2× Altera † | 832 MH/s | FTDI USB-UART | 2011 | `bitforce` | Runs the `Z_X` protocol — the direct ancestor of the Jalapeño's. |
| **Bitcoin Dominator X5000** | 1× Spartan-6 LX150 † | 100 MH/s | serial † | 2012 | `icarus` † | Obscure low-power single-FPGA stick; thinly documented. |
| **Open-Source FPGA Miner** (fpgaminer — the HDL project) | Altera / Xilinx dev kits | ~5–110 MH/s | USB-Blaster JTAG | 2011–12 | (various) | The Verilog SHA-256d core many boards ran — DE2-115, DE0-Nano, Nexys 2, Atlys. |

---

## 01 · SHA-256 USB sticks — the main event

When ASICs arrived in 2013 they came, briefly and wonderfully, in thumb-drive
form. Four chip families did nearly all the work: ASICMiner's own die, Bitmain's
`BM138x` line, the `BM1384`/`BM1387` that GekkoScience still ships, and one
remarkable BitFury chip (`BF1`) that spawned a dozen "Fury" sticks.

### ASICMiner

| Device | Chip | Hashrate | USB bridge | Year | Driver | Notes |
|---|---|---|---|---|---|---|
| **Block Erupter USB** ("Sapphire") | ASICMiner 130nm, 1× | 330–336 MH/s | CP2102 | May 2013 | `icarus` / `erupter` | The original mass USB miner. ~2.5 W, green blink LED — the icon of the era. |

### Bitmain Antminer — U-series

| Device | Chip | Hashrate | USB bridge | Year | Driver | Notes |
|---|---|---|---|---|---|---|
| **Antminer U1** | BM1380, 55nm, 1× | 1.6 GH/s (OC ~2.2) | CP210x | 2013 | `icarus` / `antminer` | Classic blue overclockable stick; clock set by hex word. |
| **Antminer U2 / U2+** | BM1380, 55nm, 1× | ~2.0 GH/s (OC) | CP210x | 2014 | `icarus` / `antminer` | Minor revs of the U1, same silicon, higher stock clock. |
| **Antminer U3** `[box]` | BM1382, 28nm, 4× | ~63 GH/s (OC+V) | serial (`bmsc`) | Mar 2015 | `bmsc` | Needs external 12 V 6 A — USB is data only. Last of the "U" line. |

### The BitFury "Fury" family — one chip (BF1, 55nm), a dozen sticks

| Device | Chip | Hashrate | USB bridge | Year | Driver | Notes |
|---|---|---|---|---|---|---|
| **Red Fury** (BPMC) | 1× BF1 | 2.6 GH/s | ATmega32U2 CDC † | 2013 | `bigpic` / `bitfury` | Among the first USB ASIC sticks; large full-red heatsink. |
| **Blue Fury** (BPMC) | 1× BF1 | ~2.5–2.7 GH/s | ATmega32U2 CDC † | 2013–14 | `bigpic` / `bitfury` | Cost-reduced Red Fury: half-size black heatsink. |
| **Ice Fury** | 1× BF1 | ~2.9 GH/s † | MCP2210 † | 2013–14 | `nanofury` / `bitfury` | Lesser-known BPMC-adjacent variant. |
| **Bi·Fury** | 2× BF1 | 5 GH/s (OC) | onboard MCU CDC | Dec 2013 | `bifury` (BXF) | First 5 GH/s USB stick; wants a USB-3 / 0.9 A port. |
| **HexFury** | 6× BF1 | ~11 GH/s (OC ~15) | onboard MCU CDC | 2014 | `bifury` (HXF) | First 11 GH/s+ USB miner; needs a powered hub. |
| **NanoFury NF1** (Technobit, open) | 1× BF1 | ~2.0 GH/s (OC) | MCP2210 (USB→SPI) | 2014 | `nanofury` / `bitfury` | The one Fury bridge confirmable from source. `--nfu-bits`. |
| **NanoFury NF2** | 2× BF1 | ~3.7–5.4 GH/s (OC ~6.6) | MCP2210 | 2014 | `nanofury` | Per-chip clocks; hashrate scales with the "bits" setting. |
| **TwinFury / BFx2** | 2× BF1 | 3.7–4.0 GH/s (OC ~5) | FTDI-SPI / CDC † | 2014 | `twinfury` (BXM) | Made by the Red/Blue Fury team; interface chip disputed. |
| **LittleFury** (BitCentury) | 1× BF1 † | ~2.7 GH/s † | FTDI FT232 | 2013 | `littlefury` / `bitfury` | Early open-source board; sets `osc6_bits=50`. |
| **Drillbit Thumb** (Drillbit Systems, AU) | 1× BF1 **(not Avalon)** | ~2.2–2.7 GH/s (OC) | FT232R | 2013–14 | `drillbit` | Enumerates as an Atmel string; the driver has a latent Avalon path but shipped units were BitFury. |
| **Drillbit Eight** `[board]` | 8× BF1 | ~16–24 GH/s † | FT232 family † | 2013–14 | `drillbit` | 8-chip sibling of the Thumb; reports "Eight" for >1 chip. |
| **OneStringMiner** `[board]` | 15× BF1 | ~30+ GH/s (OC) | onboard MCU CDC | 2014 | `bifury` | The open "string" board HexFury derived from; USB data + 12 V. |
| **HashBuster Micro** `[board]` | multi-chip BF1 | ~22 GH/s (OC) | MCP2210 (HID) | 2014 | `hashbusterusb` | ~3.4" board; c-scape (HexFury team). |
| **HashBuster Nano** `[board]` | 1× BF1 | ~2.5–2.9 GH/s (OC) | MCP2210 | 2014 | `hashbusterusb` | Single-chip board sibling. |

### GekkoScience — the sticks that outlived everything

| Device | Chip | Hashrate | USB bridge | Year | Driver | Notes |
|---|---|---|---|---|---|---|
| **Compac** | 1× BM1384 | ~8–15 GH/s (OC ~23) | CP2102 | 2015 | `gekko` (GSC) | Original single-BM1384 stick; freq flag + trimpot core voltage. |
| **2Pac / Compac 2** | 2× BM1384 | ~11–15 GH/s (OC ~25) | CP2102 | 2017 | `gekko` (GSD) | Dual-BM1384; adjustable 550–800 mV regulator. |
| **NewPac** | 2× BM1387 (the Antminer S9 chip) | ~23 GH/s (OC ~90+) | CP2102 | 2018 | `gekko` (GSH) | The last great retro-window stick; powered hub for high clocks (~100–600 MHz). |

*(The GekkoScience line continued past this window — Compac F on `BM1397`,
the Terminus R606/R909 pods, and the 7 nm Compac A1 — but those are later.)*

### Avalon · Rockminer · Klondike

| Device | Chip | Hashrate | USB bridge | Year | Driver | Notes |
|---|---|---|---|---|---|---|
| **Avalon Nano (3)** | Avalon A3233, 1× | ~1.0–3.6 GH/s (OC) | native USB-CDC † | 2014 | `avalon` | A true stick (~100–360 MHz). **Not** the unrelated 2024 Canaan "Nano 3" home heater. |
| **Rockminer R-Box** `[box]` | 4× ASICMiner BE200, 40nm † | 32–37 GH/s (OC ~40) | CP2102 | 2014 | `rockminer` / `icarus` | ~90 mm fan box, 12 V ~5 A. Often mistaken for a stick. |
| **New R-Box / R-Box 2** `[box]` | BE200, 40nm | ~100–130 GH/s (OC) | CP2102 | 2014–15 | `rockminer` | Larger dual-fan box, 12 V 12–15 A. |
| **Klondike (K16)** `[board]` | Avalon A3255, up to 16× | ~5.6 GH/s @350 MHz (OC) | ARM-MCU USB | 2013 | `klondike` | The genuine open Avalon-chip DIY reference board. |

---

## 02 · Dual-algo — the GC3355 detour

The strangest branch: a single chip — GridSeed's `GC3355` (55nm) — that could
mine SHA-256 *and* Scrypt, together or either alone. Every "does both" USB miner
traces to this one die, sold under GridSeed's own name and rebadged as
"DualMiner." Nothing else in the era did two algorithms on one stick.

| Device | Chip | Hashrate | USB bridge | Year | Driver | Notes |
|---|---|---|---|---|---|---|
| **GridSeed 5-chip** ("Orb" / USB Mini — the "tuna can") | 5× GC3355 | ~11.25 GH/s SHA + ~350–360 KH/s scrypt | CP2102 → STM32 VCP | 2014 | `gridseed` (OC) | The iconic round dual-mode miner; the workhorse of the category. |
| **DualMiner USB** | 1× GC3355 | ~500 MH/s SHA + ~40 KH/s scrypt (or scrypt-only ~70 KH/s) | CP2102 † | 2014 | `dualminer` / `gridseed` (OC) | Single-chip dual-algo thumbstick; DIP switch picks the mode. "DualMiner 2" is a simplified single-chip rev, **not** a two-chip upgrade. |
| **GridSeed G-Blade** `[blade]` | 80× GC3355 (2 panels) | ~5.2–6 MH/s scrypt | CP2102 / STM32 VCP | 2014 | `gridseed` (OC) | Blade form, USB-driven, sold as a Scrypt LTC/DOGE unit. |

---

## 03 · Scrypt-only — the Litecoin/Doge sticks

A parallel world with entirely different silicon. Where dual-algo meant GC3355,
pure Scrypt meant the Zeus chip, and later FutureBit's dedicated sticks — the
only devices in this whole guide built for Litecoin and Dogecoin rather than
Bitcoin.

| Device | Chip | Hashrate | USB bridge | Year | Driver | Notes |
|---|---|---|---|---|---|---|
| **ZeusMiner Blizzard** | Zeus 55nm, 5–6× † | ~1.3–1.4 MH/s scrypt | CP2102 | 2014 | `zeus` (OC) | The only stick-class Zeus. Also rebadged as GAWMiner "Fury". |
| **LKETC USB** | Zeus-clone, 55nm | ~144–280 KH/s scrypt † | CP2102 | 2014–15 | `lketc` / `zeus` (OC) | Cheap eBay Zeus clones; often must run under-clocked to stay stable. |
| **FutureBit MoonLander** | AlcheMist scrypt ASIC | ~0.4–1.2 MH/s | CP210x | 2015–16 | `moonlander` (OC) | First true single-stick Scrypt USB miner (uses the AlcheMist chip, not an FPGA). |
| **FutureBit MoonLander 2** | 28nm scrypt ASIC † | 3–5.5 MH/s | CP210x | 2017 | `moonlander2` (OC+V) | The modern scrypt stick: pin heatsink + forced-air fan, core clock ~0.5–1 GHz. |

---

## 04 · Everything else — the one X11 stick

The honest answer to "was there anything beyond SHA-256 and Scrypt?" is: *almost
nothing*. Every X11, X13, and Quark miner shipped as an Ethernet box (Baikal
Mini, iBeLink) or a rackmount (PinIdea DR-series). Exactly one genuine USB stick
escaped that pattern.

| Device | Chip | Hashrate | USB bridge | Year | Driver | Notes |
|---|---|---|---|---|---|---|
| **PinIdea DU-1** | PinIdea X11 ASIC | ~9 MH/s (Dash) | USB † | May 2016 | vendor sgminer † | The one stick-class non-SHA/non-Scrypt ASIC. ~7 W, needed a 2 A powered hub. Sold for ~9 DASH (~$65). |

---

## The bus everyone rode — USB bridge families

Every one of these sticks is really an ASIC bolted to a USB-to-something bridge.
Which bridge is a surprisingly good fingerprint — and the single most-disputed
spec across sources, because retail listings and driver source often disagree.

| Bridge | Role | Devices |
|---|---|---|
| **SiLabs CP210x** (CP2102) | USB → UART (the workhorse) | Block Erupter, Antminer U1/U2, all GekkoScience, GridSeed (early), Zeus, Rockminer, LKETC |
| **FTDI FT232 / FT2232H** | USB → UART | X6500, Cairnsmore1, LittleFury, Drillbit Thumb, (disputed) TwinFury |
| **Microchip MCP2210** | USB → SPI | NanoFury NF1/NF2, HashBuster, Ice Fury — the *only* Fury bridge confirmable from source code |
| **Native USB-CDC** | onboard MCU (ATmega32U2 / ARM), no bridge chip | Red/Blue/Bi/Hex Fury, Avalon Nano, ModMiner, Klondike |
| **Cypress EZ-USB FX2** | USB microcontroller | every ZTEX 1.15-series module |
| **STM32 Virtual COM** | later revs | GridSeed swapped CP2102 → STM32 VCP on later boards |

---

## Edges of the catalog

### USB-connected, but not a stick

Externally powered boxes, blades, and open boards — USB is the control plane,
not the power:

- **Antminer U3** · **Rockminer R-Box** · **Drillbit Eight** — small boxes, 12 V input
- **OneStringMiner**, **HashBuster**, **Klondike** — open PCBs, not enclosures
- **GridSeed G-Blade** · **ZeusMiner Hurricane / Thunder / Lightning** — blades & controller boxes
- **Innosilicon A2** · **Baikal Mini** · **iBeLink DM-series** · **PinIdea DR-series** — Ethernet-managed, no USB-stick form
- **Block Erupter Blade / Cube / Tube / Prisma** — ASICMiner's larger network units

### Couldn't verify / not real

Named in passing but unconfirmable from two independent sources — flagged rather
than listed as fact:

- **Rockminer R-Box "Delta"** — no record; likely nonexistent
- **A multi-chip "DualMiner 2"** — the real USB 2 is a single-chip simplification
- **Vintage "Avalon Nano 3S"** — conflated with the 2024 Canaan heater
- **PinIdea DU-1 "Mark II" / 12.9 GH class** — only the ~9 MH/s DU-1 is documented
- **GekkoScience "R601" / "R808"** — unverifiable model numbers
- **"CoolingMining"** (a mining blog) · **"Sableminer"** (no device record)

---

*Compiled 2026-08-17. Every cell marked † is a spec that could not be confirmed
from two independent sources — a flag, not a fact. Corrections welcome.*
