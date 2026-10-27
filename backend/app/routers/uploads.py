"""Phase 2: upload and artifact routers."""
from __future__ import annotations

import json
import logging
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Artifact, Upload
from app.schemas import ArtifactOut, UploadResponse
from app.services.ingest import parse_file

logger = logging.getLogger("autoscout.uploads")

router = APIRouter(prefix="/api", tags=["uploads"])

SAMPLE_DIR = Path(__file__).resolve().parents[3] / "data" / "sample"
ALLOWED_EXTENSIONS = {".csv", ".txt"}
MAX_FILE_BYTES = 5 * 1024 * 1024  # 5 MB per file


def _store_artifacts(
    db: Session,
    upload: Upload,
    artifacts: list[dict],
) -> int:
    """Persist parsed artifacts for an upload; return how many were stored."""
    stored = 0
    for a in artifacts:
        db.add(Artifact(
            upload_id=upload.id,
            kind=a["kind"],
            source_ref=a.get("source_ref", ""),
            timestamp=a.get("timestamp"),
            title=a.get("title", ""),
            text=a.get("text", ""),
            raw_json=json.dumps(a.get("raw_json", {}), ensure_ascii=False, default=str),
        ))
        stored += 1
    return stored


def _counts_for(db: Session, upload_id: int) -> dict[str, int]:
    rows = db.query(Artifact.kind, Artifact.id).filter(Artifact.upload_id == upload_id).all()
    counts: dict[str, int] = {}
    for kind, _ in rows:
        counts[kind] = counts.get(kind, 0) + 1
    return counts


@router.post("/uploads", response_model=UploadResponse)
async def create_upload(
    files: list[UploadFile] = File(...),
    db: Session = Depends(get_db),
) -> UploadResponse:
    """Parse and store one or more uploaded files (CSV/TXT)."""
    if not files:
        raise HTTPException(status_code=400, detail="No files provided.")

    errors: list[str] = []
    skipped = 0
    upload = Upload(filename=", ".join(f.filename or "" for f in files), is_sample=0)
    db.add(upload)
    db.flush()  # get upload.id

    for f in files:
        name = f.filename or ""
        ext = Path(name).suffix.lower()
        if ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type '{ext}' for {name}. Allowed: .csv, .txt",
            )
        raw = await f.read()
        if len(raw) > MAX_FILE_BYTES:
            raise HTTPException(
                status_code=400,
                detail=f"File {name} is too large ({len(raw)} bytes). Max is 5 MB.",
            )
        try:
            content = raw.decode("utf-8-sig", errors="replace")
        except Exception:
            content = raw.decode("latin-1", errors="replace")
        artifacts = parse_file(name, content)
        if not artifacts:
            skipped += 1
            logger.warning("No artifacts parsed from %s", name)
        _store_artifacts(db, upload, artifacts)

    db.commit()
    counts = _counts_for(db, upload.id)
    if not counts:
        raise HTTPException(status_code=400, detail="No parsable rows found in the provided files.")
    return UploadResponse(upload_id=upload.id, counts=counts, skipped=skipped, errors=errors)


@router.post("/uploads/sample", response_model=UploadResponse)
def create_sample_upload(db: Session = Depends(get_db)) -> UploadResponse:
    """Load the committed data/sample/ directory in one call."""
    if not SAMPLE_DIR.exists():
        raise HTTPException(status_code=404, detail="Sample data directory not found.")

    upload = Upload(filename="sample", is_sample=1)
    db.add(upload)
    db.flush()

    total = 0
    for path in sorted(SAMPLE_DIR.rglob("*")):
        if path.is_dir() or path.name.startswith("."):
            continue
        if path.suffix.lower() not in ALLOWED_EXTENSIONS:
            logger.debug("Skipping unsupported sample file %s", path.name)
            continue
        content = path.read_text(encoding="utf-8", errors="replace")
        artifacts = parse_file(path.name, content)
        _store_artifacts(db, upload, artifacts)
        total += len(artifacts)

    if total == 0:
        raise HTTPException(status_code=404, detail="Sample data is empty or unreadable.")

    db.commit()
    counts = _counts_for(db, upload.id)
    return UploadResponse(upload_id=upload.id, counts=counts)


@router.get("/artifacts", response_model=list[ArtifactOut])
def list_artifacts(upload_id: int, db: Session = Depends(get_db)) -> list[ArtifactOut]:
    """List artifacts for a given upload, ordered by id."""
    rows = (
        db.query(Artifact)
        .filter(Artifact.upload_id == upload_id)
        .order_by(Artifact.id)
        .all()
    )
    return [ArtifactOut.model_validate(r) for r in rows]
