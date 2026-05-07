# Slice 4 — MinIO Object Storage Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add MinIO as a content-addressed sidecar to Orthanc — every DICOM upload and reconstruction output is also written to a SHA-256-keyed S3 bucket, with a `storage_objects` Postgres table tracking metadata and a presigned-URL endpoint surfaced through the audit page.

**Architecture:** boto3 client targeting `endpoint_url=http://minio:9000` from inside api-service. New `services/storage.py` does the tee + DB write. Slice 1's `upload_orchestrator` and Slice 3's `job_runner` get one extra step each. Best-effort: MinIO down → upload still succeeds, audit row records `success_minio_skipped`. Web audit page gains a "Share link" button looking up storage_objects by SHA-256.

**Tech Stack:** boto3, botocore, moto[s3] (unit-test mocking), MinIO (Docker), testcontainers (generic `DockerContainer` — no `[minio]` extra needed). Existing api-service stack unchanged.

**Spec:** [`docs/superpowers/specs/2026-05-07-slice-4-minio-storage-design.md`](../specs/2026-05-07-slice-4-minio-storage-design.md)

**Branch:** `slice-4-minio-storage` (off `main`, with Slices 1–3 already merged)

**Commit policy (from user):** Small, incremental, logically-isolated commits. Each task in this plan produces 1–2 commits. Never combine unrelated changes. Never amend.

**TDD scope:** Pure-logic modules (`s3_client`, `storage` service) are written test-first using moto. Routes are smoke-verified via integration tests. The orchestrator + job_runner modifications in Phase G are minimal additions verified by the existing Slice 1+3 integration tests AND the new Slice 4 ones.

---

## File structure

Created in this slice:

```text
services/api-service/
├── app/
│   ├── clients/s3.py                                    # NEW
│   ├── services/storage.py                              # NEW
│   ├── models/storage.py                                # NEW
│   ├── schemas/storage.py                               # NEW
│   ├── routes/storage.py                                # NEW
│   └── alembic/versions/003_storage_objects.py          # NEW
└── tests/
    ├── unit/
    │   ├── test_s3_client.py                            # NEW
    │   └── test_storage_service.py                      # NEW
    └── integration/test_storage_flow.py                 # NEW

apps/web-viewer/src/api/storage.ts                       # NEW
```

Modified in this slice:

```text
services/api-service/pyproject.toml                      # add boto3, moto[s3]
services/api-service/uv.lock                             # regenerated
services/api-service/app/main.py                         # register storage router + ensure_bucket on startup
services/api-service/app/models/__init__.py              # export StorageObject
services/api-service/app/config.py                       # add MINIO_* settings
services/api-service/app/schemas/audit.py                # widen status enum
services/api-service/app/services/upload.py              # add tee step
services/api-service/app/services/reconstruction/job_runner.py  # add tee step
services/api-service/app/routes/health.py               # add minio_reachable
services/api-service/tests/conftest.py                   # add MinIO testcontainer

infra/docker-compose.yml                                 # add minio service
.env.example                                             # add MINIO_*

apps/web-viewer/src/types/index.ts                       # add StorageObject type
apps/web-viewer/src/components/AuditTable.tsx            # add Share link column
apps/web-viewer/src/pages/AuditPage.tsx                  # pass storage map

docs/qa-validation-plan.md                               # add TC-09
docs/status.md                                           # mark slice 4 done at end
docs/roadmap.md                                          # mark slice 4 done at end
README.md                                                # MinIO console URL in quickstart
```

Untouched: `apps/desktop-viewer/`, `tests/e2e/`, `scripts/`, all Slice 1/2/3 unit test files.

---

## Phase A — Tooling

### Task A1: Add `boto3` and `moto` to api-service pyproject

**Files:**
- Modify: `services/api-service/pyproject.toml`
- Modify: `services/api-service/uv.lock` (regenerated)

- [ ] **Step 1: Update dependencies**

In `services/api-service/pyproject.toml`, append to the runtime `[project].dependencies` array:

```toml
    "boto3>=1.35",
```

And to the `[dependency-groups].dev` array:

```toml
    "moto[s3]>=5.0",
```

- [ ] **Step 2: Re-lock**

```bash
cd services/api-service
uv sync
```

Expected: `uv.lock` updated; boto3 + botocore + moto wheels download (~25 MB).

- [ ] **Step 3: Smoke verify imports**

```bash
uv run python -c "import boto3; from moto import mock_aws; print('OK', boto3.__version__)"
```

Expected: `OK 1.35.x` (or higher).

- [ ] **Step 4: Run existing tests to confirm no regression**

```bash
DOCKER_HOST=unix://$HOME/.orbstack/run/docker.sock uv run pytest tests/unit/ -q
```

Expected: 56 passed.

- [ ] **Step 5: Commit**

```bash
cd /Users/harshilvyas/Documents/Github\ Repos/NeuroScan
git add services/api-service/pyproject.toml services/api-service/uv.lock
git commit -m "feat(slice-4): add boto3 and moto deps to api-service"
```

---

## Phase B — Config + S3 client

### Task B1: Add MinIO settings to `config.py`

**Files:**
- Modify: `services/api-service/app/config.py`

- [ ] **Step 1: Add MinIO fields to `Settings`**

Open `services/api-service/app/config.py`. The `Settings` class currently has `database_url`, `orthanc_url`, `orthanc_user`, `orthanc_password`, `log_level`, `api_port`. Add five new fields after `orthanc_password`:

```python
    minio_endpoint: str = "http://localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_bucket: str = "neuroscan"
    minio_region: str = "us-east-1"
```

The full updated `Settings` class should look like:

```python
class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    api_port: int = 8000
    database_url: str = Field(
        default="postgresql+psycopg://neuroscan:neuroscan@localhost:5432/neuroscan",
    )
    orthanc_url: str = "http://localhost:8042"
    orthanc_user: str = "orthanc"
    orthanc_password: str = "orthanc"
    minio_endpoint: str = "http://localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_bucket: str = "neuroscan"
    minio_region: str = "us-east-1"
    log_level: str = "INFO"
```

- [ ] **Step 2: Smoke verify**

```bash
cd services/api-service
uv run python -c "
from app.config import get_settings
get_settings.cache_clear()
s = get_settings()
print(s.minio_endpoint, s.minio_bucket)
"
```

Expected: `http://localhost:9000 neuroscan`.

- [ ] **Step 3: Commit**

```bash
git add services/api-service/app/config.py
git commit -m "feat(slice-4): add MINIO_* settings to api-service config"
```

---

### Task B2: TDD `clients/s3.py`

**Files:**
- Create: `services/api-service/app/clients/s3.py`
- Create: `services/api-service/tests/unit/test_s3_client.py`

- [ ] **Step 1: Write the failing tests**

`services/api-service/tests/unit/test_s3_client.py`:

```python
import boto3
import pytest
from moto import mock_aws

from app.clients.s3 import S3Client, S3Error


@pytest.fixture
def s3_client():
    """A real S3Client wired against moto's in-memory AWS mock."""
    with mock_aws():
        # moto needs a region but doesn't actually validate creds
        client = S3Client(
            endpoint_url=None,  # let boto3 pick the moto-mocked AWS endpoint
            access_key="testing",
            secret_key="testing",
            bucket="test-bucket",
            region="us-east-1",
        )
        yield client


def test_ensure_bucket_creates_when_absent(s3_client):
    s3_client.ensure_bucket()
    # Verify via raw boto3
    raw = boto3.client("s3", region_name="us-east-1")
    buckets = [b["Name"] for b in raw.list_buckets()["Buckets"]]
    assert "test-bucket" in buckets


def test_ensure_bucket_is_idempotent(s3_client):
    s3_client.ensure_bucket()
    s3_client.ensure_bucket()  # second call should not raise
    raw = boto3.client("s3", region_name="us-east-1")
    buckets = [b["Name"] for b in raw.list_buckets()["Buckets"]]
    assert buckets.count("test-bucket") == 1


def test_put_object_writes_bytes(s3_client):
    s3_client.ensure_bucket()
    s3_client.put_object(
        key="dicom/abc123.dcm",
        body=b"fake-dicom-bytes",
        content_type="application/dicom",
    )
    head = s3_client.head_object("dicom/abc123.dcm")
    assert head["ContentType"] == "application/dicom"
    assert head["ContentLength"] == len(b"fake-dicom-bytes")


def test_is_reachable_returns_true_when_bucket_exists(s3_client):
    s3_client.ensure_bucket()
    assert s3_client.is_reachable() is True


def test_generate_presigned_get_url_returns_signed_url(s3_client):
    s3_client.ensure_bucket()
    s3_client.put_object(key="dicom/x.dcm", body=b"data")
    url, expires_at = s3_client.generate_presigned_get_url(
        "dicom/x.dcm", expires_in=300
    )
    assert "X-Amz-Signature" in url
    assert "X-Amz-Expires=300" in url
    # expires_at should be ~5 minutes in the future
    from datetime import datetime, timezone
    delta = (expires_at - datetime.now(timezone.utc)).total_seconds()
    assert 290 <= delta <= 310


def test_put_object_raises_s3error_on_missing_bucket(s3_client):
    # Don't ensure_bucket; put should fail
    with pytest.raises(S3Error):
        s3_client.put_object(key="x", body=b"data")
```

