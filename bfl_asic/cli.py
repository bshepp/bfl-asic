"""Click-based command-line interface for interacting with BFL ASIC devices.

Provides subcommands for device identification, temperature monitoring,
probing, discovery, benchmarking, hashing, statistical analysis, and
iterated hash dynamics through either a real serial connection or the
built-in simulator.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import click

from bfl_asic.device import BFLDevice
from bfl_asic.protocol.responses import WorkStatus
from bfl_asic.protocol.work import build_synthetic_work


def get_transport(port: str | None, simulate: bool, baudrate: int):
    """Create the appropriate transport based on CLI options.

    If *simulate* is ``True`` or *port* is ``None``, returns a
    :class:`~bfl_asic.transport.simulator.SimulatorTransport`.
    Otherwise returns a :class:`~bfl_asic.transport.serial.SerialTransport`.
    """
    if simulate or port is None:
        from bfl_asic.transport.simulator import SimulatorTransport

        return SimulatorTransport()
    else:
        from bfl_asic.transport.serial import SerialTransport

        return SerialTransport(port=port, baudrate=baudrate)


@click.group()
@click.option("--port", "-p", default=None, help="Serial port (e.g. /dev/ttyUSB0, COM3)")
@click.option(
    "--simulate", "-s", is_flag=True, default=False,
    help="Use simulator instead of real device",
)
@click.option("--baudrate", "-b", default=115200, type=int, help="Baud rate")
@click.pass_context
def main(ctx: click.Context, port: str | None, simulate: bool, baudrate: int) -> None:
    """BFL ASIC Repurpose Tool -- interact with Butterfly Labs SHA-256 hardware."""
    ctx.ensure_object(dict)
    ctx.obj["port"] = port
    ctx.obj["simulate"] = simulate
    ctx.obj["baudrate"] = baudrate


# ======================================================================
# identify
# ======================================================================


@main.command()
@click.pass_context
def identify(ctx: click.Context) -> None:
    """Query device identification."""
    transport = get_transport(
        ctx.obj["port"], ctx.obj["simulate"], ctx.obj["baudrate"],
    )
    with BFLDevice(transport) as device:
        info = device.identify()
        click.echo(f"Device: {info.model}")
        click.echo(f"SHA-256: {'Yes' if info.sha256 else 'No'}")


# ======================================================================
# temperature
# ======================================================================


@main.command()
@click.pass_context
def temperature(ctx: click.Context) -> None:
    """Query device temperature and voltages."""
    transport = get_transport(
        ctx.obj["port"], ctx.obj["simulate"], ctx.obj["baudrate"],
    )
    with BFLDevice(transport) as device:
        reading = device.get_temperature()
        click.echo("Temperature:")
        for idx, temp in enumerate(reading.sensors):
            click.echo(f"  Chip {idx + 1}: {temp:.1f}\u00b0C")
        try:
            volts = device.get_voltage()
            click.echo("Voltages:")
            click.echo(f"  VCC1:  {volts.vcc1:.3f}V")
            click.echo(f"  VCC2:  {volts.vcc2:.3f}V")
            click.echo(f"  VMAIN: {volts.vmain:.3f}V")
        except Exception:
            pass  # Simulator or older firmware may not support ZTX


# ======================================================================
# probe
# ======================================================================


@main.command()
@click.pass_context
def probe(ctx: click.Context) -> None:
    """Send all known commands and display responses."""
    transport = get_transport(
        ctx.obj["port"], ctx.obj["simulate"], ctx.obj["baudrate"],
    )
    with BFLDevice(transport) as device:
        click.echo("=== Device Probe ===")
        click.echo()

        # Identify
        info = device.identify()
        click.echo("[ZGX] Identify:")
        click.echo(f"  {info.model}")
        click.echo()

        # Temperature
        reading = device.get_temperature()
        click.echo("[ZLX] Temperature:")
        for idx, temp in enumerate(reading.sensors):
            click.echo(f"  Chip {idx + 1}: {temp:.1f}\u00b0C")
        click.echo()

        # Voltages
        try:
            volts = device.get_voltage()
            click.echo("[ZTX] Voltages:")
            click.echo(f"  VCC1:  {volts.vcc1:.3f}V")
            click.echo(f"  VCC2:  {volts.vcc2:.3f}V")
            click.echo(f"  VMAIN: {volts.vmain:.3f}V")
            click.echo()
        except Exception:
            pass  # Simulator or older firmware may not support ZTX

        # Poll (no work submitted -- should be IDLE)
        result = device.poll_result()
        click.echo("[ZFX] Poll (no work submitted):")
        if result.status == WorkStatus.IDLE:
            click.echo("  Status: IDLE")
        elif result.status == WorkStatus.NONCE_FOUND:
            click.echo("  Status: NONCE_FOUND")
            for nonce in result.nonces:
                click.echo(f"    0x{nonce:08x}")
        elif result.status == WorkStatus.NO_NONCE:
            click.echo("  Status: NO_NONCE")
        elif result.status == WorkStatus.BUSY:
            click.echo("  Status: BUSY")


# ======================================================================
# discover
# ======================================================================


@main.command()
def discover() -> None:
    """List detected BFL devices on serial ports."""
    from bfl_asic.transport.discovery import discover_devices

    devices = discover_devices()
    if not devices:
        click.echo("No BFL devices found.")
    else:
        click.echo(f"Found {len(devices)} device(s):")
        for dev in devices:
            vid_str = f"0x{dev.vid:04x}" if dev.vid is not None else "N/A"
            pid_str = f"0x{dev.pid:04x}" if dev.pid is not None else "N/A"
            click.echo(f"  {dev.port} - {dev.description} (VID:{vid_str}, PID:{pid_str})")


# ======================================================================
# benchmark
# ======================================================================


@main.command()
@click.option("--duration", "-d", default=5.0, type=float, help="Benchmark duration in seconds")
@click.pass_context
def benchmark(ctx: click.Context, duration: float) -> None:
    """Measure throughput by submitting synthetic work units."""
    from bfl_asic.exceptions import BFLError

    transport = get_transport(
        ctx.obj["port"], ctx.obj["simulate"], ctx.obj["baudrate"],
    )
    click.echo(f"Benchmarking for {duration:.1f} seconds...")

    work_count = 0
    nonce_count = 0
    start = time.monotonic()

    with BFLDevice(transport) as device:
        counter = 0

        while time.monotonic() - start < duration:
            seed = counter.to_bytes(8, "big").ljust(64, b"\x00")
            midstate, tail = build_synthetic_work(seed)
            try:
                result = device.submit_and_wait(midstate, tail)
            except BFLError:
                # Device may overheat or time out; stop gracefully.
                break
            work_count += 1
            nonce_count += len(result.nonces)
            counter += 1

    elapsed = max(time.monotonic() - start, 0.001)  # avoid division by zero
    rate = work_count / elapsed

    click.echo(f"Work units completed: {work_count}")
    click.echo(f"Total nonces found: {nonce_count}")
    click.echo(f"Rate: {rate:.1f} work units/sec")


# ======================================================================
# hash
# ======================================================================


@main.command(name="hash")
@click.argument("input_data")
@click.pass_context
def hash_cmd(ctx: click.Context, input_data: str) -> None:
    """Hash arbitrary input data via the BFL ASIC."""
    transport = get_transport(
        ctx.obj["port"], ctx.obj["simulate"], ctx.obj["baudrate"],
    )
    with BFLDevice(transport) as device:
        nonces = device.hash_data(input_data.encode("utf-8"))
        click.echo(f"Input: {input_data}")
        click.echo(f"Nonces found: {len(nonces)}")
        for nonce in nonces:
            click.echo(f"  0x{nonce:08x}")


# ======================================================================
# stats
# ======================================================================


class _MutuallyExclusive(click.Option):
    """Click option that is mutually exclusive with another option."""

    def __init__(self, *args, **kwargs):
        self.mutually_exclusive = set(kwargs.pop("mutually_exclusive", []))
        super().__init__(*args, **kwargs)

    def handle_parse_result(self, ctx, opts, args):
        current = self.name in opts and opts[self.name] is not None
        for other in self.mutually_exclusive:
            if other in opts and opts[other] is not None and current:
                raise click.UsageError(
                    f"--{self.name} and --{other} are mutually exclusive."
                )
        return super().handle_parse_result(ctx, opts, args)


@main.group()
def stats() -> None:
    """SHA-256 statistical analysis commands."""


@stats.command(name="run")
@click.option(
    "--samples", default=None, type=int,
    cls=_MutuallyExclusive, mutually_exclusive=["duration"],
    help="Number of hash samples to collect (default: 10000).",
)
@click.option(
    "--duration", default=None, type=float,
    cls=_MutuallyExclusive, mutually_exclusive=["samples"],
    help="Run for N seconds instead of a fixed sample count.",
)
@click.option("--report-interval", default=2000, type=int, help="Progress report interval.")
@click.option("-o", "--output", default=None, type=click.Path(), help="Save snapshot to JSON file.")
@click.option("--plot", is_flag=True, default=False, help="Generate dashboard PNG.")
def stats_run(samples, duration, report_interval, output, plot) -> None:
    """Run the statistical analysis pipeline."""
    from bfl_asic.stats import StatsPipeline

    def _progress(count: int, report: dict) -> None:
        hr = report.get("hash_rate", 0.0)
        click.echo(f"  [{count:,} samples] hash rate: {hr:,.0f} H/s")

    pipeline = StatsPipeline(report_interval=report_interval, on_progress=_progress)

    if duration is not None:
        click.echo(f"Running statistical analysis for {duration:.1f} seconds...")
        snapshot = pipeline.run_timed(duration)
    else:
        n = samples if samples is not None else 10_000
        click.echo(f"Running statistical analysis ({n:,} samples)...")
        snapshot = pipeline.run(n)

    # Print summary
    click.echo("")
    click.echo("=== Summary ===")
    click.echo(f"  Samples:           {snapshot.sample_count:,}")
    click.echo(f"  Hash rate:         {snapshot.hash_rate:,.0f} H/s")
    click.echo(f"  Max bias:          {snapshot.bit_frequency.get('max_bias', 'N/A')}")
    click.echo(f"  Mean Hamming:      {snapshot.avalanche.get('mean', 'N/A')}")
    click.echo(f"  Shannon entropy:   {snapshot.entropy.get('shannon_entropy', 'N/A')}")

    # Save snapshot
    if output is not None:
        snapshot.save(Path(output))
        click.echo(f"  Snapshot saved to: {output}")

    # Generate dashboard plot
    if plot:
        import matplotlib.pyplot as plt
        from bfl_asic.stats.visualization import plot_dashboard

        if output is not None:
            png_path = Path(output).with_suffix(".png")
        else:
            png_path = Path("dashboard.png")
        fig = plot_dashboard(snapshot, save_path=png_path)
        plt.close(fig)
        click.echo(f"  Dashboard saved to: {png_path}")


@stats.command(name="animate-convergence")
@click.option("--samples", default=100_000, type=int,
              help="Total hashes to feed through the accumulator.")
@click.option("--frames", default=60, type=int,
              help="Approximate number of animation frames (log-spaced).")
@click.option("--fps", default=10, type=int, help="Frames per second in the GIF.")
@click.option("-o", "--output", default="convergence.gif",
              type=click.Path(), help="Output GIF path.")
def stats_animate_convergence(samples, frames, fps, output) -> None:
    """Animate per-bit frequency deviation converging to zero as N grows.

    A learning aid: the 16x16 heatmap fades from speckled to flat-white while
    the bottom line plot shows max/mean |bias| tracking the theoretical
    0.5/sqrt(N) envelope.
    """
    import matplotlib.pyplot as plt
    from bfl_asic.stats.visualization import animate_bit_frequency_convergence

    click.echo(
        f"Building convergence animation ({samples:,} samples, "
        f"{frames} frames)..."
    )
    fig, _anim = animate_bit_frequency_convergence(
        total_samples=samples,
        n_frames=frames,
        fps=fps,
        save_path=Path(output),
    )
    plt.close(fig)
    click.echo(f"  Animation saved to: {output}")


@stats.command(name="report")
@click.argument("snapshot_path", type=click.Path(exists=True))
def stats_report(snapshot_path: str) -> None:
    """Load a snapshot JSON file and print a formatted summary."""
    from bfl_asic.stats.snapshot import StatsSnapshot

    try:
        snapshot = StatsSnapshot.load(Path(snapshot_path))
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        raise click.ClickException(f"Failed to load snapshot: {exc}")

    click.echo("=== Stats Report ===")
    click.echo(f"  Timestamp:         {snapshot.timestamp}")
    click.echo(f"  Engine:            {snapshot.engine_name}")
    click.echo(f"  Samples:           {snapshot.sample_count:,}")
    click.echo(f"  Duration:          {snapshot.duration_seconds:.2f}s")
    click.echo(f"  Hash rate:         {snapshot.hash_rate:,.0f} H/s")
    click.echo("")
    click.echo("--- Bit Frequency ---")
    click.echo(f"  Max bias:          {snapshot.bit_frequency.get('max_bias', 'N/A')}")
    click.echo("")
    click.echo("--- Avalanche ---")
    click.echo(f"  Mean Hamming:      {snapshot.avalanche.get('mean', 'N/A')}")
    click.echo(f"  Std Hamming:       {snapshot.avalanche.get('std', 'N/A')}")
    click.echo("")
    click.echo("--- Correlation ---")
    click.echo(f"  Max deviation:     {snapshot.correlation.get('max_deviation', 'N/A')}")
    click.echo("")
    click.echo("--- Near Collision ---")
    click.echo(f"  Collisions found:  {snapshot.near_collision.get('collision_count', 'N/A')}")
    click.echo("")
    click.echo("--- Byte Distribution ---")
    click.echo(f"  Chi-squared:       {snapshot.byte_distribution.get('chi_squared', 'N/A')}")
    click.echo("")
    click.echo("--- Entropy ---")
    click.echo(f"  Shannon entropy:   {snapshot.entropy.get('shannon_entropy', 'N/A')}")


# ======================================================================
# dynamics
# ======================================================================


def _orbit_to_dict(orbit) -> dict:
    """Serialize an OrbitResult to a JSON-compatible dict."""
    return {
        "seed": orbit.seed.hex(),
        "iterations": orbit.iterations,
        "tail_length": orbit.tail_length,
        "cycle_length": orbit.cycle_length,
        "cycle_entry": orbit.cycle_entry.hex() if orbit.cycle_entry else None,
        "is_fixed_point": orbit.is_fixed_point,
        "hamming_distances": orbit.hamming_distances,
        "mean_hamming": orbit.mean_hamming,
        "min_hamming": orbit.min_hamming,
        "max_hamming": orbit.max_hamming,
        "trajectory_sample": [
            {"iteration": pt.iteration, "value": pt.value.hex()}
            for pt in orbit.trajectory_sample
        ],
    }


def _orbit_from_dict(d: dict):
    """Deserialize an OrbitResult from a dict."""
    from bfl_asic.dynamics.orbit import OrbitResult, OrbitPoint

    return OrbitResult(
        seed=bytes.fromhex(d["seed"]),
        iterations=d["iterations"],
        tail_length=d["tail_length"],
        cycle_length=d["cycle_length"],
        cycle_entry=bytes.fromhex(d["cycle_entry"]) if d["cycle_entry"] else None,
        is_fixed_point=d["is_fixed_point"],
        hamming_distances=d["hamming_distances"],
        mean_hamming=d["mean_hamming"],
        min_hamming=d["min_hamming"],
        max_hamming=d["max_hamming"],
        trajectory_sample=[
            OrbitPoint(iteration=pt["iteration"], value=bytes.fromhex(pt["value"]))
            for pt in d["trajectory_sample"]
        ],
    )


def _convergence_to_dict(result) -> dict:
    """Serialize a ConvergenceResult to a JSON-compatible dict."""
    return {
        "seed_count": result.seed_count,
        "max_iterations": result.max_iterations,
        "orbits": [_orbit_to_dict(o) for o in result.orbits],
        "convergence_pairs": result.convergence_pairs,
        "common_states": result.common_states,
    }


def _convergence_from_dict(d: dict):
    """Deserialize a ConvergenceResult from a dict."""
    from bfl_asic.dynamics.convergence import ConvergenceResult

    return ConvergenceResult(
        seed_count=d["seed_count"],
        max_iterations=d["max_iterations"],
        orbits=[_orbit_from_dict(o) for o in d["orbits"]],
        convergence_pairs=[tuple(p) for p in d["convergence_pairs"]],
        common_states=d["common_states"],
    )


@main.group()
def dynamics() -> None:
    """Iterated hash dynamics analysis commands."""


@dynamics.command(name="run")
@click.option("--seeds", default=3, type=int, help="Number of random seeds.")
@click.option("--max-iterations", default=10000, type=int, help="Max iterations per orbit.")
@click.option("-o", "--output", default=None, type=click.Path(), help="Save results to JSON file.")
def dynamics_run(seeds: int, max_iterations: int, output: str | None) -> None:
    """Run iterated hash dynamics analysis."""
    from bfl_asic.dynamics.convergence import analyze_convergence, generate_random_seeds

    seed_list = generate_random_seeds(seeds)
    click.echo(f"Running dynamics analysis ({seeds} seeds, {max_iterations:,} max iterations)...")

    result = analyze_convergence(
        seeds=seed_list,
        max_iterations=max_iterations,
        check_interval=max(1, max_iterations // 100),
    )

    # Print orbit summaries
    click.echo("")
    click.echo("=== Orbit Summary ===")
    for idx, orbit in enumerate(result.orbits):
        seed_hex = orbit.seed[:8].hex()
        mean_hd = f"{orbit.mean_hamming:.1f}" if orbit.mean_hamming is not None else "N/A"
        min_hd = orbit.min_hamming if orbit.min_hamming is not None else "N/A"
        max_hd = orbit.max_hamming if orbit.max_hamming is not None else "N/A"
        click.echo(f"  Seed {idx} ({seed_hex}...):")
        click.echo(f"    Iterations:     {orbit.iterations:,}")
        click.echo(f"    Mean Hamming:   {mean_hd}")
        click.echo(f"    Min Hamming:    {min_hd}")
        click.echo(f"    Max Hamming:    {max_hd}")
        click.echo(f"    Fixed point:    {orbit.is_fixed_point}")

    # Print convergence summary
    click.echo("")
    click.echo("=== Convergence Summary ===")
    click.echo(f"  Pairs found:      {len(result.convergence_pairs)}")
    click.echo(f"  Common states:    {result.common_states}")

    # Save results
    if output is not None:
        data = _convergence_to_dict(result)
        Path(output).write_text(json.dumps(data, indent=2))
        click.echo(f"  Results saved to: {output}")


@dynamics.command(name="plot")
@click.argument("results_path", type=click.Path(exists=True))
def dynamics_plot(results_path: str) -> None:
    """Load dynamics results JSON and generate plots."""
    from bfl_asic.dynamics.visualization import (
        plot_orbit_hamming,
        plot_convergence,
        plot_tail_cycle_distribution,
    )

    import matplotlib.pyplot as plt

    try:
        data = json.loads(Path(results_path).read_text())
        result = _convergence_from_dict(data)
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        raise click.ClickException(f"Failed to load dynamics results: {exc}")

    base = Path(results_path).with_suffix("")

    # Plot individual orbits
    for idx, orbit in enumerate(result.orbits):
        png_path = Path(f"{base}_orbit_{idx}.png")
        fig = plot_orbit_hamming(orbit, save_path=png_path)
        plt.close(fig)
        click.echo(f"  Orbit {idx} plot saved to: {png_path}")

    # Convergence plot
    conv_path = Path(f"{base}_convergence.png")
    fig = plot_convergence(result, save_path=conv_path)
    plt.close(fig)
    click.echo(f"  Convergence plot saved to: {conv_path}")

    # Tail/cycle distribution
    dist_path = Path(f"{base}_tail_cycle.png")
    fig = plot_tail_cycle_distribution(result.orbits, save_path=dist_path)
    plt.close(fig)
    click.echo(f"  Tail/cycle plot saved to: {dist_path}")


# ======================================================================
# randomness
# ======================================================================


@main.group()
def randomness() -> None:
    """NIST SP 800-22 randomness test battery."""


@randomness.command(name="run")
@click.option(
    "--hashes", default=1000, type=int,
    help="Number of SHA-256d hashes to harvest (256 bits each).",
)
@click.option(
    "--alpha", default=0.01, type=float,
    help="Significance level; tests pass when p_value >= alpha.",
)
@click.option(
    "-o", "--output", default=None, type=click.Path(),
    help="Save snapshot to JSON file.",
)
def randomness_run(hashes: int, alpha: float, output: str | None) -> None:
    """Harvest hashes and run the full NIST SP 800-22 battery."""
    from bfl_asic.randomness.battery import RandomnessBattery

    click.echo(f"Running randomness battery ({hashes:,} hashes, alpha={alpha})...")
    battery = RandomnessBattery(alpha=alpha)
    snapshot = battery.run(hash_count=hashes)

    click.echo("")
    click.echo("=== Results ===")
    click.echo(f"  Engine:    {snapshot.engine_name}")
    click.echo(f"  Hashes:    {snapshot.sample_count:,}")
    click.echo(f"  Bits:      {snapshot.bit_count:,}")
    click.echo(f"  Duration:  {snapshot.duration_seconds:.2f}s")
    click.echo("")
    click.echo(f"  {'Test':<28} {'p-value':>12}   Verdict")
    click.echo(f"  {'-' * 28} {'-' * 12}   -------")
    for r in snapshot.results:
        verdict = "PASS" if r["passed"] else "FAIL"
        click.echo(f"  {r['name']:<28} {r['p_value']:>12.6f}   {verdict}")
    click.echo("")
    click.echo(
        f"  Summary: {snapshot.pass_count} passed, {snapshot.fail_count} failed"
    )

    if output is not None:
        snapshot.save(Path(output))
        click.echo(f"  Snapshot saved to: {output}")


@randomness.command(name="report")
@click.argument("snapshot_path", type=click.Path(exists=True))
def randomness_report(snapshot_path: str) -> None:
    """Load a randomness snapshot JSON file and print a formatted summary."""
    from bfl_asic.randomness.snapshot import RandomnessSnapshot

    try:
        snapshot = RandomnessSnapshot.load(Path(snapshot_path))
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        raise click.ClickException(f"Failed to load snapshot: {exc}")

    click.echo("=== Randomness Report ===")
    click.echo(f"  Timestamp:  {snapshot.timestamp}")
    click.echo(f"  Engine:     {snapshot.engine_name}")
    click.echo(f"  Hashes:     {snapshot.sample_count:,}")
    click.echo(f"  Bits:       {snapshot.bit_count:,}")
    click.echo(f"  Duration:   {snapshot.duration_seconds:.2f}s")
    click.echo(f"  Alpha:      {snapshot.alpha}")
    click.echo("")
    click.echo(f"  {'Test':<28} {'p-value':>12}   Verdict")
    click.echo(f"  {'-' * 28} {'-' * 12}   -------")
    for r in snapshot.results:
        verdict = "PASS" if r["passed"] else "FAIL"
        click.echo(f"  {r['name']:<28} {r['p_value']:>12.6f}   {verdict}")
    click.echo("")
    click.echo(
        f"  Summary: {snapshot.pass_count} passed, {snapshot.fail_count} failed"
    )
