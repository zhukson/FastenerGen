# Session 1: Project Initialization

Read @CLAUDE.md completely before starting. Every decision in that file is final.

## Goal

By end of session: a working monorepo with backend + frontend communicating, Docker dev environment running, all data models defined, ready for feature development. This is pure infrastructure — no AI, no drawings, no geometry yet.

## Task 1: Monorepo Setup

Create the complete folder structure from CLAUDE.md. Initialize:

- `backend/` — Python project with `uv` package manager
- `frontend/` — Next.js 15 App Router with TypeScript strict
- `docker-compose.yml` — full local dev environment
- Root: `.gitignore`, `README.md`, copy CLAUDE.md
- CI: `.github/workflows/ci.yml`

## Task 2: Backend Foundation

### Framework

- FastAPI 0.115+ with async, lifespan context manager
- Pydantic v2 for all models
- `pydantic-settings` for env-based config
- `structlog` for structured JSON logging
- Health check: `GET /api/health`

### Dependencies

```
# Core
fastapi, uvicorn[standard], pydantic, pydantic-settings
python-multipart, httpx, structlog

# AI/LLM (install now, use in later sessions)
anthropic, google-generativeai, voyageai

# Data
sqlalchemy[asyncio], asyncpg, alembic
chromadb, redis

# Geometry & Drawing (install now, use in later sessions)
ezdxf, cadquery, trimesh, numpy, scipy

# Task queue
celery[redis]

# Dev
pytest, pytest-asyncio, ruff, mypy
```

Note: `cadquery` may need conda. If pip install fails, add a note and continue — geometry module will gracefully degrade with ImportError handling.

### Structure

```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py                  # FastAPI app, lifespan, CORS
│   ├── core/
│   │   ├── config.py            # Settings(BaseSettings) from .env
│   │   ├── logging.py           # structlog configuration
│   │   └── exceptions.py        # Custom exception hierarchy
│   ├── api/
│   │   ├── deps.py              # Dependency injection (get_db, get_llm, etc.)
│   │   └── v1/
│   │       ├── health.py        # Health check endpoint
│   │       ├── drawings.py      # Drawing upload + parse (stub)
│   │       ├── designs.py       # Design generation (stub)
│   │       └── eval.py          # Eval dashboard (stub)
│   ├── drawings/                # Stub modules with docstrings + NotImplementedError
│   │   ├── __init__.py
│   │   ├── parser.py
│   │   ├── generator.py
│   │   └── standards.py
│   ├── geometry/                # Stub modules
│   │   ├── __init__.py
│   │   ├── punch_templates.py
│   │   ├── die_templates.py
│   │   ├── workpiece.py
│   │   ├── assembly.py
│   │   ├── exporter.py
│   │   └── projector.py
│   ├── ai/                      # Stub modules
│   │   ├── __init__.py
│   │   ├── drawing_reader.py
│   │   ├── rag.py
│   │   ├── embeddings.py
│   │   ├── fewshot.py
│   │   ├── designer.py
│   │   ├── reasoning.py
│   │   ├── quality.py
│   │   ├── verification.py
│   │   └── prompts/
│   │       ├── __init__.py
│   │       ├── drawing_understanding.py
│   │       ├── process_planning.py
│   │       ├── die_design.py
│   │       └── pseudo_reasoning.py
│   ├── data/
│   │   ├── __init__.py
│   │   ├── schemas.py           # ALL Pydantic models (Task 3)
│   │   ├── ingestion.py         # Stub
│   │   └── synthetic.py         # Stub
│   └── eval/                    # Stub modules
│       ├── __init__.py
│       ├── golden_set.py
│       ├── metrics.py
│       ├── judge.py
│       └── regression.py
├── tests/
│   ├── conftest.py
│   ├── test_health.py
│   └── test_schemas.py
├── scripts/                     # Empty with __init__.py
├── pyproject.toml
├── Dockerfile
└── Dockerfile.dev
```

For stub modules: include a module docstring explaining purpose, define the main class/function signatures with type hints, and raise `NotImplementedError("Implemented in Session N")` in the body. This documents the interface contract.

## Task 3: Data Schemas (Critical)

Create `backend/app/data/schemas.py` with ALL Pydantic models the system will use. These define the data contract between every component. Get them right now.

Design these models based on the real PDF drawing we analyzed (18149-D6 M6×33 flat head bolt, 10B21, 8.8 grade). Every field should be justifiable by something visible in that drawing.

Models to define:

```python
# === Part Features (extracted from product drawing) ===
class HeadFeatures(BaseModel): ...      # type, diameter, height, chamfer, flange, teeth
class ShankFeatures(BaseModel): ...     # diameter, length
class ThreadFeatures(BaseModel): ...    # spec, pitch, length, class
class TailFeatures(BaseModel): ...      # type, dimensions
class PartFeatures(BaseModel): ...      # aggregates above + material, grade, surface, etc.

# === Process Plan (AI-generated) ===
class ShapeDescription(BaseModel): ...  # dimensions describing an intermediate shape
class StationPlan(BaseModel): ...       # one station: operation, input/output shapes, params
class ProcessPlan(BaseModel): ...       # total_stations, blank dims, list of StationPlan, post_processes

# === Die Design (AI-generated) ===
class DieComponentParams(BaseModel): ...  # one component: geometry, material, hardness, tolerances
class DieParameters(BaseModel): ...       # one station: punch + die + expected life

# === RAG ===
class PseudoReasoning(BaseModel): ...   # LLM-inferred reasoning with confidence
class RAGCase(BaseModel): ...           # complete case in vector DB
class RetrievedCase(BaseModel): ...     # retrieved case with similarity score

# === Pipeline Output ===
class OutputFile(BaseModel): ...        # file_type, station_number, file_path, format
class VerificationCheck(BaseModel): ... # check_name, passed, message
class VerificationResult(BaseModel): ... # passed, checks list, retry_count
class DesignResult(BaseModel): ...      # the complete output of the pipeline

# === Drawing Parsing ===
class ExtractedDimension(BaseModel): ... # from DWG parsing
class TitleBlock(BaseModel): ...         # from DWG title block
class ParsedDrawing(BaseModel): ...      # complete parsed drawing

# === Evaluation ===
class ExpectedDecisions(BaseModel): ... # expected AI decisions for test cases
class MetricResult(BaseModel): ...      # single metric result
class EvalReport(BaseModel): ...        # aggregated eval results
```