- [ ] **Step 2: Run, expect FAIL (ImportError)**

```bash
cd services/api-service
uv run pytest tests/unit/test_s3_client.py -v
```

Expected: ImportError on `app.clients.s3`.

- [ ] **Step 3: Write `app/clients/s3.py`**

```python
"""Sync S3 client backed by boto3, configured for MinIO endpoint by default.

Migrating to AWS S3 (Slice 10+) requires only setting endpoint_url=None and
swapping the credentials to AWS-issued ones. All other code stays the same.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

import boto3
from botocore.client import Config
from botocore.exceptions import BotoCoreError, ClientError

logger = logging.getLogger(__name__)


class S3Error(Exception):
    """Raised when an S3 operation fails."""


class S3Client:
    def __init__(
        self,
        *,
        endpoint_url: str | None,
        access_key: str,
        secret_key: str,
        bucket: str,
        region: str = "us-east-1",
    ) -> None:
        self._bucket = bucket
        self._region = region
        self._client = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region,
            config=Config(
                signature_version="s3v4",
                retries={"max_attempts": 3},
                s3={"addressing_style": "path"},
            ),
        )

    @property
    def bucket(self) -> str:
        return self._bucket

    def ensure_bucket(self) -> None:
        try:
            self._client.head_bucket(Bucket=self._bucket)
            return
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code")
            if code in ("404", "NoSuchBucket"):
                self._client.create_bucket(Bucket=self._bucket)
                return
            raise S3Error(f"head_bucket failed: {exc}") from exc

    def put_object(
        self,
        *,
        key: str,
        body: bytes,
        content_type: str = "application/dicom",
    ) -> None:
        try:
            self._client.put_object(
                Bucket=self._bucket,
                Key=key,
                Body=body,
                ContentType=content_type,
            )
        except (BotoCoreError, ClientError) as exc:
            raise S3Error(f"put_object {key} failed: {exc}") from exc

    def head_object(self, key: str) -> dict:
        try:
            return self._client.head_object(Bucket=self._bucket, Key=key)
        except ClientError as exc:
            raise S3Error(f"head_object {key} failed: {exc}") from exc

    def is_reachable(self) -> bool:
        try:
            self._client.list_buckets()
            return True
        except (BotoCoreError, ClientError):
            return False

    def generate_presigned_get_url(
        self, key: str, *, expires_in: int = 300
    ) -> tuple[str, datetime]:
        try:
            url = self._client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self._bucket, "Key": key},
                ExpiresIn=expires_in,
            )
        except (BotoCoreError, ClientError) as exc:
            raise S3Error(f"presign {key} failed: {exc}") from exc
        return url, datetime.now(timezone.utc) + timedelta(seconds=expires_in)
```

- [ ] **Step 4: Run, expect PASS**

```bash
uv run pytest tests/unit/test_s3_client.py -v
```

Expected: 6 passed.

- [ ] **Step 5: Run all unit tests**

```bash
DOCKER_HOST=unix://$HOME/.orbstack/run/docker.sock uv run pytest tests/unit/ -q
```

Expected: 56 + 6 = 62 passed.

- [ ] **Step 6: Commit**

```bash
cd /Users/harshilvyas/Documents/Github\ Repos/NeuroScan
git add services/api-service/app/clients/s3.py services/api-service/tests/unit/test_s3_client.py
git commit -m "feat(slice-4): add S3Client (boto3 + path-style + retries) with moto tests"
```

---

## Phase C — Data model

### Task C1: `StorageObject` model + Alembic migration 003

**Files:**
- Create: `services/api-service/app/models/storage.py`
- Modify: `services/api-service/app/models/__init__.py`
- Create: `services/api-service/app/alembic/versions/003_storage_objects.py`

- [ ] **Step 1: Write `app/models/storage.py`**

```python
from datetime import datetime, timezone

from sqlalchemy import (
    BigInteger,
    DateTime,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class StorageObject(Base):
    __tablename__ = "storage_objects"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer(), "sqlite"),
        primary_key=True,
        autoincrement=True,
    )
    bucket: Mapped[str] = mapped_column(String(64), nullable=False)
    object_key: Mapped[str] = mapped_column(String(256), nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    content_type: Mapped[str] = mapped_column(String(64), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        UniqueConstraint("bucket", "object_key", name="uq_storage_bucket_key"),
        Index("idx_storage_sha256", sha256),
        Index("idx_storage_source", source),
        Index("idx_storage_created_at", created_at.desc()),
    )
```

- [ ] **Step 2: Update `app/models/__init__.py`**

Replace contents with:

```python
from app.models.audit import AuditEvent
from app.models.reconstruction import ReconstructionJob
from app.models.storage import StorageObject

__all__ = ["AuditEvent", "ReconstructionJob", "StorageObject"]
```

- [ ] **Step 3: Generate the migration**

```bash
export PATH="$HOME/.orbstack/bin:$PATH"
cd /Users/harshilvyas/Documents/Github\ Repos/NeuroScan/infra
docker compose up -d postgres
for i in $(seq 1 20); do
  if docker compose ps --format json postgres | grep -q '"Health":"healthy"'; then break; fi
  sleep 2
done
cd ../services/api-service
DATABASE_URL=postgresql+psycopg://neuroscan:neuroscan@localhost:5432/neuroscan \
  uv run alembic upgrade head  # ensure 001 + 002 are applied
DATABASE_URL=postgresql+psycopg://neuroscan:neuroscan@localhost:5432/neuroscan \
  uv run alembic revision --autogenerate -m "storage_objects"
```

Expected: a new file `app/alembic/versions/<hash>_storage_objects.py` is created.

Rename:
```bash
mv app/alembic/versions/*_storage_objects.py app/alembic/versions/003_storage_objects.py
```

Edit the new file:
- Set `revision: str = "003"`
- Set `down_revision: str | None = "002"`

The body should call `op.create_table('storage_objects', ...)` with all 8 columns plus the `UniqueConstraint` and three `op.create_index` calls.

- [ ] **Step 4: Apply and verify**

```bash
DATABASE_URL=postgresql+psycopg://neuroscan:neuroscan@localhost:5432/neuroscan \
  uv run alembic upgrade head
```

Expected: log line `Running upgrade 002 -> 003, storage_objects`.

Verify the table:
```bash
docker compose -f /Users/harshilvyas/Documents/Github\ Repos/NeuroScan/infra/docker-compose.yml \
  exec -T postgres psql -U neuroscan -c "\d storage_objects"
```

Expected: 8 columns + 3 indexes (`idx_storage_sha256`, `idx_storage_source`, `idx_storage_created_at`) + unique on `(bucket, object_key)` + PK on `id`.

- [ ] **Step 5: Tear down**

```bash
cd /Users/harshilvyas/Documents/Github\ Repos/NeuroScan/infra
docker compose down  # NOT -v
```

- [ ] **Step 6: Run unit tests**

```bash
cd /Users/harshilvyas/Documents/Github\ Repos/NeuroScan/services/api-service
DOCKER_HOST=unix://$HOME/.orbstack/run/docker.sock uv run pytest tests/unit/ -q
```

Expected: 62 passed.

- [ ] **Step 7: Commit**

