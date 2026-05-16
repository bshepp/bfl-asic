"""fan CLI command (simulator-backed)."""
from __future__ import annotations

from click.testing import CliRunner

from bfl_asic.cli import main


def test_fan_auto_ok():
    r = CliRunner().invoke(main, ["--simulate", "fan", "auto"])
    assert r.exit_code == 0, r.output
    assert "auto" in r.output.lower()


def test_fan_fixed_level_warns():
    r = CliRunner().invoke(main, ["--simulate", "fan", "4"])
    assert r.exit_code == 0, r.output
    assert "thermal" in r.output.lower()  # safety warning surfaced


def test_fan_rejects_bad_arg():
    r = CliRunner().invoke(main, ["--simulate", "fan", "9"])
    assert r.exit_code != 0


def test_fan_rejects_non_numeric_arg():
    r = CliRunner().invoke(main, ["--simulate", "fan", "frosty"])
    assert r.exit_code != 0


def test_help_lists_fan():
    r = CliRunner().invoke(main, ["--help"])
    assert r.exit_code == 0 and "fan" in r.output
