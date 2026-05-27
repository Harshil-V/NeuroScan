# NeuroScan Workstation — Status

**Last updated:** 2026-05-12

> Frequently-updated, short. If you're returning to this project after a break, read this first.

## Current slice

**Slice 4 — MinIO Object Storage + Signed URLs.** Merged to `main` 2026-05-27.

Spec: [`superpowers/specs/2026-05-07-slice-4-minio-storage-design.md`](./superpowers/specs/2026-05-07-slice-4-minio-storage-design.md)
Plan: [`superpowers/plans/2026-05-07-slice-4-minio-storage.md`](./superpowers/plans/2026-05-07-slice-4-minio-storage.md)

Slice 3 (merged to `main`):
- Spec: [`superpowers/specs/2026-05-06-slice-3-reconstruction-service-design.md`](./superpowers/specs/2026-05-06-slice-3-reconstruction-service-design.md)
- Plan: [`superpowers/plans/2026-05-06-slice-3-reconstruction-service.md`](./superpowers/plans/2026-05-06-slice-3-reconstruction-service.md)

Slice 2 (merged to `main`):
- Spec: [`superpowers/specs/2026-05-05-slice-2-qt-desktop-viewer-design.md`](./superpowers/specs/2026-05-05-slice-2-qt-desktop-viewer-design.md)
- Plan: [`superpowers/plans/2026-05-06-slice-2-qt-desktop-viewer.md`](./superpowers/plans/2026-05-06-slice-2-qt-desktop-viewer.md)
- README: [`../apps/desktop-viewer/README.md`](../apps/desktop-viewer/README.md)

Slice 1 (merged to `main`):
- Spec: [`superpowers/specs/2026-05-05-slice-1-vertical-spine-design.md`](./superpowers/specs/2026-05-05-slice-1-vertical-spine-design.md)
- Plan: [`superpowers/plans/2026-05-05-slice-1-vertical-spine.md`](./superpowers/plans/2026-05-05-slice-1-vertical-spine.md)
- QA plan: [`qa-validation-plan.md`](./qa-validation-plan.md)

## What's done

- Repo initialized with project context docs (overview, roadmap, status, original PRD)
- Slice 1 design spec written, reviewed, approved
- Slice 1 implementation plan written
- Slice 1 implementation complete on `slice-1-vertical-spine`:
  - Docker Compose stack: postgres, orthanc, api-service, web-viewer (all healthy)
  - FastAPI api-service: `/health`, `/api/dicom/upload`, `/api/studies`, `/api/studies/{uid}`, `/api/series/{uid}/instances`, `/api/instances/{id}/preview.png`, `/api/audit/events`
  - Global `UploadFailedError` exception handler emits flat `{detail, code}` JSON
  - SQLAlchemy + Alembic with `audit_events` table (cross-dialect UUID + BigInt-with-SQLite-Integer-variant for tests)
  - `OrthancClient` (httpx async, retries with exponential backoff, respx-tested)
  - DICOM validation, metadata extraction, checksum, upload orchestrator
  - React web viewer (Vite + TS + react-router + TanStack Query): study list, study detail with preview thumbnails, upload page, audit page
  - Synthetic DICOM fixture + manual TCIA download script
  - 24 unit tests + 12 integration tests (testcontainers) + 1 Playwright E2E happy-path
  - GitHub Actions CI (python, web, e2e jobs)
  - QA validation plan with 7 manual test cases
  - macOS + OrbStack quirks documented in README and QA plan
- Slice 1 merged to `main` 2026-05-05, pushed.
- Slice 2 design spec written, reviewed, approved.
- Slice 2 implementation plan written.
- Slice 2 implementation complete on `slice-2-qt-desktop-viewer`:
  - PySide6 6.11 desktop app at `apps/desktop-viewer/` with 3-panel layout
  - DICOM folder scanner with Study/Series/Instance grouping (10 unit tests)
  - pyqtgraph ImageView with zoom (Cmd+scroll) / pan (middle-drag)
  - Slice navigation: slider, scroll wheel, ↑/↓/←/→ keys
  - Window/level: 2 sliders + 4 clinical presets (Brain/Bone/Lung/Soft Tissue) + Default
  - Metadata panel with 18-row DICOM tag table
  - Upload-to-backend button with httpx + QThread (5 respx tests)
  - Settings dialog persisting `api_url` via `QSettings`
  - Empty-state "Load sample data" shortcut for zero-friction demo
  - Compressed DICOM support via pylibjpeg
  - Multi-slice synthetic generator (`scripts/generate-synthetic-dicom.py --count N`)
  - 32-slice synthetic test data committed under `data/sample-dicom/synthetic-series/` (gitignored)
  - 29 unit tests total (loader 10, window/level 7, series 7, upload worker 5)
  - New `desktop-viewer` job in CI (lint + 29 unit tests, headless Qt with `QT_QPA_PLATFORM=offscreen`)
  - README with usage docs + 13-item manual smoke checklist

