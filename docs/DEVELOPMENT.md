# Development Guide

## Prerequisites

- Docker + Docker Compose
- Python 3.12+ with [uv](https://github.com/astral-sh/uv)
- Node.js 20+
- (Optional) conda for cadquery

## Local Dev Setup

```bash
cp .env.example .env
# Fill in API keys: ANTHROPIC_API_KEY, VOYAGE_API_KEY, GOOGLE_API_KEY

docker-compose up          # starts all 6 services
```

## Backend

```bash
cd backend

# Install deps
uv sync

# Run locally (without Docker)
uv run uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload

# Tests
uv run pytest tests/ -v

# Lint + format
uv run ruff check .
uv run ruff format .
uv run mypy app
```

### cadquery (3D geometry)

cadquery requires conda on some systems:

```bash
conda create -n fastenergpt python=3.12
conda activate fastenergpt
conda install -c cadquery cadquery
pip install uv
uv sync
```

If cadquery is unavailable, geometry modules raise `ImportError` gracefully
and the pipeline skips 3D generation.

## Frontend

```bash
cd frontend

npm install
npm run dev        # http://localhost:3000
npm run type-check
npm run lint
npm test
```

## Adding a New API Endpoint

1. Create route in `backend/app/api/v1/<module>.py`
2. Register router in `backend/app/main.py`
3. Add TypeScript function to `frontend/src/lib/api.ts`
4. Write test in `backend/tests/`

## Adding a New Schema

1. Add Pydantic model to `backend/app/data/schemas.py`
2. Add test in `backend/tests/test_schemas.py`
3. Regenerate TypeScript types: `npx openapi-typescript http://localhost:8080/api/openapi.json -o src/types/api.ts`

## Services

| Service | URL | Credentials |
|---------|-----|-------------|
| Backend API | http://localhost:8080 | — |
| API Docs | http://localhost:8080/api/docs | — |
| Frontend | http://localhost:3000 | — |
| PostgreSQL | localhost:5432 | dev/dev |
| Redis | localhost:6379 | — |
| ChromaDB | http://localhost:8000 | — |
| MinIO Console | http://localhost:9001 | minioadmin/minioadmin |
