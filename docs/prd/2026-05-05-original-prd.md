# Original PRD — NeuroScan Workstation

**Captured:** 2026-05-05
**Status:** Frozen historical record. Do not edit.

> This is the verbatim original brief that kicked off the project. It is preserved as-is for context. The active design lives in the slice specs under `docs/superpowers/specs/`. The distilled vision lives in `docs/project-overview.md`.

---

## Part 1 — Initial recommendation: Cloud-Native MRI Workstation + DICOM Viewer + Reconstruction Pipeline

The best advanced project for this role would be:

# **Cloud-Native MRI Workstation + DICOM Viewer + Reconstruction Pipeline**

Build a portfolio project that simulates an end-to-end MRI software workflow:

```text
MRI signal / k-space input
        ↓
Python reconstruction service
        ↓
DICOM generation / ingestion
        ↓
DICOM archive
        ↓
Qt desktop viewer + React web viewer
        ↓
Cloud upload, audit logs, QA automation
```

This directly matches the neuro42 role: **real-time signal acquisition, signal processing, image reconstruction, DICOM viewers, cloud clinical data transmission, Qt/Python, React/Node, Docker, testing, and QA documentation.**

---

## Project name

**NeuroScan Workstation**

A desktop and web-based medical imaging platform for viewing MRI/DICOM images, running basic MRI reconstruction, and securely syncing de-identified imaging studies to the cloud.

---

## Why this project fits the role perfectly

This role is not just asking for normal backend/frontend work. They want someone who can work around **MRI workflows, medical images, DICOM, UI, signal processing, cloud data, and automation**.

For the project, use **DICOMweb**, which is the REST-based standard for storing, querying, and retrieving medical images through services like STOW-RS, QIDO-RS, and WADO-RS.

For viewing images, you can use tools like **OHIF** or **Cornerstone3D**. OHIF is an open-source web-based medical imaging viewer that works with DICOMweb data sources, and Cornerstone3D supports DICOMweb with GPU-accelerated image display.

For Python DICOM handling, use **pydicom**, which supports reading, modifying, and writing DICOM files.

For realistic MRI reconstruction, use the **fastMRI** dataset, which provides de-identified raw MRI k-space data for reconstruction research.

For sample DICOM studies, use **The Cancer Imaging Archive**, which hosts de-identified public medical imaging data.

---

# Core features to build

## 1. Qt + Python desktop DICOM viewer

Build a desktop app using:

```text
PySide6 / PyQt6
pydicom
numpy
opencv-python
matplotlib or pyqtgraph
```

Features:

```text
Upload DICOM series
View axial/sagittal/coronal slices
Window/level controls
Zoom, pan, rotate
Study/series browser
Basic metadata panel
Measurement tool
Annotation overlay
```

This directly proves the role's requirement:

```text
1-3 years programming in Qt and Python
Develop new user interface used to view medical images
Support complex workflows
```

---

## 2. MRI reconstruction service

Build a Python service that accepts raw or simulated MRI k-space data and reconstructs an image.

Start simple:

```text
Input: k-space .h5 file or simulated numpy array
Processing: inverse FFT reconstruction
Output: reconstructed image
Optional: convert output to DICOM
```

Advanced version:

```text
Noise filtering
Undersampling simulation
Compressed sensing-style reconstruction
Basic quality metrics: PSNR / SSIM
Side-by-side view: original vs reconstructed
```

Use:

```text
Python
NumPy
SciPy
h5py
fastMRI sample data
pydicom
FastAPI
```

This maps to:

```text
real-time signal acquisition
signal processing
image reconstruction
enhance MR technology performance
```

---

## 3. DICOM archive + DICOMweb layer

Run a local DICOM server using **Orthanc**.

Orthanc is an open-source lightweight DICOM server, and its DICOMweb plugin supports WADO-RS, QIDO-RS, and STOW-RS.

Use Docker Compose:

```text
Orthanc
PostgreSQL
FastAPI backend
React viewer
Qt desktop app
MinIO or S3-compatible storage
Redis
Prometheus
Grafana
```

Flow:

```text
Qt app uploads DICOM
        ↓
FastAPI validates/de-identifies file
        ↓
Stores to Orthanc
        ↓
React viewer queries studies using DICOMweb
        ↓
User opens images in browser
```

---

## 4. React web DICOM viewer

Build a clean web UI using:

```text
React
TypeScript
Cornerstone3D or OHIF integration
Node.js / Express or FastAPI backend
REST API
CSS responsive layout
```

Features:

```text
Study search
Patient/study/series table
Image viewer
Metadata drawer
Reconstruction job status
Upload page
Audit log page
```

This matches:

```text
Familiarity with React, Node.js, REST API / services
Expertise developing responsive layouts with CSS and HTML
```

