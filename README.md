# bfl-asic

Communication layer and statistical analysis tools for the Butterfly Labs BF0005G Jalapeno SHA-256 ASIC miner.

This project repurposes a Butterfly Labs BitForce SHA-256 ASIC cryptocurrency miner as a general-purpose cryptographic research platform. Rather than mining, it provides tools for statistical analysis of SHA-256 hash output, iterated hash dynamics exploration, and direct hardware interaction through a layered Python API.

## Hardware

- **Device:** Butterfly Labs BF0005G Jalapeno (5 GH/s)
- **ASIC:** BitForce SHA256 SC 1.0 (Single Chip)
- **Interface:** USB serial via FTDI (VID `0x0403`, PID `0x6014`), 115200 8N1
- **Protocol:** ASCII commands (ZGX, ZLX, ZTX, ZDX, ZFX, ZPX) with 60-byte binary work packets
- **Power:** 13V DC adapter

## Installation

```bash
pip install -e .
```

Requires Python 3.10+. Dependencies: `pyserial`, `pyserial-asyncio`, `click`, `numpy`, `scipy`, `matplotlib`.

## Quick Start

### With hardware connected

```bash
# Discover devices
bfl-asic discover

# Probe device on COM3
bfl-asic -p COM3 probe

# Read temperature and voltages
bfl-asic -p COM3 temperature

# Benchmark work submission throughput
bfl-asic -p COM3 benchmark --duration 10
```

### Without hardware (simulator)

```bash
# All commands work with --simulate or with no --port flag
bfl-asic --simulate probe
bfl-asic --simulate identify
bfl-asic --simulate hash "hello world"
```

### Statistical analysis

```bash
# Run SHA-256 statistical analysis (software engine)
bfl-asic stats run --samples 100000 -o snapshot.json --plot

# View saved results
bfl-asic stats report snapshot.json

# Animated visualisation of per-bit bias shrinking as N grows
# (great for an intuitive feel for the law of large numbers)
bfl-asic stats animate-convergence --samples 100000 --frames 60
```

### Iterated hash dynamics

```bash
# Run orbit/convergence analysis
bfl-asic dynamics run --seeds 5 --max-iterations 50000 -o dynamics.json

# Generate plots from saved results
bfl-asic dynamics plot dynamics.json
```

### Randomness validation (NIST SP 800-22)

```bash
# Harvest hashes and run the NIST randomness battery
bfl-asic randomness run --hashes 1000 -o randomness.json

# View saved results
bfl-asic randomness report randomness.json
```

Six tests are included: frequency (monobit), block frequency, runs,
longest run of ones in a block, DFT spectral, and cumulative sums
(forward + reverse).  The battery consumes any `HashSource`, so an
ASIC-backed source plugs in unchanged once the firmware 42-work-limit
is worked around.

### Where outputs go

When you do not pass `-o`, results land under a `runs/` folder in the
current directory, organised by command:

```
runs/
  stats/<timestamp>/snapshot.json + dashboard.png   (stats run --plot)
  animations/convergence-<timestamp>.gif            (stats animate-convergence)
```

Explicit `-o paths/file.ext` is always honoured verbatim.  Two writes to
the same path never overwrite each other -- the second one is suffixed with a
timestamp.  Override the output root with the `BFL_ASIC_OUTPUT_DIR`
environment variable.

## Architecture

```
bfl_asic/
  protocol/       # Pure encoding/decoding — no I/O
    constants.py   # Baud rate, commands, timing, response tokens
    commands.py    # Build ZGX, ZLX, ZTX, ZDX, ZFX, ZPX byte sequences
    responses.py   # Parse identify, temperature, voltage, work results
    work.py        # SHA-256 midstate computation, synthetic work generation
  transport/       # I/O abstraction
    base.py        # BaseTransport ABC (sync + async)
    serial.py      # Real hardware via pyserial
    simulator.py   # In-process simulated device with thermal model
    discovery.py   # FTDI device scanning
  stats/           # SHA-256 statistical analysis pipeline
    engine.py      # HashSource ABC, SoftwareHashEngine
    accumulators.py # Bit frequency, avalanche, correlation, entropy, etc.
    spectral.py    # FFT-based periodicity detection
    snapshot.py    # JSON-serializable results
    pipeline.py    # Orchestrator wiring engine → accumulators → snapshot
    visualization.py # Matplotlib plots: heatmaps, histograms, dashboards
  dynamics/        # Iterated hash dynamics (x → SHA-256(x) → ...)
    orbit.py       # Orbit computation with sampled trajectories
    rho.py         # Floyd's and Brent's cycle detection (O(1) memory)
    convergence.py # Multi-seed convergence analysis
    visualization.py # Orbit, convergence, and distribution plots
  randomness/      # NIST SP 800-22 randomness test battery
    tests.py       # Pure-function tests over uint8 bit arrays
    battery.py     # Orchestrator over any HashSource
    snapshot.py    # JSON-serializable results
  device.py        # BFLDevice — sync high-level API
  async_device.py  # AsyncBFLDevice — async API with stream iterators
  cli.py           # Click CLI: identify, temperature, probe, discover,
                   #   benchmark, hash, stats, dynamics, randomness
  exceptions.py    # BFLError hierarchy
```

