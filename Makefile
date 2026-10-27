.PHONY: backend-dev frontend-dev test

backend-dev:
	cd backend && python -m uvicorn app.main:app --reload --port 8000

frontend-dev:
	cd frontend && npm run dev

test:
	cd backend && python -m pytest -q
