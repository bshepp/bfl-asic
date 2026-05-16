# Learning Path: SHA-256 and Cryptography with the BFL Toolkit

A guided study plan that pairs this repository's tools with high-quality
free lecture courses, so the theory and the lab work reinforce each
other.  Designed for a self-directed learner who has the device (or just
the simulator) and a few hours per week.

---

## What this toolkit teaches, what it does not

**Teaches well** -- through the code and the visualisations:

- The *statistical* properties of SHA-256 output: bit uniformity,
  avalanche, byte distribution, spectral flatness, entropy.
- How those properties are *measured* empirically (`bfl_asic/stats/`,
  `bfl_asic/randomness/`).
- What a *one-way function* feels like to interact with: orbits, cycles,
  rho structure when SHA-256 is iterated (`bfl_asic/dynamics/`).
- How a hash function is *used* as a primitive at the hardware level: a
  miner accepts work, computes hashes, returns nonces (`bfl_asic/protocol/`,
  `bfl_asic/device.py`).
- How real hardware behaves vs the ideal: firmware quirks, ADC noise,
  USB bottlenecks (see `DEVLOG.md` 2026-03-02 entry).

**Does not teach** -- you need other resources for these:

- The *construction* of SHA-256 internally (compression function, round
  constants, message schedule).  Paar's lectures fill this gap.
- Symmetric ciphers (AES), public-key crypto (RSA, ECC), digital
  signatures, key exchange, TLS, certificates, side-channel attacks.
- Why hashes are useful in *protocols* (HMAC, commitments, signatures,
  proof-of-work).  Boneh's course and the Princeton book fill this gap.

> **Important framing:** SHA-256 is a *hash function*, not encryption.
> Encryption is reversible (AES, RSA); hashing is one-way.  Everything
> this toolkit demonstrates is about the properties that make a one-way
> function *cryptographically useful* -- which is the foundation that
> HMAC, signatures, commitments, blockchain, and proof-of-work all rest
> on.  If you want to learn AES or RSA, those need a separate setup.

---

## Primary resources

### 1. Christof Paar -- "Introduction to Cryptography" (YouTube, free)

**Best single pairing with this toolkit.**  ~24 university lectures from
Ruhr-Universität Bochum, all free on YouTube.  Search:

> `Christof Paar Introduction to Cryptography`

Watch lectures 11-12 (hash functions, Merkle-Damgård, SHA family).
Paar will draw the SHA-256 round on the board; afterwards you'll be
able to read every line of `bfl_asic/protocol/work.py` and recognise
the round constants and message schedule.

Lectures 1-4 give you symmetric crypto context.  Lecture 13 covers
MACs and HMAC, which is the natural next step after you understand a
hash function.

**Pairs with:**
- `bfl_asic/protocol/work.py` -- the midstate computation he describes
- `bfl_asic/stats/` accumulators -- he motivates the avalanche property
- `bfl_asic/randomness/` -- he explains why hash outputs *look* random

### 2. Dan Boneh -- "Cryptography I" (Coursera / Stanford, free to audit)

The rigorous, mathematical complement to Paar.  Free to audit.  Six
weeks of material:

- **Weeks 1-2**: stream ciphers, PRGs, statistical distance.  Useful
  framing for *why* the NIST tests in `bfl_asic/randomness/` work the
  way they do.
- **Week 5**: hash functions -- collision resistance, Merkle-Damgård,
  HMAC, the random-oracle model.  This is the formal theory behind
  what Paar showed you visually.

**Pairs with:**
- `bfl_asic/randomness/` -- his PRG-security definitions are what NIST
  tests empirically check.
- `bfl_asic/dynamics/` -- he explains why a random-function model
  predicts the rho-shaped orbits you see.

### 3. Princeton -- "Bitcoin and Cryptocurrency Technologies"

Narayanan, Bonneau, Felten, Miller, Goldfeder.  Free PDF textbook +
free Coursera course + free YouTube lecture playlist.  Search:

> `Bitcoin Princeton textbook PDF`
> `Bitcoin Princeton Narayanan Coursera`

Chapter 1 is "Introduction to Cryptography & Cryptocurrencies" --
hash puzzles, proof-of-work, Merkle trees.  This is exactly what your
physical BFL device was *built* to do.  After this you'll understand:

- Why the firmware only returns *winning* nonces (the design choice
  that makes hash-property research awkward and forces the
  `SoftwareHashEngine` workaround in `bfl_asic/stats/engine.py`).
- The motivation for App 3 (PoW tokens) and App 7 (commitments) in
  `bfl-asic-repurpose.md`.
- Why the 42-work-submission firmware limit (DEVLOG.md 2026-03-02) is
  a stock-mining-firmware artefact, not a hardware limit.

**Pairs with:**
- The hardware layer (historical/economic context for why this ASIC
  exists in the first place).
- The unimplemented roadmap apps (3, 4, 7) -- this book provides the
  conceptual basis.

### 4. Computerphile -- Mike Pound hash / crypto videos

Short single videos, not a course.  Best as *introductions* or
*follow-ups* to something you just saw in the lab.  Search:

> `Computerphile SHA-256`
> `Computerphile Mike Pound hashing`
> `Computerphile HMAC`

Each is ~10-20 minutes and Mike Pound's pedagogy is among the best on
YouTube.  Watch one *before* starting on Paar to set the stage, then
again *after* a topic to consolidate.

---

## Suggested week-by-week path

### Week 1 -- Visual intuition

Goal: get a feel for "hash output looks random."

