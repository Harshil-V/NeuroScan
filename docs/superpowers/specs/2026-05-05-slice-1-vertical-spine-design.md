# NeuroScan Workstation — Slice 1: Vertical Spine

**Date:** 2026-05-05
**Status:** Draft (pending user review)
**Phase:** 1 of N (see "Future Phases" at end)
**Parent project:** NeuroScan Workstation — local-first MRI / DICOM platform

---

## 1. Purpose

Build the thinnest end-to-end vertical slice of the NeuroScan Workstation: a user can drag a DICOM file into a React web app, the file lands in a local Orthanc archive, the audit log records the event, and the user sees the study in a list with a PNG preview.

This slice exists to prove the integration spine works (React ↔ FastAPI ↔ Orthanc ↔ Postgres) before any of the more visible features (Qt desktop viewer, MRI reconstruction, secure cloud transfer simulation) are layered on. Each later feature gets its own spec, plan, and implementation cycle.

## 2. Out-of-Scope (deliberately deferred)

Anything in the parent PRD that is not listed in §5 is out of scope for this slice. Specifically deferred:

- Qt / PySide6 desktop viewer
- MRI reconstruction service (FFT, k-space, generated DICOM output)
- MinIO object storage and signed-URL flow
- De-identification scanner
- Authentication / authorization (JWT, RBAC)
- Prometheus + Grafana + structured logging
- Redis, background workers, async job queue
- Cornerstone3D / OHIF viewer integration
- Postgres tables for studies / series / instances (Orthanc remains the only source of truth for those in this slice)
- Real cloud deployment (AWS/GCP)
- Kubernetes

These are mapped to future slices in §16.

## 3. Architecture

```text
┌──────────────────┐   multipart   ┌────────────────────────┐
│  React Web App   │──────────────▶│   FastAPI api-service  │
│  (Vite + TS)     │◀──────────────│   :8000                │
│  :5173           │   JSON / PNG  └─────┬──────────────┬───┘
└──────────────────┘                     │              │
                                         │ REST         │ SQL
                                         ▼              ▼
                              ┌────────────────┐  ┌─────────────┐
                              │  Orthanc       │  │ PostgreSQL  │
                              │  :8042 (REST)  │  │ :5432       │
                              │  :4242 (DIMSE) │  │ audit_events│
                              └────────────────┘  └─────────────┘
```

### Service responsibilities

- **React web app (`apps/web-viewer`)** — UI only. Talks exclusively to api-service. Never to Orthanc directly.
- **api-service (FastAPI)** — Sole entry point. Validates DICOM uploads, computes checksums, talks to Orthanc, writes audit rows, proxies study/series/instance reads from Orthanc, proxies PNG previews.
- **Orthanc** — DICOM archive. Source of truth for studies, series, instances, and pixel data.
- **Postgres** — App-owned data only. In slice 1: just the `audit_events` table. Studies/series/instances are *not* duplicated here.

### Key architectural decisions (locked)

| ID | Decision | Rationale |
|---|---|---|
| AD-1 | Postgres holds only `audit_events` in slice 1 | Smallest amount of code that still demonstrates an audit trail. Migration path to a cache/projection model preserved (§7). |
| AD-2 | Orthanc's built-in `/instances/{id}/preview` endpoint provides PNG previews, proxied by api-service | Zero pixel-rendering code in slice 1. When window/level controls are added later, swap to pydicom + Pillow. |
| AD-3 | React never talks to Orthanc directly | Single audited entry point. Future auth/RBAC has one place to enforce. |
| AD-4 | Upload is synchronous (no Redis, no queue) | Sample DICOMs are small. Async + queue is its own slice. |
| AD-5 | Sample data: synthetic-generated fixtures (CI) + one small real TCIA series (demo) | Synthetic = fast deterministic CI. Real = honest portfolio screenshots. |
| AD-6 | Python tooling: uv + pyproject.toml | Fast, lockfile, clean Dockerfiles. |
| AD-7 | JS tooling: npm + Vite, no workspaces | One JS package. YAGNI on monorepo machinery. |
| AD-8 | Alembic migrations from day 1 | Cheap now, painful to retrofit later. |
| AD-9 | Integration tests via testcontainers | Pytest-managed lifecycle, no separate compose file to maintain. |

## 4. Data flows

### 4.1 Upload

