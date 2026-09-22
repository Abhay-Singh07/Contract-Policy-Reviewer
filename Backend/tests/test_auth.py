from app.config import settings
from app.core.auth import verify_api_key


def test_health_never_requires_api_key():
    """Health checks stay open — load balancers/monitoring shouldn't need a key."""
    from app.main import app
    from fastapi.testclient import TestClient
    client = TestClient(app)
    resp = client.get("/health")
    assert resp.status_code == 200


def test_documents_open_when_no_api_key_configured(clean_tables, monkeypatch):
    """Dev-mode default: no API_KEY configured means auth is disabled.
    Explicitly simulates this via monkeypatch, regardless of whatever the
    developer's real local .env happens to have set — this test must pass
    the same way on every machine."""
    from app.main import app
    app.dependency_overrides.pop(verify_api_key, None)  # exercise the real dependency, not the suite-wide bypass
    monkeypatch.setattr(settings, "API_KEY", "")

    from fastapi.testclient import TestClient
    client = TestClient(app)
    resp = client.get("/documents/")
    assert resp.status_code == 200


def test_documents_rejected_without_key_once_configured(clean_tables, monkeypatch):
    from app.main import app
    app.dependency_overrides.pop(verify_api_key, None)
    monkeypatch.setattr(settings, "API_KEY", "test-secret-key")

    from fastapi.testclient import TestClient
    client = TestClient(app)

    resp = client.get("/documents/")
    assert resp.status_code == 401

    resp = client.get("/documents/", headers={"X-API-Key": "wrong-key"})
    assert resp.status_code == 401

    resp = client.get("/documents/", headers={"X-API-Key": "test-secret-key"})
    assert resp.status_code == 200


def test_review_routes_also_gated(clean_tables, monkeypatch):
    """Confirms the review router picked up the same dependency, not just documents."""
    from app.main import app
    app.dependency_overrides.pop(verify_api_key, None)
    monkeypatch.setattr(settings, "API_KEY", "test-secret-key")

    from fastapi.testclient import TestClient
    client = TestClient(app)

    resp = client.post("/documents/some-fake-id/review")
    assert resp.status_code == 401  # rejected before it even gets to the 404-document-not-found check