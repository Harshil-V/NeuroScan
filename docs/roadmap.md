# NeuroScan Workstation — Roadmap

**Last updated:** 2026-05-27

The project is built in independently-shippable slices. Each slice goes through brainstorming → spec → plan → implementation before the next is started. No slice is committed until its predecessors' Definition of Done is met.

## Slice status

| # | Slice | Status | Spec | Notes |
|---|---|---|---|---|
| 1 | Vertical spine: Compose + FastAPI + Orthanc + Postgres + minimal React + audit + checksum + CI + E2E | **done** | [spec](./superpowers/specs/2026-05-05-slice-1-vertical-spine-design.md) · [plan](./superpowers/plans/2026-05-05-slice-1-vertical-spine.md) | Completed 2026-05-05 on branch `slice-1-vertical-spine` |
| 2 | Qt desktop viewer (standalone, reads local DICOM dir, no backend dependency) | **done** | [spec](./superpowers/specs/2026-05-05-slice-2-qt-desktop-viewer-design.md) · [plan](./superpowers/plans/2026-05-06-slice-2-qt-desktop-viewer.md) | Completed 2026-05-06 on branch `slice-2-qt-desktop-viewer` |
| 3 | Reconstruction service (k-space → reconstructed image → DICOM → Orthanc) | **done** | [spec](./superpowers/specs/2026-05-06-slice-3-reconstruction-service-design.md) · [plan](./superpowers/plans/2026-05-06-slice-3-reconstruction-service.md) | Completed 2026-05-07. In-process module inside api-service (see AD-S3-1). |
| 4 | MinIO + signed-URL upload flow + checksum-validated object storage | **done** | [spec](./superpowers/specs/2026-05-07-slice-4-minio-storage-design.md) · [plan](./superpowers/plans/2026-05-07-slice-4-minio-storage.md) | Completed 2026-05-12, merged 2026-05-27. Sidecar to Orthanc; best-effort failure mode. |
| 5 | De-identification scanner + warning UI on upload | **done** | [spec](./superpowers/specs/2026-05-27-slice-5-deid-scanner-design.md) · [plan](./superpowers/plans/2026-05-27-slice-5-deid-scanner.md) | Completed 2026-05-27. Warn-only (no tag stripping). PHI in web upload panel + desktop viewer. |
| 6 | Auth (JWT, RBAC) + studies/series/instances cache tables in Postgres | planned | — | First time we duplicate metadata into Postgres |
| 7 | Prometheus + Grafana + structured logging with request IDs | planned | — | |
| 8 | Cornerstone3D viewer upgrade (window/level, multi-frame, measurements) | planned | — | |
| 9 | Background job queue (Redis + Celery or RQ); async reconstruction with retries | planned | — | |
| 9.5 | Advanced reconstruction: undersampling sim + compressed sensing + optional U-Net | planned | — | Split from old "advanced" bucket; slice 9 focuses on queue, 9.5 owns algorithm depth |
| 10+ | Kubernetes manifests; real cloud (S3/GCS); CI/CD deploy pipeline | planned | — | |

**Status legend:** `planned` · `in-progress` · `done` · `deferred` · `cancelled`

## Locked decisions that span all slices

These were settled during slice 1 brainstorming and apply to all subsequent slices unless explicitly revisited in a later spec.

| ID | Decision |
|---|---|
| AD-1 | Postgres holds only app-owned data; Orthanc is source of truth for studies/series/instances until slice 6 |
| AD-2 | Orthanc's built-in `/preview` is used for PNG previews until a richer viewer is needed |
| AD-3 | React never talks to Orthanc directly — always via api-service |
| AD-4 | Uploads are synchronous until slice 9 introduces a job queue |
| AD-5 | Sample data: synthetic pydicom fixtures (CI) + small real TCIA series (demo); no git-lfs |
| AD-6 | Python tooling: `uv` + `pyproject.toml` |
| AD-7 | JS tooling: `npm` + Vite, no monorepo workspaces |
| AD-8 | Alembic migrations from day 1 |
| AD-9 | Integration tests via `testcontainers`, not a separate compose file |

If a future slice needs to revisit one of these, the slice spec must explicitly call it out.

## How to add a slice

1. Brainstorm with the user, capture decisions.
2. Write `docs/superpowers/specs/YYYY-MM-DD-slice-N-<topic>-design.md`.
3. Update this roadmap row's `status` and link the spec.
4. Update [`status.md`](./status.md) to point at the new active slice.
5. Move to writing the implementation plan.