1. User drops a DICOM file in the React `UploadPage` → `POST /api/dicom/upload` (multipart, field name `file`).
2. api-service:
   1. Reads bytes into memory.
   2. Validates with `pydicom.dcmread(BytesIO, force=False)`. On parse failure → 400 `invalid_dicom`, audit row with `status=failure`.
   3. Verifies required tags (`StudyInstanceUID`, `SeriesInstanceUID`, `SOPInstanceUID`, `Modality`). Missing → 400 `missing_required_tag`, audit row with `status=failure`.
   4. Computes `sha256` of the raw bytes.
   5. `POST /instances` to Orthanc with the raw bytes. On non-2xx → 502 `orthanc_rejected`, audit row with `status=failure`.
   6. Writes one `audit_events` row with `event_type=dicom_uploaded`, `status=success`, all UIDs, orthanc instance id, checksum.
3. Response: `{ status: "uploaded", study_instance_uid, series_instance_uid, sop_instance_uid, orthanc_instance_id, checksum }`.

### 4.2 List / detail

- `GET /api/studies?limit&offset`: api-service calls Orthanc `/studies?expand`, maps each entry to the DTO in §6, returns paginated.
- `GET /api/studies/{study_instance_uid}`: resolve to Orthanc study id (Orthanc `/tools/find` with the UID), fetch study + child series, return composite DTO.
- `GET /api/series/{series_instance_uid}/instances`: same pattern.
- No audit rows are written for read operations in slice 1. (`preview_viewed` is reserved as a future event type but not emitted yet.)

### 4.3 Preview

- `GET /api/instances/{orthanc_instance_id}/preview.png`: api-service streams Orthanc `/instances/{id}/preview` (already PNG) back to the client. `Content-Type: image/png`, cache headers passthrough.

### 4.4 Audit

- `GET /api/audit/events?limit&offset&event_type&status`: pure Postgres read, ordered by `created_at DESC`. No write side effects.

## 5. Slice 1 scope (what we build)

### Backend (api-service)

- FastAPI app skeleton, `pydantic-settings` config, SQLAlchemy + Alembic, structured logger (stdlib `logging` with JSON formatter; full structured-logging story comes later).
- Routes: health, dicom upload, studies list/detail, series instances, preview proxy, audit list.
- `OrthancClient` (httpx, async, retries on 5xx with exponential backoff up to 3 attempts).
- DICOM validation + metadata extraction module (pydicom).
- Audit writer.

### Web (web-viewer)

- Vite + React 18 + TypeScript.
- Routing via `react-router-dom` (≥6).
- API state via `@tanstack/react-query` (cache, retries, loading states for free).
- Pages: `/studies` (list), `/studies/:studyInstanceUid` (detail + previews), `/upload` (dropzone), `/audit` (table).
- Styling: CSS Modules. No Tailwind in slice 1 (kept simple; can migrate later).
- Typed API client (one fetch wrapper per resource, generated types kept in `src/types/`).

### Infrastructure (`infra/docker-compose.yml`)

Services:
- `postgres:16` — exposes 5432, volume-backed.
- `orthanc/orthanc:latest` — exposes 8042 (REST) and 4242 (DIMSE), volume-backed, `orthanc.json` mounts a config with the DICOMweb plugin enabled (for forward compatibility) and credentials from env.
- `api-service` — built from `services/api-service/Dockerfile`, depends on postgres + orthanc, runs Alembic migrations on startup.
- `web-viewer` — built from `apps/web-viewer/Dockerfile`, served by Vite preview or nginx (see §10).

A `.env.example` at the repo root documents every variable.

### Tests

- Unit (pytest): DICOM validation, metadata extraction, checksum, Orthanc client (mocked with respx).
- Integration (pytest + testcontainers): real Postgres + Orthanc, full upload happy path, full upload negative path (txt file), audit list returns the expected row.
- E2E (Playwright, in `tests/e2e/`): one happy-path scenario — start compose, upload a synthetic DICOM, see it in the studies list, open detail, see the preview render.

### CI (`.github/workflows/ci.yml`)

Three parallel jobs:
1. `python` — `uv sync`, `ruff check`, `ruff format --check`, `pytest` (testcontainers run in GH-hosted Docker).
2. `web` — `npm ci`, `tsc --noEmit`, `eslint`, `vite build`.
3. `e2e` — `docker compose -f infra/docker-compose.yml up -d`, `npx playwright test`, teardown.

### Sample data

