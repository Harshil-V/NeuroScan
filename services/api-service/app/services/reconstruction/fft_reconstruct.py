"""Inverse FFT reconstruction.

Takes complex k-space, returns a uint16 magnitude image normalized to [0, 4095].
"""

from __future__ import annotations

import numpy as np


def reconstruct(kspace: np.ndarray) -> np.ndarray:
    """Run inverse FFT on shifted k-space and return a uint16 magnitude image.

    Steps:
      1. ifftshift to undo any forward shift
      2. ifft2 → complex image
      3. magnitude (np.abs)
      4. normalize to [0, 4095] uint16 (12-bit MR-style range)
    """
    shifted = np.fft.ifftshift(kspace)
    complex_image = np.fft.ifft2(shifted)
    magnitude = np.abs(complex_image).astype(np.float32)
    peak = float(magnitude.max())
    if peak > 0:
        magnitude = magnitude / peak * 4095.0
    return magnitude.astype(np.uint16)
