# NeuroScan Workstation — Slice 3: MRI Reconstruction Service

**Date:** 2026-05-06
**Status:** Draft (pending user review)
**Phase:** 3 of N
**Parent project:** NeuroScan Workstation — local-first MRI / DICOM platform
**Branch:** `slice-3-reconstruction-service` (off `main`)
**Predecessors:** Slice 1 (vertical spine) + Slice 2 (Qt desktop viewer), both merged to `main`

---

## 1. Purpose

Add an MRI reconstruction pipeline to the NeuroScan Workstation: take raw k-space data as input, run inverse FFT, generate a reconstructed image, save it as a DICOM file, store it back in the Orthanc archive, and surface the result in the React web viewer with quality metrics and a side-by-side comparison against ground truth.

This is the most role-differentiating slice of the project. The neuro42 role description explicitly calls for "real-time signal acquisition, signal processing, image reconstruction, enhance MR technology performance." Slice 3 demonstrates exactly that — not just CRUD around DICOM, but actual MR signal-to-image conversion with quantitative validation.

The slice also establishes the "background job" pattern that Slice 9 will later harden with a real queue.

## 2. Out-of-scope (deliberately deferred)

- Undersampling simulation (mask k-space, reconstruct partial)
- Compressed sensing / iterative reconstruction
- Deep-learning-based reconstruction (U-Net, etc.)
- Real Redis-backed queue with retries (Slice 9)
- 3D / volumetric reconstruction (Slice 3 handles 2D slices only)
- Multi-coil reconstruction (sum-of-squares from multi-channel k-space)
- Permanent storage of raw k-space inputs (Slice 4: MinIO)
- Reconstruction from real fastMRI multi-coil data (.h5 path supports single-coil 2D only in this slice)
- Desktop viewer integration (`apps/desktop-viewer/` is untouched)
- Real-time progress percentage updates (status transitions only: `queued → running → completed | failed`)
- Cancellation of in-flight jobs

These are explicit deferrals. Trying any of them in Slice 3 is scope creep.

## 3. Architecture

### Single-process inside `api-service`

```text
React /reconstruction page
        │
        │ (1) POST /api/reconstruction/jobs   (multipart: file=.npy|.npz|.h5)
        ▼
┌──────────────────────────────────────────────────────────────────┐
│  api-service                                                     │
│                                                                  │
│  routes/reconstruction.py                                        │
│    POST  /api/reconstruction/jobs                                │
│    GET   /api/reconstruction/jobs/{id}                           │
│    GET   /api/reconstruction/jobs                                │
│                                                                  │
│  services/reconstruction/                                        │
│    kspace_loader.py     # parse .npy/.npz/.h5 → np.complex64     │
│    fft_reconstruct.py   # inverse FFT + magnitude image          │
│    forward_fft.py       # DICOM → synthetic .npz k-space         │
│    metrics.py           # PSNR + SSIM                            │
│    dicom_writer.py      # numpy image → MR DICOM bytes           │
│    job_runner.py        # FastAPI BackgroundTask body            │
│                                                                  │
│  models/reconstruction.py     ReconstructionJob (SQLAlchemy)     │
│  Alembic migration 002_reconstruction_jobs                       │
└─────┬────────────────────────────────────────────────┬───────────┘
      │ (2) write job row                              │ (5) POST /instances
      ▼                                                ▼
┌─────────────┐                                  ┌────────────┐
│ PostgreSQL  │                                  │  Orthanc   │
│ recon_jobs  │                                  │  archive   │
└─────────────┘                                  └────────────┘
      ▲
      │ (3) update job row as it transitions
      │ (4) read for status
      │
React polls GET /api/reconstruction/jobs/{id}
        │
        │ (6) when status=completed: render side-by-side preview
        ▼
PNG of reconstructed image (Orthanc /preview)
+ original ground-truth PNG (if input was forward-generated)
+ PSNR / SSIM numbers
```

### Job lifecycle

```text
queued → running → completed
             ↓
           failed
```

