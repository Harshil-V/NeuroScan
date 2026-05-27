"""PHI findings retrieval endpoint (audit detail)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_session
from app.models.audit import AuditEvent
from app.models.phi_findings import PhiFinding
from app.schemas.phi import FindingItemWithHash, PhiFindingsDetail

router = APIRouter(prefix="/api/audit", tags=["audit"])


@router.get(
    "/events/{event_id}/phi-findings",
    response_model=PhiFindingsDetail,
)
async def get_phi_findings(
    event_id: UUID,
    session: Session = Depends(get_session),
) -> PhiFindingsDetail:
    audit = session.scalar(select(AuditEvent).where(AuditEvent.event_id == event_id))
    if audit is None:
        raise HTTPException(status_code=404, detail="audit_event_not_found")

    rows = list(
        session.scalars(
            select(PhiFinding)
            .where(PhiFinding.audit_event_id == event_id)
            .order_by(PhiFinding.severity, PhiFinding.tag)
        )
    )
    items = [
        FindingItemWithHash(
            tag=r.tag,
            tag_name=r.tag_name,
            severity=r.severity,
            value_sha256=r.value_sha256,
        )
        for r in rows
    ]
    high = sum(1 for r in rows if r.severity == "high")
    medium = sum(1 for r in rows if r.severity == "medium")
    return PhiFindingsDetail(
        audit_event_id=str(event_id),
        total=len(rows),
        high=high,
        medium=medium,
        items=items,
    )
