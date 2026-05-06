# Slice 2 — Qt Desktop Viewer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a standalone PySide6 desktop app that loads DICOM folders, browses studies/series/instances, navigates slices, applies window/level (with clinical presets), zooms/pans, and optionally uploads instances to the Slice 1 backend — all without Docker or any backend dependency at launch.

**Architecture:** Single-process Qt app. Pure-logic modules (loader, series, window/level) tested with pytest. Widgets wired together by `MainWindow` via Qt signals. Folder load and HTTP upload run in background `QThread`s. All series pixel data held in memory as numpy `[N,H,W]` after series selection. Settings persisted via `QSettings`. Compressed DICOMs supported via `pylibjpeg`.

**Tech Stack:** Python 3.12, PySide6 ≥ 6.8, pyqtgraph ≥ 0.13, pydicom ≥ 3.0, pylibjpeg + pylibjpeg-libjpeg + pylibjpeg-openjpeg, numpy ≥ 2.1, httpx ≥ 0.27, pytest ≥ 8.3, ruff, uv.

**Spec:** [`docs/superpowers/specs/2026-05-05-slice-2-qt-desktop-viewer-design.md`](../specs/2026-05-05-slice-2-qt-desktop-viewer-design.md)

**Branch:** `slice-2-qt-desktop-viewer` (off `main`, with Slice 1 already merged)

**Commit policy (from user, inherited from slice 1):** Small, incremental, logically-isolated commits. Each task in this plan produces 1–2 commits. Never combine unrelated changes. Never amend.

**TDD scope:** Pure-logic modules (`dicom/loader.py`, `dicom/series.py`, `dicom/window_level.py`, `upload/worker.py`) are written test-first per AD-S2-7. Qt widgets are written without unit tests (manual smoke only) — pytest-qt is explicitly out of scope for Slice 2.

---

## File structure

Created in this slice:

```text
apps/desktop-viewer/
├── pyproject.toml
├── uv.lock
├── README.md
├── app/
│   ├── __init__.py                # __version__
│   ├── main.py                    # entry point, sets Org/AppName, builds MainWindow
│   ├── main_window.py             # MainWindow: 3-panel layout, signal wiring, threads
│   ├── config.py                  # QSettings wrapper for api_url
│   ├── dicom/
│   │   ├── __init__.py
│   │   ├── loader.py              # scan_folder, is_dicom, dataclasses (StudyRef, SeriesRef, InstanceRef)
│   │   ├── series.py              # load_series, auto_window_level, LoadedSeries dataclass
│   │   └── window_level.py        # apply_window_level (numpy → uint8)
│   ├── widgets/
│   │   ├── __init__.py
│   │   ├── empty_state.py         # "Open folder…" / "Load sample data" placeholder
│   │   ├── browser_panel.py       # QTreeWidget with study/series/instance tree
│   │   ├── viewer_panel.py        # pyqtgraph ImageView + slice/W/L sliders + presets
│   │   ├── metadata_panel.py      # QTableWidget + Upload button + status label
│   │   └── settings_dialog.py     # QDialog with api_url QLineEdit
│   └── upload/
│       ├── __init__.py
│       └── worker.py              # UploadWorker(QThread) using httpx
└── tests/
    ├── __init__.py
    ├── unit/
    │   ├── __init__.py
    │   ├── test_loader.py
    │   ├── test_series.py
    │   ├── test_window_level.py
    │   └── test_upload_worker.py
    └── fixtures/
        ├── __init__.py
        └── make_test_series.py    # generates multi-instance synthetic series for tests
```

Modified in this slice:

```text
scripts/generate-synthetic-dicom.py     # add --count N + --output DIR flags
.github/workflows/ci.yml                # add desktop-viewer job
docs/status.md                          # mark slice 2 done at end of slice
docs/roadmap.md                         # mark slice 2 done at end of slice
```

Untouched: everything in `services/`, `infra/`, `apps/web-viewer/`, `tests/e2e/`.

---

## Phase A — Tooling

### Task A1: `pyproject.toml` + `uv sync`

**Files:**
- Create: `apps/desktop-viewer/pyproject.toml`
- Create: `apps/desktop-viewer/uv.lock` (generated)

- [ ] **Step 1: Write `apps/desktop-viewer/pyproject.toml`**

```toml
[project]
name = "neuroscan-desktop-viewer"
version = "0.1.0"
description = "NeuroScan Workstation Qt desktop DICOM viewer"
requires-python = ">=3.12"
dependencies = [
    "PySide6>=6.8",
    "pyqtgraph>=0.13",
    "pydicom>=3.0",
    "pylibjpeg>=2.0",
    "pylibjpeg-libjpeg>=2.1",
    "pylibjpeg-openjpeg>=2.2",
    "numpy>=2.1",
    "httpx>=0.27",
]

[dependency-groups]
dev = [
    "pytest>=8.3",
    "pytest-asyncio>=0.24",
    "respx>=0.21",
    "ruff>=0.7",
]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
addopts = "-ra --strict-markers"

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "I", "N", "UP", "B", "SIM"]

[tool.ruff.lint.per-file-ignores]
"tests/**/*.py" = ["N806"]
```

- [ ] **Step 2: Lock + verify**

```bash
mkdir -p apps/desktop-viewer
cd apps/desktop-viewer
uv sync
```

Expected: `.venv/` and `uv.lock` created. PySide6 wheels download (~75 MB on macOS Apple Silicon). No errors.

- [ ] **Step 3: Smoke verify Qt imports**

```bash
cd apps/desktop-viewer
uv run python -c "from PySide6 import QtCore, QtWidgets; import pyqtgraph; import pydicom; import numpy; print('OK', QtCore.qVersion())"
```

Expected: `OK 6.8.x` (or higher).

- [ ] **Step 4: Commit**

```bash
cd /Users/harshilvyas/Documents/Github\ Repos/NeuroScan
git add apps/desktop-viewer/pyproject.toml apps/desktop-viewer/uv.lock
git commit -m "feat(slice-2): add desktop-viewer pyproject with PySide6 + pydicom deps"
```

---

### Task A2: Extend `generate-synthetic-dicom.py` with `--count` and `--output`

**Files:**
- Modify: `scripts/generate-synthetic-dicom.py`

Slice 1's script writes one DICOM at a fixed path. Slice 2 needs to generate a multi-instance series so we can manually test slice navigation. We add two flags while preserving backward compatibility (the existing `OUTPUT_PATH` positional usage still works for `--count 1`).

- [ ] **Step 1: Replace the script**

```python
#!/usr/bin/env python3
"""Generate synthetic MR DICOM file(s).

Usage:
    # Single instance (slice 1 backward-compatible form):
    uv run --directory services/api-service python ../../scripts/generate-synthetic-dicom.py /tmp/x.dcm

    # Multi-instance series (slice 2):
    uv run --directory services/api-service python ../../scripts/generate-synthetic-dicom.py \\
        --count 32 --output /tmp/multi
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "services" / "api-service"))

import numpy as np  # noqa: E402
from pydicom.uid import generate_uid  # noqa: E402

from tests.fixtures.synthetic_dicom import make_synthetic_mr_dicom_bytes  # noqa: E402


def _gradient_pixels(rows: int, cols: int, slice_idx: int, n_slices: int) -> np.ndarray:
    """Per-slice gradient so navigation is visually obvious.

    Combines an X gradient with a Y gradient that shifts based on slice index.
    """
    x = np.linspace(0, 4095, cols, dtype=np.float32)
    y = np.linspace(0, 4095, rows, dtype=np.float32)
    xx, yy = np.meshgrid(x, y)
    phase = (slice_idx / max(n_slices - 1, 1)) * np.pi
    return ((xx + yy * np.cos(phase)) % 4096).astype(np.uint16)


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate synthetic MR DICOM(s).")
    parser.add_argument(
        "output",
        nargs="?",
        help="Output file path (single-instance mode) — required if --output not given.",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=1,
        help="Number of instances to generate (default: 1).",
    )
    parser.add_argument(
        "--output",
        dest="output_dir",
        help="Output directory (multi-instance mode) — required if --count > 1.",
    )
    parser.add_argument("--rows", type=int, default=64)
    parser.add_argument("--columns", type=int, default=64)
    args = parser.parse_args()

    if args.count == 1 and args.output and not args.output_dir:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        data = make_synthetic_mr_dicom_bytes(rows=args.rows, columns=args.columns)
        out.write_bytes(data)
        print(f"Wrote {out} ({out.stat().st_size} bytes)")
        return 0

    if args.count > 1:
        if not args.output_dir:
            print("--output DIR is required when --count > 1", file=sys.stderr)
            return 2
        out_dir = Path(args.output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        study_uid = generate_uid()
        series_uid = generate_uid()
        for i in range(args.count):
            sop_uid = generate_uid()
            pixels = _gradient_pixels(args.rows, args.columns, i, args.count)
            data = make_synthetic_mr_dicom_bytes(
                study_instance_uid=study_uid,
                series_instance_uid=series_uid,
                sop_instance_uid=sop_uid,
                rows=args.rows,
                columns=args.columns,
                pixel_array_override=pixels,
                instance_number=i + 1,
            )
            (out_dir / f"slice_{i:03d}.dcm").write_bytes(data)
        print(f"Wrote {args.count} instances to {out_dir}")
        return 0

    print("Specify either OUTPUT (single instance) or --count N --output DIR", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Update the synthetic fixture to accept overrides**

The script above passes `pixel_array_override` and `instance_number` to `make_synthetic_mr_dicom_bytes`. The existing helper at `services/api-service/tests/fixtures/synthetic_dicom.py` doesn't accept these yet. Modify it:

`services/api-service/tests/fixtures/synthetic_dicom.py`:
```python
"""Synthetic MR DICOM generator used by all tests.

Produces small but valid DICOM bytes that exercise the same code path as
real DICOM files (parsable by pydicom, has all required tags).
"""

from __future__ import annotations

from datetime import datetime
from io import BytesIO

import numpy as np
import pydicom
from pydicom.dataset import FileDataset, FileMetaDataset
from pydicom.uid import ExplicitVRLittleEndian, generate_uid