| State | When | What's set |
|---|---|---|
| `queued` | row inserted on POST | created_at |
| `running` | BackgroundTask picks it up | started_at |
| `completed` | reconstruction finished, DICOM stored, metrics computed | completed_at, output_dicom_uid, output_orthanc_instance_id, psnr_db, ssim, duration_ms |
| `failed` | any exception during load/reconstruct/write | completed_at, error_message |

### Architectural decisions (locked)

| ID | Decision | Rationale |
|---|---|---|
| AD-S3-1 | Reconstruction lives **inside** api-service, not a separate container | **Revises** the original roadmap entry. Same external API; vastly less infra ceremony; clean module boundaries make future extraction trivial if a GPU node ever becomes necessary. |
| AD-S3-2 | FastAPI `BackgroundTasks` for in-process async | No Redis/Celery in this slice. Same job API as the eventual Slice 9 queue version, so the upgrade is non-breaking. |
| AD-S3-3 | Inputs accepted as `.npy`, `.npz` (NumPy), and `.h5` (fastMRI HDF5) | `.npy`/`.npz` for synthetic + tests; `.h5` for real fastMRI samples and resume keyword recognition. |
| AD-S3-4 | Forward-FFT helper that converts existing DICOM → synthetic k-space `.npz` with embedded ground-truth image | Closes the loop. Lets tests, demos, and CI run without external datasets. Makes PSNR/SSIM meaningful. |
| AD-S3-5 | Quality metrics (PSNR + SSIM) computed only when ground truth is available | Honest reporting — no fake metrics on real data. Stored as nullable `DOUBLE PRECISION` columns. |
| AD-S3-6 | Output DICOM constructed with **fresh** synthetic UIDs (Patient/Study/Series/SOP) | Reconstruction output is a NEW study, not a derivative. Keeps Orthanc semantics clean. Patient/Study metadata is stamped with reconstruction provenance (`PatientName: "Reconstruction^Output"`, `StudyDescription: "MRI Reconstruction"`). |
| AD-S3-7 | Uploaded k-space file stored in a temp directory during processing, deleted on terminal state | No need to keep raw k-space around long-term in this slice. MinIO is Slice 4's job. |
| AD-S3-8 | Job state in Postgres (`reconstruction_jobs` table); api-service polls the same DB on GET | Reuses existing Postgres. AD-1 still satisfied (app-owned data only). |
| AD-S3-9 | UI is web-only; desktop viewer is unchanged | Job lists/history naturally live on the web. Desktop integration is a follow-on if it turns out to matter. |
| AD-S3-10 | New deps in api-service: `h5py`, `scikit-image` | h5py for .h5 parsing; scikit-image for SSIM. Both are standard scientific Python. |

### Cross-slice decisions still inherited

AD-1 through AD-9 from `docs/roadmap.md` continue to apply. AD-1 is satisfied: `reconstruction_jobs` is app-owned data, not a duplicate of DICOM metadata. AD-4 (sync uploads) is technically softened in this slice — uploads of k-space are sync, but reconstruction itself is async via BackgroundTasks. We document this nuance in the spec rather than amending AD-4 globally.

## 4. Data flows

### 4.1 Forward FFT generator (the "ground truth" trick)

```text
Input:  any DICOM image we already have on disk
        e.g. data/sample-dicom/real-multislice/slice_010.dcm

Steps:
  1. pydicom.dcmread → numpy [H, W] int16
  2. Cast to float32 (preserves dynamic range)
  3. np.fft.fft2 → np.fft.fftshift → complex64 [H, W]
  4. np.savez(out_path, kspace=k, ground_truth_image=image, original_shape=image.shape)

Output: <name>.npz  containing both k-space AND original image as a sidecar
```

The `.npz` format is the same NumPy archive used by countless ML codebases. Loading it gives a dict-like object with `kspace`, `ground_truth_image`, and `original_shape` keys. When the reconstruction service sees a `.npz` with those keys, it computes PSNR/SSIM. When the input is a plain `.npy` or fastMRI `.h5`, ground truth is absent and metrics are stored as `null`.

CLI wrapper: `scripts/generate-synthetic-kspace.py <input.dcm> <output.npz>`.

