import asyncio
from typing import Any

import httpx


class OrthancError(Exception):
    """Raised when Orthanc returns an unexpected response."""


class OrthancClient:
    """Thin async httpx client for Orthanc REST API."""

    def __init__(
        self,
        base_url: str,
        user: str,
        password: str,
        *,
        timeout: float = 30.0,
        max_retries: int = 3,
        retry_backoff_seconds: float = 0.5,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._auth = (user, password)
        self._timeout = timeout
        self._max_retries = max_retries
        self._retry_backoff_seconds = retry_backoff_seconds

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(base_url=self._base_url, auth=self._auth, timeout=self._timeout)

    async def _request_with_retries(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        last_exc: Exception | None = None
        for attempt in range(self._max_retries):
            try:
                async with self._client() as client:
                    response = await client.request(method, path, **kwargs)
                if 500 <= response.status_code < 600:
                    last_exc = OrthancError(f"Orthanc {response.status_code} on {method} {path}")
                    if attempt < self._max_retries - 1:
                        await asyncio.sleep(self._retry_backoff_seconds * (2**attempt))
                        continue
                    raise last_exc
                return response
            except httpx.HTTPError as exc:
                last_exc = OrthancError(str(exc))
                if attempt < self._max_retries - 1:
                    await asyncio.sleep(self._retry_backoff_seconds * (2**attempt))
                    continue
                raise last_exc from exc
        assert last_exc is not None
        raise last_exc

    async def upload_instance(self, dicom_bytes: bytes) -> str:
        response = await self._request_with_retries(
            "POST",
            "/instances",
            content=dicom_bytes,
            headers={"Content-Type": "application/dicom"},
        )
        if response.status_code >= 400:
            raise OrthancError(f"Orthanc rejected upload: {response.status_code} {response.text}")
        body = response.json()
        instance_id = body.get("ID")
        if not instance_id:
            raise OrthancError(f"Orthanc upload missing ID in response: {body}")
        return instance_id

    async def list_studies(self) -> list[dict[str, Any]]:
        response = await self._request_with_retries("GET", "/studies")
        ids: list[str] = response.json()
        studies: list[dict[str, Any]] = []
        for sid in ids:
            detail = await self._request_with_retries("GET", f"/studies/{sid}")
            studies.append(detail.json())
        return studies

    async def get_study(self, orthanc_study_id: str) -> dict[str, Any]:
        response = await self._request_with_retries("GET", f"/studies/{orthanc_study_id}")
        if response.status_code == 404:
            raise OrthancError(f"Study {orthanc_study_id} not found")
        return response.json()

    async def get_series(self, orthanc_series_id: str) -> dict[str, Any]:
        response = await self._request_with_retries("GET", f"/series/{orthanc_series_id}")
        return response.json()

    async def find_study_by_uid(self, study_instance_uid: str) -> str | None:
        response = await self._request_with_retries(
            "POST",
            "/tools/find",
            json={
                "Level": "Study",
                "Query": {"StudyInstanceUID": study_instance_uid},
            },
        )
        ids = response.json()
        return ids[0] if ids else None

    async def find_series_by_uid(self, series_instance_uid: str) -> str | None:
        response = await self._request_with_retries(
            "POST",
            "/tools/find",
            json={
                "Level": "Series",
                "Query": {"SeriesInstanceUID": series_instance_uid},
            },
        )
        ids = response.json()
        return ids[0] if ids else None

    async def get_instance(self, orthanc_instance_id: str) -> dict[str, Any]:
        response = await self._request_with_retries("GET", f"/instances/{orthanc_instance_id}")
        return response.json()

    async def get_instance_preview(self, orthanc_instance_id: str) -> tuple[bytes, str]:
        response = await self._request_with_retries(
            "GET", f"/instances/{orthanc_instance_id}/preview"
        )
        if response.status_code == 404:
            raise OrthancError(f"Instance {orthanc_instance_id} preview not found")
        return response.content, response.headers.get("Content-Type", "image/png")

    async def system(self) -> dict[str, Any]:
        response = await self._request_with_retries("GET", "/system")
        return response.json()
