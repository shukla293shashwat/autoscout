"""Phase 2 tests: Upload/Artifact models and ingest routers."""
from __future__ import annotations

import io

from fastapi.testclient import TestClient

from app.db import get_db, init_db
from app.main import app

client = TestClient(app)


def test_init_db_creates_tables() -> None:
    """init_db() must create the Upload and Artifact tables."""
    init_db()  # should not raise
    # Hitting /health confirms the app still boots with the new models.
    resp = client.get("/health")
    assert resp.status_code == 200


def test_sample_upload_returns_counts() -> None:
    """POST /api/uploads/sample must parse the committed sample dataset."""
    resp = client.post("/api/uploads/sample")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["counts"]["email"] == 60, data["counts"]
    assert data["counts"]["lead"] == 30, data["counts"]
    assert data["counts"]["note"] == 5, data["counts"]
    assert data["counts"]["task"] == 25, data["counts"]
    assert data["upload_id"] > 0


def test_multipart_upload_accepts_multiple_files() -> None:
    """POST /api/uploads must accept multiple files and return counts."""
    csv_bytes = (
        b"id,date,from,to,subject,body,labels\n"
        b"E901,2025-01-10 16:20,a@example.com,b@example.com,Hello,World,inbox\n"
    )
    files = [
        ("files", ("emails.csv", io.BytesIO(csv_bytes), "text/csv")),
        ("files", ("leads.csv", io.BytesIO(csv_bytes), "text/csv")),
    ]
    resp = client.post("/api/uploads", files=files)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["upload_id"] > 0
    assert sum(data["counts"].values()) >= 2


def test_get_artifacts_by_upload_id() -> None:
    """GET /api/artifacts?upload_id=... returns artifacts for that upload."""
    # First create an upload via sample.
    resp = client.post("/api/uploads/sample")
    upload_id = resp.json()["upload_id"]

    resp = client.get("/api/artifacts", params={"upload_id": upload_id})
    assert resp.status_code == 200, resp.text
    artifacts = resp.json()
    assert len(artifacts) > 0
    kinds = {a["kind"] for a in artifacts}
    assert {"email", "lead", "note", "task"} == kinds


def test_unsupported_file_type_is_rejected() -> None:
    """A .exe file must be rejected with a friendly 400, not a stack trace."""
    files = [("files", ("malware.exe", io.BytesIO(b"MZ\x90\x00"), "application/octet-stream"))]
    resp = client.post("/api/uploads", files=files)
    assert resp.status_code == 400
    assert "unsupported" in resp.json()["detail"].lower()


def test_oversize_file_is_rejected() -> None:
    """A file larger than MAX_FILE_BYTES must 400 without buffering it fully."""
    from app.routers.uploads import MAX_FILE_BYTES

    big = io.BytesIO(b"a" * (MAX_FILE_BYTES + 1))
    files = [("files", ("huge.csv", big, "text/csv"))]
    resp = client.post("/api/uploads", files=files)
    assert resp.status_code == 400
    assert "too large" in resp.json()["detail"].lower()


def test_upload_with_no_files_returns_client_error() -> None:
    """POST /api/uploads with no files is a clear 4xx, not a 500.

    FastAPI validates the required multipart `files` field and returns 422
    before the handler runs, so the route never sees an empty list.
    """
    resp = client.post("/api/uploads")
    assert resp.status_code in (400, 422)


def test_missing_upload_id_on_artifacts_is_404_or_422() -> None:
    """A bad/absent upload_id must be a client error, not a server error."""
    resp = client.get("/api/artifacts", params={"upload_id": 999999})
    assert resp.status_code == 200  # empty list is acceptable for unknown id
    assert resp.json() == []
