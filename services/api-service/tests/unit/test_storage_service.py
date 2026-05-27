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
    from datetime import UTC, datetime

    delta = (expires_at - datetime.now(UTC)).total_seconds()
    assert 290 <= delta <= 310


def test_mint_presigned_url_404s_for_unknown_id(session, s3_client):
    with pytest.raises(StorageObjectNotFoundError):
        mint_presigned_url(
            s3=s3_client,
            session=session,
            object_id=99999,
            expires_in=300,
        )
