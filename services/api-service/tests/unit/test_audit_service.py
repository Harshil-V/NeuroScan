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