- Slice 3 implementation complete on `slice-3-reconstruction-service`:
  - Six pure-logic modules: `kspace_loader`, `fft_reconstruct`, `forward_fft`, `metrics` (PSNR+SSIM), `dicom_writer`, `job_runner`
  - `reconstruction_jobs` table (alembic migration 002, 15 columns, 2 indexes)
  - `POST /api/reconstruction/jobs` + `GET /api/reconstruction/jobs/{id}` + `GET /api/reconstruction/jobs`
  - FastAPI BackgroundTasks (sync, threadpool) — 0 ms response latency on submit
  - Forward-FFT helper: DICOM → `.npz` with embedded ground truth → honest PSNR/SSIM
  - h5py for fastMRI HDF5 input; scikit-image for SSIM
  - React `/reconstruction` page: dropzone, polling job table, side-by-side preview, "Open reconstructed study" link
  - `scripts/generate-synthetic-kspace.py` CLI
  - 56 unit tests + 17 integration tests = **73 tests** total
  - QA TC-08 + README quickstart added
  - Integration test confirmed: FFT round-trip PSNR > 60 dB, SSIM > 0.95

- Slice 4 implementation complete on `slice-4-minio-storage`:
  - `storage_objects` table (alembic migration 003) with SHA-256 content addressing
  - `S3Client` (boto3, path-style addressing, retries) with moto-mocked unit tests
  - `services/storage.py`: `tee_to_s3`, `mint_presigned_url`, `object_key_for`
  - `routes/storage.py`: list, detail, presigned-url endpoints
  - Orchestrator + job_runner write to MinIO after Orthanc on every upload (best-effort)
  - Best-effort: MinIO down → audit `status=success_minio_skipped`, upload still 201
  - `/health` reports `minio_reachable`; status downgrades to `degraded` when MinIO is down
  - Audit page gains a "Share link" button (looks up storage_object by SHA-256)
  - MinIO container in compose (port 9000/9001); `MINIO_*` env vars in `.env.example`
  - 69 unit tests + 22 integration tests = **91 tests** total
  - QA TC-09 + README MinIO console URL added

## What's next

1. Brainstorm Slice 5 — De-identification scanner + warning UI on upload.

## Test data

| Folder | Data | Slices | Use |
|---|---|---|---|
| `data/sample-dicom/real/` | Real brain MR | 1 | Single-instance load, upload |
| `data/sample-dicom/real-multislice/` | Real MR pixels, 20 slices | 20 | Slice nav, W/L, Default preset |
| `data/sample-dicom/synthetic-series/` | Synthetic gradient | 32 | Many-slice stress test |

## Open questions / blockers

None.

## Recent decisions log

