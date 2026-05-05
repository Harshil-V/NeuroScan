# NeuroScan Workstation — Project Overview

**Status:** Active
**Last updated:** 2026-05-05

## What is this?

NeuroScan Workstation is a local-first medical imaging engineering platform that simulates an end-to-end MRI software workflow:

```text
MRI signal / k-space input
        ↓
Python reconstruction service
        ↓
DICOM generation / ingestion
        ↓
Local DICOM archive (Orthanc)
        ↓
Qt desktop viewer  +  React web viewer
        ↓
Object storage (MinIO), audit logs, QA automation
```

It is a **portfolio engineering project**, not a clinical product. It uses only synthetic or de-identified public imaging data (TCIA, fastMRI). It explicitly does not claim HIPAA compliance, FDA validation, or clinical fitness for use.

## Why does it exist?

To demonstrate, in a single coherent codebase, the skill set needed for medical-imaging-adjacent software roles:

- Qt/Python desktop UI for medical image viewing
- DICOM workflow handling (pydicom, DICOMweb, Orthanc)
- MRI signal/image processing (FFT-based reconstruction over k-space)
- Cloud-style transmission of sensitive imaging data (signed URLs, checksums, audit, de-id checks) — simulated locally with MinIO
- React/TypeScript web frontend for medical imaging review
- FastAPI backend services with tests, observability, CI/CD
- Containerized local deployment with Docker Compose; eventual K8s/cloud path

The goal is one strong flagship project, not five small ones.

## Target outcome

A demoable, fully-local platform where a user can:

1. Drop a DICOM file in a web UI → it's stored, audited, viewable.
2. Open the same DICOM in a Qt desktop viewer with slice nav, window/level, metadata.
3. Upload sample k-space data → an MRI image is reconstructed via inverse FFT, written back as DICOM, and viewable in the same web/desktop tools.
4. Run the entire stack with `docker compose up -d`.
5. Show audit logs, checksums, and storage events that mirror a real clinical-data movement workflow.

## High-level architecture (full platform vision)

This is the eventual shape; we build it in slices.

```text
                ┌─────────────────────────┐
                │   Qt Desktop Viewer     │
                │   PySide6 / pydicom     │
                └───────────┬─────────────┘
                            │ Upload / View
                            ▼
┌─────────────────────────────────────────────────┐
│                 FastAPI api-service             │
│  Auth · Uploads · Studies · Audit · Recon API   │
└──┬──────────────┬───────────────┬───────────────┘
   │              │               │
   ▼              ▼               ▼
┌────────┐   ┌──────────────┐   ┌───────────────────┐
│Orthanc │   │ PostgreSQL   │   │ Reconstruction    │
│DICOM   │   │ metadata +   │   │ service (FastAPI, │
│archive │   │ audit + jobs │   │ NumPy, SciPy)     │
└───┬────┘   └──────────────┘   └─────────┬─────────┘
    │                                     │
    ▼                                     ▼
┌───────────────────┐              ┌───────────────┐
│ React Web Viewer  │              │ Generated     │
│ Studies, Upload,  │              │ DICOM →       │
│ Audit, Recon UI   │              │ Orthanc       │
└───────────────────┘              └───────────────┘

         ┌─────────────────┐    ┌────────────────┐
         │ MinIO (S3 sim)  │    │ Prometheus +   │
         │ + signed URLs   │    │ Grafana        │
         └─────────────────┘    └────────────────┘
```

## Tech stack (full platform)

| Layer | Tech |
|---|---|
| Desktop | Python, PySide6, pydicom, NumPy, OpenCV, pyqtgraph |
| Backend | Python, FastAPI, SQLAlchemy, Alembic, Pydantic, httpx |
| Reconstruction | Python, NumPy, SciPy, h5py, pydicom |
| Web | React 18, TypeScript, Vite, react-router, TanStack Query, CSS Modules |
| DICOM | Orthanc, pydicom, DICOMweb |
| Storage | PostgreSQL, MinIO (local S3), Redis (later phases) |
| Infra | Docker Compose; K8s in late phases |
| Observability | Prometheus, Grafana (later phases) |
| Test | pytest, pytest-asyncio, respx, testcontainers, Playwright |
| Tooling | uv (Python), npm + Vite (JS), GitHub Actions |
| Sample data | Synthetic pydicom fixtures + TCIA public series + fastMRI samples |

## What this is NOT

- Not a real PACS replacement
- Not HIPAA-certified or FDA-validated
- Not connected to real MRI hardware
- Not multi-tenant
- Not deployed to production

## How the work is organized

We slice the work into independently-shippable phases. Each slice gets its own brainstorming → spec → plan → implementation cycle. See [`roadmap.md`](./roadmap.md) for the slice list and status, and [`status.md`](./status.md) for the current state.

The original brief is preserved verbatim in [`prd/2026-05-05-original-prd.md`](./prd/2026-05-05-original-prd.md) as a historical anchor.

## Key references

- [Roadmap](./roadmap.md) — slice list + status
- [Status](./status.md) — current state, what's next
- [Original PRD](./prd/2026-05-05-original-prd.md) — frozen original brief
- [Slice specs](./superpowers/specs/) — one design doc per slice
