"""Click-based command-line interface for interacting with BFL ASIC devices.

Provides subcommands for device identification, temperature monitoring,
probing, discovery, benchmarking, and hashing through either a real serial
connection or the built-in simulator.
"""

from __future__ import annotations

import time

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
    """Query device temperature."""
    transport = get_transport(
        ctx.obj["port"], ctx.obj["simulate"], ctx.obj["baudrate"],
    )
    with BFLDevice(transport) as device:
        reading = device.get_temperature()
        for idx, temp in enumerate(reading.sensors):
            click.echo(f"Sensor {idx}: {temp:.1f}\u00b0C")


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
        click.echo("[ZTX] Temperature:")
        for idx, temp in enumerate(reading.sensors):
            click.echo(f"  Sensor {idx}: {temp:.1f}\u00b0C")
        click.echo()

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
