async def test_health_with_real_services(api_client):
    response = await api_client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["orthanc_reachable"] is True
    assert body["db_reachable"] is True
