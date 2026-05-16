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


def test_class_b_random_false_path_differs_and_is_deterministic():
    same_a = DistinguisherDatasetBuilder(seed=3, rounds=4, n=512).build()
    ctrl1 = DistinguisherDatasetBuilder(
        seed=3, rounds=4, n=512, class_b_random=False
    ).build()
    ctrl2 = DistinguisherDatasetBuilder(
        seed=3, rounds=4, n=512, class_b_random=False
    ).build()
    # class_b_random=False (full-64-round SHA as the negative class) must be
    # reproducible and must differ from the random-bytes class B.
    assert torch.equal(ctrl1.x_train, ctrl2.x_train)
    assert not torch.equal(ctrl1.x_train, same_a.x_train)
    assert ctrl1.x_train.shape[1:] == (1, 16, 16)


def test_val_and_train_tensor_dtypes():
    d = DistinguisherDatasetBuilder(seed=8, rounds=4, n=256).build()
    assert d.x_train.dtype == torch.float32
    assert d.y_train.dtype == torch.int64
    assert d.x_val.dtype == torch.float32
    assert d.y_val.dtype == torch.int64


def test_custom_extractor_injection():
    builder = DistinguisherDatasetBuilder(
        seed=2, rounds=4, n=512, extractor=PerBatchDeviationMap(batch=64)
    )
    d = builder.build()
    assert d.x_train.shape[1:] == (1, 16, 16)
    assert d.feature_name == "per-batch-deviation-map-b64"


def test_per_batch_deviation_map_truncates_remainder():
    ex = PerBatchDeviationMap(batch=64)
    rng = np.random.default_rng(1)
    outputs = rng.integers(0, 256, size=(193, 32), dtype=np.uint8)
    dev = ex.extract(outputs)
    assert dev.shape == (3, 16, 16)  # 193 // 64 == 3, remainder dropped


def test_orbit_dataset_builder_labels_and_determinism():
    from bfl_asic.ml.datasets import OrbitDatasetBuilder

    a = OrbitDatasetBuilder(seed=5, trunc_bytes=2, n=128, n_bins=3).build()
    b = OrbitDatasetBuilder(seed=5, trunc_bytes=2, n=128, n_bins=3).build()
    assert torch.equal(a.x_train, b.x_train)
    assert a.x_train.shape[1:] == (1, 16, 16)
    labels = torch.cat([a.y_train, a.y_val])
    assert int(labels.min()) >= 0
    assert int(labels.max()) <= 2
