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
