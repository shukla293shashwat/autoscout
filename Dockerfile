# ---- Stage 1: build the frontend (Vite + tsc) ----
FROM node:20-slim AS frontend
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ---- Stage 2: Python runtime with the built SPA ----
FROM python:3.11-slim
ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# System deps: none strictly required for our wheels; sqlite3 is stdlib.
# We only need CPU inference (sentence-transformers), so pull CPU-only torch
# from the PyTorch wheel index to avoid shipping ~5 GB of CUDA libraries.
COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir \
      --extra-index-url https://download.pytorch.org/whl/cpu \
      -r backend/requirements.txt

# App source
COPY backend/ ./backend/
COPY data/ ./data/

# Drop the built SPA where app.main expects it (backend/../frontend/dist).
COPY --from=frontend /app/frontend/dist ./frontend/dist

WORKDIR /app/backend
EXPOSE 8000

# Bind 0.0.0.0 so the container is reachable from the host.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
