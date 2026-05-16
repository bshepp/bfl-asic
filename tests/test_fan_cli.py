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


def test_fan_no_ack_exits_nonzero(monkeypatch):
    # The critical safety-failure branch: device did NOT acknowledge a
    # (dangerous, persistent) fan command -> non-zero exit, clear msg.
    import bfl_asic.cli as climod

    class ErrTransport:
        is_open = True

        def open(self):
            self.is_open = True

        def close(self):
            self.is_open = False

        def write(self, data: bytes):
            self._last = data

        def readline(self, timeout=None):
            last = getattr(self, "_last", b"")
            if last.startswith(b"ZGX"):
                return b"BitForce SHA256 SC 1.0\n"
            return b"ERR:TIMEOUT\n"

    monkeypatch.setattr(climod, "get_transport", lambda *a, **k: ErrTransport())

    r = CliRunner().invoke(main, ["fan", "auto"])
    assert r.exit_code != 0
    assert "did not acknowledge" in r.output.lower()

    r2 = CliRunner().invoke(main, ["fan", "4"])
    assert r2.exit_code != 0
    assert "did not acknowledge" in r2.output.lower()
