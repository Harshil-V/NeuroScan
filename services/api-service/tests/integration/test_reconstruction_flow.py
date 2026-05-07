"""End-to-end reconstruction flow tests against real Postgres + Orthanc."""

import asyncio
from io import BytesIO

import numpy as np
import pytest

from app.services.reconstruction.forward_fft import dicom_to_kspace
from tests.fixtures.synthetic_dicom import make_synthetic_mr_dicom_bytes


def _build_npz_bytes(rows: int = 64, cols: int = 64) -> bytes:
    """Build a forward-generated .npz with kspace + ground truth in memory."""
    dicom_bytes = make_synthetic_mr_dicom_bytes(rows=rows, columns=cols)
    kspace, ground_truth = dicom_to_kspace(dicom_bytes)
    buf = BytesIO()
    np.savez(buf, kspace=kspace, ground_truth_image=ground_truth)
    return buf.getvalue()


def _build_npy_bytes(rows: int = 32, cols: int = 32) -> bytes:
    """Build a plain .npy (no ground truth)."""
    arr = np.ones((rows, cols), dtype=np.complex64)
    buf = BytesIO()
    np.save(buf, arr)
    return buf.getvalue()


async def _wait_for_terminal(api_client, job_id, timeout_s: float = 30.0) -> dict:
    """Poll GET /api/reconstruction/jobs/{job_id} until terminal status."""
    for _ in range(int(timeout_s * 5)):
        resp = await api_client.get(f"/api/reconstruction/jobs/{job_id}")
        assert resp.status_code == 200, resp.text
        body = resp.json()
        if body["status"] in ("completed", "failed"):
            return body
        await asyncio.sleep(0.2)
    pytest.fail(f"Job {job_id} did not reach terminal status within {timeout_s}s")


async def test_reconstruction_npz_with_ground_truth_completes_with_metrics(api_client, db_session):
    npz_bytes = _build_npz_bytes(rows=64, cols=64)
    response = await api_client.post(
        "/api/reconstruction/jobs",
        files={"file": ("brain.npz", npz_bytes, "application/octet-stream")},
    )
    assert response.status_code == 201, response.text
    job_id = response.json()["job_id"]
    assert response.json()["status"] == "queued"

    body = await _wait_for_terminal(api_client, job_id)
    assert body["status"] == "completed", body
    assert body["output_dicom_uid"] is not None
    assert body["output_orthanc_instance_id"] is not None
    assert body["psnr_db"] is not None
    assert body["ssim"] is not None
    # FFT round-trip is essentially lossless
    assert body["psnr_db"] > 60, f"PSNR={body['psnr_db']}"
    assert body["ssim"] > 0.95, f"SSIM={body['ssim']}"


async def test_reconstruction_npy_without_ground_truth_completes_without_metrics(
    api_client, db_session
):
    npy_bytes = _build_npy_bytes()
    response = await api_client.post(
        "/api/reconstruction/jobs",
        files={"file": ("plain.npy", npy_bytes, "application/octet-stream")},
    )
    assert response.status_code == 201
    job_id = response.json()["job_id"]

    body = await _wait_for_terminal(api_client, job_id)
    assert body["status"] == "completed", body
    assert body["psnr_db"] is None
    assert body["ssim"] is None
    assert body["output_dicom_uid"] is not None


async def test_reconstruction_garbage_returns_400(api_client):
    response = await api_client.post(
        "/api/reconstruction/jobs",
        files={"file": ("nope.npy", b"this is not a numpy file", "application/octet-stream")},
    )
    assert response.status_code == 400
    body = response.json()
    assert body["code"] == "invalid_kspace"


async def test_reconstruction_unsupported_extension_returns_400(api_client):
    response = await api_client.post(
        "/api/reconstruction/jobs",
        files={"file": ("data.txt", b"plain text", "text/plain")},
    )
    assert response.status_code == 400
    assert response.json()["code"] == "invalid_kspace"


async def test_reconstruction_jobs_list_returns_recent_jobs(api_client):
    npz_bytes = _build_npz_bytes(rows=32, cols=32)
    for i in range(3):
        resp = await api_client.post(
            "/api/reconstruction/jobs",
            files={"file": (f"j{i}.npz", npz_bytes, "application/octet-stream")},
        )
        assert resp.status_code == 201
        await _wait_for_terminal(api_client, resp.json()["job_id"])

    resp = await api_client.get("/api/reconstruction/jobs?limit=50")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] >= 3
    times = [item["created_at"] for item in body["items"]]
    assert times == sorted(times, reverse=True)
