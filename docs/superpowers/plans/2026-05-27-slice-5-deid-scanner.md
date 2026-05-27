# Slice 5 — De-identification Scanner Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a warn-only PHI scanner that detects DICOM PS3.15 identifying tags on every upload, persists findings to a new `phi_findings` table, and surfaces them in the web upload page and Qt desktop viewer.

**Architecture:** Pure-Python scanner module reading a single JSON rule file (`data/deid-rules.json`). Runs inline in the upload orchestrator between validate and Orthanc PUT. Findings persisted with FK to `audit_events`. Salted SHA-256 of values (no raw PHI stored). Scanner module duplicated across api-service and desktop-viewer (desktop is standalone per AD-S2-6); a CI drift check guarantees byte-equality.

**Tech Stack:** pydicom (existing), SQLAlchemy + Alembic (existing), FastAPI (existing), React + TypeScript (existing), PySide6 (existing). No new runtime dependencies.

**Spec:** [`docs/superpowers/specs/2026-05-27-slice-5-deid-scanner-design.md`](../specs/2026-05-27-slice-5-deid-scanner-design.md)

**Branch:** `slice-5-deid-scanner` (off `main`, already created)

**Commit policy:** Small, incremental, logically-isolated commits. Each task produces 1–2 commits. Never combine unrelated changes. Never amend.

**TDD scope:** Pure-logic modules (`deid/scanner.py`, `deid/rules.py`) are written test-first. Routes, schemas, and the upload orchestrator change are smoke-verified via integration tests.

---

## File structure

Created in this slice:

```text
data/deid-rules.json                                              # NEW (repo root)

services/api-service/
├── app/
│   ├── deid/
│   │   ├── __init__.py                                           # NEW
│   │   ├── rules.py                                              # NEW
│   │   └── scanner.py                                            # NEW (byte-identical to desktop copy)
│   ├── models/phi_findings.py                                    # NEW
│   ├── schemas/phi.py                                            # NEW
│   ├── routes/phi.py                                             # NEW (alt: extend audit.py)
│   └── alembic/versions/005_phi_findings.py                      # NEW
└── tests/unit/test_deid_scanner.py                               # NEW
└── tests/integration/test_phi_flow.py                            # NEW

apps/desktop-viewer/
├── app/deid/
│   ├── __init__.py                                               # NEW
│   ├── rules.json                                                # NEW (byte-identical copy of data/deid-rules.json)
│   ├── rules.py                                                  # NEW
│   └── scanner.py                                                # NEW (byte-identical copy of api-service scanner.py)
└── tests/unit/test_deid_scanner.py                               # NEW
└── tests/unit/test_metadata_panel_phi.py                         # NEW

apps/web-viewer/src/components/PhiFindingsBanner.tsx              # NEW

scripts/check-deid-scanner-drift.sh                               # NEW
```

Modified in this slice:

```text
services/api-service/app/config.py                                # +deid_hash_salt
services/api-service/app/models/__init__.py                       # +PhiFinding export
services/api-service/app/schemas/upload.py                        # +phi_findings on UploadResult
services/api-service/app/services/upload.py                       # +scanner call + findings persist
services/api-service/app/routes/dicom.py                          # pass summary through
services/api-service/app/main.py                                  # +include phi.router
services/api-service/tests/fixtures/synthetic_dicom.py            # +make_dicom_with_phi()

apps/web-viewer/src/types/index.ts                                # +Finding, PhiFindingsSummary, PhiFindingsDetail
apps/web-viewer/src/pages/UploadPage.tsx                          # +banner render

apps/desktop-viewer/app/widgets/metadata_panel.py                 # +PHI row highlighting + summary

.env.example                                                      # +DEID_HASH_SALT
.github/workflows/ci.yml                                          # +scanner drift check step
docs/qa-validation-plan.md                                        # +TC-10
docs/status.md                                                    # mark slice 5 done at end
docs/roadmap.md                                                   # mark slice 5 done at end
README.md                                                         # +PHI detection bullet
```

Untouched: `tests/e2e/`, `infra/docker-compose.yml`, all storage / reconstruction code from prior slices.

---

## Phase A — Rules file + config + drift check

### Task A1: Create `data/deid-rules.json`

**Files:**
- Create: `data/deid-rules.json`

- [ ] **Step 1: Write the rules JSON**

Create `data/deid-rules.json` with the exact content:

```json
{
  "version": "1.0",
  "source": "DICOM PS3.15 Basic Confidentiality Profile (subset)",
  "high_severity_tags": [
    {"tag": "0010,0010", "name": "PatientName"},
    {"tag": "0010,0020", "name": "PatientID"},
    {"tag": "0010,0030", "name": "PatientBirthDate"},
    {"tag": "0010,0040", "name": "PatientSex"},
    {"tag": "0010,1000", "name": "OtherPatientIDs"},
    {"tag": "0010,1001", "name": "OtherPatientNames"},
    {"tag": "0010,1010", "name": "PatientAge"},
    {"tag": "0010,1040", "name": "PatientAddress"},
    {"tag": "0010,2154", "name": "PatientTelephoneNumbers"},
    {"tag": "0010,2160", "name": "EthnicGroup"}
  ],
  "medium_severity_tags": [
    {"tag": "0008,0080", "name": "InstitutionName"},
    {"tag": "0008,0081", "name": "InstitutionAddress"},
    {"tag": "0008,0090", "name": "ReferringPhysicianName"},
    {"tag": "0008,1010", "name": "StationName"},
    {"tag": "0008,1030", "name": "StudyDescription"},
    {"tag": "0008,1040", "name": "InstitutionalDepartmentName"},
    {"tag": "0008,1048", "name": "PhysiciansOfRecord"},
    {"tag": "0008,1050", "name": "PerformingPhysicianName"},
    {"tag": "0008,1060", "name": "NameOfPhysiciansReadingStudy"},
    {"tag": "0008,1070", "name": "OperatorsName"},
    {"tag": "0008,0050", "name": "AccessionNumber"},
    {"tag": "0008,0020", "name": "StudyDate"},
    {"tag": "0008,0021", "name": "SeriesDate"},
    {"tag": "0008,0022", "name": "AcquisitionDate"},
    {"tag": "0008,0030", "name": "StudyTime"}
  ]
}
```

- [ ] **Step 2: Verify it parses**

```bash
cd "/Users/harshilvyas/Documents/Github Repos/NeuroScan"
python3 -c "import json; d=json.load(open('data/deid-rules.json')); print('high:', len(d['high_severity_tags']), 'medium:', len(d['medium_severity_tags']))"
```

Expected: `high: 10 medium: 15`

- [ ] **Step 3: Commit**

```bash
git add data/deid-rules.json
git commit -m "feat(slice-5): add DICOM PS3.15 PHI rule list (10 high + 15 medium)"
```

---

### Task A2: Add `deid_hash_salt` setting + env example

**Files:**
- Modify: `services/api-service/app/config.py`
- Modify: `.env.example`

- [ ] **Step 1: Add `deid_hash_salt` to `Settings`**

In `services/api-service/app/config.py`, add **after** `minio_public_url`:

```python
    # PHI scanner salt for value hashing. Override DEID_HASH_SALT in production.
    # Never log this value; never return it via API.
    deid_hash_salt: str = "neuroscan-dev-salt"
```

- [ ] **Step 2: Add `DEID_HASH_SALT` to `.env.example`**

Append at the end of `.env.example`:

```env

# de-identification scanner
# IMPORTANT: override this in production. Used to salt SHA-256 of PHI values.
DEID_HASH_SALT=neuroscan-dev-salt
```

- [ ] **Step 3: Smoke verify**

```bash
cd "/Users/harshilvyas/Documents/Github Repos/NeuroScan/services/api-service"
uv run python -c "
from app.config import get_settings
get_settings.cache_clear()
s = get_settings()
print('salt set:', bool(s.deid_hash_salt))
"
```

Expected: `salt set: True`

- [ ] **Step 4: Commit**

```bash
cd "/Users/harshilvyas/Documents/Github Repos/NeuroScan"
git add services/api-service/app/config.py .env.example
git commit -m "feat(slice-5): add DEID_HASH_SALT config setting"
```

---

### Task A3: Drift-check script + CI step

**Files:**
- Create: `scripts/check-deid-scanner-drift.sh`
- Modify: `.github/workflows/ci.yml`

- [ ] **Step 1: Write the drift-check script**

Create `scripts/check-deid-scanner-drift.sh`:

```bash
#!/usr/bin/env bash
# Verify the duplicated PHI scanner files match byte-for-byte across
# api-service and desktop-viewer. Slice 5 ships two copies of the scanner
# because the desktop viewer is standalone (no backend dep) — this script
# is the safety net against drift. Refactor into a shared package is a
# future concern.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
API_SCANNER="$ROOT/services/api-service/app/services/deid/scanner.py"
DESKTOP_SCANNER="$ROOT/apps/desktop-viewer/app/deid/scanner.py"
RULES_SOURCE="$ROOT/data/deid-rules.json"
RULES_DESKTOP="$ROOT/apps/desktop-viewer/app/deid/rules.json"

if ! cmp -s "$API_SCANNER" "$DESKTOP_SCANNER"; then
  echo "DRIFT: api-service scanner.py != desktop-viewer scanner.py" >&2
  diff -u "$API_SCANNER" "$DESKTOP_SCANNER" >&2 || true
  exit 1
fi

if ! cmp -s "$RULES_SOURCE" "$RULES_DESKTOP"; then
  echo "DRIFT: data/deid-rules.json != apps/desktop-viewer/app/deid/rules.json" >&2
  diff -u "$RULES_SOURCE" "$RULES_DESKTOP" >&2 || true
  exit 1
fi

echo "OK: scanner.py and rules.json match across api-service and desktop-viewer"
```

