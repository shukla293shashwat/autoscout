"""Phase 3 + 4: discovery and workflow routers (with ROI ranking)."""
from __future__ import annotations

import json
import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Artifact, Workflow
from app.services.discovery import discover_workflows
from app.services.roi import score_workflows, total_hours_saved_per_week

logger = logging.getLogger("autoscout.discover")

router = APIRouter(prefix="/api", tags=["discover"])


def _window_days(db: Session, upload_id: int) -> int:
    """Length of the data window (in days) used to scale occurrences to a week.

    Computed from the *work* artifacts (emails, notes, tasks) rather than leads,
    whose historical "created" dates predate the work week and would otherwise
    inflate the window. Falls back to 7 (a week) when unknown.
    """
    stmt = (
        select(Artifact.timestamp)
        .where(Artifact.upload_id == upload_id, Artifact.kind != "lead")
        .distinct()
    )
    timestamps = [row[0] for row in db.execute(stmt) if row[0] is not None]
    if not timestamps:
        return 7
    day_keys = {d.strftime("%Y-%m-%d") for d in timestamps}
    return len(day_keys) or 7


def _workflow_rows(db: Session, upload_id: int) -> list[dict]:
    rows = (
        db.query(Workflow)
        .filter(Workflow.upload_id == upload_id)
        .order_by(Workflow.id)
        .all()
    )
    return [
        {
            "id": r.id,
            "upload_id": r.upload_id,
            "name": r.name,
            "description": r.description,
            "trigger": r.trigger,
            "steps": json.loads(r.steps or "[]"),
            "inputs": json.loads(r.inputs or "[]"),
            "outputs": json.loads(r.outputs or "[]"),
            "minutes_per_occurrence": r.minutes_per_occurrence,
            "occurrences": r.occurrences,
            "feasibility": r.feasibility,
            "evidence": json.loads(r.evidence or "[]"),
            "status": r.status,
            "low_confidence": bool(r.low_confidence),
            "time_rationale": r.time_rationale,
            "feasibility_reason": r.feasibility_reason,
        }
        for r in rows
    ]


@router.post("/uploads/{upload_id}/discover")
def run_discovery(upload_id: int, db: Session = Depends(get_db)) -> dict:
    """Run the pattern-discovery pipeline for an upload."""
    count = db.query(Artifact).filter(Artifact.upload_id == upload_id).count()
    if count == 0:
        raise HTTPException(status_code=404, detail=f"No artifacts found for upload {upload_id}.")

    workflows = discover_workflows(db, upload_id)
    return {"upload_id": upload_id, "workflows": workflows, "count": len(workflows)}


@router.get("/workflows")
def list_workflows(upload_id: int, db: Session = Depends(get_db)) -> list[dict]:
    """List discovered workflows for an upload, ranked by ROI (priority desc)."""
    rows = _workflow_rows(db, upload_id)
    window = _window_days(db, upload_id)
    return score_workflows(rows, window_days=window)


@router.get("/workflows/{workflow_id}")
def get_workflow(workflow_id: int, db: Session = Depends(get_db)) -> dict:
    """Fetch a single workflow by id (with its ROI fields)."""
    wf = db.get(Workflow, workflow_id)
    if wf is None:
        raise HTTPException(status_code=404, detail="Workflow not found.")
    rows = _workflow_rows(db, wf.upload_id)
    window = _window_days(db, wf.upload_id)
    for r in score_workflows(rows, window_days=window):
        if r["id"] == workflow_id:
            return r
    raise HTTPException(status_code=404, detail="Workflow not found.")


@router.get("/summary")
def summary(upload_id: int, db: Session = Depends(get_db)) -> dict:
    """Aggregate ROI totals for an upload."""
    rows = _workflow_rows(db, upload_id)
    window = _window_days(db, upload_id)
    scored = score_workflows(rows, window_days=window)

    by_feasibility: dict[str, int] = {}
    for r in scored:
        by_feasibility[r["feasibility"]] = by_feasibility.get(r["feasibility"], 0) + 1

    total_occ = sum(r["occurrences"] for r in scored)
    return {
        "upload_id": upload_id,
        "workflow_count": len(scored),
        "total_hours_saved_per_week": total_hours_saved_per_week(scored),
        "total_occurrences_per_week": round(sum(r["occurrences_per_week"] for r in scored), 2),
        "by_feasibility": by_feasibility,
        "top_workflow": scored[0]["name"] if scored else None,
    }
