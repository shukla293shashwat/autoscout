"""Phase 4 tests: ROI-aware workflow endpoints (sorted list + summary)."""
from __future__ import annotations

import json

from fastapi.testclient import TestClient

from app.db import init_db
from app.main import app

client = TestClient(app)


def _seed_workflows() -> int:
    """Insert a fresh upload + 3 workflows with known ROI inputs."""
    from app.db import SessionLocal
    from app.models import Upload, Workflow

    init_db()
    db = SessionLocal()
    up = Upload(filename="roi-test", is_sample=0)
    db.add(up)
    db.flush()
    specs = [
        # (name, minutes, occurrences, feasibility)
        ("Low saver", 10, 5, "low"),
        ("Big saver", 25, 5, "high"),
        ("No time", 0, 5, "high"),
    ]
    for name, mins, occ, feas in specs:
        db.add(Workflow(
            upload_id=up.id,
            name=name,
            description="d",
            trigger="t",
            steps=json.dumps(["s"]),
            minutes_per_occurrence=mins,
            occurrences=occ,
            feasibility=feas,
            evidence=json.dumps(["E1"]),
            status="discovered",
        ))
    db.commit()
    uid = up.id
    db.close()
    return uid


def test_workflows_sorted_by_priority_desc() -> None:
    uid = _seed_workflows()
    resp = client.get("/api/workflows", params={"upload_id": uid})
    assert resp.status_code == 200, resp.text
    rows = resp.json()
    assert len(rows) == 3
    priorities = [r["priority_score"] for r in rows]
    assert priorities == sorted(priorities, reverse=True), priorities
    # Biggest saver (25 min, high) must come first.
    assert rows[0]["name"] == "Big saver"
    assert rows[0]["priority_score"] > rows[-1]["priority_score"]


def test_workflows_rows_carry_roi_fields() -> None:
    uid = _seed_workflows()
    rows = client.get("/api/workflows", params={"upload_id": uid}).json()
    for r in rows:
        assert "hours_saved_per_week" in r
        assert "occurrences_per_week" in r
        assert "priority_score" in r
        assert "roi_explanation" in r


def test_summary_returns_totals() -> None:
    uid = _seed_workflows()
    resp = client.get("/api/summary", params={"upload_id": uid})
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["workflow_count"] == 3
    assert data["total_hours_saved_per_week"] > 0
    # Summary totals must equal the sum of the ranked rows.
    rows = client.get("/api/workflows", params={"upload_id": uid}).json()
    summed = sum(r["hours_saved_per_week"] for r in rows)
    assert abs(data["total_hours_saved_per_week"] - summed) < 0.01
    assert "by_feasibility" in data