- `scripts/generate-synthetic-dicom.py` — uses pydicom to fabricate a small valid MR DICOM series from numpy arrays. Outputs to `data/sample-dicom/synthetic/` (gitignored). Used as the canonical fixture by all unit/integration/E2E tests via a pytest fixture that regenerates on demand.
- `scripts/download-sample-tcia.sh` — fetches one small public MR series from TCIA into `data/sample-dicom/tcia-brain-mr/` (gitignored). Used for manual demos and README screenshots only. README documents the exact collection + URL so anyone can reproduce.
- No git-lfs.

## 6. API contract

All app routes are prefixed `/api`. Errors return `{ detail: string, code?: string }` with appropriate 4xx/5xx status.

### `GET /health`

```json
{
  "status": "ok",
  "service": "api-service",
  "version": "0.1.0",
  "orthanc_reachable": true,
  "db_reachable": true
}
```

Returns 200 only when both `orthanc_reachable` and `db_reachable` are true; otherwise 503 with the same body.

### `POST /api/dicom/upload`

Request: `multipart/form-data` with field `file`.

Success (201):
```json
{
  "status": "uploaded",
  "study_instance_uid": "1.2.840...",
  "series_instance_uid": "1.2.840...",
  "sop_instance_uid": "1.2.840...",
  "orthanc_instance_id": "abc-123",
  "checksum_sha256": "..."
}
```

Errors:
- 400 `invalid_dicom` — pydicom could not parse.
- 400 `missing_required_tag` — required tag absent.
- 502 `orthanc_rejected` — Orthanc returned non-2xx.

### `GET /api/studies?limit=50&offset=0`

```json
{
  "items": [
    {
      "orthanc_study_id": "...",
      "study_instance_uid": "...",
      "patient_id": "...",
      "modality": "MR",
      "study_date": "2026-04-01",
      "study_description": "BRAIN MR",
      "series_count": 2,
      "instance_count": 32
    }
  ],
  "total": 1,
  "limit": 50,
  "offset": 0
}
```

### `GET /api/studies/{study_instance_uid}`

```json
{
  "orthanc_study_id": "...",
  "study_instance_uid": "...",
  "patient_id": "...",
  "modality": "MR",
  "study_date": "2026-04-01",
  "study_description": "BRAIN MR",
  "series": [
    {
      "orthanc_series_id": "...",
      "series_instance_uid": "...",
      "series_description": "T1",
      "modality": "MR",
      "series_number": 1,
      "instance_count": 16
    }
  ]
}
```

### `GET /api/series/{series_instance_uid}/instances`

```json
{
  "items": [
    {
      "orthanc_instance_id": "...",
      "sop_instance_uid": "...",
      "instance_number": 1,
      "rows": 256,
      "columns": 256
    }
  ]
}
```

### `GET /api/instances/{orthanc_instance_id}/preview.png`

Returns `image/png`. 404 if Orthanc returns 404.

### `GET /api/audit/events?limit=50&offset=0&event_type=&status=`

```json
{
  "items": [
    {
      "event_id": "uuid",
      "event_type": "dicom_uploaded",
      "status": "success",
      "message": null,
      "actor": "local-user",
      "study_instance_uid": "...",
      "series_instance_uid": "...",
      "sop_instance_uid": "...",
      "orthanc_instance_id": "...",
      "checksum_sha256": "...",
      "created_at": "2026-05-05T17:00:00Z"
    }
  ],
  "total": 1,
  "limit": 50,
  "offset": 0
}
```

## 7. Data model

```sql
CREATE TABLE audit_events (
  id                   BIGSERIAL PRIMARY KEY,
  event_id             UUID NOT NULL UNIQUE,
  event_type           TEXT NOT NULL,
  status               TEXT NOT NULL,
  message              TEXT,
  actor                TEXT NOT NULL DEFAULT 'local-user',
  study_instance_uid   TEXT,
  series_instance_uid  TEXT,
  sop_instance_uid     TEXT,
  orthanc_instance_id  TEXT,
  checksum_sha256      TEXT,
  created_at           TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_audit_created_at ON audit_events (created_at DESC);
CREATE INDEX idx_audit_event_type ON audit_events (event_type);
```

`event_type` allowed values in slice 1: `dicom_uploaded` (success and failure both use this; failures distinguished by `status=failure`). Reserved for later: `preview_viewed`, `study_listed`, `reconstruction_started`, `reconstruction_completed`.

`status` allowed values: `success`, `failure`.

Future migration path: when slice that needs `studies`/`series`/`instances` cache lands, add those tables; `audit_events` already references them by UID, so no FK retrofitting headaches.

## 8. Repository layout (slice 1)

