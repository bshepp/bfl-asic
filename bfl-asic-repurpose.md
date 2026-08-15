# BFL ASIC Repurposing Project

## Reclaiming a Butterfly Labs SHA-256 Cryptocurrency Miner as a Multi-Purpose Cryptographic Instrument

### Project Overview

This document serves as a seed specification for repurposing a Butterfly Labs (BFL) SHA-256 ASIC cryptocurrency miner into a general-purpose cryptographic research and utility platform. Rather than treating the device as obsolete e-waste, we exploit the fact that SHA-256 is a **fundamental cryptographic primitive** with applications far beyond cryptocurrency mining.

The device is essentially a dedicated hardware engine capable of computing billions of SHA-256 double-hashes per second. By replacing the stock mining firmware/controller with a custom interface layer, we unlock the full utility of this capability.

### Hardware Inventory (completed 2026-03-01)

| Component | Details | Status |
|---|---|---|
| **ASIC Model** | BitForce SHA256 SC 1.0 (Single Chip Jalapeno BF0005G, ~5 GH/s) | Identified via `ZGX` |
| **Controller Board** | FTDI USB-serial bridge (VID `0x0403`, PID `0x6014`) | Confirmed |
| **USB Interface** | USB serial, 115200 8N1 | Tested on COM3 |
| **Power Supply** | 13V DC adapter (VMAIN rail reads 11.4V at device) | Measured via `ZTX` |
| **Cooling** | Stock fan + heatsink; idle ~30°C ambient +9°C | Adequate at USB-limited 1 wps |
| **Enclosure** | Metal chassis (original BFL retail) | Intact |

**Characterised behaviour** (see DEVLOG.md 2026-03-02 entry for full data):
- USB serial round-trip caps throughput at ~1 work unit/sec — the ASIC's 5 GH/s rate sits idle most of the time.
- The SC firmware has a hard 42-work-submission limit per power cycle. Only a power cycle clears it.
- Idle voltages: VCC1 ≈ 3.564 V (nominal 3.3), VCC2 ≈ 1.011 V (nominal 1.0), VMAIN ≈ 11.42 V. VCC1 shows a ~1.2 V dip immediately after ADC queries (suspected multiplexer settling).

---

## Phase 1: Device Communication Layer

### Objective
Establish reliable bidirectional communication with the ASIC, bypassing stock mining assumptions.

### Background
BFL devices communicate over USB serial. The stock protocol is simple:

- **Host → Device:** Sends work units (block header templates, ~80 bytes, with nonce ranges)
- **Device → Host:** Returns nonces that produced hashes below a given difficulty target

The stock firmware **discards** the vast majority of computed hashes because they don't meet mining difficulty. For our purposes, **every hash is valuable data**. The fundamental task is modifying or replacing the controller to emit all computed hashes or configurable subsets.

### Known BFL Serial Commands (varies by model)
```
ZGX — Get device info / identify
ZDX — Send work to device
ZFX — Read results
ZTX — Get temperature
```

> **Status (2026-08-15):** command layer implemented and largely mapped
> (`bfl_asic/protocol/`). Corrections vs. the list above: **ZLX** reads
> temperature and **ZTX** reads voltage (they were reversed from initial
> assumptions). Full SC set now covered: identify `ZGX`, temp `ZLX`,
> voltage `ZTX`, work `ZDX`/poll `ZFX`, nonce-range `ZPX`, fan
> `Z9X`/`Z0X`–`Z4X`, and the SC queued path `ZNX`/`ZWX`/`ZOX`/`ZQX`/`ZCX`.
> **Task 4 (map the full command set):** the `ZCX` details census is now
> parsed in full (`device details` CLI + `scripts/hw/read_details.py`,
> read-only). On the real unit it exposes undocumented fields cgminer
> never consumed — real per-processor engine/clock topology, a
> firmware-estimated hashrate, and a critical-temp field. Still open:
> the genuinely-unused `ZJX`/`ZSX`/`ZUX` commands (defined in the
> cgminer header but never sent), queued for a probe increment; blind
> `Z?X` scanning and `ZMX` flash are reserved for a **sacrificial** unit.
> **Task 5 (output modes):** settled — the firmware returns only winning
> *nonces*, never full digests, and difficulty is fixed at diff-1 in
> firmware. Full-digest capture would require a controller reflash
> (out of scope); bulk hash study is done in software instead.

