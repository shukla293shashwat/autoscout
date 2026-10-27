# AutoScout backend

Python 3.11+ / FastAPI / SQLAlchemy (SQLite) / Pydantic v2.

## Install

```bash
cd backend
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate
pip install -r requirements.txt
```

## Run

```bash
uvicorn app.main:app --reload --port 8000
```

GET http://localhost:8000/health -> `{"status":"ok"}`

## Configure

Copy `.env.example` to `.env` and set your LLM provider.

## Test

```bash
pytest
```
