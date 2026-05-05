from tests.fixtures.synthetic_dicom import make_synthetic_mr_dicom_bytes


async def test_studies_list_after_upload(api_client):
    raw = make_synthetic_mr_dicom_bytes()
    upload = await api_client.post(
        "/api/dicom/upload", files={"file": ("a.dcm", raw, "application/dicom")}
    )
    study_uid = upload.json()["study_instance_uid"]

    resp = await api_client.get("/api/studies")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] >= 1
    uids = [s["study_instance_uid"] for s in body["items"]]
    assert study_uid in uids


async def test_study_detail_returns_series(api_client):
    raw = make_synthetic_mr_dicom_bytes()
    upload = await api_client.post(
        "/api/dicom/upload", files={"file": ("a.dcm", raw, "application/dicom")}
    )
    study_uid = upload.json()["study_instance_uid"]

    resp = await api_client.get(f"/api/studies/{study_uid}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["study_instance_uid"] == study_uid
    assert len(body["series"]) == 1
    series_uid = body["series"][0]["series_instance_uid"]
    assert series_uid


async def test_series_instances_listed(api_client):
    raw = make_synthetic_mr_dicom_bytes()
    upload = await api_client.post(
        "/api/dicom/upload", files={"file": ("a.dcm", raw, "application/dicom")}
    )
    study_uid = upload.json()["study_instance_uid"]
    detail = await api_client.get(f"/api/studies/{study_uid}")
    series_uid = detail.json()["series"][0]["series_instance_uid"]

    resp = await api_client.get(f"/api/series/{series_uid}/instances")
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) == 1
    assert items[0]["sop_instance_uid"]
