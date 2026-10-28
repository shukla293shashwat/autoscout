# AutoScout

AutoScout reads a person's messy work files (emails, spreadsheets, meeting notes),
discovers the repetitive workflows hiding in them, ranks them by hours saved per week,
and automates the top one safely with human approval.

> One-sentence pitch: AutoScout turns a week of your inbox and spreadsheets into a
> ranked list of automations you can review, dry-run, and approve — with evidence for
> every claim.

## Status

This project is being built in phases. See the roadmap below.

## Tech stack

- **Backend:** Python 3.11+, FastAPI, SQLAlchemy (SQLite), Pydantic v2
- **AI:** provider-agnostic LLM wrapper (`LLM_PROVIDER=mock|openai`), local
  sentence-transformers embeddings (`all-MiniLM-L6-v2`), scikit-learn clustering
- **Frontend:** React + Vite + TypeScript, Tailwind CSS
- **Tests:** pytest (backend), smoke test script (end-to-end)

## Getting started

```bash
# 1. Backend
cd backend
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# 2. Frontend (in a second terminal)
cd frontend
npm install
npm run dev                   # http://localhost:5173

# 3. Tests
pytest                        # from backend/
```

Health check: `GET http://localhost:8000/health` -> `{"status":"ok"}`

## Roadmap

- [x] Phase 0 — Project setup
- [x] Phase 1 — Realistic sample dataset
- [x] Phase 2 — Ingestion and normalization
- [x] Phase 3 — Pattern discovery
- [x] Phase 4 — ROI scoring
- [ ] Phase 5 — Safe automation generator and sandbox
- [ ] Phase 6 — Frontend
- [ ] Phase 7 — Reliability and testing
- [ ] Phase 8 — Documentation and submission assets
- [ ] Phase 9 — Deployment

## License

MIT
