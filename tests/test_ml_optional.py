# tests/test_ml_optional.py
"""The ML subsystem must not burden the torch-free core."""
from __future__ import annotations

import builtins
import importlib

import click
import pytest
from click.testing import CliRunner

from bfl_asic.cli import main, _require_torch


class TestMLOptional:
    @pytest.fixture
    def runner(self):
        return CliRunner()

    def test_help_works_without_touching_torch(self, runner):
        result = runner.invoke(main, ["--help"])
        assert result.exit_code == 0
        assert "ml" in result.output

    def test_ml_group_help_works(self, runner):
        result = runner.invoke(main, ["ml", "--help"])
        assert result.exit_code == 0

    def test_require_torch_raises_friendly_message(self, monkeypatch):
        real_import = builtins.__import__

        def fake_import(name, *args, **kwargs):
            if name == "torch" or name.startswith("torch."):
                raise ImportError("No module named 'torch'")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", fake_import)
        with pytest.raises(click.ClickException) as exc:
            _require_torch()
        assert 'pip install -e ".[ml]"' in str(exc.value)

    def test_ml_package_import_is_torch_free(self, monkeypatch):
        real_import = builtins.__import__

        def fake_import(name, *args, **kwargs):
            if name == "torch" or name.startswith("torch."):
                raise ImportError("blocked")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", fake_import)
        import bfl_asic.ml as ml_pkg
        importlib.reload(ml_pkg)
        assert hasattr(ml_pkg, "round_reduced_sha256")
