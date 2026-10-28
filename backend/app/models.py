"""Phase 2: Upload and Artifact models."""
from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Upload(Base):
    """A batch of uploaded (or sample) files parsed in one call."""

    __tablename__ = "uploads"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    filename: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    is_sample: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))

    artifacts: Mapped[list["Artifact"]] = relationship(
        "Artifact", back_populates="upload", cascade="all, delete-orphan"
    )


class Artifact(Base):
    """A single normalized work item (email, lead, note, or task)."""

    __tablename__ = "artifacts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    upload_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("uploads.id", ondelete="CASCADE"), nullable=False, index=True
    )
    kind: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    source_ref: Mapped[str] = mapped_column(String(256), nullable=False, default="")
    timestamp: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    title: Mapped[str] = mapped_column(String(1024), nullable=False, default="")
    text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    raw_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")

    upload: Mapped[Upload] = relationship("Upload", back_populates="artifacts")


class Workflow(Base):
    """A discovered repetitive workflow candidate."""

    __tablename__ = "workflows"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    upload_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("uploads.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    trigger: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    steps: Mapped[str] = mapped_column(Text, nullable=False, default="[]")  # JSON list
    inputs: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    outputs: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    minutes_per_occurrence: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    occurrences: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    feasibility: Mapped[str] = mapped_column(String(16), nullable=False, default="medium")
    evidence: Mapped[str] = mapped_column(Text, nullable=False, default="[]")  # JSON list
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="discovered")
    low_confidence: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    time_rationale: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    feasibility_reason: Mapped[str] = mapped_column(String(512), nullable=False, default="")


class AuditLog(Base):
    """Every automation run (dry_run or executed) is recorded here."""

    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    workflow_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False, index=True
    )
    mode: Mapped[str] = mapped_column(String(16), nullable=False, default="dry_run")
    approved_by: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    started_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    step_results: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="ok")
