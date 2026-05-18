# HF Community Blog Post — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce a publish-ready Hugging Face Hub Article (markdown +
one optimized figure), committed to the repo, telling the project's
story with honest negative-result rigor and pointing at the dataset and
GitHub repo.

**Architecture:** Prose deliverable, not code. The TDD loop is adapted:
"establish verified ground truth → write → verify against spec/ledger".
The plan gives concrete per-section briefs and exact verification
commands instead of pre-writing the 1,200–1,800-word essay inside the
plan (the plan is not the publish artifact). Source of truth lives in
the repo; the author publishes by pasting into `/new-blog`.

**Tech Stack:** Markdown + YAML frontmatter; Python/Pillow for the
figure; git.

**Spec:** `docs/superpowers/specs/2026-05-17-hf-blog-post-design.md`
(the Claims ledger there is binding).

---

## File Structure

- Create: `blog/round-reduced-sha256-learnability.md` — the post
  (frontmatter + body + a non-rendering HTML comment block holding
  alternate titles and publish instructions).
- Create: `blog/assets/round4-cliff.png` — the single figure, optimized
  from an existing committed Tier B sweep PNG.
- Modify: `README.md` — one link to the writeup.
- Read-only fact sources (do NOT modify): `dataset/README.md`,
  `dataset/bounded_null.parquet`, `dataset/learnability_sweep.parquet`,
  `archive/hf-runs/bfl-ml-tierB/summary.json`, `DEVLOG.md`,
  `docs/images/jalapeno-rig.jpg`.

---

### Task 1: Prepare the figure

**Files:**
- Source (read): `archive/hf-runs/bfl-ml-tierB/sweep_seed0.png`
- Create: `blog/assets/round4-cliff.png`

- [ ] **Step 1: Inspect the source PNG to confirm it shows the cliff**

Use the Read tool on `archive/hf-runs/bfl-ml-tierB/sweep_seed0.png`.
Expected: an accuracy-vs-rounds sweep plot, ≈1.0 at rounds 1–3 dropping
to ≈0.5 from round 4 on. If seed0 is not the cleanest, inspect
`sweep_seed1.png`..`sweep_seed4.png` and pick the clearest; use that
path consistently below.

- [ ] **Step 2: Generate the optimized figure**

```bash
cd F:/experimental-projects/bfl-asic && mkdir -p blog/assets && python - <<'EOF'
import os
from PIL import Image, ImageOps
src = "archive/hf-runs/bfl-ml-tierB/sweep_seed0.png"   # <- the chosen seed
im = ImageOps.exif_transpose(Image.open(src)).convert("RGB")
im.thumbnail((1280, 1280), Image.LANCZOS)
out = "blog/assets/round4-cliff.png"
im.save(out, "PNG", optimize=True)
print(out, im.size, f"{os.path.getsize(out)/1024:.1f} KB")
EOF
```

Expected: prints a path, size ≤ 1280px long edge, file < ~250 KB. If
PNG exceeds ~250 KB, re-save as JPEG quality 85 to
`blog/assets/round4-cliff.jpg` and use that filename downstream.

- [ ] **Step 3: Commit**

```bash
git add blog/assets/round4-cliff.png && git commit -m "blog: optimized round-4 cliff figure"
```

---

### Task 2: Establish verified ground truth (the "tests-first" analog)

**Files:** none created; produces a checked facts list used by Task 3.

- [ ] **Step 1: Cross-check every Claims-ledger number**

Run and read:

```bash
cd F:/experimental-projects/bfl-asic && python - <<'EOF'
import pandas as pd, json
bn = pd.read_parquet("dataset/bounded_null.parquet")
ind = bn[bn.experiment=="indistinguishability"].iloc[0]
print("indist:", ind.n_train, ind.n_val, round(ind.accuracy,6),
      [round(ind.ci_lo,5), round(ind.ci_hi,5)], round(ind.ci_resolution_floor,5))
fs = bn[bn.experiment=="full_structure"]
print("full_structure floor set:", sorted({round(x,5) for x in fs.ci_resolution_floor}),
      "n_val:", sorted(set(fs.n_val)))
sw = pd.read_parquet("dataset/learnability_sweep.parquet")
post = sw[sw.rounds>=4]
print("post-cliff points:", len(post), "learnable=True:",
      post[post.learnable].rounds.tolist(),
      post[post.learnable][["tier","seed","rounds","accuracy","ci_lo"]].to_dict("records"))
s = json.load(open("archive/hf-runs/bfl-ml-tierB/summary.json"))
print("tierB elapsed_s:", s["total_elapsed_s"], "status:", s["status"])
EOF
```

Expected (must match the spec ledger): indist `n_train=4000000`,
`n_val=800000`, acc `0.500065`, CI `[0.49897, 0.50116]`, floor
`≈0.00219`; full_structure floor `≈0.0049`; post-cliff = 55 points,
exactly one `learnable=True` (Tier A seed 1 round 6, acc ≈0.506,
ci_lo ≈0.5007). If any number disagrees with the spec ledger, STOP and
flag it (the spec ledger wins only if it matches committed data —
discrepancy = bug to surface, not paper over).