### 4.2 Reconstruction job submission

1. User drops a `.npy`/`.npz`/`.h5` file in the React `/reconstruction` page → `POST /api/reconstruction/jobs`.
2. api-service validates extension (allowed: `.npy`, `.npz`, `.h5`), checks size (< 100MB by default), and tries to parse the file with `kspace_loader.load(path)`. Parse failures → 400 `invalid_kspace`. Shape failures (not 2D, not complex-castable) → 400 `unsupported_shape`.
3. api-service inserts a row into `reconstruction_jobs` with `status=queued` and saves the uploaded bytes to a tempfile path that the BackgroundTask will read.
4. api-service registers a BackgroundTask with the job_id and tempfile path; returns 201 with the job_id immediately.

### 4.3 Reconstruction job execution

The BackgroundTask body (`job_runner.run_job`):

```text
1. UPDATE reconstruction_jobs SET status='running', started_at=now() WHERE job_id=…
2. kspace, ground_truth = kspace_loader.load(tempfile_path)
3. recon_image = fft_reconstruct.reconstruct(kspace)
4. if ground_truth is not None:
       psnr_db = metrics.psnr(recon_image, ground_truth)
       ssim    = metrics.ssim(recon_image, ground_truth)
   else:
       psnr_db, ssim = None, None
5. dicom_bytes = dicom_writer.image_to_mr_dicom(recon_image, source_filename)
6. orthanc_instance_id = orthanc_client.upload_instance(dicom_bytes)
7. UPDATE reconstruction_jobs SET status='completed', completed_at=now(),
       output_dicom_uid=…, output_orthanc_instance_id=…,
       psnr_db=…, ssim=…, duration_ms=…
       WHERE job_id=…
8. delete tempfile
```

On any exception in steps 2–6: catch, set `status='failed'`, write `error_message`, set `completed_at`, delete tempfile.

### 4.4 Status polling from the web UI

React polls `GET /api/reconstruction/jobs` every 2s when any visible job is `queued` or `running`. Polling stops when all jobs in the current view are terminal (`completed` or `failed`). The expanded preview row fires `GET /api/reconstruction/jobs/{id}` once on expansion, then relies on the list polling.

## 5. Slice 3 scope — what we build

### Backend (api-service)

- New SQLAlchemy model `ReconstructionJob` + alembic migration `002`
- New deps in `pyproject.toml`: `h5py`, `scikit-image`
- Six pure-logic modules under `services/reconstruction/`:
  - `kspace_loader.py` — load `.npy`, `.npz`, `.h5` → `(kspace: np.complex64, ground_truth: np.ndarray | None)`
  - `fft_reconstruct.py` — `reconstruct(kspace) -> np.ndarray` (magnitude image, normalized to [0, 4095] uint16)
  - `forward_fft.py` — `dicom_to_kspace(dicom_bytes) -> (kspace, ground_truth)`
  - `metrics.py` — `psnr(a, b) -> float` and `ssim(a, b) -> float`
  - `dicom_writer.py` — `image_to_mr_dicom(image, source_name) -> bytes`
  - `job_runner.py` — `run_job(job_id, tempfile_path)` — the BackgroundTask body
- New routes module `routes/reconstruction.py` with the three endpoints
- New pydantic schemas `schemas/reconstruction.py`
- Unit tests for all six pure-logic modules (≥ 5 tests each)
- One integration test exercising the full flow against testcontainers

### Web (web-viewer)

- New page component `pages/ReconstructionPage.tsx`
- Three new components: `KspaceUploadDropzone`, `ReconstructionJobTable`, `SideBySidePreview`
- New API client wrapper `api/reconstruction.ts`
- Router + Nav additions to expose `/reconstruction`
- TanStack Query polling setup for active jobs

### Scripts

- `scripts/generate-synthetic-kspace.py` — CLI wrapper around `forward_fft.dicom_to_kspace`

### Docs

- `docs/qa-validation-plan.md` — new TC-08 for reconstruction
- `docs/status.md` and `docs/roadmap.md` — mark Slice 3 done
- README quickstart paragraph mentioning `/reconstruction`

