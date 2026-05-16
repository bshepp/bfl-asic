# tests/test_ml_cli.py
import json

import pytest
from click.testing import CliRunner

torch = pytest.importorskip("torch")

from bfl_asic.cli import main


def test_ml_sweep_tiny(tmp_path, monkeypatch):
    monkeypatch.setenv("BFL_ASIC_OUTPUT_DIR", str(tmp_path))
    res = CliRunner().invoke(
        main,
        ["ml", "sweep", "--rounds", "2,64", "--n", "256",
         "--epochs", "1", "--model", "linear_probe"],
    )
    assert res.exit_code == 0, res.output
    runs = list((tmp_path / "ml").rglob("snapshot.json"))
    assert runs, res.output
    data = json.loads(runs[0].read_text())
    assert data["experiment"] == "sweep"
    assert len(data["points"]) == 2


def test_ml_report_reads_snapshot(tmp_path):
    from bfl_asic.ml.snapshot import MLSnapshot

    snap = MLSnapshot.from_runs(
        experiment="sweep", feature="per-hash-image", model="linear_probe",
        points=[{"rounds": 64, "accuracy": 0.5, "advantage": 0.0,
                 "accuracy_ci": [0.47, 0.53], "auc": 0.5,
                 "min_detectable_advantage": 0.06}],
        controls={"positive_ok": True, "negative_ok": True},
    )
    p = tmp_path / "s.json"
    snap.save(p)
    res = CliRunner().invoke(main, ["ml", "report", str(p)])
    assert res.exit_code == 0
    assert "sweep" in res.output
    assert "64" in res.output
