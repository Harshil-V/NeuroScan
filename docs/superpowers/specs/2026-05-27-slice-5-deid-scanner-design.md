# NeuroScan Workstation — Slice 5: De-identification Scanner + PHI Warning UI

**Date:** 2026-05-27
**Status:** Draft (pending user review)
**Phase:** 5 of N
**Parent project:** NeuroScan Workstation — local-first MRI / DICOM platform
**Branch:** `slice-5-deid-scanner` (off `main`)
**Predecessors:** Slices 1, 2, 3, 4 — all merged to `main`

---

## 1. Purpose

Add a **PHI (Protected Health Information) scanner** that inspects every DICOM as it enters NeuroScan and reports which identifying tags are present. The scanner is **warn-only** — it never modifies tags, never blocks the upload, and never decides for the user whether content is safe to share. It surfaces structured findings in three places:

1. The upload page (yellow banner + findings table in the success panel)
2. The audit row (linked `phi_findings` rows queryable via API)
3. The Qt desktop viewer's metadata panel (red/amber highlight on PHI tags)

This slice demonstrates the **compliance posture** the parent PRD called for — checksumming + content-addressed storage (Slice 4) plus PHI visibility (this slice) plus audit logging (Slice 1) — without claiming HIPAA certification.

The slice is deliberately scoped to *detection*. **Tag stripping / anonymization** is deferred to a future slice; making the scanner authoritative about anonymization without a real review workflow would be misleading.

## 2. Out-of-scope (deliberately deferred)

- Tag stripping or rewriting of any kind (no PatientName blanking, no UID replacement, no date shifting)
- Pseudonymization or consistent-hash patient ID generation
- Free-text PHI detection inside string-VR fields (StudyDescription, ImageComments, etc.) — Microsoft Presidio integration deferred
- Burned-in pixel data PHI (face removal, OCR over the image plane) — separate problem, separate slice
- Per-user / per-role access to findings (Slice 6 — auth)
- Customizable rule profiles per organization or study type
- TCIA / real-data validation runs — only synthetic fixtures used
- Re-scanning historic studies (only new uploads are scanned)
- A "download anonymized copy" button (deferred to a future slice if and when stripping ships)
- Findings export (CSV, JSON-LD) — out of scope
- Findings retention policy / TTL — out of scope

These are explicit deferrals. The slice is "show what's there, don't touch it."

## 3. Architecture

### Topology

```text
                       upload bytes
                  ┌──────────────────┐
                  ▼                  │
         ┌──────────────────────────────────────────┐
         │  api-service (FastAPI)                    │
         │                                           │
         │  upload_orchestrator:                     │
         │    1. validate DICOM                      │
         │    2. compute sha256                      │
         │    3. ★ NEW: scan_phi(dataset) → findings │
         │    4. POST → Orthanc                      │
         │    5. tee → MinIO (Slice 4)               │
         │    6. write audit_events row              │
         │    7. ★ NEW: write phi_findings rows      │
         │    8. write storage_objects row           │
         │    9. return UploadResult (incl. findings)│
         │                                           │
         │  scanner module (deid.scanner):           │
         │    - reads data/deid-rules.json           │
         │    - pure function: dataset → [Finding]   │
         │    - salted SHA-256 of present values     │
         │                                           │
         │  routes/audit.py (extended):              │
         │    GET /api/audit/events/{id}/phi-findings│
         └────┬──────────────────┬─────────────────┬─┘
              │                  │                 │
              │ SQL              │ HTTP            │ S3
              ▼                  ▼                 ▼
         ┌─────────┐        ┌──────────┐    ┌────────────┐
         │Postgres │        │ Orthanc  │    │   MinIO    │
         │ + new:  │        └──────────┘    └────────────┘
         │ phi_    │
         │ findings│
         └─────────┘

         ┌─────────────────────────┐    ┌─────────────────────────┐
         │  apps/web-viewer        │    │  apps/desktop-viewer    │
         │  Upload success panel:  │    │  Metadata panel:        │
         │  ★ yellow banner + table│    │  ★ red/amber row bg     │
         │  Audit detail (future)  │    │  ★ "N PHI findings"     │
         │                         │    │     summary at top      │
         │  Reads via API          │    │  Local scan (no API)    │
         │                         │    │  via duplicated module  │
         └─────────────────────────┘    └─────────────────────────┘
```

