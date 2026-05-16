# ML Learnability Instrument — Design Spec

- **Date:** 2026-05-15
- **Status:** Approved (brainstorming complete; pending written-spec review)
- **Author:** Brian Sheppard + Claude
- **Scope:** One new optional subsystem, `bfl_asic/ml/`, plus additive `pyproject.toml`, `cli.py`, and docs changes. No existing pipeline is modified.

---

## 1. Context and motivation

`bfl-asic` is a SHA-256 research/learning platform built around a Butterfly Labs Jalapeno ASIC. It has independent application subsystems (`stats/`, `dynamics/`, `randomness/`) layered over a pure protocol/transport/device stack. This spec adds another: a machine-learning subsystem.

The central reality that shapes the whole design: **full SHA-256 has, by construction, nothing for a model to learn.** Cryptographic security *is* the statement that no efficient algorithm — a CNN included — can distinguish SHA-256 output from true randomness or predict it. A model trained on full SHA-256 converges to chance. That is not a failure; it is the primitive working.

The rich ML work is therefore not "break SHA-256." It is **measuring where learnability lives and where it dies** — by weakening SHA-256 in a controlled way and charting the collapse. This is real, well-known reduced-round cryptanalysis pedagogy, and it directly leverages the round structure already present in `bfl_asic/protocol/work.py`.

## 2. Goals and non-goals

**Goals**

- A reusable "learnability instrument": generate data → train the strongest practical model → measure whether it extracts structure → report the advantage with a confidence bound.
- Four configured experiments on that one instrument (Section 4).
- Strict isolation: torch is required only to *use* the subsystem, never to install or use the rest of the project.
- The project's character preserved: deterministic from a seed, fully testable, scales to an AWS GPU box with zero code change.

**Non-goals**

- No genuine cryptanalytic exploit of full SHA-256. Experiment #4 is a *rigorous bounded null*, not an attack.
- No AWS SDK / boto3 / SageMaker orchestration in code. "Cloud" = ssh to a GPU box and run the same CLI.
- No dataset hosting. Datasets are regenerated from a seed (cheaper and more reproducible than download).
- No changes to `protocol/`, `transport/`, `device.py`, `async_device.py`, `stats/`, `dynamics/`, `randomness/` logic.

## 3. The unifying idea

The four experiments are one instrument pointed at different knobs:

| Exp | Knob | Expected outcome |
|-----|------|------------------|
| #1 sweep | SHA-256 rounds 1 → 64 | accuracy collapses ~100% → ~50%; the curve *is* "where SHA-256 becomes secure" |
| #2 indistinguishability | rounds = 64 (sweep's right endpoint) | ≈50% by design — the lesson is the failure |
| #4 any-structure-in-full-SHA | rounds = 64, widened model/feature search | rigorous bounded null: "no advantage > ε detectable at N samples" |
| #3 dynamics learnability | iterated-hash truncation width | does iterating a one-way function leave seed-predictable orbit structure? same shape, dynamics domain |

#2 and #4 are the rounds=64 endpoint of #1's machinery. #3 is the same instrument with a different knob (truncation width) and a different label (orbit tail/cycle length) in the iterated-hash domain.

## 4. The four experiments

### #1 — Round-reduced learnability sweep (the spine)

For `R` in a configured set (e.g., `1,2,3,4,6,8,12,16,24,32,48,64`): build a balanced dataset of `R`-round SHA-256 outputs (class A) vs true random bytes (class B), train the model, record held-out accuracy / AUC / advantage. Output: a learnability curve over `R`.

### #2 — Pure indistinguishability demo

The `R=64` point of #1, single experiment, reported on its own: full SHA-256 vs true random ⇒ accuracy CI overlaps 0.5. The pedagogical payoff is the *failure*.

### #4 — "Any structure in full SHA-256" (rigorous bounded null)

`R=64`, but widened: both feature extractors, the CNN *and* the linear probe, the largest practical sample size. The result is reported as a **bounded null**: held-out accuracy with a 95% confidence interval, advantage = 2·acc−1 with CI, and the **minimum detectable advantage** at that sample size (a power statement). The conclusion "no structure detected" is emitted *only if* both controls (Section 7) pass; otherwise the run is flagged as an instrument failure, not a null result.

### #3 — Dynamics learnability

Reusing `bfl_asic/dynamics`: iterate a truncated SHA-256 (`sha256_iterate` with a `t`-byte-truncated hash) from random seeds; label each seed with its orbit tail length and cycle length (via `brent_detect`). Task: predict the (binned) tail/cycle length from the seed. Knob: truncation width `t`. Expectation: a well-behaved random function gives Rho/birthday-distributed orbits essentially unpredictable from the seed except at very small `t` where the state space is tiny — the same learnability-collapse shape, in the iterated domain.

## 5. Architecture — `bfl_asic/ml/`

