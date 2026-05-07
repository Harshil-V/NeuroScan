"""Load k-space data from .npy, .npz, or .h5 files.

Returns a 2D complex64 array plus optional ground-truth image when present.
"""

from __future__ import annotations

from pathlib import Path

import h5py
import numpy as np


class InvalidKspaceError(Exception):
    """File is not parseable as a supported k-space format."""


class UnsupportedShapeError(Exception):
    """K-space array shape is not supported (must reduce to 2D)."""


_FASTMRI_DATASET_CANDIDATES = ("kspace", "reconstruction_rss", "reconstruction_esc")


def load(path: Path) -> tuple[np.ndarray, np.ndarray | None]:
    """Load k-space and optional ground-truth image.

    Returns:
        (kspace, ground_truth)
        - kspace: complex64, shape (H, W)
        - ground_truth: float32, shape (H, W), or None if not embedded.

    Raises:
        InvalidKspaceError: file is not a parseable .npy/.npz/.h5
        UnsupportedShapeError: array shape can't be reduced to 2D
    """
    suffix = path.suffix.lower()
    if suffix == ".npy":
        return _load_npy(path)
    if suffix == ".npz":
        return _load_npz(path)
    if suffix in (".h5", ".hdf5"):
        return _load_h5(path)
    raise InvalidKspaceError(f"Unsupported file extension: {suffix}")


def _load_npy(path: Path) -> tuple[np.ndarray, np.ndarray | None]:
    try:
        arr = np.load(path)
    except (ValueError, OSError) as exc:
        raise InvalidKspaceError(f"Failed to load .npy: {exc}") from exc
    return _coerce_2d_complex(arr), None


def _load_npz(path: Path) -> tuple[np.ndarray, np.ndarray | None]:
    try:
        archive = np.load(path)
    except (ValueError, OSError) as exc:
        raise InvalidKspaceError(f"Failed to load .npz: {exc}") from exc
    if "kspace" not in archive.files:
        raise InvalidKspaceError("'.npz' archive is missing required 'kspace' key")
    kspace = _coerce_2d_complex(archive["kspace"])
    ground_truth = None
    if "ground_truth_image" in archive.files:
        ground_truth = archive["ground_truth_image"].astype(np.float32)
    return kspace, ground_truth


def _load_h5(path: Path) -> tuple[np.ndarray, np.ndarray | None]:
    try:
        with h5py.File(path, "r") as f:
            for name in _FASTMRI_DATASET_CANDIDATES:
                if name in f:
                    arr = f[name][...]
                    return _coerce_2d_complex(arr), None
            available = list(f.keys())
            raise InvalidKspaceError(
                f"No recognized k-space dataset in HDF5; "
                f"looked for {_FASTMRI_DATASET_CANDIDATES}, found {available}"
            )
    except OSError as exc:
        raise InvalidKspaceError(f"Failed to open HDF5: {exc}") from exc


def _coerce_2d_complex(arr: np.ndarray) -> np.ndarray:
    """Reduce arrays to 2D complex64.

    Handles:
      - 2D real → cast to complex64
      - 2D complex → cast dtype to complex64
      - 3D (slices, h, w) → take middle slice
      - 4D (slices, coils, h, w) → middle slice, average across coils
    """
    if arr.ndim == 2:
        return arr.astype(np.complex64)
    if arr.ndim == 3:
        mid = arr.shape[0] // 2
        return arr[mid].astype(np.complex64)
    if arr.ndim == 4:
        mid_slice = arr.shape[0] // 2
        coil_avg = np.mean(arr[mid_slice], axis=0)
        return coil_avg.astype(np.complex64)
    raise UnsupportedShapeError(
        f"K-space must be 2D/3D/4D, got shape {arr.shape}"
    )
