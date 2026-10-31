"""Phase 7: shared test fixtures — DB isolation + one-time model warm-up.

Reliability:
  * Point the SQLite engine at a throwaway file per test session (via the
    AUTOSCOUT_DB_PATH env var, read by app.db at import time) so tests never
    mutate — and are never polluted by — the developer's backend/autoscout.db.
    This is set BEFORE any app module is imported, so every ``from app.db
    import SessionLocal`` in the test modules binds to the same isolated engine.

Speed:
  * Warm the sentence-transformers model once per session so the one-time load
    happens regardless of test order, and the embed cache is built once.
"""
from __future__ import annotations

import os
import tempfile

# Set the DB override BEFORE importing anything from the app package so
# app.db binds its engine to the temp file. (conftest is imported by pytest
# before any test module, so this runs first.)
_TEST_DB = os.path.join(tempfile.gettempdir(), "autoscout_test.db")
os.environ["AUTOSCOUT_DB_PATH"] = _TEST_DB

import pytest  # noqa: E402

from app import db as _db  # noqa: E402


def pytest_configure(config: pytest.Config) -> None:
    """Ensure the isolated DB file exists and tables are created once."""
    if os.path.exists(_TEST_DB):
        try:
            os.remove(_TEST_DB)
        except OSError:
            pass
    _db.init_db()


@pytest.fixture(scope="session", autouse=True)
def _warm_embedding_model() -> None:
    """Load the sentence-transformers model once per session (best effort)."""
    try:
        from app.services.discovery import _get_model

        _get_model()
    except Exception:  # pragma: no cover - warm-up is best-effort
        pass


@pytest.fixture()
def client():
    """TestClient wired to the shared FastAPI app (isolated DB)."""
    from fastapi.testclient import TestClient

    from app.main import app

    return TestClient(app)


@pytest.fixture()
def db():
    """A DB session bound to the isolated engine, closed after the test."""
    session = _db.SessionLocal()
    try:
        yield session
    finally:
        session.close()