Mirrors the existing subsystem pattern (pure data layer, model layer, harness, snapshot, visualization, CLI group). Each module has one purpose and a well-defined interface.

### `roundreduced.py` — round-reduced SHA-256 (core new artifact)

- **What it does:** numpy-vectorized, batched round-reduced SHA-256 / SHA-256d.
- **Interface:** `round_reduced_sha256(data: np.ndarray, *, rounds: int, double: bool = False, feed_forward: bool = True) -> np.ndarray`. Input shape `(N, L)` uint8, `L ≤ 55` so the message is exactly one 512-bit block after standard padding (this matches the existing `SoftwareHashEngine`'s 32-byte inputs and keeps the implementation single-block — no multi-block logic). Output `(N, 32)` uint8.
- **Implementation:** message schedule and the eight working variables as `(N, …)` uint32 numpy arrays; SHA-256 σ/Σ/Ch/Maj as vectorized bitwise ops with explicit `& 0xFFFFFFFF` masking and modular addition. The round loop runs `rounds` iterations; `W` is expanded via the γ recurrence only as far as needed. `feed_forward` toggles the post-round add-back to `H`. `double` applies the same `rounds`-round function twice.
- **Why fresh, not reused:** the existing `_sha256_compress` is bigint, per-block, scalar — far too slow for millions of training examples.
- **Regression anchor:** at `rounds=64, double=True, feed_forward=True` with standard padding, output must equal `hashlib.sha256(hashlib.sha256(x).digest()).digest()` for random inputs. Same spirit as the NIST reference p-values anchoring `randomness/`.
- **Depends on:** numpy only.

### `datasets.py` — feature extraction and dataset building

- **What it does:** turns hash bytes into model-ready tensors and labels, deterministically from a seed.
- **Interfaces:**
  - `FeatureExtractor` ABC → `extract(outputs: np.ndarray) -> np.ndarray`.
  - `PerHashImage` (default): one hash's 256 output bits → `16×16` binary image.
  - `PerBatchDeviationMap`: per-bit frequency deviation over `K` hashes → `16×16` float image (the original "deviation map" idea; ties into the existing convergence heatmap).
  - `DistinguisherDatasetBuilder(seed, rounds, extractor, n, split)` → deterministic `(X_train, y_train, X_val, y_val)` torch tensors; class A = `round_reduced_sha256(...)`, class B = seeded true-random bytes.
  - `OrbitDatasetBuilder(seed, trunc_bytes, n, split)` → seeds → binned (tail, cycle) labels, computed via `bfl_asic.dynamics` (read-only reuse).
- **Depends on:** `roundreduced`, numpy, torch (tensor output), `bfl_asic.dynamics` (read-only), `bfl_asic.stats.engine` (read-only, for the deviation-map path).

### `models.py` — PyTorch models

- `TinyCNN`: the headline CNN over `16×16×1`; configurable channels/depth; small by default for fast CI.
- `LinearProbe`: logistic regression on flattened input — the rigor baseline and a lower bound on detectable advantage.
- `MODELS: dict[str, type]` registry, selected by name from config.
- **Depends on:** torch.

### `harness.py` — train and evaluate

- **What it does:** deterministic training and evaluation.
- **Interface:** `run_training(config) -> RunResult`. Fixed seeds (input gen, split, shuffle, torch init); CPU/GPU auto-detect; early stopping; returns accuracy, AUC, advantage = 2·acc−1, and a 95% binomial CI on accuracy (Clopper–Pearson) plus minimum detectable advantage at the held-out N.
- **Controls (always run with each experiment):**
  - *Positive control:* a low-`R` config must exceed a high-accuracy threshold (default 0.90). If it does not, the instrument is broken.
  - *Negative control:* true-random vs true-random must have an accuracy CI overlapping 0.5.
  - A null/no-structure conclusion is only valid when both controls pass.
- **Depends on:** torch, numpy, `models`, `datasets`.

### `experiments.py` — recipes

Dataclass configs for the four experiments (Section 4), consumed by `harness`. One config object fully determines a reproducible run.

### `snapshot.py` — results serialization

JSON-serializable result mirroring `stats/snapshot.py` / `randomness/snapshot.py`: experiment config, per-knob metrics, control outcomes, CIs, environment (torch version, device, seed). `save`/`load`, `to_json`/`from_json`, numpy-safe defaults. Writes under `runs/ml/<timestamp>/`, no-overwrite policy, `BFL_ASIC_OUTPUT_DIR` honored — identical conventions to existing subsystems.

### `visualization.py` — plots

- Learnability curve: accuracy/advantage vs knob, with a chance band, CI ribbon, and control markers.
- Training curves (loss/accuracy per epoch).
- Per-bit saliency map: a `16×16` map of what the CNN attends to — at low rounds it lights up specific bits; at 64 it is uniform noise. This is the visual payoff and the pedagogical bridge to the existing heatmaps. Matplotlib `Agg`, like the rest of the project.

### `cli.py` additions (the only edit to existing CLI code)

A new `ml` Click group registered alongside `stats`/`dynamics`/`randomness`, using the **same lazy-import pattern those groups already use** — `bfl_asic.ml` is imported inside the command body, never at module load. Commands:

- `bfl-asic ml sweep` — experiment #1.
- `bfl-asic ml run <experiment>` — #2 / #3 / #4 by name.
- `bfl-asic ml report <snapshot.json>` — text summary.
- `bfl-asic ml plot <snapshot.json>` — figures.
- `bfl-asic ml publish <run-dir>` — **optional, scheduled last, cuttable from the first pass without affecting anything else.** Lazy-imports `huggingface_hub` (from the `[ml]` extra) and pushes the snapshot + trained model + a generated model card to a HF repo as a shareable lab notebook.

If torch is absent, any `ml` subcommand exits with one clean message — `ML subsystem requires: pip install -e ".[ml]"` — not a raw `ModuleNotFoundError`. `bfl-asic --help` and all other commands work with no torch installed.

## 6. Dependencies and isolation

- Core install (`pip install -e .`) is unchanged: numpy, scipy, matplotlib, click, pyserial, pyserial-asyncio.
- New optional extra in `pyproject.toml`: `[project.optional-dependencies] ml = ["torch", "huggingface_hub"]`. `huggingface_hub` is only needed by `ml publish`.
- Import direction is one-way: `ml` imports `dynamics`/`stats` read-only; neither imports `ml`, so torch never leaks into the core.
- Delivery: directly on `master`, dependency-isolated behind the `[ml]` extra and lazy CLI import. One git history.

## 7. Scientific rigor (experiment #4 in particular)

A null result is only trustworthy with controls. Every experiment run carries a positive and a negative control (Section 5, `harness.py`). #4's conclusion is phrased as a bounded null: *"At N held-out samples, held-out accuracy = a [95% CI lo–hi]; advantage = 2a−1 [CI]; the experiment could have detected an advantage as small as ε; no advantage above ε was found."* This is the rigorous form the user asked for — "any structure," reported honestly with its detection floor.

## 8. Testing strategy

- `tests/test_ml_roundreduced.py` — hashlib regression anchor at R=64 (single and double), batched-vs-scalar equivalence, avalanche sanity (1-bit input flip diffuses with more rounds).
- `tests/test_ml_datasets.py` — determinism from seed, shapes, class balance, both extractors.
- `tests/test_ml_models.py` — forward shapes, parameter counts within budget.
- `tests/test_ml_harness.py` — **positive control learns, negative control fails** (the documentation anchors), determinism across two identical seeded runs.
- `tests/test_ml_cli.py` — tiny-config smoke for each command.
- `tests/test_ml_optional.py` — `bfl-asic --help` and a non-ml command succeed with torch import simulated as absent; `ml` subcommand emits the friendly install message.
- Heavy training is `@pytest.mark.slow` and excluded from the default fast run. ML tests skip cleanly when torch is not installed, so the default `pytest` stays torch-free and the existing ~671-test fast suite is unaffected.

## 9. Build order (one plan, incremental)

1. `roundreduced.py` + its regression-anchor tests.
2. `datasets.py` (per-hash extractor first) + `models.py` + `harness.py` with controls.
3. Experiment #1 (`ml sweep`) + `snapshot.py` + `visualization.py` (learnability curve) + CLI wiring + torch-free guarantee test.
4. Experiments #2 and #4 (same machinery + bounded-null reporting + saliency map) + `PerBatchDeviationMap` extractor.
5. Experiment #3 (`OrbitDatasetBuilder` reusing `dynamics`) + dynamics learnability curve.
6. `ml publish` (optional, cuttable).
7. Docs bookkeeping: README (Quick Start + Learning), LEARNING.md (new section/week), DEVLOG.md entry, `bfl-asic-repurpose.md` status banner, CLAUDE.md architecture note, test-count refresh.

## 10. Risks and mitigations

- **Vectorized SHA correctness** → the hashlib regression anchor + batched-vs-scalar test pin it before any model is trained.
- **Training nondeterminism** → single seed threaded through input gen, split, shuffle, and torch init; CPU default in CI; a determinism test asserts two identical seeded runs match.
- **False "structure" from data leakage** (e.g., class-imbalance or generator artifacts the model latches onto instead of SHA structure) → the negative control (random vs random) must fail; if it "succeeds," the pipeline is leaking and the run is rejected.
- **CI time** → tiny model on a tiny dataset for default tests; real training behind `slow`.
- **Scope creep into a cryptanalysis project** → Section 2 non-goals; #4 is explicitly a bounded null.
