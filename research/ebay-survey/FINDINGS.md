# BFL eBay survey — findings

Images in this folder, named by the operator's verified pass (2026-09-08):
`MODEL-SERIAL-STATUS-PRICE[-auction].webp`. `sold` = it cleared; `unsold` =
asking price only; `auction` = closing bid incl. shipping + est. tax, rounded.

Analysis: `analyze.py` (reproducible).

## The chassis holds THREE models, not one

The BFL "Single" enclosure is shared by **BF0050G**, **SGL300G** and
**SGL600G** — identical from the outside. Partial external tell:

- **1× 6-pin PCIe** (+ one blanked cutout) => **SGL300G**
- **2× 6-pin PCIe** => **BF0050G _or_ SGL600G** — the label is required

(An earlier claim here that 2 connectors implies SGL600G was **wrong**;
`002845` is a BF0050G with two connectors.)

Two naming generations are in play: **BF00nnG** and **SGLnnnG**. Surviving
retail listings confirm the codes: `BF0005G` is the Jalapeño (5 GH/s) and
**`BF0050G` is the BFL "Little Single" SC (60 GH/s)**. Monarch uses a separate
**4-digit** serial format entirely.

## Observed units

| model | serial | status | price | note |
|---|---|---|---|---|
| BF0005G Jalapeño | `005794` | owned | $35 | our sacrificial unit |
| BF0005G Jalapeño | `006068` | unsold | $160 | **new to census** |
| BF0005G Jalapeño | `013626` | unsold | $125 | already in census; now photo-backed |
| BF0005G Jalapeño | `023617` | unsold | $75 | **new to census** |
| BF0005G Jalapeño | `024017` | unsold | $170 | **new to census** |
| BF0005G Jalapeño | 3× unknown | **sold** | **$220 / 3** | ~$73 each; box art photos belong to this lot |
| BF0050G Single | `002845` | unsold | $125 | 2 connectors |
| SGL300G | `002476` | **sold** | **$60** | 1 connector |
| SGL300G | `003263` | **sold** | **$40** | auction close |
| SGL300G | `003522` | unsold | $110 | |
| SGL600G | `002397` | **sold** | **$80** | label reads `002397`, not `023970` |
| SGL600G | `005729` | unsold | $110 | |
| SGL600G | `009401` | unsold | $320 | ships w/ 13 V @ 31 A (~400 W) brick |
| SGL600G? | `002468` | — | — | model not on label — **unconfirmed** |
| SGL600G? | blurred | unsold | $110 | serial unreadable — excluded from stats |
| Monarch | `6773` `6890` `7334` `8664` | **sold** | **$140 / 4** | ~$35 each, ONE lot |
| Monarch | `6422` | unsold | $180 | |
| Monarch | `6541` | unsold | $140 | |

## Serials interleave across models

`2397`(600G) `2468`(?) `2476`(**300G**) `2845`(**50G**) `3263`(300G)
`3522`(300G) `5729`(600G) `9401`(600G)

**Three different models fall within 448 of each other** (2397 / 2468 / 2476 /
2845). Under separate per-SKU sequences that requires three product lines to
coincidentally sit at ~2,400–2,900 simultaneously. Under one shared sequence
it is simply expected. **Interleaved is the better-supported hypothesis.**

## Market: asking prices are 2–4x what things actually clear at

| model | actually SOLD | asking (unsold) |
|---|---|---|
| Jalapeño | ~$73 ea (3-lot @ $220) | $75 – $170 |
| SGL300G | $40 – $60 | $110 |
| SGL600G | $80 | $110 – $320 |
| Monarch | ~$35 ea (4-lot @ $140) | $140 – $180 |

Cheapest route to hardware is clearly **multi-unit lots**. Monarch is the
cheapest per unit observed (~$35).

## Caveats that limit the Monarch estimate

