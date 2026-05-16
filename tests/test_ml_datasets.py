# tests/test_ml_datasets.py
import numpy as np
import pytest

torch = pytest.importorskip("torch")

from bfl_asic.ml.datasets import (
    PerHashImage,
    PerBatchDeviationMap,
    DistinguisherDatasetBuilder,
)


def test_per_hash_image_shape_and_values():
    ex = PerHashImage()
    outputs = np.zeros((5, 32), dtype=np.uint8)
    outputs[:, 0] = 0x80  # top bit of byte 0 set -> pixel (0,0) == 1
    img = ex.extract(outputs)
    assert img.shape == (5, 16, 16)
    assert img.dtype == np.float32
    assert img[0, 0, 0] == 1.0
    assert img[0, 0, 1] == 0.0


def test_per_batch_deviation_map_shape():
    ex = PerBatchDeviationMap(batch=64)
    rng = np.random.default_rng(0)
    outputs = rng.integers(0, 256, size=(64 * 3, 32), dtype=np.uint8)
    dev = ex.extract(outputs)
    assert dev.shape == (3, 16, 16)
    assert np.all(np.abs(dev) <= 0.5 + 1e-6)


def test_distinguisher_builder_deterministic_and_balanced():
    b1 = DistinguisherDatasetBuilder(seed=7, rounds=4, n=512, val_fraction=0.25)
    b2 = DistinguisherDatasetBuilder(seed=7, rounds=4, n=512, val_fraction=0.25)
    d1 = b1.build()
    d2 = b2.build()
    assert torch.equal(d1.x_train, d2.x_train)
    assert torch.equal(d1.y_train, d2.y_train)
    ytr = d1.y_train
    pos = int((ytr == 1).sum())
    assert abs(pos - len(ytr) / 2) <= len(ytr) * 0.1
    assert d1.x_train.shape[1:] == (1, 16, 16)
    assert d1.x_val.shape[0] == 128


def test_distinguisher_different_seed_changes_data():
    a = DistinguisherDatasetBuilder(seed=1, rounds=4, n=256).build()
    b = DistinguisherDatasetBuilder(seed=2, rounds=4, n=256).build()
    assert not torch.equal(a.x_train, b.x_train)