### Untouched

- `apps/desktop-viewer/` — Slice 2 unchanged
- `infra/` — no new container, no compose changes
- `tests/e2e/` — no new Playwright test in this slice (could add later)
- Slice 1 routes (audit, studies, dicom upload, preview) — unchanged

## 6. Component specs

### 6.1 `kspace_loader.py`

```python
from pathlib import Path
import numpy as np

def load(path: Path) -> tuple[np.ndarray, np.ndarray | None]:
    """Load k-space data from .npy, .npz, or .h5.

    Returns:
        (kspace, ground_truth)
        - kspace: complex64, shape (H, W)
        - ground_truth: float32, shape (H, W), or None if not embedded
    """
    ...

class InvalidKspaceError(Exception): ...
class UnsupportedShapeError(Exception): ...
```

Behavior:
- `.npy`: load with `np.load`. Must be 2D and castable to complex. No ground truth.
- `.npz`: load with `np.load`. Required key `kspace`; optional keys `ground_truth_image`, `original_shape`.
- `.h5`: load with `h5py`. Look for the fastMRI conventional dataset names (`kspace`, `reconstruction_rss`, `reconstruction_esc`); take a single 2D slice if 4D (multi-coil) — middle slice, average across coils as fallback. No ground truth (fastMRI is what we're trying to reconstruct *from*).
- Anything else: `InvalidKspaceError`.
- Shape not 2D after coil reduction: `UnsupportedShapeError`.

### 6.2 `fft_reconstruct.py`

```python
import numpy as np

def reconstruct(kspace: np.ndarray) -> np.ndarray:
    """Inverse FFT reconstruction.

    Steps:
      1. ifftshift to undo any forward shift
      2. ifft2 → complex image
      3. magnitude (np.abs)
      4. normalize to [0, 4095] uint16 (12-bit MR-style range)
    """
    shifted = np.fft.ifftshift(kspace)
    complex_image = np.fft.ifft2(shifted)
    magnitude = np.abs(complex_image).astype(np.float32)
    if magnitude.max() > 0:
        magnitude = magnitude / magnitude.max() * 4095
    return magnitude.astype(np.uint16)
```

### 6.3 `forward_fft.py`

```python
import numpy as np
import pydicom
from io import BytesIO

def dicom_to_kspace(dicom_bytes: bytes) -> tuple[np.ndarray, np.ndarray]:
    """Convert a DICOM image into synthetic k-space + return original as ground truth.

    Returns:
        (kspace, ground_truth)
        - kspace: complex64, shape (H, W), fftshifted
        - ground_truth: float32, shape (H, W), normalized to [0, 1]
    """
    ds = pydicom.dcmread(BytesIO(dicom_bytes))
    image = ds.pixel_array.astype(np.float32)
    # Normalize ground truth to [0, 1]
    if image.max() > 0:
        image_norm = image / image.max()
    else:
        image_norm = image
    kspace = np.fft.fftshift(np.fft.fft2(image_norm)).astype(np.complex64)
    return kspace, image_norm
```

### 6.4 `metrics.py`

```python
import numpy as np

def psnr(reconstructed: np.ndarray, ground_truth: np.ndarray) -> float:
    """Peak signal-to-noise ratio in dB. Both arrays normalized to same scale."""
    ...

def ssim(reconstructed: np.ndarray, ground_truth: np.ndarray) -> float:
    """Structural similarity index. Wraps scikit-image's ssim with default params."""
    ...
```

Behavior:
- Both functions normalize their inputs to [0, 1] before computing.
- `psnr` uses `MAX = 1.0` for the formula `20 * log10(MAX / sqrt(MSE))`; clamps to 100 dB if MSE is below 1e-10.
- `ssim` calls `skimage.metrics.structural_similarity(..., data_range=1.0)`.

### 6.5 `dicom_writer.py`

```python
def image_to_mr_dicom(
    image: np.ndarray,
    *,
    source_name: str,
    patient_id: str = "RECON-001",
    study_description: str = "MRI Reconstruction",
    series_description: str = "Reconstructed",
) -> tuple[bytes, str, str, str]:
    """Build an MR DICOM from a uint16 image.

    Returns:
        (dicom_bytes, study_instance_uid, series_instance_uid, sop_instance_uid)
    """
```

Generates fresh UIDs for Study/Series/SOP. Writes `Modality=MR`, `PhotometricInterpretation=MONOCHROME2`, `BitsAllocated=16`, etc. Reuses Slice 1's synthetic generator pattern but is a standalone module here (don't import test fixtures from production code).