Write comprehensive models with docstrings, field descriptions, validators where appropriate, and example values in Field(..., examples=[...]). Test that all models can be instantiated and serialized.

## Task 4: Frontend Setup

### Stack

- Next.js 15 App Router, TypeScript strict
- Tailwind CSS + shadcn/ui
- `@react-three/fiber` + `@react-three/drei` for 3D
- `occt-import-js` for STEP loading in browser
- Zod for runtime validation
- TanStack Query for API state

### Pages

- `/` — Dashboard with project status cards
- `/upload` — Drawing upload (drag-drop, support PDF/DWG/DXF/JPG/PNG)
- `/designs` — List of generated designs
- `/designs/[id]` — Design detail page with:
  - 3D viewer panel (Three.js — load STL files)
  - Station selector (tabs or carousel)
  - Process flow diagram
  - Extracted features panel
  - AI reasoning panel
  - File download panel (DWG, STEP, STL)
  - Feedback buttons (Accept / Reject / Needs Changes)
- `/eval` — Evaluation dashboard (scores, history chart, case list)

### Layout

- Sidebar navigation (collapsible)
- Main content area
- Responsive (works on tablet for factory floor use)

### API Client

- Generate TypeScript types from backend OpenAPI spec
- Type-safe API calls
- Proper loading/error states with TanStack Query

## Task 5: Docker Compose

Complete `docker-compose.yml` for local development:

```yaml
services:
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: fastenergpt
      POSTGRES_USER: dev
      POSTGRES_PASSWORD: dev
    ports: ["5432:5432"]
    volumes: [postgres_data:/var/lib/postgresql/data]
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U dev"]
      interval: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      retries: 5

  chromadb:
    image: chromadb/chroma:latest
    ports: ["8000:8000"]
    volumes: [chroma_data:/chroma/chroma]

  minio:
    image: minio/minio
    command: server /data --console-address ":9001"
    environment:
      MINIO_ROOT_USER: minioadmin
      MINIO_ROOT_PASSWORD: minioadmin
    ports: ["9000:9000", "9001:9001"]
    volumes: [minio_data:/data]

  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile.dev
    volumes:
      - ./backend:/app
      - backend_cache:/root/.cache
    ports: ["8080:8080"]
    env_file: .env
    environment:
      DATABASE_URL: postgresql+asyncpg://dev:dev@postgres:5432/fastenergpt
      REDIS_URL: redis://redis:6379
      CHROMA_URL: http://chromadb:8000
      S3_ENDPOINT: http://minio:9000
      S3_ACCESS_KEY: minioadmin
      S3_SECRET_KEY: minioadmin
    depends_on:
      postgres: { condition: service_healthy }
      redis: { condition: service_healthy }
      chromadb: { condition: service_started }
      minio: { condition: service_started }

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile.dev
    volumes:
      - ./frontend:/app
      - /app/node_modules
      - /app/.next
    ports: ["3000:3000"]
    environment:
      NEXT_PUBLIC_API_URL: http://localhost:8080

volumes:
  postgres_data:
  chroma_data:
  minio_data:
  backend_cache:
```

Create `.env.example`:

```
ANTHROPIC_API_KEY=sk-ant-...
VOYAGE_API_KEY=pa-...
GOOGLE_API_KEY=AI...
```

Create `Dockerfile.dev` for backend (hot-reload, dev dependencies).
Create `Dockerfile.dev` for frontend (hot-reload).

## Task 6: CI Skeleton

`.github/workflows/ci.yml`:

- Trigger on push to main and on PRs
- Backend job: ruff check, mypy, pytest
- Frontend job: biome check, tsc --noEmit, vitest
- Keep simple — no Docker in CI, no deployment

## Task 7: Documentation

- `README.md`: Project description, quick start (`docker-compose up`), architecture diagram
- `docs/DEVELOPMENT.md`: Dev commands, how to add tests, how to add API endpoints
- `docs/DECISION_LOG.md`: Copy from CLAUDE.md, updated incrementally
- `docs/ARCHITECTURE.md`: System diagram, data flow, component responsibilities

## Verification Checklist

- [ ] `docker-compose up` starts all 6 services without errors
- [ ] `curl http://localhost:8080/api/health` returns 200 with JSON
- [ ] `http://localhost:3000` renders dashboard page with navigation
- [ ] `pytest backend/tests/` passes (health check + schema tests)
- [ ] All Pydantic schemas instantiate with example data and serialize to JSON
- [ ] All stub modules import without error
- [ ] Frontend can call backend health endpoint (CORS configured)
- [ ] Git repo initialized with clean commit
- [ ] `.env.example` exists with all required variables documented
