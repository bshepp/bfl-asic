# tests/test_ml_snapshot.py
from bfl_asic.ml.snapshot import MLSnapshot


def test_snapshot_roundtrips_through_json(tmp_path):
    snap = MLSnapshot.from_runs(
        experiment="sweep",
        feature="per-hash-image",
        model="tiny_cnn",
        points=[
            {"rounds": 2, "accuracy": 0.99, "advantage": 0.98,
             "accuracy_ci": [0.97, 1.0], "auc": 0.99,
             "min_detectable_advantage": 0.06},
            {"rounds": 64, "accuracy": 0.50, "advantage": 0.0,
             "accuracy_ci": [0.47, 0.53], "auc": 0.50,
             "min_detectable_advantage": 0.06},
        ],
        controls={"positive_ok": True, "negative_ok": True},
    )
    p = tmp_path / "snap.json"
    snap.save(p)
    back = MLSnapshot.load(p)
    assert back.experiment == "sweep"
    assert back.points[1]["rounds"] == 64
    assert back.controls["positive_ok"] is True