def make_synthetic_mr_dicom_bytes(
    *,
    study_instance_uid: str | None = None,
    series_instance_uid: str | None = None,
    sop_instance_uid: str | None = None,
    rows: int = 16,
    columns: int = 16,
    patient_id: str = "TEST-001",
    modality: str = "MR",
    instance_number: int = 1,
    pixel_array_override: np.ndarray | None = None,
) -> bytes:
    """Generate a valid MR DICOM as bytes."""
    study_uid = study_instance_uid or generate_uid()
    series_uid = series_instance_uid or generate_uid()
    sop_uid = sop_instance_uid or generate_uid()

    file_meta = FileMetaDataset()
    file_meta.MediaStorageSOPClassUID = pydicom.uid.MRImageStorage
    file_meta.MediaStorageSOPInstanceUID = sop_uid
    file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
    file_meta.ImplementationClassUID = generate_uid()

    ds = FileDataset("synthetic.dcm", {}, file_meta=file_meta, preamble=b"\0" * 128)
    ds.SOPClassUID = pydicom.uid.MRImageStorage
    ds.SOPInstanceUID = sop_uid
    ds.StudyInstanceUID = study_uid
    ds.SeriesInstanceUID = series_uid
    ds.PatientID = patient_id
    ds.PatientName = "Synthetic^Test"
    ds.Modality = modality
    now = datetime.now()
    ds.StudyDate = now.strftime("%Y%m%d")
    ds.StudyTime = now.strftime("%H%M%S")
    ds.StudyDescription = "Synthetic Test Study"
    ds.SeriesDescription = "Synthetic Test Series"
    ds.SeriesNumber = 1
    ds.InstanceNumber = instance_number
    ds.Rows = rows
    ds.Columns = columns
    ds.BitsAllocated = 16
    ds.BitsStored = 16
    ds.HighBit = 15
    ds.PixelRepresentation = 0
    ds.SamplesPerPixel = 1
    ds.PhotometricInterpretation = "MONOCHROME2"

    if pixel_array_override is not None:
        if pixel_array_override.shape != (rows, columns):
            raise ValueError(
                f"pixel_array_override shape {pixel_array_override.shape} "
                f"does not match rows×columns ({rows}×{columns})"
            )
        pixel_array = pixel_array_override.astype(np.uint16)
    else:
        seed = abs(hash(sop_uid)) % (2**32)
        pixel_array = np.random.default_rng(seed).integers(
            0, 4096, (rows, columns), dtype=np.uint16
        )
    ds.PixelData = pixel_array.tobytes()
    ds.is_little_endian = True
    ds.is_implicit_VR = False

    buf = BytesIO()
    ds.save_as(buf, write_like_original=False)
    return buf.getvalue()


def make_dicom_missing_modality() -> bytes:
    """Generate a DICOM that is structurally valid but missing the Modality tag.

    Used to test the missing-required-tag negative path.
    """
    raw = make_synthetic_mr_dicom_bytes()
    ds = pydicom.dcmread(BytesIO(raw))
    del ds.Modality
    buf = BytesIO()
    ds.save_as(buf, write_like_original=False)
    return buf.getvalue()
```

The change is: added `instance_number` and `pixel_array_override` parameters; default behavior unchanged.

- [ ] **Step 3: Verify slice 1 tests still pass**

```bash
cd services/api-service
uv run pytest tests/unit/ -q
```

Expected: 24 passed.

- [ ] **Step 4: Smoke test the new flags**

```bash
cd /Users/harshilvyas/Documents/Github\ Repos/NeuroScan
mkdir -p /tmp/multi_test
uv run --directory services/api-service python ../../scripts/generate-synthetic-dicom.py --count 4 --output /tmp/multi_test --rows 32 --columns 32
ls -la /tmp/multi_test
uv run --directory services/api-service python -c "
import pydicom
from pathlib import Path
files = sorted(Path('/tmp/multi_test').glob('*.dcm'))
assert len(files) == 4, f'expected 4 files, got {len(files)}'
study_uids = set()
series_uids = set()
for f in files:
    ds = pydicom.dcmread(f)
    study_uids.add(ds.StudyInstanceUID)
    series_uids.add(ds.SeriesInstanceUID)
    assert ds.Rows == 32 and ds.Columns == 32
assert len(study_uids) == 1, 'all instances should share StudyInstanceUID'
assert len(series_uids) == 1, 'all instances should share SeriesInstanceUID'
print('OK 4 instances, shared study/series UIDs')
"
rm -rf /tmp/multi_test
```

Expected: `OK 4 instances, shared study/series UIDs`.

- [ ] **Step 5: Commit**

```bash
git add scripts/generate-synthetic-dicom.py services/api-service/tests/fixtures/synthetic_dicom.py
git commit -m "feat(slice-2): extend synthetic DICOM generator with --count and --output

- Add --count N + --output DIR flags for multi-instance series generation
- Slices share StudyInstanceUID + SeriesInstanceUID, distinct SOPInstanceUID
- Per-slice gradient pixel pattern so slice navigation is visually obvious
- Backward compatible with slice 1's positional OUTPUT_PATH usage"
```

---

## Phase B — TDD pure-logic modules

### Task B1: Test fixture for multi-instance synthetic series (used by unit tests)

**Files:**
- Create: `apps/desktop-viewer/tests/__init__.py`
- Create: `apps/desktop-viewer/tests/fixtures/__init__.py`
- Create: `apps/desktop-viewer/tests/fixtures/make_test_series.py`

This wraps the api-service fixture so desktop-viewer tests can import it without depending on the api-service venv. It writes synthetic DICOM files to a temp directory and returns paths.

- [ ] **Step 1: Both `__init__.py` files** — empty.

- [ ] **Step 2: Write `tests/fixtures/make_test_series.py`**

```python
"""Helpers to write synthetic DICOM files to disk for desktop-viewer tests.

This module is independent of the api-service venv. We re-implement a minimal
synthetic generator here rather than imposing cross-project imports.
"""

from __future__ import annotations

from datetime import datetime
from io import BytesIO
from pathlib import Path

import numpy as np
import pydicom
from pydicom.dataset import FileDataset, FileMetaDataset
from pydicom.uid import ExplicitVRLittleEndian, generate_uid


def _make_one_dicom_bytes(
    *,
    study_uid: str,
    series_uid: str,
    sop_uid: str,
    instance_number: int,
    rows: int = 32,
    columns: int = 32,
    series_description: str = "Test Series",
    modality: str = "MR",
    patient_id: str = "TEST-001",
) -> bytes:
    file_meta = FileMetaDataset()
    file_meta.MediaStorageSOPClassUID = pydicom.uid.MRImageStorage
    file_meta.MediaStorageSOPInstanceUID = sop_uid
    file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
    file_meta.ImplementationClassUID = generate_uid()

    ds = FileDataset("test.dcm", {}, file_meta=file_meta, preamble=b"\0" * 128)
    ds.SOPClassUID = pydicom.uid.MRImageStorage
    ds.SOPInstanceUID = sop_uid
    ds.StudyInstanceUID = study_uid
    ds.SeriesInstanceUID = series_uid
    ds.PatientID = patient_id
    ds.PatientName = "Test^Subject"
    ds.Modality = modality
    now = datetime.now()
    ds.StudyDate = now.strftime("%Y%m%d")
    ds.StudyDescription = "Desktop Viewer Test Study"
    ds.SeriesDescription = series_description
    ds.SeriesNumber = 1
    ds.InstanceNumber = instance_number
    ds.Rows = rows
    ds.Columns = columns
    ds.BitsAllocated = 16
    ds.BitsStored = 16
    ds.HighBit = 15
    ds.PixelRepresentation = 0
    ds.SamplesPerPixel = 1
    ds.PhotometricInterpretation = "MONOCHROME2"

    seed = abs(hash(sop_uid)) % (2**32)
    pixels = np.random.default_rng(seed).integers(0, 4096, (rows, columns), dtype=np.uint16)
    ds.PixelData = pixels.tobytes()
    ds.is_little_endian = True
    ds.is_implicit_VR = False

    buf = BytesIO()
    ds.save_as(buf, write_like_original=False)
    return buf.getvalue()


def write_test_series(
    out_dir: Path,
    *,
    n_instances: int = 4,
    series_description: str = "Test Series",
    rows: int = 32,
    columns: int = 32,
) -> tuple[str, str, list[Path]]:
    """Write a series of N DICOM files into out_dir.

    Returns (study_instance_uid, series_instance_uid, list_of_file_paths).
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    study_uid = generate_uid()
    series_uid = generate_uid()
    paths: list[Path] = []
    for i in range(n_instances):
        sop_uid = generate_uid()
        data = _make_one_dicom_bytes(
            study_uid=study_uid,
            series_uid=series_uid,
            sop_uid=sop_uid,
            instance_number=i + 1,
            rows=rows,
            columns=columns,
            series_description=series_description,
        )
        path = out_dir / f"slice_{i:03d}.dcm"
        path.write_bytes(data)
        paths.append(path)
    return study_uid, series_uid, paths


def write_two_studies(out_dir: Path) -> dict:
    """Write two separate studies (different StudyInstanceUIDs) into the same dir.

    Useful for testing folder scanning + grouping. Returns a dict describing what was written.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    s1_study, s1_series, s1_paths = write_test_series(
        out_dir / "studyA", n_instances=3, series_description="Study A Series"
    )
    s2_study, s2_series, s2_paths = write_test_series(
        out_dir / "studyB", n_instances=2, series_description="Study B Series"
    )
    return {
        "study_a": {"study_uid": s1_study, "series_uid": s1_series, "paths": s1_paths},
        "study_b": {"study_uid": s2_study, "series_uid": s2_series, "paths": s2_paths},
    }
```

- [ ] **Step 3: Sanity check the fixture**

```bash
cd apps/desktop-viewer
uv run python -c "
from pathlib import Path
import tempfile
from tests.fixtures.make_test_series import write_test_series
with tempfile.TemporaryDirectory() as td:
    study, series, paths = write_test_series(Path(td), n_instances=3)
    assert len(paths) == 3
    assert all(p.exists() for p in paths)
    print('OK', len(paths), 'files,', study[:30], '...')
"
```

Expected: `OK 3 files, 1.2.826...`.

- [ ] **Step 4: Commit**

```bash
cd /Users/harshilvyas/Documents/Github\ Repos/NeuroScan
git add apps/desktop-viewer/tests/__init__.py apps/desktop-viewer/tests/fixtures/
git commit -m "test(slice-2): add multi-instance synthetic DICOM fixture for desktop-viewer tests"
```

---

### Task B2: TDD `dicom/loader.py`

**Files:**
- Create: `apps/desktop-viewer/tests/unit/__init__.py`
- Create: `apps/desktop-viewer/tests/unit/test_loader.py`
- Create: `apps/desktop-viewer/app/__init__.py`
- Create: `apps/desktop-viewer/app/dicom/__init__.py`
- Create: `apps/desktop-viewer/app/dicom/loader.py`

- [ ] **Step 1: Write `app/__init__.py`**

```python
__version__ = "0.1.0"
```

- [ ] **Step 2: Write `app/dicom/__init__.py`** — empty.

- [ ] **Step 3: Write `tests/unit/__init__.py`** — empty.

- [ ] **Step 4: Write the failing tests**

`apps/desktop-viewer/tests/unit/test_loader.py`:
```python
from pathlib import Path

import pytest

from app.dicom.loader import (
    InstanceRef,
    SeriesRef,
    StudyRef,
    is_dicom,
    scan_folder,
)
from tests.fixtures.make_test_series import write_test_series, write_two_studies


def test_scan_folder_empty_returns_empty_list(tmp_path: Path):
    assert scan_folder(tmp_path) == []


def test_scan_folder_skips_non_dicom_silently(tmp_path: Path):
    (tmp_path / "notes.txt").write_text("hello")
    (tmp_path / "image.png").write_bytes(b"\x89PNG-fake")
    assert scan_folder(tmp_path) == []


def test_scan_folder_groups_one_series(tmp_path: Path):
    study_uid, series_uid, paths = write_test_series(tmp_path, n_instances=4)
    studies = scan_folder(tmp_path)
    assert len(studies) == 1
    s = studies[0]
    assert isinstance(s, StudyRef)
    assert s.study_instance_uid == study_uid
    assert s.patient_id == "TEST-001"
    assert len(s.series) == 1
    series = s.series[0]
    assert isinstance(series, SeriesRef)
    assert series.series_instance_uid == series_uid
    assert series.modality == "MR"
    assert len(series.instances) == 4


