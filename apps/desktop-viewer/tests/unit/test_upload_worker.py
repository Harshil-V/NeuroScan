import httpx
import pytest
import respx

from app.upload.worker import UploadError, do_upload


@respx.mock
def test_do_upload_happy_path():
    respx.post("http://localhost:8000/api/dicom/upload").respond(
        201,
        json={
            "status": "uploaded",
            "study_instance_uid": "1.2.3",
            "series_instance_uid": "1.2.4",
            "sop_instance_uid": "1.2.5",
            "orthanc_instance_id": "abc",
            "checksum_sha256": "deadbeef" * 8,
        },
    )
    result = do_upload(
        api_url="http://localhost:8000",
        dicom_bytes=b"fake-dicom",
        sop_uid="1.2.5",
    )
    assert result["orthanc_instance_id"] == "abc"
    assert result["checksum_sha256"].startswith("deadbeef")


@respx.mock
def test_do_upload_invalid_dicom_raises_with_code():
    respx.post("http://localhost:8000/api/dicom/upload").respond(
        400, json={"detail": "bad bytes", "code": "invalid_dicom"}
    )
    with pytest.raises(UploadError) as exc:
        do_upload(api_url="http://localhost:8000", dicom_bytes=b"x", sop_uid="1.2.5")
    assert "invalid_dicom" in str(exc.value)


@respx.mock
def test_do_upload_5xx_raises():
    respx.post("http://localhost:8000/api/dicom/upload").respond(500, text="boom")
    with pytest.raises(UploadError):
        do_upload(api_url="http://localhost:8000", dicom_bytes=b"x", sop_uid="1.2.5")


@respx.mock
def test_do_upload_connect_error_raises():
    respx.post("http://localhost:8000/api/dicom/upload").mock(
        side_effect=httpx.ConnectError("connection refused")
    )
    with pytest.raises(UploadError) as exc:
        do_upload(api_url="http://localhost:8000", dicom_bytes=b"x", sop_uid="1.2.5")
    assert "Could not reach" in str(exc.value)


@respx.mock
def test_do_upload_strips_trailing_slash_from_api_url():
    respx.post("http://localhost:8000/api/dicom/upload").respond(
        201,
        json={
            "status": "uploaded",
            "study_instance_uid": "x",
            "series_instance_uid": "x",
            "sop_instance_uid": "x",
            "orthanc_instance_id": "x",
            "checksum_sha256": "x" * 64,
        },
    )
    result = do_upload(api_url="http://localhost:8000/", dicom_bytes=b"x", sop_uid="1.2.5")
    assert result["orthanc_instance_id"] == "x"
