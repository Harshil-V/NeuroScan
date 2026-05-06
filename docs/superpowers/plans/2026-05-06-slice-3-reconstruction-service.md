# Slice 3 — Reconstruction Service Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an MRI reconstruction pipeline to NeuroScan: accept k-space data (.npy/.npz/.h5) in api-service, run inverse FFT in a FastAPI BackgroundTask, generate a DICOM, store it in Orthanc, compute PSNR/SSIM against ground truth when available, and surface jobs + side-by-side previews on a new `/reconstruction` page in the React app.

**Architecture:** New `services/reconstruction/` package inside api-service (six pure-logic modules). New `reconstruction_jobs` table (alembic 002). New `/api/reconstruction/jobs` POST + GET endpoints. BackgroundTasks runs the job out-of-band; UI polls. Forward-FFT helper builds synthetic k-space `.npz` from existing DICOMs with embedded ground truth — that's how PSNR/SSIM are honest. Web-only UI; desktop viewer untouched.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2, Alembic, pydicom, numpy, scipy (already in pydicom's tree), h5py (new), scikit-image (new), httpx, pytest, respx, testcontainers, ruff. React 18 + TS + Vite + TanStack Query (existing).

**Spec:** [`docs/superpowers/specs/2026-05-06-slice-3-reconstruction-service-design.md`](../specs/2026-05-06-slice-3-reconstruction-service-design.md)

**Branch:** `slice-3-reconstruction-service` (off `main`, with Slice 1 + Slice 2 already merged)

**Commit policy (from user):** Small, incremental, logically-isolated commits. Each task in this plan produces 1–2 commits. Never combine unrelated changes. Never amend.

