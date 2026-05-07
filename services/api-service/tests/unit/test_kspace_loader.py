from pathlib import Path

import h5py
import numpy as np
import pytest

from app.services.reconstruction.kspace_loader import (
    InvalidKspaceError,
    UnsupportedShapeError,
    load,
)


def _write_npy(path: Path, arr: np.ndarray) -> None:
    np.save(path, arr)


def _write_npz(path: Path, **arrays) -> None:
    np.savez(path, **arrays)


def _write_h5(path: Path, dataset_name: str, arr: np.ndarray) -> None:
    with h5py.File(path, "w") as f:
        f.create_dataset(dataset_name, data=arr)


def test_load_npy_2d_complex(tmp_path: Path):
    arr = (np.random.default_rng(0).standard_normal((64, 64))
           + 1j * np.random.default_rng(1).standard_normal((64, 64))).astype(np.complex64)
    p = tmp_path / "k.npy"
    _write_npy(p, arr)

    kspace, ground_truth = load(p)

    assert kspace.shape == (64, 64)
    assert kspace.dtype == np.complex64
    assert ground_truth is None


def test_load_npy_real_2d_is_cast_to_complex(tmp_path: Path):
    arr = np.ones((32, 32), dtype=np.float32)
    p = tmp_path / "k.npy"
    _write_npy(p, arr)

    kspace, ground_truth = load(p)

    assert kspace.dtype == np.complex64
    assert kspace.shape == (32, 32)
    assert ground_truth is None


def test_load_npz_with_ground_truth(tmp_path: Path):
    kspace = np.ones((48, 48), dtype=np.complex64)
    truth = np.ones((48, 48), dtype=np.float32) * 0.5
    p = tmp_path / "k.npz"
    _write_npz(p, kspace=kspace, ground_truth_image=truth)

    loaded_kspace, loaded_truth = load(p)

    assert loaded_kspace.shape == (48, 48)
    assert loaded_truth is not None
    assert loaded_truth.shape == (48, 48)
    assert loaded_truth.dtype == np.float32


def test_load_npz_without_ground_truth_returns_none(tmp_path: Path):
    kspace = np.ones((48, 48), dtype=np.complex64)
    p = tmp_path / "k.npz"
    _write_npz(p, kspace=kspace)

    _, loaded_truth = load(p)

    assert loaded_truth is None


def test_load_h5_single_coil_2d(tmp_path: Path):
    arr = (np.random.default_rng(0).standard_normal((128, 128))
           + 1j * np.random.default_rng(1).standard_normal((128, 128))).astype(np.complex64)
    p = tmp_path / "k.h5"
    _write_h5(p, "kspace", arr)

    kspace, ground_truth = load(p)

    assert kspace.shape == (128, 128)
    assert kspace.dtype == np.complex64
    assert ground_truth is None


def test_load_h5_multi_coil_takes_middle_slice_with_coil_average(tmp_path: Path):
    """fastMRI 4D shape (slices, coils, h, w) → reduce to 2D."""
    arr = np.zeros((5, 4, 64, 64), dtype=np.complex64)
    arr[2, :, :, :] = 1.0 + 0j  # middle slice
    p = tmp_path / "k.h5"
    _write_h5(p, "kspace", arr)

    kspace, _ = load(p)

    assert kspace.shape == (64, 64)
    assert kspace.dtype == np.complex64


def test_load_garbage_bytes_raises_invalid(tmp_path: Path):
    p = tmp_path / "garbage.npy"
    p.write_bytes(b"this is not a numpy file")
    with pytest.raises(InvalidKspaceError):
        load(p)


def test_load_npz_missing_kspace_key_raises_invalid(tmp_path: Path):
    p = tmp_path / "k.npz"
    _write_npz(p, something_else=np.ones((32, 32)))
    with pytest.raises(InvalidKspaceError):
        load(p)


def test_load_1d_array_raises_unsupported_shape(tmp_path: Path):
    arr = np.ones(100, dtype=np.complex64)
    p = tmp_path / "k.npy"
    _write_npy(p, arr)
    with pytest.raises(UnsupportedShapeError):
        load(p)


def test_load_unknown_extension_raises_invalid(tmp_path: Path):
    p = tmp_path / "k.txt"
    p.write_text("hello")
    with pytest.raises(InvalidKspaceError):
        load(p)
