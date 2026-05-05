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
