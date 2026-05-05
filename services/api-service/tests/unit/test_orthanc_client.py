import httpx
import pytest
import respx

from app.clients.orthanc import OrthancClient, OrthancError


@pytest.fixture
def client() -> OrthancClient:
    return OrthancClient(base_url="http://orthanc:8042", user="u", password="p")


@respx.mock
async def test_upload_instance_returns_id(client: OrthancClient):
    route = respx.post("http://orthanc:8042/instances").respond(
        200, json={"ID": "abc-123", "Status": "Success"}
    )
    instance_id = await client.upload_instance(b"fake-dicom-bytes")
    assert instance_id == "abc-123"
    assert route.called


@respx.mock
async def test_upload_instance_raises_on_4xx(client: OrthancClient):
    respx.post("http://orthanc:8042/instances").respond(400, text="bad dicom")
    with pytest.raises(OrthancError):
        await client.upload_instance(b"x")


@respx.mock
async def test_upload_instance_retries_on_5xx_then_succeeds(client: OrthancClient):
    respx.post("http://orthanc:8042/instances").mock(
        side_effect=[
            httpx.Response(503),
            httpx.Response(503),
            httpx.Response(200, json={"ID": "ok-1"}),
        ]
    )
    instance_id = await client.upload_instance(b"x")
    assert instance_id == "ok-1"


@respx.mock
async def test_upload_instance_raises_after_retries_exhausted(client: OrthancClient):
    respx.post("http://orthanc:8042/instances").respond(500)
    with pytest.raises(OrthancError):
        await client.upload_instance(b"x")


@respx.mock
async def test_get_studies_returns_list(client: OrthancClient):
    respx.get("http://orthanc:8042/studies").respond(
        200, json=["s1", "s2"]
    )
    respx.get("http://orthanc:8042/studies/s1").respond(
        200, json={"ID": "s1", "MainDicomTags": {"StudyInstanceUID": "1.2.3"}, "Series": []}
    )
    respx.get("http://orthanc:8042/studies/s2").respond(
        200, json={"ID": "s2", "MainDicomTags": {"StudyInstanceUID": "4.5.6"}, "Series": []}
    )
    studies = await client.list_studies()
    assert {s["ID"] for s in studies} == {"s1", "s2"}


@respx.mock
async def test_get_preview_passes_through_bytes(client: OrthancClient):
    respx.get("http://orthanc:8042/instances/abc/preview").respond(
        200, content=b"\x89PNG-fake", headers={"Content-Type": "image/png"}
    )
    content, content_type = await client.get_instance_preview("abc")
    assert content == b"\x89PNG-fake"
    assert content_type == "image/png"
