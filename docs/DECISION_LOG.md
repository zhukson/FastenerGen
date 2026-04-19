# Decision Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-04-18 | Python backend + TypeScript frontend | PythonOCC/ezdxf/CADQuery require Python; Three.js requires JS/TS |
| 2026-04-18 | No LangChain/LlamaIndex ever | Over-abstraction, not for geometric data, lock-in, industry consensus |
| 2026-04-18 | Input = 2D drawings (PDF/DWG), not 3D STEP | Real factory data is 2D; most factories work in 2D |
| 2026-04-18 | Output = 2D DWG + 3D STEP/STL | DWG for engineers to edit; 3D for visualization and Deform export |
| 2026-04-18 | Deform/QForm = verification layer, not competitor | They need die 3D as input; we generate die designs |
| 2026-04-18 | Pseudo-reasoning via LLM, no expert yet | Bootstrap with AI; hire expert after Pre-seed |
| 2026-04-18 | Phase 1 = Agentic Workflow, not Multi-Agent | Simpler, faster, more predictable |
| 2026-04-18 | Docker for local dev from Day 1 | 3-person team needs consistent environments |
| 2026-04-18 | Parametric 3D templates (CADQuery) | More reliable than free-form generation |
| 2026-04-18 | 3-layer data: Source / RAG / Few-shot | Separate storage / retrieval / LLM presentation |
| 2026-04-18 | uv for Python package management | Fastest resolver, deterministic lockfile, replaces pip/poetry |
| 2026-04-18 | Biome for frontend lint + format | Faster than ESLint + Prettier; single tool |
| 2026-04-18 | Pydantic v2 for all data models | Strict typing, JSON serialization, schema export for LLM prompts |
| 2026-04-18 | structlog for backend logging | Structured JSON logs; full LLM request/response tracing |
