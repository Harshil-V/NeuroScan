import numpy as np

from app.dicom.window_level import apply_window_level


def test_apply_window_level_returns_uint8():
    arr = np.array([[0, 100, 200], [300, 400, 500]], dtype=np.int16)
    out = apply_window_level(arr, level=250, window=200)
    assert out.dtype == np.uint8


def test_apply_window_level_clips_low():
    arr = np.array([[-100, 0, 50]], dtype=np.int16)
    out = apply_window_level(arr, level=100, window=100)
    assert out[0, 0] == 0
    assert out[0, 1] == 0


def test_apply_window_level_clips_high():
    arr = np.array([[0, 200, 500]], dtype=np.int16)
    out = apply_window_level(arr, level=100, window=100)
    assert out[0, 2] == 255


def test_apply_window_level_centers_at_level():
    arr = np.array([[100]], dtype=np.int16)
    out = apply_window_level(arr, level=100, window=100)
    # value == level → midpoint of [0, 255]
    assert 120 <= out[0, 0] <= 135


def test_apply_window_level_zero_window_is_safe():
    arr = np.array([[100, 200]], dtype=np.int16)
    out = apply_window_level(arr, level=150, window=0)
    assert out.dtype == np.uint8
    assert out.shape == (1, 2)


def test_apply_window_level_preserves_shape_2d():
    arr = np.zeros((64, 64), dtype=np.int16)
    out = apply_window_level(arr, level=0, window=100)
    assert out.shape == (64, 64)


def test_apply_window_level_preserves_shape_3d():
    arr = np.zeros((10, 64, 64), dtype=np.int16)
    out = apply_window_level(arr, level=0, window=100)
    assert out.shape == (10, 64, 64)
