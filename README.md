# NeuroScan Workstation

Local-first MRI / DICOM viewing, reconstruction, and clinical-data-transfer simulation platform. Built with Qt, Python, FastAPI, React, Orthanc, and Docker.

> Portfolio engineering project. Uses only synthetic or de-identified public imaging data. Not a clinical product. Not HIPAA-certified. Not FDA-validated.

**What this project demonstrates:**

- DICOM upload, validation, and Orthanc archival with audit logging.
- Qt desktop viewer (PySide6 + pyqtgraph) for multi-slice DICOM series.
- **MRI reconstruction**: inverse FFT pipeline with PSNR/SSIM quality metrics, queued via FastAPI BackgroundTasks, output stored as DICOM in Orthanc.
- **Object storage with signed URLs**: MinIO sidecar persists every DICOM under a content-addressed S3 path; presigned-URL endpoint mints short-TTL share links.
- **PHI detection**: every DICOM upload is scanned against the DICOM PS3.15 Basic Confidentiality Profile; identifying tags are surfaced in the UI with severity classification (high/medium), values recorded only as salted SHA-256 hashes.

## Status

See **[`docs/status.md`](docs/status.md)** for the current state.

Active slice: **Slice 5 — De-identification Scanner** (implementation complete on branch).

## Documentation

Start with **[`docs/README.md`](docs/README.md)** for the docs index.

Quick links:

- [Project overview](docs/project-overview.md) — what and why
- [Roadmap](docs/roadmap.md) — phased slice plan
- [Status](docs/status.md) — current state
- [Slice specs](docs/superpowers/specs/) — design docs per slice
- [Original PRD](docs/prd/2026-05-05-original-prd.md) — frozen historical brief
- [`AGENTS.md`](AGENTS.md) — guidance for AI agents working on this repo

## Quickstart

**Prereqs:** Docker (Docker Desktop, OrbStack, or Colima), Python 3.12+, [`uv`](https://docs.astral.sh/uv/), Node 20+.

```bash
git clone <repo> && cd NeuroScan
cp .env.example .env

# Bring up the local stack (postgres + orthanc + api-service + web-viewer)
docker compose -f infra/docker-compose.yml up -d --build

# Visit
#   http://localhost:5173        web viewer
#   http://localhost:8000/docs   API docs
#   http://localhost:8042        Orthanc UI (orthanc/orthanc)
#   http://localhost:9001        MinIO console (minioadmin/minioadmin)

# Generate a synthetic DICOM and upload it via the UI
uv run --directory services/api-service python ../../scripts/generate-synthetic-dicom.py /tmp/x.dcm

# Generate a synthetic k-space file (for the /reconstruction page)
mkdir -p data/sample-dicom/synthetic-kspace
uv run --directory services/api-service python ../../scripts/generate-synthetic-kspace.py \
    "$PWD/data/sample-dicom/real-multislice/slice_010.dcm" \
    "$PWD/data/sample-dicom/synthetic-kspace/brain.npz"
```

### macOS + OrbStack note

OrbStack does not bind `/var/run/docker.sock` by default. For testcontainers (Python integration tests) and direct docker-py usage, set:

```bash
export PATH="$HOME/.orbstack/bin:$PATH"
export DOCKER_HOST="unix://$HOME/.orbstack/run/docker.sock"
```

The `docker compose` CLI itself works without `DOCKER_HOST` once `~/.orbstack/bin` is on PATH.

### Tests

```bash
# api-service: unit + integration (testcontainers spins postgres + orthanc)
cd services/api-service && uv run pytest

# web-viewer: typecheck + production build
cd apps/web-viewer && npm run typecheck && npm run build

# Playwright E2E (stack must be up)
cd tests/e2e && npm test
```

For the manual QA checklist, see [`docs/qa-validation-plan.md`](docs/qa-validation-plan.md).

## License

See [LICENSE](LICENSE).
