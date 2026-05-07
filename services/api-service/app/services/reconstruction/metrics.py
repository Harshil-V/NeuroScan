"""Image quality metrics: PSNR and SSIM.

Both functions normalize inputs internally to [0, 1] so absolute scale
doesn't affect results.
"""

from __future__ import annotations

import numpy as np
from skimage.metrics import structural_similarity

_PSNR_MAX_DB = 100.0
_PSNR_MIN_MSE = 1e-10


def _normalize(arr: np.ndarray) -> np.ndarray:
    arr = arr.astype(np.float32)
    arr = arr - arr.min()
    peak = float(arr.max())
    if peak > 0:
        arr = arr / peak
    return arr


def psnr(reconstructed: np.ndarray, ground_truth: np.ndarray) -> float:
    """Peak signal-to-noise ratio in dB.

    Both inputs are normalized to [0, 1] before MSE is computed.
    Returns 100 dB for identical (or near-identical) inputs.
    """
    a = _normalize(reconstructed)
    b = _normalize(ground_truth)
    mse = float(np.mean((a - b) ** 2))
    if mse < _PSNR_MIN_MSE:
        return _PSNR_MAX_DB
    return float(20.0 * np.log10(1.0 / np.sqrt(mse)))


def ssim(reconstructed: np.ndarray, ground_truth: np.ndarray) -> float:
    """Structural similarity index in [-1, 1].

    Both inputs are normalized to [0, 1] before comparison.
    """
    a = _normalize(reconstructed)
    b = _normalize(ground_truth)
    return float(structural_similarity(a, b, data_range=1.0))
