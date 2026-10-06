from fastapi.testclient import TestClient

from paxrelay_simulator.main import create_app


def test_demo_provider_returns_stable_local_sample():
    with TestClient(create_app()) as client:
        response = client.post(
            "/demo-provider/search",
            json={"query": "PaxRelay demo"},
        )

    assert response.status_code == 200
    assert response.json()["query"] == "PaxRelay demo"
    assert response.json()["simulation"] is True


def test_demo_provider_rejects_invalid_query():
    with TestClient(create_app()) as client:
        response = client.post("/demo-provider/search", json={"query": ""})

    assert response.status_code == 422
