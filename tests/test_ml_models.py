# tests/test_ml_models.py
import pytest

torch = pytest.importorskip("torch")

from bfl_asic.ml.models import MODELS, build_model


def test_registry_has_expected_models():
    assert set(MODELS) == {"tiny_cnn", "linear_probe"}


@pytest.mark.parametrize("name", ["tiny_cnn", "linear_probe"])
def test_forward_shape(name):
    model = build_model(name)
    x = torch.randn(4, 1, 16, 16)
    out = model(x)
    assert out.shape == (4, 2)


def test_linear_probe_param_budget():
    model = build_model("linear_probe")
    n = sum(p.numel() for p in model.parameters())
    assert n == 256 * 2 + 2  # weights + bias for 256->2


def test_unknown_model_raises():
    with pytest.raises(KeyError, match="choices"):
        build_model("nope")


def test_tiny_cnn_channels_kwarg_via_build_model():
    model = build_model("tiny_cnn", channels=32)
    x = torch.randn(2, 1, 16, 16)
    assert model(x).shape == (2, 2)
    # channels kwarg must thread through to the final classifier layer
    assert model.net[-1].in_features == 32
