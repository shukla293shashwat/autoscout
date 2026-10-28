"""Pydantic schemas for API request/response models."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class HealthResponse(BaseModel):
    """Response schema for GET /health."""

    status: str


class ArtifactOut(BaseModel):
    """Serialized Artifact for API responses."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    upload_id: int
    kind: str
    source_ref: str
    timestamp: datetime | None = None
    title: str
    text: str
    raw_json: str


class UploadResponse(BaseModel):
    """Response for POST /api/uploads and POST /api/uploads/sample."""

    upload_id: int
    counts: dict[str, int]
    skipped: int = 0
    errors: list[str] = []


class ErrorResponse(BaseModel):
    """Friendly error payload for 4xx responses."""

    detail: str


class WorkflowOut(BaseModel):
    """Serialized Workflow for API responses."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    upload_id: int
    name: str
    description: str
    trigger: str
    steps: str
    minutes_per_occurrence: int
    occurrences: int
    feasibility: str
    evidence: str
    status: str
    low_confidence: int
    time_rationale: str
    feasibility_reason: str