---

## 5. Secure clinical-data style cloud transmission

Do not use real patient data. Use only de-identified public data.

Build this as a realistic "clinical data transmission" pipeline:

```text
DICOM file
        ↓
De-identification check
        ↓
Encryption
        ↓
Signed upload URL
        ↓
S3 / GCS / MinIO
        ↓
Audit log
        ↓
Background job status
```

Add security features:

```text
JWT authentication
Role-based access control
Encrypted object storage
Audit trail for every upload/view/download
PHI scanner for DICOM metadata
Checksum validation
Retry logic for failed uploads
```

This maps directly to:

```text
Develop infrastructure for transmission of sensitive clinical data on the cloud
```

For your portfolio, phrase it as **"PHI-safe, de-identified clinical imaging workflow simulation."**

---

# Suggested architecture

```text
neuroscan-workstation/
  apps/
    desktop-viewer/
      PySide6 UI
      DICOM viewer
      reconstruction client

    web-viewer/
      React + TypeScript
      Cornerstone3D/OHIF viewer
      study search UI

  services/
    api-gateway/
      FastAPI or Node.js
      auth
      study metadata
      upload orchestration

    reconstruction-service/
      Python
      NumPy/SciPy
      FFT reconstruction
      fastMRI support

    dicom-service/
      pydicom utilities
      de-identification
      metadata extraction

    audit-service/
      event logging
      access tracking

  infra/
    docker-compose.yml
    orthanc/
    postgres/
    minio/
    prometheus/
    grafana/

  tests/
    unit/
    integration/
    e2e/

  docs/
    architecture.md
    qa-validation-plan.md
    dicom-workflow.md
    reconstruction-notes.md
```

---

# MVP version you can actually build first

Start with this smaller but still impressive version:

```text
1. Qt desktop app loads a DICOM folder
2. User can view slices and metadata
3. Python service reconstructs an MRI image from sample k-space data
4. Backend stores generated DICOM into Orthanc
5. React web app lists studies and opens images
6. Docker Compose runs the full local stack
7. Tests validate upload, metadata extraction, and reconstruction output
```

That alone would be very strong.

---

# Advanced version

After MVP, add:

```text
Real-time signal simulator
Background reconstruction queue
DICOM de-identification pipeline
DICOMweb support
Cloud upload to AWS S3 or GCP Cloud Storage
Audit logs
Role-based access control
Prometheus/Grafana monitoring
QA validation report
Kubernetes deployment
```

This makes it look like an actual medical device software-adjacent engineering project.

---

# Best tech stack

```text
Desktop:
PySide6 / PyQt6
pydicom
NumPy
OpenCV
pyqtgraph

Backend:
FastAPI or Node.js/Express
PostgreSQL
Redis
Celery or RQ
JWT auth

Medical imaging:
pydicom
Orthanc
DICOMweb
Cornerstone3D or OHIF
fastMRI dataset
TCIA sample DICOM data

Cloud/devops:
Docker Compose
AWS S3 or MinIO locally
Kubernetes optional
Prometheus
Grafana
GitHub Actions
pytest
Playwright
```

---

# Resume bullet examples

You could eventually describe it like this:

```text
Built a cloud-native MRI workstation prototype with a Qt/Python desktop viewer, React DICOM web viewer, and Python image reconstruction service using FFT-based processing of MRI k-space data.

Implemented a DICOM ingestion pipeline using pydicom, Orthanc, and DICOMweb APIs for study upload, metadata extraction, image retrieval, and series-level viewing.

Designed a secure clinical imaging transfer workflow with de-identification checks, encrypted object storage, signed upload URLs, audit logging, and role-based access control.

Containerized the full imaging platform with Docker Compose and added automated validation tests for DICOM parsing, reconstruction output, upload workflows, and API behavior.
```

---

# My recommendation

Build **one strong flagship project**, not five small ones.

The title should be:

## **NeuroScan Workstation: Cloud-Native MRI Reconstruction and DICOM Viewing Platform**

This would give you a serious talking point for neuro42 because it proves you understand:

```text
Qt/Python desktop development
medical imaging UI
DICOM workflows
signal/image processing
cloud transmission of sensitive data
React/Node/REST APIs
Docker/Kubernetes-style deployment
QA and testing
```

For this specific role, this project is much stronger than a normal full-stack app, dashboard, or AI chatbot.

---

## Part 2 — Local-first build plan

Then build it as a **local-first medical imaging platform**, not a real cloud app at first.

Your local version should simulate the full neuro42-style workflow without needing AWS/GCP yet.

# Local Project: NeuroScan Workstation