```bash
cd /Users/harshilvyas/Documents/Github\ Repos/NeuroScan
git add services/api-service/app/models/ services/api-service/app/alembic/versions/003_storage_objects.py
git commit -m "feat(slice-4): add StorageObject model and alembic migration 003"
```

---

## Phase D — Storage service (TDD)

### Task D1: TDD `services/storage.py`

**Files:**
- Create: `services/api-service/app/services/storage.py`
- Create: `services/api-service/tests/unit/test_storage_service.py`

- [ ] **Step 1: Write the failing tests**

`services/api-service/tests/unit/test_storage_service.py`:

```python
import pytest
from moto import mock_aws
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.clients.s3 import S3Client
from app.db import Base
from app.models.storage import StorageObject
from app.services.storage import (
    KEY_PREFIX_DICOM,
    KEY_PREFIX_RECONSTRUCTION,
    StorageObjectNotFoundError,
    mint_presigned_url,
    object_key_for,
    tee_to_s3,
)


@pytest.fixture
def session():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    with session_factory() as s:
        yield s


@pytest.fixture
def s3_client():
    with mock_aws():
        client = S3Client(
            endpoint_url=None,
            access_key="testing",
            secret_key="testing",
            bucket="test-bucket",
        )
        client.ensure_bucket()
        yield client


def test_object_key_for_dicom():
    key = object_key_for(source="dicom_upload", sha256="abc123")
    assert key == "dicom/abc123.dcm"
    assert key.startswith(KEY_PREFIX_DICOM)


def test_object_key_for_reconstruction():
    key = object_key_for(source="reconstruction_output", sha256="def456")
    assert key == "reconstructed/def456.dcm"
    assert key.startswith(KEY_PREFIX_RECONSTRUCTION)


def test_tee_to_s3_writes_row_on_success(session, s3_client):
    body = b"fake-dicom"
    sha = "a" * 64
    obj = tee_to_s3(
        s3=s3_client,
        session=session,
        body=body,
        sha256=sha,
        source="dicom_upload",
    )
    assert obj is not None
    assert obj.bucket == "test-bucket"
    assert obj.object_key == f"dicom/{sha}.dcm"
    assert obj.sha256 == sha
    assert obj.size_bytes == len(body)
    assert obj.source == "dicom_upload"
    assert obj.id is not None


def test_tee_to_s3_returns_none_on_s3_failure(session):
    """If S3 raises, no row is written and we return None (best-effort)."""
    from unittest.mock import MagicMock

    from app.clients.s3 import S3Error

    fake_s3 = MagicMock()
    fake_s3.bucket = "test-bucket"
    fake_s3.put_object.side_effect = S3Error("simulated failure")

    obj = tee_to_s3(
        s3=fake_s3,
        session=session,
        body=b"data",
        sha256="x" * 64,
        source="dicom_upload",
    )
    assert obj is None
    assert session.query(StorageObject).count() == 0


def test_tee_to_s3_idempotent_on_duplicate(session, s3_client):
    """Two writes of identical content do not produce two rows."""
    body = b"same"
    sha = "b" * 64
    obj1 = tee_to_s3(
        s3=s3_client,
        session=session,
        body=body,
        sha256=sha,
        source="dicom_upload",
    )
    obj2 = tee_to_s3(
        s3=s3_client,
        session=session,
        body=body,
        sha256=sha,
        source="dicom_upload",
    )
    assert obj1 is not None
    assert obj2 is not None
    # Same row returned (or at least same id)
    assert obj1.id == obj2.id
    assert session.query(StorageObject).count() == 1


def test_mint_presigned_url_returns_url_and_expiry(session, s3_client):
    body = b"hello"
    sha = "c" * 64
    obj = tee_to_s3(
        s3=s3_client,
        session=session,
        body=body,
        sha256=sha,
        source="dicom_upload",
    )
    url, expires_at = mint_presigned_url(
        s3=s3_client,
        session=session,
        object_id=obj.id,
        expires_in=300,
    )
    assert "X-Amz-Signature" in url
    from datetime import datetime, timezone
    delta = (expires_at - datetime.now(timezone.utc)).total_seconds()
    assert 290 <= delta <= 310


def test_mint_presigned_url_404s_for_unknown_id(session, s3_client):
    with pytest.raises(StorageObjectNotFoundError):
        mint_presigned_url(
            s3=s3_client,
            session=session,
            object_id=99999,
            expires_in=300,
        )
```

- [ ] **Step 2: Run, expect FAIL**

```bash
uv run pytest tests/unit/test_storage_service.py -v
```

- [ ] **Step 3: Write `app/services/storage.py`**

```python
"""Tee uploads to S3 and look up storage objects.

Best-effort: tee_to_s3 returns None on S3 failure so the caller can record
a 'success_minio_skipped' audit row instead of failing the whole request.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.clients.s3 import S3Client, S3Error
from app.models.storage import StorageObject

logger = logging.getLogger(__name__)

KEY_PREFIX_DICOM = "dicom/"
KEY_PREFIX_RECONSTRUCTION = "reconstructed/"

StorageSource = Literal["dicom_upload", "reconstruction_output"]


class StorageObjectNotFoundError(Exception):
    """Raised when a storage_object id does not exist."""


def object_key_for(*, source: StorageSource, sha256: str) -> str:
    if source == "dicom_upload":
        return f"{KEY_PREFIX_DICOM}{sha256}.dcm"
    if source == "reconstruction_output":
        return f"{KEY_PREFIX_RECONSTRUCTION}{sha256}.dcm"
    raise ValueError(f"Unknown source: {source}")


def tee_to_s3(
    *,
    s3: S3Client,
    session: Session,
    body: bytes,
    sha256: str,
    source: StorageSource,
    content_type: str = "application/dicom",
) -> StorageObject | None:
    """Write bytes to S3 and record a storage_objects row.

    Returns the row on success, None on S3 failure (best-effort).
    Idempotent: if a row already exists for (bucket, object_key), reuse it.
    """
    key = object_key_for(source=source, sha256=sha256)

    try:
        s3.put_object(key=key, body=body, content_type=content_type)
    except S3Error as exc:
        logger.warning("S3 tee failed for %s: %s", key, exc)
        return None

    existing = session.scalar(
        select(StorageObject).where(
            StorageObject.bucket == s3.bucket,
            StorageObject.object_key == key,
        )
    )
    if existing is not None:
        return existing

    obj = StorageObject(
        bucket=s3.bucket,
        object_key=key,
        sha256=sha256,
        content_type=content_type,
        size_bytes=len(body),
        source=source,
    )
    session.add(obj)
    session.commit()
    session.refresh(obj)
    return obj


def mint_presigned_url(
    *,
    s3: S3Client,
    session: Session,
    object_id: int,
    expires_in: int,
) -> tuple[str, datetime]:
    obj = session.get(StorageObject, object_id)
    if obj is None:
        raise StorageObjectNotFoundError(f"storage_object {object_id} not found")
    return s3.generate_presigned_get_url(obj.object_key, expires_in=expires_in)
```

- [ ] **Step 4: Run, expect PASS**

```bash
uv run pytest tests/unit/test_storage_service.py -v
```

Expected: 7 passed.

- [ ] **Step 5: Run all unit tests**

```bash
DOCKER_HOST=unix://$HOME/.orbstack/run/docker.sock uv run pytest tests/unit/ -q
```

Expected: 62 + 7 = 69 passed.

- [ ] **Step 6: Commit**

```bash
cd /Users/harshilvyas/Documents/Github\ Repos/NeuroScan
git add services/api-service/app/services/storage.py services/api-service/tests/unit/test_storage_service.py
git commit -m "feat(slice-4): add storage service (tee_to_s3 + mint_presigned_url)"
```

---

## Phase E — Schemas + routes

### Task E1: `schemas/storage.py` + widen audit status enum

**Files:**
- Create: `services/api-service/app/schemas/storage.py`
- Modify: `services/api-service/app/schemas/audit.py`

- [ ] **Step 1: Write `schemas/storage.py`**

```python
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


class StorageObjectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    bucket: str
    object_key: str
    sha256: str
    content_type: str
    size_bytes: int
    source: Literal["dicom_upload", "reconstruction_output"]
    created_at: datetime


class StorageObjectList(BaseModel):
    items: list[StorageObjectOut]
    total: int
    limit: int
    offset: int


class PresignedUrlOut(BaseModel):
    url: str
    expires_at: datetime
```

