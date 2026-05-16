# tests/test_ml_publish.py
import sys
import types

from bfl_asic.ml.publish import build_model_card


def test_model_card_contains_key_facts():
    from bfl_asic.ml.snapshot import MLSnapshot

    snap = MLSnapshot.from_runs(
        experiment="sweep", feature="per-hash-image", model="tiny_cnn",
        points=[{"rounds": 64, "accuracy": 0.5, "advantage": 0.0,
                 "accuracy_ci": [0.47, 0.53], "auc": 0.5,
                 "min_detectable_advantage": 0.06}],
        controls={"positive_ok": True, "negative_ok": True},
    )
    card = build_model_card(snap)
    assert "sweep" in card
    assert "tiny_cnn" in card
    assert "learnability" in card.lower()


def test_publish_invokes_hf_api(monkeypatch, tmp_path):
    calls = {}

    fake_hf = types.ModuleType("huggingface_hub")

    class FakeApi:
        def create_repo(self, repo_id, exist_ok=False, **kw):
            calls["repo"] = repo_id

        def upload_folder(self, repo_id, folder_path, **kw):
            calls["folder"] = folder_path

    fake_hf.HfApi = FakeApi
    monkeypatch.setitem(sys.modules, "huggingface_hub", fake_hf)

    from bfl_asic.ml.publish import publish_run

    (tmp_path / "snapshot.json").write_text("{}")
    publish_run(tmp_path, repo_id="user/bfl-ml")
    assert calls["repo"] == "user/bfl-ml"
    assert str(tmp_path) in str(calls["folder"])


def test_publish_writes_readme_from_real_snapshot(monkeypatch, tmp_path):
    from bfl_asic.ml.snapshot import MLSnapshot

    fake_hf = types.ModuleType("huggingface_hub")

    class FakeApi:
        def create_repo(self, repo_id, exist_ok=False, **kw):
            pass

        def upload_folder(self, repo_id, folder_path, **kw):
            pass

    fake_hf.HfApi = FakeApi
    monkeypatch.setitem(sys.modules, "huggingface_hub", fake_hf)

    from bfl_asic.ml.publish import publish_run

    snap = MLSnapshot.from_runs(
        experiment="sweep", feature="per-hash", model="tiny_cnn",
        points=[{"rounds": 4, "accuracy": 0.6, "advantage": 0.2,
                 "accuracy_ci": [0.57, 0.63], "auc": 0.61,
                 "min_detectable_advantage": 0.05}],
        controls={},
    )
    (tmp_path / "snapshot.json").write_text(snap.to_json())
    publish_run(tmp_path, repo_id="user/bfl-ml")
    readme = (tmp_path / "README.md").read_text()
    assert "BFL-ASIC ML Learnability Run" in readme
    assert "0.6000" in readme