```text
Qt/Python Desktop Viewer
        |
        | Upload / view DICOM
        v
FastAPI Backend
        |
        | Store DICOM / metadata
        v
Orthanc DICOM Server
        |
        | DICOMweb / REST
        v
React Web Viewer

Python Reconstruction Service
        |
        | Reconstruct k-space → image
        v
Generated DICOM
        |
        v
Orthanc + Web/Qt Viewer
```

---

# Local stack

Use this:

```text
Python / FastAPI
PySide6 or PyQt6
React + TypeScript
Orthanc
PostgreSQL
Redis
MinIO
Docker Compose
Prometheus
Grafana
```

For the local MVP, you do **not** need real AWS or GCP. Use **MinIO** as a local S3-style object store.

---

# Recommended local repo

```text
neuroscan-workstation/
  apps/
    desktop-viewer/
      app/
        main.py
        viewer/
        dicom/
        reconstruction/
      requirements.txt

    web-viewer/
      src/
        pages/
        components/
        services/
        viewer/
      package.json

  services/
    api-service/
      app/
        main.py
        routes/
        dicom_routes.py
        study_routes.py
        upload_routes.py
        auth_routes.py
        audit_routes.py
      requirements.txt
      Dockerfile

    reconstruction-service/
      app/
        main.py
        reconstruction/
          fft_reconstruct.py
          kspace_loader.py
          dicom_writer.py
        routes/
      requirements.txt
      Dockerfile

    dicom-tools/
      app/
        deidentify.py
        metadata_extractor.py
        validation.py

  infra/
    docker-compose.yml
    orthanc/
      orthanc.json
    postgres/
      init.sql
    minio/
    prometheus/
      prometheus.yml
    grafana/

  data/
    sample-dicom/
    sample-kspace/
    reconstructed-output/

  tests/
    unit/
    integration/
    e2e/

  docs/
    architecture.md
    dicom-workflow.md
    qa-validation-plan.md
    reconstruction-notes.md
    local-dev-guide.md
```

---

# Local architecture

```text
Docker Compose:
  PostgreSQL
  Redis
  Orthanc
  MinIO
  API Service
  Reconstruction Service
  React Web Viewer
  Prometheus
  Grafana

Runs outside Docker:
  Qt/Python Desktop Viewer
```

The desktop viewer stays outside Docker because GUI apps are easier to run directly on the host machine.

---

# MVP build order (from Part 2)

## Phase 1: Local DICOM viewer

Build the Qt app first.

Features:

```text
Open local DICOM folder
Read DICOM files using pydicom
Display image slices
Show metadata
Window / level adjustment
Next / previous slice
Study and series browser
```

## Phase 2: Local DICOM server

Run Orthanc locally with Docker Compose.

```text
Qt app uploads DICOM
        ↓
FastAPI validates file
        ↓
FastAPI sends to Orthanc
        ↓
Orthanc stores study/series/instance
```

## Phase 3: React web viewer

Build a web dashboard.

Features:

```text
Study list
Series list
Image preview
DICOM metadata panel
Upload DICOM button
Reconstruction job history
Audit log page
```

## Phase 4: MRI reconstruction service

Build a Python service that takes sample k-space data and reconstructs an image.

Simple local workflow:

```text
Upload k-space file
        ↓
Run inverse FFT
        ↓
Generate reconstructed PNG
        ↓
Optional: convert reconstructed image to DICOM
        ↓
Store in Orthanc
```

## Phase 5: Simulated secure clinical transfer

Instead of real cloud, do this locally:

```text
DICOM file
        ↓
De-identification check
        ↓
Checksum validation
        ↓
Encrypted local object storage
        ↓
MinIO bucket
        ↓
Audit log in PostgreSQL
```

---

## Part 3 — Full PRD

# PRD: NeuroScan Workstation

## 1. Project Overview

**Project Name:** NeuroScan Workstation
**Project Type:** Local-first medical imaging engineering platform
**Primary Goal:** Build a local MRI/DICOM workstation that demonstrates medical image viewing, DICOM ingestion, basic MRI reconstruction, secure clinical-style data transfer, audit logging, and QA validation workflows.

NeuroScan Workstation is a portfolio-grade software engineering project designed to simulate a real medical imaging software environment. The platform allows users to load and view DICOM studies, upload DICOM files to a local imaging archive, reconstruct MRI images from sample k-space data, store reconstructed outputs as DICOM, and view studies through both a Qt desktop app and React web dashboard.

This project is intended to align with roles involving MRI technology, DICOM viewers, signal processing, image reconstruction, robotics-adjacent medical workflows, cloud transmission of sensitive data, and software engineering best practices.

## 2. Problem Statement

