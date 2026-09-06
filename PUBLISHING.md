# PUBLISHING

**Status:** note, written 2026-09-05. Where this project's work goes when it ships,
and what it is allowed to claim when it gets there.

Conventions, venue details, and the publication ledger live in
`F:\utility-projects\publish-all-the-things`. **Add a ledger row when anything
ships.** The governing constraint over there is *the goal is contact, not reach* —
which suits this project unusually well, because retro-mining hardware has a small,
findable, opinionated audience and almost no passing traffic.

---

## What is already out

| What | Where | When |
|---|---|---|
| The repo | `github.com/bshepp/bfl-asic` | 2026-02-26 · 1 external star |
| Round-reduced SHA-256 dataset | `huggingface.co/datasets/bshepp/round-reduced-sha256-learnability` | 2026-05-17 |

| HF Post — round-4 cliff | `huggingface.co/posts/bshepp/401535278039137` | 2026-05-18 · 1 reaction, no comments |
| HF Post — command surface | `huggingface.co/posts/bshepp/223913258822282` | 2026-08-16 · 4 reactions, no comments |

**Checked against Hugging Face 2026-09-05.** The last two were published and were
missing from the ledger; they are in it now.

Three things that check settled:

- **`README.md` is wrong about the format.** It says the learnability writeup was
  "also published as a Hugging Face Article — link added on publish". It went out
  as a **Post**, not an Article, and there is no bfl-asic Article at all. Those are
  different surfaces with different lengths and audiences. Fix that line, and
  either drop the promised link or point it at the Post.
- **`hf-post-jalapeno-2.txt` is not among the published posts** — the two-Jalapeño
  nonce agreement and the production census, the strongest draft in the folder.
  Treat this as *unconfirmed rather than unpublished*: HF reports four posts on
  this account and only two can be enumerated even with a valid token, so check
  while logged in before assuming it never went out.
- **`hn-submission.txt` and `hackaday-tip.txt` cannot be checked from Hugging
  Face.** Still open, and still worth ten minutes.

**Neither Post drew a single comment.** Four reactions on the better one is
acknowledgement, not contact — `venues/huggingface.md` now records this. The post
that did better is the one that leads with an admitted mistake, which is the same
pattern `venues/seqfan.md` observed: the audience rewards being situated and
honest over being impressive.

## This project is not one category

The style guide at `F:\webpages\briansheppard.com\epistemological_style_guide.md`
governs. This repo holds at least four different kinds of work and they do not share
a category, so they must not share a framing:

- **The lab itself** — `bfl_asic`, `characterize_source`, dead-core `health`, the
  device-agnostic core across a growing fleet. **Tool / Infrastructure.** Claim what
  it does, who would use it, what gap it fills. Do not claim it reveals anything
  about SHA-256.
- **The round-4 cliff** — distinguishable through 3 rounds, chance from round 4 out
  to 64, reproduced across 5 seeds, dataset deposited. **Research Finding**, and a
  *negative* one. It is listed in `publish-all-the-things/WINNOW.md` under negative
  results worth publishing, which is the correct home for it.
- **The two-Jalapeño nonce agreement and the production census** — two 2013 chips
  fed identical work return an identical winning-nonce set, which is ground truth
  that both still compute SHA-256 correctly thirteen years on; plus ~28,000 units
  estimated from serial numbers via the German-tank method and the FTC
  built-not-shipped angle. **Research Finding.** Falsifiable, method stated,
  checkable by a stranger. This is the strongest story in the repo.
- **The command-surface re-derivation** — undocumented commands "found", then traced
  to Butterfly Labs' own 2012 spec and open firmware. **Implementation of Published
  Work**, and the honest framing is already in the draft: *re-derivation, not
  discovery.* Keep that sentence. It is the reason the piece is good.

The failure mode `conventions/category-to-venue.md` exists to catch is the middle
two collapsing into the first — the lab is not evidence about SHA-256, and the
census is not a property of the toolkit.

## The video work

The live question as of 2026-09-05: a disassembly of a sacrificial Jalapeño, and the
repair of device #4, the GekkoScience 2Pac with the lifted USB data pad.

**These are two films and should not be one.**

- **The Jalapeño teardown is a reference document.** Slow, complete, found by search
  years later. `venues/youtube.md`'s durability argument is the only real reason it
  is worth the effort — contact arrives thin over years instead of in one afternoon.
- **The 2Pac repair is a story.** Symptom, diagnosis, fix, verification. It has an
  ending, its audience owns the same board, and its fault has a searchable name.
  **If only one gets made, make this one.**