def test_scan_folder_sorts_instances_by_instance_number(tmp_path: Path):
    write_test_series(tmp_path, n_instances=5)
    studies = scan_folder(tmp_path)
    instances = studies[0].series[0].instances
    numbers = [i.instance_number for i in instances]
    assert numbers == sorted(numbers)


def test_scan_folder_groups_two_studies(tmp_path: Path):
    info = write_two_studies(tmp_path)
    studies = scan_folder(tmp_path)
    assert len(studies) == 2
    uids = {s.study_instance_uid for s in studies}
    assert uids == {info["study_a"]["study_uid"], info["study_b"]["study_uid"]}


def test_scan_folder_recurses_into_subdirectories(tmp_path: Path):
    subdir = tmp_path / "deep" / "nested" / "path"
    write_test_series(subdir, n_instances=2)
    studies = scan_folder(tmp_path)
    assert len(studies) == 1
    assert len(studies[0].series[0].instances) == 2


def test_instance_ref_carries_file_path(tmp_path: Path):
    _, _, paths = write_test_series(tmp_path, n_instances=2)
    studies = scan_folder(tmp_path)
    instance_paths = {i.file_path for i in studies[0].series[0].instances}
    assert instance_paths == set(paths)


def test_is_dicom_recognizes_valid_file(tmp_path: Path):
    _, _, paths = write_test_series(tmp_path, n_instances=1)
    assert is_dicom(paths[0]) is True


def test_is_dicom_rejects_text_file(tmp_path: Path):
    text_path = tmp_path / "fake.dcm"
    text_path.write_text("this is not a DICOM at all even with the .dcm extension")
    assert is_dicom(text_path) is False


def test_instance_ref_dataclass_is_frozen():
    ref = InstanceRef(
        file_path=Path("/x.dcm"),
        sop_instance_uid="1.2.3",
        instance_number=1,
        rows=64,
        columns=64,
    )
    with pytest.raises(Exception):
        ref.sop_instance_uid = "different"  # type: ignore[misc]
```

- [ ] **Step 5: Run tests, expect FAIL (import error)**

```bash
cd apps/desktop-viewer
uv run pytest tests/unit/test_loader.py -v
```

Expected: ImportError on `app.dicom.loader`.

- [ ] **Step 6: Write `app/dicom/loader.py`**

```python
"""DICOM folder scanner.

Walks a directory recursively, parses any file pydicom can read, and groups
the results into a Study → Series → Instance hierarchy. Pure logic — no Qt.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pydicom
from pydicom.errors import InvalidDicomError


@dataclass(frozen=True)
class InstanceRef:
    file_path: Path
    sop_instance_uid: str
    instance_number: int | None
    rows: int | None
    columns: int | None


@dataclass(frozen=True)
class SeriesRef:
    series_instance_uid: str
    series_description: str | None
    modality: str | None
    series_number: int | None
    instances: tuple[InstanceRef, ...]


@dataclass(frozen=True)
class StudyRef:
    study_instance_uid: str
    patient_id: str | None
    patient_name: str | None
    study_date: str | None
    study_description: str | None
    series: tuple[SeriesRef, ...]


def is_dicom(path: Path) -> bool:
    """Quick header check — no full parse, no pixel decode."""
    try:
        with open(path, "rb") as f:
            f.seek(128)
            return f.read(4) == b"DICM"
    except OSError:
        return False


def _read_metadata(path: Path) -> pydicom.Dataset | None:
    try:
        return pydicom.dcmread(path, stop_before_pixels=True, force=False)
    except (InvalidDicomError, OSError, Exception):
        return None


def _str_or_none(ds: pydicom.Dataset, tag: str) -> str | None:
    value = getattr(ds, tag, None)
    if value in (None, ""):
        return None
    return str(value)


def _int_or_none(ds: pydicom.Dataset, tag: str) -> int | None:
    value = getattr(ds, tag, None)
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def scan_folder(root: Path) -> list[StudyRef]:
    """Walk root recursively, parse every file with pydicom, group hierarchically.

    Returns a list of StudyRef. Files that are not parseable as DICOM are silently
    skipped. Within a series, instances are sorted by InstanceNumber (None last,
    then by filename).
    """
    if not root.exists() or not root.is_dir():
        return []

    by_study: dict[str, dict] = {}

    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if not is_dicom(path):
            continue
        ds = _read_metadata(path)
        if ds is None:
            continue
        study_uid = _str_or_none(ds, "StudyInstanceUID")
        series_uid = _str_or_none(ds, "SeriesInstanceUID")
        sop_uid = _str_or_none(ds, "SOPInstanceUID")
        if not (study_uid and series_uid and sop_uid):
            continue

        study_entry = by_study.setdefault(
            study_uid,
            {
                "study_instance_uid": study_uid,
                "patient_id": _str_or_none(ds, "PatientID"),
                "patient_name": _str_or_none(ds, "PatientName"),
                "study_date": _str_or_none(ds, "StudyDate"),
                "study_description": _str_or_none(ds, "StudyDescription"),
                "series": {},
            },
        )

        series_entry = study_entry["series"].setdefault(
            series_uid,
            {
                "series_instance_uid": series_uid,
                "series_description": _str_or_none(ds, "SeriesDescription"),
                "modality": _str_or_none(ds, "Modality"),
                "series_number": _int_or_none(ds, "SeriesNumber"),
                "instances": [],
            },
        )

        series_entry["instances"].append(
            InstanceRef(
                file_path=path,
                sop_instance_uid=sop_uid,
                instance_number=_int_or_none(ds, "InstanceNumber"),
                rows=_int_or_none(ds, "Rows"),
                columns=_int_or_none(ds, "Columns"),
            )
        )

    studies: list[StudyRef] = []
    for study_data in by_study.values():
        series_list: list[SeriesRef] = []
        for series_data in study_data["series"].values():
            sorted_instances = tuple(
                sorted(
                    series_data["instances"],
                    key=lambda i: (
                        i.instance_number if i.instance_number is not None else 1_000_000,
                        str(i.file_path),
                    ),
                )
            )
            series_list.append(
                SeriesRef(
                    series_instance_uid=series_data["series_instance_uid"],
                    series_description=series_data["series_description"],
                    modality=series_data["modality"],
                    series_number=series_data["series_number"],
                    instances=sorted_instances,
                )
            )
        studies.append(
            StudyRef(
                study_instance_uid=study_data["study_instance_uid"],
                patient_id=study_data["patient_id"],
                patient_name=study_data["patient_name"],
                study_date=study_data["study_date"],
                study_description=study_data["study_description"],
                series=tuple(series_list),
            )
        )
    return studies
```

- [ ] **Step 7: Run tests, expect PASS**

```bash
cd apps/desktop-viewer
uv run pytest tests/unit/test_loader.py -v
```

Expected: 9 passed.

- [ ] **Step 8: Commit**

```bash
cd /Users/harshilvyas/Documents/Github\ Repos/NeuroScan
git add apps/desktop-viewer/app/__init__.py apps/desktop-viewer/app/dicom/__init__.py apps/desktop-viewer/app/dicom/loader.py apps/desktop-viewer/tests/unit/__init__.py apps/desktop-viewer/tests/unit/test_loader.py
git commit -m "feat(slice-2): add DICOM folder scanner with study/series/instance grouping"
```

---

### Task B3: TDD `dicom/window_level.py`

**Files:**
- Create: `apps/desktop-viewer/tests/unit/test_window_level.py`
- Create: `apps/desktop-viewer/app/dicom/window_level.py`

- [ ] **Step 1: Write the failing tests**

`apps/desktop-viewer/tests/unit/test_window_level.py`:
```python
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
```

- [ ] **Step 2: Run, expect FAIL**

```bash
cd apps/desktop-viewer
uv run pytest tests/unit/test_window_level.py -v
```

- [ ] **Step 3: Write `app/dicom/window_level.py`**

```python
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
```

- [ ] **Step 4: Run, expect PASS**

```bash
uv run pytest tests/unit/test_window_level.py -v
```

Expected: 7 passed.

- [ ] **Step 5: Commit**

```bash
cd /Users/harshilvyas/Documents/Github\ Repos/NeuroScan
git add apps/desktop-viewer/app/dicom/window_level.py apps/desktop-viewer/tests/unit/test_window_level.py
git commit -m "feat(slice-2): add window/level math (linear LUT to uint8)"
```

---

### Task B4: TDD `dicom/series.py`

**Files:**
- Create: `apps/desktop-viewer/tests/unit/test_series.py`
- Create: `apps/desktop-viewer/app/dicom/series.py`

- [ ] **Step 1: Write the failing tests**

`apps/desktop-viewer/tests/unit/test_series.py`:
```python
from pathlib import Path

import numpy as np
import pydicom

from app.dicom.loader import scan_folder
from app.dicom.series import LoadedSeries, auto_window_level, load_series
from tests.fixtures.make_test_series import write_test_series


def test_load_series_returns_volume_with_correct_shape(tmp_path: Path):
    write_test_series(tmp_path, n_instances=5, rows=32, columns=32)
    studies = scan_folder(tmp_path)
    series = studies[0].series[0]
    loaded = load_series(series)
    assert isinstance(loaded, LoadedSeries)
    assert loaded.volume.shape == (5, 32, 32)


def test_load_series_caches_raw_bytes(tmp_path: Path):
    write_test_series(tmp_path, n_instances=3)
    studies = scan_folder(tmp_path)
    loaded = load_series(studies[0].series[0])
    assert len(loaded.raw_bytes) == 3
    assert all(isinstance(b, bytes) for b in loaded.raw_bytes)
    assert all(len(b) > 0 for b in loaded.raw_bytes)


def test_load_series_caches_datasets(tmp_path: Path):
    write_test_series(tmp_path, n_instances=3)
    studies = scan_folder(tmp_path)
    loaded = load_series(studies[0].series[0])
    assert len(loaded.datasets) == 3
    assert all(isinstance(d, pydicom.Dataset) for d in loaded.datasets)
    assert loaded.datasets[0].SOPInstanceUID != loaded.datasets[1].SOPInstanceUID


def test_load_series_default_level_window_from_stats(tmp_path: Path):
    write_test_series(tmp_path, n_instances=3, rows=16, columns=16)
    studies = scan_folder(tmp_path)
    loaded = load_series(studies[0].series[0])
    # Synthetic data has uint16 values 0..4095 → level/window are sane numbers.
    assert isinstance(loaded.default_level, float)
    assert isinstance(loaded.default_window, float)
    assert loaded.default_window > 0


def test_auto_window_level_uses_dicom_tags_when_present():
    volume = np.array([[[100, 200], [300, 400]]], dtype=np.int16)

    class FakeDataset:
        WindowCenter = 250.0
        WindowWidth = 300.0

    level, window = auto_window_level(volume, [FakeDataset()])
    assert level == 250.0
    assert window == 300.0


def test_auto_window_level_handles_multi_value_window():
    """DICOM allows lists of window centers/widths; we take the first."""
    volume = np.array([[[100, 200]]], dtype=np.int16)

    class FakeDataset:
        WindowCenter = [40.0, 80.0]
        WindowWidth = [200.0, 400.0]

    level, window = auto_window_level(volume, [FakeDataset()])
    assert level == 40.0
    assert window == 200.0


def test_auto_window_level_falls_back_to_stats():
    rng = np.random.default_rng(0)
    volume = rng.integers(0, 4096, (10, 32, 32), dtype=np.uint16)

    class FakeDataset:
        pass  # no WindowCenter/WindowWidth

    level, window = auto_window_level(volume, [FakeDataset()])
    assert isinstance(level, float)
    assert isinstance(window, float)
    assert window > 0
    # Level should be near mean
    assert abs(level - float(np.mean(volume))) < 100
```

- [ ] **Step 2: Run, expect FAIL**

```bash
uv run pytest tests/unit/test_series.py -v
```

- [ ] **Step 3: Write `app/dicom/series.py`**

```python
"""Loading a series into memory: stack pixel data + cache datasets/bytes.

