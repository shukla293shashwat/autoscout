"""Phase 3: discovery and workflow routers."""
from __future__ import annotations

import json
import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Workflow
from app.schemas import WorkflowOut
from app.services.discovery import discover_workflows

logger = logging.getLogger("autoscout.discover")

router = APIRouter(prefix="/api", tags=["discover"])


@router.post("/uploads/{upload_id}/discover")
def run_discovery(upload_id: int, db: Session = Depends(get_db)) -> dict:
    """Run the pattern-discovery pipeline for an upload."""
    from app.models import Artifact
    count = db.query(Artifact).filter(Artifact.upload_id == upload_id).count()
    if count == 0:
        raise HTTPException(status_code=404, detail=f"No artifacts found for upload {upload_id}.")

    workflows = discover_workflows(db, upload_id)
    return {"upload_id": upload_id, "workflows": workflows, "count": len(workflows)}


@router.get("/workflows", response_model=list[WorkflowOut])
def list_workflows(upload_id: int, db: Session = Depends(get_db)) -> list[WorkflowOut]:
    """List discovered workflows for an upload."""
    rows = (
        db.query(Workflow)
        .filter(Workflow.upload_id == upload_id)
        .order_by(Workflow.id)
        .all()
    )
    return [WorkflowOut.model_validate(r) for r in rows]


@router.get("/workflows/{workflow_id}", response_model=WorkflowOut)
def get_workflow(workflow_id: int, db: Session = Depends(get_db)) -> WorkflowOut:
    """Fetch a single workflow by id."""
    wf = db.get(Workflow, workflow_id)
    if wf is None:
        raise HTTPException(status_code=404, detail="Workflow not found.")
    return WorkflowOut.model_validate(wf)