**The shoot produces a plate set; the video is derived from it.** The overhead arm
over the gridded mat is a copy stand. Shoot every stage as a locked still at a fixed
height — unit whole, case off, board top, board bottom, heatsink off, die exposed —
and those plates go in `docs/images/`, outliving the footage. Organise the session
around the plates and let the video fall out of it, never the reverse.
`venues/youtube.md`: *do not gate anything behind the video; the repo and the
write-up stay the primary record.*

**Two optical layers, and they divide cleanly:**

| Layer | Tool | Scale |
|---|---|---|
| Context — hands, board, tools | Z50 overhead on the arm | ~50–200 mm |
| Detail — the joint | USB microscope over USB | ~5–15 mm |

The lifted-pad fault sits at roughly 10–15 mm across, which the scope handles
easily. No macro lens or extension tubes are needed for this job.

**Characterise the scope before the first take.** Its listing claims 16 MP and
1200×; both numbers are almost certainly marketing — the sensor is likely
interpolated, and magnification is not a physical quantity without a stated display
size and working distance. This is a model-free characterization lab: point that at
the instrument. Put a rule or a stage micrometer under it, and for each detent
record **working distance, field of view in mm, and µm per pixel**. One table in
`docs/`. It buys a real scale bar for every scope still — which turns the repair
images into measurements — and it finds the *usable* magnification, since working
distance collapses at the top end and an iron will not fit under it.

**The gridded mat is a claim, not a background.** If the measurement lines are
legible, people will measure off them. Locked height, perpendicular, no zoom change
between plates — or the grid is a false precision cue, which is the same offence as
implying a QPU where a simulator ran.

**Narrate after, not during.** For a teardown this is strictly better: you do not
know what you are looking at until you have looked, live narration commits guesses
to the permanent record, and post-narration lets you cite the protocol and firmware
work that already exists in this repo.

Practical notes: the built-in ring light will blow out solder, because solder is a
mirror — diffuse it or kill it and light from the side. A black mat plus a dark PCB
plus one overhead source is mush; use two diffused sources at about 45° from
opposite sides and keep a light surface for dark components. Check the Z50's clip
limit and whether it will run on USB-C power before a long session, and note the
screen flips *down* into the arm mount, so plan on an external monitor or a
generation with a vari-angle screen.

**Before publishing any image:** `publish-all-the-things/conventions/media.md`, and
the hard rule it points at. The Z50 can be geotagged via SnapBridge location sync
from a phone — confirm that is off. The phone photographs in this very repo are the
case that produced that convention.

## Venues, in order

1. **github** — the plate set and the write-up land here first. Everything else
   points at it. Already the project's home; this is a commit, not a launch.
2. **hackaday** — *not yet in the registry; see below.* A tip draft already exists
   in `blog/`, and for a 2013 ASIC teardown with a production census attached this
   is very likely the highest-contact venue available to this project.
3. **hackernews** — a draft exists. The census plus the nonce agreement is the
   story; the toolkit is not. Submit once, do not resubmit.
4. **youtube** — the teardown and the repair, per the plan above. Both are
   Tool / Infrastructure; the census is the finding they *point at*, not a claim
   the video makes. Review the dormant account before drawing attention to it —
   `venues/youtube.md` Gotchas.
5. **reddit** — the repair, where 2Pac owners are. Per-sub rules are strict.
6. **huggingface** — already used for the dataset; the Articles are the open
   question above.
7. **video-short** — probably not. Apply the test in `venues/video-short.md`
   honestly: is the artifact visually native, or would the clip be an advert for it?
   A die shot might pass. A repair almost certainly does not.

## A registry gap this project exposes

**There is no `venues/hackaday.md`.** Seventeen venue files, and the one that fits a
retro-hardware teardown with a documented method is missing — while a finished tip
draft sits in `blog/`. Hackaday's tip line, its comment section, and its audience
are a much better match for this work than most of the registry. Raise it there
rather than routing around it.

## Framing rules

- Lead with the mechanism, not the delight. *Two dead miners agree on the same
  winning nonces* is a fact; *isn't old hardware wonderful* is the internal register.
- Never let the lab claim the finding, or the finding claim the lab.
- Keep "re-derivation, not discovery" wherever the command surface is discussed. The
  correction is the interesting part and removing it would be the one genuinely
  dishonest edit available here.
- The name `bfl-asic` is narrower than the scope. Say "retro mining silicon" in any
  short form, or the reader expects one device.
