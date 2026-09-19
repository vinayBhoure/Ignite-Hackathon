"""Signed-in TestClients for the static demo accounts."""

from fastapi.testclient import TestClient

DISPATCHER = {"role": "dispatcher", "identifier": "dispatch@aevora.in", "password": "aevora-dispatch"}
RIDER_1 = {"role": "rider", "identifier": "+91 99000 00001", "password": "aevora-rider"}
RIDER_2 = {"role": "rider", "identifier": "9900000002", "password": "aevora-rider"}


def signed_in(creds: dict) -> TestClient:
    from api.main import app

    client = TestClient(app)
    resp = client.post("/api/auth/login", json=creds)
    assert resp.status_code == 200, resp.text
    return client
