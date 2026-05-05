# Slice 1 — Vertical Spine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the thinnest end-to-end vertical slice of NeuroScan Workstation: drag a DICOM into a React app → validated, checksummed, audited, stored in Orthanc → list/detail/preview through a FastAPI proxy → audit log visible in UI. All run via `docker compose up -d`. CI green.

**Architecture:** React (Vite + TS) → FastAPI (`api-service`, uv + pyproject) → Orthanc (DICOM archive) + PostgreSQL (audit only). React never talks to Orthanc directly. Postgres holds *only* `audit_events` in this slice; Orthanc is source of truth for studies/series/instances. Orthanc's built-in `/preview` endpoint provides PNG previews (proxied). Uploads are synchronous (no queue).

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2, Alembic, pydicom, httpx, respx, pytest, testcontainers, uv. React 18, TypeScript, Vite, react-router 6, TanStack Query, CSS Modules, npm. Orthanc, PostgreSQL 16, Docker Compose v2. Playwright. GitHub Actions.

**Spec:** [`docs/superpowers/specs/2026-05-05-slice-1-vertical-spine-design.md`](../specs/2026-05-05-slice-1-vertical-spine-design.md)

**Branch:** `slice-1-vertical-spine`

**Commit policy (from user):** Small, incremental, logically-isolated commits. Each task in this plan produces 1–3 commits. Never combine unrelated changes.

---

## File structure (everything created in this slice)

```text
.gitignore                                              # repo-wide ignores
.env.example                                            # documented env vars
README.md                                               # MODIFY: add quickstart + status link
AGENTS.md                                               # already exists, no change
docs/
  qa-validation-plan.md                                 # manual QA checklist
  status.md                                             # MODIFY at end of slice
  roadmap.md                                            # MODIFY at end of slice
infra/
  docker-compose.yml                                    # postgres, orthanc, api-service, web-viewer
  orthanc/orthanc.json                                  # Orthanc config (DICOMweb plugin on, creds via env)
services/api-service/
  pyproject.toml                                        # uv-managed
  uv.lock                                               # generated
  Dockerfile                                            # multi-stage with uv
  alembic.ini
  app/
    __init__.py
    main.py                                             # FastAPI app + router includes
    config.py                                           # pydantic-settings
    db.py                                               # SQLAlchemy engine + session
    routes/{__init__,health,dicom,studies,audit}.py
    clients/{__init__,orthanc}.py                       # httpx-based Orthanc client
    services/{__init__,upload,audit,dicom_validation,metadata,checksum}.py
    models/{__init__,audit}.py                          # SQLAlchemy AuditEvent
    schemas/{__init__,audit,study,upload}.py            # pydantic DTOs
    alembic/{env.py,script.py.mako,versions/001_audit_events.py}
  tests/
    __init__.py
    conftest.py                                         # testcontainers + httpx async client
    fixtures/{__init__,synthetic_dicom}.py              # pydicom synthetic generator
    unit/test_{dicom_validation,metadata,checksum,orthanc_client,upload_service,audit_service}.py
    integration/test_{health,upload_flow,studies_flow,audit_flow,preview_flow}.py
apps/web-viewer/
  package.json
  package-lock.json                                     # generated
  tsconfig.json, tsconfig.node.json
  vite.config.ts
  index.html
  Dockerfile                                            # nginx-served prod build
  nginx.conf
  src/
    main.tsx, App.tsx, routes.tsx
    pages/{StudyListPage,StudyDetailPage,UploadPage,AuditPage}.tsx
    components/{Nav,StudyTable,UploadDropzone,AuditTable,PreviewImage}.tsx
    api/{client,studies,dicom,audit}.ts
    types/index.ts
    styles/*.module.css                                 # one per page/component
tests/e2e/
  package.json
  playwright.config.ts
  upload-flow.spec.ts
scripts/
  generate-synthetic-dicom.py                           # standalone CLI wrapper around the test fixture
  download-sample-tcia.sh
.github/workflows/ci.yml                                # python, web, e2e jobs
```

---

## Phase A — Repo skeleton & tooling

### Task A1: Add `.gitignore` and `.env.example`

**Files:**
- Create: `.gitignore`
- Create: `.env.example`

- [ ] **Step 1: Write `.gitignore`**

```gitignore
# Python
__pycache__/
*.py[cod]
*.egg-info/
.venv/
.python-version
.pytest_cache/
.ruff_cache/
.coverage
htmlcov/

# Node
node_modules/
dist/
.vite/
playwright-report/
test-results/

# Env / secrets
.env
.env.local
*.local

# Editor / OS
.vscode/
.idea/
.DS_Store
Thumbs.db

# Sample data (large, regenerable, or fetched on demand)
data/sample-dicom/synthetic/
data/sample-dicom/tcia-brain-mr/

# Docker volumes when bind-mounted to local dirs
infra/.volumes/
```

- [ ] **Step 2: Write `.env.example`**

```env
# api-service
API_PORT=8000
DATABASE_URL=postgresql+psycopg://neuroscan:neuroscan@postgres:5432/neuroscan
ORTHANC_URL=http://orthanc:8042
ORTHANC_USER=orthanc
ORTHANC_PASSWORD=orthanc
LOG_LEVEL=INFO

# postgres
POSTGRES_USER=neuroscan
POSTGRES_PASSWORD=neuroscan
POSTGRES_DB=neuroscan

# orthanc
ORTHANC_REGISTERED_USERS={"orthanc":"orthanc"}

# web-viewer (build-time)
VITE_API_BASE_URL=http://localhost:8000
```

- [ ] **Step 3: Commit**

```bash
git add .gitignore .env.example
git commit -m "chore(slice-1): add .gitignore and .env.example"
```

---

## Phase B — Infrastructure (Docker Compose)

### Task B1: Orthanc config

**Files:**
- Create: `infra/orthanc/orthanc.json`

- [ ] **Step 1: Write Orthanc config**

```json
{
  "Name": "NeuroScan Orthanc",
  "HttpPort": 8042,
  "DicomPort": 4242,
  "RemoteAccessAllowed": true,
  "AuthenticationEnabled": true,
  "RegisteredUsers": { "orthanc": "orthanc" },
  "DicomWeb": {
    "Enable": true,
    "Root": "/dicom-web/"
  },
  "PostgreSQL": {
    "EnableIndex": false,
    "EnableStorage": false
  },
  "StorageDirectory": "/var/lib/orthanc/db",
  "IndexDirectory": "/var/lib/orthanc/db",
  "ConcurrentJobs": 2
}
```

- [ ] **Step 2: Commit**

```bash
git add infra/orthanc/orthanc.json
git commit -m "feat(slice-1): add Orthanc config with DICOMweb enabled"
```

### Task B2: Docker Compose with Postgres + Orthanc only (api-service and web-viewer added later)

**Files:**
- Create: `infra/docker-compose.yml`

- [ ] **Step 1: Write compose file**

```yaml
name: neuroscan

services:
  postgres:
    image: postgres:16
    restart: unless-stopped
    environment:
      POSTGRES_USER: ${POSTGRES_USER:-neuroscan}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-neuroscan}
      POSTGRES_DB: ${POSTGRES_DB:-neuroscan}
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER:-neuroscan}"]
      interval: 5s
      timeout: 3s
      retries: 10

  orthanc:
    image: orthancteam/orthanc:24.7.3
    restart: unless-stopped
    ports:
      - "8042:8042"
      - "4242:4242"
    volumes:
      - ./orthanc/orthanc.json:/etc/orthanc/orthanc.json:ro
      - orthanc_data:/var/lib/orthanc/db
    healthcheck:
      test: ["CMD-SHELL", "wget -q -O- --user=orthanc --password=orthanc http://localhost:8042/system >/dev/null || exit 1"]
      interval: 10s
      timeout: 5s
      retries: 10

volumes:
  postgres_data:
  orthanc_data:
```

- [ ] **Step 2: Verify it boots**

Run:
```bash
cd infra && docker compose up -d && docker compose ps
```

Expected: both services show `healthy` within 60s. Test Orthanc:
```bash
curl -u orthanc:orthanc http://localhost:8042/system | head -c 200
```
Expected: JSON containing `"Name":"NeuroScan Orthanc"`.

Tear down:
```bash
docker compose down
```

- [ ] **Step 3: Commit**

```bash
git add infra/docker-compose.yml
git commit -m "feat(slice-1): add docker-compose with postgres + orthanc"
```

---

## Phase C — `api-service` skeleton

### Task C1: `pyproject.toml` with all deps

**Files:**
- Create: `services/api-service/pyproject.toml`

- [ ] **Step 1: Write pyproject**

```toml
[project]
name = "neuroscan-api-service"
version = "0.1.0"
description = "NeuroScan Workstation API service"
requires-python = ">=3.12"
dependencies = [
    "fastapi>=0.115",
    "uvicorn[standard]>=0.32",
    "pydantic>=2.9",
    "pydantic-settings>=2.6",
    "sqlalchemy>=2.0",
    "alembic>=1.13",
    "psycopg[binary]>=3.2",
    "httpx>=0.27",
    "pydicom>=3.0",
    "python-multipart>=0.0.12",
]

[dependency-groups]
dev = [
    "pytest>=8.3",
    "pytest-asyncio>=0.24",
    "pytest-cov>=5.0",
    "respx>=0.21",
    "testcontainers[postgres]>=4.8",
    "ruff>=0.7",
    "numpy>=2.1",
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
```

- [ ] **Step 2: Lock + verify**

Run:
```bash
cd services/api-service
uv sync
```
Expected: `uv.lock` created, `.venv/` populated, no errors.

- [ ] **Step 3: Commit (lockfile included)**

```bash
git add services/api-service/pyproject.toml services/api-service/uv.lock
git commit -m "feat(slice-1): add api-service pyproject with deps"
```

### Task C2: FastAPI skeleton + config + health endpoint

**Files:**
- Create: `services/api-service/app/__init__.py`
- Create: `services/api-service/app/config.py`
- Create: `services/api-service/app/main.py`
- Create: `services/api-service/app/routes/__init__.py`
- Create: `services/api-service/app/routes/health.py`

- [ ] **Step 1: Write `app/__init__.py`**

```python
__version__ = "0.1.0"
```

- [ ] **Step 2: Write `app/config.py`**

```python
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    api_port: int = 8000
    database_url: str = Field(
        default="postgresql+psycopg://neuroscan:neuroscan@localhost:5432/neuroscan",
    )
    orthanc_url: str = "http://localhost:8042"
    orthanc_user: str = "orthanc"
    orthanc_password: str = "orthanc"
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

- [ ] **Step 3: Write `app/routes/__init__.py`**

```python
```

(Empty file. Just makes it a package.)

- [ ] **Step 4: Write `app/routes/health.py` (skeleton, no DB/Orthanc checks yet)**

```python
from fastapi import APIRouter

from app import __version__

router = APIRouter()


@router.get("/health")
async def health() -> dict:
    return {
        "status": "ok",
        "service": "api-service",
        "version": __version__,
        "orthanc_reachable": None,
        "db_reachable": None,
    }
```

- [ ] **Step 5: Write `app/main.py`**

```python
from fastapi import FastAPI

from app.routes import health


def create_app() -> FastAPI:
    app = FastAPI(title="NeuroScan API", version="0.1.0")
    app.include_router(health.router)
    return app


app = create_app()
```

- [ ] **Step 6: Smoke test**

Run:
```bash
cd services/api-service
uv run uvicorn app.main:app --port 8000 &
sleep 2
curl -s http://localhost:8000/health
kill %1
```
Expected: JSON body with `"status":"ok"`.

- [ ] **Step 7: Commit**

```bash
git add services/api-service/app/__init__.py services/api-service/app/config.py services/api-service/app/main.py services/api-service/app/routes/__init__.py services/api-service/app/routes/health.py
git commit -m "feat(slice-1): add FastAPI skeleton with /health endpoint"
```

### Task C3: SQLAlchemy engine + Alembic

**Files:**
- Create: `services/api-service/app/db.py`
- Create: `services/api-service/app/models/__init__.py`
- Create: `services/api-service/app/models/audit.py`
- Create: `services/api-service/alembic.ini`
- Create: `services/api-service/app/alembic/env.py`
- Create: `services/api-service/app/alembic/script.py.mako`

- [ ] **Step 1: Write `app/db.py`**

```python
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    pass


_engine = None
_SessionLocal = None


def _init_engine() -> None:
    global _engine, _SessionLocal
    if _engine is None:
        settings = get_settings()
        _engine = create_engine(settings.database_url, pool_pre_ping=True)
        _SessionLocal = sessionmaker(bind=_engine, autoflush=False, autocommit=False)


def get_engine():
    _init_engine()
    return _engine


def get_session() -> Generator[Session, None, None]:
    _init_engine()
    assert _SessionLocal is not None
    db = _SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

- [ ] **Step 2: Write `app/models/__init__.py`**

```python
from app.models.audit import AuditEvent

__all__ = ["AuditEvent"]
```

- [ ] **Step 3: Write `app/models/audit.py`**

```python
import uuid
from datetime import datetime, timezone

from sqlalchemy import BigInteger, DateTime, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), unique=True, nullable=False, default=uuid.uuid4
    )
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    actor: Mapped[str] = mapped_column(String(128), nullable=False, default="local-user")
    study_instance_uid: Mapped[str | None] = mapped_column(String(128), nullable=True)
    series_instance_uid: Mapped[str | None] = mapped_column(String(128), nullable=True)
    sop_instance_uid: Mapped[str | None] = mapped_column(String(128), nullable=True)
    orthanc_instance_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    checksum_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        Index("idx_audit_created_at", created_at.desc()),
        Index("idx_audit_event_type", event_type),
    )
```

- [ ] **Step 4: Write `alembic.ini`**

```ini
[alembic]
script_location = app/alembic
prepend_sys_path = .
sqlalchemy.url =

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console
qualname =

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
```

- [ ] **Step 5: Write `app/alembic/script.py.mako`**

