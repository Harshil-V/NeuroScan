# NeuroScan Workstation — Status

**Last updated:** 2026-05-06

> Frequently-updated, short. If you're returning to this project after a break, read this first.

## Current slice

**Slice 2 — Qt desktop viewer.** Implementation complete on branch `slice-2-qt-desktop-viewer`. Pending manual smoke verification.

Spec: [`superpowers/specs/2026-05-05-slice-2-qt-desktop-viewer-design.md`](./superpowers/specs/2026-05-05-slice-2-qt-desktop-viewer-design.md)
Plan: [`superpowers/plans/2026-05-06-slice-2-qt-desktop-viewer.md`](./superpowers/plans/2026-05-06-slice-2-qt-desktop-viewer.md)
README: [`../apps/desktop-viewer/README.md`](../apps/desktop-viewer/README.md)

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

## What's next

1. Manually run the Slice 2 smoke checklist (`apps/desktop-viewer/README.md` "Manual smoke checklist") with the 32-slice series and Slice 1 stack.
2. Push the `slice-2-qt-desktop-viewer` branch.
3. Brainstorm Slice 3 — Reconstruction service (k-space → reconstructed DICOM → Orthanc).

## Open questions / blockers

None.

## Recent decisions log

- 2026-05-05: Locked decomposition strategy: vertical-slice first (Option A).
- 2026-05-05: Locked AD-1 through AD-9 cross-slice decisions.
- 2026-05-05: Locked slice 1 scope: includes audit + checksum + CI + Playwright; defers auth, MinIO, de-id, metrics.
- 2026-05-05: Slice 1 implementation complete and merged to `main`.
- 2026-05-06: Locked AD-S2-1..9 (PySide6, pyqtgraph, in-memory volume, software W/L, QSettings, no Docker for desktop, no pytest-qt, pylibjpeg deps, CI lint+unit only).
- 2026-05-06: Slice 2 implementation complete (29 unit tests, manual smoke pending).

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

## How to update this file

- Update **Current slice** when a new slice spec is approved.
- Update **What's done** when a milestone in the active slice closes.
- Update **What's next** as the immediate next 1–2 actions change.
- Append to **Recent decisions log** when a meaningful direction-changing decision is made.
- Keep this file under ~100 lines of working content (the decisions/deviations log can grow).
