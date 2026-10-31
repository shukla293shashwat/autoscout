"""FastAPI application entry point for AutoScout."""
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.db import init_db
from app.routers import automation, discover, uploads
from app.schemas import HealthResponse

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)

# Built frontend (npm run build). When present, served at "/" so a single
# process/API host can serve the whole app (used by the Docker image).
FRONTEND_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create database tables on startup."""
    init_db()
    yield


app = FastAPI(
    title="AutoScout API",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(uploads.router)
app.include_router(discover.router)
app.include_router(automation.router)


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """Liveness probe used by the frontend and smoke tests."""
    return HealthResponse(status="ok")


def _mount_frontend() -> None:
    """Serve the built SPA from / when frontend/dist exists (no-op in dev)."""
    index = FRONTEND_DIST / "index.html"
    if not index.is_file():
        return

    assets = FRONTEND_DIST / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=assets), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa(full_path: str) -> FileResponse:
        # Known static file? Serve it directly (bypasses the HTML re-check).
        candidate = (FRONTEND_DIST / full_path).resolve()
        if (
            full_path
            and candidate.is_file()
            and FRONTEND_DIST.resolve() in candidate.parents
        ):
            return FileResponse(candidate)

        # API / docs routes must never be swallowed by the SPA fallback.
        if full_path.startswith(("api/", "health", "docs", "redoc", "openapi")):
            from fastapi import HTTPException

            raise HTTPException(status_code=404)

        # Everything else is an SPA route: hand back index.html for the router.
        return FileResponse(index, headers={"Cache-Control": "no-cache"})


_mount_frontend()