- [ ] **Step 2: Modify `schemas/audit.py` to widen the status enum**

Find the `AuditEventOut` class. Change:

```python
    status: Literal["success", "failure"]
```

to:

```python
    status: Literal["success", "failure", "success_minio_skipped"]
```

- [ ] **Step 3: Smoke verify**

```bash
cd services/api-service
uv run python -c "
from app.schemas.storage import StorageObjectOut, StorageObjectList, PresignedUrlOut
from app.schemas.audit import AuditEventOut
print('OK', AuditEventOut.model_fields['status'].annotation)
"
```

Expected: `OK typing.Literal['success', 'failure', 'success_minio_skipped']`.

- [ ] **Step 4: Run unit tests**

```bash
DOCKER_HOST=unix://$HOME/.orbstack/run/docker.sock uv run pytest tests/unit/ -q
```

Expected: 69 passed.

- [ ] **Step 5: Commit**

```bash
git add services/api-service/app/schemas/storage.py services/api-service/app/schemas/audit.py
git commit -m "feat(slice-4): add storage DTOs and widen audit status enum"
```

---

### Task E2: `routes/storage.py` + register in main + ensure_bucket on startup + minio_reachable in health

**Files:**
- Create: `services/api-service/app/routes/storage.py`
- Modify: `services/api-service/app/main.py`
- Modify: `services/api-service/app/routes/health.py`

- [ ] **Step 1: Write `routes/storage.py`**

```python
"""Storage object endpoints: list, detail, presigned URL."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.clients.s3 import S3Client
from app.config import Settings, get_settings
from app.db import get_session
from app.models.storage import StorageObject
from app.schemas.storage import (
    PresignedUrlOut,
    StorageObjectList,
    StorageObjectOut,
)
from app.services.storage import StorageObjectNotFoundError, mint_presigned_url

router = APIRouter(prefix="/api/storage", tags=["storage"])


def get_s3_client(settings: Settings = Depends(get_settings)) -> S3Client:
    return S3Client(
        endpoint_url=settings.minio_endpoint,
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        bucket=settings.minio_bucket,
        region=settings.minio_region,
    )


@router.get("/objects", response_model=StorageObjectList)
async def list_objects(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    source: str | None = None,
    sha256: str | None = None,
    session: Session = Depends(get_session),
) -> StorageObjectList:
    stmt = select(StorageObject)
    count_stmt = select(func.count()).select_from(StorageObject)
    if source:
        stmt = stmt.where(StorageObject.source == source)
        count_stmt = count_stmt.where(StorageObject.source == source)
    if sha256:
        stmt = stmt.where(StorageObject.sha256 == sha256)
        count_stmt = count_stmt.where(StorageObject.sha256 == sha256)
    stmt = stmt.order_by(StorageObject.created_at.desc()).limit(limit).offset(offset)
    items = list(session.scalars(stmt))
    total = session.scalar(count_stmt) or 0
    return StorageObjectList(
        items=[StorageObjectOut.model_validate(i) for i in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/objects/{object_id}", response_model=StorageObjectOut)
async def get_object(
    object_id: int,
    session: Session = Depends(get_session),
) -> StorageObjectOut:
    obj = session.get(StorageObject, object_id)
    if obj is None:
        raise HTTPException(status_code=404, detail="storage_object_not_found")
    return StorageObjectOut.model_validate(obj)


@router.get("/objects/{object_id}/presigned-url", response_model=PresignedUrlOut)
async def get_presigned_url(
    object_id: int,
    expires: int = Query(300, ge=60, le=3600),
    session: Session = Depends(get_session),
    s3: S3Client = Depends(get_s3_client),
) -> PresignedUrlOut:
    try:
        url, expires_at = mint_presigned_url(
            s3=s3, session=session, object_id=object_id, expires_in=expires
        )
    except StorageObjectNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return PresignedUrlOut(url=url, expires_at=expires_at)
```

- [ ] **Step 2: Modify `app/main.py` to register storage router AND ensure_bucket on startup**

The current file imports routers from `app.routes`. Update the import to include `storage`:

```python
from app.routes import audit, dicom, health, reconstruction, storage, studies
```

Inside `create_app()`, after `app.include_router(reconstruction.router)`, add:

```python
    app.include_router(storage.router)
```

Then add a startup event hook that calls `S3Client.ensure_bucket()`. Inside `create_app()`, after the `app.exception_handler` block but before the `app.include_router` calls, add:

```python
    @app.on_event("startup")
    async def _ensure_bucket_on_startup() -> None:
        from app.clients.s3 import S3Client, S3Error
        from app.config import get_settings

        settings = get_settings()
        try:
            client = S3Client(
                endpoint_url=settings.minio_endpoint,
                access_key=settings.minio_access_key,
                secret_key=settings.minio_secret_key,
                bucket=settings.minio_bucket,
                region=settings.minio_region,
            )
            client.ensure_bucket()
        except S3Error as exc:
            # Best-effort: don't crash if MinIO is not yet up
            import logging
            logging.getLogger(__name__).warning(
                "MinIO bucket setup failed (will retry on first use): %s", exc
            )
```

- [ ] **Step 3: Modify `app/routes/health.py` to add `minio_reachable`**

The current `/health` returns `status`, `service`, `version`, `orthanc_reachable`, `db_reachable`. Add `minio_reachable`. Update the function:

```python
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app import __version__
from app.clients.orthanc import OrthancClient, OrthancError
from app.clients.s3 import S3Client
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

    minio_ok = False
    try:
        s3 = S3Client(
            endpoint_url=settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            bucket=settings.minio_bucket,
            region=settings.minio_region,
        )
        minio_ok = s3.is_reachable()
    except Exception:
        minio_ok = False

    if not (orthanc_ok and db_ok):
        status = "degraded"
        code = 503
    elif not minio_ok:
        # Orthanc + DB up, MinIO down → degraded but still 200 (best-effort sidecar)
        status = "degraded"
        code = 200
    else:
        status = "ok"
        code = 200

    return JSONResponse(
        {
            "status": status,
            "service": "api-service",
            "version": __version__,
            "orthanc_reachable": orthanc_ok,
            "db_reachable": db_ok,
            "minio_reachable": minio_ok,
        },
        status_code=code,
    )
```

- [ ] **Step 4: Smoke verify routes registered**

```bash
cd services/api-service
uv run python -c "
from app.main import app
routes = sorted({r.path for r in app.routes if hasattr(r, 'path')})
expected = [
    '/api/storage/objects',
    '/api/storage/objects/{object_id}',
    '/api/storage/objects/{object_id}/presigned-url',
]
for e in expected:
    assert e in routes, f'Missing route: {e}'
print('OK', len(routes), 'routes registered')
"
```

Expected: `OK <N> routes registered` where N >= 14.

- [ ] **Step 5: Run unit tests**

```bash
DOCKER_HOST=unix://$HOME/.orbstack/run/docker.sock uv run pytest tests/unit/ -q
```

Expected: 69 passed.

- [ ] **Step 6: Run lint**

```bash
uv run ruff check . && uv run ruff format --check .
```

If ruff reports issues, run `uv run ruff format .` and include changes in this commit.

- [ ] **Step 7: Commit**

```bash
cd /Users/harshilvyas/Documents/Github\ Repos/NeuroScan
git add services/api-service/app/routes/storage.py services/api-service/app/main.py services/api-service/app/routes/health.py
git commit -m "feat(slice-4): add /api/storage routes, bucket auto-create, minio_reachable in health"
```

---

## Phase F — Wire MinIO into compose

### Task F1: Add MinIO service + env vars

**Files:**
- Modify: `infra/docker-compose.yml`
- Modify: `.env.example`

- [ ] **Step 1: Add MinIO service to `infra/docker-compose.yml`**

In the `services:` block, add a new service entry between `orthanc` and `api-service`:

