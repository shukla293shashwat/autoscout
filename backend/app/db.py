"""SQLAlchemy engine, session factory, and dependency."""
import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.models import Base

# SQLite database file lives at backend/autoscout.db by default.
# AUTOSCOUT_DB_PATH overrides it (used by the test suite to isolate the DB).
_ENV_DB = os.environ.get("AUTOSCOUT_DB_PATH")
DB_PATH = Path(_ENV_DB) if _ENV_DB else Path(__file__).resolve().parent.parent / "autoscout.db"
DB_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(
    DB_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def init_db() -> None:
    """Create all tables (idempotent). Called on app startup."""
    Base.metadata.create_all(bind=engine)


def get_db():
    """FastAPI dependency that yields a session and closes it after use."""
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()
