# Design — HF Community Blog post for the round-reduced-SHA-256 project

**Date:** 2026-05-17
**Status:** approved (design), pending spec review
**Topic:** A Hugging Face Hub Article (community blog) for the `bfl-asic`
round-reduced SHA-256 learnability project, pointing at the public
dataset and the GitHub repo.

## Goal

A medium-length (~1,200–1,800 word), first-person, technical blog post
that tells the neat overall story of the project while keeping honest
negative-result rigor as its spine. It must clear HF's stated bar
("high-quality, long, technical, original"; LLM-generated / low-quality
posts are hidden from the feed) — i.e. it must read as genuinely the
author's, specific, and non-overclaiming.

## Publish target & mechanics

- **Target:** Hub Article on the author's profile, authored via
  `https://huggingface.co/new-blog`, rendering at
  `huggingface.co/blog/bshepp/<slug>` and appearing in the Community
  Blogs feed. Requires a HF PRO account (author confirms; not a blocker
  for drafting).
- **Canonical source:** committed to the repo at
  `blog/round-reduced-sha256-learnability.md` with a `blog/assets/`
  figure. The repo copy is the versioned original; the author
  copy/pastes it into `/new-blog` to publish. (HF Articles are authored
  on-Hub, not via a repo PR.)
- **Handoff:** per the established pattern, Claude drafts + commits the
  markdown; the author performs the public HF publish (the publish-time
  safety classifier blocks Claude from the public HF action, so the
  human pulls the trigger — same flow as the dataset).
- **Frontmatter** (Hub Article convention):
  `title`, `thumbnail`, `authors: [- user: bshepp]`.
- **README:** add a one-line link to the post once published.

## Thumbnail / figure

- One figure: the round-4 learnability-cliff sweep plot, sourced from
  an already-committed Tier B fine-grid sweep PNG
  (`archive/hf-runs/bfl-ml-tierB/sweep_seed*.png`), downsized and
  optimized into `blog/assets/` (same web-hygiene approach used for the
  rig photo: EXIF-safe, stripped, < ~200 KB).
- The Jalapeno rig photo (`docs/images/jalapeno-rig.jpg`, already
  committed) embeds lower in the body as the human hook — not the
  thumbnail.

## Title

- **Primary:** "Teaching a Dead Mining ASIC to Measure Nothing,
  Carefully: A Round-Reduced SHA-256 Learnability Study"
- Alternates retained in the post's frontmatter comment for the author
  to swap: "The Round-4 Cliff: A Controls-Gated SHA-256 Learnability
  Study on Repurposed Mining Hardware"; "What a Defunct Bitcoin Miner
  Taught Me About Negative Results".

## Structure (approved arc)

1. Hook — defunct 2013 Butterfly Labs Jalapeno reborn as a measurement
   instrument, not a miner; one-paragraph promise.
2. The question, scoped honestly — can a small/cheap model *learn*
   structure in round-reduced SHA-256? Explicitly a learnability
   instrument, not a break attempt.
3. What I built — distinguisher datasets, tiny CNN / linear probe,
   deterministic harness; the controls and the CI-resolution floor,
   with the honest aside that it is *not* a power-based MDE.
4. Finding 1 — the round-4 cliff: rounds 1–3 ≈100% distinguishable,
   ≥4 at chance; sharp; 5 seeds × 2 tiers + fine grid; the single
   marginal post-cliff exceedance reported, not buried.
5. Finding 2 — a controls-gated bounded null on full SHA-256: no
   structure above ≈0.49% (n=800k), tightened to ≈0.22% (n=4M on HF
   cpu-xl). Plain statement of what a bounded null does and does not
   claim.
6. Finding 3 — the signal that wasn't: apparent orbit-tail
   predictability the permuted-label control unmasked as a label-prior
   artifact. The instrument catching its own false positive.
7. Why this shape of result matters — negative results, controls,
   reproducibility-from-seed; the dataset is the *evidence*, not the
   training data.
8. Artifacts & repro — links to the public dataset and the MIT repo;
   how to regenerate; the embedded figure.
9. Close — a dead ASIC as a lesson in measuring nothing carefully;
   invitation to poke at the dataset.

## Claims ledger (must be stated exactly; no overclaim)

The post must use these and only these, phrased as below:

- **Round-4 cliff:** rounds 1–3 trivially distinguishable (accuracy
  ≈ 1.0); round ≥ 4 collapses to chance (≈ 0.50). Reproduced across
  5 seeds × 2 tiers (Tier A n=200k ×3, Tier B n=500k ×2) and a fine
  round grid. Of 55 post-cliff points, exactly one has a 95% CI lower
  bound above chance (Tier A seed 1, round 6: acc ≈ 0.506,
  ci_lo ≈ 0.5007) — reported via the per-point `learnable` flag, not
  hidden; fewer than the ≈ 2.7 spurious one-sided exceedances expected
  from 55 points.
- **Bounded null (full SHA-256, 64 rounds):** best-of-{TinyCNN, linear
  probe}, 95% CI brackets 0.5 every seed, controls pass. CI-resolution
  floor ≈ 0.49 % at n=800k, tightened to ≈ 0.22 % at the n=4,000,000
  HF probe (acc 0.500065, 95% CI [0.49897, 0.50116]). State explicitly:
  a bounded null at this budget — **not** a claim that SHA-256 is
  random, **not** a power calculation.
- **Dynamics negative:** apparent above-chance orbit-tail prediction
  whose **permuted-label control scored identically** → label-prior
  artifact, not learnable seed→orbit structure. A first under-validated
  harness reported it positive; the fixed harness (Clopper–Pearson CI
  + permuted-label control) converted it to a correct controlled
  negative.
- **CI-resolution floor:** smallest above-chance gain whose 95% CI
  clears chance at that n — explicitly *not* a power-based minimum
  detectable effect.
- **Reproducibility:** deterministic harness; training data is
  regenerable from seed and deliberately not hosted; the dataset is the
  distilled evidence (4 Parquet configs, 83 rows).
- **Links:** dataset
  `https://huggingface.co/datasets/bshepp/round-reduced-sha256-learnability`;
  repo `https://github.com/bshepp/bfl-asic` (MIT).
- **Hardware:** Butterfly Labs BF0005G Jalapeno, BitForce SHA256 SC;
  repurposed, not mined. No claim that ASIC hashing produced these ML
  results (the ML ran on CPU/HF; the ASIC is the project's hardware
  context and honesty about provenance must be preserved).

## Non-goals (YAGNI)

- No multi-figure deep dive; one figure only.
- No new analysis, plots, or numbers beyond what is already verified
  and committed.
- No claim of novelty, cryptanalytic result, or randomness proof.
- No automated HF publishing by Claude.

## Success criteria

- Factually matches the claims ledger; every number traceable to the
  dataset / DEVLOG / repo.
- Reads as original, first-person, technical; no generic AI filler.
- Frontmatter valid for a Hub Article; figure optimized and committed.
- Links to dataset + repo present and correct.
- Author can publish by pasting the committed markdown into
  `/new-blog` with no edits required.
