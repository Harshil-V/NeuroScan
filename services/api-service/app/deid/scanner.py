"""Pure-Python PHI scanner over a pydicom Dataset.

Reads PS3.15 tag rules from app.deid.rules and yields one Finding per
identifying tag actually present in the dataset.  Values are recorded
only as salted SHA-256 hashes — never as raw text.

NOTE: This file is duplicated byte-for-byte across api-service and the
desktop viewer (see scripts/check-deid-scanner-drift.sh). Imports use
the path `app.deid.rules` so both projects can resolve them.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from pydicom.dataset import Dataset

from app.deid.rules import severity_for, tag_name_for


@dataclass(frozen=True)
class Finding:
    tag: str
    tag_name: str
    severity: str  # "high" | "medium"
    value_sha256: str | None


def _tag_to_str(tag_int: int) -> str:
    """Convert a pydicom integer tag (e.g. 0x00100010) to 'gggg,eeee' lowercase hex."""
    group = (tag_int >> 16) & 0xFFFF
    element = tag_int & 0xFFFF
    return f"{group:04x},{element:04x}"


def _hash_value(value: str, salt: str) -> str:
    h = hashlib.sha256()
    h.update(salt.encode("utf-8"))
    h.update(b"\x00")
    h.update(value.encode("utf-8"))
    return h.hexdigest()


def scan_phi(dataset: Dataset, *, salt: str) -> list[Finding]:
    """Return a list of Finding objects for every PHI tag present in dataset.

    `salt` is required (positional or keyword); never default it so callers
    must consciously decide where the salt comes from.
    """
    findings: list[Finding] = []
    for elem in dataset.iterall():
        tag_str = _tag_to_str(int(elem.tag))
        sev = severity_for(tag_str)
        if sev is None:
            continue
        name = tag_name_for(tag_str) or "Unknown"
        value = "" if elem.value in (None, "") else str(elem.value)
        value_hash = _hash_value(value, salt) if value else None
        findings.append(Finding(tag=tag_str, tag_name=name, severity=sev, value_sha256=value_hash))
    return findings