- [ ] **Step 2: Confirm dataset + repo URLs resolve**

```bash
curl -sI https://huggingface.co/datasets/bshepp/round-reduced-sha256-learnability | head -1
curl -sI https://github.com/bshepp/bfl-asic | head -1
```

Expected: HTTP 200 (or 3xx redirect to the same resource) for both.

---

### Task 3: Draft the post

**Files:**
- Create: `blog/round-reduced-sha256-learnability.md`

- [ ] **Step 1: Write frontmatter + a non-rendering ops comment**

Exact frontmatter (authors uses the HF Hub Article convention):

```markdown
---
title: "Teaching a Dead Mining ASIC to Measure Nothing, Carefully: A Round-Reduced SHA-256 Learnability Study"
thumbnail: /blog/assets/round4-cliff.png
authors:
  - user: bshepp
---

<!--
PUBLISH: paste this file's body into https://huggingface.co/new-blog
(requires HF PRO). Set the thumbnail to blog/assets/round4-cliff.png.
Slug: round-reduced-sha256-learnability.
Alternate titles (swap in frontmatter if preferred):
  - "The Round-4 Cliff: A Controls-Gated SHA-256 Learnability Study on Repurposed Mining Hardware"
  - "What a Defunct Bitcoin Miner Taught Me About Negative Results"
-->
```

- [ ] **Step 2: Write the body — 9 sections, ~1,200–1,800 words,
  first-person, only Claims-ledger phrasing**

Section briefs (each must be concrete prose, not bullets-only; lengths
approximate):

1. **Hook (~150w):** a 2013 Butterfly Labs BF0005G Jalapeno — a
   defunct SHA-256 mining ASIC, e-waste — rebuilt as a measurement
   instrument, not a miner. One-sentence promise of the three findings.
2. **The question, scoped (~150w):** can a small, cheap model *learn*
   structure in round-reduced SHA-256? State plainly: a learnability
   instrument measuring easy/cheap learnability, **not** a break
   attempt, **not** a randomness proof.
3. **What I built (~250w):** distinguisher datasets (real vs
   R-round-reduced SHA-256, per-hash feature), a tiny CNN and a linear
   probe, a deterministic harness with positive **and** negative
   controls, and the CI-resolution floor — with the honest aside that
   it is the smallest gain whose 95% CI clears chance at that n, **not**
   a power-based MDE.
4. **Finding 1 — the round-4 cliff (~250w):** rounds 1–3 ≈1.0
   distinguishable; round ≥4 collapses to ≈0.50. Sharp; reproduced
   5 seeds × 2 tiers + fine grid. Of 55 post-cliff points exactly one
   has ci_lo > 0.5 (Tier A seed 1 round 6, acc ≈0.506, ci_lo ≈0.5007)
   — reported via the `learnable` flag, fewer than the ≈2.7 spurious
   one-sided exceedances expected. Embed `blog/assets/round4-cliff.png`
   here with a caption.
5. **Finding 2 — bounded null (~250w):** full 64-round SHA-256,
   best-of-{TinyCNN, linear probe}, 95% CI brackets 0.5 every seed,
   controls pass; floor ≈0.49% at n=800k tightened to ≈0.22% at the
   n=4,000,000 HF cpu-xl probe (acc 0.500065, CI [0.49897, 0.50116]).
   Explicit: a bounded null at this budget — not "SHA-256 is random",
   not a power calc.
6. **Finding 3 — the signal that wasn't (~250w):** apparent
   above-chance iterated-orbit-tail prediction; the **permuted-label
   control scored identically** → label-prior artifact, not learnable
   structure. A first under-validated harness called it positive; the
   fixed harness (Clopper–Pearson + permuted-label control) converted
   it to a correct controlled negative. This is the point of the
   instrument.
7. **Why this shape of result matters (~150w):** negative results,
   controls, reproducibility-from-seed; training data deliberately
   unhosted/regenerable; the dataset is the distilled *evidence*
   (4 Parquet configs, 83 rows). Embed `docs/images/jalapeno-rig.jpg`
   (the rig + sourdough) as the human aside.
8. **Artifacts & repro (~120w):** link the dataset
   `https://huggingface.co/datasets/bshepp/round-reduced-sha256-learnability`
   and the MIT repo `https://github.com/bshepp/bfl-asic`; one line on
   `pip install -e ".[ml]"` + regenerate-from-seed.
9. **Close (~80w):** a dead ASIC as a lesson in measuring nothing
   carefully; invite readers to query the dataset.

Voice: first person, specific, dry where it earns it; zero generic AI
filler, zero hype words ("revolutionary", "groundbreaking"), zero
novelty/cryptanalysis claims.