### 6.6 `job_runner.py`

```python
def run_job(job_id: UUID, tempfile_path: Path) -> None:
    """The FastAPI BackgroundTask body. Updates the DB row in place.

    Sync function on purpose: FastAPI BackgroundTasks runs sync callables in
    its threadpool, which is the right execution model for CPU-bound FFT work
    (it would block the event loop if defined as `async def`).
    """
```

Catches every exception. Always deletes the tempfile in a `finally:` block. Always sets a terminal `status` and `completed_at`.

## 7. Tech stack additions

| Layer | Tech | Version |
|---|---|---|
| HDF5 reader | `h5py` | ≥ 3.12 |
| SSIM | `scikit-image` | ≥ 0.24 |

Existing api-service stack (FastAPI, SQLAlchemy, Alembic, pydicom, pydantic, httpx, numpy, scipy via deps tree) covers everything else.

## 8. Repository changes

```text
services/api-service/
├── app/
│   ├── routes/
│   │   └── reconstruction.py                  # NEW
│   ├── services/
│   │   └── reconstruction/                    # NEW package
│   │       ├── __init__.py
│   │       ├── kspace_loader.py
│   │       ├── fft_reconstruct.py
│   │       ├── forward_fft.py
│   │       ├── metrics.py
│   │       ├── dicom_writer.py
│   │       └── job_runner.py
│   ├── models/
│   │   └── reconstruction.py                  # NEW: ReconstructionJob
│   ├── schemas/
│   │   └── reconstruction.py                  # NEW
│   └── alembic/versions/
│       └── 002_reconstruction_jobs.py         # NEW migration
├── pyproject.toml                             # MODIFY: add h5py, scikit-image
├── uv.lock                                    # regenerated
└── tests/
    ├── unit/
    │   ├── test_kspace_loader.py              # NEW (≥ 5 tests)
    │   ├── test_fft_reconstruct.py            # NEW (≥ 5 tests)
    │   ├── test_forward_fft.py                # NEW (≥ 4 tests)
    │   ├── test_metrics.py                    # NEW (≥ 5 tests)
    │   └── test_dicom_writer.py               # NEW (≥ 4 tests)
    └── integration/
        └── test_reconstruction_flow.py        # NEW (≥ 3 tests)

apps/web-viewer/
└── src/
    ├── api/reconstruction.ts                  # NEW
    ├── pages/ReconstructionPage.tsx           # NEW
    ├── components/
    │   ├── KspaceUploadDropzone.tsx           # NEW
    │   ├── ReconstructionJobTable.tsx         # NEW
    │   └── SideBySidePreview.tsx              # NEW
    ├── routes.tsx                             # MODIFY: add /reconstruction
    ├── components/Nav.tsx                     # MODIFY: add nav link
    └── types/index.ts                         # MODIFY: add ReconstructionJob type

scripts/
└── generate-synthetic-kspace.py               # NEW

docs/
├── qa-validation-plan.md                      # MODIFY: add TC-08
├── status.md                                  # MODIFY at end of slice
└── roadmap.md                                 # MODIFY at end of slice

README.md                                      # MODIFY: quickstart mention
```

## 9. UI requirements (web)

New page: **`/reconstruction`**. New top nav entry "Reconstruction" between "Upload" and "Audit".

### Page layout