```python
"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}

"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
${imports if imports else ""}

revision: str = ${repr(up_revision)}
down_revision: str | None = ${repr(down_revision)}
branch_labels: str | Sequence[str] | None = ${repr(branch_labels)}
depends_on: str | Sequence[str] | None = ${repr(depends_on)}


def upgrade() -> None:
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    ${downgrades if downgrades else "pass"}
```

- [ ] **Step 6: Write `app/alembic/env.py`**

```python
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.config import get_settings
from app.db import Base
import app.models  # noqa: F401  (registers models with Base.metadata)

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

config.set_main_option("sqlalchemy.url", get_settings().database_url)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

- [ ] **Step 7: Generate the initial migration**

Bring up just postgres so Alembic can autogenerate against an empty schema:
```bash
cd infra && docker compose up -d postgres && cd ../services/api-service
DATABASE_URL=postgresql+psycopg://neuroscan:neuroscan@localhost:5432/neuroscan \
  uv run alembic revision --autogenerate -m "audit_events"
```
Expected: `app/alembic/versions/<hash>_audit_events.py` created. Inspect it: it should call `op.create_table('audit_events', ...)` with the columns from `AuditEvent`.

Rename it to a stable filename for the plan:
```bash
mv app/alembic/versions/*_audit_events.py app/alembic/versions/001_audit_events.py
```

Edit the file's `revision: str = ...` line to `revision: str = "001"` and `down_revision: str | None = None`. Save.

- [ ] **Step 8: Apply the migration**

Run:
```bash
DATABASE_URL=postgresql+psycopg://neuroscan:neuroscan@localhost:5432/neuroscan \
  uv run alembic upgrade head
```
Expected: log line `Running upgrade  -> 001, audit_events`. Verify table exists:
```bash
docker exec -i neuroscan-postgres-1 psql -U neuroscan -c "\d audit_events"
```
(Container name may vary; use `docker compose ps` to confirm.)

- [ ] **Step 9: Tear down**

```bash
cd ../../infra && docker compose down
```

- [ ] **Step 10: Commit**

```bash
git add services/api-service/app/db.py services/api-service/app/models/ services/api-service/alembic.ini services/api-service/app/alembic/
git commit -m "feat(slice-1): add SQLAlchemy + Alembic with audit_events table"
```

### Task C4: Pydantic schemas

**Files:**
- Create: `services/api-service/app/schemas/__init__.py`
- Create: `services/api-service/app/schemas/audit.py`
- Create: `services/api-service/app/schemas/study.py`
- Create: `services/api-service/app/schemas/upload.py`

- [ ] **Step 1: `app/schemas/__init__.py`** — empty file.

- [ ] **Step 2: `app/schemas/audit.py`**

```python
import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


class AuditEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    event_id: uuid.UUID
    event_type: str
    status: Literal["success", "failure"]
    message: str | None
    actor: str
    study_instance_uid: str | None
    series_instance_uid: str | None
    sop_instance_uid: str | None
    orthanc_instance_id: str | None
    checksum_sha256: str | None
    created_at: datetime


class AuditEventList(BaseModel):
    items: list[AuditEventOut]
    total: int
    limit: int
    offset: int
```

- [ ] **Step 3: `app/schemas/study.py`**

```python
from pydantic import BaseModel


class SeriesOut(BaseModel):
    orthanc_series_id: str
    series_instance_uid: str
    series_description: str | None
    modality: str | None
    series_number: int | None
    instance_count: int


class StudyOut(BaseModel):
    orthanc_study_id: str
    study_instance_uid: str
    patient_id: str | None
    modality: str | None
    study_date: str | None
    study_description: str | None
    series_count: int
    instance_count: int


class StudyDetailOut(StudyOut):
    series: list[SeriesOut]


class StudyListOut(BaseModel):
    items: list[StudyOut]
    total: int
    limit: int
    offset: int


class InstanceOut(BaseModel):
    orthanc_instance_id: str
    sop_instance_uid: str
    instance_number: int | None
    rows: int | None
    columns: int | None


class InstanceListOut(BaseModel):
    items: list[InstanceOut]
```

- [ ] **Step 4: `app/schemas/upload.py`**

```python
from pydantic import BaseModel


class UploadResult(BaseModel):
    status: str
    study_instance_uid: str
    series_instance_uid: str
    sop_instance_uid: str
    orthanc_instance_id: str
    checksum_sha256: str


class ApiError(BaseModel):
    detail: str
    code: str | None = None
```

- [ ] **Step 5: Commit**

```bash
git add services/api-service/app/schemas/
git commit -m "feat(slice-1): add pydantic DTOs for audit, study, upload"
```

---

## Phase D — `api-service` core modules (TDD)

### Task D1: Synthetic DICOM fixture (used by every later test)

**Files:**
- Create: `services/api-service/tests/__init__.py`
- Create: `services/api-service/tests/fixtures/__init__.py`
- Create: `services/api-service/tests/fixtures/synthetic_dicom.py`

- [ ] **Step 1: Both `__init__.py` files** — empty.

- [ ] **Step 2: Write `tests/fixtures/synthetic_dicom.py`**

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
from pydicom.dataset import Dataset, FileDataset, FileMetaDataset
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
    ds.InstanceNumber = 1
    ds.Rows = rows
    ds.Columns = columns
    ds.BitsAllocated = 16
    ds.BitsStored = 16
    ds.HighBit = 15
    ds.PixelRepresentation = 0
    ds.SamplesPerPixel = 1
    ds.PhotometricInterpretation = "MONOCHROME2"

    pixel_array = np.random.default_rng(seed=42).integers(0, 4096, (rows, columns), dtype=np.uint16)
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

- [ ] **Step 3: Sanity check the fixture**

Run:
```bash
cd services/api-service
uv run python -c "
from tests.fixtures.synthetic_dicom import make_synthetic_mr_dicom_bytes
import pydicom
from io import BytesIO
b = make_synthetic_mr_dicom_bytes()
ds = pydicom.dcmread(BytesIO(b))
assert ds.Modality == 'MR'
assert ds.Rows == 16
print('OK', len(b), 'bytes')
"
```
Expected: `OK <some-int> bytes`.

- [ ] **Step 4: Commit**

```bash
git add services/api-service/tests/__init__.py services/api-service/tests/fixtures/
git commit -m "test(slice-1): add synthetic DICOM fixture generator"
```

### Task D2: Checksum service (TDD)

**Files:**
- Create: `services/api-service/tests/unit/__init__.py`
- Create: `services/api-service/tests/unit/test_checksum.py`
- Create: `services/api-service/app/services/__init__.py`
- Create: `services/api-service/app/services/checksum.py`

- [ ] **Step 1: Both `__init__.py` files** — empty.

- [ ] **Step 2: Write the failing test**

`tests/unit/test_checksum.py`:
```python
from app.services.checksum import sha256_of


def test_sha256_of_empty_bytes():
    assert sha256_of(b"") == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"


def test_sha256_of_known_input():
    assert sha256_of(b"hello").startswith("2cf24dba5fb0a30e")


def test_sha256_of_is_hex():
    digest = sha256_of(b"abc")
    assert len(digest) == 64
    int(digest, 16)  # raises if not hex
```

- [ ] **Step 3: Run test, expect FAIL**

```bash
cd services/api-service
uv run pytest tests/unit/test_checksum.py -v
```
Expected: import error / FAIL.

- [ ] **Step 4: Write minimal implementation**

`app/services/checksum.py`:
```python
import hashlib


def sha256_of(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()
```

- [ ] **Step 5: Run test, expect PASS**

```bash
uv run pytest tests/unit/test_checksum.py -v
```
Expected: 3 passed.

- [ ] **Step 6: Commit**

```bash
git add services/api-service/tests/unit/__init__.py services/api-service/tests/unit/test_checksum.py services/api-service/app/services/__init__.py services/api-service/app/services/checksum.py
git commit -m "feat(slice-1): add checksum.sha256_of with tests"
```

### Task D3: DICOM validation (TDD)

**Files:**
- Create: `services/api-service/tests/unit/test_dicom_validation.py`
- Create: `services/api-service/app/services/dicom_validation.py`

- [ ] **Step 1: Write the failing tests**

`tests/unit/test_dicom_validation.py`:
```python
import pytest

from app.services.dicom_validation import (
    DicomValidationError,
    InvalidDicomError,
    MissingRequiredTagError,
    validate_dicom,
)
from tests.fixtures.synthetic_dicom import (
    make_dicom_missing_modality,
    make_synthetic_mr_dicom_bytes,
)


def test_validate_synthetic_mr_returns_dataset():
    raw = make_synthetic_mr_dicom_bytes()
    ds = validate_dicom(raw)
    assert ds.Modality == "MR"
    assert ds.StudyInstanceUID
    assert ds.SeriesInstanceUID
    assert ds.SOPInstanceUID


def test_validate_empty_bytes_raises_invalid():
    with pytest.raises(InvalidDicomError):
        validate_dicom(b"")


def test_validate_garbage_raises_invalid():
    with pytest.raises(InvalidDicomError):
        validate_dicom(b"this is not a dicom file at all")


def test_validate_missing_modality_raises_missing_tag():
    raw = make_dicom_missing_modality()
    with pytest.raises(MissingRequiredTagError) as exc:
        validate_dicom(raw)
    assert "Modality" in str(exc.value)


def test_errors_share_base_class():
    assert issubclass(InvalidDicomError, DicomValidationError)
    assert issubclass(MissingRequiredTagError, DicomValidationError)
```

- [ ] **Step 2: Run, expect FAIL**

```bash
uv run pytest tests/unit/test_dicom_validation.py -v
```

- [ ] **Step 3: Write implementation**

`app/services/dicom_validation.py`:
```python
from io import BytesIO

import pydicom
from pydicom.dataset import Dataset
from pydicom.errors import InvalidDicomError as PydicomInvalidDicomError

REQUIRED_TAGS: tuple[str, ...] = (
    "StudyInstanceUID",
    "SeriesInstanceUID",
    "SOPInstanceUID",
    "Modality",
)


class DicomValidationError(Exception):
    """Base class for DICOM validation failures."""


class InvalidDicomError(DicomValidationError):
    """Bytes are not a parseable DICOM file."""


class MissingRequiredTagError(DicomValidationError):
    """DICOM is parseable but missing a required tag."""

    def __init__(self, tag: str) -> None:
        self.tag = tag
        super().__init__(f"Missing required DICOM tag: {tag}")


def validate_dicom(data: bytes) -> Dataset:
    """Parse and validate DICOM bytes.

    Raises:
        InvalidDicomError: bytes cannot be parsed as DICOM.
        MissingRequiredTagError: parsed but missing a required tag.
    """
    if not data:
        raise InvalidDicomError("Empty bytes")
    try:
        ds = pydicom.dcmread(BytesIO(data), force=False)
    except (PydicomInvalidDicomError, Exception) as exc:
        # Force=False rejects non-DICOM. Anything else (truncated, etc.)
        # we also classify as invalid.
        raise InvalidDicomError(str(exc)) from exc

    for tag in REQUIRED_TAGS:
        if not getattr(ds, tag, None):
            raise MissingRequiredTagError(tag)
    return ds
```

- [ ] **Step 4: Run, expect PASS**

```bash
uv run pytest tests/unit/test_dicom_validation.py -v
```
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add services/api-service/tests/unit/test_dicom_validation.py services/api-service/app/services/dicom_validation.py
git commit -m "feat(slice-1): add DICOM validation with required-tag checks"
```

### Task D4: Metadata extraction (TDD)

**Files:**
- Create: `services/api-service/tests/unit/test_metadata.py`
- Create: `services/api-service/app/services/metadata.py`

- [ ] **Step 1: Write tests**

`tests/unit/test_metadata.py`:
```python
from io import BytesIO

import pydicom

from app.services.metadata import extract_metadata
from tests.fixtures.synthetic_dicom import make_synthetic_mr_dicom_bytes


def test_extract_metadata_returns_expected_fields():
    raw = make_synthetic_mr_dicom_bytes(patient_id="P-1")
    ds = pydicom.dcmread(BytesIO(raw))
    md = extract_metadata(ds)
    assert md["patient_id"] == "P-1"
    assert md["modality"] == "MR"
    assert md["study_instance_uid"] == ds.StudyInstanceUID
    assert md["series_instance_uid"] == ds.SeriesInstanceUID
    assert md["sop_instance_uid"] == ds.SOPInstanceUID
    assert md["rows"] == 16
    assert md["columns"] == 16


def test_extract_metadata_handles_missing_optional_fields():
    raw = make_synthetic_mr_dicom_bytes()
    ds = pydicom.dcmread(BytesIO(raw))
    del ds.StudyDescription
    md = extract_metadata(ds)
    assert md["study_description"] is None
    assert md["modality"] == "MR"  # required fields still there
```

- [ ] **Step 2: Run, FAIL**

```bash
uv run pytest tests/unit/test_metadata.py -v
```

- [ ] **Step 3: Implementation**

`app/services/metadata.py`:
```python
from typing import Any

from pydicom.dataset import Dataset


def _str_or_none(ds: Dataset, tag: str) -> str | None:
    value = getattr(ds, tag, None)
    if value in (None, ""):
        return None
    return str(value)


def _int_or_none(ds: Dataset, tag: str) -> int | None:
    value = getattr(ds, tag, None)
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def extract_metadata(ds: Dataset) -> dict[str, Any]:
    return {
        "patient_id": _str_or_none(ds, "PatientID"),
        "study_instance_uid": _str_or_none(ds, "StudyInstanceUID"),
        "series_instance_uid": _str_or_none(ds, "SeriesInstanceUID"),
        "sop_instance_uid": _str_or_none(ds, "SOPInstanceUID"),
        "modality": _str_or_none(ds, "Modality"),
        "study_date": _str_or_none(ds, "StudyDate"),
        "study_description": _str_or_none(ds, "StudyDescription"),
        "series_description": _str_or_none(ds, "SeriesDescription"),
        "series_number": _int_or_none(ds, "SeriesNumber"),
        "instance_number": _int_or_none(ds, "InstanceNumber"),
        "rows": _int_or_none(ds, "Rows"),
        "columns": _int_or_none(ds, "Columns"),
    }
```

- [ ] **Step 4: Run, PASS**

```bash
uv run pytest tests/unit/test_metadata.py -v
```

- [ ] **Step 5: Commit**

```bash
git add services/api-service/tests/unit/test_metadata.py services/api-service/app/services/metadata.py
git commit -m "feat(slice-1): add DICOM metadata extraction"
```

### Task D5: OrthancClient (TDD with respx)

**Files:**
- Create: `services/api-service/app/clients/__init__.py`
- Create: `services/api-service/app/clients/orthanc.py`
- Create: `services/api-service/tests/unit/test_orthanc_client.py`

- [ ] **Step 1: `app/clients/__init__.py`** — empty.

- [ ] **Step 2: Write the tests**

`tests/unit/test_orthanc_client.py`:
```python
import httpx
import pytest
import respx

from app.clients.orthanc import OrthancClient, OrthancError


@pytest.fixture
def client() -> OrthancClient:
    return OrthancClient(base_url="http://orthanc:8042", user="u", password="p")


@respx.mock
async def test_upload_instance_returns_id(client: OrthancClient):
    route = respx.post("http://orthanc:8042/instances").respond(
        200, json={"ID": "abc-123", "Status": "Success"}
    )
    instance_id = await client.upload_instance(b"fake-dicom-bytes")
    assert instance_id == "abc-123"
    assert route.called


@respx.mock
async def test_upload_instance_raises_on_4xx(client: OrthancClient):
    respx.post("http://orthanc:8042/instances").respond(400, text="bad dicom")
    with pytest.raises(OrthancError):
        await client.upload_instance(b"x")


@respx.mock
async def test_upload_instance_retries_on_5xx_then_succeeds(client: OrthancClient):
    respx.post("http://orthanc:8042/instances").mock(
        side_effect=[
            httpx.Response(503),
            httpx.Response(503),
            httpx.Response(200, json={"ID": "ok-1"}),
        ]
    )
    instance_id = await client.upload_instance(b"x")
    assert instance_id == "ok-1"


@respx.mock
async def test_upload_instance_raises_after_retries_exhausted(client: OrthancClient):
    respx.post("http://orthanc:8042/instances").respond(500)
    with pytest.raises(OrthancError):
        await client.upload_instance(b"x")


@respx.mock
async def test_get_studies_returns_list(client: OrthancClient):
    respx.get("http://orthanc:8042/studies").respond(
        200, json=["s1", "s2"]
    )
    respx.get("http://orthanc:8042/studies/s1").respond(
        200, json={"ID": "s1", "MainDicomTags": {"StudyInstanceUID": "1.2.3"}, "Series": []}
    )
    respx.get("http://orthanc:8042/studies/s2").respond(
        200, json={"ID": "s2", "MainDicomTags": {"StudyInstanceUID": "4.5.6"}, "Series": []}
    )
    studies = await client.list_studies()
    assert {s["ID"] for s in studies} == {"s1", "s2"}


@respx.mock
async def test_get_preview_passes_through_bytes(client: OrthancClient):
    respx.get("http://orthanc:8042/instances/abc/preview").respond(
        200, content=b"\x89PNG-fake", headers={"Content-Type": "image/png"}
    )
    content, content_type = await client.get_instance_preview("abc")
    assert content == b"\x89PNG-fake"
    assert content_type == "image/png"
```

- [ ] **Step 3: Run, FAIL**

```bash
uv run pytest tests/unit/test_orthanc_client.py -v
```

- [ ] **Step 4: Implementation**

`app/clients/orthanc.py`:
```python
import asyncio
from typing import Any

import httpx


class OrthancError(Exception):
    """Raised when Orthanc returns an unexpected response."""


class OrthancClient:
    """Thin async httpx client for Orthanc REST API."""

    def __init__(
        self,
        base_url: str,
        user: str,
        password: str,
        *,
        timeout: float = 30.0,
        max_retries: int = 3,
        retry_backoff_seconds: float = 0.5,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._auth = (user, password)
        self._timeout = timeout
        self._max_retries = max_retries
        self._retry_backoff_seconds = retry_backoff_seconds

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=self._base_url, auth=self._auth, timeout=self._timeout
        )

    async def _request_with_retries(
        self, method: str, path: str, **kwargs: Any
    ) -> httpx.Response:
        last_exc: Exception | None = None
        for attempt in range(self._max_retries):
            try:
                async with self._client() as client:
                    response = await client.request(method, path, **kwargs)
                if 500 <= response.status_code < 600:
                    last_exc = OrthancError(
                        f"Orthanc {response.status_code} on {method} {path}"
                    )
                    if attempt < self._max_retries - 1:
                        await asyncio.sleep(self._retry_backoff_seconds * (2**attempt))
                        continue
                    raise last_exc
                return response
            except httpx.HTTPError as exc:
                last_exc = OrthancError(str(exc))
                if attempt < self._max_retries - 1:
                    await asyncio.sleep(self._retry_backoff_seconds * (2**attempt))
                    continue
                raise last_exc from exc
        assert last_exc is not None
        raise last_exc

    async def upload_instance(self, dicom_bytes: bytes) -> str:
        response = await self._request_with_retries(
            "POST",
            "/instances",
            content=dicom_bytes,
            headers={"Content-Type": "application/dicom"},
        )
        if response.status_code >= 400:
            raise OrthancError(
                f"Orthanc rejected upload: {response.status_code} {response.text}"
            )
        body = response.json()
        instance_id = body.get("ID")
        if not instance_id:
            raise OrthancError(f"Orthanc upload missing ID in response: {body}")
        return instance_id

    async def list_studies(self) -> list[dict[str, Any]]:
        response = await self._request_with_retries("GET", "/studies")
        ids: list[str] = response.json()
        studies: list[dict[str, Any]] = []
        for sid in ids:
            detail = await self._request_with_retries("GET", f"/studies/{sid}")
            studies.append(detail.json())
        return studies

    async def get_study(self, orthanc_study_id: str) -> dict[str, Any]:
        response = await self._request_with_retries(
            "GET", f"/studies/{orthanc_study_id}"
        )
        if response.status_code == 404:
            raise OrthancError(f"Study {orthanc_study_id} not found")
        return response.json()

    async def get_series(self, orthanc_series_id: str) -> dict[str, Any]:
        response = await self._request_with_retries(
            "GET", f"/series/{orthanc_series_id}"
        )
        return response.json()

    async def find_study_by_uid(self, study_instance_uid: str) -> str | None:
        response = await self._request_with_retries(
            "POST",
            "/tools/find",
            json={
                "Level": "Study",
                "Query": {"StudyInstanceUID": study_instance_uid},
            },
        )
        ids = response.json()
        return ids[0] if ids else None

    async def find_series_by_uid(self, series_instance_uid: str) -> str | None:
        response = await self._request_with_retries(
            "POST",
            "/tools/find",
            json={
                "Level": "Series",
                "Query": {"SeriesInstanceUID": series_instance_uid},
            },
        )
        ids = response.json()
        return ids[0] if ids else None

    async def get_instance(self, orthanc_instance_id: str) -> dict[str, Any]:
        response = await self._request_with_retries(
            "GET", f"/instances/{orthanc_instance_id}"
        )
        return response.json()

    async def get_instance_preview(
        self, orthanc_instance_id: str
    ) -> tuple[bytes, str]:
        response = await self._request_with_retries(
            "GET", f"/instances/{orthanc_instance_id}/preview"
        )
        if response.status_code == 404:
            raise OrthancError(f"Instance {orthanc_instance_id} preview not found")
        return response.content, response.headers.get("Content-Type", "image/png")

    async def system(self) -> dict[str, Any]:
        response = await self._request_with_retries("GET", "/system")
        return response.json()
```

- [ ] **Step 5: Run, PASS**

```bash
uv run pytest tests/unit/test_orthanc_client.py -v
```
Expected: 6 passed.

- [ ] **Step 6: Commit**

```bash
git add services/api-service/app/clients/ services/api-service/tests/unit/test_orthanc_client.py
git commit -m "feat(slice-1): add OrthancClient with retries and respx tests"
```

### Task D6: Audit service (TDD with in-memory SQLite)

**Files:**
- Create: `services/api-service/tests/unit/test_audit_service.py`
- Create: `services/api-service/app/services/audit.py`

- [ ] **Step 1: Write tests**

`tests/unit/test_audit_service.py`:
```python
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db import Base
from app.models.audit import AuditEvent
from app.services.audit import list_events, write_event


@pytest.fixture
def session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    with SessionLocal() as s:
        yield s


def test_write_event_persists_row(session: Session):
    write_event(
        session,
        event_type="dicom_uploaded",
        status="success",
        message=None,
        study_instance_uid="1.2.3",
        series_instance_uid="1.2.4",
        sop_instance_uid="1.2.5",
        orthanc_instance_id="abc",
        checksum_sha256="deadbeef",
    )
    rows = session.query(AuditEvent).all()
    assert len(rows) == 1
    assert rows[0].status == "success"
    assert rows[0].event_id is not None


def test_list_events_orders_newest_first(session: Session):
    for i in range(3):
        write_event(
            session,
            event_type="dicom_uploaded",
            status="success",
            message=f"e{i}",
        )
    items, total = list_events(session, limit=10, offset=0)
    assert total == 3
    assert [e.message for e in items] == ["e2", "e1", "e0"]


def test_list_events_filters_by_event_type(session: Session):
    write_event(session, event_type="dicom_uploaded", status="success")
    write_event(session, event_type="other_event", status="success")
    items, total = list_events(session, event_type="dicom_uploaded")
    assert total == 1
    assert items[0].event_type == "dicom_uploaded"


def test_list_events_filters_by_status(session: Session):
    write_event(session, event_type="dicom_uploaded", status="success")
    write_event(session, event_type="dicom_uploaded", status="failure")
    items, total = list_events(session, status="failure")
    assert total == 1
    assert items[0].status == "failure"
```

- [ ] **Step 2: Run, FAIL**

```bash
uv run pytest tests/unit/test_audit_service.py -v
```

(Note: SQLite doesn't support `UUID(as_uuid=True)` by default. We'll handle that by making the column type compatible — `String(36)` fallback when SQLite. But the cleanest fix is to use `sqlalchemy.types.Uuid` (cross-dialect). Let's update the model.)

- [ ] **Step 3: Update `app/models/audit.py` to use cross-dialect UUID**

Replace:
```python
from sqlalchemy.dialects.postgresql import UUID
```
with:
```python
from sqlalchemy import Uuid
```
and:
```python
event_id: Mapped[uuid.UUID] = mapped_column(
    UUID(as_uuid=True), unique=True, nullable=False, default=uuid.uuid4
)
```
with:
```python
event_id: Mapped[uuid.UUID] = mapped_column(
    Uuid(as_uuid=True), unique=True, nullable=False, default=uuid.uuid4
)
```

Regenerate the migration to keep it consistent:
```bash
cd services/api-service
rm app/alembic/versions/001_audit_events.py
cd ../../infra && docker compose up -d postgres && cd ../services/api-service
DATABASE_URL=postgresql+psycopg://neuroscan:neuroscan@localhost:5432/neuroscan \
  uv run alembic revision --autogenerate -m "audit_events"
mv app/alembic/versions/*_audit_events.py app/alembic/versions/001_audit_events.py
```
Manually edit the new migration: set `revision = "001"`, `down_revision = None`, then re-apply:
```bash
DATABASE_URL=postgresql+psycopg://neuroscan:neuroscan@localhost:5432/neuroscan \
  uv run alembic downgrade base && uv run alembic upgrade head
cd ../../infra && docker compose down
```

- [ ] **Step 4: Implementation**

`app/services/audit.py`:
```python
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.audit import AuditEvent


def write_event(
    session: Session,
    *,
    event_type: str,
    status: str,
    message: str | None = None,
    actor: str = "local-user",
    study_instance_uid: str | None = None,
    series_instance_uid: str | None = None,
    sop_instance_uid: str | None = None,
    orthanc_instance_id: str | None = None,
    checksum_sha256: str | None = None,
) -> AuditEvent:
    event = AuditEvent(
        event_type=event_type,
        status=status,
        message=message,
        actor=actor,
        study_instance_uid=study_instance_uid,
        series_instance_uid=series_instance_uid,
        sop_instance_uid=sop_instance_uid,
        orthanc_instance_id=orthanc_instance_id,
        checksum_sha256=checksum_sha256,
    )
    session.add(event)
    session.commit()
    session.refresh(event)
    return event


def list_events(
    session: Session,
    *,
    limit: int = 50,
    offset: int = 0,
    event_type: str | None = None,
    status: str | None = None,
) -> tuple[list[AuditEvent], int]:
    stmt = select(AuditEvent)
    count_stmt = select(func.count()).select_from(AuditEvent)
    if event_type:
        stmt = stmt.where(AuditEvent.event_type == event_type)
        count_stmt = count_stmt.where(AuditEvent.event_type == event_type)
    if status:
        stmt = stmt.where(AuditEvent.status == status)
        count_stmt = count_stmt.where(AuditEvent.status == status)
    stmt = stmt.order_by(AuditEvent.created_at.desc()).limit(limit).offset(offset)
    items = list(session.scalars(stmt))
    total = session.scalar(count_stmt) or 0
    return items, total
```

- [ ] **Step 5: Run, PASS**

```bash
uv run pytest tests/unit/test_audit_service.py -v
```

- [ ] **Step 6: Commit**

```bash
git add services/api-service/app/models/audit.py services/api-service/app/alembic/versions/001_audit_events.py services/api-service/app/services/audit.py services/api-service/tests/unit/test_audit_service.py
git commit -m "feat(slice-1): add audit service with write_event and list_events"
```

### Task D7: Upload service (orchestrator, TDD)

**Files:**
- Create: `services/api-service/tests/unit/test_upload_service.py`
- Create: `services/api-service/app/services/upload.py`

- [ ] **Step 1: Write tests**

`tests/unit/test_upload_service.py`:
```python
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.clients.orthanc import OrthancError
from app.db import Base
from app.models.audit import AuditEvent
from app.services.dicom_validation import (
    InvalidDicomError,
    MissingRequiredTagError,
)
from app.services.upload import UploadFailedError, handle_upload
from tests.fixtures.synthetic_dicom import (
    make_dicom_missing_modality,
    make_synthetic_mr_dicom_bytes,
)


@pytest.fixture
def session():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    with SessionLocal() as s:
        yield s


async def test_handle_upload_happy_path(session):
    orthanc = AsyncMock()
    orthanc.upload_instance.return_value = "orthanc-id-1"

    raw = make_synthetic_mr_dicom_bytes()
    result = await handle_upload(session=session, orthanc=orthanc, dicom_bytes=raw)

    assert result.orthanc_instance_id == "orthanc-id-1"
    assert len(result.checksum_sha256) == 64
    orthanc.upload_instance.assert_awaited_once_with(raw)
    rows = session.query(AuditEvent).all()
    assert len(rows) == 1
    assert rows[0].status == "success"
    assert rows[0].orthanc_instance_id == "orthanc-id-1"


async def test_handle_upload_invalid_dicom_writes_failure_audit(session):
    orthanc = AsyncMock()
    with pytest.raises(UploadFailedError) as exc:
        await handle_upload(session=session, orthanc=orthanc, dicom_bytes=b"garbage")
    assert exc.value.code == "invalid_dicom"
    orthanc.upload_instance.assert_not_awaited()
    rows = session.query(AuditEvent).all()
    assert len(rows) == 1
    assert rows[0].status == "failure"


async def test_handle_upload_missing_tag_writes_failure_audit(session):
    orthanc = AsyncMock()
    raw = make_dicom_missing_modality()
    with pytest.raises(UploadFailedError) as exc:
        await handle_upload(session=session, orthanc=orthanc, dicom_bytes=raw)
    assert exc.value.code == "missing_required_tag"
    orthanc.upload_instance.assert_not_awaited()
    rows = session.query(AuditEvent).all()
    assert rows[0].status == "failure"


async def test_handle_upload_orthanc_failure_writes_audit(session):
    orthanc = AsyncMock()
    orthanc.upload_instance.side_effect = OrthancError("boom")
    raw = make_synthetic_mr_dicom_bytes()
    with pytest.raises(UploadFailedError) as exc:
        await handle_upload(session=session, orthanc=orthanc, dicom_bytes=raw)
    assert exc.value.code == "orthanc_rejected"
    rows = session.query(AuditEvent).all()
    assert rows[0].status == "failure"
```

- [ ] **Step 2: Run, FAIL**

```bash
uv run pytest tests/unit/test_upload_service.py -v
```

- [ ] **Step 3: Implementation**

`app/services/upload.py`:
```python
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.clients.orthanc import OrthancClient, OrthancError
from app.services.audit import write_event
from app.services.checksum import sha256_of
from app.services.dicom_validation import (
    InvalidDicomError,
    MissingRequiredTagError,
    validate_dicom,
)
from app.services.metadata import extract_metadata


@dataclass
class UploadResult:
    study_instance_uid: str
    series_instance_uid: str
    sop_instance_uid: str
    orthanc_instance_id: str
    checksum_sha256: str


class UploadFailedError(Exception):
    def __init__(self, code: str, message: str, status_code: int) -> None:
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


async def handle_upload(
    *,
    session: Session,
    orthanc: OrthancClient,
    dicom_bytes: bytes,
) -> UploadResult:
    checksum = sha256_of(dicom_bytes)
    try:
        ds = validate_dicom(dicom_bytes)
    except InvalidDicomError as exc:
        write_event(
            session,
            event_type="dicom_uploaded",
            status="failure",
            message=f"invalid_dicom: {exc}",
            checksum_sha256=checksum,
        )
        raise UploadFailedError("invalid_dicom", str(exc), 400) from exc
    except MissingRequiredTagError as exc:
        write_event(
            session,
            event_type="dicom_uploaded",
            status="failure",
            message=f"missing_required_tag: {exc.tag}",
            checksum_sha256=checksum,
        )
        raise UploadFailedError("missing_required_tag", str(exc), 400) from exc

    md = extract_metadata(ds)
    try:
        orthanc_instance_id = await orthanc.upload_instance(dicom_bytes)
    except OrthancError as exc:
        write_event(
            session,
            event_type="dicom_uploaded",
            status="failure",
            message=f"orthanc_rejected: {exc}",
            study_instance_uid=md["study_instance_uid"],
            series_instance_uid=md["series_instance_uid"],
            sop_instance_uid=md["sop_instance_uid"],
            checksum_sha256=checksum,
        )
        raise UploadFailedError("orthanc_rejected", str(exc), 502) from exc

    write_event(
        session,
        event_type="dicom_uploaded",
        status="success",
        study_instance_uid=md["study_instance_uid"],
        series_instance_uid=md["series_instance_uid"],
        sop_instance_uid=md["sop_instance_uid"],
        orthanc_instance_id=orthanc_instance_id,
        checksum_sha256=checksum,
    )

    return UploadResult(
        study_instance_uid=md["study_instance_uid"],
        series_instance_uid=md["series_instance_uid"],
        sop_instance_uid=md["sop_instance_uid"],
        orthanc_instance_id=orthanc_instance_id,
        checksum_sha256=checksum,
    )
```

- [ ] **Step 4: Run, PASS**

```bash
uv run pytest tests/unit/test_upload_service.py -v
```

- [ ] **Step 5: Commit**

```bash
git add services/api-service/app/services/upload.py services/api-service/tests/unit/test_upload_service.py
git commit -m "feat(slice-1): add upload orchestrator service with audit integration"
```

---

## Phase E — Routes (wire services into HTTP)

### Task E1: Health route reaches DB + Orthanc

**Files:**
- Modify: `services/api-service/app/routes/health.py`

- [ ] **Step 1: Update health route**

```python
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app import __version__
from app.clients.orthanc import OrthancClient, OrthancError
from app.config import get_settings
from app.db import get_engine

router = APIRouter()


@router.get("/health")
async def health() -> JSONResponse:
    settings = get_settings()
    orthanc_ok = False
    try:
        client = OrthancClient(
            base_url=settings.orthanc_url,
            user=settings.orthanc_user,
            password=settings.orthanc_password,
            max_retries=1,
        )
        await client.system()
        orthanc_ok = True
    except OrthancError:
        orthanc_ok = False

    db_ok = False
    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
            db_ok = True
    except Exception:
        db_ok = False

    body = {
        "status": "ok" if (orthanc_ok and db_ok) else "degraded",
        "service": "api-service",
        "version": __version__,
        "orthanc_reachable": orthanc_ok,
        "db_reachable": db_ok,
    }
    code = 200 if (orthanc_ok and db_ok) else 503
    return JSONResponse(body, status_code=code)
```

- [ ] **Step 2: Commit**

```bash
git add services/api-service/app/routes/health.py
git commit -m "feat(slice-1): make /health verify db + orthanc reachability"
```

### Task E2: DICOM upload route

**Files:**
- Modify: `services/api-service/app/routes/__init__.py`
- Create: `services/api-service/app/routes/dicom.py`
- Modify: `services/api-service/app/main.py`

- [ ] **Step 1: Write `app/routes/dicom.py`**

```python
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.clients.orthanc import OrthancClient, OrthancError
from app.config import Settings, get_settings
from app.db import get_session
from app.schemas.upload import UploadResult
from app.services.upload import handle_upload

router = APIRouter(prefix="/api/dicom", tags=["dicom"])


def get_orthanc_client(settings: Settings = Depends(get_settings)) -> OrthancClient:
    return OrthancClient(
        base_url=settings.orthanc_url,
        user=settings.orthanc_user,
        password=settings.orthanc_password,
    )


@router.post(
    "/upload",
    response_model=UploadResult,
    status_code=status.HTTP_201_CREATED,
)
async def upload_dicom(
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
    orthanc: OrthancClient = Depends(get_orthanc_client),
) -> UploadResult:
    data = await file.read()
    # UploadFailedError is translated to a flat {detail, code} JSON body
    # by the global exception handler registered in app/main.py.
    result = await handle_upload(session=session, orthanc=orthanc, dicom_bytes=data)
    return UploadResult(
        status="uploaded",
        study_instance_uid=result.study_instance_uid,
        series_instance_uid=result.series_instance_uid,
        sop_instance_uid=result.sop_instance_uid,
        orthanc_instance_id=result.orthanc_instance_id,
        checksum_sha256=result.checksum_sha256,
    )


instances_router = APIRouter(prefix="/api/instances", tags=["instances"])


@instances_router.get("/{orthanc_instance_id}/preview.png")
async def preview_png(
    orthanc_instance_id: str,
    orthanc: OrthancClient = Depends(get_orthanc_client),
) -> Response:
    try:
        content, content_type = await orthanc.get_instance_preview(orthanc_instance_id)
    except OrthancError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return Response(content=content, media_type=content_type)
```

- [ ] **Step 2: Update `app/main.py`**

```python
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.routes import dicom, health
from app.services.upload import UploadFailedError


def create_app() -> FastAPI:
    app = FastAPI(title="NeuroScan API", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(UploadFailedError)
    async def upload_failed_handler(_: Request, exc: UploadFailedError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.message, "code": exc.code},
        )

    app.include_router(health.router)
    app.include_router(dicom.router)
    app.include_router(dicom.instances_router)
    return app


app = create_app()
```

- [ ] **Step 3: Commit**

```bash
git add services/api-service/app/routes/dicom.py services/api-service/app/main.py
git commit -m "feat(slice-1): add /api/dicom/upload and instance preview routes"
```

### Task E3: Studies routes

**Files:**
- Create: `services/api-service/app/routes/studies.py`
- Modify: `services/api-service/app/main.py`

- [ ] **Step 1: Write `app/routes/studies.py`**

```python
from fastapi import APIRouter, Depends, HTTPException, Query

from app.clients.orthanc import OrthancClient, OrthancError
from app.routes.dicom import get_orthanc_client
from app.schemas.study import (
    InstanceListOut,
    InstanceOut,
    SeriesOut,
    StudyDetailOut,
    StudyListOut,
    StudyOut,
)

router = APIRouter(prefix="/api", tags=["studies"])


def _study_from_orthanc(detail: dict) -> StudyOut:
    tags = detail.get("MainDicomTags", {})
    patient_tags = detail.get("PatientMainDicomTags", {})
    series_ids = detail.get("Series", [])
    return StudyOut(
        orthanc_study_id=detail["ID"],
        study_instance_uid=tags.get("StudyInstanceUID", ""),
        patient_id=patient_tags.get("PatientID"),
        modality=tags.get("ModalitiesInStudy") or tags.get("Modality"),
        study_date=tags.get("StudyDate"),
        study_description=tags.get("StudyDescription"),
        series_count=len(series_ids),
        instance_count=detail.get("Statistics", {}).get("CountInstances")
        or sum(1 for _ in series_ids),  # fallback approximation
    )


@router.get("/studies", response_model=StudyListOut)
async def list_studies(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    orthanc: OrthancClient = Depends(get_orthanc_client),
) -> StudyListOut:
    studies = await orthanc.list_studies()
    total = len(studies)
    page = studies[offset : offset + limit]
    items = [_study_from_orthanc(s) for s in page]
    return StudyListOut(items=items, total=total, limit=limit, offset=offset)


@router.get("/studies/{study_instance_uid}", response_model=StudyDetailOut)
async def get_study(
    study_instance_uid: str,
    orthanc: OrthancClient = Depends(get_orthanc_client),
) -> StudyDetailOut:
    orthanc_study_id = await orthanc.find_study_by_uid(study_instance_uid)
    if not orthanc_study_id:
        raise HTTPException(status_code=404, detail="study_not_found")
    detail = await orthanc.get_study(orthanc_study_id)
    series_out: list[SeriesOut] = []
    for series_id in detail.get("Series", []):
        s = await orthanc.get_series(series_id)
        s_tags = s.get("MainDicomTags", {})
        series_out.append(
            SeriesOut(
                orthanc_series_id=s["ID"],
                series_instance_uid=s_tags.get("SeriesInstanceUID", ""),
                series_description=s_tags.get("SeriesDescription"),
                modality=s_tags.get("Modality"),
                series_number=int(s_tags["SeriesNumber"])
                if s_tags.get("SeriesNumber")
                else None,
                instance_count=len(s.get("Instances", [])),
            )
        )
    base = _study_from_orthanc(detail)
    return StudyDetailOut(**base.model_dump(), series=series_out)


@router.get(
    "/series/{series_instance_uid}/instances",
    response_model=InstanceListOut,
)
async def list_series_instances(
    series_instance_uid: str,
    orthanc: OrthancClient = Depends(get_orthanc_client),
) -> InstanceListOut:
    orthanc_series_id = await orthanc.find_series_by_uid(series_instance_uid)
    if not orthanc_series_id:
        raise HTTPException(status_code=404, detail="series_not_found")
    detail = await orthanc.get_series(orthanc_series_id)
    items: list[InstanceOut] = []
    for inst_id in detail.get("Instances", []):
        inst = await orthanc.get_instance(inst_id)
        tags = inst.get("MainDicomTags", {})
        items.append(
            InstanceOut(
                orthanc_instance_id=inst["ID"],
                sop_instance_uid=tags.get("SOPInstanceUID", ""),
                instance_number=int(tags["InstanceNumber"])
                if tags.get("InstanceNumber")
                else None,
                rows=int(tags["Rows"]) if tags.get("Rows") else None,
                columns=int(tags["Columns"]) if tags.get("Columns") else None,
            )
        )
    return InstanceListOut(items=items)
```

- [ ] **Step 2: Wire into `app/main.py`**

Add `from app.routes import dicom, health, studies` and `app.include_router(studies.router)`.

- [ ] **Step 3: Commit**

```bash
git add services/api-service/app/routes/studies.py services/api-service/app/main.py
git commit -m "feat(slice-1): add /api/studies and /api/series routes"
```

### Task E4: Audit route

**Files:**
- Create: `services/api-service/app/routes/audit.py`
- Modify: `services/api-service/app/main.py`

- [ ] **Step 1: Write `app/routes/audit.py`**

```python
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db import get_session
from app.schemas.audit import AuditEventList, AuditEventOut
from app.services.audit import list_events

router = APIRouter(prefix="/api/audit", tags=["audit"])


@router.get("/events", response_model=AuditEventList)
async def get_events(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    event_type: str | None = None,
    status: str | None = None,
    session: Session = Depends(get_session),
) -> AuditEventList:
    items, total = list_events(
        session,
        limit=limit,
        offset=offset,
        event_type=event_type,
        status=status,
    )
    return AuditEventList(
        items=[AuditEventOut.model_validate(i) for i in items],
        total=total,
        limit=limit,
        offset=offset,
    )
```

- [ ] **Step 2: Wire into `app/main.py`**

Add `audit` to the imports and `app.include_router(audit.router)`.

- [ ] **Step 3: Commit**

```bash
git add services/api-service/app/routes/audit.py services/api-service/app/main.py
git commit -m "feat(slice-1): add /api/audit/events route"
```

---

## Phase F — Integration tests with testcontainers

### Task F1: `conftest.py` with shared containers + httpx client

**Files:**
- Create: `services/api-service/tests/conftest.py`
- Create: `services/api-service/tests/integration/__init__.py`

- [ ] **Step 1: Write `tests/conftest.py`**

```python
"""Session-scoped fixtures: Postgres + Orthanc via testcontainers."""

from __future__ import annotations

import os
import time
from collections.abc import AsyncIterator, Iterator
from typing import Any

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from testcontainers.core.container import DockerContainer
from testcontainers.core.waiting_utils import wait_for_logs
from testcontainers.postgres import PostgresContainer

from app.db import Base


@pytest.fixture(scope="session")
def postgres_container() -> Iterator[PostgresContainer]:
    with PostgresContainer("postgres:16", driver="psycopg") as pg:
        yield pg


@pytest.fixture(scope="session")
def orthanc_container() -> Iterator[DockerContainer]:
    container = (
        DockerContainer("orthancteam/orthanc:24.7.3")
        .with_exposed_ports(8042)
        .with_env("ORTHANC__REGISTERED_USERS", '{"orthanc":"orthanc"}')
        .with_env("ORTHANC__AUTHENTICATION_ENABLED", "true")
    )
    container.start()
    try:
        wait_for_logs(container, "Orthanc has started", timeout=60)
        yield container
    finally:
        container.stop()


@pytest.fixture(scope="session")
def orthanc_url(orthanc_container: DockerContainer) -> str:
    host = orthanc_container.get_container_host_ip()
    port = orthanc_container.get_exposed_port(8042)
    url = f"http://{host}:{port}"
    # Poll until /system responds
    deadline = time.time() + 30
    while time.time() < deadline:
        try:
            r = httpx.get(f"{url}/system", auth=("orthanc", "orthanc"), timeout=2)
            if r.status_code == 200:
                return url
        except httpx.HTTPError:
            pass
        time.sleep(0.5)
    raise RuntimeError("Orthanc did not become reachable")


@pytest.fixture(scope="session")
def database_url(postgres_container: PostgresContainer) -> str:
    return postgres_container.get_connection_url()


@pytest.fixture(scope="session", autouse=True)
def configure_settings(database_url: str, orthanc_url: str) -> Iterator[None]:
    """Override settings via env so the FastAPI app under test sees test infra."""
    old: dict[str, str | None] = {}
    overrides = {
        "DATABASE_URL": database_url,
        "ORTHANC_URL": orthanc_url,
        "ORTHANC_USER": "orthanc",
        "ORTHANC_PASSWORD": "orthanc",
    }
    for k, v in overrides.items():
        old[k] = os.environ.get(k)
        os.environ[k] = v

    # Reset cached settings
    from app.config import get_settings

    get_settings.cache_clear()

    # Create schema fresh
    engine = create_engine(database_url)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    engine.dispose()

    yield

    for k, v in old.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v
    get_settings.cache_clear()


@pytest.fixture
def db_session(database_url: str):
    engine = create_engine(database_url)
    SessionLocal = sessionmaker(bind=engine)
    with SessionLocal() as s:
        yield s
        s.rollback()
    # Truncate audit_events between tests
    with engine.begin() as conn:
        conn.exec_driver_sql("TRUNCATE TABLE audit_events RESTART IDENTITY")
    engine.dispose()


@pytest_asyncio.fixture
async def api_client(orthanc_url: str) -> AsyncIterator[httpx.AsyncClient]:
    from app.main import create_app

    # Reset Orthanc state between tests by deleting all studies
    async with httpx.AsyncClient(base_url=orthanc_url, auth=("orthanc", "orthanc")) as oc:
        r = await oc.get("/studies")
        for sid in r.json():
            await oc.delete(f"/studies/{sid}")

    app = create_app()
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        yield client
```

- [ ] **Step 2: `tests/integration/__init__.py`** — empty.

- [ ] **Step 3: Commit**

```bash
git add services/api-service/tests/conftest.py services/api-service/tests/integration/__init__.py
git commit -m "test(slice-1): add testcontainers conftest for postgres + orthanc"
```

### Task F2: Health integration test

**Files:**
- Create: `services/api-service/tests/integration/test_health.py`

- [ ] **Step 1: Write test**

```python
async def test_health_with_real_services(api_client):
    response = await api_client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["orthanc_reachable"] is True
    assert body["db_reachable"] is True
```

- [ ] **Step 2: Run, expect PASS**

```bash
cd services/api-service
uv run pytest tests/integration/test_health.py -v
```
Expected: PASS (testcontainers will pull images on first run; allow ~2 min).

- [ ] **Step 3: Commit**

```bash
git add services/api-service/tests/integration/test_health.py
git commit -m "test(slice-1): add /health integration test"
```

### Task F3: Upload + studies + audit + preview integration tests

**Files:**
- Create: `services/api-service/tests/integration/test_upload_flow.py`
- Create: `services/api-service/tests/integration/test_studies_flow.py`
- Create: `services/api-service/tests/integration/test_audit_flow.py`
- Create: `services/api-service/tests/integration/test_preview_flow.py`

- [ ] **Step 1: `test_upload_flow.py`**

```python
from tests.fixtures.synthetic_dicom import (
    make_dicom_missing_modality,
    make_synthetic_mr_dicom_bytes,
)


async def test_upload_happy_path(api_client, db_session):
    raw = make_synthetic_mr_dicom_bytes()
    response = await api_client.post(
        "/api/dicom/upload", files={"file": ("test.dcm", raw, "application/dicom")}
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] == "uploaded"
    assert body["orthanc_instance_id"]
    assert len(body["checksum_sha256"]) == 64

    # Audit row exists with success
    audit = await api_client.get("/api/audit/events")
    assert audit.status_code == 200
    items = audit.json()["items"]
    assert any(i["status"] == "success" for i in items)


async def test_upload_garbage_returns_400(api_client):
    response = await api_client.post(
        "/api/dicom/upload",
        files={"file": ("nope.txt", b"hello world", "text/plain")},
    )
    assert response.status_code == 400
    body = response.json()
    assert body["code"] == "invalid_dicom"
    assert isinstance(body["detail"], str)


async def test_upload_missing_modality_returns_400(api_client):
    raw = make_dicom_missing_modality()
    response = await api_client.post(
        "/api/dicom/upload", files={"file": ("nm.dcm", raw, "application/dicom")}
    )
    assert response.status_code == 400
    assert response.json()["code"] == "missing_required_tag"


async def test_failure_writes_audit_row(api_client):
    await api_client.post(
        "/api/dicom/upload", files={"file": ("nope.txt", b"x", "text/plain")}
    )
    audit = await api_client.get("/api/audit/events?status=failure")
    assert audit.json()["total"] == 1
```

- [ ] **Step 2: `test_studies_flow.py`**

```python
from tests.fixtures.synthetic_dicom import make_synthetic_mr_dicom_bytes


async def test_studies_list_after_upload(api_client):
    raw = make_synthetic_mr_dicom_bytes()
    upload = await api_client.post(
        "/api/dicom/upload", files={"file": ("a.dcm", raw, "application/dicom")}
    )
    study_uid = upload.json()["study_instance_uid"]

    resp = await api_client.get("/api/studies")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] >= 1
    uids = [s["study_instance_uid"] for s in body["items"]]
    assert study_uid in uids


async def test_study_detail_returns_series(api_client):
    raw = make_synthetic_mr_dicom_bytes()
    upload = await api_client.post(
        "/api/dicom/upload", files={"file": ("a.dcm", raw, "application/dicom")}
    )
    study_uid = upload.json()["study_instance_uid"]

    resp = await api_client.get(f"/api/studies/{study_uid}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["study_instance_uid"] == study_uid
    assert len(body["series"]) == 1
    series_uid = body["series"][0]["series_instance_uid"]
    assert series_uid


async def test_series_instances_listed(api_client):
    raw = make_synthetic_mr_dicom_bytes()
    upload = await api_client.post(
        "/api/dicom/upload", files={"file": ("a.dcm", raw, "application/dicom")}
    )
    study_uid = upload.json()["study_instance_uid"]
    detail = await api_client.get(f"/api/studies/{study_uid}")
    series_uid = detail.json()["series"][0]["series_instance_uid"]

    resp = await api_client.get(f"/api/series/{series_uid}/instances")
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) == 1
    assert items[0]["sop_instance_uid"]
```

- [ ] **Step 3: `test_audit_flow.py`**

```python
from tests.fixtures.synthetic_dicom import make_synthetic_mr_dicom_bytes


async def test_audit_orders_newest_first(api_client):
    for _ in range(3):
        await api_client.post(
            "/api/dicom/upload",
            files={
                "file": (
                    "a.dcm",
                    make_synthetic_mr_dicom_bytes(),
                    "application/dicom",
                )
            },
        )
    resp = await api_client.get("/api/audit/events")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 3
    times = [i["created_at"] for i in body["items"]]
    assert times == sorted(times, reverse=True)


async def test_audit_filter_by_status(api_client):
    await api_client.post(
        "/api/dicom/upload",
        files={
            "file": ("a.dcm", make_synthetic_mr_dicom_bytes(), "application/dicom")
        },
    )
    await api_client.post(
        "/api/dicom/upload", files={"file": ("b.txt", b"x", "text/plain")}
    )
    success = await api_client.get("/api/audit/events?status=success")
    failure = await api_client.get("/api/audit/events?status=failure")
    assert success.json()["total"] == 1
    assert failure.json()["total"] == 1
```

- [ ] **Step 4: `test_preview_flow.py`**

```python
from tests.fixtures.synthetic_dicom import make_synthetic_mr_dicom_bytes


async def test_preview_returns_png(api_client):
    upload = await api_client.post(
        "/api/dicom/upload",
        files={
            "file": ("a.dcm", make_synthetic_mr_dicom_bytes(), "application/dicom")
        },
    )
    instance_id = upload.json()["orthanc_instance_id"]
    resp = await api_client.get(f"/api/instances/{instance_id}/preview.png")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("image/")
    assert len(resp.content) > 0


async def test_preview_404_for_unknown(api_client):
    resp = await api_client.get("/api/instances/does-not-exist/preview.png")
    assert resp.status_code == 404
```

- [ ] **Step 5: Run all integration tests**

```bash
uv run pytest tests/integration/ -v
```
Expected: all pass. Total integration runtime should be < 90s on a developer laptop.

- [ ] **Step 6: Commit**

```bash
git add services/api-service/tests/integration/
git commit -m "test(slice-1): add integration tests for upload, studies, audit, preview"
```

### Task F4: api-service Dockerfile

**Files:**
- Create: `services/api-service/Dockerfile`

- [ ] **Step 1: Write Dockerfile**

```dockerfile
FROM ghcr.io/astral-sh/uv:0.5-python3.12-bookworm-slim AS builder

WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

FROM python:3.12-slim-bookworm

WORKDIR /app
COPY --from=builder /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:${PATH}"

COPY app ./app
COPY alembic.ini ./

ENV PYTHONUNBUFFERED=1

EXPOSE 8000

CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
```

- [ ] **Step 2: Build it**

```bash
cd services/api-service
docker build -t neuroscan/api-service:dev .
```

- [ ] **Step 3: Commit**

```bash
git add services/api-service/Dockerfile
git commit -m "feat(slice-1): add api-service Dockerfile (multi-stage with uv)"
```

---

## Phase G — Web viewer (React)

### Task G1: Vite scaffold + tooling

**Files:**
- Create: `apps/web-viewer/package.json`
- Create: `apps/web-viewer/tsconfig.json`
- Create: `apps/web-viewer/tsconfig.node.json`
- Create: `apps/web-viewer/vite.config.ts`
- Create: `apps/web-viewer/index.html`

- [ ] **Step 1: `package.json`**

```json
{
  "name": "neuroscan-web-viewer",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc -b && vite build",
    "preview": "vite preview --host 0.0.0.0",
    "lint": "eslint src --ext .ts,.tsx",
    "typecheck": "tsc --noEmit"
  },
  "dependencies": {
    "@tanstack/react-query": "^5.59.0",
    "react": "^18.3.1",
    "react-dom": "^18.3.1",
    "react-router-dom": "^6.27.0"
  },
  "devDependencies": {
    "@types/react": "^18.3.12",
    "@types/react-dom": "^18.3.1",
    "@typescript-eslint/eslint-plugin": "^8.13.0",
    "@typescript-eslint/parser": "^8.13.0",
    "@vitejs/plugin-react": "^4.3.3",
    "eslint": "^9.14.0",
    "eslint-plugin-react-hooks": "^5.0.0",
    "typescript": "^5.6.3",
    "vite": "^5.4.10"
  }
}
```

- [ ] **Step 2: `tsconfig.json`**

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "lib": ["ES2022", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "moduleResolution": "bundler",
    "jsx": "react-jsx",
    "strict": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "noFallthroughCasesInSwitch": true,
    "esModuleInterop": true,
    "isolatedModules": true,
    "resolveJsonModule": true,
    "skipLibCheck": true,
    "forceConsistentCasingInFileNames": true,
    "allowImportingTsExtensions": true,
    "noEmit": true,
    "useDefineForClassFields": true,
    "types": ["vite/client"]
  },
  "include": ["src"],
  "references": [{ "path": "./tsconfig.node.json" }]
}
```

- [ ] **Step 3: `tsconfig.node.json`**

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "lib": ["ES2023"],
    "module": "ESNext",
    "moduleResolution": "bundler",
    "skipLibCheck": true,
    "allowSyntheticDefaultImports": true,
    "strict": true,
    "noEmit": true
  },
  "include": ["vite.config.ts"]
}
```

- [ ] **Step 4: `vite.config.ts`**

```typescript
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: { host: true, port: 5173 },
  preview: { host: true, port: 5173 },
});
```

- [ ] **Step 5: `index.html`**

```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>NeuroScan Workstation</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

- [ ] **Step 6: Install + verify**

```bash
cd apps/web-viewer
npm install
npm run typecheck
```
Expected: no errors (the project doesn't have source yet, but typecheck will succeed on empty `src/`).

- [ ] **Step 7: Commit**

```bash
git add apps/web-viewer/package.json apps/web-viewer/package-lock.json apps/web-viewer/tsconfig.json apps/web-viewer/tsconfig.node.json apps/web-viewer/vite.config.ts apps/web-viewer/index.html
git commit -m "feat(slice-1): scaffold web-viewer Vite + TS + React + Query"
```

### Task G2: Types + API client

**Files:**
- Create: `apps/web-viewer/src/types/index.ts`
- Create: `apps/web-viewer/src/api/client.ts`
- Create: `apps/web-viewer/src/api/studies.ts`
- Create: `apps/web-viewer/src/api/dicom.ts`
- Create: `apps/web-viewer/src/api/audit.ts`

- [ ] **Step 1: `src/types/index.ts`**

```typescript
export interface Study {
  orthanc_study_id: string;
  study_instance_uid: string;
  patient_id: string | null;
  modality: string | null;
  study_date: string | null;
  study_description: string | null;
  series_count: number;
  instance_count: number;
}

export interface Series {
  orthanc_series_id: string;
  series_instance_uid: string;
  series_description: string | null;
  modality: string | null;
  series_number: number | null;
  instance_count: number;
}

export interface StudyDetail extends Study {
  series: Series[];
}

export interface Instance {
  orthanc_instance_id: string;
  sop_instance_uid: string;
  instance_number: number | null;
  rows: number | null;
  columns: number | null;
}

export interface Paginated<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}

export interface UploadResult {
  status: string;
  study_instance_uid: string;
  series_instance_uid: string;
  sop_instance_uid: string;
  orthanc_instance_id: string;
  checksum_sha256: string;
}

export interface ApiError {
  detail: string;
  code?: string;
}

export interface AuditEvent {
  event_id: string;
  event_type: string;
  status: "success" | "failure";
  message: string | null;
  actor: string;
  study_instance_uid: string | null;
  series_instance_uid: string | null;
  sop_instance_uid: string | null;
  orthanc_instance_id: string | null;
  checksum_sha256: string | null;
  created_at: string;
}
```

- [ ] **Step 2: `src/api/client.ts`**

```typescript
const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export class ApiClientError extends Error {
  constructor(
    public status: number,
    public code: string | undefined,
    message: string
  ) {
    super(message);
  }
}

async function parseError(response: Response): Promise<ApiClientError> {
  let code: string | undefined;
  let detail = response.statusText;
  try {
    const body = await response.json();
    if (typeof body.detail === "string") detail = body.detail;
    if (typeof body.code === "string") code = body.code;
  } catch {
    // non-JSON body; keep statusText
  }
  return new ApiClientError(response.status, code, detail);
}

export async function apiGet<T>(path: string): Promise<T> {
  const response = await fetch(`${BASE_URL}${path}`);
  if (!response.ok) throw await parseError(response);
  return response.json() as Promise<T>;
}

export async function apiUpload<T>(path: string, file: File): Promise<T> {
  const fd = new FormData();
  fd.append("file", file);
  const response = await fetch(`${BASE_URL}${path}`, {
    method: "POST",
    body: fd,
  });
  if (!response.ok) throw await parseError(response);
  return response.json() as Promise<T>;
}

export function previewUrl(orthancInstanceId: string): string {
  return `${BASE_URL}/api/instances/${orthancInstanceId}/preview.png`;
}
```

- [ ] **Step 3: `src/api/studies.ts`**

```typescript
import { apiGet } from "./client";
import type { Instance, Paginated, Study, StudyDetail } from "../types";

export const studiesApi = {
  list: (limit = 50, offset = 0) =>
    apiGet<Paginated<Study>>(`/api/studies?limit=${limit}&offset=${offset}`),
  detail: (studyInstanceUid: string) =>
    apiGet<StudyDetail>(`/api/studies/${encodeURIComponent(studyInstanceUid)}`),
  seriesInstances: (seriesInstanceUid: string) =>
    apiGet<{ items: Instance[] }>(
      `/api/series/${encodeURIComponent(seriesInstanceUid)}/instances`
    ),
};
```

- [ ] **Step 4: `src/api/dicom.ts`**

```typescript
import { apiUpload } from "./client";
import type { UploadResult } from "../types";

export const dicomApi = {
  upload: (file: File) => apiUpload<UploadResult>("/api/dicom/upload", file),
};
```

- [ ] **Step 5: `src/api/audit.ts`**

```typescript
import { apiGet } from "./client";
import type { AuditEvent, Paginated } from "../types";

export const auditApi = {
  list: (params: { limit?: number; eventType?: string; status?: string } = {}) => {
    const q = new URLSearchParams();
    q.set("limit", String(params.limit ?? 100));
    if (params.eventType) q.set("event_type", params.eventType);
    if (params.status) q.set("status", params.status);
    return apiGet<Paginated<AuditEvent>>(`/api/audit/events?${q.toString()}`);
  },
};
```

- [ ] **Step 6: Commit**

```bash
git add apps/web-viewer/src/types/ apps/web-viewer/src/api/
git commit -m "feat(slice-1): add web-viewer types and API client wrappers"
```

### Task G3: Routes, app shell, and pages

**Files:**
- Create: `apps/web-viewer/src/main.tsx`
- Create: `apps/web-viewer/src/App.tsx`
- Create: `apps/web-viewer/src/routes.tsx`
- Create: `apps/web-viewer/src/components/Nav.tsx`
- Create: `apps/web-viewer/src/components/Nav.module.css`
- Create: `apps/web-viewer/src/pages/StudyListPage.tsx`
- Create: `apps/web-viewer/src/pages/StudyDetailPage.tsx`
- Create: `apps/web-viewer/src/pages/UploadPage.tsx`
- Create: `apps/web-viewer/src/pages/AuditPage.tsx`
- Create: `apps/web-viewer/src/components/StudyTable.tsx`
- Create: `apps/web-viewer/src/components/UploadDropzone.tsx`
- Create: `apps/web-viewer/src/components/AuditTable.tsx`
- Create: `apps/web-viewer/src/components/PreviewImage.tsx`
- Create: `apps/web-viewer/src/styles/global.css`

- [ ] **Step 1: `src/main.tsx`**

```typescript
import React from "react";
import ReactDOM from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter } from "react-router-dom";
import App from "./App";
import "./styles/global.css";

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: 1, refetchOnWindowFocus: false } },
});

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </QueryClientProvider>
  </React.StrictMode>
);
```

- [ ] **Step 2: `src/App.tsx`**

```typescript
import Routes from "./routes";
import Nav from "./components/Nav";

export default function App() {
  return (
    <div>
      <Nav />
      <main style={{ maxWidth: 1200, margin: "0 auto", padding: "1.5rem" }}>
        <Routes />
      </main>
    </div>
  );
}
```

- [ ] **Step 3: `src/routes.tsx`**

```typescript
import { Navigate, Route, Routes as RouterRoutes } from "react-router-dom";
import StudyListPage from "./pages/StudyListPage";
import StudyDetailPage from "./pages/StudyDetailPage";
import UploadPage from "./pages/UploadPage";
import AuditPage from "./pages/AuditPage";

export default function Routes() {
  return (
    <RouterRoutes>
      <Route path="/" element={<Navigate to="/studies" replace />} />
      <Route path="/studies" element={<StudyListPage />} />
      <Route path="/studies/:studyInstanceUid" element={<StudyDetailPage />} />
      <Route path="/upload" element={<UploadPage />} />
      <Route path="/audit" element={<AuditPage />} />
    </RouterRoutes>
  );
}
```

- [ ] **Step 4: `src/styles/global.css`**

```css
* { box-sizing: border-box; }

body {
  margin: 0;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  background: #f5f6f8;
  color: #1f2330;
}

a { color: #2360d8; }

table { border-collapse: collapse; width: 100%; }
th, td { padding: 0.5rem 0.75rem; text-align: left; border-bottom: 1px solid #e3e5ec; }
th { background: #ebedf2; font-weight: 600; }
tr:hover { background: #f8f9fb; cursor: pointer; }

button {
  font: inherit;
  padding: 0.5rem 0.9rem;
  border: 1px solid #c9ccd5;
  background: white;
  border-radius: 4px;
  cursor: pointer;
}
button:hover { background: #f0f1f5; }
```

- [ ] **Step 5: `src/components/Nav.module.css`**

```css
.nav {
  background: white;
  border-bottom: 1px solid #e3e5ec;
  padding: 0.75rem 1.5rem;
  display: flex;
  gap: 1.5rem;
  align-items: center;
}
.brand { font-weight: 700; }
.link { text-decoration: none; color: #1f2330; padding: 0.25rem 0.5rem; border-radius: 4px; }
.link:hover { background: #ebedf2; }
.active { background: #d9e3f8; color: #103080; }
```

- [ ] **Step 6: `src/components/Nav.tsx`**

```typescript
import { NavLink } from "react-router-dom";
import styles from "./Nav.module.css";

export default function Nav() {
  return (
    <nav className={styles.nav}>
      <span className={styles.brand}>NeuroScan</span>
      <NavLink to="/studies" className={({ isActive }) => `${styles.link} ${isActive ? styles.active : ""}`}>Studies</NavLink>
      <NavLink to="/upload" className={({ isActive }) => `${styles.link} ${isActive ? styles.active : ""}`}>Upload</NavLink>
      <NavLink to="/audit" className={({ isActive }) => `${styles.link} ${isActive ? styles.active : ""}`}>Audit</NavLink>
    </nav>
  );
}
```

- [ ] **Step 7: `src/components/StudyTable.tsx`**

```typescript
import { Link } from "react-router-dom";
import type { Study } from "../types";

export default function StudyTable({ items }: { items: Study[] }) {
  if (items.length === 0) {
    return (
      <p>
        No studies yet. <Link to="/upload">Upload one</Link>.
      </p>
    );
  }
  return (
    <table>
      <thead>
        <tr>
          <th>Study Date</th>
          <th>Patient ID</th>
          <th>Modality</th>
          <th>Description</th>
          <th>Series</th>
          <th>Instances</th>
        </tr>
      </thead>
      <tbody>
        {items.map((s) => (
          <tr
            key={s.orthanc_study_id}
            onClick={() => {
              window.location.href = `/studies/${encodeURIComponent(s.study_instance_uid)}`;
            }}
          >
            <td>{s.study_date ?? "-"}</td>
            <td>{s.patient_id ?? "-"}</td>
            <td>{s.modality ?? "-"}</td>
            <td>{s.study_description ?? "-"}</td>
            <td>{s.series_count}</td>
            <td>{s.instance_count}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
```

- [ ] **Step 8: `src/pages/StudyListPage.tsx`**

```typescript
import { useQuery } from "@tanstack/react-query";
import { studiesApi } from "../api/studies";
import StudyTable from "../components/StudyTable";

export default function StudyListPage() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["studies"],
    queryFn: () => studiesApi.list(),
  });
  if (isLoading) return <p>Loading studies...</p>;
  if (error) return <p>Error loading studies: {(error as Error).message}</p>;
  return (
    <section>
      <h1>Studies</h1>
      <StudyTable items={data?.items ?? []} />
    </section>
  );
}
```

- [ ] **Step 9: `src/components/PreviewImage.tsx`**

```typescript
import { previewUrl } from "../api/client";

export default function PreviewImage({
  orthancInstanceId,
  alt,
}: {
  orthancInstanceId: string;
  alt: string;
}) {
  return (
    <img
      src={previewUrl(orthancInstanceId)}
      alt={alt}
      style={{
        maxWidth: 256,
        maxHeight: 256,
        background: "black",
        border: "1px solid #ccc",
      }}
    />
  );
}
```

- [ ] **Step 10: `src/pages/StudyDetailPage.tsx`**

```typescript
import { useParams } from "react-router-dom";
import { useQueries, useQuery } from "@tanstack/react-query";
import { studiesApi } from "../api/studies";
import PreviewImage from "../components/PreviewImage";
import type { Series } from "../types";

export default function StudyDetailPage() {
  const { studyInstanceUid = "" } = useParams();
  const { data: study, isLoading, error } = useQuery({
    queryKey: ["study", studyInstanceUid],
    queryFn: () => studiesApi.detail(studyInstanceUid),
    enabled: !!studyInstanceUid,
  });

  const seriesQueries = useQueries({
    queries: (study?.series ?? []).map((s: Series) => ({
      queryKey: ["series-instances", s.series_instance_uid],
      queryFn: () => studiesApi.seriesInstances(s.series_instance_uid),
    })),
  });

  if (isLoading) return <p>Loading...</p>;
  if (error) return <p>Error: {(error as Error).message}</p>;
  if (!study) return null;

  return (
    <section>
      <h1>Study {study.study_description ?? study.study_instance_uid}</h1>
      <p>
        Patient: {study.patient_id ?? "-"} · Modality: {study.modality ?? "-"} · Date:{" "}
        {study.study_date ?? "-"}
      </p>

      {study.series.map((s, idx) => {
        const instances = seriesQueries[idx]?.data?.items ?? [];
        return (
          <div key={s.series_instance_uid} style={{ marginTop: "1.5rem" }}>
            <h2>
              Series {s.series_number ?? "?"} — {s.series_description ?? s.series_instance_uid}
            </h2>
            <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
              {instances.map((i) => (
                <PreviewImage
                  key={i.orthanc_instance_id}
                  orthancInstanceId={i.orthanc_instance_id}
                  alt={`Instance ${i.instance_number ?? i.sop_instance_uid}`}
                />
              ))}
            </div>
          </div>
        );
      })}
    </section>
  );
}
```

- [ ] **Step 11: `src/components/UploadDropzone.tsx`**

```typescript
import { useState } from "react";

export default function UploadDropzone({
  onFile,
  disabled,
}: {
  onFile: (file: File) => void;
  disabled?: boolean;
}) {
  const [over, setOver] = useState(false);

  return (
    <div
      data-testid="dropzone"
      onDragOver={(e) => {
        e.preventDefault();
        setOver(true);
      }}
      onDragLeave={() => setOver(false)}
      onDrop={(e) => {
        e.preventDefault();
        setOver(false);
        const file = e.dataTransfer.files?.[0];
        if (file) onFile(file);
      }}
      style={{
        border: "2px dashed #c9ccd5",
        background: over ? "#eef3ff" : "white",
        borderRadius: 8,
        padding: "2rem",
        textAlign: "center",
        opacity: disabled ? 0.5 : 1,
        pointerEvents: disabled ? "none" : "auto",
      }}
    >
      <p>Drop a DICOM file here or:</p>
      <input
        type="file"
        accept=".dcm,application/dicom,application/octet-stream"
        onChange={(e) => {
          const f = e.target.files?.[0];
          if (f) onFile(f);
        }}
      />
    </div>
  );
}
```

- [ ] **Step 12: `src/pages/UploadPage.tsx`**

```typescript
import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { dicomApi } from "../api/dicom";
import UploadDropzone from "../components/UploadDropzone";
import { ApiClientError } from "../api/client";
import type { UploadResult } from "../types";

export default function UploadPage() {
  const queryClient = useQueryClient();
  const [result, setResult] = useState<UploadResult | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: (file: File) => dicomApi.upload(file),
    onSuccess: (data) => {
      setResult(data);
      setErrorMsg(null);
      queryClient.invalidateQueries({ queryKey: ["studies"] });
    },
    onError: (e: unknown) => {
      setResult(null);
      if (e instanceof ApiClientError) {
        setErrorMsg(`${e.code ?? "error"}: ${e.message}`);
      } else {
        setErrorMsg(String(e));
      }
    },
  });

  return (
    <section>
      <h1>Upload DICOM</h1>
      <UploadDropzone
        onFile={(f) => mutation.mutate(f)}
        disabled={mutation.isPending}
      />
      {mutation.isPending && <p>Uploading...</p>}
      {result && (
        <div data-testid="upload-success" style={{ marginTop: "1rem", color: "#0a6b1f" }}>
          <p>Uploaded successfully.</p>
          <ul>
            <li>Study UID: {result.study_instance_uid}</li>
            <li>Series UID: {result.series_instance_uid}</li>
            <li>SOP UID: {result.sop_instance_uid}</li>
            <li>Checksum: {result.checksum_sha256}</li>
          </ul>
          <Link to={`/studies/${encodeURIComponent(result.study_instance_uid)}`}>
            Open study
          </Link>
        </div>
      )}
      {errorMsg && (
        <p data-testid="upload-error" style={{ color: "#a4282b" }}>{errorMsg}</p>
      )}
    </section>
  );
}
```

- [ ] **Step 13: `src/components/AuditTable.tsx`**

```typescript
import type { AuditEvent } from "../types";

export default function AuditTable({ items }: { items: AuditEvent[] }) {
  if (items.length === 0) return <p>No events yet.</p>;
  return (
    <table>
      <thead>
        <tr>
          <th>Time</th>
          <th>Type</th>
          <th>Status</th>
          <th>Study UID</th>
          <th>Message</th>
        </tr>
      </thead>
      <tbody>
        {items.map((e) => (
          <tr key={e.event_id}>
            <td>{new Date(e.created_at).toLocaleString()}</td>
            <td>{e.event_type}</td>
            <td style={{ color: e.status === "success" ? "#0a6b1f" : "#a4282b" }}>
              {e.status}
            </td>
            <td>{e.study_instance_uid ?? "-"}</td>
            <td>{e.message ?? "-"}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
```

- [ ] **Step 14: `src/pages/AuditPage.tsx`**

```typescript
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { auditApi } from "../api/audit";
import AuditTable from "../components/AuditTable";

export default function AuditPage() {
  const [statusFilter, setStatusFilter] = useState<string>("");
  const { data, isLoading, error } = useQuery({
    queryKey: ["audit", statusFilter],
    queryFn: () => auditApi.list({ status: statusFilter || undefined }),
  });
  return (
    <section>
      <h1>Audit Log</h1>
      <label>
        Status:{" "}
        <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
          <option value="">All</option>
          <option value="success">Success</option>
          <option value="failure">Failure</option>
        </select>
      </label>
      {isLoading ? (
        <p>Loading...</p>
      ) : error ? (
        <p>Error: {(error as Error).message}</p>
      ) : (
        <AuditTable items={data?.items ?? []} />
      )}
    </section>
  );
}
```

- [ ] **Step 15: Verify build + typecheck**

```bash
cd apps/web-viewer
npm run typecheck
npm run build
```
Expected: both succeed; `dist/` contains built assets.

- [ ] **Step 16: Smoke test against running api-service**

In a separate shell, with infra up:
```bash
cd infra && docker compose up -d
cd ../services/api-service && uv run alembic upgrade head && uv run uvicorn app.main:app --port 8000 &
cd ../../apps/web-viewer && npm run dev
```
Open http://localhost:5173. Navigate the four pages. Drop a synthetic DICOM (use `scripts/generate-synthetic-dicom.py` from Task H1, or generate one ad-hoc with `uv run python -c "from tests.fixtures.synthetic_dicom import make_synthetic_mr_dicom_bytes; open('/tmp/x.dcm','wb').write(make_synthetic_mr_dicom_bytes())"`).

Verify: upload succeeds, study list updates, study detail renders preview image, audit page shows the event.

Tear down servers when done. Tear down compose: `docker compose down`.

- [ ] **Step 17: Commit**

```bash
git add apps/web-viewer/src/
git commit -m "feat(slice-1): add web-viewer pages, components, and routing"
```

### Task G4: web-viewer Dockerfile + nginx config

**Files:**
- Create: `apps/web-viewer/Dockerfile`
- Create: `apps/web-viewer/nginx.conf`

- [ ] **Step 1: `Dockerfile`**

```dockerfile
FROM node:20-alpine AS builder
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
ARG VITE_API_BASE_URL=http://localhost:8000
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
RUN npm run build

FROM nginx:1.27-alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
```

- [ ] **Step 2: `nginx.conf`**

```nginx
server {
  listen 80;
  server_name _;
  root /usr/share/nginx/html;
  index index.html;

  location / {
    try_files $uri $uri/ /index.html;
  }
}
```

- [ ] **Step 3: Build**

```bash
cd apps/web-viewer
docker build -t neuroscan/web-viewer:dev --build-arg VITE_API_BASE_URL=http://localhost:8000 .
```

- [ ] **Step 4: Commit**

```bash
git add apps/web-viewer/Dockerfile apps/web-viewer/nginx.conf
git commit -m "feat(slice-1): add web-viewer Dockerfile (nginx-served prod build)"
```

---

## Phase H — Tie services into compose, scripts, E2E

### Task H1: Generator script + TCIA download script

**Files:**
- Create: `scripts/generate-synthetic-dicom.py`
- Create: `scripts/download-sample-tcia.sh`

- [ ] **Step 1: `scripts/generate-synthetic-dicom.py`**

```python
#!/usr/bin/env python3
"""Generate a synthetic MR DICOM file at the given path.

Usage:
    uv run --directory services/api-service python ../../scripts/generate-synthetic-dicom.py /tmp/x.dcm
"""

from __future__ import annotations

import sys
from pathlib import Path

# This script is intended to be run via `uv run --directory services/api-service`,
# which makes the api-service venv (with pydicom and the test fixtures) importable.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "services" / "api-service"))

from tests.fixtures.synthetic_dicom import make_synthetic_mr_dicom_bytes  # noqa: E402


def main() -> None:
    if len(sys.argv) != 2:
        print("Usage: generate-synthetic-dicom.py OUTPUT_PATH", file=sys.stderr)
        sys.exit(2)
    out = Path(sys.argv[1])
    out.write_bytes(make_synthetic_mr_dicom_bytes())
    print(f"Wrote {out} ({out.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: `scripts/download-sample-tcia.sh`**

```bash
#!/usr/bin/env bash
# Downloads a small public MR series from TCIA into data/sample-dicom/tcia-brain-mr/.
#
# This script is for manual demos and screenshots. It is NOT used by tests or CI.
# Tests use the synthetic generator at scripts/generate-synthetic-dicom.py.
#
# Reference dataset: TCGA-GBM (a public glioblastoma cohort).
# https://www.cancerimagingarchive.net/collection/tcga-gbm/
#
# Update the SERIES_INSTANCE_UID below to point at any public MR series. The
# WADO endpoint is the standard NBIA WADO interface.

set -euo pipefail

DEST="$(cd "$(dirname "$0")/.." && pwd)/data/sample-dicom/tcia-brain-mr"
mkdir -p "$DEST"

# Replace with the SeriesInstanceUID you want to download. Pick one from
# https://services.cancerimagingarchive.net/services/v4/TCIA/query/getSeries
# for a public collection.
SERIES_INSTANCE_UID="${TCIA_SERIES_UID:-1.3.6.1.4.1.14519.5.2.1.4591.4001.124543141213723121925723796837}"

WADO_URL="https://services.cancerimagingarchive.net/services/v4/TCIA/query/getImage?SeriesInstanceUID=${SERIES_INSTANCE_UID}"

echo "Downloading $SERIES_INSTANCE_UID -> $DEST/series.zip"
curl -L -o "$DEST/series.zip" "$WADO_URL"

echo "Unzipping..."
unzip -o "$DEST/series.zip" -d "$DEST"
rm "$DEST/series.zip"

echo "Done. DICOM files in $DEST"
```

Make it executable:
```bash
chmod +x scripts/download-sample-tcia.sh
```

- [ ] **Step 3: Smoke test the synthetic generator**

```bash
mkdir -p /tmp/neuroscan && uv run --directory services/api-service python scripts/generate-synthetic-dicom.py /tmp/neuroscan/x.dcm
```
Expected: prints `Wrote /tmp/neuroscan/x.dcm (NN bytes)`.

- [ ] **Step 4: Commit**

```bash
git add scripts/
git commit -m "feat(slice-1): add synthetic DICOM generator and TCIA download script"
```

### Task H2: Add api-service + web-viewer to docker-compose

**Files:**
- Modify: `infra/docker-compose.yml`

- [ ] **Step 1: Append two services**

Add to the `services:` block:

```yaml
  api-service:
    build:
      context: ../services/api-service
      dockerfile: Dockerfile
    image: neuroscan/api-service:dev
    restart: unless-stopped
    depends_on:
      postgres:
        condition: service_healthy
      orthanc:
        condition: service_healthy
    environment:
      DATABASE_URL: postgresql+psycopg://${POSTGRES_USER:-neuroscan}:${POSTGRES_PASSWORD:-neuroscan}@postgres:5432/${POSTGRES_DB:-neuroscan}
      ORTHANC_URL: http://orthanc:8042
      ORTHANC_USER: orthanc
      ORTHANC_PASSWORD: orthanc
      LOG_LEVEL: INFO
    ports:
      - "8000:8000"
    healthcheck:
      test: ["CMD-SHELL", "python -c 'import urllib.request,sys;sys.exit(0 if urllib.request.urlopen(\"http://localhost:8000/health\",timeout=2).status==200 else 1)'"]
      interval: 10s
      timeout: 5s
      retries: 6

  web-viewer:
    build:
      context: ../apps/web-viewer
      dockerfile: Dockerfile
      args:
        VITE_API_BASE_URL: http://localhost:8000
    image: neuroscan/web-viewer:dev
    restart: unless-stopped
    depends_on:
      api-service:
        condition: service_started
    ports:
      - "5173:80"
```

- [ ] **Step 2: Bring it all up**

```bash
cd infra
docker compose down
docker compose up -d --build
docker compose ps
```
Expected: all four services running, postgres + orthanc + api-service `healthy`. Visit http://localhost:5173.

- [ ] **Step 3: Manual smoke**

Generate a DICOM and upload via UI:
```bash
uv run --directory services/api-service python scripts/generate-synthetic-dicom.py /tmp/x.dcm
```
Drag `/tmp/x.dcm` into the upload page, verify success, navigate to Studies, click in, see the preview. Check the audit page.

Tear down: `docker compose down`.

- [ ] **Step 4: Commit**

```bash
git add infra/docker-compose.yml
git commit -m "feat(slice-1): wire api-service and web-viewer into docker-compose"
```

### Task H3: Playwright E2E

**Files:**
- Create: `tests/e2e/package.json`
- Create: `tests/e2e/playwright.config.ts`
- Create: `tests/e2e/upload-flow.spec.ts`

- [ ] **Step 1: `tests/e2e/package.json`**

```json
{
  "name": "neuroscan-e2e",
  "private": true,
  "type": "module",
  "scripts": {
    "test": "playwright test",
    "install-browsers": "playwright install --with-deps chromium"
  },
  "devDependencies": {
    "@playwright/test": "^1.48.0"
  }
}
```

- [ ] **Step 2: `tests/e2e/playwright.config.ts`**

```typescript
import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: ".",
  timeout: 60_000,
  fullyParallel: false,
  retries: 1,
  use: {
    baseURL: process.env.BASE_URL ?? "http://localhost:5173",
    trace: "on-first-retry",
  },
  projects: [{ name: "chromium", use: { browserName: "chromium" } }],
});
```

- [ ] **Step 3: `tests/e2e/upload-flow.spec.ts`**

```typescript
import { test, expect } from "@playwright/test";
import { execSync } from "node:child_process";
import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

test("upload a synthetic DICOM and see it in the study list", async ({ page }) => {
  const dir = mkdtempSync(join(tmpdir(), "neuroscan-"));
  const dicomPath = join(dir, "x.dcm");
  execSync(
    `uv run --directory services/api-service python scripts/generate-synthetic-dicom.py "${dicomPath}"`,
    { stdio: "inherit", cwd: process.cwd().replace(/\/tests\/e2e$/, "") }
  );

  await page.goto("/upload");
  await page.locator('input[type="file"]').setInputFiles(dicomPath);
  await expect(page.getByTestId("upload-success")).toBeVisible({ timeout: 15_000 });

  await page.goto("/studies");
  const firstRow = page.locator("tbody tr").first();
  await expect(firstRow).toBeVisible();
  await firstRow.click();

  const img = page.locator("img").first();
  await expect(img).toBeVisible();
  const naturalWidth = await img.evaluate((el) => (el as HTMLImageElement).naturalWidth);
  expect(naturalWidth).toBeGreaterThan(0);

  await page.goto("/audit");
  await expect(page.getByText("dicom_uploaded")).toBeVisible();
});
```

- [ ] **Step 4: Install + run**

```bash
cd tests/e2e
npm install
npm run install-browsers
# Bring up the stack first
(cd ../../infra && docker compose up -d --build)
npm test
(cd ../../infra && docker compose down)
```
Expected: 1 test passed.

- [ ] **Step 5: Commit**

```bash
git add tests/e2e/package.json tests/e2e/package-lock.json tests/e2e/playwright.config.ts tests/e2e/upload-flow.spec.ts
git commit -m "test(slice-1): add Playwright E2E for upload→list→preview→audit"
```

---

## Phase I — CI

### Task I1: GitHub Actions workflow

**Files:**
- Create: `.github/workflows/ci.yml`

- [ ] **Step 1: Write workflow**

```yaml
name: CI

on:
  pull_request:
  push:
    branches: [main, "slice-*"]

jobs:
  python:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: services/api-service
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v3
        with:
          enable-cache: true
      - name: Install
        run: uv sync --frozen
      - name: Lint
        run: |
          uv run ruff check .
          uv run ruff format --check .
      - name: Test
        run: uv run pytest -q
        env:
          TESTCONTAINERS_RYUK_DISABLED: "true"

  web:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: apps/web-viewer
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: "20"
          cache: "npm"
          cache-dependency-path: apps/web-viewer/package-lock.json
      - run: npm ci
      - run: npm run typecheck
      - run: npm run build

  e2e:
    runs-on: ubuntu-latest
    needs: [python, web]
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v3
        with:
          enable-cache: true
      - name: Install api-service deps
        working-directory: services/api-service
        run: uv sync --frozen
      - uses: actions/setup-node@v4
        with:
          node-version: "20"
          cache: "npm"
          cache-dependency-path: tests/e2e/package-lock.json
      - name: Install Playwright
        working-directory: tests/e2e
        run: |
          npm ci
          npx playwright install --with-deps chromium
      - name: Bring up stack
        working-directory: infra
        run: docker compose up -d --build
      - name: Wait for api-service
        run: |
          for i in {1..30}; do
            if curl -sf http://localhost:8000/health; then break; fi
            sleep 2
          done
      - name: Run E2E
        working-directory: tests/e2e
        run: npm test
      - name: Tear down
        if: always()
        working-directory: infra
        run: docker compose down -v
```

- [ ] **Step 2: Commit**

```bash
git add .github/workflows/ci.yml
git commit -m "ci(slice-1): add GitHub Actions for python, web, and e2e jobs"
```

---

## Phase J — Docs

### Task J1: QA validation plan

**Files:**
- Create: `docs/qa-validation-plan.md`

- [ ] **Step 1: Write the QA plan**

```markdown
# QA Validation Plan — Slice 1

**Last updated:** 2026-05-05
**Slice:** 1 — Vertical spine
**Spec:** [`superpowers/specs/2026-05-05-slice-1-vertical-spine-design.md`](superpowers/specs/2026-05-05-slice-1-vertical-spine-design.md)

## Test environment

- macOS / Linux developer laptop
- Docker Desktop or compatible (Compose v2)
- Stack started via `docker compose -f infra/docker-compose.yml up -d --build`

## Test data

- Synthetic MR DICOM via `scripts/generate-synthetic-dicom.py`
- Real MR series via `scripts/download-sample-tcia.sh` (manual demo only)

## Manual test cases

### TC-01 Upload valid synthetic DICOM (happy path)

Steps:
1. Generate `/tmp/x.dcm` via the synthetic generator.
2. Open http://localhost:5173/upload.
3. Drop the file.
4. Wait for success message.
5. Navigate to /studies.
6. Click into the study.

Expected:
- Upload page shows `upload-success` panel with non-empty UIDs and 64-char checksum.
- Studies page shows a row with Modality `MR`.
- Study detail page renders at least one preview image.
- /audit shows a `dicom_uploaded` `success` row referencing the same study UID.

Pass criteria: all four expected outcomes met.

### TC-02 Upload non-DICOM file (negative)

Steps:
1. Drop `notes.txt` (any plain-text file) on /upload.

Expected:
- UI shows error with `code = invalid_dicom`.
- /audit shows a matching `dicom_uploaded` `failure` row.
- Studies list is unchanged.

### TC-03 Upload DICOM with missing Modality tag

Steps:
1. Generate via `tests/fixtures/synthetic_dicom.make_dicom_missing_modality()`.
2. Drop on /upload.

Expected:
- UI shows error with `code = missing_required_tag`.
- /audit shows failure row.

### TC-04 Orthanc service down

Steps:
1. `docker compose stop orthanc`.
2. Drop a valid DICOM.

Expected:
- UI shows error with `code = orthanc_rejected` (after retries).
- /audit shows failure row.
- /health returns 503 with `orthanc_reachable=false`.

Recovery: `docker compose start orthanc`; /health returns 200 within ~30s.

### TC-05 Postgres service down

Steps:
1. `docker compose stop postgres`.
2. Reload /studies (which doesn't need DB) → still works.
3. Reload /audit → fails.
4. Drop a valid DICOM → fails because audit write fails.

Expected:
- /audit shows error in UI.
- /health returns 503 with `db_reachable=false`.

Recovery: `docker compose start postgres`.

### TC-06 Persistence across restart

Steps:
1. Upload one DICOM.
2. `docker compose down` (without `-v`).
3. `docker compose up -d`.
4. Visit /studies and /audit.

Expected:
- Study still listed.
- Audit row still present.

### TC-07 Browser refresh during upload

Steps:
1. Drop a large synthetic DICOM (generate one with `rows=1024, columns=1024`).
2. Refresh the page mid-upload.

Expected:
- No partial study appears in /studies after Orthanc settles.
- A `failure` audit row may or may not appear depending on where the request was interrupted; either is acceptable.

## Known limitations (slice 1)

- No authentication
- No de-identification scanning
- No window/level controls (preview is fixed)
- No MinIO / signed URL flow
- No Prometheus / Grafana metrics
```

- [ ] **Step 2: Commit**

```bash
git add docs/qa-validation-plan.md
git commit -m "docs(slice-1): add QA validation plan with manual test cases"
```

### Task J2: Update README with quickstart, update status & roadmap

**Files:**
- Modify: `README.md`
- Modify: `docs/status.md`
- Modify: `docs/roadmap.md`

- [ ] **Step 1: Update `README.md` Quickstart section**

Replace the current Quickstart section with:

```markdown
## Quickstart

Prereqs: Docker Desktop, Python 3.12 + `uv`, Node 20+.

```bash
git clone <repo>
cd NeuroScan
cp .env.example .env

# Bring up the local stack
docker compose -f infra/docker-compose.yml up -d --build

# Visit
#   http://localhost:5173        web viewer
#   http://localhost:8000/docs   API docs
#   http://localhost:8042        Orthanc UI (orthanc/orthanc)

# Generate a synthetic DICOM and upload it via the UI
uv run --directory services/api-service python scripts/generate-synthetic-dicom.py /tmp/x.dcm
```

Tests:

```bash
# api-service unit + integration
cd services/api-service && uv run pytest

# web-viewer typecheck + build
cd apps/web-viewer && npm run typecheck && npm run build

# Playwright E2E (stack must be up)
cd tests/e2e && npm test
```

For the manual QA checklist, see [`docs/qa-validation-plan.md`](docs/qa-validation-plan.md).
```

- [ ] **Step 2: Update `docs/status.md`**

Set Current slice section to "Slice 1 — implementation complete" once all tasks pass. Update What's done and What's next accordingly. Add an entry to the decisions log noting completion.

```markdown
## Current slice

**Slice 1 — Vertical spine.** Implementation complete. CI green.

Spec: [`superpowers/specs/2026-05-05-slice-1-vertical-spine-design.md`](./superpowers/specs/2026-05-05-slice-1-vertical-spine-design.md)
Plan: [`superpowers/plans/2026-05-05-slice-1-vertical-spine.md`](./superpowers/plans/2026-05-05-slice-1-vertical-spine.md)

## What's done

- Repo initialized with project context docs (overview, roadmap, status, original PRD)
- Slice 1 design spec written, reviewed, approved
- Slice 1 implementation plan written
- Slice 1 implementation complete:
  - Docker Compose stack (postgres, orthanc, api-service, web-viewer)
  - FastAPI api-service: health, dicom upload, studies, audit, preview proxy
  - SQLAlchemy + Alembic with `audit_events` table
  - OrthancClient with retries (respx-tested)
  - DICOM validation, metadata extraction, checksum, upload orchestrator
  - React web viewer: studies list, study detail with previews, upload, audit
  - Synthetic DICOM fixture + TCIA download script
  - Unit, integration (testcontainers), and E2E (Playwright) tests
  - GitHub Actions CI (python, web, e2e jobs)
  - QA validation plan

## What's next

1. Brainstorm Slice 2 — Qt desktop viewer.

## Open questions / blockers

None.

## Recent decisions log

- 2026-05-05: Locked decomposition strategy: vertical-slice first (Option A).
- 2026-05-05: Locked AD-1 through AD-9 cross-slice decisions.
- 2026-05-05: Locked slice 1 scope: includes audit + checksum + CI + Playwright; defers auth, MinIO, de-id, metrics.
- 2026-05-05: Slice 1 implementation complete and merged.
```

- [ ] **Step 3: Update `docs/roadmap.md`**

Change Slice 1's status from `planned` to `done` and add the link to the plan:

| 1 | Vertical spine: ... | **done** | [spec](./superpowers/specs/2026-05-05-slice-1-vertical-spine-design.md) · [plan](./superpowers/plans/2026-05-05-slice-1-vertical-spine.md) | Completed 2026-05-05 |

- [ ] **Step 4: Commit**

```bash
git add README.md docs/status.md docs/roadmap.md
git commit -m "docs(slice-1): update README quickstart and mark slice 1 done"
```

---

## Phase K — Final verification

### Task K1: Full Definition of Done check

- [ ] **Step 1: From a clean checkout, verify everything**

```bash
git status  # clean working tree
docker compose -f infra/docker-compose.yml down -v  # ensure clean state
docker compose -f infra/docker-compose.yml up -d --build
sleep 60
curl -sf http://localhost:8000/health | grep '"status":"ok"'
```

- [ ] **Step 2: Run all tests**

```bash
(cd services/api-service && uv run pytest -q)
(cd apps/web-viewer && npm run typecheck && npm run build)
(cd tests/e2e && npm test)
```
Expected: every test passes.

- [ ] **Step 3: Walk the spec's Definition of Done (§15) item by item**

Confirm each of the 11 items in the slice 1 spec's Definition of Done is met. If any item fails, return to the corresponding phase above and fix.

- [ ] **Step 4: Tear down**

```bash
docker compose -f infra/docker-compose.yml down
```

- [ ] **Step 5: Push the branch**

```bash
git push -u origin slice-1-vertical-spine
```

(PR creation is optional and at the user's discretion; the brainstorming → spec → plan → implementation cycle is complete at this point.)

---

## Notes for the implementing engineer

- **TDD discipline matters.** Every backend module in Phase D was built test-first. If you skip the failing-test step, you're working blind.
- **One commit per task minimum.** Some tasks contain a single commit; others contain 2–3. Don't squash unrelated changes into one commit. The user explicitly asked for small, incremental, logical commits.
- **Run lint locally before committing.** `cd services/api-service && uv run ruff check . && uv run ruff format .` to keep CI green.
- **If a step fails, stop and debug.** Don't power through. Especially: testcontainers can be flaky on first run because of image pulls. Re-run after the image is cached.
- **Don't add features that aren't in this plan.** If you find yourself wanting to add (auth, MinIO, metrics, fancy viewer), stop — that's a future slice. Add a note to `docs/status.md` "Open questions" if you think it's urgent.
