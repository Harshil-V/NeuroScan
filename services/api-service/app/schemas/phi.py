from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

Severity = Literal["high", "medium"]


class FindingItem(BaseModel):
    """Single PHI finding as returned in API responses (no hash)."""

    tag: str
    tag_name: str
    severity: Severity


class FindingItemWithHash(FindingItem):
    """Single PHI finding including the salted-SHA-256 hash (audit detail only)."""

    value_sha256: str | None


class PhiFindingsSummary(BaseModel):
    """Embedded in UploadResult — counts + list without hashes."""

    total: int
    high: int
    medium: int
    items: list[FindingItem]


class PhiFindingsDetail(BaseModel):
    """Audit-detail endpoint response — includes hashes."""

    model_config = ConfigDict(from_attributes=True)

    audit_event_id: str
    total: int
    high: int
    medium: int
    items: list[FindingItemWithHash]


class PhiFindingRow(BaseModel):
    """ORM-friendly Pydantic view of a single phi_findings row."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    audit_event_id: str
    tag: str
    tag_name: str
    severity: Severity
    value_sha256: str | None
    created_at: datetime
