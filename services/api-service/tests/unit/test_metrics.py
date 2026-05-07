import numpy as np

from app.services.reconstruction.metrics import psnr, ssim


def test_psnr_identical_arrays_returns_max():
    a = np.random.default_rng(0).integers(0, 4095, (64, 64), dtype=np.uint16)
    result = psnr(a, a)
    assert result >= 100.0


def test_psnr_different_arrays_finite_and_positive():
    rng = np.random.default_rng(0)
    a = rng.integers(0, 4095, (64, 64), dtype=np.uint16).astype(np.float32)
    b = (a + rng.standard_normal(a.shape) * 100).clip(0, 4095).astype(np.float32)
    result = psnr(a, b)
    assert np.isfinite(result)
    assert 10 < result < 100


def test_psnr_normalizes_inputs_so_scale_doesnt_matter():
    base = np.random.default_rng(0).integers(0, 4095, (32, 32)).astype(np.float32)
    noisy = base + np.random.default_rng(1).standard_normal(base.shape) * 50
    p1 = psnr(base, noisy)
    p2 = psnr(base * 2, noisy * 2)
    # Should be close (within rounding)
    assert abs(p1 - p2) < 0.5


def test_ssim_identical_arrays_returns_one():
    a = np.random.default_rng(0).integers(0, 4095, (64, 64), dtype=np.uint16).astype(np.float32)
    result = ssim(a, a)
    assert result == 1.0 or abs(result - 1.0) < 1e-6


def test_ssim_decreases_with_noise():
    rng = np.random.default_rng(0)
    base = rng.standard_normal((64, 64)).astype(np.float32)
    light_noise = base + rng.standard_normal(base.shape) * 0.01
    heavy_noise = base + rng.standard_normal(base.shape) * 1.0
    s_light = ssim(base, light_noise)
    s_heavy = ssim(base, heavy_noise)
    assert s_light > s_heavy
    assert -1.0 <= s_heavy <= 1.0
    assert -1.0 <= s_light <= 1.0


def test_ssim_normalizes_inputs():
    base = np.random.default_rng(0).standard_normal((32, 32)).astype(np.float32)
    s1 = ssim(base, base * 0.5)  # not equal in absolute terms
    s2 = ssim(base * 2, base)  # same relative relationship
    # both should be high (the relative shape is preserved)
    assert s1 > 0.5
    assert s2 > 0.5