```
┌──────────────────────────────────────────────────────────────────┐
│ Reconstruction                                                    │
├──────────────────────────────────────────────────────────────────┤
│ ┌────────────────────────────────────────────────────────────┐   │
│ │ Drop k-space file here (.npy / .npz / .h5)                 │   │
│ │ or click to pick                                           │   │
│ └────────────────────────────────────────────────────────────┘   │
│                                                                   │
│ Recent jobs                                                       │
│ ┌────────────┬──────────┬────────────┬──────┬──────┬──────────┐  │
│ │ Created    │ File     │ Status     │ PSNR │ SSIM │ Duration │  │
│ ├────────────┼──────────┼────────────┼──────┼──────┼──────────┤  │
│ │ 18:01      │ brain... │ ✓ done     │ 32.4 │ 0.87 │ 1.2s     │  │
│ │ 18:00      │ scan.h5  │ ⏳ running │  —   │  —   │  —       │  │
│ └────────────┴──────────┴────────────┴──────┴──────┴──────────┘  │
│   ↑ click row to expand                                           │
│                                                                   │
│ ┌── Expanded row: side-by-side preview ─────────────────────┐    │
│ │  ┌──────────┐  ┌──────────┐                                │    │
│ │  │ Original │  │ Recon    │                                │    │
│ │  │ (ground  │  │ (output) │                                │    │
│ │  │  truth)  │  │          │                                │    │
│ │  └──────────┘  └──────────┘                                │    │
│ │  PSNR: 32.4 dB    SSIM: 0.87                               │    │
│ │  Open reconstructed study →                                │    │
│ └────────────────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────────┘
```

Behavior:
- Job list polls `GET /api/reconstruction/jobs` every 2s when any job is `queued` or `running`. Polling stops when all current-page jobs are terminal.
- The "Original" preview only appears when `psnr_db` and `ssim` are non-null (proxy for ground-truth-was-present).
- The "Recon" preview is a `<img src="/api/instances/{output_orthanc_instance_id}/preview.png">`.
- "Open reconstructed study" → existing Slice 1 page `/studies/{output_dicom_uid}`.

## 10. API contract

All endpoints under `/api/reconstruction/`. JSON unless noted.

### `POST /api/reconstruction/jobs`

multipart/form-data: `file` field with `.npy`, `.npz`, or `.h5`.

Success (201):
```json
{
  "job_id": "uuid",
  "status": "queued",
  "input_file_name": "brain_kspace.npz",
  "input_format": "npz",
  "created_at": "2026-05-06T18:00:00Z"
}
```

Errors:
- 400 `invalid_kspace` — file isn't a parseable .npy/.npz/.h5
- 400 `unsupported_shape` — array isn't 2D after coil reduction
- 413 `file_too_large` — over 100 MB (env-configurable via `MAX_KSPACE_BYTES`)

### `GET /api/reconstruction/jobs/{job_id}`

```json
{
  "job_id": "uuid",
  "status": "completed",
  "input_file_name": "brain_kspace.npz",
  "input_format": "npz",
  "input_shape": "(64, 64)",
  "output_dicom_uid": "1.2.999...",
  "output_orthanc_instance_id": "abc-123",
  "psnr_db": 84.2,
  "ssim": 0.999,
  "duration_ms": 1240,
  "error_message": null,
  "created_at": "...",
  "started_at": "...",
  "completed_at": "..."
}
```

### `GET /api/reconstruction/jobs?limit=&offset=&status=`

```json
{
  "items": [ <ReconstructionJob>, ... ],
  "total": 42,
  "limit": 50,
  "offset": 0
}
```

## 11. Data model

```sql
CREATE TABLE reconstruction_jobs (
  id                          BIGSERIAL PRIMARY KEY,
  job_id                      UUID NOT NULL UNIQUE,
  status                      TEXT NOT NULL,    -- queued | running | completed | failed
  input_file_name             TEXT NOT NULL,
  input_format                TEXT NOT NULL,    -- npy | npz | h5
  input_shape                 TEXT,
  output_dicom_uid            TEXT,
  output_orthanc_instance_id  TEXT,
  psnr_db                     DOUBLE PRECISION,
  ssim                        DOUBLE PRECISION,
  duration_ms                 INTEGER,
  error_message               TEXT,
  created_at                  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  started_at                  TIMESTAMPTZ,
  completed_at                TIMESTAMPTZ
);
CREATE INDEX idx_recon_created_at ON reconstruction_jobs (created_at DESC);
CREATE INDEX idx_recon_status     ON reconstruction_jobs (status);
```

