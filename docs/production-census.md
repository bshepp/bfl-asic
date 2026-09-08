# BFL Jalapeño production census

An independent estimate of **how many Butterfly Labs BF0005G "Jalapeño"
SHA-256 ASIC miners were actually built** — derived from confirmed serial
numbers, because Butterfly Labs never credibly documented it (and the U.S.
Federal Trade Commission found their production claims unsupported).

![Serial numbers of confirmed Jalapeño units across the production run, with the German-tank production estimate](images/production-census.png)

## The confirmed serials

Thirteen board serials confirmed — units held by this project (including the
consecutive `024991`/`024992` pair) plus serials visible in online listings.
**Prices and sources are intentionally omitted:** this is a production study,
not a market survey.

| Serial | Status |
|--------|--------|
| `002659` | held (reference unit) |
| `005794` | held (sacrificial unit) |
| `006068` | observed |
| `007857` | observed |
| `010216` | observed — near-consecutive with `010265` |
| `010265` | observed — near-consecutive with `010216` |
| `013626` | observed |
| `022662` | observed |
| `023617` | observed |
| `024017` | observed |
| `024991` | **held** — consecutive with `024992` (1 apart) |
| `024992` | **held** — consecutive with `024991`; same lot |
| **`025327`** | observed — **highest confirmed serial** |

## The estimate (German tank problem)

