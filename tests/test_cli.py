"""Tests for the Click-based CLI (bfl_asic.cli).

All device-facing tests use --simulate so no hardware is required.
Group-level options (--simulate, --port, --baudrate) must be placed
before the subcommand name in Click invocations.
"""

from __future__ import annotations

import pytest
from click.testing import CliRunner

from bfl_asic.cli import main


@pytest.fixture
def runner() -> CliRunner:
    """Provide a Click CliRunner instance."""
    return CliRunner()


# ======================================================================
# identify
# ======================================================================


class TestIdentify:
    def test_identify(self, runner: CliRunner) -> None:
        result = runner.invoke(main, ["--simulate", "identify"])
        assert result.exit_code == 0
        assert "SHA-256" in result.output

    def test_identify_shows_device(self, runner: CliRunner) -> None:
        result = runner.invoke(main, ["--simulate", "identify"])
        assert "Device:" in result.output
        assert "Jalapeno" in result.output


# ======================================================================
# temperature
# ======================================================================


class TestTemperature:
    def test_temperature(self, runner: CliRunner) -> None:
        result = runner.invoke(main, ["--simulate", "temperature"])
        assert result.exit_code == 0
        # The degree symbol may render differently; check for 'C'
        assert "C" in result.output

    def test_temperature_shows_chip(self, runner: CliRunner) -> None:
        result = runner.invoke(main, ["--simulate", "temperature"])
        assert "Chip 1" in result.output


# ======================================================================
# device details
# ======================================================================


class TestDeviceDetails:
    def test_device_details_prints_census(self, runner: CliRunner) -> None:
        result = runner.invoke(main, ["--simulate", "device", "details"])
        assert result.exit_code == 0
        assert "BitFORCE SC" in result.output
        assert "30" in result.output          # engine count
        assert "[UNKNOWN]" in result.output   # frequency field

    def test_device_group_has_details_subcommand(self, runner: CliRunner) -> None:
        result = runner.invoke(main, ["device", "--help"])
        assert result.exit_code == 0
        assert "details" in result.output

    def test_render_census_labels_discovered_fields(self) -> None:
        from bfl_asic.cli import _render_census
        from bfl_asic.protocol.queued import parse_details
        real = (
            b"DEVICE: BitFORCE SC\nFIRMWARE: 1.0.0\n"
            b"MINIG SPEED: 5.15 GH/s\n"
            b"PROCESSOR 3: 12 engines @ 199 MHz\n"
            b"PROCESSOR 7: 14 engines @ 200 MHz\n"
            b"ENGINES: 26\nFREQUENCY: 189 MHz\n"
            b"XLINK MODE: MASTER\nCRITICAL TEMPERATURE: 0\n"
            b"XLINK PRESENT: NO\nOK\n"
        )
        text = "\n".join(_render_census(parse_details(real)))
        assert "5.15 GH/s" in text
        assert "189 MHz" in text
        assert "Processor 3: 12 engines @ 199 MHz" in text
        assert "Processor 7: 14 engines @ 200 MHz" in text
        # Every field here is now first-class, so nothing is dumped as
        # "undocumented".
        assert "undocumented" not in text.lower()

    def test_device_firmware(self, runner: CliRunner) -> None:
        result = runner.invoke(main, ["--simulate", "device", "firmware"])
        assert result.exit_code == 0
        assert "1.0.0" in result.output

    def test_device_note_read_empty(self, runner: CliRunner) -> None:
        result = runner.invoke(main, ["--simulate", "device", "note"])
        assert result.exit_code == 0
        assert "empty" in result.output.lower()

    def test_device_note_write_requires_confirm(self, runner: CliRunner) -> None:
        result = runner.invoke(
            main, ["--simulate", "device", "note", "--write", "hi"])
        assert result.exit_code != 0
        assert "confirm" in result.output.lower()

    def test_device_note_write_with_confirm_roundtrips(
            self, runner: CliRunner) -> None:
        result = runner.invoke(
            main, ["--simulate", "device", "note", "--write", "hi",
                   "--confirm-nvram-write"])
        assert result.exit_code == 0
        assert "hi" in result.output


# ======================================================================
# probe
# ======================================================================


class TestProbe:
    def test_probe(self, runner: CliRunner) -> None:
        result = runner.invoke(main, ["--simulate", "probe"])
        assert result.exit_code == 0
        assert "Identify" in result.output
        assert "Temperature" in result.output
        assert "Poll" in result.output

    def test_probe_header(self, runner: CliRunner) -> None:
        result = runner.invoke(main, ["--simulate", "probe"])
        assert "=== Device Probe ===" in result.output

    def test_probe_shows_idle(self, runner: CliRunner) -> None:
        result = runner.invoke(main, ["--simulate", "probe"])
        assert "IDLE" in result.output


# ======================================================================
# discover
# ======================================================================


class TestDiscover:
    def test_discover(self, runner: CliRunner) -> None:
        result = runner.invoke(main, ["discover"])
        assert result.exit_code == 0
        # On a machine without BFL hardware, should report none found
        # or list devices -- either way, exit code 0.


# ======================================================================
# benchmark
# ======================================================================


class TestBenchmark:
    def test_benchmark(self, runner: CliRunner) -> None:
        result = runner.invoke(main, ["--simulate", "benchmark", "--duration", "1"])
        assert result.exit_code == 0
        assert "work units" in result.output.lower()

    def test_benchmark_shows_rate(self, runner: CliRunner) -> None:
        result = runner.invoke(main, ["--simulate", "benchmark", "--duration", "1"])
        assert "Rate:" in result.output

    def test_benchmark_shows_nonces(self, runner: CliRunner) -> None:
        result = runner.invoke(main, ["--simulate", "benchmark", "--duration", "1"])
        assert "nonces found" in result.output.lower()


# ======================================================================
# hash
# ======================================================================


class TestHash:
    def test_hash(self, runner: CliRunner) -> None:
        result = runner.invoke(main, ["--simulate", "hash", "hello"])
        assert result.exit_code == 0
        assert "Input: hello" in result.output

    def test_hash_shows_nonce_count(self, runner: CliRunner) -> None:
        result = runner.invoke(main, ["--simulate", "hash", "hello world"])
        assert "Nonces found:" in result.output

    def test_hash_with_different_input(self, runner: CliRunner) -> None:
        result = runner.invoke(main, ["--simulate", "hash", "test data"])
        assert result.exit_code == 0
        assert "Input: test data" in result.output


# ======================================================================
# default simulate behaviour
# ======================================================================


class TestDefaultSimulate:
    def test_default_is_simulate(self, runner: CliRunner) -> None:
        """When neither --port nor --simulate is given, simulate by default."""
        result = runner.invoke(main, ["identify"])
        assert result.exit_code == 0
        assert "SHA-256" in result.output


# ======================================================================
# help
# ======================================================================


class TestHelp:
    def test_help(self, runner: CliRunner) -> None:
        result = runner.invoke(main, ["--help"])
        assert result.exit_code == 0
        assert "BFL ASIC" in result.output

    def test_help_lists_subcommands(self, runner: CliRunner) -> None:
        result = runner.invoke(main, ["--help"])
        assert "identify" in result.output
        assert "temperature" in result.output
        assert "probe" in result.output
        assert "discover" in result.output
        assert "benchmark" in result.output
        assert "hash" in result.output
        assert "stats" in result.output
        assert "dynamics" in result.output
