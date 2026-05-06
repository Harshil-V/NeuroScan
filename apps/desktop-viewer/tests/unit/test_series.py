from pathlib import Path

import numpy as np
import pydicom

from app.dicom.loader import scan_folder
from app.dicom.series import LoadedSeries, auto_window_level, load_series
from tests.fixtures.make_test_series import write_test_series


def test_load_series_returns_volume_with_correct_shape(tmp_path: Path):
    write_test_series(tmp_path, n_instances=5, rows=32, columns=32)
    studies = scan_folder(tmp_path)
    series = studies[0].series[0]
    loaded = load_series(series)
    assert isinstance(loaded, LoadedSeries)
    assert loaded.volume.shape == (5, 32, 32)


def test_load_series_caches_raw_bytes(tmp_path: Path):
    write_test_series(tmp_path, n_instances=3)
    studies = scan_folder(tmp_path)
    loaded = load_series(studies[0].series[0])
    assert len(loaded.raw_bytes) == 3
    assert all(isinstance(b, bytes) for b in loaded.raw_bytes)
    assert all(len(b) > 0 for b in loaded.raw_bytes)


def test_load_series_caches_datasets(tmp_path: Path):
    write_test_series(tmp_path, n_instances=3)
    studies = scan_folder(tmp_path)
    loaded = load_series(studies[0].series[0])
    assert len(loaded.datasets) == 3
    assert all(isinstance(d, pydicom.Dataset) for d in loaded.datasets)
    assert loaded.datasets[0].SOPInstanceUID != loaded.datasets[1].SOPInstanceUID


def test_load_series_default_level_window_from_stats(tmp_path: Path):
    write_test_series(tmp_path, n_instances=3, rows=16, columns=16)
    studies = scan_folder(tmp_path)
    loaded = load_series(studies[0].series[0])
    # Synthetic data has uint16 values 0..4095 → level/window are sane numbers.
    assert isinstance(loaded.default_level, float)
    assert isinstance(loaded.default_window, float)
    assert loaded.default_window > 0


def test_auto_window_level_uses_dicom_tags_when_present():
    volume = np.array([[[100, 200], [300, 400]]], dtype=np.int16)

    class FakeDataset:
        WindowCenter = 250.0
        WindowWidth = 300.0

    level, window = auto_window_level(volume, [FakeDataset()])
    assert level == 250.0
    assert window == 300.0


def test_auto_window_level_handles_multi_value_window():
    """DICOM allows lists of window centers/widths; we take the first."""
    volume = np.array([[[100, 200]]], dtype=np.int16)

    class FakeDataset:
        WindowCenter = [40.0, 80.0]
        WindowWidth = [200.0, 400.0]

    level, window = auto_window_level(volume, [FakeDataset()])
    assert level == 40.0
    assert window == 200.0


def test_auto_window_level_falls_back_to_stats():
    rng = np.random.default_rng(0)
    volume = rng.integers(0, 4096, (10, 32, 32), dtype=np.uint16)

    class FakeDataset:
        pass  # no WindowCenter/WindowWidth

    level, window = auto_window_level(volume, [FakeDataset()])
    assert isinstance(level, float)
    assert isinstance(window, float)
    assert window > 0
    # Level should be near mean
    assert abs(level - float(np.mean(volume))) < 100