### Tasks

1. **Enumerate the USB device**
   ```bash
   lsusb
   dmesg | grep -i butterfly
   ls /dev/ttyUSB* /dev/ttyACM*
   ```

2. **Establish serial communication**
   ```bash
   # Typical BFL serial settings
   screen /dev/ttyUSB0 115200
   # Or via Python
   pip install pyserial
   ```

3. **Probe the device with known commands**
   ```python
   import serial
   
   ser = serial.Serial('/dev/ttyUSB0', 115200, timeout=2)
   
   # Identity query
   ser.write(b'ZGX')
   response = ser.read(1024)
   print(f"Device ID: {response}")
   
   # Temperature query
   ser.write(b'ZTX')
   response = ser.read(1024)
   print(f"Temperature: {response}")
   ```

4. **Map the full command set** — Send exploratory commands and document all responses. Capture protocol timing. Determine maximum throughput of the USB interface relative to ASIC hash rate (this is the likely bottleneck).

5. **Determine output modes** — Can the firmware be configured to return full hash outputs rather than just winning nonces? If not, assess whether the controller board firmware can be reflashed or replaced entirely.

### USB Throughput Constraint

At even 1 GH/s, full 256-bit hash output would be:
- 1,000,000,000 hashes/sec × 32 bytes = **32 GB/s**
- USB 2.0 max: ~480 Mbit/s ≈ 60 MB/s

This means we can capture roughly **1 in 500** hashes at full speed over USB 2.0. Strategies:
- **On-board sampling**: Modify controller to emit every Nth hash
- **Statistical summarization**: Controller computes running statistics on-board, exports summaries
- **Threshold capture**: Lower the difficulty target to capture more (but not all) hashes
- **Direct ASIC bus tapping**: Bypass USB entirely if controller board allows (advanced)

---

## Phase 2: Core Applications

### Application 1: Hardware Random Number Generator (HRNG)

> **Status (2026-05-13):** validation suite built (`bfl_asic/randomness/` — NIST SP 800-22 battery, exposed as `bfl-asic randomness run`). The harvest side runs against `SoftwareHashEngine` today; the same battery will plug into an ASIC-backed `HashSource` once one exists.

#### Concept
Use SHA-256 hash outputs as a cryptographically strong entropy source. SHA-256 output is statistically indistinguishable from true randomness assuming the algorithm's properties hold — which our exploration work (Application 2) continuously validates.

#### Architecture
```
[BFL ASIC] → [USB Serial] → [Linux Host]
                                  │
                          /dev/bfl-hwrng
                                  │
                    ┌─────────────┼─────────────┐
                    │             │             │
              rngd → kernel   /dev/urandom   Application
              entropy pool    supplement     direct feed
```

#### Implementation

1. **Create a character device** that exposes the hash stream as `/dev/bfl-hwrng`
   ```python
   #!/usr/bin/env python3
   """BFL ASIC Hardware RNG Daemon"""
   
   import serial
   import os
   import struct
   import hashlib
   import time
   
   DEVICE = '/dev/ttyUSB0'
   BAUD = 115200
   OUTPUT_FIFO = '/tmp/bfl-hwrng'
   
   class BFLRandomSource:
       def __init__(self, device, baud):
           self.ser = serial.Serial(device, baud, timeout=1)
           self.nonce_counter = 0
       
       def get_work_unit(self):
           """Generate a synthetic work unit to feed the ASIC."""
           # We don't care about valid blocks — any input works
           # Use incrementing counter + timestamp for input diversity
           header = struct.pack('>Q', self.nonce_counter) + \
                    struct.pack('>d', time.time()) + \
                    os.urandom(64)  # Pad to 80 bytes
           self.nonce_counter += 1
           return header
       
       def submit_work(self, header):
           """Send work unit to ASIC and collect results."""
           # TODO: Implement BFL-specific protocol
           # This is model-dependent
           pass
       
       def harvest_entropy(self):
           """Collect hash outputs as random bytes."""
           # TODO: Implement based on device protocol discovery
           pass
   
   if __name__ == '__main__':
       source = BFLRandomSource(DEVICE, BAUD)
       # Main loop: feed work, harvest entropy, write to FIFO
   ```

