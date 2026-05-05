from tests.fixtures.synthetic_dicom import make_synthetic_mr_dicom_bytes


async def test_audit_orders_newest_first(api_client):
    for _ in range(3):
        await api_client.post(
            "/api/dicom/upload",
            files={
                "file": (
                    "a.dcm",
                    make_synthetic_mr_dicom_bytes(),
                    "application/dicom",
                )
            },
        )
    resp = await api_client.get("/api/audit/events")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 3
    times = [i["created_at"] for i in body["items"]]
    assert times == sorted(times, reverse=True)


async def test_audit_filter_by_status(api_client):
    await api_client.post(
        "/api/dicom/upload",
        files={
            "file": ("a.dcm", make_synthetic_mr_dicom_bytes(), "application/dicom")
        },
    )
    await api_client.post(
        "/api/dicom/upload", files={"file": ("b.txt", b"x", "text/plain")}
    )
    success = await api_client.get("/api/audit/events?status=success")
    failure = await api_client.get("/api/audit/events?status=failure")
    assert success.json()["total"] == 1
    assert failure.json()["total"] == 1
