import numpy as np

from app.services.reconstruction.fft_reconstruct import reconstruct


def _make_image(shape=(64, 64), seed=0) -> np.ndarray:
    """Build a smooth test image (gaussian blob)."""
    h, w = shape
    rng = np.random.default_rng(seed)
    yy, xx = np.meshgrid(np.linspace(-1, 1, h), np.linspace(-1, 1, w), indexing="ij")
    blob = np.exp(-(xx**2 + yy**2) * 4)
    noise = rng.standard_normal(shape) * 0.01
    return (blob + noise).astype(np.float32)


def _forward_fft(image: np.ndarray) -> np.ndarray:
    """Inline forward FFT used to build test k-space (not the production module)."""
    return np.fft.fftshift(np.fft.fft2(image)).astype(np.complex64)


def test_reconstruct_returns_uint16():
    kspace = _forward_fft(_make_image()).astype(np.complex64)
    out = reconstruct(kspace)
    assert out.dtype == np.uint16


def test_reconstruct_preserves_shape():
    kspace = _forward_fft(_make_image((128, 128)))
    out = reconstruct(kspace)
    assert out.shape == (128, 128)


def test_reconstruct_round_trip_psnr_high():
    """forward → reconstruct → compare. Should be near-lossless."""
    image = _make_image()
    kspace = _forward_fft(image)
    recon = reconstruct(kspace)

    # Normalize both to [0, 1] for fair comparison
    recon_norm = recon.astype(np.float32) / max(recon.max(), 1)
    image_norm = image - image.min()
    image_norm = image_norm / max(image_norm.max(), 1e-9)

    mse = float(np.mean((recon_norm - image_norm) ** 2))
    psnr = 20 * np.log10(1.0 / max(np.sqrt(mse), 1e-10))
    assert psnr > 30, f"Expected near-lossless round-trip, got PSNR={psnr:.1f} dB"


def test_reconstruct_handles_complex128():
    kspace = _forward_fft(_make_image()).astype(np.complex128)
    out = reconstruct(kspace)
    assert out.shape == kspace.shape
    assert out.dtype == np.uint16


def test_reconstruct_zero_kspace_returns_zero_image():
    kspace = np.zeros((32, 32), dtype=np.complex64)
    out = reconstruct(kspace)
    assert out.shape == (32, 32)
    assert out.max() == 0
    assert not np.any(np.isnan(out))


def test_reconstruct_normalizes_to_4095_max():
    image = _make_image() * 10000  # arbitrary large scale
    kspace = _forward_fft(image)
    out = reconstruct(kspace)
    assert out.max() <= 4095
