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

    # No raw values or hashes in the summary response
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


async def test_upload_without_phi_returns_well_formed_findings(api_client):
    # The default synthetic fixture has PatientName + PatientID + StudyDate etc.
    # (always some PHI hits). Verify the structure is correct.
    raw = make_synthetic_mr_dicom_bytes()
    resp = await api_client.post(
        "/api/dicom/upload",
        files={"file": ("a.dcm", raw, "application/dicom")},
    )
    body = resp.json()
    assert "phi_findings" in body
    assert isinstance(body["phi_findings"]["total"], int)
    assert body["phi_findings"]["total"] >= 1
    assert all(item["severity"] in {"high", "medium"} for item in body["phi_findings"]["items"])


async def test_phi_findings_404_for_unknown_event(api_client):
    bogus = "00000000-0000-0000-0000-000000000000"
    resp = await api_client.get(f"/api/audit/events/{bogus}/phi-findings")
    assert resp.status_code == 404