### Scanner module placement

Per **AD-S5-10**, the scanner logic is duplicated across api-service and desktop-viewer because the desktop viewer is standalone (AD-S2-6, no backend dependency). The **rules** live in a single JSON file at `data/deid-rules.json` (in the repo root, version-controlled). Each project bundles or reads that file at runtime:

- **api-service**: reads from a path constructed relative to the app root. In Docker, the file is copied into the image at `/app/data/deid-rules.json`. In tests, the file is read from the repo root.
- **desktop-viewer**: a build step (or runtime resolver) bundles the JSON. For simplicity in this slice, we **copy** `data/deid-rules.json` into `apps/desktop-viewer/app/deid/rules.json` and add a `pre-run` script note to the README; both projects load the JSON via a tiny helper. (A future slice can clean this up with a real shared package.)

The **scanner code** (Python module) is duplicated — one copy at `services/api-service/app/services/deid/scanner.py`, one at `apps/desktop-viewer/app/deid/scanner.py`. The two files are identical, ~80 lines each, and have an integration test that asserts byte-equality so drift is caught in CI.

### Architectural decisions (locked)

| ID | Decision | Rationale |
|---|---|---|
| AD-S5-1 | Warn-only behavior — scanner never modifies tags or blocks upload | Avoids implying authoritative anonymization. The scanner reports; the human decides. |
| AD-S5-2 | Server-side **inline** scan in the upload orchestrator, between validate and Orthanc PUT | Findings are persisted on the same code path as the audit row; no race or "scan came back later" UX. |
| AD-S5-3 | Rule source = **DICOM PS3.15 Basic Confidentiality Profile** | Industry standard. Reviewable. Won't surprise a clinical reviewer who knows the standard. |
| AD-S5-4 | Findings surface = **upload page success panel** (yellow banner + table) | Immediate feedback at the point of action. |
| AD-S5-5 | Findings persistence = **new `phi_findings` table**, FK to `audit_events` | Normalized; queryable per-tag aggregations possible; clear separation of concerns from audit. |
| AD-S5-6 | Severity = **two-level** (`high` direct identifiers, `medium` indirect) | Two colors (red/amber) in UI. Avoids debate about ambiguous "low" tags. |
| AD-S5-7 | Value handling = **salted SHA-256** of present value | Allows duplicate detection across uploads without storing raw PHI. Salt configured via env var, never logged. |
| AD-S5-8 | Desktop viewer also surfaces findings | Consistent across surfaces. AD-S2-6 (standalone) preserved via duplicated scanner. |
| AD-S5-9 | Test data = synthetic only via extended `make_dicom_with_phi()` fixture | No real PHI risk in CI; fixture is deterministic. |
| AD-S5-10 | Code sharing strategy = **single JSON rule file** at `data/deid-rules.json`; scanner module duplicated across api-service and desktop-viewer | Zero new tooling. Drift caught by a byte-equality CI check. Refactor into a shared package is a future concern. |

### Cross-slice decisions inherited

AD-1 through AD-S4-10 continue to apply. Specifically:
- **AD-1**: `phi_findings` is app-owned metadata (analysis output), not duplicated DICOM data. Compliant.
- **AD-4**: Upload remains synchronous. Scanner runs in-line; performance budget below.
- **AD-S2-6**: Desktop viewer remains standalone. Scanner duplicated to honor this.
- **AD-S4-1..4**: MinIO sidecar pattern continues. PHI findings do NOT affect MinIO writes; a DICOM with high-severity findings is still tee'd to MinIO (warn-only).

## 4. Data flows

### 4.1 DICOM upload (modified Slice 1+4 path)

1. Client `POST /api/dicom/upload` with multipart `file=…`
2. api-service: validate DICOM, compute sha256
3. **NEW:** `findings = scan_phi(dataset)` — returns a list of `Finding(tag, tag_name, severity, value_sha256)`
4. POST to Orthanc (as before)
5. Tee to MinIO (Slice 4, best-effort)
6. Write `audit_events` row (status as before — `success`, `success_minio_skipped`, etc.)
7. **NEW:** For each finding, write a `phi_findings` row with `audit_event_id` FK
8. Write `storage_objects` row (if MinIO tee succeeded)
9. Return `UploadResult` with the existing fields **plus** a new `phi_findings_summary` object:
   ```json
   {
     "status": "uploaded",
     "study_instance_uid": "…",
     "checksum_sha256": "…",
     "phi_findings": {
       "total": 7,
       "high": 3,
       "medium": 4,
       "items": [
         {"tag": "0010,0010", "tag_name": "PatientName", "severity": "high"},
         {"tag": "0010,0020", "tag_name": "PatientID", "severity": "high"},
         …
       ]
     }
   }
   ```