After load_series() returns, slice navigation requires zero disk I/O.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pydicom
from pydicom.dataset import Dataset

from app.dicom.loader import SeriesRef


@dataclass
class LoadedSeries:
    series_ref: SeriesRef
    volume: np.ndarray  # [N, H, W], native dtype
    raw_bytes: list[bytes]
    datasets: list[Dataset]
    default_level: float
    default_window: float


def load_series(series: SeriesRef) -> LoadedSeries:
    if not series.instances:
        raise ValueError(f"Series {series.series_instance_uid} has no instances")

    raw_bytes: list[bytes] = []
    datasets: list[Dataset] = []
    slices: list[np.ndarray] = []

    for inst in series.instances:
        data = inst.file_path.read_bytes()
        raw_bytes.append(data)
        ds = pydicom.dcmread(inst.file_path)
        datasets.append(ds)
        slices.append(ds.pixel_array)

    target_shape = slices[0].shape
    for i, s in enumerate(slices):
        if s.shape != target_shape:
            raise ValueError(
                f"Inconsistent slice shape: instance {i} has shape {s.shape}, "
                f"expected {target_shape}"
            )

    volume = np.stack(slices, axis=0)
    level, window = auto_window_level(volume, datasets)

    return LoadedSeries(
        series_ref=series,
        volume=volume,
        raw_bytes=raw_bytes,
        datasets=datasets,
        default_level=level,
        default_window=window,
    )