- [ ] **Step 3: Commit**

```bash
git add blog/round-reduced-sha256-learnability.md && git commit -m "blog: draft the round-reduced SHA-256 learnability post"
```

---

### Task 4: Verify the draft against the spec, fix inline

**Files:** `blog/round-reduced-sha256-learnability.md` (fixes only)

- [ ] **Step 1: Mechanical checks**

```bash
cd F:/experimental-projects/bfl-asic && python - <<'EOF'
import re, pathlib
t = pathlib.Path("blog/round-reduced-sha256-learnability.md").read_text(encoding="utf-8")
body = t.split("-->",1)[1] if "-->" in t else t
words = len(re.findall(r"\S+", body))
print("word count:", words, "OK" if 1200 <= words <= 1800 else "OUT OF RANGE")
for needle in ["huggingface.co/datasets/bshepp/round-reduced-sha256-learnability",
               "github.com/bshepp/bfl-asic", "round4-cliff.png",
               "jalapeno-rig.jpg", "bounded null", "permuted-label",
               "CI-resolution", "0.500065", "0.22", "round 4"]:
    print(("FOUND   " if needle in t else "MISSING ")+needle)
for ban in ["revolutionary","groundbreaking","breaks SHA","cryptanaly",
            "proves SHA-256 is random","world-first","novel attack"]:
    if ban.lower() in t.lower(): print("BANNED PHRASE PRESENT:", ban)
import yaml  # frontmatter must be valid YAML with required keys
fm = t.split("---")[1]
d = yaml.safe_load(fm)
assert d.get("title") and d.get("thumbnail") and d.get("authors"), d
print("frontmatter OK:", list(d))
EOF
```

Expected: word count in [1200,1800]; all needles FOUND; no BANNED
PHRASE lines; `frontmatter OK`. (If `yaml` import fails, `pip install
pyyaml` or eyeball the frontmatter block instead.)

- [ ] **Step 2: Editorial read-through against the Claims ledger**

Re-read the post end to end. Confirm every number/claim matches Task 2
output and the spec ledger verbatim in meaning; confirm the
hardware-provenance honesty (the ML ran on CPU/HF; the ASIC is project
context, no claim it produced the ML results). Fix any drift inline.

- [ ] **Step 3: Commit fixes (if any)**

```bash
git add blog/round-reduced-sha256-learnability.md && git commit -m "blog: fix draft to match the claims ledger"
```

---

### Task 5: README link + push

**Files:** `README.md`

- [ ] **Step 1: Add the writeup link**

Add under the title/intro area of `README.md` (follow the existing
heading style; do not invent a section if a natural spot exists, e.g.
near the dataset/links references):

```markdown
- **Writeup:** [Round-reduced SHA-256 learnability — the story & the negative results](blog/round-reduced-sha256-learnability.md) (also published as a Hugging Face Article — link added on publish)
```

- [ ] **Step 2: Commit and push everything**

```bash
git add README.md && git commit -m "docs: link the blog writeup from the README" && git push origin master
```

Expected: push succeeds; `git status --porcelain` clean.

- [ ] **Step 3: Hand off the publish steps**

Report to the user: the post is committed; to publish, paste the body
of `blog/round-reduced-sha256-learnability.md` into
`https://huggingface.co/new-blog` (HF PRO required), set the thumbnail,
use slug `round-reduced-sha256-learnability`; then send back the public
URL so the README link can be updated. Do **not** attempt the HF
publish from Claude (publish classifier handoff).

---

## Self-Review

**1. Spec coverage:**
- Publish target / mechanics / frontmatter → Task 3 Step 1, Task 5
  Step 3. ✓
- Thumbnail/figure from committed Tier B PNG, optimized → Task 1. ✓
- Title primary + alternates retained → Task 3 Step 1 comment. ✓
- 9-section approved arc → Task 3 Step 2. ✓
- Claims ledger exactness → Task 2 (ground truth) + Task 4 (verify). ✓
- Non-goals (one figure, no new analysis, no novelty/overclaim, no
  auto-publish) → enforced in Task 3 voice note + Task 4 banned-phrase
  scan + Task 5 Step 3. ✓
- README link → Task 5. ✓
- Success criteria (traceable numbers, original voice, valid
  frontmatter, working links, paste-ready) → Task 2/Task 4 checks. ✓
No gaps.

**2. Placeholder scan:** No "TBD/TODO/handle appropriately". Section
briefs specify concrete content, lengths, and exact ledger facts; the
chosen-seed path is explicitly carried forward from Task 1 Step 1.

**3. Type/consistency:** Figure filename `blog/assets/round4-cliff.png`
(with the explicit JPEG fallback note) used consistently in Tasks 1, 3,
4. Frontmatter keys (`title`/`thumbnail`/`authors`) consistent between
Task 3 and the Task 4 YAML check. Dataset/repo URLs identical across
Tasks 2, 3, 5.

No issues outstanding.