The `items` array in the response includes tag identification but **not** the value or the value hash — the response is meant for UI display, not for downstream PHI analysis. Hashes are only retrievable via the persisted `phi_findings` rows.

### 4.2 Reconstruction (Slice 3 path, **unchanged**)

Reconstructed DICOMs are generated by NeuroScan itself with synthetic patient metadata (`Reconstruction^Output` etc.) — they contain no inherited PHI. The reconstruction `job_runner` does **not** call the scanner. This is a deliberate scoping decision: scanning system-generated output is a different problem (verifying our own anonymization), deferred.

### 4.3 Findings retrieval (audit detail)

- `GET /api/audit/events/{event_id}/phi-findings` returns the persisted findings for an audit row:
  ```json
  {
    "audit_event_id": "uuid",
    "total": 7,
    "high": 3,
    "medium": 4,
    "items": [
      {
        "tag": "0010,0010",
        "tag_name": "PatientName",
        "severity": "high",
        "value_sha256": "ab12…"
      },
      …
    ]
  }
  ```
- The endpoint returns 404 if no audit event exists with that id, 200 with empty items if no PHI was detected.

### 4.4 Desktop viewer local scan

1. User loads a DICOM folder via the existing Slice 2 file dialog.
2. For each parsed dataset, the local `deid.scanner.scan_phi(dataset)` runs in-process (no network).
3. The metadata panel renders each tag row with a background color: red for `high`, amber for `medium`, default for non-PHI.
4. A summary banner at the top of the panel reads: `"3 high-severity PHI tags, 4 medium-severity PHI tags detected"` when findings exist.
5. No persistence on the desktop side — findings are computed on demand from the loaded dataset.

### 4.5 Health endpoint

No change. `/health` does not report scanner status because the scanner has no external dependencies (in-process, pure-Python).

## 5. Slice 5 scope

### Backend (api-service)

- New `data/deid-rules.json` at repo root — PS3.15 rule list.
- New `app/services/deid/__init__.py` (re-exports).
- New `app/services/deid/scanner.py` — `scan_phi(dataset, salt) -> list[Finding]`. Pure function.
- New `app/services/deid/rules.py` — loads + caches the JSON, exposes `RULES: dict[str, RuleEntry]`.
- New `app/models/phi_findings.py` — SQLAlchemy `PhiFinding` model.
- New alembic migration `006_phi_findings`. (Migration 005 reserved for any pending slice; this slice claims 006 to stay clear of conflicts.) **Note**: Migration 005 doesn't exist yet — we use the next available number. Confirmed during plan.
- New `app/routes/phi.py` (or extend `routes/audit.py`) — `GET /api/audit/events/{event_id}/phi-findings`.
- New `app/schemas/phi.py` — `Finding`, `PhiFindingsSummary`, `PhiFindingsDetail` Pydantic DTOs.
- New `app/config.py` setting: `deid_hash_salt: str` (default `"neuroscan-dev-salt"`, env `DEID_HASH_SALT`).
- Modify `app/services/upload.py` — inject scanner + salt, call between validate and Orthanc PUT, persist findings, attach summary to response.
- Modify `app/schemas/upload.py` — add `phi_findings: PhiFindingsSummary` field to `UploadResult`.

### Web viewer (web-viewer)

- New types in `types/index.ts`: `Finding`, `PhiFindingsSummary`, `PhiFindingsDetail`.
- Modify `api/dicom.ts` — `UploadResult` response shape includes findings summary.
- Modify `pages/UploadPage.tsx` — when `phi_findings.total > 0`, render a yellow banner with a small table of findings (tag + tag_name + severity badge).
- (Optional, not blocking) Audit page row click expands to call `GET /api/audit/events/{id}/phi-findings` and show the detail table.

### Desktop viewer (desktop-viewer)

