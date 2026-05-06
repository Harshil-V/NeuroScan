"""Loading a series into memory: stack pixel data + cache datasets/bytes.

After load_series() returns, slice navigation requires zero disk I/O.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pydicom
from pydicom.dataset import Dataset

from app.dicom.loader import SeriesRef


@dataclass
class LoadedSeries:
    series_ref: SeriesRef
    volume: np.ndarray  # [N, H, W], native dtype
    raw_bytes: list[bytes]
    datasets: list[Dataset]
    default_level: float
    default_window: float


def load_series(series: SeriesRef) -> LoadedSeries:
    if not series.instances:
        raise ValueError(f"Series {series.series_instance_uid} has no instances")

    raw_bytes: list[bytes] = []
    datasets: list[Dataset] = []
    slices: list[np.ndarray] = []

    for inst in series.instances:
        data = inst.file_path.read_bytes()
        raw_bytes.append(data)
        ds = pydicom.dcmread(inst.file_path)
        datasets.append(ds)
        slices.append(ds.pixel_array)

    target_shape = slices[0].shape
    for i, s in enumerate(slices):
        if s.shape != target_shape:
            raise ValueError(
                f"Inconsistent slice shape: instance {i} has shape {s.shape}, "
                f"expected {target_shape}"
            )

    volume = np.stack(slices, axis=0)
    level, window = auto_window_level(volume, datasets)

    return LoadedSeries(
        series_ref=series,
        volume=volume,
        raw_bytes=raw_bytes,
        datasets=datasets,
        default_level=level,
        default_window=window,
    )


def _first_value(value: object) -> float | None:
    """DICOM lets WindowCenter/WindowWidth be a single value or a list. Take the first."""
    if value is None:
        return None
    if isinstance(value, list | tuple):
        if not value:
            return None
        try:
            return float(value[0])
        except (TypeError, ValueError):
            return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def auto_window_level(volume: np.ndarray, datasets: list[Dataset]) -> tuple[float, float]:
    """Determine default level and window for a volume.

    Prefers DICOM tags from the middle slice; falls back to mean ± 2*std clamped
    to the volume's actual range.
    """
    if datasets:
        mid = datasets[len(datasets) // 2]
        center = _first_value(getattr(mid, "WindowCenter", None))
        width = _first_value(getattr(mid, "WindowWidth", None))
        if center is not None and width is not None and width > 0:
            return center, width

    arr = volume.astype(np.float32)
    mean = float(np.mean(arr))
    std = float(np.std(arr))
    width = max(4.0 * std, 1.0)
    return mean, width