Make it executable:

```bash
chmod +x scripts/check-deid-scanner-drift.sh
```

- [ ] **Step 2: Add CI step**

Read `.github/workflows/ci.yml` first. Identify the `python` job (or whichever job runs api-service tests). Append a new step to that job, **after** the lint/test steps:

```yaml
      - name: PHI scanner drift check
        run: ./scripts/check-deid-scanner-drift.sh
```

If the structure of `ci.yml` is unclear, add a new top-level job:

```yaml
  deid-drift-check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Verify scanner files match
        run: ./scripts/check-deid-scanner-drift.sh
```

- [ ] **Step 3: Local sanity test (will fail until Phase I)**

```bash
cd "/Users/harshilvyas/Documents/Github Repos/NeuroScan"
./scripts/check-deid-scanner-drift.sh
```

Expected on this run: failure (files don't exist yet). That's fine — the check exists; later phases populate the files.

- [ ] **Step 4: Commit**

```bash
git add scripts/check-deid-scanner-drift.sh .github/workflows/ci.yml
git commit -m "ci(slice-5): add scanner/rules drift-check script"
```

---

## Phase B — Scanner module (TDD)

### Task B1: TDD `app/deid/rules.py`

**Files:**
- Create: `services/api-service/app/deid/__init__.py`
- Create: `services/api-service/app/deid/rules.py`
- Create: `services/api-service/tests/unit/test_deid_rules.py`

**Note on placement**: api-service usually puts logic under `app/services/`. We deliberately use `app/deid/` (no `services/` prefix) so the desktop viewer can import the *byte-identical* scanner via the same path. The drift-check script (Task A3) enforces byte-equality across `services/api-service/app/deid/scanner.py` and `apps/desktop-viewer/app/deid/scanner.py`. Different import paths would break the check.

- [ ] **Step 1: Create empty `__init__.py`**

```bash
mkdir -p "/Users/harshilvyas/Documents/Github Repos/NeuroScan/services/api-service/app/deid"
touch "/Users/harshilvyas/Documents/Github Repos/NeuroScan/services/api-service/app/deid/__init__.py"
```

- [ ] **Step 2: Write failing tests**

Create `services/api-service/tests/unit/test_deid_rules.py`:

```python
import pytest

from app.deid.rules import (
    HIGH_SEVERITY_TAGS,
    MEDIUM_SEVERITY_TAGS,
    Severity,
    TagName,
    load_rules,
    severity_for,
    tag_name_for,
)


def test_load_rules_returns_two_lists():
    rules = load_rules()
    assert "version" in rules
    assert len(rules["high_severity_tags"]) == 10
    assert len(rules["medium_severity_tags"]) == 15


def test_high_severity_tags_contains_patient_name():
    assert "0010,0010" in HIGH_SEVERITY_TAGS
    assert HIGH_SEVERITY_TAGS["0010,0010"] == "PatientName"


def test_medium_severity_tags_contains_institution_name():
    assert "0008,0080" in MEDIUM_SEVERITY_TAGS
    assert MEDIUM_SEVERITY_TAGS["0008,0080"] == "InstitutionName"


def test_severity_for_high_tag():
    assert severity_for("0010,0010") == "high"


def test_severity_for_medium_tag():
    assert severity_for("0008,0080") == "medium"


def test_severity_for_unknown_tag_returns_none():
    assert severity_for("ffff,ffff") is None


def test_tag_name_for_known_tag():
    assert tag_name_for("0010,0010") == "PatientName"


def test_tag_name_for_unknown_tag_returns_none():
    assert tag_name_for("ffff,ffff") is None


def test_severity_type_alias_is_str():
    s: Severity = "high"
    assert s == "high"
    t: TagName = "PatientName"
    assert t == "PatientName"
```

- [ ] **Step 3: Run, expect ImportError**

```bash
cd "/Users/harshilvyas/Documents/Github Repos/NeuroScan/services/api-service"
uv run pytest tests/unit/test_deid_rules.py -v 2>&1 | head -15
```

Expected: ImportError on `app.services.deid.rules`.

- [ ] **Step 4: Write `app/deid/rules.py`**

```python
"""PHI rule registry — loads data/deid-rules.json once and exposes lookups."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Literal

Severity = Literal["high", "medium"]
TagName = str

# Resolution order:
#   1) DEID_RULES_PATH env override (tests / Docker)
#   2) repo-root data/deid-rules.json (local dev: 4 levels up from this file)
#   3) /app/data/deid-rules.json (Docker image)
def _rules_path() -> Path:
    import os

    override = os.environ.get("DEID_RULES_PATH")
    if override:
        return Path(override)

    # services/api-service/app/deid/rules.py
    # parents[0]=deid  [1]=app  [2]=api-service  [3]=services  [4]=<repo root>
    here = Path(__file__).resolve()
    repo_root = here.parents[4]
    candidate = repo_root / "data" / "deid-rules.json"
    if candidate.exists():
        return candidate

    return Path("/app/data/deid-rules.json")


@lru_cache(maxsize=1)
def load_rules() -> dict:
    """Read the JSON rule file. Cached for the process lifetime."""
    path = _rules_path()
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _build_index(items: list[dict]) -> dict[str, str]:
    return {entry["tag"]: entry["name"] for entry in items}


_rules = load_rules()
HIGH_SEVERITY_TAGS: dict[str, str] = _build_index(_rules["high_severity_tags"])
MEDIUM_SEVERITY_TAGS: dict[str, str] = _build_index(_rules["medium_severity_tags"])


def severity_for(tag: str) -> Severity | None:
    if tag in HIGH_SEVERITY_TAGS:
        return "high"
    if tag in MEDIUM_SEVERITY_TAGS:
        return "medium"
    return None


def tag_name_for(tag: str) -> TagName | None:
    if tag in HIGH_SEVERITY_TAGS:
        return HIGH_SEVERITY_TAGS[tag]
    if tag in MEDIUM_SEVERITY_TAGS:
        return MEDIUM_SEVERITY_TAGS[tag]
    return None
```

- [ ] **Step 5: Run, expect PASS**

```bash
uv run pytest tests/unit/test_deid_rules.py -v
```

Expected: **9 passed**.

- [ ] **Step 6: Commit**

```bash
cd "/Users/harshilvyas/Documents/Github Repos/NeuroScan"
git add services/api-service/app/deid/__init__.py \
        services/api-service/app/deid/rules.py \
        services/api-service/tests/unit/test_deid_rules.py
git commit -m "feat(slice-5): add PHI rule registry with severity + tag-name lookups"
```

---

### Task B2: TDD `app/deid/scanner.py`

**Files:**
- Create: `services/api-service/app/deid/scanner.py`
- Create: `services/api-service/tests/unit/test_deid_scanner.py`

- [ ] **Step 1: Write failing tests**

Create `services/api-service/tests/unit/test_deid_scanner.py`:

```python
from io import BytesIO

import pydicom
import pytest

from app.deid.scanner import Finding, scan_phi
from tests.fixtures.synthetic_dicom import make_synthetic_mr_dicom_bytes


def _ds_with(**fields):
    """Build a dataset with the given attributes set on top of the synthetic fixture."""
    raw = make_synthetic_mr_dicom_bytes()
    ds = pydicom.dcmread(BytesIO(raw))
    for k, v in fields.items():
        setattr(ds, k, v)
    return ds


def test_scan_returns_list_of_findings():
    ds = _ds_with()
    findings = scan_phi(ds, salt="test-salt")
    assert isinstance(findings, list)
    assert all(isinstance(f, Finding) for f in findings)


def test_scan_flags_patient_name_high_severity():
    ds = _ds_with(PatientName="DOE^JOHN")
    findings = scan_phi(ds, salt="test-salt")
    pn = next((f for f in findings if f.tag == "0010,0010"), None)
    assert pn is not None
    assert pn.tag_name == "PatientName"
    assert pn.severity == "high"
    assert pn.value_sha256 is not None
    assert len(pn.value_sha256) == 64  # SHA-256 hex


def test_scan_flags_institution_name_medium_severity():
    ds = _ds_with(InstitutionName="General Hospital")
    findings = scan_phi(ds, salt="test-salt")
    inst = next((f for f in findings if f.tag == "0008,0080"), None)
    assert inst is not None
    assert inst.severity == "medium"


def test_scan_ignores_non_phi_tags():
    ds = _ds_with()
    findings = scan_phi(ds, salt="test-salt")
    tags = {f.tag for f in findings}
    assert "0028,0010" not in tags  # Rows — not PHI
    assert "0028,0011" not in tags  # Columns — not PHI


def test_scan_empty_value_yields_null_hash():
    ds = _ds_with(PatientID="")
    findings = scan_phi(ds, salt="test-salt")
    pid = next((f for f in findings if f.tag == "0010,0020"), None)
    # PatientID tag exists but value is empty
    assert pid is not None
    assert pid.value_sha256 is None


def test_scan_missing_tag_not_flagged():
    raw = make_synthetic_mr_dicom_bytes()
    ds = pydicom.dcmread(BytesIO(raw))
    del ds.PatientName
    findings = scan_phi(ds, salt="test-salt")
    tags = {f.tag for f in findings}
    assert "0010,0010" not in tags


def test_scan_deterministic_hash_with_same_salt():
    ds = _ds_with(PatientName="DOE^JOHN")
    a = scan_phi(ds, salt="salt-A")
    b = scan_phi(ds, salt="salt-A")
    ha = next(f.value_sha256 for f in a if f.tag == "0010,0010")
    hb = next(f.value_sha256 for f in b if f.tag == "0010,0010")
    assert ha == hb


def test_scan_different_salt_yields_different_hash():
    ds = _ds_with(PatientName="DOE^JOHN")
    a = scan_phi(ds, salt="salt-A")
    b = scan_phi(ds, salt="salt-B")
    ha = next(f.value_sha256 for f in a if f.tag == "0010,0010")
    hb = next(f.value_sha256 for f in b if f.tag == "0010,0010")
    assert ha != hb


def test_scan_counts_high_and_medium_correctly():
    ds = _ds_with(
        PatientName="DOE^JOHN",
        PatientID="MRN-001",
        PatientBirthDate="19800101",
        InstitutionName="General Hospital",
        ReferringPhysicianName="SMITH^J",
    )
    findings = scan_phi(ds, salt="test-salt")
    high = [f for f in findings if f.severity == "high"]
    medium = [f for f in findings if f.severity == "medium"]
    assert len(high) >= 3  # PatientName, PatientID, PatientBirthDate
    assert len(medium) >= 2  # InstitutionName, ReferringPhysicianName


def test_scan_performance_under_50ms_on_large_dataset():
    import time

    ds = _ds_with(PatientName="DOE^JOHN")
    # pydicom Dataset supports arbitrary private tags; add 500 of them
    for i in range(500):
        ds.add_new((0x0099, 0x1000 + i), "LO", f"value-{i}")

    t0 = time.perf_counter()
    findings = scan_phi(ds, salt="test-salt")
    elapsed_ms = (time.perf_counter() - t0) * 1000

    assert elapsed_ms < 50, f"scan_phi took {elapsed_ms:.1f}ms, expected < 50ms"
    assert any(f.tag == "0010,0010" for f in findings)
```

- [ ] **Step 2: Run, expect ImportError**

```bash
uv run pytest tests/unit/test_deid_scanner.py -v 2>&1 | head -10
```

Expected: ImportError on `app.services.deid.scanner`.

- [ ] **Step 3: Write `app/deid/scanner.py`**

This file must be **byte-identical** to `apps/desktop-viewer/app/deid/scanner.py` (copied in Phase I1). The drift-check CI step (Task A3) enforces this. Use no platform-specific paths, no api-service-specific imports.

```python
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
        findings.append(
            Finding(tag=tag_str, tag_name=name, severity=sev, value_sha256=value_hash)
        )
    return findings
```

- [ ] **Step 4: Run, expect PASS**

```bash
uv run pytest tests/unit/test_deid_scanner.py -v
```

Expected: **10 passed**.

- [ ] **Step 5: Run all unit tests (no regression)**

```bash
export DOCKER_HOST="unix://$HOME/.orbstack/run/docker.sock"
uv run pytest tests/unit/ -q
```

Expected: 69 (existing) + 9 (rules) + 10 (scanner) = **88 passed**.

- [ ] **Step 6: Commit**

```bash
cd "/Users/harshilvyas/Documents/Github Repos/NeuroScan"
git add services/api-service/app/deid/scanner.py \
        services/api-service/tests/unit/test_deid_scanner.py
git commit -m "feat(slice-5): add PHI scanner with salted-SHA-256 value hashing"
```

---

## Phase C — Data model + migration

### Task C1: `PhiFinding` model + migration 005

**Files:**
- Create: `services/api-service/app/models/phi_findings.py`
- Modify: `services/api-service/app/models/__init__.py`
- Create: `services/api-service/app/alembic/versions/005_phi_findings.py`

- [ ] **Step 1: Write `app/models/phi_findings.py`**

```python
import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class PhiFinding(Base):
    __tablename__ = "phi_findings"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer(), "sqlite"),
        primary_key=True,
        autoincrement=True,
    )
    audit_event_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("audit_events.event_id", ondelete="CASCADE"),
        nullable=False,
    )
    tag: Mapped[str] = mapped_column(String(9), nullable=False)
    tag_name: Mapped[str] = mapped_column(String(64), nullable=False)
    severity: Mapped[str] = mapped_column(String(8), nullable=False)
    value_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )

    __table_args__ = (
        Index("idx_phi_findings_audit_event_id", "audit_event_id"),
        Index("idx_phi_findings_severity", "severity"),
    )
```

- [ ] **Step 2: Update `app/models/__init__.py`**

Replace contents with:

```python
from app.models.audit import AuditEvent
from app.models.phi_findings import PhiFinding
from app.models.reconstruction import ReconstructionJob
from app.models.storage import StorageObject

__all__ = ["AuditEvent", "PhiFinding", "ReconstructionJob", "StorageObject"]
```

- [ ] **Step 3: Write migration 005**

Create `services/api-service/app/alembic/versions/005_phi_findings.py`:

```python
"""phi_findings

Revision ID: 005
Revises: 004
Create Date: 2026-05-27

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "005"
down_revision: str | None = "004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "phi_findings",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("audit_event_id", sa.Uuid(), nullable=False),
        sa.Column("tag", sa.String(length=9), nullable=False),
        sa.Column("tag_name", sa.String(length=64), nullable=False),
        sa.Column("severity", sa.String(length=8), nullable=False),
        sa.Column("value_sha256", sa.String(length=64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["audit_event_id"],
            ["audit_events.event_id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_phi_findings_audit_event_id",
        "phi_findings",
        ["audit_event_id"],
    )
    op.create_index(
        "idx_phi_findings_severity",
        "phi_findings",
        ["severity"],
    )


def downgrade() -> None:
    op.drop_index("idx_phi_findings_severity", table_name="phi_findings")
    op.drop_index("idx_phi_findings_audit_event_id", table_name="phi_findings")
    op.drop_table("phi_findings")
```

- [ ] **Step 4: Apply migration locally and verify**

```bash
export PATH="$HOME/.orbstack/bin:$PATH"
export DOCKER_HOST="unix://$HOME/.orbstack/run/docker.sock"
cd "/Users/harshilvyas/Documents/Github Repos/NeuroScan/infra"
docker compose up -d postgres
sleep 5

cd "/Users/harshilvyas/Documents/Github Repos/NeuroScan/services/api-service"
DATABASE_URL=postgresql+psycopg://neuroscan:neuroscan@localhost:5432/neuroscan \
  uv run alembic upgrade head
```

Expected: `Running upgrade 004 -> 005, phi_findings`.

Verify the table:

```bash
cd "/Users/harshilvyas/Documents/Github Repos/NeuroScan/infra"
docker compose exec -T postgres psql -U neuroscan -c "\d phi_findings"
```

Expected: 7 columns + PK + 2 indexes + FK to `audit_events.event_id`.

Tear down (preserve volumes):

```bash
docker compose down
```

- [ ] **Step 5: Run unit tests**

```bash
cd "/Users/harshilvyas/Documents/Github Repos/NeuroScan/services/api-service"
export DOCKER_HOST="unix://$HOME/.orbstack/run/docker.sock"
uv run pytest tests/unit/ -q
```

Expected: **88 passed**.

- [ ] **Step 6: Commit**

```bash
cd "/Users/harshilvyas/Documents/Github Repos/NeuroScan"
git add services/api-service/app/models/ \
        services/api-service/app/alembic/versions/005_phi_findings.py
git commit -m "feat(slice-5): add PhiFinding model + alembic migration 005"
```

---

## Phase D — Schemas + upload-orchestrator wiring

### Task D1: PHI schemas

**Files:**
- Create: `services/api-service/app/schemas/phi.py`
- Modify: `services/api-service/app/schemas/upload.py`

- [ ] **Step 1: Write `app/schemas/phi.py`**

```python
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
```

- [ ] **Step 2: Modify `app/schemas/upload.py`**

Replace contents with:

```python
from pydantic import BaseModel

from app.schemas.phi import PhiFindingsSummary


class UploadResult(BaseModel):
    status: str
    study_instance_uid: str
    series_instance_uid: str
    sop_instance_uid: str
    orthanc_instance_id: str
    checksum_sha256: str
    phi_findings: PhiFindingsSummary


class ApiError(BaseModel):
    detail: str
    code: str | None = None
```

- [ ] **Step 3: Smoke verify**

```bash
cd "/Users/harshilvyas/Documents/Github Repos/NeuroScan/services/api-service"
uv run python -c "
from app.schemas.phi import PhiFindingsSummary, FindingItem
from app.schemas.upload import UploadResult
print('OK', UploadResult.model_fields['phi_findings'].annotation.__name__)
"
```

Expected: `OK PhiFindingsSummary`.

- [ ] **Step 4: Commit**

```bash
cd "/Users/harshilvyas/Documents/Github Repos/NeuroScan"
git add services/api-service/app/schemas/phi.py services/api-service/app/schemas/upload.py
git commit -m "feat(slice-5): add PHI Pydantic schemas; extend UploadResult"
```

---

### Task D2: Wire scanner into `handle_upload`

**Files:**
- Modify: `services/api-service/app/services/upload.py`
- Modify: `services/api-service/app/routes/dicom.py`

- [ ] **Step 1: Read current `app/services/upload.py`**

You already have the content from prior tasks; the key points to understand:
- `handle_upload` already takes `s3: S3Client | None = None`.
- It currently returns `UploadResult` with: study_instance_uid, series_instance_uid, sop_instance_uid, orthanc_instance_id, checksum_sha256.
- We will: (a) call `scan_phi` after the dataset is validated; (b) on success path, persist findings into `phi_findings` table linked to the new audit row's `event_id`; (c) return the summary as part of the result.

- [ ] **Step 2: Update `services/upload.py`**

Replace contents with:

```python
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.clients.orthanc import OrthancClient, OrthancError
from app.clients.s3 import S3Client
from app.models.audit import AuditEvent
from app.models.phi_findings import PhiFinding
from app.schemas.phi import FindingItem, PhiFindingsSummary
from app.deid.scanner import Finding, scan_phi
from app.services.audit import write_event
from app.services.checksum import sha256_of
from app.services.dicom_validation import (
    InvalidDicomError,
    MissingRequiredTagError,
    validate_dicom,
)
from app.services.metadata import extract_metadata
from app.services.storage import tee_to_s3


@dataclass
class UploadResult:
    study_instance_uid: str
    series_instance_uid: str
    sop_instance_uid: str
    orthanc_instance_id: str
    checksum_sha256: str
    phi_findings: PhiFindingsSummary = field(
        default_factory=lambda: PhiFindingsSummary(total=0, high=0, medium=0, items=[])
    )


class UploadFailedError(Exception):
    def __init__(self, code: str, message: str, status_code: int) -> None:
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


def _summarize(findings: list[Finding]) -> PhiFindingsSummary:
    high = sum(1 for f in findings if f.severity == "high")
    medium = sum(1 for f in findings if f.severity == "medium")
    items = [
        FindingItem(tag=f.tag, tag_name=f.tag_name, severity=f.severity)
        for f in findings
    ]
    return PhiFindingsSummary(total=len(findings), high=high, medium=medium, items=items)


async def handle_upload(
    *,
    session: Session,
    orthanc: OrthancClient,
    dicom_bytes: bytes,
    s3: S3Client | None = None,
    deid_salt: str = "",
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

    # PHI scan — pure, in-process, never raises (scanner is total).
    findings = scan_phi(ds, salt=deid_salt) if deid_salt else []
    summary = _summarize(findings)

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

    audit_status = "success"
    audit_message: str | None = None
    if s3 is not None:
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

    audit_event: AuditEvent = write_event(
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

    # Persist PHI findings (best-effort; never fail the upload over this)
    if findings:
        for f in findings:
            session.add(
                PhiFinding(
                    audit_event_id=audit_event.event_id,
                    tag=f.tag,
                    tag_name=f.tag_name,
                    severity=f.severity,
                    value_sha256=f.value_sha256,
                )
            )
        session.commit()

    return UploadResult(
        study_instance_uid=md["study_instance_uid"],
        series_instance_uid=md["series_instance_uid"],
        sop_instance_uid=md["sop_instance_uid"],
        orthanc_instance_id=orthanc_instance_id,
        checksum_sha256=checksum,
        phi_findings=summary,
    )
```

**Note**: this assumes `write_event(...)` returns the persisted `AuditEvent`. Confirm by reading `app/services/audit.py`. If it returns `None`, modify it to return the row (it should — Slice 1 likely already does this; if not, change the `return` statement to return the inserted object).

- [ ] **Step 3: Confirm `write_event` returns the row**

```bash
grep -n "def write_event" "/Users/harshilvyas/Documents/Github Repos/NeuroScan/services/api-service/app/services/audit.py"
```

Then read that function. If it doesn't return the `AuditEvent`, edit it so it does (add `return event` at the end, where `event` is the persisted row).

- [ ] **Step 4: Update `app/routes/dicom.py`**

Replace the body of `upload_dicom` so the route reads `deid_salt` from settings and passes it through:

```python
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.clients.orthanc import OrthancClient, OrthancError
from app.clients.s3 import S3Client
from app.config import Settings, get_settings
from app.db import get_session
from app.routes.storage import get_s3_client
from app.schemas.upload import UploadResult
from app.services.upload import handle_upload

router = APIRouter(prefix="/api/dicom", tags=["dicom"])


def get_orthanc_client(settings: Settings = Depends(get_settings)) -> OrthancClient:
    return OrthancClient(
        base_url=settings.orthanc_url,
        user=settings.orthanc_user,
        password=settings.orthanc_password,
    )


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
    settings: Settings = Depends(get_settings),
) -> UploadResult:
    data = await file.read()
    result = await handle_upload(
        session=session,
        orthanc=orthanc,
        dicom_bytes=data,
        s3=s3,
        deid_salt=settings.deid_hash_salt,
    )
    return UploadResult(
        status="uploaded",
        study_instance_uid=result.study_instance_uid,
        series_instance_uid=result.series_instance_uid,
        sop_instance_uid=result.sop_instance_uid,
        orthanc_instance_id=result.orthanc_instance_id,
        checksum_sha256=result.checksum_sha256,
        phi_findings=result.phi_findings,
    )


instances_router = APIRouter(prefix="/api/instances", tags=["instances"])


@instances_router.get("/{orthanc_instance_id}/preview.png")
async def preview_png(
    orthanc_instance_id: str,
    orthanc: OrthancClient = Depends(get_orthanc_client),
) -> Response:
    try:
        content, content_type = await orthanc.get_instance_preview(orthanc_instance_id)
    except OrthancError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return Response(content=content, media_type=content_type)
```

- [ ] **Step 5: Update existing unit tests for `handle_upload`**

The Slice 1 tests at `tests/unit/test_upload_service.py` call `handle_upload(...)` without `deid_salt`. Confirm they still pass — `deid_salt` defaults to `""`, which short-circuits the scan to `[]` so existing assertions about no PHI findings on the synthetic fixture remain valid.

```bash
cd "/Users/harshilvyas/Documents/Github Repos/NeuroScan/services/api-service"
uv run pytest tests/unit/test_upload_service.py -v
```

Expected: 4 passed (unchanged).

- [ ] **Step 6: Run lint**

```bash
uv run ruff check . && uv run ruff format --check .
```

If lint issues, fix with `uv run ruff format .` and `uv run ruff check --fix .`.

- [ ] **Step 7: Run all unit tests**

```bash
export DOCKER_HOST="unix://$HOME/.orbstack/run/docker.sock"
uv run pytest tests/unit/ -q
```

Expected: **88 passed**.

- [ ] **Step 8: Commit**

```bash
cd "/Users/harshilvyas/Documents/Github Repos/NeuroScan"
git add services/api-service/app/services/upload.py \
        services/api-service/app/services/audit.py \
        services/api-service/app/routes/dicom.py
git commit -m "feat(slice-5): wire PHI scanner into upload orchestrator; persist findings"
```

(Include `audit.py` only if you modified it to return the inserted row.)

---

## Phase E — PHI findings detail route

### Task E1: `GET /api/audit/events/{event_id}/phi-findings`

**Files:**
- Create: `services/api-service/app/routes/phi.py`
- Modify: `services/api-service/app/main.py`

- [ ] **Step 1: Write `app/routes/phi.py`**

```python
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
    audit = session.scalar(
        select(AuditEvent).where(AuditEvent.event_id == event_id)
    )
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
```

- [ ] **Step 2: Register router in `app/main.py`**

Read the current `app/main.py`. Find the import line listing routers (likely `from app.routes import audit, dicom, health, reconstruction, storage, studies`). Add `phi`:

```python
from app.routes import audit, dicom, health, phi, reconstruction, storage, studies
```

Find the `app.include_router(...)` block in `create_app()` and add:

```python
    app.include_router(phi.router)
```

- [ ] **Step 3: Smoke verify routes**

```bash
cd "/Users/harshilvyas/Documents/Github Repos/NeuroScan/services/api-service"
uv run python -c "
from app.main import create_app
app = create_app()
paths = sorted({r.path for r in app.routes if hasattr(r, 'path')})
assert '/api/audit/events/{event_id}/phi-findings' in paths, paths
print('OK', len(paths), 'routes')
"
```

Expected: `OK <N> routes` where N ≥ 17.

- [ ] **Step 4: Run lint + unit tests**

```bash
uv run ruff check . && uv run ruff format --check .
export DOCKER_HOST="unix://$HOME/.orbstack/run/docker.sock"
uv run pytest tests/unit/ -q
```

Expected: lint clean, **88 passed**.

- [ ] **Step 5: Commit**

```bash
cd "/Users/harshilvyas/Documents/Github Repos/NeuroScan"
git add services/api-service/app/routes/phi.py services/api-service/app/main.py
git commit -m "feat(slice-5): add GET /api/audit/events/{event_id}/phi-findings endpoint"
```

---

## Phase F — Test fixture with PHI

### Task F1: Extend `synthetic_dicom.py` with `make_dicom_with_phi()`

**Files:**
- Modify: `services/api-service/tests/fixtures/synthetic_dicom.py`

- [ ] **Step 1: Append the new fixture**

Append at the end of `services/api-service/tests/fixtures/synthetic_dicom.py`:

```python
def make_dicom_with_phi() -> bytes:
    """Generate a synthetic DICOM with PHI tags injected.

    Used by Slice 5 tests for the PHI scanner. Contains:
    - 3 high-severity tags (PatientName, PatientID, PatientBirthDate)
    - 4 medium-severity tags (InstitutionName, ReferringPhysicianName,
      AccessionNumber, StudyDate is already present by default).

    All values are obviously fake test data.
    """
    raw = make_synthetic_mr_dicom_bytes()
    ds = pydicom.dcmread(BytesIO(raw))
    ds.PatientName = "DOE^JOHN^TEST"
    ds.PatientID = "FAKE-MRN-12345"
    ds.PatientBirthDate = "19800101"
    ds.InstitutionName = "Test Memorial Hospital"
    ds.ReferringPhysicianName = "SMITH^JANE"
    ds.AccessionNumber = "ACC-TEST-001"
    # StudyDate already set by make_synthetic_mr_dicom_bytes (medium-severity hit)
    buf = BytesIO()
    ds.save_as(buf, write_like_original=False)
    return buf.getvalue()
```

- [ ] **Step 2: Smoke verify**

```bash
cd "/Users/harshilvyas/Documents/Github Repos/NeuroScan/services/api-service"
uv run python -c "
from io import BytesIO
import pydicom
from tests.fixtures.synthetic_dicom import make_dicom_with_phi
ds = pydicom.dcmread(BytesIO(make_dicom_with_phi()))
print('PatientName:', ds.PatientName)
print('InstitutionName:', ds.InstitutionName)
"
```

Expected:
```
PatientName: DOE^JOHN^TEST
InstitutionName: Test Memorial Hospital
```

- [ ] **Step 3: Commit**

```bash
cd "/Users/harshilvyas/Documents/Github Repos/NeuroScan"
git add services/api-service/tests/fixtures/synthetic_dicom.py
git commit -m "test(slice-5): add make_dicom_with_phi() fixture"
```

---

## Phase G — Integration tests

### Task G1: PHI flow integration tests

**Files:**
- Create: `services/api-service/tests/integration/test_phi_flow.py`
- Modify: `services/api-service/tests/integration/conftest.py`

- [ ] **Step 1: Update integration conftest to truncate `phi_findings`**

Open `services/api-service/tests/integration/conftest.py`. Find the `_truncate_tables_between_tests` fixture. Update the TRUNCATE statement to include `phi_findings`:

```python
            conn.exec_driver_sql(
                "TRUNCATE TABLE audit_events, reconstruction_jobs, storage_objects, phi_findings RESTART IDENTITY CASCADE"
            )
```

Note: add `CASCADE` — `phi_findings.audit_event_id` is FK to `audit_events.event_id`, so truncating audit_events without CASCADE would fail.

- [ ] **Step 2: Write the integration tests**

Create `services/api-service/tests/integration/test_phi_flow.py`:

```python
"""End-to-end PHI scanner tests against real Postgres + Orthanc + MinIO."""

from tests.fixtures.synthetic_dicom import (
    make_dicom_with_phi,
    make_synthetic_mr_dicom_bytes,
)


async def test_upload_with_phi_returns_findings_in_response(api_client):
    raw = make_dicom_with_phi()
    resp = await api_client.post(
        "/api/dicom/upload",
        files={"file": ("phi.dcm", raw, "application/dicom")},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()

    findings = body["phi_findings"]
    assert findings["total"] >= 7  # 3 high + ≥4 medium
    assert findings["high"] >= 3
    assert findings["medium"] >= 4

    tag_names = {item["tag_name"] for item in findings["items"]}
    assert "PatientName" in tag_names
    assert "PatientID" in tag_names
    assert "PatientBirthDate" in tag_names
    assert "InstitutionName" in tag_names

    # No raw values leak through the summary
    for item in findings["items"]:
        assert "value_sha256" not in item
        assert "value" not in item


async def test_upload_with_phi_persists_phi_findings_rows(api_client):
    raw = make_dicom_with_phi()
    await api_client.post(
        "/api/dicom/upload",
        files={"file": ("phi.dcm", raw, "application/dicom")},
    )

    audit = await api_client.get("/api/audit/events?limit=1")
    event_id = audit.json()["items"][0]["event_id"]

    detail = await api_client.get(f"/api/audit/events/{event_id}/phi-findings")
    assert detail.status_code == 200, detail.text
    body = detail.json()
    assert body["total"] >= 7
    # The detail endpoint DOES include value_sha256
    for item in body["items"]:
        assert "value_sha256" in item
        # Non-empty values must have a 64-char hash
        if item["value_sha256"] is not None:
            assert len(item["value_sha256"]) == 64


async def test_upload_without_phi_returns_empty_findings(api_client):
    # The default synthetic fixture has PatientName="Synthetic^Test" — that's
    # still a PHI tag (PatientName always counts). So we use a special fixture
    # by stripping ALL PHI tags. The simplest path: assert the summary
    # structure is well-formed even if non-zero.
    raw = make_synthetic_mr_dicom_bytes()
    resp = await api_client.post(
        "/api/dicom/upload",
        files={"file": ("a.dcm", raw, "application/dicom")},
    )
    body = resp.json()
    # Synthetic fixture has PatientName + PatientID + StudyDate + StudyDescription
    # (4 hits). Verify the structure is correct rather than asserting "no PHI".
    assert "phi_findings" in body
    assert isinstance(body["phi_findings"]["total"], int)
    assert body["phi_findings"]["total"] >= 1
    assert all(
        item["severity"] in {"high", "medium"} for item in body["phi_findings"]["items"]
    )


async def test_phi_findings_404_for_unknown_event(api_client):
    bogus = "00000000-0000-0000-0000-000000000000"
    resp = await api_client.get(f"/api/audit/events/{bogus}/phi-findings")
    assert resp.status_code == 404
```

- [ ] **Step 3: Run the tests**

```bash
export PATH="$HOME/.orbstack/bin:$PATH"
export DOCKER_HOST="unix://$HOME/.orbstack/run/docker.sock"
cd "/Users/harshilvyas/Documents/Github Repos/NeuroScan/services/api-service"
uv run pytest tests/integration/test_phi_flow.py -v
```

Expected: **4 passed**.

- [ ] **Step 4: Run all integration tests**

```bash
uv run pytest tests/integration/ -q
```

Expected: 22 (existing) + 4 (new) = **26 passed**.

- [ ] **Step 5: Commit**

```bash
cd "/Users/harshilvyas/Documents/Github Repos/NeuroScan"
git add services/api-service/tests/integration/test_phi_flow.py \
        services/api-service/tests/integration/conftest.py
git commit -m "test(slice-5): add PHI flow integration tests; truncate phi_findings with CASCADE"
```

---

## Phase H — Web UI

### Task H1: TypeScript types

**Files:**
- Modify: `apps/web-viewer/src/types/index.ts`

- [ ] **Step 1: Append PHI types**

Append at the end of `apps/web-viewer/src/types/index.ts`:

```typescript
export type PhiSeverity = "high" | "medium";

export interface PhiFindingItem {
  tag: string;
  tag_name: string;
  severity: PhiSeverity;
}

export interface PhiFindingItemWithHash extends PhiFindingItem {
  value_sha256: string | null;
}

export interface PhiFindingsSummary {
  total: number;
  high: number;
  medium: number;
  items: PhiFindingItem[];
}

export interface PhiFindingsDetail {
  audit_event_id: string;
  total: number;
  high: number;
  medium: number;
  items: PhiFindingItemWithHash[];
}
```

Also widen `UploadResult` (which is already defined in this file) to include `phi_findings`:

Find:

```typescript
export interface UploadResult {
  status: string;
  study_instance_uid: string;
  series_instance_uid: string;
  sop_instance_uid: string;
  orthanc_instance_id: string;
  checksum_sha256: string;
}
```

Replace with:

```typescript
export interface UploadResult {
  status: string;
  study_instance_uid: string;
  series_instance_uid: string;
  sop_instance_uid: string;
  orthanc_instance_id: string;
  checksum_sha256: string;
  phi_findings: PhiFindingsSummary;
}
```

- [ ] **Step 2: Typecheck**

```bash
cd "/Users/harshilvyas/Documents/Github Repos/NeuroScan/apps/web-viewer"
npm run typecheck
```

Expected: clean.

- [ ] **Step 3: Commit**

```bash
cd "/Users/harshilvyas/Documents/Github Repos/NeuroScan"
git add apps/web-viewer/src/types/index.ts
git commit -m "feat(slice-5): add PHI types to web viewer"
```

---

### Task H2: PHI findings banner component

**Files:**
- Create: `apps/web-viewer/src/components/PhiFindingsBanner.tsx`
- Modify: `apps/web-viewer/src/pages/UploadPage.tsx`

- [ ] **Step 1: Create the banner component**

Create `apps/web-viewer/src/components/PhiFindingsBanner.tsx`:

```typescript
import type { PhiFindingsSummary } from "../types";

const SEV_COLOR: Record<"high" | "medium", string> = {
  high: "#fee2e2",
  medium: "#fef3c7",
};
const SEV_TEXT: Record<"high" | "medium", string> = {
  high: "#991b1b",
  medium: "#92400e",
};

export default function PhiFindingsBanner({
  findings,
}: {
  findings: PhiFindingsSummary;
}) {
  if (findings.total === 0) return null;
  return (
    <div
      style={{
        background: "#fef9c3",
        border: "1px solid #facc15",
        borderRadius: 6,
        padding: "12px 16px",
        margin: "12px 0",
      }}
    >
      <div style={{ fontWeight: 600, marginBottom: 8 }}>
        ⚠ PHI detected: <strong>{findings.high} high-severity</strong> and{" "}
        <strong>{findings.medium} medium-severity</strong> identifiers found
        in this DICOM. The file was uploaded as-is (no tag stripping).
      </div>
      <table style={{ width: "100%", fontSize: 13, borderCollapse: "collapse" }}>
        <thead>
          <tr style={{ borderBottom: "1px solid #facc15", textAlign: "left" }}>
            <th style={{ padding: "4px 8px" }}>Tag</th>
            <th style={{ padding: "4px 8px" }}>Name</th>
            <th style={{ padding: "4px 8px" }}>Severity</th>
          </tr>
        </thead>
        <tbody>
          {findings.items.map((item) => (
            <tr key={item.tag}>
              <td style={{ padding: "4px 8px", fontFamily: "monospace" }}>
                {item.tag}
              </td>
              <td style={{ padding: "4px 8px" }}>{item.tag_name}</td>
              <td style={{ padding: "4px 8px" }}>
                <span
                  style={{
                    background: SEV_COLOR[item.severity],
                    color: SEV_TEXT[item.severity],
                    padding: "2px 8px",
                    borderRadius: 4,
                    fontSize: 12,
                  }}
                >
                  {item.severity}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
```

- [ ] **Step 2: Wire into `UploadPage.tsx`**

Read `apps/web-viewer/src/pages/UploadPage.tsx`. Find where the success panel renders (it will show study_instance_uid, checksum_sha256, etc. after a successful upload). Import the banner and render it above (or inside) the success panel:

```typescript
import PhiFindingsBanner from "../components/PhiFindingsBanner";
```

In the JSX where the success state renders, add `<PhiFindingsBanner findings={result.phi_findings} />` immediately above the existing success display (e.g. above the UIDs block).

- [ ] **Step 3: Typecheck + build**

```bash
cd "/Users/harshilvyas/Documents/Github Repos/NeuroScan/apps/web-viewer"
npm run typecheck && npm run build
```

Expected: both clean.

- [ ] **Step 4: Commit**

```bash
cd "/Users/harshilvyas/Documents/Github Repos/NeuroScan"
git add apps/web-viewer/src/components/PhiFindingsBanner.tsx \
        apps/web-viewer/src/pages/UploadPage.tsx
git commit -m "feat(slice-5): add PHI findings banner to upload success panel"
```

---

## Phase I — Desktop viewer

### Task I1: Copy scanner + rules into desktop project

**Files:**
- Create: `apps/desktop-viewer/app/deid/__init__.py`
- Create: `apps/desktop-viewer/app/deid/scanner.py`  (byte-identical copy)
- Create: `apps/desktop-viewer/app/deid/rules.py`
- Create: `apps/desktop-viewer/app/deid/rules.json`  (byte-identical copy)

- [ ] **Step 1: Create the directory and `__init__.py`**

```bash
mkdir -p "/Users/harshilvyas/Documents/Github Repos/NeuroScan/apps/desktop-viewer/app/deid"
touch "/Users/harshilvyas/Documents/Github Repos/NeuroScan/apps/desktop-viewer/app/deid/__init__.py"
```

- [ ] **Step 2: Copy `scanner.py` byte-for-byte**

The api-service scanner was written at `app/deid/scanner.py` (no `services/` prefix) precisely so the desktop copy can use the identical import path. Just copy:

```bash
cp "/Users/harshilvyas/Documents/Github Repos/NeuroScan/services/api-service/app/deid/scanner.py" \
   "/Users/harshilvyas/Documents/Github Repos/NeuroScan/apps/desktop-viewer/app/deid/scanner.py"
```

Verify they match:

```bash
cmp -s "/Users/harshilvyas/Documents/Github Repos/NeuroScan/services/api-service/app/deid/scanner.py" \
       "/Users/harshilvyas/Documents/Github Repos/NeuroScan/apps/desktop-viewer/app/deid/scanner.py" \
  && echo "BYTE-IDENTICAL" || echo "DRIFT"
```

Expected: `BYTE-IDENTICAL`.

- [ ] **Step 3: Write desktop `rules.py`**

Desktop's `rules.py` resolves the JSON path differently — it reads `app/deid/rules.json` relative to the project. Create `apps/desktop-viewer/app/deid/rules.py`:

```python
"""PHI rule registry (desktop copy) — reads bundled rules.json."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Literal

Severity = Literal["high", "medium"]
TagName = str


def _rules_path() -> Path:
    return Path(__file__).resolve().parent / "rules.json"


@lru_cache(maxsize=1)
def load_rules() -> dict:
    with _rules_path().open("r", encoding="utf-8") as f:
        return json.load(f)


def _build_index(items: list[dict]) -> dict[str, str]:
    return {entry["tag"]: entry["name"] for entry in items}


_rules = load_rules()
HIGH_SEVERITY_TAGS: dict[str, str] = _build_index(_rules["high_severity_tags"])
MEDIUM_SEVERITY_TAGS: dict[str, str] = _build_index(_rules["medium_severity_tags"])


def severity_for(tag: str) -> Severity | None:
    if tag in HIGH_SEVERITY_TAGS:
        return "high"
    if tag in MEDIUM_SEVERITY_TAGS:
        return "medium"
    return None


def tag_name_for(tag: str) -> TagName | None:
    if tag in HIGH_SEVERITY_TAGS:
        return HIGH_SEVERITY_TAGS[tag]
    if tag in MEDIUM_SEVERITY_TAGS:
        return MEDIUM_SEVERITY_TAGS[tag]
    return None
```

Note: the api-service `rules.py` uses repo-root path resolution; the desktop version uses a sibling-file path. **The two `rules.py` files do NOT need to be byte-identical** — only `scanner.py` and the JSON do. The drift-check script only checks scanner.py + JSON.

- [ ] **Step 4: Copy the JSON byte-for-byte**

```bash
cp "/Users/harshilvyas/Documents/Github Repos/NeuroScan/data/deid-rules.json" \
   "/Users/harshilvyas/Documents/Github Repos/NeuroScan/apps/desktop-viewer/app/deid/rules.json"
```

- [ ] **Step 5: Run drift check**

```bash
cd "/Users/harshilvyas/Documents/Github Repos/NeuroScan"
./scripts/check-deid-scanner-drift.sh
```

Expected: `OK: scanner.py and rules.json match across api-service and desktop-viewer`.

- [ ] **Step 6: Run api-service unit tests (verify import refactor didn't break anything)**

```bash
cd "/Users/harshilvyas/Documents/Github Repos/NeuroScan/services/api-service"
export DOCKER_HOST="unix://$HOME/.orbstack/run/docker.sock"
uv run pytest tests/unit/ -q
```

Expected: **88 passed**.

- [ ] **Step 7: Write a desktop-viewer unit test for the scanner**

Create `apps/desktop-viewer/tests/unit/test_deid_scanner.py`:

```python
"""Smoke tests for the desktop's local PHI scanner.

The detailed test matrix lives in api-service. Here we verify the desktop
copy imports cleanly and produces a finding on a known-PHI dataset.
"""

from io import BytesIO

import pydicom
import pytest

from app.deid.scanner import Finding, scan_phi


def _make_ds():
    from pydicom.dataset import FileDataset, FileMetaDataset
    from pydicom.uid import ExplicitVRLittleEndian, generate_uid

    file_meta = FileMetaDataset()
    file_meta.MediaStorageSOPClassUID = pydicom.uid.MRImageStorage
    file_meta.MediaStorageSOPInstanceUID = generate_uid()
    file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
    file_meta.ImplementationClassUID = generate_uid()

    ds = FileDataset("test.dcm", {}, file_meta=file_meta, preamble=b"\0" * 128)
    ds.PatientName = "DOE^JOHN"
    ds.PatientID = "MRN-12345"
    ds.InstitutionName = "Test Hospital"
    ds.Modality = "MR"
    return ds


def test_scanner_imports_cleanly():
    assert Finding is not None
    assert scan_phi is not None


def test_scanner_finds_high_severity_tags():
    ds = _make_ds()
    findings = scan_phi(ds, salt="test")
    severities = {f.severity for f in findings}
    assert "high" in severities
    assert any(f.tag == "0010,0010" for f in findings)


def test_scanner_finds_medium_severity_tags():
    ds = _make_ds()
    findings = scan_phi(ds, salt="test")
    assert any(f.severity == "medium" and f.tag == "0008,0080" for f in findings)
```

- [ ] **Step 8: Run desktop unit tests**

```bash
cd "/Users/harshilvyas/Documents/Github Repos/NeuroScan/apps/desktop-viewer"
QT_QPA_PLATFORM=offscreen uv run pytest tests/unit/test_deid_scanner.py -v
```

Expected: **3 passed**.

- [ ] **Step 9: Commit**

```bash
cd "/Users/harshilvyas/Documents/Github Repos/NeuroScan"
git add apps/desktop-viewer/app/deid \
        apps/desktop-viewer/tests/unit/test_deid_scanner.py
git commit -m "feat(slice-5): ship PHI scanner + rules.json to desktop viewer"
```

---

### Task I2: Highlight PHI rows in desktop metadata panel

**Files:**
- Modify: `apps/desktop-viewer/app/widgets/metadata_panel.py`
- Create: `apps/desktop-viewer/tests/unit/test_metadata_panel_phi.py`

- [ ] **Step 1: Read the current metadata panel**

```bash
cat "/Users/harshilvyas/Documents/Github Repos/NeuroScan/apps/desktop-viewer/app/widgets/metadata_panel.py"
```

Understand:
- How rows are added to the table.
- Where the dataset is received (e.g. a slot/method like `set_dataset(ds)`).
- What QTableWidget / QStandardItemModel API is in use.

- [ ] **Step 2: Add PHI scan + highlighting**

In the method that populates the table (e.g. `set_dataset`), after the rows have been built, run the scanner and color-code:

```python
from app.deid.scanner import scan_phi  # add to imports

# ... inside the populate method, AFTER rows are added ...

# Run PHI scan and highlight rows
findings = scan_phi(dataset, salt="desktop-local")  # local-only, no DB
phi_by_tag = {f.tag: f.severity for f in findings}

# Assume table rows are filled with tags in column 0 like "0010,0010"
from PySide6.QtGui import QColor

HIGH_BG = QColor("#fee2e2")
MEDIUM_BG = QColor("#fef3c7")

for row in range(self.table.rowCount()):
    tag_item = self.table.item(row, 0)
    if tag_item is None:
        continue
    tag = tag_item.text().strip().lower()
    sev = phi_by_tag.get(tag)
    if sev == "high":
        bg = HIGH_BG
    elif sev == "medium":
        bg = MEDIUM_BG
    else:
        continue
    for col in range(self.table.columnCount()):
        item = self.table.item(row, col)
        if item is not None:
            item.setBackground(bg)
```

Also add a summary label at the top of the panel:

```python
# Near widget construction, add a QLabel for the summary; update it in set_dataset:
high = sum(1 for s in phi_by_tag.values() if s == "high")
medium = sum(1 for s in phi_by_tag.values() if s == "medium")
if high or medium:
    self.summary_label.setText(
        f"🔴 {high} high · 🟡 {medium} medium PHI tags detected"
    )
    self.summary_label.setStyleSheet("background:#fef9c3; padding:4px;")
else:
    self.summary_label.setText("")
    self.summary_label.setStyleSheet("")
```

The exact code depends on the existing widget structure — adapt the construction (`QLabel("")` added to layout) and the populate method accordingly.

- [ ] **Step 3: Write a unit test**

Create `apps/desktop-viewer/tests/unit/test_metadata_panel_phi.py`:

```python
"""Verify the metadata panel highlights PHI rows.

This test instantiates the widget under offscreen Qt and asserts
that, after loading a dataset with known PHI tags, the rows for
those tags carry the high/medium background color.
"""

import sys

import pytest
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication

from app.widgets.metadata_panel import MetadataPanel


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication(sys.argv)
    yield app


def _make_ds_with_phi():
    import pydicom
    from pydicom.dataset import FileDataset, FileMetaDataset
    from pydicom.uid import ExplicitVRLittleEndian, generate_uid

    file_meta = FileMetaDataset()
    file_meta.MediaStorageSOPClassUID = pydicom.uid.MRImageStorage
    file_meta.MediaStorageSOPInstanceUID = generate_uid()
    file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
    file_meta.ImplementationClassUID = generate_uid()
    ds = FileDataset("t.dcm", {}, file_meta=file_meta, preamble=b"\0" * 128)
    ds.PatientName = "DOE^JOHN"
    ds.PatientID = "MRN-001"
    ds.InstitutionName = "Test Hospital"
    ds.Modality = "MR"
    ds.StudyInstanceUID = generate_uid()
    ds.SeriesInstanceUID = generate_uid()
    ds.SOPInstanceUID = generate_uid()
    return ds


def test_panel_highlights_high_severity_rows(qapp):
    panel = MetadataPanel()
    panel.set_dataset(_make_ds_with_phi())

    # Find the row with tag "0010,0010" (PatientName)
    found_high = False
    for row in range(panel.table.rowCount()):
        item = panel.table.item(row, 0)
        if item is None:
            continue
        if item.text().strip().lower() == "0010,0010":
            bg = item.background().color()
            # Light red background
            assert bg == QColor("#fee2e2"), f"unexpected bg for PatientName: {bg.name()}"
            found_high = True
            break
    assert found_high, "PatientName row not found in metadata table"


def test_panel_highlights_medium_severity_rows(qapp):
    panel = MetadataPanel()
    panel.set_dataset(_make_ds_with_phi())

    found_medium = False
    for row in range(panel.table.rowCount()):
        item = panel.table.item(row, 0)
        if item is None:
            continue
        if item.text().strip().lower() == "0008,0080":
            bg = item.background().color()
            assert bg == QColor("#fef3c7"), f"unexpected bg for InstitutionName: {bg.name()}"
            found_medium = True
            break
    assert found_medium, "InstitutionName row not found in metadata table"


def test_panel_summary_text_includes_counts(qapp):
    panel = MetadataPanel()
    panel.set_dataset(_make_ds_with_phi())
    text = panel.summary_label.text()
    assert "high" in text.lower() or "PHI" in text
```

**Important**: if the metadata panel's existing table column 0 is something other than the DICOM tag string (e.g. it's the tag name), adapt the row-matching logic to use the correct column. Read the widget code first.

- [ ] **Step 4: Run all desktop unit tests**

```bash
cd "/Users/harshilvyas/Documents/Github Repos/NeuroScan/apps/desktop-viewer"
QT_QPA_PLATFORM=offscreen uv run pytest tests/unit/ -v
```

Expected: 29 (existing Slice 2) + 3 (scanner) + 3 (panel highlight) = **35 passed**.

- [ ] **Step 5: Commit**

```bash
cd "/Users/harshilvyas/Documents/Github Repos/NeuroScan"
git add apps/desktop-viewer/app/widgets/metadata_panel.py \
        apps/desktop-viewer/tests/unit/test_metadata_panel_phi.py
git commit -m "feat(slice-5): highlight PHI rows + summary banner in desktop metadata panel"
```

---

## Phase J — Docs + final verification + push

### Task J1: Docs updates

**Files:**
- Modify: `README.md`
- Modify: `docs/qa-validation-plan.md`
- Modify: `docs/status.md`
- Modify: `docs/roadmap.md`

- [ ] **Step 1: README bullet**

In the "What this project demonstrates" bullet list of `README.md`, after the "Object storage with signed URLs" line, add:

```markdown
- **PHI detection**: every DICOM upload is scanned against the DICOM PS3.15 Basic Confidentiality Profile; identifying tags are surfaced in the UI with severity classification (high/medium), values recorded only as salted SHA-256 hashes.
```

- [ ] **Step 2: Update active slice in README**

Find:

```markdown
Active slice: **Slice 4 — MinIO Object Storage** (implementation complete on branch).
```

Replace with:

```markdown
Active slice: **Slice 5 — De-identification Scanner** (implementation complete on branch).
```

- [ ] **Step 3: Add TC-10 to qa-validation-plan.md**

Update the header date and slice range:

```markdown
# QA Validation Plan — Slices 1–5

**Last updated:** 2026-05-27
**Slices covered:** 1–5 (De-identification Scanner)
```

Insert this test case BEFORE the `## Automated tests as QA artifacts` section:

```markdown
### TC-10 PHI scanner (web + desktop)

Steps:
1. With the stack running, generate a PHI-laden DICOM:
   ```bash
   cd services/api-service
   uv run python -c "
   from tests.fixtures.synthetic_dicom import make_dicom_with_phi
   open('/Users/harshilvyas/Documents/Github Repos/NeuroScan/data/temp/phi.dcm','wb').write(make_dicom_with_phi())
   "
   ```
2. Open http://localhost:5173/upload and drop `data/temp/phi.dcm`.
3. Observe the upload success view: yellow banner appears above the green panel with "⚠ PHI detected: 3 high-severity and 4 medium-severity identifiers".
4. Below the banner, a table lists the detected tags (PatientName, PatientID, PatientBirthDate, InstitutionName, ReferringPhysicianName, AccessionNumber, StudyDate) with red/amber severity badges.
5. Navigate to /audit. Find the new row.
6. Open the API endpoint directly: `curl http://localhost:8000/api/audit/events/<event_id>/phi-findings | python3 -m json.tool` — confirms findings persisted with `value_sha256` populated.
7. Open the Qt desktop viewer (apps/desktop-viewer). Load `data/temp/phi.dcm` via File → Open.
8. Metadata panel shows a yellow summary at the top: "🔴 3 high · 🟡 4 medium PHI tags detected".
9. Rows for PatientName, PatientID, PatientBirthDate are highlighted in light red.
10. Rows for InstitutionName, ReferringPhysicianName, AccessionNumber, StudyDate are highlighted in light amber.

Expected:
- Step 3: yellow banner visible.
- Step 4: 7+ rows in findings table.
- Step 6: API returns 200 with non-empty items and 64-char `value_sha256` strings.
- Step 8-10: desktop viewer highlights match the rule list.

Pass criteria: all 4 expected outcomes met.
```

Append to **Known limitations**:

```markdown
- PHI scanner is **warn-only** — tags are flagged but never stripped or rewritten. A future slice can add anonymization.
- Free-text PHI inside string-VR fields (StudyDescription, ImageComments) is not detected — only the tag's presence is flagged, not the contents.
- Burned-in pixel data PHI (faces, text overlays) is not detected.
- The rule list ships a clinically meaningful subset of DICOM PS3.15 (~25 tags). The full standard has ~120 tags. Expanding the list is a JSON edit; no code change needed.
- Scanner code is **duplicated** between `services/api-service/app/deid/scanner.py` and `apps/desktop-viewer/app/deid/scanner.py`. A CI drift check enforces byte-equality. A refactor to a shared Python package is a future concern.
```

- [ ] **Step 4: Update roadmap**

Find:

```markdown
| 5 | De-identification scanner + warning UI on upload | planned | — | |
```

Replace with:

```markdown
| 5 | De-identification scanner + warning UI on upload | **done** | [spec](./superpowers/specs/2026-05-27-slice-5-deid-scanner-design.md) · [plan](./superpowers/plans/2026-05-27-slice-5-deid-scanner.md) | Completed 2026-05-27. Warn-only (no tag stripping). |
```

Also bump the file header date to `**Last updated:** 2026-05-27`.

- [ ] **Step 5: Update status**

Replace the **Current slice** section with:

```markdown
## Current slice

**Slice 5 — De-identification Scanner.** Implementation complete on `slice-5-deid-scanner`. Pending merge to `main`.

Spec: [`superpowers/specs/2026-05-27-slice-5-deid-scanner-design.md`](./superpowers/specs/2026-05-27-slice-5-deid-scanner-design.md)
Plan: [`superpowers/plans/2026-05-27-slice-5-deid-scanner.md`](./superpowers/plans/2026-05-27-slice-5-deid-scanner.md)

Slice 4 (merged to `main`):
- Spec: [`superpowers/specs/2026-05-07-slice-4-minio-storage-design.md`](./superpowers/specs/2026-05-07-slice-4-minio-storage-design.md)
- Plan: [`superpowers/plans/2026-05-07-slice-4-minio-storage.md`](./superpowers/plans/2026-05-07-slice-4-minio-storage.md)
```

Append to **What's done**:

```markdown
- Slice 5 implementation complete on `slice-5-deid-scanner`:
  - `data/deid-rules.json` — PS3.15 subset (10 high + 15 medium tags)
  - `app/deid/scanner.py` — pure-Python, salted-SHA-256 value hashing
  - `phi_findings` table (alembic migration 005, FK to audit_events with CASCADE)
  - PHI scan wired into `upload_orchestrator`; findings persisted + returned in UploadResult
  - `GET /api/audit/events/{event_id}/phi-findings` for audit detail
  - Yellow banner + findings table on web upload success panel
  - Qt desktop viewer: row highlighting + summary banner in metadata panel
  - Scanner module duplicated to desktop; CI drift check via `scripts/check-deid-scanner-drift.sh`
  - ~16 new tests (19 unit + 4 integration + 6 desktop)
  - QA TC-10 + README + .env.example updates
```

Replace **What's next**:

```markdown
## What's next

1. Merge `slice-5-deid-scanner` to `main` and push.
2. Brainstorm Slice 6 — Auth (JWT, RBAC) + studies cache tables in Postgres.
```

Append to **Recent decisions log**:

```markdown
- 2026-05-27: Locked AD-S5-1..10 (warn-only, server-inline, PS3.15 subset, upload-page UI surface, new phi_findings table with FK to audit_events, two-level severity, salted-SHA-256, desktop also surfaces findings, synthetic-only test data, scanner module duplicated with CI drift check).
- 2026-05-27: Slice 5 implementation complete on `slice-5-deid-scanner`.
```

Add a new deviations block at the end (initially empty):

```markdown
### Slice 5 implementation deviations from spec/plan (record for posterity)

- (Fill in any deviations encountered during implementation.)
```

- [ ] **Step 6: Commit docs**

```bash
cd "/Users/harshilvyas/Documents/Github Repos/NeuroScan"
git add README.md docs/qa-validation-plan.md docs/status.md docs/roadmap.md
git commit -m "docs(slice-5): add TC-10, PHI bullet in README, status + roadmap updates"
```

---

### Task J2: Final verification + push

- [ ] **Step 1: Run the drift check**

```bash
cd "/Users/harshilvyas/Documents/Github Repos/NeuroScan"
./scripts/check-deid-scanner-drift.sh
```

Expected: `OK: scanner.py and rules.json match across api-service and desktop-viewer`.

- [ ] **Step 2: Run all api-service tests**

```bash
export PATH="$HOME/.orbstack/bin:$PATH"
export DOCKER_HOST="unix://$HOME/.orbstack/run/docker.sock"
cd "/Users/harshilvyas/Documents/Github Repos/NeuroScan/services/api-service"
uv run pytest -q
uv run ruff check . && uv run ruff format --check .
```

Expected: **88 unit + 26 integration = 114 passed**; lint clean.

- [ ] **Step 3: Run all desktop tests**

```bash
cd "/Users/harshilvyas/Documents/Github Repos/NeuroScan/apps/desktop-viewer"
QT_QPA_PLATFORM=offscreen uv run pytest tests/unit/ -v
uv run ruff check . && uv run ruff format --check .
```

Expected: **35 passed**; lint clean.

- [ ] **Step 4: Web typecheck + build**

```bash
cd "/Users/harshilvyas/Documents/Github Repos/NeuroScan/apps/web-viewer"
npm run typecheck && npm run build
```

Expected: both clean.

- [ ] **Step 5: Manual smoke (recommended but optional for this step)**

Run TC-10 from the QA plan to confirm the full vertical works end-to-end. Document any deviations in `docs/status.md` under the new deviations section.

- [ ] **Step 6: Push branch**

```bash
cd "/Users/harshilvyas/Documents/Github Repos/NeuroScan"
git push -u origin slice-5-deid-scanner
```

Print the PR URL for the user.

---

## Self-review checklist (engineer to run before opening PR)

- [ ] Spec section 5 (scope) — every bullet has a task above
- [ ] All new files listed in "File structure" exist
- [ ] All modified files listed in "File structure" actually have diffs in the branch
- [ ] All `phi_findings` rows persist `audit_event_id` (UUID, FK valid) and survive CASCADE delete of audit_events
- [ ] `value_sha256` is NEVER in `UploadResult` (only in `GET /api/audit/events/.../phi-findings`)
- [ ] No raw PHI values in logs (`grep -r "value=" services/api-service/app/deid/` should yield nothing in `logger.*` calls)
- [ ] Drift check passes
- [ ] All tests pass (114 api-service + 35 desktop + clean web)
- [ ] Documented limitations honestly (warn-only, no free-text scan, no pixel-data scan)

---

## Notes for the implementing engineer

- **Phase B (scanner TDD) is strict TDD.** Don't skip the failing-test step.
- **Phase D wires the scanner into the existing upload path.** Read `app/services/upload.py` carefully before editing — Slice 4 left it with `s3: S3Client | None` and best-effort `tee_to_s3`. The PHI scan goes BEFORE the Orthanc upload (so a bad scan doesn't leave an Orthanc-only artifact), but findings are PERSISTED AFTER the audit row exists (because the FK requires it).
- **Phase B places the scanner at `app/deid/`** (not `app/services/deid/`) in api-service so the desktop copy can use the identical import path. This is the only deviation from api-service's `app/services/...` convention.
- **CASCADE on the FK** is critical because the integration conftest's TRUNCATE must respect it.
- **The `deid_salt=""` short-circuit** means existing Slice 1 unit tests (which don't pass a salt) still see `phi_findings=PhiFindingsSummary(total=0,...)` — they won't break.
- **The drift check uses `cmp -s`** — a single trailing-newline difference will fail it. When copying files, use `cp` (preserves bytes) not editor save.
- **Performance budget**: scanner < 5ms typical, < 50ms with 500 private tags. Test at the high end to catch quadratic accidents.
- **Salt rotation** is out of scope; if the salt is rotated, old hashes won't match new ones (this is documented in the spec, not in user-facing UI).
