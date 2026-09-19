"""T1.3 validation: /health returns 200, /docs renders, errors use the envelope."""

from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)


def test_health_ok():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_docs_renders():
    resp = client.get("/docs")
    assert resp.status_code == 200


def test_404_uses_error_envelope():
    resp = client.get("/does-not-exist")
    assert resp.status_code == 404
    body = resp.json()
    assert body["error"]["code"] == "http_404"