2. **Feed system entropy pool** via `rngd`:
   ```bash
   rngd -r /tmp/bfl-hwrng -o /dev/random
   ```

3. **Validate output quality** using NIST SP 800-22 test suite:
   ```bash
   # Collect sample
   dd if=/tmp/bfl-hwrng of=sample.bin bs=1M count=100
   # Run NIST tests (install sts from NIST)
   ./assess 1000000 < sample.bin
   ```

#### Validation

The HRNG output should pass all of:
- NIST SP 800-22 Statistical Test Suite
- Dieharder test battery (`dieharder -a -f sample.bin`)
- TestU01 (Crush / BigCrush)
- ENT entropy analysis

---

### Application 2: SHA-256 Probability Landscape Exploration

> **Status (2026-02-25):** implemented as `bfl_asic/stats/` — 7 numpy-vectorised accumulators (bit frequency, avalanche, bit-pair correlation, near-collision, byte distribution, Shannon entropy, FFT spectral), `StatsPipeline` orchestrator, matplotlib dashboard. CLI: `bfl-asic stats run/report/animate-convergence`.

#### Concept
Use the ASIC as a high-throughput empirical observatory for studying the statistical properties of SHA-256 output space. At billions of samples per second, we can build datasets that would take software implementations weeks or months to generate.

#### Research Questions

1. **Output uniformity at scale**: Is SHA-256 output truly uniform across all 256 bit positions? At what sample size do deviations (if any) become detectable?

2. **Avalanche characterization**: For sequential inputs (nonce, nonce+1, nonce+2...), what is the empirical distribution of Hamming distances between consecutive outputs? Theory predicts ~128 bits (half of 256) with binomial variance. Does this hold at scale?

3. **Near-collision statistics**: How frequently do output pairs land within Hamming distance d of each other? What is the empirical near-collision rate vs. theoretical prediction?

4. **Bit position correlations**: Are any bit positions in the output correlated across many samples? Even weak correlations would be cryptographically significant.

5. **Iterated hash dynamics**: Feeding output back as input creates a discrete dynamical system on a state space of 2^256. What are the orbit structures? Cycle lengths? Convergence properties? Attractor topology?

6. **Spectral analysis**: FFT of individual bit position time series across sequential inputs. Any frequency components would indicate periodicity.

#### Data Pipeline Architecture
```
[BFL ASIC] → [USB] → [Stream Processor] → [Statistical Accumulators]
                              │                        │
                              │                   [Visualization]
                              │                        │
                              └──── [Raw Sample Archive (selective)]
```

#### Statistical Accumulators (Real-Time)

These run continuously on the incoming hash stream without storing every hash:

