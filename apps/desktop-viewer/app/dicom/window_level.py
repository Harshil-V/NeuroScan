"""Window/level math for DICOM image display.

Linear LUT mapping a center/width range to uint8 [0, 255].
"""

from __future__ import annotations

import numpy as np


def apply_window_level(arr: np.ndarray, level: float, window: float) -> np.ndarray:
    """Apply DICOM-style window/level mapping.

    Args:
        arr: input pixel array (any numeric dtype, any shape).
        level: window center (the pixel value mapped to mid-gray).
        window: window width.

    Returns:
        uint8 array with the same shape as arr.
    """
    safe_window = max(float(window), 1.0)
    low = float(level) - safe_window / 2
    high = float(level) + safe_window / 2
    clipped = np.clip(arr.astype(np.float32), low, high)
    return ((clipped - low) / safe_window * 255).astype(np.uint8)
