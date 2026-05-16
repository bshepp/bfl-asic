# tests/test_ml_models.py
import pytest

torch = pytest.importorskip("torch")

from bfl_asic.ml.models import MODELS, build_model


def test_registry_has_expected_models():
    assert set(MODELS) == {"tiny_cnn", "linear_probe"}


@pytest.mark.parametrize("name", ["tiny_cnn", "linear_probe"])
def test_forward_shape(name):
    model = build_model(name)
    x = torch.zeros(4, 1, 16, 16)
    out = model(x)
    assert out.shape == (4, 2)


def test_linear_probe_param_budget():
    model = build_model("linear_probe")
    n = sum(p.numel() for p in model.parameters())
    assert n == 256 * 2 + 2  # weights + bias for 256->2


def test_unknown_model_raises():
    with pytest.raises(KeyError):
        build_model("nope")