```python
class HashSpaceAccumulators:
    """Real-time statistical accumulators for SHA-256 output analysis."""
    
    def __init__(self):
        # Bit frequency counters (256 counters)
        self.bit_counts = [0] * 256
        self.total_hashes = 0
        
        # Avalanche tracking (sequential input pairs)
        self.hamming_histogram = [0] * 257  # 0-256 possible distances
        self.prev_hash = None
        
        # Bit pair correlations (256x256 matrix — track subset)
        # Full matrix is 64KB, manageable
        self.bit_pair_counts = {}  # (i,j) → count where both bits are 1
        
        # Near-collision tracking
        self.near_collision_counts = {d: 0 for d in range(1, 17)}
        self.recent_hashes = []  # Rolling window for collision search
        
        # Running entropy estimate
        self.byte_histogram = [0] * 256  # Distribution of each byte position
    
    def ingest(self, hash_bytes: bytes):
        """Process one 32-byte SHA-256 output."""
        self.total_hashes += 1
        
        # Convert to integer for bit operations
        hash_int = int.from_bytes(hash_bytes, 'big')
        
        # Bit frequencies
        for i in range(256):
            if hash_int & (1 << i):
                self.bit_counts[i] += 1
        
        # Avalanche (Hamming distance from previous)
        if self.prev_hash is not None:
            xor = hash_int ^ self.prev_hash
            hamming = bin(xor).count('1')
            self.hamming_histogram[hamming] += 1
        self.prev_hash = hash_int
        
        # Byte distribution
        for b in hash_bytes:
            self.byte_histogram[b] += 1
    
    def report(self):
        """Generate statistical summary."""
        n = self.total_hashes
        if n == 0:
            return "No data collected yet."
        
        # Bit bias: each bit should be 1 exactly 50% of the time
        bit_biases = [(c / n - 0.5) for c in self.bit_counts]
        max_bias = max(abs(b) for b in bit_biases)
        
        # Avalanche: mean Hamming distance should be 128
        total_hamming = sum(d * c for d, c in enumerate(self.hamming_histogram))
        total_pairs = sum(self.hamming_histogram)
        mean_hamming = total_hamming / total_pairs if total_pairs > 0 else 0
        
        return {
            'total_hashes': n,
            'max_bit_bias': max_bias,
            'mean_hamming_distance': mean_hamming,
            'expected_hamming': 128.0,
        }
```

#### Visualization Approaches

- **Hilbert curve mapping**: Map 256-bit outputs onto a 2D Hilbert curve to preserve locality. Render density as a heatmap. Uniform distribution should produce uniform color; any structure indicates non-randomness.
- **Bit position heat maps**: 256×N grid showing bit values over sequential samples. Visual patterns = correlations.
- **Hamming distance distribution**: Overlay empirical histogram on theoretical binomial(256, 0.5).
- **Orbit visualizations**: For iterated hashing, project the 256-dimensional state into 2D/3D via PCA or t-SNE and plot trajectories.

---

### Application 3: Document Notarization and Timestamping

#### Concept
Use the ASIC to rapidly hash documents and datasets, anchoring the resulting digests to public timestamping services or blockchains. Provides cryptographic proof that specific data existed at a specific time.

#### Use Cases
- Timestamp research drafts before submission (priority of discovery)
- Create tamper-evident records of datasets (LiDAR data, environmental monitoring)
- Notarize versions of open-source code

#### Implementation
```python
import hashlib
import time
import json

class NotaryService:
    """Local document notarization using BFL ASIC for hashing."""
    
    def __init__(self, asic_interface):
        self.asic = asic_interface
        self.ledger = []  # Local notarization log
    
    def notarize(self, filepath):
        """Hash a file and create a timestamped notarization record."""
        # Read file and compute SHA-256 via ASIC (or software fallback)
        with open(filepath, 'rb') as f:
            file_data = f.read()
        
        # For small files, software hash is fine
        # ASIC advantage is for bulk operations or streaming data
        file_hash = hashlib.sha256(file_data).hexdigest()
        
        record = {
            'filepath': filepath,
            'sha256': file_hash,
            'timestamp': time.time(),
            'timestamp_iso': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
            'filesize': len(file_data),
        }
        
        self.ledger.append(record)
        return record
    
    def anchor_to_opentimestamps(self, file_hash):
        """Anchor hash to Bitcoin blockchain via OpenTimestamps."""
        # TODO: Integrate with opentimestamps-client
        # ots stamp <file>
        pass
    
    def export_ledger(self, path):
        """Export notarization ledger as JSON."""
        with open(path, 'w') as f:
            json.dump(self.ledger, f, indent=2)
```

---

### Application 4: Post-Quantum Cryptography Accelerator

