# NeuroScan Workstation — Slice 2: Qt Desktop Viewer

**Date:** 2026-05-05
**Status:** Draft (pending user review)
**Phase:** 2 of N
**Parent project:** NeuroScan Workstation — local-first MRI / DICOM platform
**Branch:** `slice-2-qt-desktop-viewer` (off `main`)
**Predecessor:** Slice 1 — Vertical spine (merged to `main`)

---

## 1. Purpose

Build a standalone Qt/Python desktop application that loads DICOM folders from disk and provides clinical-style viewing — multi-series browser, slice navigation, window/level, zoom/pan, metadata inspection, and an optional one-click upload to the Slice 1 backend.

Slice 2 is the most role-differentiating piece of the project. The neuro42 role description specifically calls for "1–3 years programming in Qt and Python" and "develop new user interface used to view medical images." This slice exists to demonstrate exactly that.

The desktop viewer is **standalone**: it opens DICOM folders entirely offline, with no Docker, no backend, no Postgres, no Orthanc required to run. The only network dependency is the optional "Upload to backend" button.

## 2. Out-of-scope (deliberately deferred)

- Multiplanar reconstruction (axial / sagittal / coronal) — deferred to Slice 8 alongside the Cornerstone3D web viewer upgrade.
- Measurement tools (ruler, ROI, angle) — Slice 8.
- Annotation overlays — Slice 8.
- DICOM Q/R against Orthanc (browse remote studies into the desktop app) — future slice TBD.
- Save / export modified DICOMs — future slice TBD.
- PNG / PDF export — future slice TBD.
- Anatomically-correct display via `ImageOrientationPatient` + `PixelSpacing` — significant scope; most value is in slice 8 multiplanar.
- Headless GUI smoke tests in CI (Xvfb on Linux runners) — defer until the test surface justifies it.
- Distribution as a packaged `.app` bundle / installer — future slice TBD.

These are explicit deferrals. Trying to do any of them in Slice 2 is scope creep.

## 3. Architecture

### Single-process desktop app

```text
┌──────────────────────────────────────────────────────────────────┐
│                  Qt Desktop App (PySide6)                        │
│                                                                  │
│  ┌─────────────────┐  ┌──────────────────────────┐  ┌──────────┐ │
│  │  Browser Panel  │  │      Viewer Panel        │  │ Metadata │ │
│  │  (left)         │  │      (center)            │  │ (right)  │ │
│  │                 │  │                          │  │          │ │
│  │  Study tree     │  │  pyqtgraph ImageView     │  │ Tag      │ │
│  │  ├ Series A     │  │  (zoom + pan)            │  │ table    │ │
│  │  │ ├ Inst 1     │  │                          │  │          │ │
│  │  │ └ Inst 2     │  │                          │  │ Upload   │ │
│  │  └ Series B     │  │                          │  │ button + │ │
│  │                 │  │  W/L preset buttons      │  │ status   │ │
│  │                 │  │  Slice / W / L sliders   │  │          │ │
│  └─────────────────┘  └──────────────────────────┘  └──────────┘ │
│                                                                  │
│  Status bar:  Slice 7 / 32   filename.dcm    Loaded 1.2s         │
└──────────────────────────────────────────────────────────────────┘

  Optional outbound HTTP only on Upload button click:
  ─── POST {api_url}/api/dicom/upload ───▶  Slice 1 api-service
```

### Threading model

- Main thread: Qt UI.
- Folder loading runs in a `QThread` to keep the UI responsive on large folders. Emits per-file progress and final `loaded(studies)` signal.
- Upload runs in its own one-shot `QThread`. Emits `succeeded(json)` / `failed(error)`.

### Architectural decisions (locked)

| ID | Decision | Rationale |
|---|---|---|
| AD-S2-1 | PySide6 binding | LGPL licensing for portfolio; matches PRD. |
| AD-S2-2 | pyqtgraph for image display | Native numpy support, zoom/pan/level built in, fastest option for slice scrolling. |
| AD-S2-3 | All series pixel data held in memory as 3D numpy `[N,H,W]` after series selection | Fast slice switching; no repeated disk reads. Acceptable memory for sub-1000-slice series. |
| AD-S2-4 | Window/level applied in software (numpy) before QImage conversion | Standard medical-imaging approach; works for any DICOM regardless of native bits. |
| AD-S2-5 | Settings persisted via `QSettings` ("NeuroScan" / "DesktopViewer") | Native macOS/Linux/Windows persistence with zero extra deps. |
| AD-S2-6 | No Docker for the desktop viewer | GUI-in-container on macOS = XQuartz pain for zero benefit. |
| AD-S2-7 | No pytest-qt / no GUI integration tests in this slice | Keep test surface tight; cover pure logic (loader, W/L math) with pytest, manual smoke for UI. |
| AD-S2-8 | Compressed DICOM support via `pylibjpeg`, `pylibjpeg-libjpeg`, `pylibjpeg-openjpeg` | Many real-world DICOMs use JPEG/JPEG2000; without these pydicom raises on `pixel_array`. |
| AD-S2-9 | Add a `desktop-viewer` job to existing CI workflow (lint + non-Qt unit tests only) | Keeps the project consistently green; cheap; no GUI runner needed. |

