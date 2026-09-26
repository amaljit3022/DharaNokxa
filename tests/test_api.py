from fastapi.testclient import TestClient

from api.main import app


def test_health_and_existing_demo():
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["engine"] == "EPANET 2.2 through WNTR"
    demo = client.get("/demo")
    assert demo.status_code == 200
    assert demo.json()["status"] == "PASS"
