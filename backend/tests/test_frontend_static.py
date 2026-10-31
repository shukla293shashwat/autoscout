"""Phase 9 tests: the FastAPI app serves the built SPA (when present) without
swallowing API/docs routes.

These tests are written to be safe whether or not frontend/dist exists:
  * When dist is present (CI build / Docker), `/` returns the HTML shell and
    SPA routes fall back to index.html.
  * /health, /api/*, /docs and /openapi.json always keep working.
"""
from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.main import FRONTEND_DIST, app

client = TestClient(app)
DIST_EXISTS = (FRONTEND_DIST / "index.html").is_file()


def test_health_always_json() -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_api_routes_are_not_swallowed_by_spa() -> None:
    # A bad upload_id still hits the API layer (200 empty list / 4xx), never HTML.
    resp = client.get("/api/artifacts", params={"upload_id": 123456})
    assert resp.status_code == 200
    assert resp.json() == []


def test_openapi_and_docs_still_available() -> None:
    assert client.get("/openapi.json").status_code == 200
    assert client.get("/docs").status_code == 200


def test_root_serves_spa_when_dist_present() -> None:
    if not DIST_EXISTS:
        # Dev without a build: root falls through to FastAPI's default 404.
        resp = client.get("/")
        assert resp.status_code in (200, 404)
        return
    resp = client.get("/")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert 'id="root"' in resp.text


def test_spa_route_falls_back_to_index_when_dist_present() -> None:
    if not DIST_EXISTS:
        return
    resp = client.get("/some/client/route")
    assert resp.status_code == 200
    assert 'id="root"' in resp.text


def test_served_asset_path_stays_within_dist() -> None:
    if not DIST_EXISTS:
        return
    # Traversal attempt must not escape the dist directory.
    resp = client.get("/../../etc/passwd")
    # FastAPI normalizes; either it 404s or serves index.html, never a real file.
    assert resp.status_code in (200, 404)
    assert "root:" not in resp.text
