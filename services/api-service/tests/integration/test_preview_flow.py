from tests.fixtures.synthetic_dicom import make_synthetic_mr_dicom_bytes


async def test_preview_returns_png(api_client):
    upload = await api_client.post(
        "/api/dicom/upload",
        files={
            "file": ("a.dcm", make_synthetic_mr_dicom_bytes(), "application/dicom")
        },
    )
    instance_id = upload.json()["orthanc_instance_id"]
    resp = await api_client.get(f"/api/instances/{instance_id}/preview.png")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("image/")
    assert len(resp.content) > 0


async def test_preview_404_for_unknown(api_client):
    resp = await api_client.get("/api/instances/does-not-exist/preview.png")
    assert resp.status_code == 404