- Watch Computerphile's SHA-256 video.
- Run the convergence animation:
  ```bash
  bfl-asic stats animate-convergence --samples 100000 --frames 60
  ```
- Open `runs/animations/convergence-*.gif` and watch the speckle fade.
- Generate a static dashboard:
  ```bash
  bfl-asic stats run --samples 100000 --plot
  ```
- Open the PNG and inspect each panel: bit-frequency heatmap, Hamming
  histogram vs Binomial(256, 0.5), byte distribution, correlation
  matrix.

### Weeks 2-3 -- The construction of SHA-256

Goal: understand the algorithm, not just its outputs.

- Paar lectures 11-12 (hash functions, SHA-256 internals).
- After lecture 11, open `bfl_asic/protocol/work.py` and read
  `compute_midstate()`.  You should now recognise the K constants,
  the message schedule expansion, and the round function (Ch, Maj,
  Sigma, sigma).
- Optional exercise: instrument `_compress_block()` to log the eight
  working variables `(a, b, c, d, e, f, g, h)` after each round.
  Watch them mix.

### Week 4 -- Why the properties hold

Goal: understand the formal theory under the lab measurements.

- Boneh Crypto I, Week 5 (hash functions and MACs).
- Run the randomness battery:
  ```bash
  bfl-asic randomness run --hashes 10000
  ```
- For each NIST test in the output, find the property in Boneh's
  lectures that the test is checking.  Cross-reference
  `bfl_asic/randomness/tests.py` -- every function corresponds to a
  formal definition.
- Boneh's "statistical distance" lecture from Week 2 is the
  theoretical concept behind the p-values you're computing.

### Week 5 -- Iterated dynamics, finite functions

Goal: see SHA-256 as a deterministic map on a finite state space.

- Run the dynamics module:
  ```bash
  bfl-asic dynamics run --seeds 5 --max-iterations 10000 -o dyn.json
  bfl-asic dynamics plot dyn.json
  ```
- Read `bfl_asic/dynamics/rho.py` -- Floyd's and Brent's cycle
  detection.  These are general-purpose algorithms; SHA-256 is just
  the random-looking function you're applying them to.
- Background reading: Knuth Vol 2 (Seminumerical Algorithms), section
  on random functions and cycle detection.  Alternatively, search
  for "Pollard's rho algorithm" and "birthday paradox" treatments
  online.

### Week 6 -- Hash functions in protocols

Goal: see hashes as components of real systems.

- Princeton Bitcoin book, Chapters 1-3.
- Connect concepts back to the toolkit:
  - **Hash puzzles** -- what the ASIC actually computes.  The 5 GH/s
    rate × difficulty 1 means ~0.86 seconds per nonce range.
  - **Merkle trees** -- foreshadows App 4 (data authentication) and
    App 5 (preimage search) on the roadmap.
  - **Commitments** -- foreshadows App 7.
- Optional: implement App 3 (proof-of-work token minting,
  Hashcash-style) as your first contribution to the toolkit.

### Beyond Week 6 -- where to go next

Once hash functions feel intuitive, the natural extensions are:

- **HMAC and authenticated encryption** -- Paar lectures 13-14,
  Boneh Crypto I Week 4.
- **Public-key crypto** -- Boneh Crypto I Weeks 5-6, Paar lectures
  15-20.
- **Digital signatures** -- Paar lectures 17, including post-quantum
  hash-based signatures (SLH-DSA / SPHINCS+, which is built entirely
  out of SHA functions and is mentioned as App 4 in
  `bfl-asic-repurpose.md`).
- **Side-channel and hardware attacks** -- App 9 in the roadmap.

### Week 7 — Where learnability dies

Goal: see, empirically, that cryptographic strength == unlearnability.

- Run the sweep:
  ```bash
  bfl-asic ml sweep --rounds 1,2,4,8,16,32,64 --plot
  ```
- Open `runs/ml/<ts>/learnability.png`. The accuracy curve falls from
  ~100% to the chance line: that collapse *is* the avalanche finishing.
- Run `bfl-asic ml run full_structure`. The bounded-null line is the
  honest scientific statement of "we found nothing, and here is the
  CI-resolution floor below which we could not have detected a bias."
  A flat curve at 64 rounds is SHA-256 working exactly as designed.

---

## How to use this toolkit while learning

- **Read the code.**  The four subsystems (`protocol`, `stats`,
  `dynamics`, `randomness`) are deliberately small and well-tested.
  Reading them is faster than re-reading lecture notes.
- **Run experiments.**  Almost every command works with the
  `SoftwareHashEngine` (no hardware required).  Try varying sample
  sizes, seed values, block sizes.  See where things break.
- **Tests are documentation.**  `tests/test_randomness_tests.py`
  encodes NIST SP 800-22 reference p-values for the §2.1.8, §2.2.8,
  §2.3.8 examples.  If you change a test function, see what the
  reference value moves to and ask why.
- **The `runs/` folder is your lab notebook.**  Every snapshot/PNG/GIF
  you generate accumulates there, never overwritten.  Date-stamped
  output makes it easy to compare experiments across study sessions.

---

## Reference: the four documents in this repo

- **`README.md`** -- installation, quick-start, Python API.
- **`DEVLOG.md`** -- chronological session log including hardware
  characterisation findings.
- **`bfl-asic-repurpose.md`** -- the original seed specification
  listing nine repurposing applications.  Status banners mark which
  are implemented.
- **`CLAUDE.md`** -- onboarding notes for AI assistants working in
  the repo.

If you find a course or video that's an even better fit than the ones
above, open a PR adding it here.