### Cross-slice decisions inherited

All AD-1 through AD-9 from `docs/roadmap.md` continue to apply. None are revisited in this slice.

## 4. Data flows

### 4.1 Folder load

1. User: **File → Open Folder…** (`⌘O`) → `QFileDialog.getExistingDirectory(...)`.
2. App spawns `LoaderWorker(QThread)` with the folder path.
3. Worker walks recursively, attempts `pydicom.dcmread(path, stop_before_pixels=True)` on every file. Files that fail to parse are silently skipped. (We use `stop_before_pixels=True` for speed during the scan; pixels are loaded lazily when a series is selected.)
4. Successful instances are grouped:
   ```text
   Study  (StudyInstanceUID)
     └─ Series  (SeriesInstanceUID)
         └─ Instance  (SOPInstanceUID, file path)
   ```
   Within a series, instances are sorted by `InstanceNumber`, falling back to filename.
5. Status-bar progress: "Scanning… 124 / 532".
6. On completion the worker emits `loaded(list[Study])`. MainWindow populates the browser tree.

### 4.2 Series selection → image display

1. User clicks a series in the browser tree.
2. App reads pixel data for every instance in the series with `pydicom.dcmread(path).pixel_array`. Stacks them into a numpy `[N, H, W]` array (typed `int16` or whatever the source uses; we keep the native type and only cast to `uint8` at display time).
3. Default W/L is read from the first instance's `WindowCenter` / `WindowWidth` tags. If absent, auto-calculated as `mean ± 2*std` of the volume.
4. Viewer panel displays slice 0; slice slider range is `[0, N-1]`.
5. Metadata panel updates to instance 0's tags.

### 4.3 Slice navigation

The current slice index is a single source of truth on `ViewerPanel`. It can be changed by:
- Clicking the slice slider
- Mouse scroll wheel over the image (no modifier)
- Up/Down or Left/Right arrow keys when the viewer has focus
- Selecting a different instance in the browser tree

When the index changes:
- The viewer recomputes its display (apply current W/L to slice N, push to pyqtgraph)
- The metadata panel updates to that instance's tags
- The status bar updates "Slice N / total"

### 4.4 Window / level

Three controls share the same backing state on `ViewerPanel`:

- **Two sliders** (Window, Level): range = `[volume_min, volume_max]`.
- **Preset buttons**: Brain (W:80, L:40), Bone (W:2000, L:300), Lung (W:1500, L:-600), Soft Tissue (W:400, L:50), Default (from DICOM tags or auto). Clicking a preset updates both sliders and re-renders.
- **Reset** button: same as Default preset.

Pixel mapping:
```python
def apply_window_level(arr: np.ndarray, level: float, window: float) -> np.ndarray:
    low = level - window / 2
    high = level + window / 2
    clipped = np.clip(arr, low, high)
    return ((clipped - low) / max(window, 1) * 255).astype(np.uint8)
```

The result is fed into pyqtgraph's `ImageView.setImage(...)`.

### 4.5 Zoom / pan

Provided by pyqtgraph's `ImageView`:
- **Scroll wheel + Ctrl/Cmd**: zoom (we override the default to make plain scroll = slice nav).
- **Middle-click drag** OR **Shift + left-drag**: pan.
- **Double-click**: reset view.

We hide pyqtgraph's default histogram, ROI, menu, and norm buttons because we provide our own UI for them.

### 4.6 Upload to backend