```text
neuroscan-workstation/
├── apps/
│   └── web-viewer/
│       ├── src/{pages,components,api,types}/
│       ├── index.html
│       ├── package.json
│       ├── tsconfig.json
│       ├── vite.config.ts
│       └── Dockerfile
├── services/
│   └── api-service/
│       ├── app/
│       │   ├── main.py
│       │   ├── config.py
│       │   ├── db.py
│       │   ├── routes/{health,dicom,studies,audit}.py
│       │   ├── clients/orthanc.py
│       │   ├── services/{upload,audit}.py
│       │   ├── models/audit.py
│       │   ├── schemas/
│       │   └── alembic/
│       ├── tests/{unit,integration,fixtures}/
│       ├── pyproject.toml
│       ├── uv.lock
│       └── Dockerfile
├── infra/
│   ├── docker-compose.yml
│   ├── orthanc/orthanc.json
│   └── postgres/init.sql
├── data/sample-dicom/{synthetic,tcia-brain-mr}/   # gitignored
├── tests/e2e/                                     # Playwright
├── scripts/{generate-synthetic-dicom.py,download-sample-tcia.sh}
├── docs/superpowers/specs/
├── .github/workflows/ci.yml
├── .env.example
├── .gitignore
├── README.md
└── LICENSE
```

## 9. UI requirements (web-viewer)

Pages and minimum content:

- **`/studies`** — table of studies with columns: Study Date, Patient ID, Modality, Study Description, Series, Instances. Row click → `/studies/:studyInstanceUid`. Empty state with a CTA to `/upload`.
- **`/studies/:studyInstanceUid`** — header with study metadata. List of series. For each series, a horizontal strip of preview thumbnails (one `<img>` per instance pointing at `/api/instances/{id}/preview.png`). Click a thumbnail → larger preview pane.
- **`/upload`** — dropzone (drag-and-drop + click-to-pick). On drop: POST to `/api/dicom/upload`, show inline progress, on success show the returned UIDs and a link to the new study, on failure show `code` + `detail`.
- **`/audit`** — table of audit events with simple filter controls (event_type select, status select, date range deferred to a later slice). Newest first.

No sidebar, no global nav fanciness. A simple top nav with four links is enough. Responsive layout is required only insofar as the table doesn't break on a 1280px-wide viewport; full mobile responsiveness is deferred.

## 10. Local development

### Prerequisites

- Docker Desktop or equivalent (with Compose v2)
- Python 3.12 + `uv` (`brew install uv`)
- Node 20+
- macOS, Linux, or WSL2 (the project is developed on macOS but should work on Linux)

### Start the stack

```bash
docker compose -f infra/docker-compose.yml up -d
```

After this:
- React app: http://localhost:5173
- api-service: http://localhost:8000/docs
- Orthanc UI: http://localhost:8042 (creds in `.env.example`)
- Postgres: localhost:5432

### Run api-service outside Docker (for fast iteration)

```bash
cd services/api-service
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --reload --port 8000
```

### Run web-viewer outside Docker

```bash
cd apps/web-viewer
npm install
npm run dev
```

The compose `web-viewer` service uses an nginx-based production-style image; the local-dev story uses `npm run dev` for HMR.

## 11. Configuration

All config via env vars, loaded by `pydantic-settings`. `.env.example`:

```env
# api-service
API_PORT=8000
DATABASE_URL=postgresql+psycopg://neuroscan:neuroscan@postgres:5432/neuroscan
ORTHANC_URL=http://orthanc:8042
ORTHANC_USER=orthanc
ORTHANC_PASSWORD=orthanc
LOG_LEVEL=INFO

# web-viewer (Vite)
VITE_API_BASE_URL=http://localhost:8000
```

## 12. Testing strategy (detail)

### Unit (≥ 80% coverage of backend `services/` and `clients/`)

- `validate_dicom`: accepts synthetic, rejects empty bytes, rejects truncated bytes, rejects valid file with missing required tag.
- `extract_metadata`: returns expected fields; missing optional tags result in `None` not exceptions.
- `sha256_of`: deterministic, matches reference.
- `OrthancClient.upload_instance`: respx-mocked — happy path, 4xx, 5xx with retry exhaustion.
- `OrthancClient.get_studies`: respx-mocked.

### Integration (testcontainers spin Postgres + Orthanc once per session)

