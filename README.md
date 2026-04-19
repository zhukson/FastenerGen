# FastenerGPT

**AI-powered die design for cold-heading fasteners.**

Upload a product drawing (PDF/DWG), get production-ready die designs in 30 minutes instead of 7 days.

```
Customer drawing (PDF/DWG)
        │
        ▼
[Claude Opus 4.7 Vision] → PartFeatures JSON
        │
        ▼
[Hybrid RAG] → 3 similar historical cases
        │
        ▼
[LLM Process Planning] → ProcessPlan JSON
        │
        ▼
[LLM Die Design] → DieParameters JSON
        │
        ▼
[CADQuery] → STEP + STL
[ezdxf]    → DXF drawings
        │
        ▼
Engineer review → approve → manufacture
```

## Quick Start

```bash
# 1. Clone and copy env
git clone <repo>
cp .env.example .env   # add your API keys

# 2. Start all services
docker-compose up

# 3. Access
# Frontend: http://localhost:3000
# API docs:  http://localhost:8080/api/docs
# MinIO:     http://localhost:9001 (minioadmin/minioadmin)
```

## Development

See [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) for backend and frontend dev commands.

## Architecture

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for system design.

## Tech Stack

| Layer | Choice |
|-------|--------|
| Backend | Python 3.12, FastAPI, Pydantic v2 |
| Frontend | Next.js 15, TypeScript, Tailwind CSS |
| LLM | Claude Opus 4.7 (primary), Claude Haiku 4.5 (aux), Gemini 2.5 Pro (cross-val) |
| Embeddings | Voyage-3-large + rerank-2 |
| Vector DB | ChromaDB (Phase 1) |
| 3D | CADQuery + PythonOCC |
| 2D | ezdxf |

## Status

Phase 1 — Infrastructure & Demo. Pre-data, pre-seed stage.