#### Concept
NIST-standardized post-quantum signature schemes like **SPHINCS+** (now SLH-DSA) are built entirely on hash functions. A SHA-256 ASIC can serve as a hardware accelerator for generating and verifying these signatures.

#### Relevance
As quantum computing advances (relevant given existing AWS Braket experience), hash-based signatures become critical infrastructure. Having a dedicated hardware accelerator for the core primitive is forward-looking.

#### Tasks
1. Study SPHINCS+/SLH-DSA internals — identify where SHA-256 is the bottleneck
2. Profile software SPHINCS+ implementation to quantify hash computation percentage
3. Design interface to offload SHA-256 calls to ASIC
4. Benchmark: ASIC-accelerated vs. pure software SPHINCS+ performance

#### Reference
- NIST FIPS 205 (SLH-DSA / SPHINCS+)
- `pqcrypto` Python library for post-quantum algorithms

---

### Application 5: Merkle Tree Engine

#### Concept
SHA-256 is the foundation of Merkle trees — used in Git, IPFS, certificate transparency, blockchain, and data verification systems. The ASIC can construct Merkle trees over large datasets at hardware speed.

#### Applications
- Build verifiable, tamper-evident data structures over LiDAR terrain datasets (RESIDUALS project)
- Create Merkle proofs for environmental monitoring data integrity
- Accelerate Git-like version control operations on large binary datasets

#### Architecture
```
Dataset Chunks → [BFL ASIC: leaf hashing] → Leaf Hashes
                                                  │
                              [BFL ASIC: pairwise hashing] → Internal Nodes
                                                                    │
                                                              Merkle Root
```

---

### Application 6: Hash-Based Commitment Schemes

#### Concept
Cryptographic commitments allow proving "I knew X at time T" without revealing X until later. Built on SHA-256.

#### Use Cases
- Establish research priority without premature disclosure
- Collaborative research protocols where parties commit to results before sharing
- Sealed-bid or sealed-prediction schemes

#### Protocol
```
COMMIT:   commitment = SHA-256(secret || nonce)  → publish commitment
REVEAL:   publish (secret, nonce)                → anyone can verify
VERIFY:   SHA-256(secret || nonce) == commitment  → proven
```

---

### Application 7: Proof-of-Work Utility Services

#### Concept
Use the ASIC's native proof-of-work capability for non-cryptocurrency applications.

#### Applications
- **Anti-spam**: Require proof-of-work tokens to access personal APIs or services (Hashcash-style)
- **Rate limiting**: Proof-of-work as a computational cost gate
- **Fair lottery/selection**: Verifiable random selection using hash-based commit-reveal

---

### Application 8: Iterated Hash Dynamics Research

> **Status (2026-02-26):** implemented as `bfl_asic/dynamics/` — orbit analysis with sampled trajectories, Floyd's and Brent's cycle detection (both O(1) memory), multi-seed convergence analysis, matplotlib plots. CLI: `bfl-asic dynamics run/plot`.

#### Concept
Feeding SHA-256 output back as input creates a discrete deterministic dynamical system:

```
x₀ → SHA-256(x₀) = x₁ → SHA-256(x₁) = x₂ → ...
```

This orbit exists in a finite state space of 2^256 states. By the pigeonhole principle, every orbit must eventually cycle. The structure of these orbits — cycle lengths, tail lengths, convergence basins — is essentially unstudied empirically.

#### Research Questions
- What is the empirical distribution of cycle entry points (rho length)?
- Do different seed values converge to common cycles (attractor basins)?
- How does the cycle structure compare to a random function on 2^256 elements? (Expected cycle length ≈ √(π·2^256/2) by random function theory)
- Are there fixed points? (x such that SHA-256(x) = x)
- Is there structure in the pre-image tree?

#### Connection to Existing Work
This connects to discrete dynamical systems theory and may exhibit phenomena analogous to the sensitivity and growth patterns observed in Poisson algebra work on the three-body problem. The hash function acts as a deterministic map on a high-dimensional discrete space — a finite analog of continuous chaotic systems.