German-tank assumes independent, uniform sampling. **Four of the six Monarch
serials came from a single 4-unit lot** — lot-mates are not independent draws,
so the Monarch figure is the weakest here. The same caveat already applies to
the published Jalapeño census, where `024991`/`024992` are lot-mates.

**And Monarch numbering ran far ahead of delivery.** The FTC complaint states
that as of **August 2014** BFL *"had yet to ship a single Monarch machine"*
(¶31) — one month before the company was shut down — yet observed Monarch
serials already reach `8664`. So Monarch serials measure *numbering*, and quite
possibly not even manufacture; the units that reached the wild presumably did so
through the wind-down. Treat ~9,100 as an upper-bound-ish figure for numbers
issued, not a count of machines built.

## Open question with real consequences

Jalapeño and Single serial ranges **overlap** (Jalapeño 2659–25327, Single
2397–9401), and a BF0050G sits at 2845 inside the Jalapeño range. If BFL used
one sequence per *family* (or globally), then the published "~28,000
Jalapeños" is really "~28,000 **BF-series units**" — the number barely moves,
but **what it counts changes**. See `analyze.py` H1/H2/H3.

## Fields to capture on the next pass

Filenames currently encode **model / serial / status / price**. Two further
fields have proven to matter and are not being recorded:

- **Condition** — `working` / `for parts` / `untested`. The prevalence of
  "for parts / untested" listings is what **rules out a quality explanation**
  for the Jalapeño serial gap: dead units still get listed, so failure changes a
  unit's price, not its visibility. Recording this makes that argument evidence
  rather than an impression.
- **Firmware version**, where a listing or seller can supply it. Expect this to
  be **sparse** — most listings never power the unit up — but it is the only
  dating handle available: firmware tracks serial position in our own fleet
  (`002659`/`005794` run 1.0.0; `024991`/`024992` run 1.2.9). Enough of these
  and the two edges of the serial gap can be dated, which is the concrete test
  for the cancelled-production-run explanation.
- **Lot size and seller provenance** — single vs `n`-unit lot; one seller with
  many units; farm / data-centre / estate liquidation wording. A concentrated
  holding is the leading non-skip explanation for the gap, and bulk lots are
  precisely where in-window serials would hide.

**Note on the multi-unit lots.** The 3-unit Jalapeño lot and the 4-unit Monarch
lot have **no serials visible in their listing photos** — the serials are not
merely unread, they were never pictured. Those listings are still useful data
points: two multi-unit lots in a 23-listing sample is evidence that **bulk
movement is common**, which is the mechanism the concentrated-holding
explanation requires.

**Open channel:** serials for lots like these have to come from **seller (and
where possible buyer) outreach** rather than from the photos. A rear-label photo
is all that is needed — see the "Contribute a data point" section of
[`docs/production-census.md`](../../docs/production-census.md). Ask for the
**model code as well as the serial**, since the same chassis housed BF0050G,
SGL300G and SGL600G.

## Sources

- FTC v. BF Labs, Inc. — [complaint (PDF)](https://www.ftc.gov/system/files/documents/cases/140923utterflylabscmpt.pdf),
  No. 4:14-cv-00815 (W.D. Mo., 2014-09-15); ¶28 (20,000+ paid-but-unshipped
  customers as of Sept 2013) and ¶31 (no Monarch shipped as of Aug 2014).
- [BF Labs Receivership — civil court documents](https://bflreceiver2.wordpress.com/civil-court-documents/);
  the Temporary Receiver's two 2014-12-04 reports are **under seal**, so no
  public hardware inventory exists.
- `BF0050G` = BFL "Little Single" SC, 60 GH/s — surviving retail listing
  ([WorthPoint](https://www.worthpoint.com/worthopedia/bf0050g-butterfly-labs-bfl-little-535504535)).
- Prices/status in the table above are read from the listing photos in this
  folder; the price-free production study lives in
  [`docs/production-census.md`](../../docs/production-census.md).