def _first_value(value: object) -> float | None:
    """DICOM lets WindowCenter/WindowWidth be a single value or a list. Take the first."""
    if value is None:
        return None
    if isinstance(value, list | tuple):
        if not value:
            return None
        try:
            return float(value[0])
        except (TypeError, ValueError):
            return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def auto_window_level(volume: np.ndarray, datasets: list[Dataset]) -> tuple[float, float]:
    """Determine default level and window for a volume.

    Prefers DICOM tags from the middle slice; falls back to mean ± 2*std clamped
    to the volume's actual range.
    """
    if datasets:
        mid = datasets[len(datasets) // 2]
        center = _first_value(getattr(mid, "WindowCenter", None))
        width = _first_value(getattr(mid, "WindowWidth", None))
        if center is not None and width is not None and width > 0:
            return center, width

    arr = volume.astype(np.float32)
    mean = float(np.mean(arr))
    std = float(np.std(arr))
    width = max(4.0 * std, 1.0)
    return mean, width
```

- [ ] **Step 4: Run, expect PASS**

```bash
uv run pytest tests/unit/test_series.py -v
```

Expected: 7 passed.

- [ ] **Step 5: Run all tests so far together**

```bash
uv run pytest tests/unit/ -v
```

Expected: 9 + 7 + 7 = 23 passed.

- [ ] **Step 6: Commit**

```bash
cd /Users/harshilvyas/Documents/Github\ Repos/NeuroScan
git add apps/desktop-viewer/app/dicom/series.py apps/desktop-viewer/tests/unit/test_series.py
git commit -m "feat(slice-2): add LoadedSeries with auto window/level computation"
```

---

## Phase C — Qt scaffold

### Task C1: `config.py` + `main.py` skeleton

**Files:**
- Create: `apps/desktop-viewer/app/config.py`
- Create: `apps/desktop-viewer/app/main.py`

These don't have unit tests (Qt-coupled) but are small and verified by smoke-launch.

- [ ] **Step 1: Write `app/config.py`**

```python
"""Persistent settings via QSettings.

Stored under the macOS plist `com.NeuroScan.DesktopViewer.plist`,
the Linux equivalent under `~/.config/NeuroScan/DesktopViewer.conf`,
or the Windows registry under HKCU\\Software\\NeuroScan\\DesktopViewer.
"""

from __future__ import annotations

from PySide6.QtCore import QSettings

DEFAULT_API_URL = "http://localhost:8000"


class Config:
    def __init__(self) -> None:
        self._settings = QSettings("NeuroScan", "DesktopViewer")

    @property
    def api_url(self) -> str:
        value = self._settings.value("api_url", DEFAULT_API_URL)
        return str(value) if value else DEFAULT_API_URL

    @api_url.setter
    def api_url(self, value: str) -> None:
        self._settings.setValue("api_url", value)
        self._settings.sync()
```

- [ ] **Step 2: Write `app/main.py` (placeholder MainWindow until C2)**

```python
"""NeuroScan Desktop Viewer entry point."""

from __future__ import annotations

import sys

from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QApplication


def main() -> int:
    QCoreApplication.setOrganizationName("NeuroScan")
    QCoreApplication.setOrganizationDomain("neuroscan.local")
    QCoreApplication.setApplicationName("DesktopViewer")

    app = QApplication(sys.argv)

    # MainWindow is wired in Task C2.
    from app.main_window import MainWindow

    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 3: Commit (cannot launch yet — main_window not implemented)**

```bash
cd /Users/harshilvyas/Documents/Github\ Repos/NeuroScan
git add apps/desktop-viewer/app/config.py apps/desktop-viewer/app/main.py
git commit -m "feat(slice-2): add app entry point and QSettings-backed Config"
```

---

### Task C2: `main_window.py` empty 3-panel layout

**Files:**
- Create: `apps/desktop-viewer/app/main_window.py`
- Create: `apps/desktop-viewer/app/widgets/__init__.py`

The widgets it depends on (browser, viewer, metadata, empty_state) don't exist yet. We use placeholder `QLabel`s so the window opens and we can verify the shell.

- [ ] **Step 1: Write `app/widgets/__init__.py`** — empty.

- [ ] **Step 2: Write `app/main_window.py`**

```python
"""Main application window: 3-panel layout, menus, status bar."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QStatusBar,
    QWidget,
)

from app.config import Config


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.config = Config()
        self.setWindowTitle("NeuroScan Desktop Viewer")
        self.resize(1400, 900)

        self._build_menus()
        self._build_status_bar()
        self._build_central_widget()

    def _build_menus(self) -> None:
        menu = self.menuBar()
        file_menu = menu.addMenu("&File")

        open_action = QAction("Open Folder…", self)
        open_action.setShortcut(QKeySequence.StandardKey.Open)
        open_action.triggered.connect(self._on_open_folder)
        file_menu.addAction(open_action)

        file_menu.addSeparator()

        quit_action = QAction("Quit", self)
        quit_action.setShortcut(QKeySequence.StandardKey.Quit)
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)

    def _build_status_bar(self) -> None:
        self._status = QStatusBar()
        self.setStatusBar(self._status)
        self._status.showMessage("Ready")

    def _build_central_widget(self) -> None:
        central = QWidget()
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Placeholder panels until D-tasks land.
        self._left = QLabel("Browser panel")
        self._left.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._left.setMinimumWidth(280)
        self._left.setStyleSheet("background:#f0f0f0; border-right:1px solid #ccc;")

        self._center = QLabel("Viewer panel")
        self._center.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._center.setStyleSheet("background:#1a1a1a; color:#888;")

        self._right = QLabel("Metadata panel")
        self._right.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._right.setMinimumWidth(320)
        self._right.setStyleSheet("background:#f0f0f0; border-left:1px solid #ccc;")

        layout.addWidget(self._left, 0)
        layout.addWidget(self._center, 1)
        layout.addWidget(self._right, 0)

        self.setCentralWidget(central)

    def _on_open_folder(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Open DICOM Folder")
        if path:
            self._status.showMessage(f"Selected: {path}")
```

- [ ] **Step 3: Smoke launch the app**

```bash
cd apps/desktop-viewer
uv run python -m app.main &
APP_PID=$!
sleep 3
# Verify window opened
ps -p $APP_PID > /dev/null && echo "App is running"
kill $APP_PID 2>/dev/null
wait $APP_PID 2>/dev/null
```

Expected: window opens with 3 placeholder panels and a menu bar. You can quit with ⌘Q.

- [ ] **Step 4: Commit**

```bash
cd /Users/harshilvyas/Documents/Github\ Repos/NeuroScan
git add apps/desktop-viewer/app/main_window.py apps/desktop-viewer/app/widgets/__init__.py
git commit -m "feat(slice-2): add MainWindow shell with 3-panel layout and File menu"
```

---

## Phase D — Widgets

### Task D1: `widgets/empty_state.py`

**Files:**
- Create: `apps/desktop-viewer/app/widgets/empty_state.py`

- [ ] **Step 1: Write the widget**

```python
"""Empty state shown in the viewer area before any folder is loaded."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QLabel, QPushButton, QVBoxLayout, QWidget


def _find_repo_sample_dir() -> Path | None:
    """Walk up from this file to find data/sample-dicom/real/ if present."""
    here = Path(__file__).resolve()
    for parent in [here, *here.parents]:
        candidate = parent / "data" / "sample-dicom" / "real"
        if candidate.is_dir() and any(candidate.iterdir()):
            return candidate
    return None


class EmptyState(QWidget):
    """Shown in the central panel when no folder is loaded."""

    openFolderRequested = Signal()
    loadSampleRequested = Signal(Path)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setStyleSheet("background:#1a1a1a; color:#bbb;")

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(16)

        label = QLabel("No folder loaded.")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setStyleSheet("font-size:16px; color:#ddd;")
        layout.addWidget(label)

        open_btn = QPushButton("Open folder…")
        open_btn.setMinimumWidth(180)
        open_btn.clicked.connect(self.openFolderRequested.emit)
        layout.addWidget(open_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        sample = _find_repo_sample_dir()
        if sample is not None:
            sample_btn = QPushButton(f"Load sample data ({sample.name}/)")
            sample_btn.setMinimumWidth(280)
            sample_btn.clicked.connect(lambda: self.loadSampleRequested.emit(sample))
            layout.addWidget(sample_btn, alignment=Qt.AlignmentFlag.AlignCenter)
```

- [ ] **Step 2: Commit**

```bash
git add apps/desktop-viewer/app/widgets/empty_state.py
git commit -m "feat(slice-2): add empty-state widget with sample-data shortcut"
```

---

### Task D2: `widgets/browser_panel.py`

**Files:**
- Create: `apps/desktop-viewer/app/widgets/browser_panel.py`

- [ ] **Step 1: Write the widget**

```python
"""Left-side study/series/instance tree."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHeaderView,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.dicom.loader import InstanceRef, SeriesRef, StudyRef

ROLE_KIND = Qt.ItemDataRole.UserRole
ROLE_PAYLOAD = Qt.ItemDataRole.UserRole + 1


class BrowserPanel(QWidget):
    seriesSelected = Signal(object)  # SeriesRef
    instanceSelected = Signal(object, int)  # SeriesRef, instance index within series

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._tree = QTreeWidget()
        self._tree.setHeaderLabels(["Studies / Series / Instances"])
        self._tree.header().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self._tree.itemSelectionChanged.connect(self._on_selection_changed)
        layout.addWidget(self._tree)

        self._studies: list[StudyRef] = []

    def set_studies(self, studies: list[StudyRef]) -> None:
        self._studies = studies
        self._tree.clear()
        for study in studies:
            study_item = QTreeWidgetItem(
                [self._study_label(study)],
            )
            study_item.setData(0, ROLE_KIND, "study")
            study_item.setData(0, ROLE_PAYLOAD, study)
            for series in study.series:
                series_item = QTreeWidgetItem([self._series_label(series)])
                series_item.setData(0, ROLE_KIND, "series")
                series_item.setData(0, ROLE_PAYLOAD, series)
                for idx, inst in enumerate(series.instances):
                    inst_item = QTreeWidgetItem([self._instance_label(inst, idx)])
                    inst_item.setData(0, ROLE_KIND, "instance")
                    inst_item.setData(0, ROLE_PAYLOAD, (series, idx))
                    series_item.addChild(inst_item)
                study_item.addChild(series_item)
            self._tree.addTopLevelItem(study_item)
            study_item.setExpanded(True)

    def _study_label(self, study: StudyRef) -> str:
        bits = []
        if study.patient_id:
            bits.append(study.patient_id)
        if study.study_date:
            bits.append(study.study_date)
        if study.study_description:
            bits.append(study.study_description)
        if not bits:
            bits.append(study.study_instance_uid[:24] + "…")
        return "📁 " + " · ".join(bits)

    def _series_label(self, series: SeriesRef) -> str:
        bits = []
        if series.modality:
            bits.append(series.modality)
        if series.series_number is not None:
            bits.append(f"#{series.series_number}")
        if series.series_description:
            bits.append(series.series_description)
        bits.append(f"({len(series.instances)} inst)")
        return "📂 " + " · ".join(bits)

    def _instance_label(self, inst: InstanceRef, idx: int) -> str:
        n = inst.instance_number if inst.instance_number is not None else idx + 1
        return f"  {n}"

    def _on_selection_changed(self) -> None:
        items = self._tree.selectedItems()
        if not items:
            return
        item = items[0]
        kind = item.data(0, ROLE_KIND)
        payload = item.data(0, ROLE_PAYLOAD)
        if kind == "series":
            self.seriesSelected.emit(payload)
        elif kind == "instance":
            series, idx = payload
            self.seriesSelected.emit(series)
            self.instanceSelected.emit(series, idx)
```

- [ ] **Step 2: Commit**

```bash
git add apps/desktop-viewer/app/widgets/browser_panel.py
git commit -m "feat(slice-2): add browser panel (study/series/instance tree)"
```

---

### Task D3: `widgets/viewer_panel.py`

**Files:**
- Create: `apps/desktop-viewer/app/widgets/viewer_panel.py`

- [ ] **Step 1: Write the widget**

```python
"""Center pane: pyqtgraph image view + slice/window/level sliders + presets."""

from __future__ import annotations

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeyEvent, QWheelEvent
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from app.dicom.series import LoadedSeries
from app.dicom.window_level import apply_window_level

WL_PRESETS: dict[str, tuple[float, float]] = {
    # name -> (window, level)
    "Brain": (80, 40),
    "Bone": (2000, 300),
    "Lung": (1500, -600),
    "Soft Tissue": (400, 50),
}


class ViewerPanel(QWidget):
    sliceChanged = Signal(int)  # current slice index

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._series: LoadedSeries | None = None
        self._slice_idx = 0
        self._level = 0.0
        self._window = 1.0

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self._image_view = pg.ImageView()
        self._image_view.ui.histogram.hide()
        self._image_view.ui.roiBtn.hide()
        self._image_view.ui.menuBtn.hide()
        self._image_view.getView().setBackgroundColor("#1a1a1a")
        self._image_view.installEventFilter(self)
        self._image_view.scene.installEventFilter(self)
        layout.addWidget(self._image_view, 1)

        layout.addWidget(self._build_slice_controls())
        layout.addWidget(self._build_wl_controls())
        layout.addWidget(self._build_preset_row())

        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def _build_slice_controls(self) -> QWidget:
        row = QWidget()
        h = QHBoxLayout(row)
        h.setContentsMargins(8, 0, 8, 0)
        self._slice_slider = QSlider(Qt.Orientation.Horizontal)
        self._slice_slider.setMinimum(0)
        self._slice_slider.setMaximum(0)
        self._slice_slider.valueChanged.connect(self._on_slice_slider_changed)
        self._slice_label = QLabel("Slice 0 / 0")
        self._slice_label.setMinimumWidth(110)
        h.addWidget(QLabel("Slice"))
        h.addWidget(self._slice_slider, 1)
        h.addWidget(self._slice_label)
        return row

    def _build_wl_controls(self) -> QWidget:
        row = QWidget()
        h = QHBoxLayout(row)
        h.setContentsMargins(8, 0, 8, 0)
        self._level_slider = QSlider(Qt.Orientation.Horizontal)
        self._window_slider = QSlider(Qt.Orientation.Horizontal)
        self._level_slider.valueChanged.connect(self._on_wl_slider_changed)
        self._window_slider.valueChanged.connect(self._on_wl_slider_changed)
        self._wl_label = QLabel("L: 0  W: 0")
        self._wl_label.setMinimumWidth(160)
        h.addWidget(QLabel("Level"))
        h.addWidget(self._level_slider, 1)
        h.addWidget(QLabel("Window"))
        h.addWidget(self._window_slider, 1)
        h.addWidget(self._wl_label)
        return row

    def _build_preset_row(self) -> QWidget:
        row = QWidget()
        h = QHBoxLayout(row)
        h.setContentsMargins(8, 0, 8, 4)
        for name in WL_PRESETS:
            btn = QPushButton(name)
            btn.clicked.connect(lambda _checked=False, n=name: self._apply_preset(n))
            h.addWidget(btn)
        default_btn = QPushButton("Default")
        default_btn.clicked.connect(self._reset_wl)
        h.addWidget(default_btn)
        h.addStretch(1)
        return row

    # ---- public API ----

    def set_series(self, loaded: LoadedSeries) -> None:
        self._series = loaded
        n = loaded.volume.shape[0]
        self._slice_idx = 0

        vmin = float(np.min(loaded.volume))
        vmax = float(np.max(loaded.volume))
        self._slice_slider.blockSignals(True)
        self._slice_slider.setMaximum(max(n - 1, 0))
        self._slice_slider.setValue(0)
        self._slice_slider.blockSignals(False)

        self._level_slider.blockSignals(True)
        self._window_slider.blockSignals(True)
        # Map level/window into integer slider range matching pixel-value extents.
        self._level_slider.setMinimum(int(vmin))
        self._level_slider.setMaximum(int(vmax))
        self._level_slider.setValue(int(loaded.default_level))
        self._window_slider.setMinimum(1)
        self._window_slider.setMaximum(int(max(vmax - vmin, 1)))
        self._window_slider.setValue(int(loaded.default_window))
        self._level_slider.blockSignals(False)
        self._window_slider.blockSignals(False)

        self._level = float(loaded.default_level)
        self._window = float(loaded.default_window)

        self._render()

    def set_slice_index(self, idx: int) -> None:
        if self._series is None:
            return
        idx = max(0, min(idx, self._series.volume.shape[0] - 1))
        if idx == self._slice_idx:
            return
        self._slice_idx = idx
        self._slice_slider.blockSignals(True)
        self._slice_slider.setValue(idx)
        self._slice_slider.blockSignals(False)
        self._render()
        self.sliceChanged.emit(idx)

    def current_slice_index(self) -> int:
        return self._slice_idx

    # ---- internals ----

    def _on_slice_slider_changed(self, v: int) -> None:
        self._slice_idx = v
        self._render()
        self.sliceChanged.emit(v)

    def _on_wl_slider_changed(self, _v: int) -> None:
        self._level = float(self._level_slider.value())
        self._window = float(max(self._window_slider.value(), 1))
        self._render()

    def _apply_preset(self, name: str) -> None:
        window, level = WL_PRESETS[name]
        self._level_slider.blockSignals(True)
        self._window_slider.blockSignals(True)
        self._level_slider.setValue(int(level))
        self._window_slider.setValue(int(window))
        self._level_slider.blockSignals(False)
        self._window_slider.blockSignals(False)
        self._level = float(level)
        self._window = float(window)
        self._render()

    def _reset_wl(self) -> None:
        if self._series is None:
            return
        self._level_slider.setValue(int(self._series.default_level))
        self._window_slider.setValue(int(self._series.default_window))

    def _render(self) -> None:
        if self._series is None:
            return
        slice_arr = self._series.volume[self._slice_idx]
        rendered = apply_window_level(slice_arr, level=self._level, window=self._window)
        # pyqtgraph expects [W, H] for default axisOrder; transpose so (rows, cols)
        # numpy array displays correctly.
        self._image_view.setImage(rendered.T, autoLevels=False, autoRange=False)
        n = self._series.volume.shape[0]
        self._slice_label.setText(f"Slice {self._slice_idx + 1} / {n}")
        self._wl_label.setText(f"L: {int(self._level)}  W: {int(self._window)}")

    # ---- input handling ----

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if self._series is None:
            super().keyPressEvent(event)
            return
        key = event.key()
        if key in (Qt.Key.Key_Right, Qt.Key.Key_Down):
            self.set_slice_index(self._slice_idx + 1)
            event.accept()
        elif key in (Qt.Key.Key_Left, Qt.Key.Key_Up):
            self.set_slice_index(self._slice_idx - 1)
            event.accept()
        else:
            super().keyPressEvent(event)

    def eventFilter(self, obj, event):  # type: ignore[override]
        # Plain wheel = slice nav. Ctrl/Cmd + wheel = pyqtgraph default zoom.
        if event.type() == event.Type.GraphicsSceneWheel or event.type() == event.Type.Wheel:
            modifiers = event.modifiers() if hasattr(event, "modifiers") else None
            if modifiers and (
                modifiers & Qt.KeyboardModifier.ControlModifier
                or modifiers & Qt.KeyboardModifier.MetaModifier
            ):
                return False  # let pyqtgraph zoom
            if self._series is None:
                return False
            delta = 0
            if isinstance(event, QWheelEvent):
                delta = event.angleDelta().y()
            else:
                delta = event.delta() if hasattr(event, "delta") else 0
            if delta == 0:
                return False
            step = -1 if delta > 0 else 1
            self.set_slice_index(self._slice_idx + step)
            return True
        return False
```

- [ ] **Step 2: Commit**

```bash
git add apps/desktop-viewer/app/widgets/viewer_panel.py
git commit -m "feat(slice-2): add viewer panel with pyqtgraph + slice/W-L controls + presets"
```

---

### Task D4: `widgets/metadata_panel.py`

**Files:**
- Create: `apps/desktop-viewer/app/widgets/metadata_panel.py`

- [ ] **Step 1: Write the widget**

```python
"""Right-side metadata table + Upload button + status label + Settings gear."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

METADATA_FIELDS: list[tuple[str, str]] = [
    ("Patient ID", "PatientID"),
    ("Patient Name", "PatientName"),
    ("Study Instance UID", "StudyInstanceUID"),
    ("Study Date", "StudyDate"),
    ("Study Description", "StudyDescription"),
    ("Series Instance UID", "SeriesInstanceUID"),
    ("Series Description", "SeriesDescription"),
    ("Series Number", "SeriesNumber"),
    ("Modality", "Modality"),
    ("SOP Instance UID", "SOPInstanceUID"),
    ("Instance Number", "InstanceNumber"),
    ("Rows", "Rows"),
    ("Columns", "Columns"),
    ("Pixel Spacing", "PixelSpacing"),
    ("Slice Thickness", "SliceThickness"),
    ("Bits Allocated", "BitsAllocated"),
    ("Window Center", "WindowCenter"),
    ("Window Width", "WindowWidth"),
]


class MetadataPanel(QWidget):
    uploadRequested = Signal()  # MainWindow looks up the current bytes
    settingsRequested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumWidth(320)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        title = QLabel("Metadata")
        title.setStyleSheet("font-weight:bold; font-size:13px;")
        layout.addWidget(title)

        self._table = QTableWidget(len(METADATA_FIELDS) + 1, 2)
        self._table.setHorizontalHeaderLabels(["Tag", "Value"])
        self._table.verticalHeader().setVisible(False)
        self._table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents
        )
        self._table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        for row, (label, _) in enumerate(METADATA_FIELDS):
            self._table.setItem(row, 0, QTableWidgetItem(label))
            self._table.setItem(row, 1, QTableWidgetItem("—"))
        # File path row at the end (filled separately)
        self._table.setItem(len(METADATA_FIELDS), 0, QTableWidgetItem("File Path"))
        self._table.setItem(len(METADATA_FIELDS), 1, QTableWidgetItem("—"))
        layout.addWidget(self._table, 1)

        # Upload row
        upload_row = QWidget()
        h = QHBoxLayout(upload_row)
        h.setContentsMargins(0, 0, 0, 0)
        self._upload_btn = QPushButton("Upload to backend")
        self._upload_btn.setEnabled(False)
        self._upload_btn.clicked.connect(self.uploadRequested.emit)
        h.addWidget(self._upload_btn, 1)
        gear = QToolButton()
        gear.setText("⚙")
        gear.setToolTip("Backend settings")
        gear.clicked.connect(self.settingsRequested.emit)
        h.addWidget(gear)
        layout.addWidget(upload_row)

        self._status = QLabel("Idle")
        self._status.setStyleSheet("color:#666;")
        layout.addWidget(self._status)

    # ---- public API ----

    def show_dataset(self, dataset, file_path: str | None = None) -> None:
        for row, (_, attr) in enumerate(METADATA_FIELDS):
            value = getattr(dataset, attr, None)
            self._table.item(row, 1).setText(self._format_value(value))
        last_row = len(METADATA_FIELDS)
        self._table.item(last_row, 1).setText(file_path or "—")
        self._upload_btn.setEnabled(True)

    def clear(self) -> None:
        for row, _ in enumerate(METADATA_FIELDS):
            self._table.item(row, 1).setText("—")
        self._table.item(len(METADATA_FIELDS), 1).setText("—")
        self._upload_btn.setEnabled(False)
        self._status.setText("Idle")

    def set_status(self, text: str, *, color: str = "#666") -> None:
        self._status.setText(text)
        self._status.setStyleSheet(f"color:{color};")

    def set_upload_busy(self, busy: bool) -> None:
        self._upload_btn.setEnabled(not busy)

    def _format_value(self, value: object) -> str:
        if value is None or value == "":
            return "—"
        if isinstance(value, list | tuple):
            return ", ".join(str(v) for v in value)
        return str(value)
```

- [ ] **Step 2: Commit**

```bash
git add apps/desktop-viewer/app/widgets/metadata_panel.py
git commit -m "feat(slice-2): add metadata panel with tag table and upload button"
```

---

### Task D5: `widgets/settings_dialog.py`

**Files:**
- Create: `apps/desktop-viewer/app/widgets/settings_dialog.py`

- [ ] **Step 1: Write the dialog**

```python
"""Settings dialog: edit api_url."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)


class SettingsDialog(QDialog):
    def __init__(self, current_url: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Backend Settings")
        self.setModal(True)
        self.resize(420, 120)

        layout = QVBoxLayout(self)
        form = QFormLayout()
        self._url_edit = QLineEdit(current_url)
        self._url_edit.setPlaceholderText("http://localhost:8000")
        form.addRow("API service URL:", self._url_edit)
        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def url(self) -> str:
        return self._url_edit.text().strip()
```

- [ ] **Step 2: Commit**

```bash
git add apps/desktop-viewer/app/widgets/settings_dialog.py
git commit -m "feat(slice-2): add settings dialog for editing api_url"
```

---

## Phase E — Upload worker (TDD)

### Task E1: TDD `upload/worker.py`

**Files:**
- Create: `apps/desktop-viewer/app/upload/__init__.py`
- Create: `apps/desktop-viewer/app/upload/worker.py`
- Create: `apps/desktop-viewer/tests/unit/test_upload_worker.py`

We unit-test the **upload logic** as a pure function (httpx + respx). The QThread wrapper around it is small and verified manually.

- [ ] **Step 1: `app/upload/__init__.py`** — empty.

- [ ] **Step 2: Write failing tests**

`apps/desktop-viewer/tests/unit/test_upload_worker.py`:
```python
import httpx
import pytest
import respx

from app.upload.worker import UploadError, do_upload


@respx.mock
def test_do_upload_happy_path():
    respx.post("http://localhost:8000/api/dicom/upload").respond(
        201,
        json={
            "status": "uploaded",
            "study_instance_uid": "1.2.3",
            "series_instance_uid": "1.2.4",
            "sop_instance_uid": "1.2.5",
            "orthanc_instance_id": "abc",
            "checksum_sha256": "deadbeef" * 8,
        },
    )
    result = do_upload(
        api_url="http://localhost:8000",
        dicom_bytes=b"fake-dicom",
        sop_uid="1.2.5",
    )
    assert result["orthanc_instance_id"] == "abc"
    assert result["checksum_sha256"].startswith("deadbeef")


@respx.mock
def test_do_upload_invalid_dicom_raises_with_code():
    respx.post("http://localhost:8000/api/dicom/upload").respond(
        400, json={"detail": "bad bytes", "code": "invalid_dicom"}
    )
    with pytest.raises(UploadError) as exc:
        do_upload(api_url="http://localhost:8000", dicom_bytes=b"x", sop_uid="1.2.5")
    assert "invalid_dicom" in str(exc.value)


@respx.mock
def test_do_upload_5xx_raises():
    respx.post("http://localhost:8000/api/dicom/upload").respond(500, text="boom")
    with pytest.raises(UploadError):
        do_upload(api_url="http://localhost:8000", dicom_bytes=b"x", sop_uid="1.2.5")


@respx.mock
def test_do_upload_connect_error_raises():
    respx.post("http://localhost:8000/api/dicom/upload").mock(
        side_effect=httpx.ConnectError("connection refused")
    )
    with pytest.raises(UploadError) as exc:
        do_upload(api_url="http://localhost:8000", dicom_bytes=b"x", sop_uid="1.2.5")
    assert "Could not reach" in str(exc.value)


@respx.mock
def test_do_upload_strips_trailing_slash_from_api_url():
    respx.post("http://localhost:8000/api/dicom/upload").respond(
        201,
        json={
            "status": "uploaded",
            "study_instance_uid": "x",
            "series_instance_uid": "x",
            "sop_instance_uid": "x",
            "orthanc_instance_id": "x",
            "checksum_sha256": "x" * 64,
        },
    )
    result = do_upload(
        api_url="http://localhost:8000/", dicom_bytes=b"x", sop_uid="1.2.5"
    )
    assert result["orthanc_instance_id"] == "x"
```

- [ ] **Step 3: Run, expect FAIL**

```bash
cd apps/desktop-viewer
uv run pytest tests/unit/test_upload_worker.py -v
```

- [ ] **Step 4: Write `app/upload/worker.py`**

```python
"""Background DICOM upload to the api-service.

`do_upload` is the pure-function core (httpx, no Qt) — unit-tested with respx.
`UploadWorker` is a thin QThread wrapper that emits Qt signals.
"""

from __future__ import annotations

import httpx
from PySide6.QtCore import QThread, Signal


class UploadError(Exception):
    """Raised when the api-service rejects the upload or is unreachable."""


def do_upload(
    *,
    api_url: str,
    dicom_bytes: bytes,
    sop_uid: str,
    timeout: float = 30.0,
) -> dict:
    base = api_url.rstrip("/")
    url = f"{base}/api/dicom/upload"
    files = {"file": (f"{sop_uid}.dcm", dicom_bytes, "application/dicom")}
    try:
        with httpx.Client(timeout=timeout) as client:
            response = client.post(url, files=files)
    except httpx.ConnectError as exc:
        raise UploadError(f"Could not reach api-service at {base}: {exc}") from exc
    except httpx.HTTPError as exc:
        raise UploadError(f"HTTP error talking to api-service: {exc}") from exc

    if response.status_code >= 400:
        try:
            body = response.json()
            code = body.get("code", "error")
            detail = body.get("detail", response.text)
            raise UploadError(f"{code}: {detail}")
        except ValueError:
            raise UploadError(
                f"api-service returned {response.status_code}: {response.text}"
            ) from None
    return response.json()


class UploadWorker(QThread):
    succeeded = Signal(dict)
    failed = Signal(str)

    def __init__(
        self,
        api_url: str,
        dicom_bytes: bytes,
        sop_uid: str,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._api_url = api_url
        self._bytes = dicom_bytes
        self._sop_uid = sop_uid

    def run(self) -> None:
        try:
            result = do_upload(
                api_url=self._api_url,
                dicom_bytes=self._bytes,
                sop_uid=self._sop_uid,
            )
        except UploadError as exc:
            self.failed.emit(str(exc))
            return
        except Exception as exc:  # noqa: BLE001 — defensive in a worker thread
            self.failed.emit(f"Unexpected: {exc}")
            return
        self.succeeded.emit(result)
```

- [ ] **Step 5: Run, expect PASS**

```bash
uv run pytest tests/unit/test_upload_worker.py -v
```

Expected: 5 passed.

- [ ] **Step 6: Run all unit tests together**

```bash
uv run pytest tests/unit/ -v
```

Expected: 9 + 7 + 7 + 5 = 28 passed.

- [ ] **Step 7: Commit**

```bash
cd /Users/harshilvyas/Documents/Github\ Repos/NeuroScan
git add apps/desktop-viewer/app/upload/__init__.py apps/desktop-viewer/app/upload/worker.py apps/desktop-viewer/tests/unit/test_upload_worker.py
git commit -m "feat(slice-2): add upload worker (httpx) with respx tests + QThread wrapper"
```

---

## Phase F — Wire it all up

### Task F1: Update `MainWindow` to use the real widgets and threading

**Files:**
- Modify: `apps/desktop-viewer/app/main_window.py`

This is the biggest task. We replace placeholder labels with real widgets, wire signals, add a folder loader QThread, and the upload flow.

- [ ] **Step 1: Rewrite `main_window.py`**

```python
"""Main application window: 3-panel layout, signal wiring, background threads."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, Qt, QThread, Signal
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QMainWindow,
    QMessageBox,
    QStackedWidget,
    QStatusBar,
    QWidget,
)

from app.config import Config
from app.dicom.loader import SeriesRef, StudyRef, scan_folder
from app.dicom.series import LoadedSeries, load_series
from app.upload.worker import UploadWorker
from app.widgets.browser_panel import BrowserPanel
from app.widgets.empty_state import EmptyState
from app.widgets.metadata_panel import MetadataPanel
from app.widgets.settings_dialog import SettingsDialog
from app.widgets.viewer_panel import ViewerPanel


class FolderScanWorker(QObject):
    """Runs scan_folder in a worker QThread."""

    finished = Signal(list)
    failed = Signal(str)

    def __init__(self, root: Path) -> None:
        super().__init__()
        self._root = root

    def run(self) -> None:
        try:
            studies = scan_folder(self._root)
        except Exception as exc:  # noqa: BLE001 — defensive
            self.failed.emit(str(exc))
            return
        self.finished.emit(studies)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.config = Config()
        self.setWindowTitle("NeuroScan Desktop Viewer")
        self.resize(1400, 900)

        self._loaded_series: LoadedSeries | None = None
        self._scan_thread: QThread | None = None
        self._scan_worker: FolderScanWorker | None = None
        self._upload_worker: UploadWorker | None = None

        self._build_menus()
        self._build_status_bar()
        self._build_central_widget()

    # ---- UI ----

    def _build_menus(self) -> None:
        menu = self.menuBar()
        file_menu = menu.addMenu("&File")

        open_action = QAction("Open Folder…", self)
        open_action.setShortcut(QKeySequence.StandardKey.Open)
        open_action.triggered.connect(self._on_open_folder)
        file_menu.addAction(open_action)

        file_menu.addSeparator()

        quit_action = QAction("Quit", self)
        quit_action.setShortcut(QKeySequence.StandardKey.Quit)
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)

    def _build_status_bar(self) -> None:
        self._status = QStatusBar()
        self.setStatusBar(self._status)
        self._status.showMessage("Ready")

    def _build_central_widget(self) -> None:
        central = QWidget()
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._browser = BrowserPanel()
        self._browser.setMinimumWidth(280)
        self._browser.setMaximumWidth(380)
        self._browser.seriesSelected.connect(self._on_series_selected)
        self._browser.instanceSelected.connect(self._on_instance_selected)

        # Center: stack of empty state and viewer
        self._center_stack = QStackedWidget()
        self._empty_state = EmptyState()
        self._empty_state.openFolderRequested.connect(self._on_open_folder)
        self._empty_state.loadSampleRequested.connect(self._load_folder)
        self._viewer = ViewerPanel()
        self._viewer.sliceChanged.connect(self._on_slice_changed)
        self._center_stack.addWidget(self._empty_state)
        self._center_stack.addWidget(self._viewer)
        self._center_stack.setCurrentWidget(self._empty_state)

        self._metadata = MetadataPanel()
        self._metadata.uploadRequested.connect(self._on_upload_requested)
        self._metadata.settingsRequested.connect(self._on_settings_requested)

        layout.addWidget(self._browser, 0)
        layout.addWidget(self._center_stack, 1)
        layout.addWidget(self._metadata, 0)
        self.setCentralWidget(central)

    # ---- Folder loading ----

    def _on_open_folder(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Open DICOM Folder")
        if path:
            self._load_folder(Path(path))

    def _load_folder(self, root: Path) -> None:
        self._status.showMessage(f"Scanning {root}…")
        self._scan_thread = QThread(self)
        self._scan_worker = FolderScanWorker(root)
        self._scan_worker.moveToThread(self._scan_thread)
        self._scan_thread.started.connect(self._scan_worker.run)
        self._scan_worker.finished.connect(self._on_scan_finished)
        self._scan_worker.failed.connect(self._on_scan_failed)
        self._scan_worker.finished.connect(self._scan_thread.quit)
        self._scan_worker.failed.connect(self._scan_thread.quit)
        self._scan_thread.finished.connect(self._scan_worker.deleteLater)
        self._scan_thread.finished.connect(self._scan_thread.deleteLater)
        self._scan_thread.start()

    def _on_scan_finished(self, studies: list[StudyRef]) -> None:
        self._scan_worker = None
        self._scan_thread = None
        if not studies:
            self._status.showMessage("No DICOM files found")
            QMessageBox.information(self, "No DICOMs", "No DICOM files were found in that folder.")
            return
        n_series = sum(len(s.series) for s in studies)
        n_inst = sum(len(se.instances) for s in studies for se in s.series)
        self._status.showMessage(
            f"Loaded {len(studies)} studies · {n_series} series · {n_inst} instances"
        )
        self._browser.set_studies(studies)

    def _on_scan_failed(self, message: str) -> None:
        self._scan_worker = None
        self._scan_thread = None
        self._status.showMessage(f"Scan failed: {message}")
        QMessageBox.critical(self, "Scan failed", message)

    # ---- Series / instance selection ----

    def _on_series_selected(self, series: SeriesRef) -> None:
        try:
            loaded = load_series(series)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Load failed", f"Could not load series:\n{exc}")
            self._status.showMessage(f"Load failed: {exc}")
            return
        self._loaded_series = loaded
        self._viewer.set_series(loaded)
        self._center_stack.setCurrentWidget(self._viewer)
        self._update_metadata_for_slice(0)

    def _on_instance_selected(self, _series: SeriesRef, idx: int) -> None:
        if self._loaded_series is None:
            return
        self._viewer.set_slice_index(idx)

    def _on_slice_changed(self, idx: int) -> None:
        self._update_metadata_for_slice(idx)

    def _update_metadata_for_slice(self, idx: int) -> None:
        if self._loaded_series is None:
            return
        ds = self._loaded_series.datasets[idx]
        path = self._loaded_series.series_ref.instances[idx].file_path
        self._metadata.show_dataset(ds, file_path=str(path))
        n = self._loaded_series.volume.shape[0]
        self._status.showMessage(f"Slice {idx + 1} / {n}  ·  {path.name}")

    # ---- Upload ----

    def _on_upload_requested(self) -> None:
        if self._loaded_series is None:
            return
        idx = self._viewer.current_slice_index()
        if idx < 0 or idx >= len(self._loaded_series.raw_bytes):
            return
        dicom_bytes = self._loaded_series.raw_bytes[idx]
        sop_uid = self._loaded_series.datasets[idx].SOPInstanceUID

        self._metadata.set_upload_busy(True)
        self._metadata.set_status("Uploading…", color="#666")

        self._upload_worker = UploadWorker(
            api_url=self.config.api_url,
            dicom_bytes=dicom_bytes,
            sop_uid=str(sop_uid),
        )
        self._upload_worker.succeeded.connect(self._on_upload_succeeded)
        self._upload_worker.failed.connect(self._on_upload_failed)
        self._upload_worker.finished.connect(self._upload_worker.deleteLater)
        self._upload_worker.start()

    def _on_upload_succeeded(self, result: dict) -> None:
        checksum = result.get("checksum_sha256", "")
        short = checksum[:12] if checksum else "?"
        self._metadata.set_status(f"Uploaded ✓  (sha256: {short}…)", color="#0a6b1f")
        self._metadata.set_upload_busy(False)
        self._upload_worker = None

    def _on_upload_failed(self, message: str) -> None:
        self._metadata.set_status(f"Failed: {message}", color="#a4282b")
        self._metadata.set_upload_busy(False)
        self._upload_worker = None

    # ---- Settings ----

    def _on_settings_requested(self) -> None:
        dialog = SettingsDialog(self.config.api_url, self)
        if dialog.exec() == SettingsDialog.DialogCode.Accepted:
            new_url = dialog.url() or self.config.api_url
            self.config.api_url = new_url
            self._status.showMessage(f"API URL set to {new_url}")
```

- [ ] **Step 2: Smoke launch**

```bash
cd apps/desktop-viewer
uv run python -m app.main &
APP_PID=$!
sleep 3
ps -p $APP_PID > /dev/null && echo "App running"
kill $APP_PID 2>/dev/null
wait $APP_PID 2>/dev/null
```

Expected: window opens with "Load sample data" button (because `data/sample-dicom/real/` exists from slice 1).

- [ ] **Step 3: Run all unit tests to confirm we didn't break anything**

```bash
uv run pytest tests/unit/ -v
```

Expected: 28 passed.

- [ ] **Step 4: Commit**

```bash
cd /Users/harshilvyas/Documents/Github\ Repos/NeuroScan
git add apps/desktop-viewer/app/main_window.py
git commit -m "feat(slice-2): wire MainWindow to real widgets with folder + upload threads"
```

---

### Task F2: Manual smoke test

This task does **not** add code — it runs the manual smoke checklist from the spec and confirms the app actually works end-to-end. Output is documented in the README that Task G2 writes.

- [ ] **Step 1: Generate a 32-slice synthetic series**

```bash
cd /Users/harshilvyas/Documents/Github\ Repos/NeuroScan
uv run --directory services/api-service python ../../scripts/generate-synthetic-dicom.py --count 32 --output /tmp/multi32 --rows 64 --columns 64
ls /tmp/multi32 | wc -l
```

Expected: `32`.

- [ ] **Step 2: Bring up Slice 1's stack for upload testing**

```bash
export PATH="$HOME/.orbstack/bin:$PATH"
docker compose -f infra/docker-compose.yml up -d
sleep 15
curl -sf http://localhost:8000/health | python3 -m json.tool
```

Expected: `"status": "ok"` with both reachable flags `true`.

- [ ] **Step 3: Launch the desktop viewer**

```bash
cd apps/desktop-viewer
uv run python -m app.main
```

Manually verify each item:

1. Empty state shows "Open folder…" + "Load sample data".
2. Click "Load sample data" → brain MR study appears in the browser panel.
3. Click the series → image renders in center; metadata table fills in on the right.
4. **File → Open Folder…** → pick `/tmp/multi32` → 32-instance series appears.
5. Slice slider moves through all 32 slices; each slice's gradient is visibly different.
6. Mouse scroll wheel changes slices (no modifier).
7. Cmd/Ctrl + scroll zooms.
8. Middle-click drag pans.
9. Arrow keys move between slices when the viewer has focus.
10. W/L sliders change contrast.
11. Click each preset (Brain/Bone/Lung/Soft Tissue) — contrast jumps; sliders update.
12. Click Default — restores original W/L.
13. Click ⚙ → Settings dialog opens, shows current URL.
14. Click Upload → status label shows "Uploading…" then "Uploaded ✓ (sha256: …)".
15. Open http://localhost:5173/studies → uploaded study appears.
16. `docker compose -f infra/docker-compose.yml stop api-service` → click Upload again → status shows clear error message; app stays responsive.

- [ ] **Step 4: Tear down test stack**

```bash
docker compose -f infra/docker-compose.yml down
```

- [ ] **Step 5: No commit for this task** (manual smoke only).

---

## Phase G — CI + docs

### Task G1: Add `desktop-viewer` job to CI

**Files:**
- Modify: `.github/workflows/ci.yml`

- [ ] **Step 1: Append the new job**

Append to `jobs:` after the `e2e` block:

```yaml
  desktop-viewer:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: apps/desktop-viewer
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v3
        with:
          enable-cache: true
      - name: Install Qt headless dependencies
        run: |
          sudo apt-get update
          sudo apt-get install -y --no-install-recommends \
            libegl1 libxkbcommon0 libdbus-1-3 libfontconfig1 \
            libxcb-icccm4 libxcb-image0 libxcb-keysyms1 libxcb-randr0 \
            libxcb-render-util0 libxcb-shape0 libxcb-sync1 libxcb-xfixes0 \
            libxcb-xinerama0 libxcb-xkb1 libxcb-cursor0
      - name: Install
        run: uv sync --frozen
      - name: Lint
        run: |
          uv run ruff check .
          uv run ruff format --check .
      - name: Test
        run: uv run pytest tests/unit/ -q
        env:
          QT_QPA_PLATFORM: offscreen
```

The Qt system libs are needed because PySide6 wheels link against them at import time, even for non-GUI tests (the loader/series/window_level tests don't open a window but the modules import PySide6 implicitly via shared package state — actually they don't, but it's still cheaper to install once than diagnose import errors per-PR).

`QT_QPA_PLATFORM=offscreen` makes any Qt code that runs at import safe.

- [ ] **Step 2: Verify the workflow YAML is valid locally**

```bash
cd /Users/harshilvyas/Documents/Github\ Repos/NeuroScan
python3 -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml'))" && echo "YAML OK"
```

Expected: `YAML OK`.

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/ci.yml
git commit -m "ci(slice-2): add desktop-viewer job (lint + unit tests, headless Qt)"
```

---

### Task G2: Write `apps/desktop-viewer/README.md`

**Files:**
- Create: `apps/desktop-viewer/README.md`

- [ ] **Step 1: Write the README**

```markdown
# NeuroScan Desktop Viewer

Standalone Qt/Python DICOM viewer. Part of the [NeuroScan Workstation](../../README.md) project.

## What it does

- Open a folder of DICOM files (`File → Open Folder…` or `⌘O`).
- Browse studies → series → instances in the left panel.
- View the image in the center panel with zoom/pan and slice navigation.
- Adjust window/level via sliders or one-click clinical presets (Brain, Bone, Lung, Soft Tissue, Default).
- Inspect DICOM tags in the right panel.
- Optionally upload the current instance to the running [Slice 1 backend](../../services/api-service/) with one click.

The app runs **fully offline** — opening DICOMs requires no backend, no Docker, no network. The only network use is the optional Upload button.

## Requirements

- macOS, Linux, or Windows
- Python ≥ 3.12
- [`uv`](https://docs.astral.sh/uv/)

## Run

```bash
cd apps/desktop-viewer
uv sync
uv run python -m app.main
```

On first launch the empty state will offer a "Load sample data" button if `data/sample-dicom/real/` exists in the repo.

## Generate test data

A 32-slice synthetic MR series for testing slice navigation:

```bash
uv run --directory services/api-service python ../../scripts/generate-synthetic-dicom.py \
    --count 32 --output /tmp/multi32 --rows 128 --columns 128
```

Then **File → Open Folder…** → `/tmp/multi32`.

## Controls

| Action | Input |
|---|---|
| Change slice | Slice slider · scroll wheel · ↑/↓/←/→ keys |
| Zoom | Cmd/Ctrl + scroll |
| Pan | Middle-click drag · Shift + left-drag |
| Reset view | Double-click image |
| Window/Level | Window/Level sliders or preset buttons |

## Upload to backend

Click "Upload to backend" in the right panel.

By default the app posts to `http://localhost:8000/api/dicom/upload`. Edit the URL via the ⚙ icon next to the Upload button. The URL is persisted across launches via `QSettings`.

To run the backend, see the [top-level Quickstart](../../README.md#quickstart):

```bash
docker compose -f ../../infra/docker-compose.yml up -d
```

## Tests

```bash
uv run pytest tests/unit/ -v
uv run ruff check .
uv run ruff format --check .
```

There are no GUI/integration tests in this slice (Slice 2 deliberately does not pull in pytest-qt). The widgets are verified via the [manual smoke checklist](#manual-smoke-checklist) below.

## Manual smoke checklist

Run after any non-trivial change to the widgets or `MainWindow`.

1. ☐ App launches with the empty state visible.
2. ☐ "Load sample data" loads the brain MR study (when `data/sample-dicom/real/` exists).
3. ☐ Clicking a series in the browser renders the image in the center.
4. ☐ Metadata panel populates with non-`—` values.
5. ☐ Generate `/tmp/multi32` (32-slice series), open it, scroll wheel cycles slices.
6. ☐ Arrow keys cycle slices.
7. ☐ Cmd/Ctrl + scroll zooms; middle-drag pans.
8. ☐ Each W/L preset visibly changes contrast; sliders move accordingly.
9. ☐ Default button restores original W/L.
10. ☐ Settings dialog opens, shows current URL, OK persists, Cancel does not.
11. ☐ With Slice 1 stack up: Upload posts the DICOM, status reads `Uploaded ✓ (sha256: …)`, file appears at http://localhost:5173/studies.
12. ☐ With api-service stopped: Upload shows clear error in status label, app does not freeze.
13. ☐ Quit app, relaunch — Settings URL persists.

## Known limitations (Slice 2)

- No multiplanar reconstruction (axial/sagittal/coronal). Coming in Slice 8.
- No measurement tools or ROI overlays. Coming in Slice 8.
- No DICOM Q/R against Orthanc — load is local-folder only.
- No anatomically-correct display (`ImageOrientationPatient` is ignored).
- Large series (1000+ instances) will use significant memory; no lazy slice loading.
- No headless GUI tests in CI; widgets are verified by manual smoke only.
- macOS / Linux primary; Windows untested but PySide6 wheels exist for it.

## Architecture

See the [design spec](../../docs/superpowers/specs/2026-05-05-slice-2-qt-desktop-viewer-design.md).

## License

Inherits the repo [LICENSE](../../LICENSE).
```

- [ ] **Step 2: Commit**

```bash
git add apps/desktop-viewer/README.md
git commit -m "docs(slice-2): add desktop-viewer README with usage + smoke checklist"
```

---

## Phase H — Final wrap-up

### Task H1: Update `status.md` and `roadmap.md`, push branch

**Files:**
- Modify: `docs/status.md`
- Modify: `docs/roadmap.md`

- [ ] **Step 1: Update `docs/roadmap.md` row for slice 2**

Find the row:
```text
| 2 | Qt desktop viewer (standalone, reads local DICOM dir, no backend dependency) | planned | — | |
```
Replace with:
```text
| 2 | Qt desktop viewer (standalone, reads local DICOM dir, no backend dependency) | **done** | [spec](./superpowers/specs/2026-05-05-slice-2-qt-desktop-viewer-design.md) · [plan](./superpowers/plans/2026-05-06-slice-2-qt-desktop-viewer.md) | Completed 2026-05-06 on branch `slice-2-qt-desktop-viewer` |
```

- [ ] **Step 2: Update `docs/status.md`**

Replace the **Current slice** section with:

```markdown
## Current slice

**Slice 2 — Qt desktop viewer.** Implementation complete on branch `slice-2-qt-desktop-viewer`.

Spec: [`superpowers/specs/2026-05-05-slice-2-qt-desktop-viewer-design.md`](./superpowers/specs/2026-05-05-slice-2-qt-desktop-viewer-design.md)
Plan: [`superpowers/plans/2026-05-06-slice-2-qt-desktop-viewer.md`](./superpowers/plans/2026-05-06-slice-2-qt-desktop-viewer.md)
README: [`apps/desktop-viewer/README.md`](../apps/desktop-viewer/README.md)
```

Replace the **What's done** list by appending a slice 2 block:

```markdown
- Slice 2 implementation complete:
  - PySide6 desktop app at `apps/desktop-viewer/` with 3-panel layout
  - DICOM folder scanner with Study/Series/Instance grouping (28 unit tests passing)
  - pyqtgraph image display with zoom/pan
  - Slice navigation: slider, scroll wheel, arrow keys
  - Window/level: sliders + 4 clinical presets (Brain, Bone, Lung, Soft Tissue) + Default
  - Metadata panel with 18-field DICOM tag table
  - Upload-to-backend button with httpx + QThread (respx-tested)
  - Settings dialog persisting api_url via QSettings
  - Empty-state "Load sample data" shortcut
  - Compressed DICOM support via pylibjpeg
  - Multi-slice synthetic generator (`scripts/generate-synthetic-dicom.py --count N`)
  - New `desktop-viewer` job in CI (lint + 28 unit tests, headless Qt)
```

Replace **What's next** with:

```markdown
1. Verify Slice 2 from a clean checkout (run unit tests, smoke-launch app, manual checklist).
2. Push the `slice-2-qt-desktop-viewer` branch and (optionally) open a PR.
3. Brainstorm Slice 3 — Reconstruction service (k-space → reconstructed DICOM).
```

Append to **Recent decisions log**:

```markdown
- 2026-05-06: Slice 2 implementation complete. Locked AD-S2-1..9 (PySide6, pyqtgraph, in-memory volume, software W/L, QSettings, no Docker for desktop, no pytest-qt, pylibjpeg deps, CI lint+unit only).
```

- [ ] **Step 3: Verify Definition of Done items 1, 11, 12, 13 from a clean state**

```bash
cd /Users/harshilvyas/Documents/Github\ Repos/NeuroScan
git status  # working tree clean
cd apps/desktop-viewer
uv run pytest tests/unit/ -q
uv run ruff check .
uv run ruff format --check .
```

Expected: 28 passed; lint clean.

- [ ] **Step 4: Commit**

```bash
cd /Users/harshilvyas/Documents/Github\ Repos/NeuroScan
git add docs/status.md docs/roadmap.md
git commit -m "docs(slice-2): mark slice 2 done in status.md and roadmap.md"
```

- [ ] **Step 5: Push branch**

```bash
git push -u origin slice-2-qt-desktop-viewer
```

(PR creation is up to the user.)

---

## Notes for the implementing engineer

- **Pure-logic-first.** Every TDD task in Phase B writes the failing test before the implementation. Don't skip the failing-test step; if you do, you're working blind.
- **Widgets are not unit-tested.** AD-S2-7 says no pytest-qt. Widgets are verified by the manual smoke checklist in Task F2 and `apps/desktop-viewer/README.md`. If you find yourself wanting to add widget unit tests, stop — that decision was deliberately deferred.
- **One commit per task minimum.** Tasks B1–B4 each end with one commit. Phase D widget tasks each end with one commit (no tests). Don't squash unrelated changes.
- **Run lint locally before committing.** `cd apps/desktop-viewer && uv run ruff check . && uv run ruff format .`. The CI job will fail otherwise.
- **Don't touch `services/api-service/`, `apps/web-viewer/`, `infra/`, or `tests/e2e/`** — Slice 2 is additive only, except for the `scripts/generate-synthetic-dicom.py` extension.
- **PySide6 wheel is large.** First `uv sync` downloads ~75 MB. Subsequent syncs reuse cache.
- **Qt event-loop debugging tip.** If the app freezes during folder scan or upload, check that the worker `QObject` is moved to the thread *before* `started.connect(...)` and that signals from the worker thread are connected with the default `Qt.AutoConnection` (Qt picks `QueuedConnection` for cross-thread automatically).
- **macOS QSettings location** is `~/Library/Preferences/com.NeuroScan.DesktopViewer.plist` (or similar). Delete it to test "first run" behavior.
- **Don't add features that aren't in this plan.** If you find yourself wanting to add measurements, annotations, multi-planar, or a 3D view — stop. Those are explicitly future slices. If you think it's urgent, append a note to `docs/status.md` "Open questions" instead.