### Layer separation

- **Protocol** is pure Python — no I/O, no state, fully testable
- **Transport** abstracts serial vs simulator vs future backends
- **Device** combines transport + protocol into a clean API
- **Applications** (stats, dynamics, randomness) are independent of the device layer

## Protocol Reference

| Command | Bytes | Response |
|---------|-------|----------|
| Identify | `ZGX` | `BitForce SHA256 SC 1.0\n` |
| Temperature | `ZLX` | `Temp1: 30, Temp2: 30\n` |
| Voltages | `ZTX` | `3564,1011,11420\n` (mV: VCC1, VCC2, VMAIN) |
| Submit work | `ZDX` + 60-byte packet | `OK\n` |
| Poll result | `ZFX` | `IDLE\n` / `B\n` / `NONCE-FOUND:<hex>\n` / `NO-NONCE\n` |
| Nonce range | `ZPX` + 68-byte packet | `OK\n` |

Work packet format (60 bytes): `>>>>>>>> [32-byte midstate] [12-byte tail] >>>>>>>>`

## Testing

```bash
python -m pytest tests/ -q
```

671 tests. All tests run against the simulator — no hardware needed. Test coverage includes protocol encoding/decoding, transport lifecycle, simulator state machine, device API round-trips, CLI smoke tests, statistical accumulators, dynamics algorithms, NIST SP 800-22 tests (with reference p-values from the spec as regression anchors), and visualization.

## Python API

```python
from bfl_asic import BFLDevice
from bfl_asic.transport.serial import SerialTransport
from bfl_asic.transport.simulator import SimulatorTransport

# Real hardware
with BFLDevice(SerialTransport(port="COM3")) as dev:
    info = dev.identify()
    temp = dev.get_temperature()
    volts = dev.get_voltage()
    nonces = dev.hash_data(b"hello world")

# Simulator
with BFLDevice(SimulatorTransport()) as dev:
    info = dev.identify()

# Async
from bfl_asic import AsyncBFLDevice
async with AsyncBFLDevice(SimulatorTransport()) as dev:
    async for nonces in dev.hash_stream(count=100):
        print(nonces)
```

```python
# Statistical analysis
from bfl_asic.stats import StatsPipeline

pipeline = StatsPipeline()
snapshot = pipeline.run(samples=100_000)
snapshot.save("results.json")
print(f"Max bias: {snapshot.bit_frequency['max_bias']}")
print(f"Mean Hamming: {snapshot.avalanche['mean']}")
print(f"Entropy: {snapshot.entropy['shannon_entropy']}")
```

```python
# Iterated hash dynamics
from bfl_asic.dynamics import brent_detect, compute_orbit
from bfl_asic.dynamics.orbit import sha256_iterate

# Truncated hash for reachable cycles
def toy_hash(v: bytes) -> bytes:
    import hashlib
    return hashlib.sha256(v).digest()[:3].ljust(32, b'\x00')

cycle = brent_detect(b'\x00' * 32, max_steps=1_000_000, hash_fn=toy_hash)
if cycle:
    print(f"Cycle length: {cycle.cycle_length}, Tail: {cycle.tail_length}")
```

```python
# NIST SP 800-22 randomness validation
from bfl_asic.randomness import RandomnessBattery
from bfl_asic.stats.engine import SoftwareHashEngine

battery = RandomnessBattery(engine=SoftwareHashEngine())
snapshot = battery.run(hash_count=1000)  # 256,000 bits
print(f"Passed: {snapshot.pass_count}/{len(snapshot.results)}")
for r in snapshot.results:
    print(f"  {r['name']:<28} p={r['p_value']:.4f}  "
          f"{'PASS' if r['passed'] else 'FAIL'}")
```

## License

Unlicensed / private project.
