# AutoScout

AutoScout reads a person's messy work files (emails, spreadsheets, meeting notes),
discovers the repetitive workflows hiding in them, ranks them by hours saved per week,
and automates the top one safely with human approval.

> One-sentence pitch: AutoScout turns a week of your inbox and spreadsheets into a
> ranked list of automations you can review, dry-run, and approve — with evidence for
> every claim.

## What it does

1. **Ingest** — drop in `emails.csv`, `leads.csv`, `tasks.csv`, and `.txt` meeting
   notes. Parsers tolerate messy dates, missing columns, signatures, and reply chains.
2. **Discover** — embeds the *discriminating* text (email body / note body), clusters
   with a semantic+lexical union-find, gates on direction (you must be the actor), and
   names each cluster with an LLM (deterministic fallback when offline).
3. **Rank (ROI)** — converts each workflow into `hours/week` and a `priority_score`
   (time saved × how automatable it is).
4. **Automate safely** — generates a declarative JSON plan against a **whitelisted**
   tool registry, runs a **dry run** (zero side effects), and only executes after a
   human reviews the preview and types their name. Every run writes an audit log.

## Quickstart (one command each)

```bash
# Backend (port 8000)
cd backend && .venv\Scripts\activate && pip install -r requirements.txt && uvicorn app.main:app --reload --port 8000

# Frontend (port 5173) — second terminal
cd frontend && npm install && npm run dev
```

Or use the helper: `scripts\dev.bat backend-dev` / `scripts\dev.bat frontend-dev` /
`scripts\dev.bat test`.

Health check: `GET http://localhost:8000/health` -> `{"status":"ok"}`

**Offline by default.** `LLM_PROVIDER=mock` (the default) means discovery and plan
generation run with zero network/API-key setup. Set `LLM_PROVIDER=openai` and
`LLM_API_KEY` for real LLM naming and plan generation.

## A 60-second demo

1. **Upload** → click **▶ Try sample data** (60 emails, 30 leads, 5 notes, 25 tasks).
2. **Discover workflows** → a bubble map + ranked list. Watch "hours/week identified".
3. Click the **top workflow** → see the description, ROI rationale, and evidence.
4. **Generate automation** → **Run dry run** → review the preview cards (no files written).
5. Check **"I reviewed the preview"**, type your name, **Approve & execute** → files
   are written under `data/output/`, and the **Impact** dashboard shows KPIs + audit log.

## Safety model (non-negotiable)

- Generated automations are **declarative JSON**, never executable code.
- Execution is restricted to a **whitelist** of 4 tools (`append_csv_row`,
  `draft_email`, `create_task`, `summarize_table`). No `exec`/`eval`, no shell.
- All writes are confined to `data/output/` — path traversal, absolute paths, and
  nested paths are rejected. Reads are confined to the data directories.
- **Dry run** before **execute**; execute requires a reviewed checkbox + approver name.
- Every plan run is recorded in an **audit log** (GET `/api/audit`).

## Tech stack

- **Backend:** Python 3.11+, FastAPI, SQLAlchemy (SQLite), Pydantic v2
- **AI:** provider-agnostic LLM wrapper (`LLM_PROVIDER=mock|openai`), local
  sentence-transformers embeddings (`all-MiniLM-L6-v2`), scikit-learn
- **Frontend:** React + Vite + TypeScript, Tailwind CSS
- **Tests:** pytest (backend, isolated per-session DB), Vite build (frontend)

## API at a glance

| Method | Path | Purpose |
| ------ | ---- | ------- |
| `POST` | `/api/uploads` | Upload CSV/TXT files |
| `POST` | `/api/uploads/sample` | Load the committed sample dataset |
| `POST` | `/api/uploads/{id}/discover` | Run pattern discovery |
| `GET`  | `/api/workflows?upload_id=` | ROI-ranked workflows |
| `GET`  | `/api/summary?upload_id=` | Aggregate hours/week + counts |
| `POST` | `/api/workflows/{id}/plan` | Generate an automation plan |
| `POST` | `/api/workflows/{id}/dry-run` | Preview (zero side effects) |
| `POST` | `/api/workflows/{id}/execute` | Execute after approval |
| `GET`  | `/api/audit` | Audit log of runs |

## Roadmap

- [x] Phase 0 — Project setup
- [x] Phase 1 — Realistic sample dataset
- [x] Phase 2 — Ingestion and normalization
- [x] Phase 3 — Pattern discovery
- [x] Phase 4 — ROI scoring
- [x] Phase 5 — Safe automation generator and sandbox
- [x] Phase 6 — Frontend
- [x] Phase 7 — Reliability and testing
- [x] Phase 8 — Documentation and submission assets
- [x] Phase 9 — Deployment

## Deployment (Docker)

The app ships as a **single container**: a multi-stage `Dockerfile` builds the
frontend (Vite + `tsc`) and runs the FastAPI server, which serves the built SPA
from `/` alongside the JSON API on one port (`:8000`).

```bash
# Build + run on http://localhost:8000
docker compose up --build

# Or with make:
make docker-run      # build + compose up -d
make docker-stop     # compose down
```

What's inside:

- **CPU-only torch** — pulls from the PyTorch CPU wheel index, so the image is
  ~2.1 GB instead of ~9.6 GB with CUDA libraries you don't need for inference.
- **Persistence** — the SQLite DB and generated outputs live in named volumes
  (`autoscout-data`, `autoscout-output`) so restarts don't lose runs.
- **Healthcheck** — compose polls `/health` every 15 s.
- **Offline by default** — `LLM_PROVIDER=mock` means no API key needed. For real
  LLM names/plans: `LLM_PROVIDER=openai LLM_API_KEY=sk-... docker compose up`.
  (With `mock`, discovered workflows get the placeholder name `mock`; a real LLM
  returns proper plain-English names.)

Verified end-to-end in a container: `/health`, built SPA at `/` + SPA routes,
`/assets/*` with correct MIME types, `/api/uploads/sample`, discovery
(embeddings on CPU), and ROI-ranked `/api/workflows`.

## License

MIT