1. Upload button is enabled only when an instance is selected.
2. Click → button disabled, status label shows "Uploading…".
3. `UploadWorker(QThread)` is constructed with `(api_url, dicom_bytes, sop_uid)` — the bytes are the raw file contents we read once during series load and cache alongside the parsed Dataset.
4. Worker runs `httpx.post(f"{api_url}/api/dicom/upload", files=..., timeout=30)`.
5. On 2xx → emits `succeeded(json)`. Status label: `Uploaded ✓ (sha256: <first 12 chars>…)`.
6. On non-2xx with parseable body → emits `failed(f"{code}: {detail}")`.
7. On network error → emits `failed("Could not reach api-service: <reason>")`.
8. Button re-enabled either way.

The api URL comes from `Config().api_url`. Default `http://localhost:8000`. Editable via the Settings dialog (gear icon next to Upload). Persisted via `QSettings`.

### 4.7 Auto-load sample data

On first launch with no folder loaded yet, the center panel shows a placeholder:

```text
No folder loaded.
[Open folder…]    [Load sample data]
```

`Load sample data` is shown only when `<repo_root>/data/sample-dicom/real/` exists. Clicking it opens that folder via the same loader path. This is the zero-friction demo experience.

## 5. Slice 2 scope — what we build

### Core (always in)

- Folder picker + recursive scan + study/series/instance grouping
- 3-panel main window: browser (left), viewer (center), metadata (right)
- pyqtgraph image display with zoom + pan
- Slice navigation: slider, scroll wheel, arrow keys
- Window / level: 2 sliders + preset buttons + reset
- Metadata table (fixed tag list per §6.3)
- Upload to backend button + status label
- Settings dialog for api URL (persisted via QSettings)
- Auto-suggest sample data on empty state
- Status bar with slice index, filename, load time
- Multi-slice synthetic series generator (extension of `scripts/generate-synthetic-dicom.py`)
- Unit tests for loader + W/L math
- README in `apps/desktop-viewer/`
- New `desktop-viewer` job in `.github/workflows/ci.yml` (lint + unit only)

### Extensions to existing slice 1 code

Just one: `scripts/generate-synthetic-dicom.py` gains a `--count N` flag. When `N > 1`, it produces a series of `N` instances with shared StudyInstanceUID + SeriesInstanceUID, distinct SOPInstanceUID, sequential `InstanceNumber`, and a moving gradient pattern in the pixel data so slice navigation is visually obvious. Default `N=1` preserves backward compatibility with Slice 1.

## 6. Component specs

### 6.1 `dicom/loader.py`

Pure functions, no Qt. Designed for direct unit testing.

```python
from dataclasses import dataclass
from pathlib import Path

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
    instances: list[InstanceRef]  # sorted by instance_number then filename

@dataclass(frozen=True)
class StudyRef:
    study_instance_uid: str
    patient_id: str | None
    patient_name: str | None
    study_date: str | None
    study_description: str | None
    series: list[SeriesRef]

def scan_folder(root: Path) -> list[StudyRef]: ...
def is_dicom(path: Path) -> bool: ...        # quick header peek (no full parse)
def read_metadata(path: Path) -> dict: ...    # used during scan
```

### 6.2 `dicom/series.py`

```python
import numpy as np
from dataclasses import dataclass, field
from pydicom.dataset import Dataset

@dataclass
class LoadedSeries:
    series_ref: SeriesRef
    volume: np.ndarray            # [N, H, W], native dtype
    raw_bytes: list[bytes]         # raw DICOM file bytes per instance, indexed by slice
    datasets: list[Dataset]        # parsed pydicom Datasets, indexed by slice
    default_level: float
    default_window: float

def load_series(series: SeriesRef) -> LoadedSeries: ...
def auto_window_level(volume: np.ndarray, datasets: list[Dataset]) -> tuple[float, float]:
    """Return (level, window). Prefer DICOM tags from the middle slice; else auto from stats."""
```

### 6.3 Metadata fields shown

Fixed list, displayed in this order. Missing tags shown as "—".

```text
Patient ID
Patient Name
Study Instance UID
Study Date
Study Description
Series Instance UID
Series Description
Series Number
Modality
SOP Instance UID
Instance Number
Rows × Columns
Pixel Spacing
Slice Thickness
Bits Allocated
Window Center
Window Width
File Path (full path to the .dcm on disk)
```

### 6.4 W/L presets

| Preset | Window | Level |
|---|---|---|
| Brain | 80 | 40 |
| Bone | 2000 | 300 |
| Lung | 1500 | -600 |
| Soft Tissue | 400 | 50 |
| Default | (from DICOM or auto) | (from DICOM or auto) |

### 6.5 Config

