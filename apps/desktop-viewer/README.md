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
    --count 32 --output "$PWD/data/sample-dicom/synthetic-series" --rows 128 --columns 128
```

Then **File → Open Folder…** → that directory.

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
5. ☐ Generate `data/sample-dicom/synthetic-series/` (32-slice series), open it, scroll wheel cycles slices.
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