Alembic migration filename: `002_reconstruction_jobs.py`. Slice 1's `001_audit_events.py` stays untouched.

## 12. Testing strategy

### Unit (pytest, ≥ 23 new tests)

- `test_kspace_loader.py`:
  - `.npy` 2D complex array loads correctly
  - `.npz` with `kspace` + `ground_truth_image` returns both
  - `.npz` with only `kspace` returns ground_truth as None
  - `.h5` with single-coil 2D loads correctly
  - garbage bytes → `InvalidKspaceError`
  - 1D array → `UnsupportedShapeError`
- `test_fft_reconstruct.py`:
  - reconstruct of a known k-space yields expected uint16 magnitude shape
  - round-trip: forward_fft then reconstruct returns near-identical image (PSNR > 60 dB)
  - reconstruction handles complex64 input
  - reconstruction handles complex128 input
  - empty/zero k-space returns zero image (no NaN)
- `test_forward_fft.py`:
  - DICOM bytes → kspace shape matches DICOM Rows×Columns
  - kspace dtype is complex64
  - ground_truth is normalized to [0, 1]
  - non-DICOM bytes raise an exception
- `test_metrics.py`:
  - `psnr(a, a) >= 100` (identical → max)
  - `psnr(a, b)` is finite for non-identical
  - `ssim(a, a) == 1.0` (identical → max)
  - `ssim` decreases when noise is added
  - both functions normalize internally so absolute scale doesn't matter
- `test_dicom_writer.py`:
  - output bytes are parseable by pydicom
  - parsed DICOM has Modality=MR, BitsAllocated=16, MONOCHROME2
  - parsed DICOM has fresh StudyInstanceUID/SeriesInstanceUID/SOPInstanceUID (not equal to inputs)
  - pixel_array round-trips through write+read

### Integration (testcontainers, ≥ 3 new tests)

- POST a forward-generated `.npz` → poll until `completed` → assert PSNR > 60 dB → assert output DICOM appears in Orthanc.
- POST garbage bytes → 400 with `code: invalid_kspace`.
- POST a `.npy` (no ground truth) → completes with `psnr_db=null` and `ssim=null`.

### Manual smoke (recorded in `docs/qa-validation-plan.md` TC-08)

1. Generate synthetic k-space:
   ```
   uv run --directory services/api-service python ../../scripts/generate-synthetic-kspace.py \
       data/sample-dicom/real-multislice/slice_010.dcm /tmp/brain.npz
   ```
2. Open `/reconstruction`, drop `/tmp/brain.npz`.
3. See job appear in the table; status transitions queued → running → completed.
4. Expand the row; see side-by-side preview; PSNR ~ 80+ dB; SSIM ~ 0.999.
5. Click "Open reconstructed study" → goes to `/studies/{uid}` and shows the reconstructed image.
6. Verify the same study appears under `/studies` listing.

### CI

The existing `python` job in `.github/workflows/ci.yml` runs the new unit + integration tests. The integration test for reconstruction uses the existing testcontainers fixtures; no CI changes needed.

## 13. Non-functional requirements

- Reconstruction of a 256×256 single-slice k-space: < 2 s end-to-end on a developer laptop.
- POST returns within 200 ms (file write + DB insert; reconstruction runs in BackgroundTasks after response).
- Job list query (50 rows): < 500 ms.
- Memory: < 500 MB during a single 256×256 reconstruction.
- Upload size limit: 100 MB by default (env-configurable).

## 14. Risks and mitigations