**TDD scope:** Pure-logic modules in Phase B are written test-first. The model + migration in Phase C is verified by Alembic + manual DDL inspection (no model unit tests — Slice 1's pattern). Routes are smoke-tested by the integration test in Phase F. The React UI in Phase G is verified by typecheck + build + manual smoke (no component unit tests, per the existing project pattern).

---

## File structure

Created in this slice:

```text
services/api-service/
├── app/
│   ├── services/
│   │   └── reconstruction/                            # NEW package
│   │       ├── __init__.py
│   │       ├── kspace_loader.py
│   │       ├── fft_reconstruct.py
│   │       ├── forward_fft.py
│   │       ├── metrics.py
│   │       ├── dicom_writer.py
│   │       └── job_runner.py
│   ├── models/
│   │   └── reconstruction.py                          # NEW
│   ├── schemas/
│   │   └── reconstruction.py                          # NEW
│   ├── routes/
│   │   └── reconstruction.py                          # NEW
│   └── alembic/versions/
│       └── 002_reconstruction_jobs.py                 # NEW
├── tests/
│   ├── unit/
│   │   ├── test_kspace_loader.py                      # NEW
│   │   ├── test_fft_reconstruct.py                    # NEW
│   │   ├── test_forward_fft.py                        # NEW
│   │   ├── test_metrics.py                            # NEW
│   │   └── test_dicom_writer.py                       # NEW
│   └── integration/
│       └── test_reconstruction_flow.py                # NEW

apps/web-viewer/src/
├── api/reconstruction.ts                              # NEW
├── pages/ReconstructionPage.tsx                       # NEW
└── components/
    ├── KspaceUploadDropzone.tsx                       # NEW
    ├── ReconstructionJobTable.tsx                     # NEW
    └── SideBySidePreview.tsx                          # NEW

scripts/generate-synthetic-kspace.py                   # NEW
```

Modified in this slice:

```text
services/api-service/pyproject.toml                    # add h5py, scikit-image
services/api-service/uv.lock                           # regenerated
services/api-service/app/main.py                       # include reconstruction router
services/api-service/app/models/__init__.py            # export ReconstructionJob
apps/web-viewer/src/types/index.ts                     # add ReconstructionJob types
apps/web-viewer/src/routes.tsx                         # add /reconstruction route
apps/web-viewer/src/components/Nav.tsx                 # add Reconstruction link
docs/qa-validation-plan.md                             # add TC-08
docs/status.md                                         # mark slice 3 done at end
docs/roadmap.md                                        # mark slice 3 done at end
README.md                                              # quickstart mention
```

Untouched: `apps/desktop-viewer/`, `infra/`, `tests/e2e/`.

---

## Phase A — Tooling

### Task A1: Add `h5py` and `scikit-image` to api-service pyproject

**Files:**
- Modify: `services/api-service/pyproject.toml`
- Modify: `services/api-service/uv.lock` (regenerated)

- [ ] **Step 1: Update pyproject dependencies**

In `services/api-service/pyproject.toml`, change the `[project].dependencies` array from:

```toml
dependencies = [
    "fastapi>=0.115",
    "uvicorn[standard]>=0.32",
    "pydantic>=2.9",
    "pydantic-settings>=2.6",
    "sqlalchemy>=2.0",
    "alembic>=1.13",
    "psycopg[binary]>=3.2",
    "httpx>=0.27",
    "pydicom>=3.0",
    "python-multipart>=0.0.12",
]
```

to:

```toml
dependencies = [
    "fastapi>=0.115",
    "uvicorn[standard]>=0.32",
    "pydantic>=2.9",
    "pydantic-settings>=2.6",
    "sqlalchemy>=2.0",
    "alembic>=1.13",
    "psycopg[binary]>=3.2",
    "httpx>=0.27",
    "pydicom>=3.0",
    "python-multipart>=0.0.12",
    "h5py>=3.12",
    "scikit-image>=0.24",
]
```

- [ ] **Step 2: Re-lock**

```bash
cd services/api-service
uv sync
```

Expected: `uv.lock` updated, `.venv/` updated. h5py + scikit-image wheels download (~30 MB total).

- [ ] **Step 3: Smoke verify imports**

```bash
cd services/api-service
uv run python -c "import h5py; from skimage.metrics import structural_similarity; print('OK', h5py.__version__)"
```

Expected: `OK 3.x.x`.

- [ ] **Step 4: Run existing tests to confirm no regression**

```bash
cd services/api-service
uv run pytest tests/unit/ -q
```

Expected: 24 passed (Slice 1's count).

- [ ] **Step 5: Commit**

```bash
cd /Users/harshilvyas/Documents/Github\ Repos/NeuroScan
git add services/api-service/pyproject.toml services/api-service/uv.lock
git commit -m "feat(slice-3): add h5py and scikit-image deps to api-service"
```

---

## Phase B — TDD pure-logic modules

### Task B1: TDD `kspace_loader.py`

**Files:**
- Create: `services/api-service/app/services/reconstruction/__init__.py`
- Create: `services/api-service/app/services/reconstruction/kspace_loader.py`
- Create: `services/api-service/tests/unit/test_kspace_loader.py`

- [ ] **Step 1: Write `app/services/reconstruction/__init__.py`** — empty file.

- [ ] **Step 2: Write the failing tests**

`services/api-service/tests/unit/test_kspace_loader.py`:

```python
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
```

- [ ] **Step 3: Run, expect FAIL (ImportError)**

```bash
cd services/api-service
uv run pytest tests/unit/test_kspace_loader.py -v
```

Expected: ImportError on `app.services.reconstruction.kspace_loader`.

- [ ] **Step 4: Write `app/services/reconstruction/kspace_loader.py`**

```python
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
```

- [ ] **Step 5: Run, expect PASS**

```bash
uv run pytest tests/unit/test_kspace_loader.py -v
```

Expected: 10 passed.

- [ ] **Step 6: Commit**

```bash
cd /Users/harshilvyas/Documents/Github\ Repos/NeuroScan
git add services/api-service/app/services/reconstruction/__init__.py services/api-service/app/services/reconstruction/kspace_loader.py services/api-service/tests/unit/test_kspace_loader.py
git commit -m "feat(slice-3): add k-space loader for .npy/.npz/.h5 inputs"
```

---

### Task B2: TDD `fft_reconstruct.py`

**Files:**
- Create: `services/api-service/app/services/reconstruction/fft_reconstruct.py`
- Create: `services/api-service/tests/unit/test_fft_reconstruct.py`

- [ ] **Step 1: Write the failing tests**

`services/api-service/tests/unit/test_fft_reconstruct.py`:

```python
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
```

- [ ] **Step 2: Run, expect FAIL**

```bash
uv run pytest tests/unit/test_fft_reconstruct.py -v
```

- [ ] **Step 3: Write `app/services/reconstruction/fft_reconstruct.py`**

```python
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
```

- [ ] **Step 4: Run, expect PASS**

```bash
uv run pytest tests/unit/test_fft_reconstruct.py -v
```

Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
cd /Users/harshilvyas/Documents/Github\ Repos/NeuroScan
git add services/api-service/app/services/reconstruction/fft_reconstruct.py services/api-service/tests/unit/test_fft_reconstruct.py
git commit -m "feat(slice-3): add inverse FFT reconstruction (k-space → uint16 image)"
```

---

### Task B3: TDD `forward_fft.py`

**Files:**
- Create: `services/api-service/app/services/reconstruction/forward_fft.py`
- Create: `services/api-service/tests/unit/test_forward_fft.py`

- [ ] **Step 1: Write the failing tests**

`services/api-service/tests/unit/test_forward_fft.py`:

```python
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
```

- [ ] **Step 2: Run, expect FAIL**

```bash
uv run pytest tests/unit/test_forward_fft.py -v
```

- [ ] **Step 3: Write `app/services/reconstruction/forward_fft.py`**

```python
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
```

- [ ] **Step 4: Run, expect PASS**

```bash
uv run pytest tests/unit/test_forward_fft.py -v
```

Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
cd /Users/harshilvyas/Documents/Github\ Repos/NeuroScan
git add services/api-service/app/services/reconstruction/forward_fft.py services/api-service/tests/unit/test_forward_fft.py
git commit -m "feat(slice-3): add forward FFT (DICOM → synthetic k-space + ground truth)"
```

---

### Task B4: TDD `metrics.py`

**Files:**
- Create: `services/api-service/app/services/reconstruction/metrics.py`
- Create: `services/api-service/tests/unit/test_metrics.py`

- [ ] **Step 1: Write the failing tests**

`services/api-service/tests/unit/test_metrics.py`:

```python
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
```

- [ ] **Step 2: Run, expect FAIL**

```bash
uv run pytest tests/unit/test_metrics.py -v
```

- [ ] **Step 3: Write `app/services/reconstruction/metrics.py`**

```python
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
```

- [ ] **Step 4: Run, expect PASS**

```bash
uv run pytest tests/unit/test_metrics.py -v
```

Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
cd /Users/harshilvyas/Documents/Github\ Repos/NeuroScan
git add services/api-service/app/services/reconstruction/metrics.py services/api-service/tests/unit/test_metrics.py
git commit -m "feat(slice-3): add PSNR and SSIM metrics with input normalization"
```

---

### Task B5: TDD `dicom_writer.py`

**Files:**
- Create: `services/api-service/app/services/reconstruction/dicom_writer.py`
- Create: `services/api-service/tests/unit/test_dicom_writer.py`

- [ ] **Step 1: Write the failing tests**

`services/api-service/tests/unit/test_dicom_writer.py`:

```python
from io import BytesIO

import numpy as np
import pydicom

from app.services.reconstruction.dicom_writer import image_to_mr_dicom


def test_image_to_mr_dicom_returns_parseable_bytes():
    image = np.random.default_rng(0).integers(0, 4095, (64, 64), dtype=np.uint16)
    result = image_to_mr_dicom(image, source_name="test.npy")
    assert len(result.dicom_bytes) > 0
    ds = pydicom.dcmread(BytesIO(result.dicom_bytes))
    assert ds.Modality == "MR"
    assert int(ds.Rows) == 64
    assert int(ds.Columns) == 64


def test_image_to_mr_dicom_required_tags_present():
    image = np.zeros((32, 32), dtype=np.uint16)
    result = image_to_mr_dicom(image, source_name="x.npy")
    ds = pydicom.dcmread(BytesIO(result.dicom_bytes))
    assert ds.BitsAllocated == 16
    assert ds.BitsStored == 16
    assert ds.PhotometricInterpretation == "MONOCHROME2"
    assert ds.SamplesPerPixel == 1
    assert ds.PixelRepresentation == 0
    # UIDs all match what we returned
    assert str(ds.StudyInstanceUID) == result.study_instance_uid
    assert str(ds.SeriesInstanceUID) == result.series_instance_uid
    assert str(ds.SOPInstanceUID) == result.sop_instance_uid


def test_image_to_mr_dicom_uids_are_fresh_each_call():
    image = np.zeros((16, 16), dtype=np.uint16)
    a = image_to_mr_dicom(image, source_name="a.npy")
    b = image_to_mr_dicom(image, source_name="b.npy")
    assert a.study_instance_uid != b.study_instance_uid
    assert a.series_instance_uid != b.series_instance_uid
    assert a.sop_instance_uid != b.sop_instance_uid


def test_image_to_mr_dicom_pixel_array_round_trips():
    image = np.arange(0, 1024, dtype=np.uint16).reshape(32, 32)
    result = image_to_mr_dicom(image, source_name="x.npy")
    ds = pydicom.dcmread(BytesIO(result.dicom_bytes))
    np.testing.assert_array_equal(ds.pixel_array, image)


def test_image_to_mr_dicom_uses_provenance_metadata():
    image = np.zeros((16, 16), dtype=np.uint16)
    result = image_to_mr_dicom(
        image,
        source_name="brain_kspace.npz",
        patient_id="MY-ID",
        study_description="Custom Study",
        series_description="Custom Series",
    )
    ds = pydicom.dcmread(BytesIO(result.dicom_bytes))
    assert ds.PatientID == "MY-ID"
    assert ds.StudyDescription == "Custom Study"
    assert ds.SeriesDescription == "Custom Series"
```

- [ ] **Step 2: Run, expect FAIL**

```bash
uv run pytest tests/unit/test_dicom_writer.py -v
```

- [ ] **Step 3: Write `app/services/reconstruction/dicom_writer.py`**

```python
"""Build a valid MR DICOM file from a uint16 numpy image.

Generates fresh Patient/Study/Series/SOP UIDs for each call. Stamps
metadata that identifies the image as a NeuroScan reconstruction output
(distinguishable from clinical data).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from io import BytesIO

import numpy as np
import pydicom
from pydicom.dataset import FileDataset, FileMetaDataset
from pydicom.uid import ExplicitVRLittleEndian, generate_uid


@dataclass(frozen=True)
class DicomWriteResult:
    dicom_bytes: bytes
    study_instance_uid: str
    series_instance_uid: str
    sop_instance_uid: str


def image_to_mr_dicom(
    image: np.ndarray,
    *,
    source_name: str,
    patient_id: str = "RECON-001",
    study_description: str = "MRI Reconstruction",
    series_description: str = "Reconstructed",
) -> DicomWriteResult:
    """Build an MR DICOM from a uint16 image.

    Args:
        image: uint16 array, shape (rows, cols).
        source_name: filename of the source k-space (recorded in ImageComments).
        patient_id, study_description, series_description: provenance metadata.

    Returns:
        DicomWriteResult with the bytes plus all generated UIDs.
    """
    if image.dtype != np.uint16:
        image = image.astype(np.uint16)
    rows, cols = image.shape

    study_uid = generate_uid()
    series_uid = generate_uid()
    sop_uid = generate_uid()

    file_meta = FileMetaDataset()
    file_meta.MediaStorageSOPClassUID = pydicom.uid.MRImageStorage
    file_meta.MediaStorageSOPInstanceUID = sop_uid
    file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
    file_meta.ImplementationClassUID = generate_uid()

    ds = FileDataset(
        f"{source_name}.dcm", {}, file_meta=file_meta, preamble=b"\0" * 128
    )
    ds.SOPClassUID = pydicom.uid.MRImageStorage
    ds.SOPInstanceUID = sop_uid
    ds.StudyInstanceUID = study_uid
    ds.SeriesInstanceUID = series_uid
    ds.PatientID = patient_id
    ds.PatientName = "Reconstruction^Output"
    ds.Modality = "MR"
    now = datetime.now()
    ds.StudyDate = now.strftime("%Y%m%d")
    ds.StudyTime = now.strftime("%H%M%S")
    ds.StudyDescription = study_description
    ds.SeriesDescription = series_description
    ds.SeriesNumber = 1
    ds.InstanceNumber = 1
    ds.ImageComments = f"Reconstructed from {source_name}"
    ds.Rows = rows
    ds.Columns = cols
    ds.BitsAllocated = 16
    ds.BitsStored = 16
    ds.HighBit = 15
    ds.PixelRepresentation = 0
    ds.SamplesPerPixel = 1
    ds.PhotometricInterpretation = "MONOCHROME2"
    ds.PixelData = image.tobytes()
    ds.is_little_endian = True
    ds.is_implicit_VR = False

    buf = BytesIO()
    ds.save_as(buf, write_like_original=False)
    return DicomWriteResult(
        dicom_bytes=buf.getvalue(),
        study_instance_uid=study_uid,
        series_instance_uid=series_uid,
        sop_instance_uid=sop_uid,
    )
```

- [ ] **Step 4: Run, expect PASS**

```bash
uv run pytest tests/unit/test_dicom_writer.py -v
```

Expected: 5 passed.

- [ ] **Step 5: Run all unit tests so far together**

```bash
uv run pytest tests/unit/ -q
```

Expected: 24 (Slice 1) + 10 + 6 + 5 + 6 + 5 = **56 passed**.

- [ ] **Step 6: Commit**

```bash
cd /Users/harshilvyas/Documents/Github\ Repos/NeuroScan
git add services/api-service/app/services/reconstruction/dicom_writer.py services/api-service/tests/unit/test_dicom_writer.py
git commit -m "feat(slice-3): add DICOM writer (numpy image → MR DICOM bytes)"
```

---

## Phase C — Data model + migration

### Task C1: `ReconstructionJob` model + Alembic migration 002

**Files:**
- Create: `services/api-service/app/models/reconstruction.py`
- Modify: `services/api-service/app/models/__init__.py`
- Create: `services/api-service/app/alembic/versions/002_reconstruction_jobs.py`

- [ ] **Step 1: Write `app/models/reconstruction.py`**

```python
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    BigInteger,
    DateTime,
    Double,
    Index,
    Integer,
    String,
    Text,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class ReconstructionJob(Base):
    __tablename__ = "reconstruction_jobs"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer(), "sqlite"),
        primary_key=True,
        autoincrement=True,
    )
    job_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), unique=True, nullable=False, default=uuid.uuid4
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    input_file_name: Mapped[str] = mapped_column(String(256), nullable=False)
    input_format: Mapped[str] = mapped_column(String(8), nullable=False)
    input_shape: Mapped[str | None] = mapped_column(String(64), nullable=True)
    output_dicom_uid: Mapped[str | None] = mapped_column(String(128), nullable=True)
    output_orthanc_instance_id: Mapped[str | None] = mapped_column(
        String(128), nullable=True
    )
    psnr_db: Mapped[float | None] = mapped_column(Double, nullable=True)
    ssim: Mapped[float | None] = mapped_column(Double, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        Index("idx_recon_created_at", created_at.desc()),
        Index("idx_recon_status", status),
    )
```

- [ ] **Step 2: Update `app/models/__init__.py`**

Replace the file's contents with:

```python
from app.models.audit import AuditEvent
from app.models.reconstruction import ReconstructionJob

__all__ = ["AuditEvent", "ReconstructionJob"]
```

- [ ] **Step 3: Generate the migration**

```bash
export PATH="$HOME/.orbstack/bin:$PATH"
cd infra
docker compose up -d postgres
# wait for postgres healthy
for i in $(seq 1 20); do
  if docker compose ps --format json postgres | grep -q '"Health":"healthy"'; then break; fi
  sleep 2
done
cd ../services/api-service
DATABASE_URL=postgresql+psycopg://neuroscan:neuroscan@localhost:5432/neuroscan \
  uv run alembic upgrade head  # ensure 001 is applied
DATABASE_URL=postgresql+psycopg://neuroscan:neuroscan@localhost:5432/neuroscan \
  uv run alembic revision --autogenerate -m "reconstruction_jobs"
```

Expected: a new file `app/alembic/versions/<hash>_reconstruction_jobs.py` is created.

Rename it to a stable filename:

```bash
mv app/alembic/versions/*_reconstruction_jobs.py app/alembic/versions/002_reconstruction_jobs.py
```

Open the file and edit:
- Set `revision: str = "002"`
- Set `down_revision: str | None = "001"`

The body should call `op.create_table('reconstruction_jobs', ...)` with all 14 columns and `op.create_index` for both indexes. Inspect to confirm.

- [ ] **Step 4: Apply and verify**

```bash
DATABASE_URL=postgresql+psycopg://neuroscan:neuroscan@localhost:5432/neuroscan \
  uv run alembic upgrade head
```

Expected: log line `Running upgrade 001 -> 002, reconstruction_jobs`.

Verify the table:

```bash
docker compose -f /Users/harshilvyas/Documents/Github\ Repos/NeuroScan/infra/docker-compose.yml exec -T postgres psql -U neuroscan -c "\d reconstruction_jobs"
```

Expected: 14 columns + 2 indexes (`idx_recon_created_at`, `idx_recon_status`) + the unique on `job_id`.

- [ ] **Step 5: Tear down**

```bash
cd /Users/harshilvyas/Documents/Github\ Repos/NeuroScan/infra
docker compose down  # NOT -v; preserve volumes
```

- [ ] **Step 6: Run all unit tests to confirm SQLite still works**

The model uses `BigInteger().with_variant(Integer(), "sqlite")` so unit tests using in-memory SQLite still work for both AuditEvent and ReconstructionJob:

```bash
cd services/api-service
uv run pytest tests/unit/ -q
```

Expected: 56 passed.

- [ ] **Step 7: Commit**

```bash
cd /Users/harshilvyas/Documents/Github\ Repos/NeuroScan
git add services/api-service/app/models/ services/api-service/app/alembic/versions/002_reconstruction_jobs.py
git commit -m "feat(slice-3): add ReconstructionJob model and alembic migration 002"
```

---

## Phase D — Schemas + job runner

### Task D1: `schemas/reconstruction.py`

**Files:**
- Create: `services/api-service/app/schemas/reconstruction.py`

- [ ] **Step 1: Write the schemas**

```python
import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


class ReconstructionJobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    job_id: uuid.UUID
    status: Literal["queued", "running", "completed", "failed"]
    input_file_name: str
    input_format: Literal["npy", "npz", "h5"]
    input_shape: str | None
    output_dicom_uid: str | None
    output_orthanc_instance_id: str | None
    psnr_db: float | None
    ssim: float | None
    duration_ms: int | None
    error_message: str | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None


class ReconstructionJobCreated(BaseModel):
    job_id: uuid.UUID
    status: Literal["queued"]
    input_file_name: str
    input_format: Literal["npy", "npz", "h5"]
    created_at: datetime


class ReconstructionJobList(BaseModel):
    items: list[ReconstructionJobOut]
    total: int
    limit: int
    offset: int
```

- [ ] **Step 2: Smoke verify import**

```bash
cd services/api-service
uv run python -c "from app.schemas.reconstruction import ReconstructionJobOut, ReconstructionJobList, ReconstructionJobCreated; print('OK')"
```

Expected: `OK`.

- [ ] **Step 3: Commit**

```bash
cd /Users/harshilvyas/Documents/Github\ Repos/NeuroScan
git add services/api-service/app/schemas/reconstruction.py
git commit -m "feat(slice-3): add pydantic DTOs for reconstruction jobs"
```

---

### Task D2: `services/reconstruction/job_runner.py`

**Files:**
- Create: `services/api-service/app/services/reconstruction/job_runner.py`

The runner is verified end-to-end by Phase F's integration test — no new unit test for it (the constituent modules already have unit tests, and the runner is glue code best validated against real Postgres + Orthanc).

- [ ] **Step 1: Write the runner**

```python
"""The FastAPI BackgroundTask body for reconstruction jobs.

This is a sync function on purpose: FastAPI BackgroundTasks runs sync
callables in its threadpool, which is the right execution model for
CPU-bound FFT work. If declared `async def`, it would block the event loop.
"""

from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import httpx
from sqlalchemy import update
from sqlalchemy.orm import Session, sessionmaker

from app.clients.orthanc import OrthancError
from app.config import Settings
from app.db import get_engine
from app.models.reconstruction import ReconstructionJob
from app.services.reconstruction.dicom_writer import image_to_mr_dicom
from app.services.reconstruction.fft_reconstruct import reconstruct
from app.services.reconstruction.kspace_loader import (
    InvalidKspaceError,
    UnsupportedShapeError,
    load,
)
from app.services.reconstruction.metrics import psnr, ssim


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _set_status(
    session: Session,
    job_id: uuid.UUID,
    **fields,
) -> None:
    session.execute(
        update(ReconstructionJob)
        .where(ReconstructionJob.job_id == job_id)
        .values(**fields)
    )
    session.commit()


def run_job(job_id: uuid.UUID, tempfile_path: Path, settings: Settings) -> None:
    """Run reconstruction for one job. Updates the DB row in place.

    Always sets a terminal status. Always deletes the tempfile.
    """
    engine = get_engine()
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    started = time.monotonic()

    try:
        with SessionLocal() as session:
            _set_status(
                session,
                job_id,
                status="running",
                started_at=_now(),
            )

        kspace, ground_truth = load(tempfile_path)
        recon_image = reconstruct(kspace)

        psnr_value = ssim_value = None
        if ground_truth is not None:
            psnr_value = psnr(recon_image, ground_truth)
            ssim_value = ssim(recon_image, ground_truth)

        write_result = image_to_mr_dicom(
            recon_image,
            source_name=tempfile_path.name,
        )

        # Use a sync httpx call to upload to Orthanc.
        # OrthancClient (in app/clients/orthanc.py) is async — fine for FastAPI
        # request handlers, but in this sync BackgroundTask body we want a sync
        # call that runs in the threadpool without spinning up an event loop.
        orthanc_instance_id = _upload_sync(settings, write_result.dicom_bytes)

        duration_ms = int((time.monotonic() - started) * 1000)

        with SessionLocal() as session:
            _set_status(
                session,
                job_id,
                status="completed",
                completed_at=_now(),
                output_dicom_uid=write_result.study_instance_uid,
                output_orthanc_instance_id=orthanc_instance_id,
                psnr_db=psnr_value,
                ssim=ssim_value,
                duration_ms=duration_ms,
                input_shape=str(kspace.shape),
            )

    except (InvalidKspaceError, UnsupportedShapeError) as exc:
        with SessionLocal() as session:
            _set_status(
                session,
                job_id,
                status="failed",
                completed_at=_now(),
                error_message=f"invalid_kspace: {exc}",
                duration_ms=int((time.monotonic() - started) * 1000),
            )
    except OrthancError as exc:
        with SessionLocal() as session:
            _set_status(
                session,
                job_id,
                status="failed",
                completed_at=_now(),
                error_message=f"orthanc_rejected: {exc}",
                duration_ms=int((time.monotonic() - started) * 1000),
            )
    except Exception as exc:  # noqa: BLE001 — defensive
        with SessionLocal() as session:
            _set_status(
                session,
                job_id,
                status="failed",
                completed_at=_now(),
                error_message=f"reconstruction_failed: {exc}",
                duration_ms=int((time.monotonic() - started) * 1000),
            )
    finally:
        try:
            tempfile_path.unlink(missing_ok=True)
        except OSError:
            pass


def _upload_sync(settings: Settings, dicom_bytes: bytes) -> str:
    """Sync-only Orthanc instance upload (parallel to the async OrthancClient).

    The async client is fine for FastAPI request handlers, but here we want a
    plain sync call that runs in the BackgroundTask threadpool.
    """
    url = f"{settings.orthanc_url.rstrip('/')}/instances"
    auth = (settings.orthanc_user, settings.orthanc_password)
    with httpx.Client(timeout=30.0, auth=auth) as client:
        response = client.post(
            url,
            content=dicom_bytes,
            headers={"Content-Type": "application/dicom"},
        )
    if response.status_code >= 400:
        raise OrthancError(
            f"Orthanc rejected upload: {response.status_code} {response.text}"
        )
    body = response.json()
    instance_id = body.get("ID")
    if not instance_id:
        raise OrthancError(f"Orthanc upload missing ID in response: {body}")
    return instance_id
```

- [ ] **Step 2: Smoke verify import**

```bash
cd services/api-service
uv run python -c "from app.services.reconstruction.job_runner import run_job; print('OK')"
```

Expected: `OK`.

- [ ] **Step 3: Run all unit tests to confirm no regression**

```bash
uv run pytest tests/unit/ -q
```

Expected: 56 passed.

- [ ] **Step 4: Run lint**

```bash
uv run ruff check . && uv run ruff format --check .
```

Expected: clean. If formatting fails, run `uv run ruff format .` and include any reformatting in this commit.

- [ ] **Step 5: Commit**

```bash
cd /Users/harshilvyas/Documents/Github\ Repos/NeuroScan
git add services/api-service/app/services/reconstruction/job_runner.py
git commit -m "feat(slice-3): add reconstruction job runner (sync, threadpool-friendly)"
```

---

## Phase E — Routes + main wiring

### Task E1: `routes/reconstruction.py` + register in `main.py`

**Files:**
- Create: `services/api-service/app/routes/reconstruction.py`
- Modify: `services/api-service/app/main.py`

- [ ] **Step 1: Write `app/routes/reconstruction.py`**

```python
"""Reconstruction job endpoints: POST to submit, GET to inspect."""

from __future__ import annotations

import tempfile
import uuid
from pathlib import Path

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db import get_session
from app.models.reconstruction import ReconstructionJob
from app.schemas.reconstruction import (
    ReconstructionJobCreated,
    ReconstructionJobList,
    ReconstructionJobOut,
)
from app.services.reconstruction.job_runner import run_job
from app.services.reconstruction.kspace_loader import (
    InvalidKspaceError,
    UnsupportedShapeError,
    load,
)

router = APIRouter(prefix="/api/reconstruction", tags=["reconstruction"])

ALLOWED_EXTENSIONS = {".npy", ".npz", ".h5", ".hdf5"}
MAX_BYTES = 100 * 1024 * 1024  # 100 MB
TEMPDIR_PREFIX = "neuroscan-recon-"


def _ext_to_format(ext: str) -> str:
    if ext == ".npy":
        return "npy"
    if ext == ".npz":
        return "npz"
    return "h5"  # .h5 or .hdf5


@router.post(
    "/jobs",
    response_model=ReconstructionJobCreated,
    status_code=status.HTTP_201_CREATED,
)
async def create_job(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> ReconstructionJobCreated:
    filename = file.filename or "upload.bin"
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail={
                "detail": f"unsupported file extension: {ext}",
                "code": "invalid_kspace",
            },
        )

    data = await file.read()
    if len(data) > MAX_BYTES:
        raise HTTPException(
            status_code=413,
            detail={
                "detail": f"file too large: {len(data)} bytes (max {MAX_BYTES})",
                "code": "file_too_large",
            },
        )

    # Save to a tempfile so the BackgroundTask can read it after the response
    tmpdir = Path(tempfile.mkdtemp(prefix=TEMPDIR_PREFIX))
    tempfile_path = tmpdir / filename
    tempfile_path.write_bytes(data)

    # Pre-validate so we can return 400 before queueing
    try:
        load(tempfile_path)
    except InvalidKspaceError as exc:
        tempfile_path.unlink(missing_ok=True)
        tmpdir.rmdir()
        raise HTTPException(
            status_code=400,
            detail={"detail": str(exc), "code": "invalid_kspace"},
        ) from exc
    except UnsupportedShapeError as exc:
        tempfile_path.unlink(missing_ok=True)
        tmpdir.rmdir()
        raise HTTPException(
            status_code=400,
            detail={"detail": str(exc), "code": "unsupported_shape"},
        ) from exc

    job = ReconstructionJob(
        job_id=uuid.uuid4(),
        status="queued",
        input_file_name=filename,
        input_format=_ext_to_format(ext),
    )
    session.add(job)
    session.commit()
    session.refresh(job)

    background_tasks.add_task(run_job, job.job_id, tempfile_path, settings)

    return ReconstructionJobCreated(
        job_id=job.job_id,
        status="queued",
        input_file_name=job.input_file_name,
        input_format=job.input_format,  # type: ignore[arg-type]
        created_at=job.created_at,
    )


@router.get("/jobs/{job_id}", response_model=ReconstructionJobOut)
async def get_job(
    job_id: uuid.UUID,
    session: Session = Depends(get_session),
) -> ReconstructionJobOut:
    job = session.scalar(
        select(ReconstructionJob).where(ReconstructionJob.job_id == job_id)
    )
    if job is None:
        raise HTTPException(status_code=404, detail="job_not_found")
    return ReconstructionJobOut.model_validate(job)


@router.get("/jobs", response_model=ReconstructionJobList)
async def list_jobs(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    status_filter: str | None = Query(None, alias="status"),
    session: Session = Depends(get_session),
) -> ReconstructionJobList:
    stmt = select(ReconstructionJob)
    count_stmt = select(func.count()).select_from(ReconstructionJob)
    if status_filter:
        stmt = stmt.where(ReconstructionJob.status == status_filter)
        count_stmt = count_stmt.where(ReconstructionJob.status == status_filter)
    stmt = stmt.order_by(ReconstructionJob.created_at.desc()).limit(limit).offset(offset)
    items = list(session.scalars(stmt))
    total = session.scalar(count_stmt) or 0
    return ReconstructionJobList(
        items=[ReconstructionJobOut.model_validate(i) for i in items],
        total=total,
        limit=limit,
        offset=offset,
    )
```

- [ ] **Step 2: Update `app/main.py` to include the new router**

Open `services/api-service/app/main.py`. The current `create_app()` includes routers for `health`, `dicom`, `studies`, `audit`. Find the imports line:

```python
from app.routes import audit, dicom, health, studies
```

Change it to:

```python
from app.routes import audit, dicom, health, reconstruction, studies
```

In `create_app()`, find the block of `app.include_router(...)` calls. Add this line after the existing `audit` line:

```python
    app.include_router(reconstruction.router)
```

- [ ] **Step 3: Smoke verify imports + route registration**

```bash
cd services/api-service
uv run python -c "
from app.main import app
routes = sorted({r.path for r in app.routes if hasattr(r, 'path')})
expected = ['/api/reconstruction/jobs', '/api/reconstruction/jobs/{job_id}']
for e in expected:
    assert e in routes, f'Missing route: {e}'
print('OK', len(routes), 'routes registered')
"
```

Expected: `OK <N> routes registered`.

- [ ] **Step 4: Run all unit tests + lint**

```bash
uv run pytest tests/unit/ -q
uv run ruff check .
uv run ruff format --check .
```

Expected: 56 passed; lint clean.

- [ ] **Step 5: Commit**

```bash
cd /Users/harshilvyas/Documents/Github\ Repos/NeuroScan
git add services/api-service/app/routes/reconstruction.py services/api-service/app/main.py
git commit -m "feat(slice-3): add /api/reconstruction/jobs routes (POST + GET)"
```

---

## Phase F — Integration test

### Task F1: `tests/integration/test_reconstruction_flow.py`

**Files:**
- Create: `services/api-service/tests/integration/test_reconstruction_flow.py`

- [ ] **Step 1: Write the integration tests**

```python
"""End-to-end reconstruction flow tests against real Postgres + Orthanc."""

import asyncio
from io import BytesIO

import numpy as np
import pytest

from app.services.reconstruction.forward_fft import dicom_to_kspace
from tests.fixtures.synthetic_dicom import make_synthetic_mr_dicom_bytes


def _build_npz_bytes(rows: int = 64, cols: int = 64) -> bytes:
    """Build a forward-generated .npz with kspace + ground truth in memory."""
    dicom_bytes = make_synthetic_mr_dicom_bytes(rows=rows, columns=cols)
    kspace, ground_truth = dicom_to_kspace(dicom_bytes)
    buf = BytesIO()
    np.savez(buf, kspace=kspace, ground_truth_image=ground_truth)
    return buf.getvalue()


def _build_npy_bytes(rows: int = 32, cols: int = 32) -> bytes:
    """Build a plain .npy (no ground truth)."""
    arr = np.ones((rows, cols), dtype=np.complex64)
    buf = BytesIO()
    np.save(buf, arr)
    return buf.getvalue()


async def _wait_for_terminal(api_client, job_id, timeout_s: float = 30.0) -> dict:
    """Poll GET /api/reconstruction/jobs/{job_id} until terminal status."""
    for _ in range(int(timeout_s * 5)):
        resp = await api_client.get(f"/api/reconstruction/jobs/{job_id}")
        assert resp.status_code == 200, resp.text
        body = resp.json()
        if body["status"] in ("completed", "failed"):
            return body
        await asyncio.sleep(0.2)
    pytest.fail(f"Job {job_id} did not reach terminal status within {timeout_s}s")


async def test_reconstruction_npz_with_ground_truth_completes_with_metrics(
    api_client, db_session
):
    npz_bytes = _build_npz_bytes(rows=64, cols=64)
    response = await api_client.post(
        "/api/reconstruction/jobs",
        files={"file": ("brain.npz", npz_bytes, "application/octet-stream")},
    )
    assert response.status_code == 201, response.text
    job_id = response.json()["job_id"]
    assert response.json()["status"] == "queued"

    body = await _wait_for_terminal(api_client, job_id)
    assert body["status"] == "completed", body
    assert body["output_dicom_uid"] is not None
    assert body["output_orthanc_instance_id"] is not None
    assert body["psnr_db"] is not None
    assert body["ssim"] is not None
    # FFT round-trip is essentially lossless
    assert body["psnr_db"] > 60, f"PSNR={body['psnr_db']}"
    assert body["ssim"] > 0.95, f"SSIM={body['ssim']}"


async def test_reconstruction_npy_without_ground_truth_completes_without_metrics(
    api_client, db_session
):
    npy_bytes = _build_npy_bytes()
    response = await api_client.post(
        "/api/reconstruction/jobs",
        files={"file": ("plain.npy", npy_bytes, "application/octet-stream")},
    )
    assert response.status_code == 201
    job_id = response.json()["job_id"]

    body = await _wait_for_terminal(api_client, job_id)
    assert body["status"] == "completed", body
    assert body["psnr_db"] is None
    assert body["ssim"] is None
    assert body["output_dicom_uid"] is not None


async def test_reconstruction_garbage_returns_400(api_client):
    response = await api_client.post(
        "/api/reconstruction/jobs",
        files={"file": ("nope.npy", b"this is not a numpy file", "application/octet-stream")},
    )
    assert response.status_code == 400
    body = response.json()
    assert body["code"] == "invalid_kspace"


async def test_reconstruction_unsupported_extension_returns_400(api_client):
    response = await api_client.post(
        "/api/reconstruction/jobs",
        files={"file": ("data.txt", b"plain text", "text/plain")},
    )
    assert response.status_code == 400
    assert response.json()["code"] == "invalid_kspace"


async def test_reconstruction_jobs_list_returns_recent_jobs(api_client):
    npz_bytes = _build_npz_bytes(rows=32, cols=32)
    for i in range(3):
        resp = await api_client.post(
            "/api/reconstruction/jobs",
            files={"file": (f"j{i}.npz", npz_bytes, "application/octet-stream")},
        )
        assert resp.status_code == 201
        await _wait_for_terminal(api_client, resp.json()["job_id"])

    resp = await api_client.get("/api/reconstruction/jobs?limit=50")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] >= 3
    times = [item["created_at"] for item in body["items"]]
    assert times == sorted(times, reverse=True)
```

- [ ] **Step 2: Confirm `tests/integration/conftest.py` truncates `reconstruction_jobs` between tests**

Slice 1's integration conftest at `services/api-service/tests/integration/conftest.py` has an autouse fixture that truncates `audit_events` between tests. We need the same for `reconstruction_jobs`. Open it and find the autouse fixture. It should look like:

```python
@pytest.fixture(autouse=True)
def _truncate_audit_between_tests(database_url):
    yield
    engine = create_engine(database_url)
    with engine.begin() as conn:
        conn.exec_driver_sql("TRUNCATE TABLE audit_events RESTART IDENTITY")
    engine.dispose()
```

Update it to also truncate `reconstruction_jobs`:

```python
@pytest.fixture(autouse=True)
def _truncate_tables_between_tests(database_url):
    yield
    engine = create_engine(database_url)
    with engine.begin() as conn:
        conn.exec_driver_sql(
            "TRUNCATE TABLE audit_events, reconstruction_jobs RESTART IDENTITY"
        )
    engine.dispose()
```

(If the fixture has a different name or implementation, preserve the structure and add `reconstruction_jobs` to the TRUNCATE list.)

- [ ] **Step 3: Run integration tests**

```bash
cd services/api-service
export DOCKER_HOST="unix://$HOME/.orbstack/run/docker.sock"
uv run pytest tests/integration/test_reconstruction_flow.py -v
```

Expected: 5 passed. The first run pulls Postgres + Orthanc images via testcontainers (~2 min). Subsequent runs are <30s.

- [ ] **Step 4: Run ALL integration tests to confirm no regression**

```bash
uv run pytest tests/integration/ -q
```

Expected: 12 (Slice 1) + 5 = **17 passed**.

- [ ] **Step 5: Commit**

```bash
cd /Users/harshilvyas/Documents/Github\ Repos/NeuroScan
git add services/api-service/tests/integration/test_reconstruction_flow.py services/api-service/tests/integration/conftest.py
git commit -m "test(slice-3): add integration tests for reconstruction flow

- POST .npz with ground truth → completes with PSNR>60 dB and SSIM>0.95
- POST .npy without ground truth → completes with null metrics
- POST garbage → 400 invalid_kspace
- POST unsupported extension → 400 invalid_kspace
- GET /jobs returns jobs newest-first

Also extends the autouse truncation fixture to cover reconstruction_jobs."
```

---

## Phase G — Web viewer

### Task G1: Types + API client

**Files:**
- Modify: `apps/web-viewer/src/types/index.ts`
- Create: `apps/web-viewer/src/api/reconstruction.ts`

- [ ] **Step 1: Append types to `apps/web-viewer/src/types/index.ts`**

Add at the end of the file:

```typescript
export interface ReconstructionJob {
  job_id: string;
  status: "queued" | "running" | "completed" | "failed";
  input_file_name: string;
  input_format: "npy" | "npz" | "h5";
  input_shape: string | null;
  output_dicom_uid: string | null;
  output_orthanc_instance_id: string | null;
  psnr_db: number | null;
  ssim: number | null;
  duration_ms: number | null;
  error_message: string | null;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
}

export interface ReconstructionJobCreated {
  job_id: string;
  status: "queued";
  input_file_name: string;
  input_format: "npy" | "npz" | "h5";
  created_at: string;
}
```

- [ ] **Step 2: Write `apps/web-viewer/src/api/reconstruction.ts`**

```typescript
import { apiGet, apiUpload } from "./client";
import type {
  Paginated,
  ReconstructionJob,
  ReconstructionJobCreated,
} from "../types";

export const reconstructionApi = {
  submit: (file: File) =>
    apiUpload<ReconstructionJobCreated>("/api/reconstruction/jobs", file),

  get: (jobId: string) =>
    apiGet<ReconstructionJob>(
      `/api/reconstruction/jobs/${encodeURIComponent(jobId)}`,
    ),

  list: (params: { limit?: number; status?: string } = {}) => {
    const q = new URLSearchParams();
    q.set("limit", String(params.limit ?? 50));
    if (params.status) q.set("status", params.status);
    return apiGet<Paginated<ReconstructionJob>>(
      `/api/reconstruction/jobs?${q.toString()}`,
    );
  },
};
```

- [ ] **Step 3: Typecheck**

```bash
cd apps/web-viewer
npm run typecheck
```

Expected: clean.

- [ ] **Step 4: Commit**

```bash
cd /Users/harshilvyas/Documents/Github\ Repos/NeuroScan
git add apps/web-viewer/src/types/index.ts apps/web-viewer/src/api/reconstruction.ts
git commit -m "feat(slice-3): add reconstruction types and API client wrapper"
```

---

### Task G2: Components — KspaceUploadDropzone, ReconstructionJobTable, SideBySidePreview

**Files:**
- Create: `apps/web-viewer/src/components/KspaceUploadDropzone.tsx`
- Create: `apps/web-viewer/src/components/ReconstructionJobTable.tsx`
- Create: `apps/web-viewer/src/components/SideBySidePreview.tsx`

- [ ] **Step 1: Write `KspaceUploadDropzone.tsx`**

```typescript
import { useState } from "react";

const ACCEPTED = ".npy,.npz,.h5,.hdf5";

export default function KspaceUploadDropzone({
  onFile,
  disabled,
}: {
  onFile: (file: File) => void;
  disabled?: boolean;
}) {
  const [over, setOver] = useState(false);

  return (
    <div
      data-testid="kspace-dropzone"
      onDragOver={(e) => {
        e.preventDefault();
        setOver(true);
      }}
      onDragLeave={() => setOver(false)}
      onDrop={(e) => {
        e.preventDefault();
        setOver(false);
        const file = e.dataTransfer.files?.[0];
        if (file) onFile(file);
      }}
      style={{
        border: "2px dashed #c9ccd5",
        background: over ? "#eef3ff" : "white",
        borderRadius: 8,
        padding: "1.5rem",
        textAlign: "center",
        opacity: disabled ? 0.5 : 1,
        pointerEvents: disabled ? "none" : "auto",
      }}
    >
      <p style={{ margin: 0 }}>Drop a k-space file (.npy / .npz / .h5)</p>
      <input
        type="file"
        accept={ACCEPTED}
        style={{ marginTop: "0.75rem" }}
        onChange={(e) => {
          const f = e.target.files?.[0];
          if (f) onFile(f);
        }}
      />
    </div>
  );
}
```

- [ ] **Step 2: Write `ReconstructionJobTable.tsx`**

```typescript
import type { ReconstructionJob } from "../types";

const STATUS_LABELS: Record<ReconstructionJob["status"], string> = {
  queued: "queued",
  running: "running",
  completed: "done",
  failed: "failed",
};

const STATUS_COLORS: Record<ReconstructionJob["status"], string> = {
  queued: "#666",
  running: "#a47900",
  completed: "#0a6b1f",
  failed: "#a4282b",
};

function formatNumber(n: number | null, decimals = 2): string {
  if (n === null || n === undefined) return "—";
  return n.toFixed(decimals);
}

function formatDuration(ms: number | null): string {
  if (ms === null || ms === undefined) return "—";
  if (ms < 1000) return `${ms} ms`;
  return `${(ms / 1000).toFixed(1)} s`;
}

export default function ReconstructionJobTable({
  items,
  expandedId,
  onToggleExpand,
}: {
  items: ReconstructionJob[];
  expandedId: string | null;
  onToggleExpand: (jobId: string) => void;
}) {
  if (items.length === 0) {
    return <p>No reconstruction jobs yet. Drop a k-space file above to start.</p>;
  }
  return (
    <table>
      <thead>
        <tr>
          <th>Created</th>
          <th>File</th>
          <th>Status</th>
          <th>PSNR</th>
          <th>SSIM</th>
          <th>Duration</th>
        </tr>
      </thead>
      <tbody>
        {items.map((job) => (
          <tr
            key={job.job_id}
            onClick={() => onToggleExpand(job.job_id)}
            style={{
              cursor: "pointer",
              background: expandedId === job.job_id ? "#eef3ff" : undefined,
            }}
          >
            <td>{new Date(job.created_at).toLocaleString()}</td>
            <td>{job.input_file_name}</td>
            <td style={{ color: STATUS_COLORS[job.status] }}>
              {STATUS_LABELS[job.status]}
            </td>
            <td>{formatNumber(job.psnr_db, 1)}</td>
            <td>{formatNumber(job.ssim, 3)}</td>
            <td>{formatDuration(job.duration_ms)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
```

- [ ] **Step 3: Write `SideBySidePreview.tsx`**

```typescript
import { Link } from "react-router-dom";
import { previewUrl } from "../api/client";
import type { ReconstructionJob } from "../types";

export default function SideBySidePreview({
  job,
}: {
  job: ReconstructionJob;
}) {
  if (job.status !== "completed") {
    if (job.status === "failed") {
      return (
        <div style={{ marginTop: "0.75rem", color: "#a4282b" }}>
          <strong>Failed:</strong> {job.error_message ?? "unknown error"}
        </div>
      );
    }
    return (
      <p style={{ marginTop: "0.75rem", color: "#666" }}>
        {job.status === "running" ? "Reconstructing…" : "Queued…"}
      </p>
    );
  }

  const reconUrl = job.output_orthanc_instance_id
    ? previewUrl(job.output_orthanc_instance_id)
    : null;
  const hasGroundTruth = job.psnr_db !== null && job.ssim !== null;

  return (
    <div
      style={{
        marginTop: "0.75rem",
        padding: "1rem",
        background: "#fafbfc",
        border: "1px solid #e3e5ec",
        borderRadius: 6,
      }}
    >
      <div style={{ display: "flex", gap: "1.5rem", flexWrap: "wrap" }}>
        {hasGroundTruth && (
          <div>
            <div style={{ fontSize: 12, marginBottom: 4 }}>Original (note: not stored — preview shows reconstruction)</div>
            <div
              style={{
                width: 256,
                height: 256,
                background: "#222",
                color: "#888",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                fontSize: 13,
              }}
            >
              Ground truth shown as metrics only
            </div>
          </div>
        )}
        {reconUrl && (
          <div>
            <div style={{ fontSize: 12, marginBottom: 4 }}>Reconstructed</div>
            <img
              src={reconUrl}
              alt="Reconstructed image"
              style={{
                width: 256,
                height: 256,
                objectFit: "contain",
                background: "#000",
                border: "1px solid #ccc",
              }}
            />
          </div>
        )}
      </div>
      {hasGroundTruth && (
        <p style={{ marginTop: "0.75rem" }}>
          <strong>PSNR:</strong> {job.psnr_db?.toFixed(2)} dB &nbsp;·&nbsp;{" "}
          <strong>SSIM:</strong> {job.ssim?.toFixed(3)}
        </p>
      )}
      {job.output_dicom_uid && (
        <p style={{ marginTop: "0.5rem" }}>
          <Link to={`/studies/${encodeURIComponent(job.output_dicom_uid)}`}>
            Open reconstructed study →
          </Link>
        </p>
      )}
    </div>
  );
}
```

- [ ] **Step 4: Typecheck + build**

```bash
cd apps/web-viewer
npm run typecheck
npm run build
```

Expected: both clean.

- [ ] **Step 5: Commit**

```bash
cd /Users/harshilvyas/Documents/Github\ Repos/NeuroScan
git add apps/web-viewer/src/components/KspaceUploadDropzone.tsx apps/web-viewer/src/components/ReconstructionJobTable.tsx apps/web-viewer/src/components/SideBySidePreview.tsx
git commit -m "feat(slice-3): add k-space dropzone, job table, and side-by-side preview components"
```

---

### Task G3: Page + routing + nav

**Files:**
- Create: `apps/web-viewer/src/pages/ReconstructionPage.tsx`
- Modify: `apps/web-viewer/src/routes.tsx`
- Modify: `apps/web-viewer/src/components/Nav.tsx`

- [ ] **Step 1: Write `ReconstructionPage.tsx`**

```typescript
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { reconstructionApi } from "../api/reconstruction";
import { ApiClientError } from "../api/client";
import KspaceUploadDropzone from "../components/KspaceUploadDropzone";
import ReconstructionJobTable from "../components/ReconstructionJobTable";
import SideBySidePreview from "../components/SideBySidePreview";

const ACTIVE_STATUSES = new Set(["queued", "running"]);

export default function ReconstructionPage() {
  const queryClient = useQueryClient();
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const { data, isLoading, error } = useQuery({
    queryKey: ["reconstructionJobs"],
    queryFn: () => reconstructionApi.list({ limit: 50 }),
    refetchInterval: (query) => {
      const items = query.state.data?.items ?? [];
      return items.some((j) => ACTIVE_STATUSES.has(j.status)) ? 2000 : false;
    },
  });

  const mutation = useMutation({
    mutationFn: (file: File) => reconstructionApi.submit(file),
    onSuccess: () => {
      setErrorMsg(null);
      queryClient.invalidateQueries({ queryKey: ["reconstructionJobs"] });
    },
    onError: (e: unknown) => {
      if (e instanceof ApiClientError) {
        setErrorMsg(`${e.code ?? "error"}: ${e.message}`);
      } else {
        setErrorMsg(String(e));
      }
    },
  });

  const items = data?.items ?? [];
  const expandedJob = items.find((j) => j.job_id === expandedId) ?? null;

  return (
    <section>
      <h1>Reconstruction</h1>
      <p style={{ color: "#666" }}>
        Upload k-space data (.npy / .npz / .h5). The service runs an inverse FFT,
        stores the result as DICOM in the local archive, and computes PSNR + SSIM
        when ground truth is embedded (forward-generated .npz files).
      </p>

      <KspaceUploadDropzone
        onFile={(f) => mutation.mutate(f)}
        disabled={mutation.isPending}
      />

      {mutation.isPending && <p>Uploading…</p>}
      {errorMsg && (
        <p data-testid="recon-error" style={{ color: "#a4282b" }}>
          {errorMsg}
        </p>
      )}

      <h2 style={{ marginTop: "1.5rem" }}>Recent jobs</h2>
      {isLoading ? (
        <p>Loading…</p>
      ) : error ? (
        <p style={{ color: "#a4282b" }}>Error: {(error as Error).message}</p>
      ) : (
        <ReconstructionJobTable
          items={items}
          expandedId={expandedId}
          onToggleExpand={(id) =>
            setExpandedId((current) => (current === id ? null : id))
          }
        />
      )}

      {expandedJob && <SideBySidePreview job={expandedJob} />}
    </section>
  );
}
```

- [ ] **Step 2: Update `apps/web-viewer/src/routes.tsx`**

The current file should look like:

```typescript
import { Navigate, Route, Routes as RouterRoutes } from "react-router-dom";
import StudyListPage from "./pages/StudyListPage";
import StudyDetailPage from "./pages/StudyDetailPage";
import UploadPage from "./pages/UploadPage";
import AuditPage from "./pages/AuditPage";

export default function Routes() {
  return (
    <RouterRoutes>
      <Route path="/" element={<Navigate to="/studies" replace />} />
      <Route path="/studies" element={<StudyListPage />} />
      <Route path="/studies/:studyInstanceUid" element={<StudyDetailPage />} />
      <Route path="/upload" element={<UploadPage />} />
      <Route path="/audit" element={<AuditPage />} />
    </RouterRoutes>
  );
}
```

Replace it with:

```typescript
import { Navigate, Route, Routes as RouterRoutes } from "react-router-dom";
import StudyListPage from "./pages/StudyListPage";
import StudyDetailPage from "./pages/StudyDetailPage";
import UploadPage from "./pages/UploadPage";
import AuditPage from "./pages/AuditPage";
import ReconstructionPage from "./pages/ReconstructionPage";

export default function Routes() {
  return (
    <RouterRoutes>
      <Route path="/" element={<Navigate to="/studies" replace />} />
      <Route path="/studies" element={<StudyListPage />} />
      <Route path="/studies/:studyInstanceUid" element={<StudyDetailPage />} />
      <Route path="/upload" element={<UploadPage />} />
      <Route path="/reconstruction" element={<ReconstructionPage />} />
      <Route path="/audit" element={<AuditPage />} />
    </RouterRoutes>
  );
}
```

- [ ] **Step 3: Update `apps/web-viewer/src/components/Nav.tsx`**

The current file has three NavLinks: Studies, Upload, Audit. Add a fourth one between Upload and Audit. The existing structure looks like:

```typescript
<NavLink to="/upload" className={...}>Upload</NavLink>
<NavLink to="/audit" className={...}>Audit</NavLink>
```

Insert a new line between them:

```typescript
<NavLink to="/upload" className={({ isActive }) => `${styles.link} ${isActive ? styles.active : ""}`}>Upload</NavLink>
<NavLink to="/reconstruction" className={({ isActive }) => `${styles.link} ${isActive ? styles.active : ""}`}>Reconstruction</NavLink>
<NavLink to="/audit" className={({ isActive }) => `${styles.link} ${isActive ? styles.active : ""}`}>Audit</NavLink>
```

(Match the exact `className` callback pattern already used by the other NavLinks; use the existing `styles` import from `./Nav.module.css` — no new CSS needed.)

- [ ] **Step 4: Typecheck + build**

```bash
cd apps/web-viewer
npm run typecheck
npm run build
```

Expected: both clean.

- [ ] **Step 5: Commit**

```bash
cd /Users/harshilvyas/Documents/Github\ Repos/NeuroScan
git add apps/web-viewer/src/pages/ReconstructionPage.tsx apps/web-viewer/src/routes.tsx apps/web-viewer/src/components/Nav.tsx
git commit -m "feat(slice-3): add /reconstruction page with polling and side-by-side preview"
```

---

## Phase H — Scripts + docs

### Task H1: `scripts/generate-synthetic-kspace.py`

**Files:**
- Create: `scripts/generate-synthetic-kspace.py`

- [ ] **Step 1: Write the script**

```python
#!/usr/bin/env python3
"""Generate a synthetic k-space file from a DICOM image.

Output is a .npz containing both 'kspace' (complex64) and 'ground_truth_image'
(float32, normalized to [0, 1]). The reconstruction service uses the embedded
ground truth to compute PSNR/SSIM on completion.

Usage:
    uv run --directory services/api-service python ../../scripts/generate-synthetic-kspace.py \\
        INPUT_DICOM OUTPUT_NPZ

Example:
    uv run --directory services/api-service python ../../scripts/generate-synthetic-kspace.py \\
        /Users/me/repo/data/sample-dicom/real-multislice/slice_010.dcm /tmp/brain.npz
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "services" / "api-service"))

