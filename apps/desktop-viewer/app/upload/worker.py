"""Background DICOM upload to the api-service.

`do_upload` is the pure-function core (httpx, no Qt) — unit-tested with respx.
`UploadWorker` is a thin QThread wrapper that emits Qt signals.
"""

from __future__ import annotations

import httpx
from PySide6.QtCore import QThread, Signal


class UploadError(Exception):
    """Raised when the api-service rejects the upload or is unreachable."""


def do_upload(
    *,
    api_url: str,
    dicom_bytes: bytes,
    sop_uid: str,
    timeout: float = 30.0,
) -> dict:
    base = api_url.rstrip("/")
    url = f"{base}/api/dicom/upload"
    files = {"file": (f"{sop_uid}.dcm", dicom_bytes, "application/dicom")}
    try:
        with httpx.Client(timeout=timeout) as client:
            response = client.post(url, files=files)
    except httpx.ConnectError as exc:
        raise UploadError(f"Could not reach api-service at {base}: {exc}") from exc
    except httpx.HTTPError as exc:
        raise UploadError(f"HTTP error talking to api-service: {exc}") from exc

    if response.status_code >= 400:
        try:
            body = response.json()
            code = body.get("code", "error")
            detail = body.get("detail", response.text)
            raise UploadError(f"{code}: {detail}")
        except ValueError:
            raise UploadError(
                f"api-service returned {response.status_code}: {response.text}"
            ) from None
    return response.json()


class UploadWorker(QThread):
    succeeded = Signal(dict)
    failed = Signal(str)

    def __init__(
        self,
        api_url: str,
        dicom_bytes: bytes,
        sop_uid: str,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._api_url = api_url
        self._bytes = dicom_bytes
        self._sop_uid = sop_uid

    def run(self) -> None:
        try:
            result = do_upload(
                api_url=self._api_url,
                dicom_bytes=self._bytes,
                sop_uid=self._sop_uid,
            )
        except UploadError as exc:
            self.failed.emit(str(exc))
            return
        except Exception as exc:  # noqa: BLE001 — defensive in a worker thread
            self.failed.emit(f"Unexpected: {exc}")
            return
        self.succeeded.emit(result)