- 2026-05-05: Locked decomposition strategy: vertical-slice first (Option A).
- 2026-05-05: Locked AD-1 through AD-9 cross-slice decisions.
- 2026-05-05: Locked slice 1 scope: includes audit + checksum + CI + Playwright; defers auth, MinIO, de-id, metrics.
- 2026-05-05: Slice 1 implementation complete and merged to `main`.
- 2026-05-06: Locked AD-S2-1..9 (PySide6, pyqtgraph, in-memory volume, software W/L, QSettings, no Docker for desktop, no pytest-qt, pylibjpeg deps, CI lint+unit only).
- 2026-05-06: Slice 2 implementation complete and merged to `main`. 29 unit tests passing.
- 2026-05-12: Locked AD-S4-1..10 (sidecar topology, both DICOM and reconstructed outputs tee'd, single bucket with prefixes, best-effort failure, boto3, presigned GET only, share-link button on audit page, no FK in storage_objects, audit status enum widened, bucket auto-create on startup).
- 2026-05-12: Slice 4 implementation complete on `slice-4-minio-storage`.
- 2026-05-27: Slice 4 merged to `main` after end-to-end QA pass (all 12 TC-09 criteria met). Two post-implementation bugs fixed: presigned URL hostname (signed with public URL for browser fetch) and `audit_events.status` VARCHAR(16) overflow.

### Slice 2 implementation deviations from spec/plan (record for posterity)

- **Test count off by one in plan prose:** plan summary said 9 tests after B2 and 23 total; verbatim spec yields 10 + 7 + 7 + 5 = 29. Implementation faithful to verbatim code.
- **Ruff B017 in plan code:** `pytest.raises(Exception)` for the frozen-dataclass test. Tightened to `pytest.raises(AttributeError)` (FrozenInstanceError subclasses it).
- **Ruff N802/N815 from Qt conventions:** plan widget code uses Qt's mixedCase signal names (`seriesSelected`, `uploadRequested`, etc.) and camelCase override methods (`keyPressEvent`, `eventFilter`). Added `"app/widgets/**/*.py" = ["N802", "N815"]` to ruff per-file-ignores in pyproject.toml.
- **Unused imports in plan code:** `metadata_panel.py` imported `Qt` and `QAction` without using them; `main_window.py` imported unused `Qt`. Removed both.
- **CI YAML is the only deviation from spec section §10.** All other sections implemented verbatim.

### Slice 1 implementation deviations from spec/plan (record for posterity)

- **Orthanc healthcheck:** plan used `wget`; the `orthancteam/orthanc:24.7.3` image has no `wget`/`curl`, so the healthcheck uses `python3 + urllib.request` with the same Basic auth call. Semantically identical.
- **`AuditEvent.id` column:** plan declared `BigInteger`; SQLite autoincrement requires `INTEGER PRIMARY KEY`, so we use `BigInteger().with_variant(Integer(), "sqlite")`. PostgreSQL DDL is unaffected.
- **`AuditEvent.event_id`:** plan changed `postgresql.UUID` → `sqlalchemy.Uuid`; the autogenerated migration also uses `sa.UUID()` (cross-dialect). Migration was not regenerated since the autogen output was already cross-dialect.
- **`tests/conftest.py`:** plan omitted `import app.models`; without it, `Base.metadata.create_all` creates zero tables. Added the import.
- **`tests/integration/conftest.py`:** added an autouse fixture to truncate `audit_events` between tests; plan placed cleanup inside `db_session`, which most integration tests don't request.
- **`tsconfig.node.json`:** plan had `noEmit: true` and no `composite`; this is invalid for project references. Set `composite: true` and removed `noEmit`.
- **Playwright audit assertion:** uses `page.getByText("dicom_uploaded").first()` to avoid strict-mode violations once data accumulates across runs.
- **Ruff per-file ignores:** added for `app/alembic/versions/` (E501 — autogen lines) and `tests/` (N806 — SQLAlchemy `SessionLocal` convention) and `app/routes/*.py` (B008 — FastAPI `Depends` defaults).
- **`.dockerignore`** added under `apps/web-viewer/` (build-context hygiene; not in plan).
- **OrbStack:** macOS users need `DOCKER_HOST=unix://$HOME/.orbstack/run/docker.sock` for testcontainers. Documented in README and QA plan.

These are recorded so subsequent slices that re-derive infrastructure don't repeat the same surprises.

### Slice 4 implementation deviations from spec/plan (record for posterity)

- No material deviations. Implementation followed the plan verbatim. Minor code quality fixes applied post-review: wrapped `ensure_bucket`'s `create_bucket` call in try/except, added warning log to `is_reachable`, fixed a module-level import in the test file.

## How to update this file

- Update **Current slice** when a new slice spec is approved.
- Update **What's done** when a milestone in the active slice closes.
- Update **What's next** as the immediate next 1–2 actions change.
- Append to **Recent decisions log** when a meaningful direction-changing decision is made.
- Keep this file under ~100 lines of working content (the decisions/deviations log can grow).