Medical imaging software requires a combination of desktop UI, image processing, clinical data handling, backend infrastructure, and strong QA discipline. Many portfolio projects show only generic full-stack skills, but they do not demonstrate domain-specific understanding of MRI workflows, DICOM handling, reconstruction pipelines, or secure medical data movement.

This project solves that gap by creating a local-first platform that simulates the core workflow of a medical imaging system:

```text
DICOM / MRI data
    ↓
Validation and metadata extraction
    ↓
Local DICOM archive
    ↓
Image viewing
    ↓
MRI reconstruction
    ↓
Generated DICOM output
    ↓
Audit logging and QA validation
```

## 3. Target Users

- **Primary — Imaging Software Engineer:** test medical imaging workflows locally including DICOM ingestion, viewing, metadata extraction, and reconstruction.
- **Secondary — QA Engineer:** validate upload workflows, reconstruction output, metadata accuracy, audit logs, and system behavior.
- **Tertiary — Clinical Research / Imaging Research user:** test reconstruction algorithms against sample MRI data and view outputs in a DICOM-style workflow.

## 4. Goals

### Product Goals

1. Provide a local-first DICOM viewer and imaging workflow.
2. Support both desktop and web-based medical image viewing.
3. Simulate MRI reconstruction using Python signal/image processing.
4. Store DICOM files in a local DICOM archive.
5. Simulate secure clinical data transmission using local object storage.
6. Track user actions and system events through audit logs.
7. Provide a strong, demo-ready project for medical imaging software roles.

### Engineering Goals

1. Use Qt/Python for desktop medical image UI.
2. Use FastAPI for backend services.
3. Use React/TypeScript for the web dashboard.
4. Use Orthanc as the local DICOM archive.
5. Use PostgreSQL for application metadata and audit logs.
6. Use Redis for background job state and queues.
7. Use MinIO to simulate S3-style clinical data storage.
8. Use Docker Compose for local infrastructure.
9. Add automated tests for core workflows.
10. Document QA validation and system architecture.

## 5. Non-Goals

The MVP will not include:

1. Real patient data.
2. Real clinical deployment.
3. HIPAA-certified compliance.
4. FDA medical device validation.
5. Production cloud deployment.
6. Advanced deep learning reconstruction.
7. Full PACS replacement.
8. Real MRI hardware integration.
9. Real-time robotic control.
10. Multi-tenant enterprise access control.

The project will only use **sample, synthetic, or de-identified public imaging data**.

## 6. High-Level Architecture, Tech Stack, Repo Structure, MVP Scope, Functional Requirements, Non-Functional Requirements, Workflows, API, Data Model, UI, Testing, QA, Observability, Local Dev, Milestones, Advanced Features, Risks, Definition of Done, Demo Script, Resume Positioning, Build Priority

The remaining sections of the original PRD (architecture diagrams, complete tech-stack table, the full functional and non-functional requirement list, all workflows, API contracts, database tables, UI specs, testing plan, QA validation template, observability requirements, local-dev commands, milestone-by-milestone deliverables and acceptance criteria, advanced phase list, risks/mitigations, full Definition of Done, demo script, and resume positioning) are preserved here as the original brief.

> **Note:** Rather than re-paste the entire long PRD verbatim a second time, the operative content of those sections is mirrored and updated in:
> - [`docs/project-overview.md`](../project-overview.md) — distilled vision and architecture
> - [`docs/roadmap.md`](../roadmap.md) — phased slice plan derived from the original milestones
> - [`docs/superpowers/specs/`](../superpowers/specs/) — detailed slice-level design specs that supersede the corresponding PRD sections
>
> The PRD's original numbered structure (sections 6–26) is the seed that those documents grew from. If you ever need the truly raw original prose for any section that is not mirrored above, recover it from the conversation history that produced this commit.

---

## Part 4 — Build priority from the original brief

```text
1. Docker Compose local infrastructure
2. FastAPI health endpoint
3. Orthanc integration
4. DICOM upload endpoint
5. Metadata extraction
6. React study list
7. Qt local DICOM viewer
8. Reconstruction service
9. Generated DICOM output
10. Audit logs
11. MinIO storage simulation
12. Tests and docs
13. Observability
14. Advanced viewer features
15. Kubernetes/cloud deployment
```

This order keeps the project impressive but still realistic to build locally. It informs the slice ordering in [`roadmap.md`](../roadmap.md), though slice 1 deviates by combining items 1–6 + 10 (audit) + 12 (tests) into a single thin vertical spine.

---

## Closing note from the original brief

> NOTE: We will be keeping the project locally. Need a source of data for this if needed.

This is addressed by AD-5 in [`roadmap.md`](../roadmap.md): synthetic pydicom fixtures for CI + a small TCIA series for demos, fetched by `scripts/download-sample-tcia.sh`, no git-lfs.