- New `apps/desktop-viewer/app/deid/__init__.py` + `apps/desktop-viewer/app/deid/scanner.py` (byte-identical copy of api-service version).
- New `apps/desktop-viewer/app/deid/rules.json` (copy of `data/deid-rules.json`).
- New `apps/desktop-viewer/app/deid/rules.py` — small loader for the JSON.
- Modify `apps/desktop-viewer/app/widgets/metadata_panel.py` — call `scan_phi` after a dataset loads, paint rows by severity, render summary banner.
- New unit tests under `apps/desktop-viewer/tests/unit/` for the highlight logic.

### Infra

- No docker-compose changes. Scanner runs in-process in api-service.
- `.env.example` gains `DEID_HASH_SALT=neuroscan-dev-salt` with a comment about overriding in production.

### Tests

- ~10 unit tests for `scan_phi` (each high-severity tag present, each medium-severity tag present, no PHI dataset, empty values, missing dataset, deterministic hash with fixed salt, different salt → different hash).
- 2 unit tests for the salted-hash helper.
- 3 integration tests: upload with PHI returns findings in response + persists `phi_findings` rows; upload without PHI returns total=0; `GET /api/audit/events/{id}/phi-findings` returns the right rows.
- 1 byte-equality CI check: `scripts/check-deid-scanner-drift.sh` asserts `services/api-service/app/services/deid/scanner.py` and `apps/desktop-viewer/app/deid/scanner.py` match.
- Desktop viewer: 3-4 unit tests for the metadata-panel highlight logic (mock dataset with PHI → red rows render).

### Docs

- New TC-10 in `docs/qa-validation-plan.md`: PHI detection on synthetic-with-PHI fixture; verify banner, audit detail, and desktop highlighting.
- README bullet: "PHI detection on every DICOM upload (DICOM PS3.15 Basic Confidentiality Profile) with severity classification and salted-SHA-256 value hashing."
- Status + roadmap updates as usual at the end.

## 6. Data model

### `phi_findings` table

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `id` | BigInt | PK, autoincrement | Surrogate key |
| `audit_event_id` | UUID | FK → `audit_events.event_id`, NOT NULL | One audit row → many findings |
| `tag` | String(9) | NOT NULL | DICOM tag in `gggg,eeee` format (e.g. `"0010,0010"`) |
| `tag_name` | String(64) | NOT NULL | Human-readable tag keyword (e.g. `"PatientName"`) |
| `severity` | String(8) | NOT NULL | `"high"` or `"medium"` |
| `value_sha256` | String(64) | NULL | Salted SHA-256 hex of the present value. Null if value was empty/missing. |
| `created_at` | DateTime(tz) | NOT NULL, default now() | |

Indexes:
- `idx_phi_findings_audit_event_id` on `audit_event_id`
- `idx_phi_findings_severity` on `severity`

No unique constraints — the same audit row can legitimately have multiple findings, and re-uploads of the same DICOM produce a new audit row + new findings rows (idempotency happens at the storage_objects layer, not here).

### `data/deid-rules.json` format

```json
{
  "version": "1.0",
  "source": "DICOM PS3.15 Basic Confidentiality Profile",
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

(The full PS3.15 list contains ~120 tags; we ship a clinically meaningful subset of ~25 to keep the slice focused. Spec note: "A future slice can expand this by adding more entries to the JSON — no code changes required.")

## 7. API contracts

### POST /api/dicom/upload (modified)

Response 201 `UploadResult`:
```typescript
{
  status: "uploaded",
  study_instance_uid: string,
  series_instance_uid: string,
  sop_instance_uid: string,
  orthanc_instance_id: string,
  checksum_sha256: string,
  phi_findings: {
    total: number,
    high: number,
    medium: number,
    items: Array<{
      tag: string,        // "0010,0010"
      tag_name: string,   // "PatientName"
      severity: "high" | "medium"
    }>
  }
}
```

### GET /api/audit/events/{event_id}/phi-findings

Response 200:
```typescript
{
  audit_event_id: string,
  total: number,
  high: number,
  medium: number,
  items: Array<{
    tag: string,
    tag_name: string,
    severity: "high" | "medium",
    value_sha256: string | null
  }>
}
```

Response 404 if audit event not found.

## 8. UI / UX

### Web upload success panel

When `phi_findings.total === 0`:
- Existing green success panel renders unchanged.

When `phi_findings.total > 0`:
- A new **yellow banner** appears above the existing green panel:
  > ⚠ PHI detected: **3 high-severity** identifiers, **4 medium-severity** identifiers found in this DICOM. The file was uploaded as-is.
- Below the banner, a small table:

| Tag | Name | Severity |
|---|---|---|
| 0010,0010 | PatientName | 🔴 high |
| 0010,0020 | PatientID | 🔴 high |
| 0010,0030 | PatientBirthDate | 🔴 high |
| 0008,0080 | InstitutionName | 🟡 medium |
| … | … | … |

No mockup file — implementation will use inline styles consistent with the existing upload page (Slice 1).

### Desktop viewer metadata panel

- Top of panel: a single-line summary in a colored box:
  > 🔴 3 high · 🟡 4 medium PHI tags detected
- Each row in the existing 18-row metadata table gets a background color:
  - High-severity PHI: light red (`#fee2e2`)
  - Medium-severity PHI: light amber (`#fef3c7`)
  - Non-PHI: default

