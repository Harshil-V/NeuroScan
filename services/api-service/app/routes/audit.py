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
