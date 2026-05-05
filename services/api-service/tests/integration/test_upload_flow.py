from tests.fixtures.synthetic_dicom import (
    make_dicom_missing_modality,
    make_synthetic_mr_dicom_bytes,
)


async def test_upload_happy_path(api_client, db_session):
    raw = make_synthetic_mr_dicom_bytes()
    response = await api_client.post(
        "/api/dicom/upload", files={"file": ("test.dcm", raw, "application/dicom")}
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] == "uploaded"
    assert body["orthanc_instance_id"]
    assert len(body["checksum_sha256"]) == 64

    audit = await api_client.get("/api/audit/events")
    assert audit.status_code == 200
    items = audit.json()["items"]
    assert any(i["status"] == "success" for i in items)


async def test_upload_garbage_returns_400(api_client):
    response = await api_client.post(
        "/api/dicom/upload",
        files={"file": ("nope.txt", b"hello world", "text/plain")},
    )
    assert response.status_code == 400
    body = response.json()
    assert body["code"] == "invalid_dicom"
    assert isinstance(body["detail"], str)


async def test_upload_missing_modality_returns_400(api_client):
    raw = make_dicom_missing_modality()
    response = await api_client.post(
        "/api/dicom/upload", files={"file": ("nm.dcm", raw, "application/dicom")}
    )
    assert response.status_code == 400
    assert response.json()["code"] == "missing_required_tag"


async def test_failure_writes_audit_row(api_client):
    await api_client.post("/api/dicom/upload", files={"file": ("nope.txt", b"x", "text/plain")})
    audit = await api_client.get("/api/audit/events?status=failure")
    assert audit.json()["total"] == 1