- Upload → 201, returns expected fields, audit row with `success`.
- Upload garbage → 400 `invalid_dicom`, audit row with `failure`.
- Upload valid DICOM missing `Modality` → 400 `missing_required_tag`, audit row with `failure`.
- After upload, `GET /api/studies` returns ≥ 1 item with the expected UID.
- `GET /api/studies/{uid}` returns the expected series count.
- `GET /api/instances/{id}/preview.png` returns 200 + `image/png`.
- `GET /api/audit/events` returns rows in DESC `created_at` order.

### E2E (Playwright)

One scenario: navigate to `/upload`, drop a synthetic DICOM, assert success toast, navigate to `/studies`, assert the row, click in, assert at least one preview image renders (Playwright `expect(locator).toBeVisible()` plus a non-zero `naturalWidth` check).

### Manual QA checklist (lives in `docs/qa-validation-plan.md`, written in this slice)

Items: invalid DICOM upload, large DICOM upload (~100 MB synthetic), missing-metadata DICOM, Orthanc service down (compose stop), Postgres down (compose stop), web app browser refresh during upload.

## 13. Non-functional requirements (slice 1 only)

- Upload of a < 10 MB DICOM completes in < 5 s on a developer laptop.
- `GET /api/studies` responds in < 500 ms with up to 100 studies in Orthanc.
- Preview endpoint responds in < 2 s.
- Compose `up` to "all healthy" in < 90 s on first run (after images pulled).
- All services must restart cleanly: `docker compose restart` leaves data intact.

Observability beyond `/health` (Prom/Grafana, structured logging, request IDs end-to-end) is deferred.

## 14. Risks and mitigations

| Risk | Mitigation |
|---|---|
| Orthanc API quirks (study/series/instance id mapping vs. UIDs) | `OrthancClient` encapsulates this; integration tests pin behavior. |
| pydicom edge cases on real TCIA data | Synthetic fixtures in CI; real series tested manually only. README documents the exact dataset used. |
| Testcontainers slow / flaky on GH Actions | Session-scoped fixtures; retry once on container-start failure; if persistent, fall back to a `docker-compose.test.yml` (revisit AD-9). |
| Playwright flake | Single happy-path test only; gated to its own job; can move to nightly if it gets noisy. |
| Scope creep into reconstruction / Qt during slice 1 | This spec; out-of-scope list in §2; future-phase mapping in §16. |

## 15. Definition of Done

Slice 1 is done when **all** of the following are true:

1. `docker compose -f infra/docker-compose.yml up -d` brings up postgres + orthanc + api-service + web-viewer cleanly on a fresh checkout.
2. Visiting http://localhost:5173 shows the React app.
3. Uploading a synthetic DICOM via the web UI returns success, the study appears in `/studies`, the detail page shows series, and a preview image renders.
4. Uploading a non-DICOM file via the web UI shows a structured error message in the UI.
5. `/audit` shows both the success and failure events from the previous two steps.
6. `pytest` passes locally and in CI.
7. `npm run build` and `tsc --noEmit` pass.
8. The Playwright happy-path test passes locally and in CI.
9. README explains: how to install prereqs, how to start the stack, how to run tests, how to fetch the TCIA sample, and known limitations (no auth, no de-id, etc.).
10. `docs/qa-validation-plan.md` exists with the manual QA checklist filled in.
11. This spec is committed and referenced from the README.

## 16. Future phases (mapped from parent PRD)

| Slice | Scope | Adds to schema | Adds infra |
|---|---|---|---|
| 2 | Qt desktop viewer (standalone, local DICOM dir, no backend dep) | — | — |
| 3 | Reconstruction service (k-space → reconstructed image → DICOM → Orthanc) | `reconstruction_jobs` | reconstruction-service container |
| 4 | MinIO + signed-URL upload flow + checksum-validated object storage | `storage_objects` | minio container |
| 5 | De-identification scanner + warning UI on upload | (enum additions) | — |
| 6 | Auth (JWT, RBAC), studies/series/instances cache tables in Postgres | `users`, `studies`, `series`, `instances` | — |
| 7 | Prometheus + Grafana + structured logging with request IDs | — | prometheus, grafana |
| 8 | Cornerstone3D viewer upgrade (window/level, multi-frame, measurements) | — | — |
| 9 | Background job queue (Redis + Celery or RQ); async reconstruction with retries | — | redis container |
| 10+ | Kubernetes manifests; real cloud (S3/GCS); CI/CD deploy pipeline | — | — |

Each subsequent slice goes through its own brainstorming → spec → plan cycle. No slice is committed until its predecessors' Definition of Done is met.