The [German tank problem](https://en.wikipedia.org/wiki/German_tank_problem) is
the classic way to estimate a total population from a sample of serial numbers:
the true maximum sits, on average, about one "average gap" beyond the largest
serial you've actually seen.

- `k = 13` confirmed serials, `min = 2,659`, `max = 25,327`
- average gap ≈ `(25,327 − 2,659) / (13 − 1)` ≈ **1,889**
- estimated top ≈ `25,327 + 1,889` ≈ **~27,216**
- MVUE cross-check: `25,327 × (k+1)/k − 1` ≈ **~27,274**

**Estimate: ~27,000 units built (± ~2,100)**, with a hard floor of **≥ 25,327**
— you cannot have built fewer units than the highest serial that demonstrably
exists.

## What the serials show

- **A near-consecutive pair (`010216` / `010265`, 49 apart).** Two units off
  almost the same point on the assembly line. This is the cleanest possible
  A/B: production-time drift is controlled out, so any difference between them
  is *pure unit-to-unit silicon variation*.
- **A large gap (`013626` → `022662`, ~9,000).** Nearly 5× the average gap, and
  it stayed empty as the sample grew to `k = 13` — `006068`, `023617` and
  `024017` all landed outside it. The units above it are the late-production
  cohort most likely to differ (for example, a later firmware build). This gap
  is large enough to test rather than eyeball — see **Is the ~9,000 gap real?**
  below.
- **An even tighter pair — `024991` / `024992`, *one* apart.** Acquired
  together from a single lot, which proves multi-unit lots were numbered
  **consecutively**.
- **Real binning drift is already visible** between our two units: `002659`
  self-reports 27 engines at ~200 MHz; `005794` reports 29 engines at ~214 MHz
  (and a higher estimated hashrate). Same architecture, different bin.

## Is the ~9,000 gap real?

The largest gap in the sample — `013626` → `022662`, **9,036 wide** — is **4.8×
the mean gap** and spans **39.9% of the whole observed range**. The next largest
is 3,361. That is lopsided enough to test rather than eyeball.

For `k` serials the largest spacing has a known distribution under uniform
sampling. Here:

> **P(largest gap ≥ 9,036 | uniform sampling) ≈ 0.045**

The closed form and a 400,000-trial Monte Carlo agree to three decimals
(`scripts/production_census_gap_test.py`). Because this is the distribution of
the *maximum* spacing, it already accounts for us having gone looking at the
biggest gap — it is not a post-hoc artefact. So the gap is unlikely under plain
sparse sampling, though at roughly 1-in-22 it is not excluded.

Four explanations fit:

1. **Chance.** p ≈ 0.045 — unlikely, not excluded.
2. **A genuine skip** — the block was never issued. Candidates: a batch or
   contract-manufacturer boundary, or numbering deliberately advanced. For a
   company the FTC found could not support its claim of 50,000+ machines, a
   serial jump would flatter the production figure. That is a motive, not
   evidence.
3. **The block belongs to other BF-series products.** A `BF0050G` Single is
   confirmed at `002845` — *inside* the Jalapeño range — sharing the `BF00nnG`
   naming scheme, and BFL shipped Singles in volume. If the family shares one
   sequence, `013626`–`022662` may simply be a stretch dominated by a different
   model, which would be invisible here because this sample is collected by
   looking for Jalapeños.
4. **A large batch went to a single holder.** BFL numbered multi-unit lots
   **consecutively** — the `024991`/`024992` pair above proves it — so one large
   buyer receives one large *contiguous* block. Units concentrated in a single
   holding never disperse to individual owners, and so never appear as
   individual listings, working or not. The most likely such holder is **BFL
   itself**: the FTC's central finding was that the company built machines and
   mined on them rather than shipping them, and BFL's own Fall-2013 video shows
   its farm dashboard (`BFL19`–`BFL27`+) running while 20,000+ paid customers
   had received nothing. A retained block would have been liquidated in bulk or
   scrapped at the wind-down — leaving a hole in the *retail* record without any
   hole in *production*.

What a skip would cost:

| | units |
|---|--:|
| contiguous estimate | ~27,200 |
| minus a 9,036 skip | **~18,200** |
| re-fit on the gap-removed serials | ~17,400 built, + 9,036 never issued |

What each explanation implies for the count:

| explanation | Jalapeños built |
|---|--:|
| 1 — chance | ~27,200 (unchanged) |
| 2 — genuine skip | **~18,200** |
| 3 — other BF products in the band | ~27,200 BF-series, fewer Jalapeños |
| 4 — batch to one holder | ~27,200 (unchanged) |

Only explanation 2 moves the headline number. Explanation 3 changes what that
number *counts*. Explanations 1 and 4 leave it intact and merely explain why the
band is invisible to a survey built from retail listings.

**How to settle it.** Any BF-series serial inside `013626`–`022662` is decisive
against a skip. What *kind* of find discriminates the rest:

- a `BF0050G` or other non-Jalapeño BF unit → explanation 3
- **several in-window serials arriving together**, in one lot or from one
  seller → explanation 4, a concentrated holding breaking up
- a single in-window Jalapeño arriving on its own → explanation 1
- continued emptiness while serials accumulate elsewhere → explanation 2

Bulk lots therefore matter more than singles: a concentrated holding is exactly
where in-window serials would be hiding.

No currently known non-Jalapeño serial fills it: the SGL line
(`002397`–`009401`) and the `BF0050G` (`002845`) all sit below `013626`.

**One external data point bears on explanation 2.** BFL demonstrably issued
serial numbers far ahead of deliveries: the FTC complaint states that as of
**August 2014** the company *"had yet to ship a single Monarch machine"* (¶31),
while Monarch serials observed in the wild already reach `8664`. A company
carrying 8,000+ numbers on a product it had delivered *none* of was not
numbering conservatively. That is not proof of a skip — but it is the kind of
behaviour a skip would sit inside.

**Caveat — and a correction to it.** The test assumes uniform sampling, and this
sample is not uniform. The obvious worry would be *survivorship*: a bad batch
died and vanished. That does **not** hold here — the secondary market lists dead
units freely as "for parts / untested", so failure changes a unit's price, not
its visibility. The bias that does survive scrutiny is **concentration**: units
that never dispersed to individual owners are never individually listed, working
or not. That is explanation 4, and it is why this study measures *units that
reached individual owners* rather than units built. BFL's surviving public
material is no help either: the archived 2013 production videos are effectively
wordless b-roll and say nothing about serial numbering.

## Serials count units *built*, not *shipped*

This is the interesting part. A serial is stamped at **manufacture**. The FTC's
case against Butterfly Labs was, in essence, that they *built* machines and
didn't deliver them — allegedly using customers' pre-ordered hardware to
self-mine, and taking ~$50M in orders (settled for **$38.6M** in 2016). The
complaint is specific about the delivery side:

> "as of September 2013, Defendants had failed to ship mining machines to more
> than **20,000 customers** who had paid for the equipment in full." (¶28)

> "As of **August 2014**, Defendants had yet to ship a **single Monarch
> machine**." (¶31)

So a serial-indexed count is a **"how many were numbered at manufacture"**
number — and the gap between that and actual customer deliveries is the scandal
itself, quantified.

**A cross-check worth not over-reading.** BFL publicly claimed *more than
50,000 machines across five product generations*. Independent serial estimates
for the three lines visible to this project land in the same neighbourhood:

| line | estimate |
|---|--:|
| Jalapeño | ~27,200 |
| Single (SGL pooled) | ~10,400 |
| Monarch | ~9,100 |
| **total** | **~46,700** |

Two readings, and this study cannot choose between them:

1. It **supports the method** — BFL's 50,000 was approximately *serials issued*,
   which is exactly what this counts; the deception was in delivery, not in
   numbering.
2. It **proves nothing** — if BFL's numbering outran production, this estimate
   inherits the identical bias. Two figures agreeing because they share a bias
   is not corroboration.

Note the complaint does **not** adjudicate the 50,000 *manufacturing* claim; it
is an action about non-delivery. **No public filing states how many units were
built.**

## Method notes & caveats

- **Small sample.** Thirteen confirmed serials; the estimator's standard error
  is roughly `N/k` ≈ ± 2,100. Every new confirmed serial tightens it — most of all
  a new **maximum** (raises the ceiling) or a serial **below 2,659** (pins the
  start).
- **Contiguity assumed.** The estimator assumes serials are roughly contiguous
  and uniformly sampled. Real production may involve batches, gaps, skipped
  ranges, RMA replacements, or numbering shared with other BFL products — any of
  which would shift the true count.
- **Lot-mates are not independent draws.** `024991`/`024992` came from one
  lot, and the estimator assumes independent uniform sampling. Two
  consecutive serials carry barely more information than one, so the true
  error is a little wider than `N/k` suggests.
- **Numbering may be shared across BFL products.** A `BF0050G` Single has
  been observed at serial `002845` — inside the Jalapeño range — and the two
  share the `BF00nnG` naming scheme. If BFL numbered a whole product family
  in one sequence, this figure counts **BF-series units**, not Jalapeños
  alone. The arithmetic barely moves; what it *counts* would change.
- **No official production figure exists to check against.** The one document
  that would carry a hardware inventory — the Temporary Receiver's report (Eric
  L. Johnson, filed 2014-12-04) — was filed **under seal**, and the court denied
  the FTC's receiver motion on 2014-12-12, winding the receivership down without
  a public inventory. Serial-number estimation is, for now, the only available
  route to a production count.
