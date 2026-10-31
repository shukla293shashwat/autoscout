.PHONY: backend-dev frontend-dev test docker-build docker-run docker-stop

backend-dev:
	cd backend && python -m uvicorn app.main:app --reload --port 8000

frontend-dev:
	cd frontend && npm run dev

test:
	cd backend && python -m pytest -q

# --- Deployment (Docker) ---
docker-build:
	docker build -t autoscout:latest .

# Run the full app (API + built SPA) on :8000. First run downloads the
# sentence-transformers model (~90 MB) into a named volume.
docker-run: docker-build
	docker compose up -d

docker-stop:
	docker compose down
