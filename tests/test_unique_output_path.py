"""Tests for the CLI ``unique_output_path`` collision-avoidance helper."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from click.testing import CliRunner

from bfl_asic.cli import main, unique_output_path


_TS_RE = re.compile(r"_\d{8}-\d{6}(?:_\d+)?")


# -------------------------------------------------------------------
# unique_output_path()
# -------------------------------------------------------------------


class TestUniqueOutputPath:
    def test_returns_path_unchanged_when_free(self, tmp_path: Path) -> None:
        target = tmp_path / "fresh.gif"
        assert unique_output_path(target) == target

    def test_inserts_timestamp_when_exists(self, tmp_path: Path) -> None:
        target = tmp_path / "out.gif"
        target.write_bytes(b"existing")
        result = unique_output_path(target)
        assert result != target
        assert result.suffix == ".gif"
        assert result.stem.startswith("out_")
        assert _TS_RE.search(result.stem) is not None
        assert not result.exists()

    def test_preserves_directory(self, tmp_path: Path) -> None:
        subdir = tmp_path / "sub"
        subdir.mkdir()
        target = subdir / "out.png"
        target.write_bytes(b"existing")
        result = unique_output_path(target)
        assert result.parent == subdir

    def test_preserves_compound_suffix_via_stem(self, tmp_path: Path) -> None:
        # Path.suffix returns the LAST suffix; we accept that limitation
        target = tmp_path / "data.tar.gz"
        target.write_bytes(b"existing")
        result = unique_output_path(target)
        assert result.suffix == ".gz"
        # The .tar part is part of the stem -> stays before the timestamp
        assert "data.tar_" in result.name

    def test_same_second_collision_gets_counter(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Pin time.strftime so two calls land in the same 'second' and force the counter."""
        import bfl_asic.cli as cli_mod
        monkeypatch.setattr(
            cli_mod.time, "strftime", lambda *_args, **_kw: "20260513-203012"
        )
        target = tmp_path / "out.gif"
        target.write_bytes(b"x")
        # Pre-create the timestamped file too, forcing the counter branch
        (tmp_path / "out_20260513-203012.gif").write_bytes(b"x")
        result = unique_output_path(target)
        assert result.name == "out_20260513-203012_1.gif"


# -------------------------------------------------------------------
# End-to-end CLI behavior: re-running does not overwrite
# -------------------------------------------------------------------


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


class TestNoOverwriteRandomnessRun:
    def test_second_run_writes_distinct_file(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        target = tmp_path / "rand.json"
        r1 = runner.invoke(
            main, ["randomness", "run", "--hashes", "20", "-o", str(target)]
        )
        assert r1.exit_code == 0, r1.output
        assert target.exists()
        first_bytes = target.read_bytes()

        r2 = runner.invoke(
            main, ["randomness", "run", "--hashes", "20", "-o", str(target)]
        )
        assert r2.exit_code == 0, r2.output

        # Original must be untouched
        assert target.read_bytes() == first_bytes
        # And exactly one new sibling must appear with a timestamp suffix
        siblings = [p for p in tmp_path.iterdir() if p != target]
        assert len(siblings) == 1
        assert _TS_RE.search(siblings[0].stem) is not None


class TestNoOverwriteStatsRun:
    def test_second_run_writes_distinct_file(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        target = tmp_path / "snap.json"
        r1 = runner.invoke(
            main, ["stats", "run", "--samples", "200", "-o", str(target)]
        )
        assert r1.exit_code == 0
        assert target.exists()
        first_size = target.stat().st_size

        r2 = runner.invoke(
            main, ["stats", "run", "--samples", "200", "-o", str(target)]
        )
        assert r2.exit_code == 0
        assert target.stat().st_size == first_size
        siblings = [p for p in tmp_path.iterdir() if p != target]
        assert len(siblings) == 1


class TestNoOverwriteAnimateConvergence:
    def test_second_run_writes_distinct_gif(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        target = tmp_path / "conv.gif"
        r1 = runner.invoke(
            main,
            [
                "stats", "animate-convergence",
                "--samples", "500", "--frames", "5",
                "-o", str(target),
            ],
        )
        assert r1.exit_code == 0, r1.output
        assert target.exists()
        first_bytes = target.read_bytes()

        r2 = runner.invoke(
            main,
            [
                "stats", "animate-convergence",
                "--samples", "500", "--frames", "5",
                "-o", str(target),
            ],
        )
        assert r2.exit_code == 0, r2.output
        assert target.read_bytes() == first_bytes
        siblings = [p for p in tmp_path.iterdir() if p != target]
        assert len(siblings) == 1
        assert siblings[0].suffix == ".gif"