| Risk | Mitigation |
|---|---|
| BackgroundTasks runs in the same process; long jobs starve the event loop | `run_job` is a sync `def`, so FastAPI executes it in its threadpool (not the event loop). Documented in `job_runner.py`. |
| h5py wheels can be heavy / OS-specific | Standard scientific Python; well-supported on macOS/Linux. CI uses Linux runners. |
| fastMRI .h5 files are huge (multi-GB) | 100 MB upload limit by default; document in README. Real fastMRI testing is a manual exercise, not a CI gate. |
| FFT is fast on small inputs but quadratic on large ones | Limit max input dimension to 2048×2048; reject larger with `unsupported_shape`. |
| Multiple concurrent BackgroundTasks could exhaust resources | Slice 9's queue + worker pool will solve this properly. For Slice 3, document that concurrent reconstructions are unbounded and not load-tested. |
| Orthanc upload during job_runner could fail mid-flight | Wrapped in try/except like Slice 1's upload; sets `status=failed` with the Orthanc error. |
| PSNR formula divides by MSE; identical inputs produce MSE=0 | Clamp to 100 dB if MSE < 1e-10. |
| Tempfile cleanup if process crashes mid-job | Tempdir uses a known prefix; a startup hook can sweep stale `*.recon.tmp` files older than 1h. (Document; don't implement in this slice.) |

## 15. Definition of Done

Slice 3 is done when **all** of the following are true:

1. Alembic migration `002_reconstruction_jobs` runs cleanly on a fresh DB; table exists with all 14 columns and 2 indexes.
2. `services/api-service/app/services/reconstruction/` package exists with `kspace_loader`, `fft_reconstruct`, `forward_fft`, `metrics`, `dicom_writer`, `job_runner` modules.
3. `scripts/generate-synthetic-kspace.py <input.dcm> <output.npz>` produces a `.npz` with `kspace` + `ground_truth_image` keys.
4. `POST /api/reconstruction/jobs` accepts `.npy`/`.npz`/`.h5`; rejects garbage with `invalid_kspace`; rejects oversized files with `file_too_large`; returns 201 with job_id within 200 ms.
5. Reconstruction runs in FastAPI BackgroundTasks; `GET /api/reconstruction/jobs/{id}` reflects `running → completed | failed` transitions.
6. On success: output DICOM has fresh UIDs, is uploaded to Orthanc, `output_orthanc_instance_id` is recorded; the new study appears at `/api/studies` and `/studies` in the web app.
7. PSNR + SSIM are computed when ground truth is present (`.npz` with `ground_truth_image` key); stored in DB; null when absent.
8. `/reconstruction` page in the web viewer shows: dropzone, paginated job table with status/PSNR/SSIM/duration columns, side-by-side preview on row expand, polling while jobs are non-terminal.
9. Side-by-side preview's "Open reconstructed study" link goes to the existing `/studies/{uid}` page and renders the reconstructed image.
10. Unit tests: ≥ 23 new tests covering all six pure-logic modules.
11. Integration tests: ≥ 3 new tests covering the full POST → poll → completed → Orthanc flow.
12. CI's existing `python` job runs the new tests and stays green.
13. `web-viewer` typecheck + production build still pass.
14. `docs/qa-validation-plan.md` has TC-08 for reconstruction.
15. README quickstart mentions `/reconstruction`.
16. `docs/status.md` and `docs/roadmap.md` mark Slice 3 done.
17. This spec is committed and referenced from `docs/status.md`.

## 16. Future phases (slight refinement)

| Slice | Scope | Change vs. previous roadmap |
|---|---|---|
| 4 | MinIO + signed-URL upload flow + checksum-validated object storage | unchanged |
| 5 | De-identification scanner | unchanged |
| 6 | Auth (JWT, RBAC) + studies/series/instances cache | unchanged |
| 7 | Prom/Grafana | unchanged |
| 8 | Cornerstone3D viewer + multiplanar + measurements | unchanged |
| 9 | Background job queue (Redis + Celery/RQ); upgrade reconstruction to use the queue | Now has a concrete first user (reconstruction) |
| 9.5 (NEW) | Advanced reconstruction: undersampling sim, compressed sensing, optional U-Net | Split out from old "advanced" bucket; meaningful enough for its own slice |
| 10+ | K8s, real cloud | unchanged |

Slice 3 introduces one new future-phase entry (9.5) reflecting the deferral of advanced reconstruction techniques.