---

### Application 9: Side-Channel Emissions Research

#### Concept
A running ASIC produces electromagnetic emissions correlated with its computational activity. Using existing RF monitoring equipment (RTL-SDR, HackRF One), characterize the device's EM signature during SHA-256 computation.

#### Research Value
- Side-channel analysis of hash computation on dedicated silicon
- Correlation between input patterns and EM emissions
- Assessment of information leakage from ASIC mining hardware
- Contribution to hardware security research

#### Equipment (Already Available)
- HackRF One (wideband monitoring)
- RTL-SDR (narrowband characterization)
- Rubidium atomic clock (precision timing reference for correlating EM events with hash outputs)

---

## Phase 3: Precision Timing Integration

### Rubidium Clock Synchronization

The existing rubidium atomic clock can provide a precision timing backbone for all applications:

- **HRNG**: Timestamp entropy samples with nanosecond precision
- **Notarization**: Cryptographically precise timestamps
- **Dynamics research**: Correlate hash computation timing with output properties
- **Side-channel**: Synchronize EM capture with hash computation cycles

---

## Appendix: Project Dependencies

```bash
# Core
pip install pyserial        # Device communication
pip install numpy            # Statistical analysis
pip install matplotlib       # Visualization
pip install scipy            # Advanced statistics

# Cryptography
pip install pycryptodome     # SHA-256 software reference
pip install opentimestamps   # Blockchain timestamping

# Testing
pip install dieharder        # Randomness testing (or system package)
# NIST SP 800-22: https://csrc.nist.gov/projects/random-bit-generation

# Post-quantum
pip install pqcrypto         # SPHINCS+ and other PQC algorithms

# Visualization
pip install plotly           # Interactive visualization
pip install pillow           # Image generation for hash space maps
```

## Appendix: References

- NIST FIPS 180-4 (SHA-256 specification)
- NIST FIPS 205 (SLH-DSA / SPHINCS+ post-quantum signatures)
- NIST SP 800-22 (Random number generation test suite)
- OpenTimestamps: https://opentimestamps.org/
- BFL device protocols: community-documented in cgminer/bfgminer source code
  - cgminer BFL driver: search cgminer source for `driver-bitforce`
  - bfgminer BFL driver: similar structure

---

## Addendum: ML learnability instrument (implemented 2026-05-15)

> **Status (2026-05-15):** implemented as `bfl_asic/ml/` — optional PyTorch subsystem
> behind the `[ml]` extra. CLI: `bfl-asic ml sweep/run/report/plot/publish`.

Four experiments ask the question "where does SHA-256 become unlearnable?"
using a TinyCNN distinguisher gated by positive/negative controls:

1. **Round-reduced learnability sweep** — train a distinguisher on 1, 2, 4, 8,
   16, 32, 64 rounds of SHA-256. Accuracy collapses to chance at ~8–16 rounds,
   showing exactly where the avalanche finishes.
2. **Full-SHA indistinguishability demo** — a classifier trained on full (64-round)
   SHA-256 learns nothing beyond chance; establishes the baseline.
3. **Dynamics-orbit learnability vs truncation** — orbit trajectories (iterated
   SHA-256) with varying truncation widths; learnability rises as the state
   space shrinks.
4. **Bounded-null "any structure" search** — a rigorous null: reports the
   CI-resolution floor (`min_detectable_advantage`) below which no advantage
   could have been detected, so "we found nothing" is a falsifiable claim.

A "no structure" conclusion is only emitted when the positive control learns
and the negative control fails. Snapshots are strict-RFC-8259 JSON and the
core install stays torch-free.

---

*Document created: 2026-02-25*
*Status: Seed specification — implementation in progress (see DEVLOG.md for session log).*
*Implemented so far: Apps 1 (validation), 2, 8, and the ML learnability instrument (addendum above).  Apps 3, 4, 5, 6, 7, 9 unbuilt.  Hardware characterisation complete; firmware 42-work-submission limit is the primary blocker for sustained-hashing applications.*
