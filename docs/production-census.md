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

*A note on reasoning.* What follows is inferred from the **serial distribution
alone**. Butterfly Labs' regulatory history is context, not evidence: the FTC
action concerned non-delivery and marketing claims, and is silent on serial
numbering. Explanations are weighed on what the numbers support, not on the
company's eventual reputation.

Four explanations fit:

1. **Chance.** p ≈ 0.045 — unlikely, not excluded.
2. **A block that was never issued.** Serial ranges are routinely *allocated*
   before they are consumed, so a reserved block that never got built leaves a
   permanent hole. Ordinary causes, roughly in order of plausibility: an
   ERP/MRP block reserved per work order, site or SKU and never used; a
   **production run cancelled or cut** — BFL announced Monarch around August
   2013, so serials pre-allocated to a Jalapeño batch dropped in that pivot
   would simply never be issued; a second site or contract manufacturer with
   its own range; an RMA/replacement reserve that went barely used; or plain
   clerical error — a counter reset, a misconfigured increment, a botched
   migration. For a company that missed nearly every date it published,
   disorganisation is a well-evidenced candidate.

   A *deliberate* inflation is the **least** supported version of this. Serials
   on rear labels were never a published production figure and nobody was
   auditing the sequence, so a skip would have deceived no one — the hypothesis
   has no beneficiary. It is also unevidenced: the FTC record says nothing
   whatever about serial numbering.
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
   individual listings, working or not — a hole in the *retail* record with no hole
   in *production*. Any bulk purchaser produces this: a mining operation, a
   reseller, a distributor, or an overseas buyer. BFL itself is one candidate
   among them, since it demonstrably retained machines, but **nothing in the
   serial data points to any particular holder** — the distribution shows only
   that a block is missing from the resale market, not who has it.

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
| 2 — block never issued | **~18,200** |
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

**A note on what serials track.** BFL issued serial numbers independently of
deliveries: the complaint records that as of **August 2014** the company *"had
yet to ship a single Monarch machine"* (¶31), while Monarch serials observed in
the wild already reach `8664`. That is a caution about *interpretation* — a
serial-derived figure counts **numbering**, which need not track delivery, and
need not strictly track completed manufacture either. It does not favour any one
of the four explanations above.

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

Own a Jalapeño, or spot one in a listing? The rear label carries both the
**model code** and the **serial** — a photo of it is enough. Add the **firmware
version** if the unit powers up: it is the only dating handle available, since
firmware tracks serial position (`002659`/`005794` run 1.0.0; `024991`/`024992`
run 1.2.9).

Three finds are worth far more than a random serial:

1. **Any BF-series serial inside `013626`–`022662`.** This window is a
   **pre-registered test** — the ~9,000-wide gap analysed above. A single serial
   landing inside it settles the question outright. If *several* arrive together
   from one seller or one lot, that points to a concentrated holding rather than
   chance. This includes non-Jalapeño `BF00nnG` units.
2. **Any serial above `025327`** — raises the confirmed ceiling, the single most
   powerful addition to the estimate.
3. **Any serial below `002659`** — pins the start of the run.

**When does a still-empty window become conclusive?** Under the null (no skip,
uniform sampling) a new serial lands inside it with probability ≈ 0.33, so every
one that misses is evidence:

| further serials, all missing | p | census size |
|--:|--:|--:|
| 8 | < 0.05 | 21 |
| 12 | < 0.01 | 25 |
| 18 | < 0.001 | 31 |
| 35 | ~10⁻⁶ | 48 |

The existing thirteen do **not** count toward this: the window was derived from
them, so reusing them would be circular. Only serials found from here on are
evidence. Reproduce with `scripts/production_census_gap_test.py`. (It assumes
uniform sampling, which a listings-derived sample is not — treat the counts as a
floor on the data needed.)

Open a GitHub issue (or `bfl-asic report-issue`) with the serial and we'll fold
it in.

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