import numpy as np  # noqa: E402

from app.services.reconstruction.forward_fft import dicom_to_kspace  # noqa: E402


def main() -> int:
    if len(sys.argv) != 3:
        print(
            "Usage: generate-synthetic-kspace.py INPUT_DICOM OUTPUT_NPZ",
            file=sys.stderr,
        )
        return 2
    input_path = Path(sys.argv[1])
    output_path = Path(sys.argv[2])
    if not input_path.exists():
        print(f"Input DICOM not found: {input_path}", file=sys.stderr)
        return 1

    dicom_bytes = input_path.read_bytes()
    kspace, ground_truth = dicom_to_kspace(dicom_bytes)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    np.savez(
        output_path,
        kspace=kspace,
        ground_truth_image=ground_truth,
    )
    print(
        f"Wrote {output_path} ({output_path.stat().st_size} bytes)\n"
        f"  kspace shape: {kspace.shape}, dtype: {kspace.dtype}\n"
        f"  ground_truth_image shape: {ground_truth.shape}, "
        f"range: [{ground_truth.min():.3f}, {ground_truth.max():.3f}]"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Make executable + smoke test**

```bash
chmod +x scripts/generate-synthetic-kspace.py
mkdir -p /tmp/recon-test
uv run --directory services/api-service python ../../scripts/generate-synthetic-kspace.py \
    "/Users/harshilvyas/Documents/Github Repos/NeuroScan/data/sample-dicom/real-multislice/slice_010.dcm" \
    /tmp/recon-test/brain.npz

# Verify the output
uv run --directory services/api-service python -c "
import numpy as np
data = np.load('/tmp/recon-test/brain.npz')
assert 'kspace' in data.files
assert 'ground_truth_image' in data.files
print('OK kspace shape:', data['kspace'].shape, 'dtype:', data['kspace'].dtype)
print('   ground_truth shape:', data['ground_truth_image'].shape)
"
rm -rf /tmp/recon-test
```

Expected: file written; verification prints expected shape and dtype.

- [ ] **Step 3: Commit**

```bash
cd /Users/harshilvyas/Documents/Github\ Repos/NeuroScan
git add scripts/generate-synthetic-kspace.py
git commit -m "feat(slice-3): add CLI script to generate synthetic k-space from DICOM"
```

---

### Task H2: README quickstart + QA validation TC-08

**Files:**
- Modify: `README.md`
- Modify: `docs/qa-validation-plan.md`

- [ ] **Step 1: Update `README.md`**

In the **Quickstart** section, after the "Generate a synthetic DICOM and upload it" line, append:

```markdown
# Generate a synthetic k-space file (for the /reconstruction page)
mkdir -p data/sample-dicom/synthetic-kspace
uv run --directory services/api-service python ../../scripts/generate-synthetic-kspace.py \
    "$PWD/data/sample-dicom/real-multislice/slice_010.dcm" \
    "$PWD/data/sample-dicom/synthetic-kspace/brain.npz"
```

In the **Tests** section, no change is needed (the new tests run under the existing `pytest` command).

In the section listing what the project demonstrates (or the introduction paragraph if there's no such section), add a bullet:

> - **MRI reconstruction**: inverse FFT pipeline with PSNR/SSIM quality metrics, queued via FastAPI BackgroundTasks, output stored as DICOM in Orthanc.

- [ ] **Step 2: Update `docs/qa-validation-plan.md`**

Find the existing test cases (TC-01 through TC-07). Add a new TC-08 at the end of the manual test cases section (before "## Automated tests as QA artifacts" or equivalent):

```markdown
### TC-08 Reconstruction round-trip (PSNR + SSIM verification)

Steps:
1. With the stack running:
   ```
   uv run --directory services/api-service python ../../scripts/generate-synthetic-kspace.py \
       "$PWD/data/sample-dicom/real-multislice/slice_010.dcm" \
       /tmp/brain.npz
   ```
2. Open http://localhost:5173/reconstruction.
3. Drop `/tmp/brain.npz`.
4. Watch the new row appear in the table; status transitions `queued → running → completed` within ~5 s.
5. Click the row to expand the side-by-side preview.
6. Click "Open reconstructed study →".

Expected:
- Status reaches `completed`.
- PSNR > 60 dB (FFT round-trip is essentially lossless).
- SSIM > 0.95.
- Reconstructed study appears under `/studies` with PatientName `Reconstruction^Output`.
- Preview image renders on the study detail page.

Pass criteria: all expected outcomes met. Reject row also added if a malformed file is uploaded.
```

Also append an entry to the **Known limitations** section:

```markdown
- Reconstruction supports 2D single-coil k-space only. Multi-coil (sum-of-squares) and 3D volumetric reconstruction are deferred to a future slice.
- Raw k-space inputs are stored only in a temp directory during processing and deleted on terminal status. Permanent k-space storage is Slice 4's job.
- Reconstruction jobs are not load-tested for concurrency; a real queue with worker pools comes in Slice 9.
```

- [ ] **Step 3: Commit**

```bash
cd /Users/harshilvyas/Documents/Github\ Repos/NeuroScan
git add README.md docs/qa-validation-plan.md
git commit -m "docs(slice-3): add reconstruction quickstart + QA TC-08 + limitations"
```

---

## Phase I — Wrap-up

### Task I1: Update status + roadmap, push branch

**Files:**
- Modify: `docs/status.md`
- Modify: `docs/roadmap.md`

- [ ] **Step 1: Update `docs/roadmap.md` row for slice 3**

Find:
```text
| 3 | Reconstruction service (k-space → reconstructed image → DICOM → Orthanc) | planned | — | Adds `reconstruction_jobs` table + reconstruction-service container |
```
Replace with:
```text
| 3 | Reconstruction service (k-space → reconstructed image → DICOM → Orthanc) | **done** | [spec](./superpowers/specs/2026-05-06-slice-3-reconstruction-service-design.md) · [plan](./superpowers/plans/2026-05-06-slice-3-reconstruction-service.md) | Completed 2026-05-06. Implemented as a module inside api-service, not a separate container — see AD-S3-1. |
```

Also add a new row for Slice 9.5 (split out from the original "advanced reconstruction" bucket). Find the row for slice 9 ("Background job queue") and add a new row immediately after it:

```text
| 9.5 | Advanced reconstruction: undersampling sim + compressed sensing + optional U-Net | planned | — | Split from slice 9; lets slice 9 focus on the queue while 9.5 owns the algorithm work |
```

- [ ] **Step 2: Update `docs/status.md`**

Replace the **Current slice** section. Old:
```markdown
**Slice 2 — Qt desktop viewer.** Implementation complete. Merged to `main` 2026-05-06.
```
New:
```markdown
**Slice 3 — MRI Reconstruction Service.** Implementation complete on branch `slice-3-reconstruction-service`. Pending merge to `main`.

Spec: [`superpowers/specs/2026-05-06-slice-3-reconstruction-service-design.md`](./superpowers/specs/2026-05-06-slice-3-reconstruction-service-design.md)
Plan: [`superpowers/plans/2026-05-06-slice-3-reconstruction-service.md`](./superpowers/plans/2026-05-06-slice-3-reconstruction-service.md)
```

In the **What's done** list, append:

```markdown
- Slice 3 implementation complete on `slice-3-reconstruction-service`:
  - Six pure-logic modules in `services/api-service/app/services/reconstruction/`: kspace_loader, fft_reconstruct, forward_fft, metrics (PSNR + SSIM), dicom_writer, job_runner
  - `reconstruction_jobs` table (alembic migration 002)
  - `POST /api/reconstruction/jobs` + `GET /api/reconstruction/jobs/{id}` + `GET /api/reconstruction/jobs` routes
  - FastAPI BackgroundTasks for in-process async execution (CPU-bound reconstruction in threadpool)
  - Forward-FFT helper builds synthetic .npz with embedded ground truth → enables honest PSNR/SSIM
  - h5py for fastMRI-compatible HDF5 input
  - 32 new unit tests (10 + 6 + 5 + 6 + 5 = 32 covering all six modules)
  - 5 new integration tests against real Postgres + Orthanc via testcontainers
  - New React `/reconstruction` page: dropzone, polling job table, side-by-side preview
  - CLI script `scripts/generate-synthetic-kspace.py`
  - README quickstart + QA TC-08 added
```

In the **What's next** section, replace with:

```markdown
1. Merge `slice-3-reconstruction-service` to `main` and push.
2. Brainstorm Slice 4 — MinIO + signed-URL upload flow + checksum-validated object storage.
```

In the **Recent decisions log**, append:

```markdown
- 2026-05-06: Locked AD-S3-1..10 (in-process reconstruction module, BackgroundTasks, .npy/.npz/.h5 inputs, forward-FFT generator, nullable PSNR/SSIM, fresh DICOM UIDs, tempfile-only k-space storage, web-only UI, h5py + scikit-image deps).
- 2026-05-06: AD-S3-1 explicitly revised the original roadmap entry: reconstruction lives inside api-service, not a separate container.
- 2026-05-06: Added Slice 9.5 to the roadmap for advanced reconstruction techniques (undersampling, compressed sensing, U-Net), split from the old "advanced" bucket.
- 2026-05-06: Slice 3 implementation complete (32 new unit tests, 5 new integration tests).
```

In the **Slice 3 implementation deviations from spec/plan** section (add this as a new top-level subsection after the existing Slice 2 deviations):

```markdown
### Slice 3 implementation deviations from spec/plan (record for posterity)

(Fill in any deviations the implementer subagents discover during execution. Examples might include: ruff per-file-ignores added for new packages, h5py warnings during import, alembic autogen producing a slightly different column order than the model declaration, etc.)
```

(The implementer agent will fill in concrete deviations as they're found.)

- [ ] **Step 3: Run all tests one final time on `slice-3-reconstruction-service`**

```bash
export DOCKER_HOST="unix://$HOME/.orbstack/run/docker.sock"
cd services/api-service
uv run pytest -q                       # 56 unit + 17 integration = 73 passed
uv run ruff check .
uv run ruff format --check .
cd ../../apps/web-viewer
npm run typecheck
npm run build
```

Expected: all green.

- [ ] **Step 4: Commit and push**

```bash
cd /Users/harshilvyas/Documents/Github\ Repos/NeuroScan
git add docs/status.md docs/roadmap.md
git commit -m "docs(slice-3): mark slice 3 done in status.md and roadmap.md"
git push -u origin slice-3-reconstruction-service
```

The push prints a PR URL.

---

## Notes for the implementing engineer

- **Phase B is strict TDD.** Every module in B1–B5 is written test-first. Don't skip the failing-test step. The tests compose well — they're independent so order between B1–B5 matters only because the cumulative test count check in B5 requires all four predecessors landed.
- **Phase C touches Postgres.** You need OrbStack running and `~/.orbstack/bin` on PATH for the alembic autogenerate step. No DOCKER_HOST needed for `docker compose` itself; only for testcontainers (Phase F).
- **Phase F integration tests need DOCKER_HOST.** Set `export DOCKER_HOST="unix://$HOME/.orbstack/run/docker.sock"` before running pytest in `services/api-service/`.
- **The job_runner's `_upload_sync`** is a deliberate parallel of OrthancClient's async upload — they do the same thing. Don't try to make the route handler call the async client from within a sync BackgroundTask; it will block the event loop.
- **Don't touch `apps/desktop-viewer/`.** Slice 3 is web-only by design (AD-S3-9).
- **Don't add to `infra/`.** No new container.
- **Don't run lint with `--fix --unsafe-fixes` blindly.** The Slice 1/2 patterns established per-file-ignores for legitimate stylistic conflicts (Qt camelCase, FastAPI `Depends`). New code in Slice 3 should not need new exceptions; if you find yourself wanting one, the code is probably wrong.
- **Commit policy is strict:** one commit per task except where the plan explicitly calls for two. NEVER amend. If a step needs a follow-up, it's a new commit.
```

