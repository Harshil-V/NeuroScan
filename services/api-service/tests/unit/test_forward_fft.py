import numpy as np
import pytest

from app.services.reconstruction.forward_fft import dicom_to_kspace
from tests.fixtures.synthetic_dicom import make_synthetic_mr_dicom_bytes


def test_dicom_to_kspace_returns_complex_kspace_and_ground_truth():
    dicom_bytes = make_synthetic_mr_dicom_bytes(rows=64, columns=64)
    kspace, ground_truth = dicom_to_kspace(dicom_bytes)

    assert kspace.shape == (64, 64)
    assert kspace.dtype == np.complex64
    assert ground_truth is not None
    assert ground_truth.shape == (64, 64)
    assert ground_truth.dtype == np.float32


def test_dicom_to_kspace_ground_truth_is_normalized_to_unit_range():
    dicom_bytes = make_synthetic_mr_dicom_bytes(rows=32, columns=32)
    _, ground_truth = dicom_to_kspace(dicom_bytes)
    assert ground_truth.min() >= 0.0
    assert ground_truth.max() <= 1.0 + 1e-6


def test_dicom_to_kspace_kspace_is_fftshifted():
    """Center frequency of a uniform image should sit at the array center."""
    # We make a non-zero ground truth by overriding pixel data to a constant
    # For a constant image, fft is a delta at DC; after fftshift, the delta is at the center.
    rows, cols = 64, 64
    constant = np.full((rows, cols), 1000, dtype=np.uint16)
    dicom_bytes = make_synthetic_mr_dicom_bytes(
        rows=rows, columns=cols, pixel_array_override=constant
    )
    kspace, _ = dicom_to_kspace(dicom_bytes)

    # The DC component (max magnitude) should be at the geometric center after fftshift
    magnitude = np.abs(kspace)
    center_value = magnitude[rows // 2, cols // 2]
    assert center_value == magnitude.max(), (
        f"Expected DC at center; max at {np.unravel_index(magnitude.argmax(), magnitude.shape)}"
    )


def test_dicom_to_kspace_handles_zero_image():
    """Avoid divide-by-zero when the DICOM is all zeros."""
    rows, cols = 32, 32
    zero_image = np.zeros((rows, cols), dtype=np.uint16)
    dicom_bytes = make_synthetic_mr_dicom_bytes(
        rows=rows, columns=cols, pixel_array_override=zero_image
    )
    kspace, ground_truth = dicom_to_kspace(dicom_bytes)
    assert kspace.shape == (rows, cols)
    assert ground_truth.shape == (rows, cols)
    assert not np.any(np.isnan(kspace))
    assert not np.any(np.isnan(ground_truth))


def test_dicom_to_kspace_garbage_raises():
    with pytest.raises(Exception):
        dicom_to_kspace(b"this is definitely not DICOM")
