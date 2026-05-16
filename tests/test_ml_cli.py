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


def test_ml_run_indistinguishability_smoke(tmp_path, monkeypatch):
    monkeypatch.setenv("BFL_ASIC_OUTPUT_DIR", str(tmp_path))
    res = CliRunner().invoke(
        main, ["ml", "run", "indistinguishability", "--n", "256",
               "--epochs", "1"]
    )
    assert res.exit_code == 0, res.output
    snaps = list((tmp_path / "ml").rglob("snapshot.json"))
    assert snaps, res.output
    data = json.loads(snaps[0].read_text())
    assert data["experiment"] == "indistinguishability"
    # provenance must match what actually trained (harness default)
    assert data["feature"] == "per-hash"


def test_ml_run_full_structure_smoke(tmp_path, monkeypatch):
    monkeypatch.setenv("BFL_ASIC_OUTPUT_DIR", str(tmp_path))
    res = CliRunner().invoke(
        main, ["ml", "run", "full_structure", "--n", "256", "--epochs", "1"]
    )
    assert res.exit_code == 0, res.output
    snaps = list((tmp_path / "ml").rglob("snapshot.json"))
    assert snaps, res.output
    data = json.loads(snaps[0].read_text())
    assert data["experiment"] == "full_structure"
    assert data["feature"] == "per-hash"
    assert data["bounded_null"]  # non-empty bounded-null block serialized
    assert "conclusion" in data["bounded_null"]


def test_ml_sweep_explicit_output_path(tmp_path):
    out = tmp_path / "myrun.json"
    res = CliRunner().invoke(
        main, ["ml", "sweep", "--rounds", "2,64", "--n", "256",
               "--epochs", "1", "--model", "linear_probe", "-o", str(out)]
    )
    assert res.exit_code == 0, res.output
    assert out.exists()  # explicit -o honoured verbatim


def test_ml_plot_writes_png(tmp_path):
    from bfl_asic.ml.snapshot import MLSnapshot

    snap = MLSnapshot.from_runs(
        experiment="sweep", feature="per-hash", model="linear_probe",
        points=[
            {"rounds": 2, "accuracy": 0.95, "advantage": 0.90,
             "accuracy_ci": [0.92, 0.98], "auc": 0.95,
             "min_detectable_advantage": 0.06},
            {"rounds": 64, "accuracy": 0.50, "advantage": 0.0,
             "accuracy_ci": [0.47, 0.53], "auc": 0.5,
             "min_detectable_advantage": 0.06},
        ],
        controls={"positive_ok": True, "negative_ok": True},
    )
    p = tmp_path / "snap.json"
    snap.save(p)
    res = CliRunner().invoke(main, ["ml", "plot", str(p)])
    assert res.exit_code == 0, res.output
    assert (tmp_path / "snap.png").exists()


def test_ml_sweep_per_batch_feature(tmp_path, monkeypatch):
    monkeypatch.setenv("BFL_ASIC_OUTPUT_DIR", str(tmp_path))
    res = CliRunner().invoke(
        main,
        ["ml", "sweep", "--rounds", "2,64", "--n", "4096",
         "--epochs", "1", "--model", "linear_probe",
         "--feature", "per-batch"],
    )
    assert res.exit_code == 0, res.output
    runs = list((tmp_path / "ml").rglob("snapshot.json"))
    assert runs, res.output
    data = json.loads(runs[0].read_text())
    assert data["experiment"] == "sweep"
    assert data["feature"] == "per-batch"
    assert len(data["points"]) == 2


def test_ml_sweep_per_batch_small_n_is_friendly_error(tmp_path, monkeypatch):
    monkeypatch.setenv("BFL_ASIC_OUTPUT_DIR", str(tmp_path))
    res = CliRunner().invoke(
        main,
        ["ml", "sweep", "--rounds", "2", "--n", "256",
         "--epochs", "1", "--feature", "per-batch"],
    )
    assert res.exit_code != 0
    assert "per-batch needs --n >= 2048" in res.output


def test_ml_run_dynamics(tmp_path, monkeypatch):
    monkeypatch.setenv("BFL_ASIC_OUTPUT_DIR", str(tmp_path))
    res = CliRunner().invoke(
        main,
        ["ml", "run", "dynamics", "--n", "128", "--epochs", "1"],
    )
    assert res.exit_code == 0, res.output
    assert list((tmp_path / "ml").rglob("snapshot.json"))


def test_dynamics_snapshot_is_strict_valid_json(tmp_path):
    import json as _json

    from bfl_asic.ml.snapshot import MLSnapshot

    snap = MLSnapshot.from_runs(
        experiment="dynamics", feature="seed-image", model="tiny_cnn",
        points=[{"rounds": 1, "accuracy": 0.5, "advantage": 0.25,
                 "auc": None, "accuracy_ci": [0.0, 1.0],
                 "min_detectable_advantage": 0.0, "chance": 0.25}],
        controls={"positive_ok": True, "negative_ok": True},
    )
    text = snap.to_json()
    assert "NaN" not in text and "Infinity" not in text
    _json.loads(text)  # must parse with the strict stdlib parser


def test_dynamics_plot_uses_correct_axis_and_chance(tmp_path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    from bfl_asic.ml.snapshot import MLSnapshot
    from bfl_asic.ml.visualization import plot_learnability_curve

    snap = MLSnapshot.from_runs(
        experiment="dynamics", feature="seed-image", model="tiny_cnn",
        points=[
            {"rounds": 1, "accuracy": 0.60, "advantage": 0.35,
             "auc": None, "accuracy_ci": [0.0, 1.0],
             "min_detectable_advantage": 0.0, "chance": 0.25},
            {"rounds": 3, "accuracy": 0.27, "advantage": 0.02,
             "auc": None, "accuracy_ci": [0.0, 1.0],
             "min_detectable_advantage": 0.0, "chance": 0.25},
        ],
        controls={"positive_ok": True, "negative_ok": True},
    )
    fig = plot_learnability_curve(snap, save_path=tmp_path / "d.png")
    assert (tmp_path / "d.png").exists()
    ax = fig.axes[0]
    assert ax.get_xlabel() == "truncation width (bytes)"
    assert "Dynamics" in ax.get_title()
    plt.close(fig)
