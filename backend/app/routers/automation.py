"""Phase 5: automation plan / dry-run / execute / audit routers."""
from __future__ import annotations

import json
import logging
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Artifact, AuditLog, Workflow
from app.services.automation import AutomationError, AutomationPlan, generate_plan, run_plan

logger = logging.getLogger("autoscout.automation.router")

router = APIRouter(prefix="/api", tags=["automation"])

RECIPIENT = "leadership@example.com"


class ExecuteRequest(BaseModel):
    """Approval gate: execution requires an explicit human approval.

    Fields default so a missing/empty body reaches the handler (which returns a
    friendly 400) instead of FastAPI's generic 422.
    """

    approved: bool = False
    approver: str = ""


def _load_workflow(db: Session, workflow_id: int) -> tuple[Workflow, list[Artifact]]:
    wf = db.get(Workflow, workflow_id)
    if wf is None:
        raise HTTPException(status_code=404, detail="Workflow not found.")
    rows = (
        db.query(Artifact)
        .filter(Artifact.upload_id == wf.upload_id)
        .order_by(Artifact.id)
        .all()
    )
    return wf, rows


def _workflow_dict(wf: Workflow) -> dict:
    return {
        "id": wf.id,
        "upload_id": wf.upload_id,
        "name": wf.name,
        "description": wf.description,
        "trigger": wf.trigger,
        "evidence": json.loads(wf.evidence or "[]"),
        "occurrences": wf.occurrences,
        "minutes_per_occurrence": wf.minutes_per_occurrence,
        "feasibility": wf.feasibility,
    }


def _audit(
    db: Session,
    workflow_id: int,
    mode: str,
    approved_by: str,
    step_results: list[dict],
    status: str,
    started_at: datetime,
) -> AuditLog:
    entry = AuditLog(
        workflow_id=workflow_id,
        mode=mode,
        approved_by=approved_by,
        started_at=started_at,
        finished_at=datetime.now(UTC),
        step_results=json.dumps(step_results, ensure_ascii=False, default=str),
        status=status,
    )
    db.add(entry)
    db.commit()
    return entry


def _overall_status(results: list[dict]) -> str:
    if not results:
        return "ok"
    if all(r.get("status") == "ok" for r in results):
        return "ok"
    if any(r.get("status") == "ok" for r in results):
        return "partial"
    return "error"


@router.post("/workflows/{workflow_id}/plan")
def create_plan(workflow_id: int, db: Session = Depends(get_db)) -> dict:
    """Generate a declarative AutomationPlan for a workflow."""
    wf, artifacts = _load_workflow(db, workflow_id)
    try:
        plan: AutomationPlan = generate_plan(
            _workflow_dict(wf), artifacts=artifacts, recipient=RECIPIENT
        )
    except AutomationError as exc:
        raise HTTPException(status_code=422, detail=f"Could not build a valid plan: {exc}")
    return plan.model_dump()


@router.post("/workflows/{workflow_id}/dry-run")
def dry_run(workflow_id: int, db: Session = Depends(get_db)) -> dict:
    """Run the plan in dry-run mode: per-step previews, zero side effects."""
    wf, artifacts = _load_workflow(db, workflow_id)
    plan = generate_plan(_workflow_dict(wf), artifacts=artifacts, recipient=RECIPIENT)
    started = datetime.now(UTC)
    try:
        results = run_plan(plan, inputs={}, dry_run=True)
    except AutomationError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    status = _overall_status(results)
    _audit(db, workflow_id, "dry_run", "", results, status, started)
    return {
        "workflow_id": workflow_id,
        "mode": "dry_run",
        "plan": plan.model_dump(),
        "step_results": results,
        "status": status,
    }


@router.post("/workflows/{workflow_id}/execute")
def execute(
    workflow_id: int, req: ExecuteRequest | None = None, db: Session = Depends(get_db)
) -> dict:
    """Execute a plan. REQUIRES explicit approval; rejects otherwise."""
    req = req or ExecuteRequest()
    if not req.approved:
        raise HTTPException(status_code=400, detail="Execution requires approval (approved=true).")
    if not req.approver or not req.approver.strip():
        raise HTTPException(status_code=400, detail="Execution requires an approver name.")

    wf, artifacts = _load_workflow(db, workflow_id)
    plan = generate_plan(_workflow_dict(wf), artifacts=artifacts, recipient=RECIPIENT)
    started = datetime.now(UTC)
    try:
        results = run_plan(plan, inputs={}, dry_run=False)
    except AutomationError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    status = _overall_status(results)
    _audit(db, workflow_id, "executed", req.approver.strip(), results, status, started)

    outputs = [r.get("path") for r in results if r.get("path") and not r.get("dry_run")]
    return {
        "workflow_id": workflow_id,
        "mode": "executed",
        "plan": plan.model_dump(),
        "step_results": results,
        "status": status,
        "approver": req.approver.strip(),
        "outputs": outputs,
    }


@router.get("/audit")
def list_audit(workflow_id: int | None = None, db: Session = Depends(get_db)) -> list[dict]:
    """List audit-log entries (optionally filtered by workflow)."""
    q = db.query(AuditLog).order_by(AuditLog.id.desc())
    if workflow_id is not None:
        q = q.filter(AuditLog.workflow_id == workflow_id)
    rows = q.limit(200).all()
    return [
        {
            "id": r.id,
            "workflow_id": r.workflow_id,
            "mode": r.mode,
            "approved_by": r.approved_by,
            "started_at": r.started_at.isoformat() if r.started_at else None,
            "finished_at": r.finished_at.isoformat() if r.finished_at else None,
            "step_results": json.loads(r.step_results or "[]"),
            "status": r.status,
        }
        for r in rows
    ]