```python
from PySide6.QtCore import QSettings

class Config:
    def __init__(self):
        self._s = QSettings("NeuroScan", "DesktopViewer")

    @property
    def api_url(self) -> str:
        return self._s.value("api_url", "http://localhost:8000")

    @api_url.setter
    def api_url(self, value: str) -> None:
        self._s.setValue("api_url", value)
```

## 7. Tech stack

| Layer | Tech | Version |
|---|---|---|
| GUI | PySide6 | ≥ 6.8 |
| Image display | pyqtgraph | ≥ 0.13 |
| DICOM | pydicom | ≥ 3.0 |
| DICOM compression | pylibjpeg, pylibjpeg-libjpeg, pylibjpeg-openjpeg | latest |
| Numerics | numpy | ≥ 2.1 |
| HTTP | httpx | ≥ 0.27 |
| Test | pytest | ≥ 8.3 |
| Tooling | uv + pyproject.toml | per AD-6 |
| Lint | ruff (same config style as api-service) | ≥ 0.7 |

## 8. Repository changes

```text
neuroscan-workstation/
├── apps/
│   ├── desktop-viewer/                    # NEW
│   │   ├── app/
│   │   │   ├── __init__.py
│   │   │   ├── main.py
│   │   │   ├── main_window.py
│   │   │   ├── config.py
│   │   │   ├── dicom/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── loader.py
│   │   │   │   └── series.py
│   │   │   ├── widgets/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── browser_panel.py
│   │   │   │   ├── viewer_panel.py
│   │   │   │   ├── metadata_panel.py
│   │   │   │   ├── empty_state.py
│   │   │   │   └── settings_dialog.py
│   │   │   └── upload/
│   │   │       ├── __init__.py
│   │   │       └── worker.py
│   │   ├── tests/
│   │   │   ├── __init__.py
│   │   │   ├── unit/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── test_loader.py
│   │   │   │   ├── test_series.py
│   │   │   │   └── test_window_level.py
│   │   │   └── fixtures/
│   │   │       ├── __init__.py
│   │   │       └── make_test_series.py
│   │   ├── pyproject.toml
│   │   ├── uv.lock
│   │   └── README.md
│   └── web-viewer/                        # already exists, untouched
├── scripts/
│   └── generate-synthetic-dicom.py        # MODIFIED: add --count flag
├── .github/workflows/ci.yml               # MODIFIED: add desktop-viewer job
├── docs/
│   ├── status.md                          # MODIFIED at end of slice
│   ├── roadmap.md                         # MODIFIED at end of slice
│   └── superpowers/
│       └── specs/
│           └── 2026-05-05-slice-2-qt-desktop-viewer-design.md  # this file
└── ...
```

Nothing in `services/`, nothing in `infra/`, nothing in `apps/web-viewer/` is touched.

## 9. Local development

### Prerequisites

- macOS, Linux, or Windows with Qt prerequisites (PySide6 wheels handle this on macOS automatically)
- Python 3.12+
- `uv`
- (Optional) Slice 1 stack running locally if you want to test the Upload button

### Run

```bash
cd apps/desktop-viewer
uv sync
uv run python -m app.main
```

App opens. Use **File → Open Folder…** or click "Load sample data" on the empty state.

### Test

```bash
cd apps/desktop-viewer
uv run pytest tests/unit/ -v
uv run ruff check .
uv run ruff format --check .
```

## 10. Testing strategy

### Unit tests (pytest, no Qt)

- `test_loader.py`:
  - `scan_folder` returns empty for an empty dir
  - `scan_folder` skips non-DICOM files silently
  - `scan_folder` correctly groups multiple files of the same series
  - `scan_folder` sorts instances by `InstanceNumber`
  - `scan_folder` handles missing optional tags
- `test_series.py`:
  - `load_series` produces `[N, H, W]` volume of expected shape
  - `auto_window_level` returns DICOM tag values when present
  - `auto_window_level` falls back to stats when tags absent
- `test_window_level.py`:
  - `apply_window_level` clamps low and high correctly
  - `apply_window_level` produces uint8 in `[0, 255]`
  - `apply_window_level` handles `window=0` without ZeroDivisionError

### Manual smoke (the QA artifact)

