"""Phase 5 tests: automation plan / dry-run / execute / audit routers."""
from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.db import init_db
from app.main import app

client = TestClient(app)


def _seed_workflow() -> tuple[int, int]:
    """Create a fresh upload + one email-dominant workflow; return (upload_id, wf_id)."""
    from app.db import SessionLocal
    from app.models import Artifact, Upload, Workflow

    init_db()
    db = SessionLocal()
    up = Upload(filename="auto-test", is_sample=0)
    db.add(up)
    db.flush()
    # Two status emails so the workflow is email-dominant (triggers the
    # summarize->draft plan template).
    for i, ref in enumerate(["E001", "E002"], start=1):
        db.add(Artifact(
            upload_id=up.id, kind="email", source_ref=ref,
            title="Weekly Pipeline Status", text=f"Status email {i}",
            raw_json=json.dumps({"labels": "sent", "subject": "Weekly Pipeline Status", "body": "body"}),
        ))
    wf = Workflow(
        upload_id=up.id, name="Weekly Pipeline Status", description="d",
        trigger="Friday", steps=json.dumps(["summarize", "draft"]),
        minutes_per_occurrence=25, occurrences=5, feasibility="high",
        evidence=json.dumps(["E001", "E002"]), status="discovered",
    )
    db.add(wf)
    db.commit()
    uid, wid = up.id, wf.id
    db.close()
    return uid, wid


def test_generate_plan_returns_whitelisted_steps() -> None:
    _, wid = _seed_workflow()
    resp = client.post(f"/api/workflows/{wid}/plan")
    assert resp.status_code == 200, resp.text
    plan = resp.json()
    assert plan["name"]
    allowed = {"append_csv_row", "draft_email", "create_task", "summarize_table"}
    for step in plan["steps"]:
        assert step["tool"] in allowed, step["tool"]


def test_dry_run_produces_preview_and_no_files() -> None:
    _, wid = _seed_workflow()
    from app.services.automation import OUTPUT_DIR
    drafts = OUTPUT_DIR / "drafts"
    before = set(drafts.glob("*.txt")) if drafts.exists() else set()

    resp = client.post(f"/api/workflows/{wid}/dry-run")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["mode"] == "dry_run"
    assert data["step_results"], "expected step previews"
    for r in data["step_results"]:
        assert r["dry_run"] is True

    # Dry run must not add any new draft files (zero side effects).
    after = set(drafts.glob("*.txt")) if drafts.exists() else set()
    assert after == before, "dry run must not create draft files"


def test_execute_without_approval_rejected() -> None:
    _, wid = _seed_workflow()
    # Missing approval.
    assert client.post(f"/api/workflows/{wid}/execute").status_code == 400
    # approved=False.
    resp = client.post(f"/api/workflows/{wid}/execute",
                       json={"approved": False, "approver": "Maya"})
    assert resp.status_code == 400
    # Missing approver name.
    resp = client.post(f"/api/workflows/{wid}/execute", json={"approved": True})
    assert resp.status_code == 400


def test_execute_with_approval_writes_file_and_audit() -> None:
    _, wid = _seed_workflow()
    resp = client.post(f"/api/workflows/{wid}/execute",
                       json={"approved": True, "approver": "Maya Rao"})
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["mode"] == "executed"
    assert data["status"] in ("ok", "partial", "error")
    # The drafted status email must exist on disk.
    from app.services.automation import OUTPUT_DIR
    drafts = list((OUTPUT_DIR / "drafts").glob("*.txt"))
    assert drafts, "expected a drafted email file after execute"
    # An audit entry must be recorded.
    audit = client.get("/api/audit").json()
    assert audit, "expected at least one audit log entry"
    assert any(a["workflow_id"] == wid and a["mode"] == "executed" for a in audit)


def test_audit_endpoint_lists_runs_with_details() -> None:
    _, wid = _seed_workflow()
    client.post(f"/api/workflows/{wid}/dry-run")
    audit = client.get("/api/audit").json()
    assert len(audit) >= 1
    entry = audit[0]
    assert entry["workflow_id"] == wid
    assert entry["mode"] == "dry_run"
    assert "step_results" in entry
    assert "started_at" in entry
