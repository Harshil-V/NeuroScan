"""End-to-end MinIO storage tests against real Postgres + Orthanc + MinIO."""

import asyncio
from io import BytesIO

import httpx
import numpy as np
import pytest

from app.services.reconstruction.forward_fft import dicom_to_kspace
from tests.fixtures.synthetic_dicom import make_synthetic_mr_dicom_bytes


def _build_npz_bytes(rows: int = 64, cols: int = 64) -> bytes:
    dicom_bytes = make_synthetic_mr_dicom_bytes(rows=rows, columns=cols)
    kspace, ground_truth = dicom_to_kspace(dicom_bytes)
    buf = BytesIO()
    np.savez(buf, kspace=kspace, ground_truth_image=ground_truth)
    return buf.getvalue()


async def _wait_for_terminal(api_client, job_id, timeout_s: float = 30.0) -> dict:
    for _ in range(int(timeout_s * 5)):
        resp = await api_client.get(f"/api/reconstruction/jobs/{job_id}")
        body = resp.json()
        if body["status"] in ("completed", "failed"):
            return body
        await asyncio.sleep(0.2)
    pytest.fail(f"Job {job_id} did not reach terminal status within {timeout_s}s")


async def test_dicom_upload_creates_storage_object(api_client):
    raw = make_synthetic_mr_dicom_bytes()
    upload = await api_client.post(
        "/api/dicom/upload", files={"file": ("a.dcm", raw, "application/dicom")}
    )
    assert upload.status_code == 201, upload.text
    sha = upload.json()["checksum_sha256"]

    # storage_object should exist with matching sha256 and source
    storage = await api_client.get(f"/api/storage/objects?sha256={sha}")
    body = storage.json()
    assert body["total"] == 1
    obj = body["items"][0]
    assert obj["source"] == "dicom_upload"
    assert obj["sha256"] == sha
    assert obj["object_key"].startswith("dicom/")
    assert obj["bucket"] == "neuroscan-test"


async def test_dicom_upload_audit_status_is_success_when_minio_ok(api_client):
    raw = make_synthetic_mr_dicom_bytes()
    await api_client.post("/api/dicom/upload", files={"file": ("a.dcm", raw, "application/dicom")})
    audit = await api_client.get("/api/audit/events?limit=1")
    body = audit.json()
    assert body["items"][0]["status"] == "success"


async def test_reconstruction_creates_storage_object(api_client):
    npz_bytes = _build_npz_bytes()
    upload = await api_client.post(
        "/api/reconstruction/jobs",
        files={"file": ("brain.npz", npz_bytes, "application/octet-stream")},
    )
    job_id = upload.json()["job_id"]
    await _wait_for_terminal(api_client, job_id)

    storage = await api_client.get("/api/storage/objects?source=reconstruction_output")
    body = storage.json()
    assert body["total"] >= 1
    assert all(item["source"] == "reconstruction_output" for item in body["items"])


async def test_presigned_url_returns_original_bytes(api_client):
    raw = make_synthetic_mr_dicom_bytes()
    upload = await api_client.post(
        "/api/dicom/upload", files={"file": ("a.dcm", raw, "application/dicom")}
    )
    sha = upload.json()["checksum_sha256"]

    storage = await api_client.get(f"/api/storage/objects?sha256={sha}")
    obj_id = storage.json()["items"][0]["id"]

    presigned = await api_client.get(f"/api/storage/objects/{obj_id}/presigned-url?expires=300")
    url = presigned.json()["url"]

    # Fetch the URL directly (NOT through api-service ASGI transport)
    async with httpx.AsyncClient() as client:
        r = await client.get(url)
    assert r.status_code == 200
    assert r.content == raw


async def test_health_reports_minio_reachable(api_client):
    resp = await api_client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["minio_reachable"] is True
    assert body["status"] == "ok"
