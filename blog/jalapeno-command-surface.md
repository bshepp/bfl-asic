---
title: "I Thought I Found Hidden Commands in a 2013 Mining ASIC. They Were in the Firmware All Along."
authors:
  - user: bshepp
---

<!--
Long-form CANONICAL writeup, meant to render as Markdown on GitHub
(linked from the README). Companion to the round-reduced SHA-256
learnability post. Honest reframe: nothing here is a novel protocol
discovery — it's re-derivation from hardware plus empirical
characterization plus a small new instrument. Keep it that way.
-->

There is a specific kind of fun in bringing a dead machine back to life, and a specific kind of humility in discovering that everything you "found" was written down years before you were looking. This post is about both, on the same little purple box.

The box is a Butterfly Labs Jalapeño: a 5 GH/s SHA-256 mining ASIC from 2013, obsolete almost the moment it shipped, that sat on a shelf as a paperweight for the better part of a decade. An [earlier post](round-reduced-sha256-learnability.md) used it as the origin story for a software learnability study. This one is about the hardware itself — and about a research reflex I'm glad I have: **before you claim a discovery, go check whether someone already documented it.**

Spoiler: they did. And it was still worth every hour.

## Talking to the thing

The Jalapeño speaks a simple serial protocol over an FTDI USB-to-serial chip: three-character ASCII commands, all starting with `Z` and ending with `X` (`ZGX` to identify, `ZLX` for temperature, `ZDX` to submit work, and so on). The community mining software, cgminer, has a driver for it. So the obvious first move was to build a clean Python toolkit — protocol layer, serial transport, an in-process simulator that computes real SHA-256d so every test runs without hardware — and start poking.

Reading cgminer's driver header, I noticed something. It **defines** several commands it never actually **sends**: `ZJX`, `ZSX`, `ZUX`. Dead constants. That's catnip. What does a mining ASIC do when you send it a command its own mining software refuses to use?

So I sent them. On real hardware:

- **`ZJX`** returned a bare `1.0.0` — a firmware-version string, no framing, no `OK`.
- **`ZUX`** returned `MEMORY EMPTY`.
- **`ZSX`**, it turned out, *writes* that memory — a small persistent string buffer. I wrote a marker, pulled the power, plugged it back in, and read it back intact. A **non-volatile scratchpad**, in a 2013 mining ASIC, that the mining software never touches.

I'll be honest: for about an hour, that felt like a discovery. A hidden persistent store in retired mining silicon that you could, say, sign with your name. (I did. My device's NVRAM now contains a URL and "bshepp was here." It survives power cycles. It's still there.)

## The humbling part

Then I did the thing you're supposed to do. I searched for prior art — and found that Butterfly Labs open-sourced the BitForce SC MCU firmware, which luke-jr has hosted on GitHub for over a decade. I cloned it and grepped.

Every single thing I'd "found" was right there in the source:

```
PROTOCOL_REQ_SAVE_STRING   18+65   // ZSX - Save String
PROTOCOL_REQ_LOAD_STRING   20+65   // ZUX - Load String
...
USB_send_string("MEMORY EMPTY\n");
```

`Protocol_save_string()`. `Protocol_load_string()`. The literal string `"MEMORY EMPTY\n"` I'd been treating as a discovered sentinel. All of it, implemented and commented, in publicly available firmware.

And then I found BFL's *official* 2012 protocol document — "BitFORCE SC Communication Protocol, Rev 1.0.0, DRAFT" — and it documents `ZJX` (§8.6, Get Firmware Version) outright. It also documents `ZMX` as **Blink** ("respond with OK and blink for ~2 seconds; visually identify the device") — which is notable because cgminer's header mislabels `ZMX` as "FLASH," a scary name for a harmless LED command. So even my one genuinely useful correction — *cgminer got a command's name wrong* — was really just reading the vendor's own spec more carefully than the driver author did.

So let me state it plainly, because the whole point of the previous post was intellectual honesty and I'm not going to abandon it here: **none of these commands are undiscovered. They are documented in the vendor's spec and/or the vendor's open-source firmware. I re-derived them from hardware because I didn't know the spec existed and the mining software never used them.**

The layers, precisely:

| Command | Official 2012 spec | Open firmware | Used by cgminer |
|---|---|---|---|
| `ZJX` firmware | ✅ documented | ✅ | defines, never sends |
| `ZMX` = Blink | ✅ documented | ✅ | **mislabeled "FLASH"** |
| `ZSX`/`ZUX` NVRAM | ❌ not in spec | ✅ implemented | defines, never sends |
| `ZVX`/`ZKX` clock | ❌ not in spec | ✅ implemented | not used |

The most interesting cell is the NVRAM one: the persistent scratchpad is *absent from the published protocol* but *present in the firmware source*. So it's genuinely under-documented — just not undiscovered. And `ZVX`/`ZKX` — set and get a frequency factor — mean you can change the clock over serial, which the published spec never mentions.

## Why it was still worth it

Here's the thing rediscovery gets you that reading the firmware doesn't.

**The firmware source cannot tell you the chip still works.** A comment that says `Protocol_save_string` doesn't tell you whether a thirteen-year-old scratchpad still holds a value across a power cycle in 2026. I measured that. It does.

**And it cannot tell you how the silicon behaves.** So I characterized it, model-free — only counts, timing, repetition, and sensor reads, nothing that assumes a hash model:

- **Four hours of continuous work, zero compute errors.** I submitted one identical work unit thirty-two times and it returned identical nonces every time; over 17,000 jobs across four hours, not a single submit or verify error. This 2013 chip is, by any reasonable standard, flawless.
- **The winner count is Poisson with mean ≈ 1.** The device only ever returns "golden" nonces (those whose hash clears difficulty-1), and the per-job count of them follows a Poisson(1) distribution almost exactly — direct evidence it scans the entire 2³² nonce space per job rather than stopping early.
- **It refuses to get hot.** I ran a supervised sweep, stepping the fan down to *off* under load. It topped out around 41 °C and never erred. You cannot reach a thermal-error regime on a desk; the chip is wildly over-provisioned for its own workload.

None of that is in a header file. It's the difference between "the manual says X" and "I watched the machine do X."

## The one small thing that's actually new

Out of all this, exactly one artifact isn't a re-derivation: a **dead-core detector**.

The reasoning is a little subtle and I like it for that. An aggregate histogram of *where* winning nonces land can *not* map the chip's healthy engine partitions — if each of the 27 engines scans a contiguous sub-range, their winners still sum to a uniform whole, and the partition is invisible. But a histogram *can* expose a **dead** engine: a range that no engine covers shows up as a cold, under-represented band. So the tool runs a per-bin Poisson test, flags contiguous cold runs, and estimates how many engines are dead from the cold fraction. On my (healthy) unit it correctly reports "no dead cores"; on synthetic data with an injected gap it localizes the dead range and estimates the count. It ships as `bfl-asic device health`.

That's the whole honest ledger. A clean Python toolkit (the firmware and cgminer are C). An empirical characterization the source code can't give you. One genuinely new instrument. And a lot of re-derivation that taught me the machine by making me rebuild its vocabulary from the outside.

## A footnote on USB, because it caught me lying

One more honesty beat, because it's a good one. Partway through, my unit dropped off the bus. I'd earlier written — after a short test — that "USB 3.0 works fine, the historical 'won't work on 3.0' wasn't reproducible." Then, sitting on a direct USB 3.0 port, the FTDI chip faulted into Windows Device Manager Code 10, "this device cannot start," and vanished.

So I was wrong, and the tooling caught me: the new port-auto-detect gracefully reported "no device found" instead of hanging, which is how I noticed. The corrected finding: direct USB 3.0 works *at first* and is *unstable over time*; the little galvanic isolator in the chain isn't just protecting the PC from the miner's 12 V rail, it's providing a stable link the bare device on xHCI doesn't get. I'd published the wrong conclusion; I retracted it in the same repo, with the evidence. That's the deal.

## What this is

It's a re-derivation, not a discovery. It's a modern toolkit for a dead machine, an empirical bill of health for a chip that has no business still being perfect, and one small new idea. It's a name written into silicon that will outlive the blog post. And it's a reminder, which I apparently needed, that the honest move — *go check whether it's already known* — costs you a discovery and gives you the truth, which is the better trade every time.

The code, the characterization data, and the sources (BFL's 2012 spec, the open firmware) are in the repo: **[github.com/bshepp/bfl-asic](https://github.com/bshepp/bfl-asic)**.