The row layout doesn't change; only the row background does.

## 9. Performance

- Scanner is pure-Python iteration over a hash-set lookup of ~25 rules. For a typical DICOM dataset with a few hundred tags, scan time is < 5 ms.
- Salted SHA-256 of each present value is also negligible (< 1 ms per tag).
- Upload-orchestrator latency budget: existing path is ~50-200ms (validate + Orthanc + MinIO tee). Adding scanner brings p95 to ~55-205ms. Acceptable.
- No async / no thread pool. The scanner runs synchronously in the request handler.

## 10. Security

- **Salt**: `DEID_HASH_SALT` env var. Default in `.env.example` is `"neuroscan-dev-salt"` — explicit "dev only" comment. Production deployments must override. The salt is NEVER logged or returned in any API response.
- **No raw PHI in logs**: scanner uses `logging.debug` only for the tag count summary, never the value. The structured logger never receives the raw value.
- **No raw PHI in audit messages**: the audit row's `message` field is unchanged — it doesn't get the findings appended.
- **No raw PHI in API responses**: the `UploadResult.phi_findings.items` does NOT include `value_sha256`. Only `GET /api/audit/events/{id}/phi-findings` returns the hash, and that endpoint can be auth-gated in Slice 6.
- **Hash collision risk**: SHA-256 + salt → astronomically low. Acceptable for "did we see this value before?" comparison.

## 11. Risks and mitigations

| Risk | Mitigation |
|---|---|
| Scanner module duplication drifts between api-service and desktop-viewer | CI check (`scripts/check-deid-scanner-drift.sh`) does byte-equality assert on both files. PR fails if they differ. |
| `data/deid-rules.json` copied into desktop bundle gets out of sync | Same byte-equality check covers the desktop's `rules.json`. |
| PS3.15 rule list is incomplete (we ship a subset) | Documented as a deliberate limitation. Adding tags = JSON edit only, no code change. Spec calls it out. |
| Upload latency budget overrun on huge datasets (1000+ tags) | Performance budget verified in unit test with a fixture that creates a 1000-tag dataset. p95 < 50ms. |
| `phi_findings` table grows unboundedly | Same as `audit_events` — retention is a separate operational concern, not part of this slice. |
| `DEID_HASH_SALT` leaked via env dump endpoint or logs | Salt never written to logs; no env-dump endpoint exists; `/health` doesn't include settings. |
| A non-PHI DICOM tag added to the rules by mistake → false positive | Two-level taxonomy + clinical-reviewer-friendly tag list reduces the risk. PS3.15 source is authoritative. |
| User assumes "scanner passed → file is safe to share" | UI banner is explicitly "warn-only" worded. README + QA plan emphasize the scope. |

## 12. Definition of Done

- 91 (current) + ~16 (new) = ~107 tests passing
- Lint clean (ruff)
- TypeScript: typecheck + build clean
- Desktop viewer unit tests + lint clean
- Byte-equality drift check passes (CI green)
- Manual TC-10 from the QA plan passes
- Docs updated: `docs/status.md`, `docs/roadmap.md`, `docs/qa-validation-plan.md`, `README.md`, `.env.example`
- Branch pushed; ready for user review + merge

## 13. Open questions

None at spec time. Locked decisions cover all material choices. If implementation surfaces a surprise (e.g. a pydicom edge case with private tags), the deviation is recorded in `docs/status.md` per the established pattern.
