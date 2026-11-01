import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import create_app
from tests.synth import BODY, render, scan, to_bytes, words


@pytest.fixture(scope="module")
def client():
    with TestClient(create_app()) as c:
        yield c


def _upload(client, data: bytes, name: str = "scan.png", ctype: str = "image/png"):
    return client.post("/api/analyses", files={"file": (name, data, ctype)})


def test_health(client):
    assert client.get("/api/health").json() == {"status": "ok", "llm_enabled": False}


def test_full_lifecycle(client):
    raw = to_bytes(scan(render([words(l, "serif", 34) for l in BODY])))
    created = _upload(client, raw)
    assert created.status_code == 201
    body = created.json()
    assert body["filename"] == "scan.png" and body["status"] == "completed"

    detail = client.get(f"/api/analyses/{body['id']}").json()
    assert detail["result"]["label"] == detail["label"]
    assert detail["finding_count"] == len(detail["result"]["findings"])

    image = client.get(f"/api/analyses/{body['id']}/files/{detail['result']['pages'][0]['image']}")
    assert image.status_code == 200 and image.headers["content-type"] == "image/jpeg"
    assert client.get(f"/api/analyses/{body['id']}/files/../original.png").status_code == 404

    listing = client.get("/api/analyses", params={"q": "scan"}).json()
    assert listing["total"] >= 1 and listing["items"][0]["id"] == body["id"]
    assert client.get("/api/analyses", params={"q": "nomatch"}).json()["total"] == 0

    assert client.delete(f"/api/analyses/{body['id']}").status_code == 204
    assert client.get(f"/api/analyses/{body['id']}").status_code == 404


def test_rejects_unsupported_and_empty(client):
    assert _upload(client, b"hello world", "a.txt", "text/plain").status_code == 400
    assert _upload(client, b"", "a.png").status_code == 400


def test_rejects_oversized(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "max_upload_mb", 0)
    response = _upload(client, b"%PDF-1.4 tiny")
    assert response.status_code == 400 and "MB" in response.json()["detail"]


def test_broken_pdf_marks_failed(client):
    response = _upload(client, b"%PDF-1.4\nnot really a pdf", "x.pdf", "application/pdf")
    assert response.status_code == 201
    detail = client.get(f"/api/analyses/{response.json()['id']}").json()
    assert detail["status"] == "failed" and detail["error"]


def test_unknown_analysis_404(client):
    assert client.get("/api/analyses/does-not-exist").status_code == 404