```yaml
  minio:
    image: minio/minio:RELEASE.2024-12-18T13-15-44Z
    restart: unless-stopped
    command: server /data --console-address ":9001"
    environment:
      MINIO_ROOT_USER: ${MINIO_ACCESS_KEY:-minioadmin}
      MINIO_ROOT_PASSWORD: ${MINIO_SECRET_KEY:-minioadmin}
    ports:
      - "9000:9000"
      - "9001:9001"
    volumes:
      - minio_data:/data
    healthcheck:
      test: ["CMD-SHELL", "curl -sf http://localhost:9000/minio/health/live >/dev/null || exit 1"]
      interval: 10s
      timeout: 5s
      retries: 6
```

Add `minio_data:` to the `volumes:` block at the bottom of the file:

```yaml
volumes:
  postgres_data:
  orthanc_data:
  minio_data:
```

Modify the `api-service` block to depend on MinIO and pass the env vars. Find:

```yaml
    depends_on:
      postgres:
        condition: service_healthy
      orthanc:
        condition: service_healthy
```

Change to:

```yaml
    depends_on:
      postgres:
        condition: service_healthy
      orthanc:
        condition: service_healthy
      minio:
        condition: service_healthy
```

In the `api-service` `environment:` block, add five new env vars:

```yaml
      MINIO_ENDPOINT: http://minio:9000
      MINIO_ACCESS_KEY: ${MINIO_ACCESS_KEY:-minioadmin}
      MINIO_SECRET_KEY: ${MINIO_SECRET_KEY:-minioadmin}
      MINIO_BUCKET: ${MINIO_BUCKET:-neuroscan}
      MINIO_REGION: ${MINIO_REGION:-us-east-1}
```

- [ ] **Step 2: Update `.env.example`**

Append to the file:

```env
# minio
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
MINIO_BUCKET=neuroscan
MINIO_REGION=us-east-1
```

- [ ] **Step 3: Verify compose YAML is valid**

```bash
cd /Users/harshilvyas/Documents/Github\ Repos/NeuroScan
python3 -c "
content = open('infra/docker-compose.yml').read()
assert 'minio:' in content
assert 'minio_data' in content
assert 'minio:' in content and 'minio:9000' in content
print('Structural check OK')
"
```

- [ ] **Step 4: Smoke test the stack**

```bash
export PATH="$HOME/.orbstack/bin:$PATH"
export DOCKER_HOST="unix://$HOME/.orbstack/run/docker.sock"
cd infra
docker compose down  # stop existing stack
docker compose up -d --build
sleep 30
docker compose ps
curl -sf http://localhost:9000/minio/health/live && echo "MinIO healthy"
curl -sf -u minioadmin:minioadmin http://localhost:8000/health | python3 -m json.tool
```

Expected:
- All 5 services healthy.
- MinIO health endpoint returns 200.
- `/health` returns `minio_reachable: true`.

Tear down:
```bash
docker compose down
```

- [ ] **Step 5: Commit**

```bash
cd /Users/harshilvyas/Documents/Github\ Repos/NeuroScan
git add infra/docker-compose.yml .env.example
git commit -m "feat(slice-4): add MinIO service to docker-compose with healthcheck"
```

---

## Phase G — Wire tee into existing flows

### Task G1: Modify `services/upload.py` to tee DICOMs

**Files:**
- Modify: `services/api-service/app/services/upload.py`

The orchestrator's current behavior:
1. validate
2. checksum
3. extract metadata
4. orthanc.upload_instance
5. write audit (status="success")

We add a step 4.5: tee to S3. If it fails, the audit row gets `status="success_minio_skipped"` instead of `"success"`.

- [ ] **Step 1: Read current `app/services/upload.py`**

Note the current `handle_upload()` signature and structure. The function takes `session`, `orthanc`, `dicom_bytes` and returns an `UploadResult` dataclass. We need to inject an `S3Client` parameter.

- [ ] **Step 2: Update `handle_upload()` to accept an optional `s3` parameter and tee**

Open `services/api-service/app/services/upload.py`. Find the success path — the block where `orthanc_instance_id = await orthanc.upload_instance(dicom_bytes)` succeeds and then `write_event(session, ..., status="success", ...)` is called.

Refactor `handle_upload` to accept `s3: S3Client | None = None`. After the Orthanc upload succeeds, before the audit row is written, attempt the tee:

```python
async def handle_upload(
    *,
    session: Session,
    orthanc: OrthancClient,
    dicom_bytes: bytes,
    s3: S3Client | None = None,
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

    # Tee to S3 (best-effort)
    audit_status = "success"
    audit_message: str | None = None
    if s3 is not None:
        from app.services.storage import tee_to_s3

        storage_obj = tee_to_s3(
            s3=s3,
            session=session,
            body=dicom_bytes,
            sha256=checksum,
            source="dicom_upload",
        )
        if storage_obj is None:
            audit_status = "success_minio_skipped"
            audit_message = "MinIO tee failed (see logs); DICOM still in Orthanc"

    write_event(
        session,
        event_type="dicom_uploaded",
        status=audit_status,
        message=audit_message,
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

- [ ] **Step 3: Update `routes/dicom.py` to pass an `S3Client` into `handle_upload`**

Open `services/api-service/app/routes/dicom.py`. Find the `upload_dicom` endpoint. It currently calls `handle_upload(session=session, orthanc=orthanc, dicom_bytes=data)`. Add an `s3` dependency.

Add an import:
```python
from app.routes.storage import get_s3_client
from app.clients.s3 import S3Client
```

Update the function signature and call site:

```python
@router.post(
    "/upload",
    response_model=UploadResult,
    status_code=status.HTTP_201_CREATED,
)
async def upload_dicom(
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
    orthanc: OrthancClient = Depends(get_orthanc_client),
    s3: S3Client = Depends(get_s3_client),
) -> UploadResult:
    data = await file.read()
    result = await handle_upload(
        session=session, orthanc=orthanc, dicom_bytes=data, s3=s3
    )
    return UploadResult(
        status="uploaded",
        study_instance_uid=result.study_instance_uid,
        series_instance_uid=result.series_instance_uid,
        sop_instance_uid=result.sop_instance_uid,
        orthanc_instance_id=result.orthanc_instance_id,
        checksum_sha256=result.checksum_sha256,
    )
```

- [ ] **Step 4: Verify Slice 1 unit tests still pass**

The unit test `test_upload_service.py` calls `handle_upload` without `s3`. Since `s3` is now optional with default `None`, this should still work.

```bash
cd services/api-service
DOCKER_HOST=unix://$HOME/.orbstack/run/docker.sock uv run pytest tests/unit/test_upload_service.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Run all unit tests**

```bash
DOCKER_HOST=unix://$HOME/.orbstack/run/docker.sock uv run pytest tests/unit/ -q
```

Expected: 69 passed.

- [ ] **Step 6: Commit**

```bash
cd /Users/harshilvyas/Documents/Github\ Repos/NeuroScan
git add services/api-service/app/services/upload.py services/api-service/app/routes/dicom.py
git commit -m "feat(slice-4): tee DICOM uploads to MinIO; widen audit status to success_minio_skipped"
```

---

### Task G2: Modify `reconstruction/job_runner.py` to tee reconstructed outputs

**Files:**
- Modify: `services/api-service/app/services/reconstruction/job_runner.py`

The `run_job` function currently:
1. status=running
2. load kspace
3. reconstruct
4. compute metrics (if ground truth)
5. write DICOM (image_to_mr_dicom)
6. _upload_sync to Orthanc
7. status=completed

We add step 6.5: tee to S3 with `source="reconstruction_output"`. Failure here is logged but does NOT mark the job as failed.

- [ ] **Step 1: Add S3 tee to `run_job`**

Open `services/api-service/app/services/reconstruction/job_runner.py`. The function takes `(job_id, tempfile_path, settings)`. After the line `orthanc_instance_id = _upload_sync(settings, write_result.dicom_bytes)`, add the S3 tee.

Add an import at the top:

```python
import hashlib

from app.clients.s3 import S3Client, S3Error
from app.services.storage import tee_to_s3
```

In `run_job`, after the `orthanc_instance_id = _upload_sync(...)` line and before the final `_set_status(... completed ...)` block, add:

```python
        # Tee reconstructed DICOM to MinIO (best-effort).
        recon_sha256 = hashlib.sha256(write_result.dicom_bytes).hexdigest()
        try:
            s3 = S3Client(
                endpoint_url=settings.minio_endpoint,
                access_key=settings.minio_access_key,
                secret_key=settings.minio_secret_key,
                bucket=settings.minio_bucket,
                region=settings.minio_region,
            )
            with SessionLocal() as session:
                tee_to_s3(
                    s3=s3,
                    session=session,
                    body=write_result.dicom_bytes,
                    sha256=recon_sha256,
                    source="reconstruction_output",
                )
        except (S3Error, Exception) as exc:  # noqa: BLE001
            # Best-effort: log and continue. Job stays 'completed'.
            import logging
            logging.getLogger(__name__).warning(
                "Recon S3 tee failed for job %s: %s", job_id, exc
            )
```

- [ ] **Step 2: Run unit tests to confirm no regression**

```bash
cd services/api-service
DOCKER_HOST=unix://$HOME/.orbstack/run/docker.sock uv run pytest tests/unit/ -q
```

Expected: 69 passed (the unit tests don't exercise this path).

- [ ] **Step 3: Run lint**

```bash
uv run ruff check . && uv run ruff format --check .
```

If lint fails, run `ruff format .` and include changes.

- [ ] **Step 4: Commit**

```bash
cd /Users/harshilvyas/Documents/Github\ Repos/NeuroScan
git add services/api-service/app/services/reconstruction/job_runner.py
git commit -m "feat(slice-4): tee reconstructed DICOMs to MinIO from job_runner"
```

---

## Phase H — Integration tests

### Task H1: Add MinIO testcontainer to `tests/conftest.py`

**Files:**
- Modify: `services/api-service/tests/conftest.py`

The current conftest spins up Postgres + Orthanc session-scoped containers. Add a third one for MinIO and override the api-service settings to point at it.

- [ ] **Step 1: Add MinIO fixture**

Open `services/api-service/tests/conftest.py`. Below the `orthanc_container` and `orthanc_url` fixtures, add:

```python
@pytest.fixture(scope="session")
def minio_container() -> Iterator[DockerContainer]:
    container = (
        DockerContainer("minio/minio:RELEASE.2024-12-18T13-15-44Z")
        .with_exposed_ports(9000)
        .with_env("MINIO_ROOT_USER", "minioadmin")
        .with_env("MINIO_ROOT_PASSWORD", "minioadmin")
        .with_command("server /data")
    )
    container.start()
    try:
        # Poll until /minio/health/live responds
        host = container.get_container_host_ip()
        port = container.get_exposed_port(9000)
        url = f"http://{host}:{port}"
        deadline = time.time() + 60
        while time.time() < deadline:
            try:
                r = httpx.get(f"{url}/minio/health/live", timeout=2)
                if r.status_code == 200:
                    break
            except httpx.HTTPError:
                pass
            time.sleep(0.5)
        else:
            raise RuntimeError("MinIO did not become reachable")
        yield container
    finally:
        container.stop()


@pytest.fixture(scope="session")
def minio_url(minio_container: DockerContainer) -> str:
    host = minio_container.get_container_host_ip()
    port = minio_container.get_exposed_port(9000)
    return f"http://{host}:{port}"
```

- [ ] **Step 2: Update `configure_settings` to include MinIO**

Find the `configure_settings` autouse fixture. Add `minio_url` as a dependency and set the MinIO env vars:

```python
@pytest.fixture(scope="session", autouse=True)
def configure_settings(
    database_url: str, orthanc_url: str, minio_url: str
) -> Iterator[None]:
    """Override settings via env so the FastAPI app under test sees test infra."""
    old: dict[str, str | None] = {}
    overrides = {
        "DATABASE_URL": database_url,
        "ORTHANC_URL": orthanc_url,
        "ORTHANC_USER": "orthanc",
        "ORTHANC_PASSWORD": "orthanc",
        "MINIO_ENDPOINT": minio_url,
        "MINIO_ACCESS_KEY": "minioadmin",
        "MINIO_SECRET_KEY": "minioadmin",
        "MINIO_BUCKET": "neuroscan-test",
        "MINIO_REGION": "us-east-1",
    }
    for k, v in overrides.items():
        old[k] = os.environ.get(k)
        os.environ[k] = v

    from app.config import get_settings
    get_settings.cache_clear()

    engine = create_engine(database_url)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    engine.dispose()

    # Ensure the test bucket exists
    from app.clients.s3 import S3Client
    s3 = S3Client(
        endpoint_url=minio_url,
        access_key="minioadmin",
        secret_key="minioadmin",
        bucket="neuroscan-test",
    )
    s3.ensure_bucket()

    yield

    for k, v in old.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v
    get_settings.cache_clear()
```

- [ ] **Step 3: Update integration `conftest.py` to truncate `storage_objects`**

Open `services/api-service/tests/integration/conftest.py`. Find the autouse truncation fixture. Update the TRUNCATE statement to include `storage_objects`:

```python
        conn.exec_driver_sql(
            "TRUNCATE TABLE audit_events, reconstruction_jobs, storage_objects RESTART IDENTITY"
        )
```

(Also clean the test bucket between tests — add after the TRUNCATE):

```python
    # Empty the test bucket between tests
    import boto3
    from botocore.client import Config

    s3 = boto3.client(
        "s3",
        endpoint_url=os.environ["MINIO_ENDPOINT"],
        aws_access_key_id=os.environ["MINIO_ACCESS_KEY"],
        aws_secret_access_key=os.environ["MINIO_SECRET_KEY"],
        region_name=os.environ["MINIO_REGION"],
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
    )
    bucket = os.environ["MINIO_BUCKET"]
    try:
        contents = s3.list_objects_v2(Bucket=bucket).get("Contents") or []
        for obj in contents:
            s3.delete_object(Bucket=bucket, Key=obj["Key"])
    except Exception:
        pass
```

(Add `import os` at the top of the file if not already present.)

- [ ] **Step 4: Run all integration tests to confirm no regression**

```bash
export DOCKER_HOST="unix://$HOME/.orbstack/run/docker.sock"
cd services/api-service
uv run pytest tests/integration/ -q
```

Expected: 17 passed (the existing Slice 1+3 integration tests). They run faster after the first MinIO image pull (~30s on first run).

- [ ] **Step 5: Commit**

```bash
cd /Users/harshilvyas/Documents/Github\ Repos/NeuroScan
git add services/api-service/tests/conftest.py services/api-service/tests/integration/conftest.py
git commit -m "test(slice-4): add MinIO testcontainer + bucket fixture for integration tests"
```

---

### Task H2: Write storage flow integration tests

**Files:**
- Create: `services/api-service/tests/integration/test_storage_flow.py`

- [ ] **Step 1: Write the tests**

```python
"""End-to-end MinIO storage tests against real Postgres + Orthanc + MinIO."""

import asyncio
from io import BytesIO

import httpx
import numpy as np
import pytest

from app.services.reconstruction.forward_fft import dicom_to_kspace
from tests.fixtures.synthetic_dicom import make_synthetic_mr_dicom_bytes


def _build_npz_bytes(rows: int = 64, cols: int = 64) -> bytes:
    dicom_bytes = make_synthetic_mr_dicom_bytes(rows=rows, columns=cols)
    kspace, ground_truth = dicom_to_kspace(dicom_bytes)
    buf = BytesIO()
    np.savez(buf, kspace=kspace, ground_truth_image=ground_truth)
    return buf.getvalue()


async def _wait_for_terminal(api_client, job_id, timeout_s: float = 30.0) -> dict:
    for _ in range(int(timeout_s * 5)):
        resp = await api_client.get(f"/api/reconstruction/jobs/{job_id}")
        body = resp.json()
        if body["status"] in ("completed", "failed"):
            return body
        await asyncio.sleep(0.2)
    pytest.fail(f"Job {job_id} did not reach terminal status within {timeout_s}s")


async def test_dicom_upload_creates_storage_object(api_client):
    raw = make_synthetic_mr_dicom_bytes()
    upload = await api_client.post(
        "/api/dicom/upload", files={"file": ("a.dcm", raw, "application/dicom")}
    )
    assert upload.status_code == 201, upload.text
    sha = upload.json()["checksum_sha256"]

    # storage_object should exist with matching sha256 and source
    storage = await api_client.get(f"/api/storage/objects?sha256={sha}")
    body = storage.json()
    assert body["total"] == 1
    obj = body["items"][0]
    assert obj["source"] == "dicom_upload"
    assert obj["sha256"] == sha
    assert obj["object_key"].startswith("dicom/")
    assert obj["bucket"] == "neuroscan-test"


async def test_dicom_upload_audit_status_is_success_when_minio_ok(api_client):
    raw = make_synthetic_mr_dicom_bytes()
    await api_client.post(
        "/api/dicom/upload", files={"file": ("a.dcm", raw, "application/dicom")}
    )
    audit = await api_client.get("/api/audit/events?limit=1")
    body = audit.json()
    assert body["items"][0]["status"] == "success"


async def test_reconstruction_creates_storage_object(api_client):
    npz_bytes = _build_npz_bytes()
    upload = await api_client.post(
        "/api/reconstruction/jobs",
        files={"file": ("brain.npz", npz_bytes, "application/octet-stream")},
    )
    job_id = upload.json()["job_id"]
    await _wait_for_terminal(api_client, job_id)

    storage = await api_client.get(
        "/api/storage/objects?source=reconstruction_output"
    )
    body = storage.json()
    assert body["total"] >= 1
    assert all(item["source"] == "reconstruction_output" for item in body["items"])


async def test_presigned_url_returns_original_bytes(api_client):
    raw = make_synthetic_mr_dicom_bytes()
    upload = await api_client.post(
        "/api/dicom/upload", files={"file": ("a.dcm", raw, "application/dicom")}
    )
    sha = upload.json()["checksum_sha256"]

    storage = await api_client.get(f"/api/storage/objects?sha256={sha}")
    obj_id = storage.json()["items"][0]["id"]

    presigned = await api_client.get(
        f"/api/storage/objects/{obj_id}/presigned-url?expires=300"
    )
    url = presigned.json()["url"]

    # Fetch the URL directly (NOT through api-service)
    async with httpx.AsyncClient() as client:
        r = await client.get(url)
    assert r.status_code == 200
    assert r.content == raw


async def test_health_reports_minio_reachable(api_client):
    resp = await api_client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["minio_reachable"] is True
    assert body["status"] == "ok"
```

- [ ] **Step 2: Run the tests**

```bash
cd services/api-service
export DOCKER_HOST="unix://$HOME/.orbstack/run/docker.sock"
uv run pytest tests/integration/test_storage_flow.py -v
```

Expected: 5 passed.

- [ ] **Step 3: Run all integration tests**

```bash
uv run pytest tests/integration/ -q
```

Expected: 17 + 5 = **22 passed**.

- [ ] **Step 4: Commit**

```bash
cd /Users/harshilvyas/Documents/Github\ Repos/NeuroScan
git add services/api-service/tests/integration/test_storage_flow.py
git commit -m "test(slice-4): add integration tests for MinIO tee + presigned URL"
```

---

## Phase I — Web UI

### Task I1: Types + API client

**Files:**
- Modify: `apps/web-viewer/src/types/index.ts`
- Create: `apps/web-viewer/src/api/storage.ts`

- [ ] **Step 1: Append to `apps/web-viewer/src/types/index.ts`**

```typescript
export interface StorageObject {
  id: number;
  bucket: string;
  object_key: string;
  sha256: string;
  content_type: string;
  size_bytes: number;
  source: "dicom_upload" | "reconstruction_output";
  created_at: string;
}

export interface PresignedUrl {
  url: string;
  expires_at: string;
}
```

Also widen the audit event status:

```typescript
// In the existing AuditEvent interface, change:
//   status: "success" | "failure";
// To:
//   status: "success" | "failure" | "success_minio_skipped";
```

- [ ] **Step 2: Write `apps/web-viewer/src/api/storage.ts`**

```typescript
import { apiGet } from "./client";
import type { Paginated, PresignedUrl, StorageObject } from "../types";

export const storageApi = {
  list: (params: { sha256?: string; source?: string; limit?: number } = {}) => {
    const q = new URLSearchParams();
    q.set("limit", String(params.limit ?? 50));
    if (params.sha256) q.set("sha256", params.sha256);
    if (params.source) q.set("source", params.source);
    return apiGet<Paginated<StorageObject>>(`/api/storage/objects?${q.toString()}`);
  },

  get: (id: number) => apiGet<StorageObject>(`/api/storage/objects/${id}`),

  presignedUrl: (id: number, expiresSeconds = 300) =>
    apiGet<PresignedUrl>(
      `/api/storage/objects/${id}/presigned-url?expires=${expiresSeconds}`,
    ),
};
```

- [ ] **Step 3: Typecheck**

```bash
cd apps/web-viewer
npm run typecheck
```

Expected: clean.

- [ ] **Step 4: Commit**

```bash
cd /Users/harshilvyas/Documents/Github\ Repos/NeuroScan
git add apps/web-viewer/src/types/index.ts apps/web-viewer/src/api/storage.ts
git commit -m "feat(slice-4): add storage types and API client wrapper"
```

---

### Task I2: Add "Share link" column to AuditTable

**Files:**
- Modify: `apps/web-viewer/src/components/AuditTable.tsx`
- Modify: `apps/web-viewer/src/pages/AuditPage.tsx`

- [ ] **Step 1: Update `AuditTable.tsx` to render a Share link column**

The current table has columns: Time, Type, Status, Study UID, Message. Add a sixth column: "Share". Replace the file's contents with:

```typescript
import { useQueries } from "@tanstack/react-query";
import { storageApi } from "../api/storage";
import type { AuditEvent } from "../types";

function StatusCell({ status }: { status: AuditEvent["status"] }) {
  const color =
    status === "success"
      ? "#0a6b1f"
      : status === "success_minio_skipped"
        ? "#a47900"
        : "#a4282b";
  return <span style={{ color }}>{status}</span>;
}

function ShareLinkButton({ objectId }: { objectId: number }) {
  const onClick = async () => {
    try {
      const result = await storageApi.presignedUrl(objectId, 300);
      await navigator.clipboard.writeText(result.url);
      alert(`Presigned URL copied (expires ${new Date(result.expires_at).toLocaleTimeString()})`);
    } catch (e) {
      alert(`Failed to mint URL: ${(e as Error).message}`);
    }
  };
  return (
    <button onClick={onClick} style={{ fontSize: 12 }}>
      Share link
    </button>
  );
}

export default function AuditTable({ items }: { items: AuditEvent[] }) {
  // For each row that has a checksum, look up the storage_object id
  const checksums = Array.from(
    new Set(items.map((e) => e.checksum_sha256).filter(Boolean) as string[]),
  );
  const queries = useQueries({
    queries: checksums.map((sha) => ({
      queryKey: ["storage-by-sha", sha],
      queryFn: () => storageApi.list({ sha256: sha, limit: 1 }),
      staleTime: 60_000,
    })),
  });

  const shaToObjectId: Record<string, number | null> = {};
  checksums.forEach((sha, i) => {
    const data = queries[i].data;
    shaToObjectId[sha] = data && data.items.length > 0 ? data.items[0].id : null;
  });

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
          <th>Share</th>
        </tr>
      </thead>
      <tbody>
        {items.map((e) => {
          const objectId = e.checksum_sha256
            ? shaToObjectId[e.checksum_sha256]
            : null;
          return (
            <tr key={e.event_id}>
              <td>{new Date(e.created_at).toLocaleString()}</td>
              <td>{e.event_type}</td>
              <td>
                <StatusCell status={e.status} />
              </td>
              <td>{e.study_instance_uid ?? "-"}</td>
              <td>{e.message ?? "-"}</td>
              <td>{objectId ? <ShareLinkButton objectId={objectId} /> : "-"}</td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}
```

- [ ] **Step 2: Confirm `AuditPage.tsx` doesn't need changes**

Open `apps/web-viewer/src/pages/AuditPage.tsx`. It should already pass `items={data?.items ?? []}` to `<AuditTable>`. No changes needed unless the import path or destructuring is different.

- [ ] **Step 3: Typecheck + build**

```bash
cd apps/web-viewer
npm run typecheck
npm run build
```

Expected: both clean.

- [ ] **Step 4: Commit**

```bash
cd /Users/harshilvyas/Documents/Github\ Repos/NeuroScan
git add apps/web-viewer/src/components/AuditTable.tsx
git commit -m "feat(slice-4): add Share link button to audit page rows"
```

---

## Phase J — Docs

### Task J1: README + QA TC-09

**Files:**
- Modify: `README.md`
- Modify: `docs/qa-validation-plan.md`

- [ ] **Step 1: Update README**

In the Quickstart section's URL list, add MinIO console:

Find:
```markdown
#   http://localhost:5173        web viewer
#   http://localhost:8000/docs   API docs
#   http://localhost:8042        Orthanc UI (orthanc/orthanc)
```

Add after the Orthanc line:

```markdown
#   http://localhost:9001        MinIO console (minioadmin/minioadmin)
```

In the project-demonstrates bullet list, add:

> - **Object storage with signed URLs**: MinIO sidecar persists every DICOM under a content-addressed S3 path; presigned-URL endpoint mints short-TTL share links.

- [ ] **Step 2: Add TC-09 to `docs/qa-validation-plan.md`**

Add this test case before the "## Automated tests as QA artifacts" section:

```markdown
### TC-09 MinIO sidecar + presigned URL

Steps:
1. With the stack running, upload a DICOM via the web app at /upload.
2. Open MinIO console at http://localhost:9001 (login: minioadmin / minioadmin).
3. Browse to the `neuroscan` bucket; expand the `dicom/` prefix.
4. Confirm a file is present whose name is the SHA-256 of the upload, with `.dcm` extension.
5. Open the `/audit` page in the web app; locate the row for the upload.
6. Click "Share link" — a presigned URL is copied to the clipboard, and an alert shows the expiration time.
7. Paste the URL into a new browser tab; the DICOM downloads.
8. Wait for the URL to expire (default 5 min) and try again — should return 403 SignatureDoesNotMatch.

Stop MinIO mid-test:
9. `docker compose stop minio`.
10. Upload another DICOM via the web app.
11. The upload returns 201 (status="uploaded").
12. Open `/audit` — the new row's status is `success_minio_skipped` and shows a yellow color.
13. The "Share link" button is NOT shown for this row (no storage_object exists).
14. `curl http://localhost:8000/health` reports `minio_reachable: false`, `status: "degraded"`.

Expected:
- Step 4: object exists in MinIO.
- Step 7: download succeeds.
- Step 8: download is rejected with SignatureDoesNotMatch.
- Steps 11-13: upload succeeds even with MinIO down; audit row shows the skip.
- Step 14: health endpoint reports the MinIO outage cleanly.

Pass criteria: all 4 expected outcomes met.
```

Also append to **Known limitations**:

```markdown
- MinIO storage is best-effort (sidecar to Orthanc). When MinIO is down, uploads still succeed but no `storage_object` row is created. Permanent loss of the MinIO copy is acceptable since Orthanc is the source of truth.
- Presigned URLs are read-only (GET). Direct-to-MinIO presigned PUT uploads are deferred to a future slice.
- No lifecycle policy: MinIO objects accumulate indefinitely. Cleanup is a future concern.
```

- [ ] **Step 3: Commit**

```bash
cd /Users/harshilvyas/Documents/Github\ Repos/NeuroScan
git add README.md docs/qa-validation-plan.md
git commit -m "docs(slice-4): add MinIO console URL to README and TC-09 to QA plan"
```

---

## Phase K — Wrap-up

### Task K1: Update status + roadmap, push branch

**Files:**
- Modify: `docs/status.md`
- Modify: `docs/roadmap.md`

- [ ] **Step 1: Update `docs/roadmap.md` row for slice 4**

Find:
```text
| 4 | MinIO + signed-URL upload flow + checksum-validated object storage | planned | — | Adds `storage_objects` table + minio container |
```
Replace with:
```text
| 4 | MinIO + signed-URL upload flow + checksum-validated object storage | **done** | [spec](./superpowers/specs/2026-05-07-slice-4-minio-storage-design.md) · [plan](./superpowers/plans/2026-05-07-slice-4-minio-storage.md) | Completed 2026-05-07. Sidecar to Orthanc; best-effort failure mode (see AD-S4-4). |
```

- [ ] **Step 2: Update `docs/status.md`**

Replace the **Current slice** section with:

```markdown
**Slice 4 — MinIO Object Storage + Signed URLs.** Implementation complete on `slice-4-minio-storage`. Pending merge to `main`.

Spec: [`superpowers/specs/2026-05-07-slice-4-minio-storage-design.md`](./superpowers/specs/2026-05-07-slice-4-minio-storage-design.md)
Plan: [`superpowers/plans/2026-05-07-slice-4-minio-storage.md`](./superpowers/plans/2026-05-07-slice-4-minio-storage.md)
```

In **What's done**, append:

```markdown
- Slice 4 implementation complete on `slice-4-minio-storage`:
  - `storage_objects` table (alembic migration 003)
  - `S3Client` (boto3, path-style, retries) with moto-mocked unit tests
  - `services/storage.py`: `tee_to_s3`, `mint_presigned_url`, `object_key_for`
  - `routes/storage.py`: list, detail, presigned-url
  - Orchestrator + job_runner write to MinIO after Orthanc on every upload
  - Best-effort: MinIO down → audit `status=success_minio_skipped`, upload still 201
  - `/health` reports `minio_reachable`; status downgrades to `degraded` when MinIO is down
  - Audit page gains a "Share link" button (looks up storage_object by SHA-256)
  - MinIO container in compose; `MINIO_*` env vars in .env.example
  - 13 new tests (6 unit S3Client + 7 unit storage service + 5 integration)
  - QA TC-09 + README MinIO console URL added
```

In **What's next**, replace with:

```markdown
1. Merge `slice-4-minio-storage` to `main` and push.
2. Brainstorm Slice 5 — De-identification scanner.
```

In **Recent decisions log**, append:

```markdown
- 2026-05-07: Locked AD-S4-1..10 (sidecar topology, both DICOM and reconstructed outputs tee'd, single bucket with prefixes, best-effort failure, boto3, presigned GET only, share-link button on audit page, no FK in storage_objects, audit status enum widened, bucket auto-create on startup).
- 2026-05-07: Slice 4 implementation complete.
```

Add a new **Slice 4 implementation deviations from spec/plan (record for posterity)** section — initially empty, the implementer can fill in any deviations they encounter.

- [ ] **Step 3: Verify final state**

```bash
export DOCKER_HOST="unix://$HOME/.orbstack/run/docker.sock"
cd services/api-service
uv run pytest -q  # 69 unit + 22 integration = 91 passed
uv run ruff check . && uv run ruff format --check .
cd ../../apps/web-viewer
npm run typecheck && npm run build
```

Expected: all green.

- [ ] **Step 4: Commit and push**

```bash
cd /Users/harshilvyas/Documents/Github\ Repos/NeuroScan
git add docs/status.md docs/roadmap.md
git commit -m "docs(slice-4): mark slice 4 done in status.md and roadmap.md"
git push -u origin slice-4-minio-storage
```

---

## Notes for the implementing engineer

- **Phase B/D are strict TDD.** The S3Client and storage service modules are written test-first using moto. Don't skip the failing-test step.
- **Phase G is the integration risk point.** The orchestrator + job_runner modifications are surgical; the existing tests verify they didn't break anything. If a Slice 1 or Slice 3 test fails after G1 or G2, the change to upload.py / job_runner.py is wrong — back out and re-do.
- **Slice 1 unit tests (`test_upload_service.py`) call `handle_upload(s3=None)`.** Because the parameter has a default of `None`, those tests still pass without modification. Don't update them.
- **MinIO testcontainer (Phase H1) adds ~30s to first integration run** while the image pulls. Subsequent runs are fast.
- **Don't forget `addressing_style="path"` in `S3Client`.** MinIO requires it; the spec's §14 risks call it out.
- **Best-effort means best-effort.** If MinIO is down, log a warning and continue. Do NOT raise. Do NOT mark the upload/job as failed.
- **The Share link button uses `navigator.clipboard.writeText`.** This requires a secure context (https or localhost). Localhost is fine for our demo; document if it fails in unusual setups.
- **Don't touch `apps/desktop-viewer/`.** Slice 4 is web-only by design (AD-S4-7 / spec §5).