Documented in `apps/desktop-viewer/README.md`:
1. Open `data/sample-dicom/real/` → see brain MR study, single-slice series.
2. Click the series → image renders in center panel.
3. Try W/L sliders → contrast changes.
4. Try preset buttons → contrast jumps to clinical defaults.
5. Generate a 32-slice synthetic series via `scripts/generate-synthetic-dicom.py --count 32 --output /tmp/multi/` → open that folder → scroll wheel through slices, arrow keys work.
6. Click Upload (with Slice 1 stack up at http://localhost:8000) → see `Uploaded ✓` → check http://localhost:5173/studies for the new study.
7. Stop Slice 1's api-service → click Upload → see clear error in status label, app stays responsive.
8. Open Settings → change URL → close app → reopen → verify URL persisted.

### CI

Existing `.github/workflows/ci.yml` gains a third job:

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
    - run: uv sync --frozen
    - run: uv run ruff check .
    - run: uv run ruff format --check .
    - run: uv run pytest tests/unit/ -q
```

No display server. No Qt main loop. Pure logic tests only.

## 11. Non-functional requirements

- App start to ready: < 2s on macOS Apple Silicon.
- Loading a 100-instance series: < 3s.
- Slice navigation latency: < 50ms per slice (visually instant).
- W/L slider drag should re-render at ≥ 30fps on a 256×256 series.
- Upload of a single 1MB DICOM: < 5s.
- App must not freeze the UI during folder load or upload (background threads).

## 12. Risks and mitigations

| Risk | Mitigation |
|---|---|
| pyqtgraph default scroll-wheel = zoom conflicts with our slice navigation | Install our own `eventFilter` on the view; consume the event when no Ctrl/Cmd modifier. |
| Compressed DICOMs (JPEG-LS, etc.) fail without decoders | Ship `pylibjpeg` + `pylibjpeg-libjpeg` + `pylibjpeg-openjpeg` in deps. (AD-S2-8) |
| Large series (1000+ slices) consume too much memory | Document limit in README. Future slice can add lazy-loading per-slice if needed. |
| Threading bugs (load/upload races, signal cross-thread) | Use `Qt.QueuedConnection` for cross-thread signals; one-shot upload worker; no shared mutable state between worker and UI. |
| pyqtgraph histogram tools confuse users | Hide them via `imageView.ui.histogram.hide()` etc. We provide our own W/L UI. |
| QSettings on Windows uses registry — unfamiliar to me on Mac dev box | Limit to string values; verify on macOS as primary platform. |

## 13. Definition of Done

Slice 2 is done when **all** of the following are true:

1. `cd apps/desktop-viewer && uv sync && uv run python -m app.main` opens the app on a fresh checkout (macOS).
2. **File → Open Folder…** loads `data/sample-dicom/real/` and shows the brain MR study in the browser.
3. Selecting the series displays the image in the center panel.
4. A 32-slice synthetic series (generated via the new `--count 32` flag) loads and supports slice navigation by slider, scroll wheel, and arrow keys.
5. Window/level sliders visibly change contrast; all four W/L preset buttons (Brain/Bone/Lung/Soft Tissue) work; Default/Reset works.
6. Zoom (scroll + Ctrl/Cmd) and pan (middle-drag) work in the image view.
7. Metadata panel shows all 17 tag rows from §6.3 for the current instance and updates on slice change.
8. With the Slice 1 stack running at `http://localhost:8000`:
   - Upload button posts the current instance's bytes
   - Status label shows `Uploaded ✓ (sha256: ...)`
   - The new study appears at `http://localhost:5173/studies`
9. With api-service stopped, Upload shows a clear error and the app stays responsive.
10. Settings dialog persists the API URL across app restarts (verified by `QSettings`).
11. Empty-state "Load sample data" link appears when `data/sample-dicom/real/` exists and is gone otherwise.
12. `pytest tests/unit/` passes (≥ 11 tests covering loader, series, W/L math).
13. `ruff check .` and `ruff format --check .` are clean.
14. CI's new `desktop-viewer` job is green.
15. `apps/desktop-viewer/README.md` documents how to run, manual smoke checklist, and known limitations.
16. `scripts/generate-synthetic-dicom.py --count 32 --output <dir>` produces a valid 32-instance MR series.
17. `docs/status.md` and `docs/roadmap.md` updated to mark Slice 2 done.
18. This spec is committed and referenced from `docs/status.md`.

## 14. Future phases (unchanged)

| Slice | Scope |
|---|---|
| 3 | Reconstruction service (k-space → DICOM → Orthanc) |
| 4 | MinIO + signed URLs |
| 5 | De-identification |
| 6 | Auth + studies cache in Postgres |
| 7 | Prom/Grafana |
| 8 | Cornerstone3D viewer + multiplanar + measurements |
| 9 | Background job queue |
| 10+ | K8s, real cloud |

Slice 2 does not introduce new entries to the future-phases table.
