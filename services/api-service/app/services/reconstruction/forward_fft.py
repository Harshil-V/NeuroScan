"""Forward FFT helper: convert a DICOM image into synthetic k-space.

Used by tests, demos, and the CLI generator at scripts/generate-synthetic-kspace.py.
The "ground truth" image is returned alongside the k-space so downstream code
can compute PSNR/SSIM after reconstruction.
"""

from __future__ import annotations

from io import BytesIO

import numpy as np
import pydicom


def dicom_to_kspace(dicom_bytes: bytes) -> tuple[np.ndarray, np.ndarray]:
    """Convert a DICOM image into synthetic k-space + return original as ground truth.

    Returns:
        (kspace, ground_truth)
        - kspace: complex64, shape (H, W), fftshifted (DC at center)
        - ground_truth: float32, shape (H, W), normalized to [0, 1]
    """
    ds = pydicom.dcmread(BytesIO(dicom_bytes))
    image = ds.pixel_array.astype(np.float32)
    peak = float(image.max())
    image_norm = image / peak if peak > 0 else image
    kspace = np.fft.fftshift(np.fft.fft2(image_norm)).astype(np.complex64)
    return kspace, image_norm.astype(np.float32)