- **Built ≠ shipped ≠ surviving.** This estimates units numbered at manufacture,
  not units delivered, and not units still running in 2026.

## Contribute a data point

Own a Jalapeño, or spot one in a listing? The board serial is on the rear label
(a photo is enough). A confirmed serial sharpens this estimate at zero cost —
and the two most valuable additions are **any serial above `025327`** or **below
`002659`**. Open a GitHub issue (or `bfl-asic report-issue`) with the serial and
we'll fold it in.

## Sources

- FTC v. BF Labs, Inc. — [complaint (PDF)](https://www.ftc.gov/system/files/documents/cases/140923utterflylabscmpt.pdf),
  No. 4:14-cv-00815 (W.D. Mo., filed 2014-09-15). Quoted above at ¶28 and ¶31.
- FTC — [case page, BF Labs, Inc.](https://www.ftc.gov/enforcement/cases-proceedings/142-3058/bf-labs-inc)
  and [press release](https://www.ftc.gov/news-events/news/press-releases/2014/09/ftcs-request-court-halts-bogus-bitcoin-mining-operation).
- [BF Labs Receivership — civil court documents](https://bflreceiver2.wordpress.com/civil-court-documents/)
  (the receiver's two 2014-12-04 reports are listed as under seal).
- Bitcoin Magazine — [$38.6M settlement](https://bitcoinmagazine.com/business/bitcoin-mining-company-butterfly-labs-settles-case-with-federal-trade-commission-for-m-1456419270)
  (source of BFL's "50,000 machines / five product generations" claim).
- Model codes cross-checked against surviving retail listings, e.g. `BF0050G` =
  BFL "Little Single" SC, 60 GH/s ([WorthPoint](https://www.worthpoint.com/worthopedia/bf0050g-butterfly-labs-bfl-little-535504535)).
- Serial observations and per-line estimates: [`research/ebay-survey/`](../research/ebay-survey/FINDINGS.md).

---

Part of the [`bfl-asic`](../README.md) retro-mining characterization lab.
