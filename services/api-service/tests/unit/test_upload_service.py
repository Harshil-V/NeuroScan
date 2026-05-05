from unittest.mock import AsyncMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.clients.orthanc import OrthancError
from app.db import Base
from app.models.audit import AuditEvent
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
