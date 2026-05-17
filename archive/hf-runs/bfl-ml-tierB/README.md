# Tier B sweep — durable archive

Version-controlled copy of the **5-seed Tier B learnability sweep**, the
scientifically load-bearing output of the Tier B HF run. Archived here so
it survives a local disk loss or HF bucket loss (it otherwise lived only
on the HF bucket + the gitignored `hf_results/` mirror).

- **Source:** HF bucket `bshepp/bfl-ml-tierB`, job `6a086568e48bea4538b9fba5`
  (cpu-xl), `run_ml_tier.py --tier B`.
- **Config (per seed):** `run_sweep`, rounds
  `[1,2,3,4,5,6,8,10,12,16,20,24,32,40,48,56,64]`, `n=500_000`,
  `epochs=30`, `model="tiny_cnn"`, `feature="per-hash"`. Seeds 0–4.
- **Contents:** `sweep_seed{0..4}.json` (data of record, 17 points each),
  `sweep_seed{0..4}.png` (derived plots), `progress.json` (idempotent
  completion marker showing all 5 seeds done).
- **Provenance note:** seeds 0–1 also feed the curated public dataset
  (`dataset/source/bfl-ml-tierB/`); seeds 2–4 are the additional
  replication seeds. The harness is deterministic — every file here is
  exactly regenerable from its seed, so this archive is belt-and-braces,
  not the only path back to the data.
- **Not** part of the published HF dataset: `publish_dataset.py`'s
  allow-list does not include this path, so it stays git-only.
