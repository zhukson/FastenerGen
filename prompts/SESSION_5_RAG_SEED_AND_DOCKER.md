# Session 5: RAG Seeding + Docker Fix

Read @CLAUDE.md for full project context. Sessions 1–4 must be complete.

## Goal

Two things that unblock everything else:
1. Fix CADQuery in Docker (libGL/X11 dependency chain)
2. Seed ChromaDB with 200+ physically correct synthetic cases so RAG returns real matches instead of `no_match`

After this session: every design request retrieves similar historical cases, LLM reasoning references them, and 3D geometry renders correctly via CADQuery.

## Why This Matters

RAG is the backbone of quality. Without seed data:
- LLM guesses die dimensions from scratch → wrong proportions
- No examples to reference in reasoning → generic output
- Verification fails frequently → retries waste time and money

With 200 seeded cases covering M4/M5/M6/M8/M10 × all head types × varying lengths, the LLM has real anchors for every common fastener type.

---

## Task 1: Fix Dockerfile — CADQuery System Dependencies

### File: `backend/Dockerfile.dev`

CADQuery's OCCT bindings require several X11/OpenGL system libraries that aren't in `python:3.12-slim`. The exact chain needed:

```dockerfile
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    curl \
    libgl1 \
    libglib2.0-0 \
    libxrender1 \
    libxext6 \
    libx11-6 \
    libfontconfig1 \
    libxi6 \
    libxrandr2 \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*
```

Add `libgomp1` — required by OCCT's parallel mesh algorithms.

### Verification

After rebuild:
```bash
docker compose exec backend /app/.venv/bin/python -c "import cadquery; print('cadquery', cadquery.__version__)"
```
Must print version without ImportError.

---

## Task 2: Fix `SyntheticDataGenerator` Quality Issues

### File: `backend/app/data/synthetic.py`

The current generator has three bugs that produce physically wrong die parameters:

**Bug 1: approach_angle_deg is always 90° for all operations**
Fix: set by operation type:
- `forward_extrusion` die: `approach_angle_deg = rng.uniform(10.0, 15.0)`
- `backward_extrusion` die: `approach_angle_deg = rng.uniform(15.0, 20.0)`
- `upsetting` die: `approach_angle_deg = None` (straight bore, no taper)
- Heading punch (`conical`/`closed_heading`): `approach_angle_deg = rng.uniform(30.0, 60.0)`
- Heading die (`closed_heading`): `approach_angle_deg = rng.uniform(40.0, 70.0)` (entry chamfer)
- `flat_face` punch: `approach_angle_deg = None`

**Bug 2: punch_od is oversized**
Fix:
- Heading station punch OD = `head_diameter × rng.uniform(0.988, 0.992)` (must fit inside head cavity)
- Extrusion station punch OD = `shank_diameter × rng.uniform(1.000, 1.005)` (guides the shank)

**Bug 3: No forward_extrusion stations generated**
Current code uses only `upsetting` (S1) and `heading` (S2+). Real M6 bolts almost always have a forward extrusion station to reduce diameter for thread forming.

Fix: expand station sequence logic:
```python
# For bolts where shank_diameter < blank_diameter × 0.85:
#   add a forward_extrusion station before the thread blank station
sequences = {
    1: ["heading"],
    2: ["upsetting", "heading"],
    3: ["upsetting", "heading", "forward_extrusion"],
    4: ["upsetting", "cone_preform", "heading", "forward_extrusion"],
}
```

**Bug 4: die outer_diameter too small**
Fix: `die_od = bore_id × rng.uniform(2.8, 3.6)` — never less than 2.5×.

**Bug 5: working_length too short**
Fix: `working_length = overall_length × rng.uniform(1.1, 1.4)` — die must be longer than the part.

### Add ISO dimension tables

Add a `_ISO_METRIC_BOLTS` dict at the top of `synthetic.py` with exact dimensions for common fastener types. This gives the generator real reference data instead of random values:

```python
# (nominal_dia, pitch, shank_dia, head_dia, head_height, thread_length_ratio)
_ISO_HEX_BOLTS = {
    "M4": (4.0, 0.7, 3.82, 7.0, 2.8, 0.6),
    "M5": (5.0, 0.8, 4.82, 8.0, 3.5, 0.6),
    "M6": (6.0, 1.0, 5.82, 10.0, 4.0, 0.65),
    "M8": (8.0, 1.25, 7.78, 13.0, 5.3, 0.65),
    "M10": (10.0, 1.5, 9.78, 16.0, 6.4, 0.7),
    "M12": (12.0, 1.75, 11.73, 18.0, 7.5, 0.7),
}
_ISO_FLAT_HEAD = {
    "M4": (4.0, 0.7, 3.82, 8.0, 2.2, 0.7),
    "M5": (5.0, 0.8, 4.82, 9.5, 2.5, 0.7),
    "M6": (6.0, 1.0, 5.82, 11.5, 3.0, 0.72),
    "M8": (8.0, 1.25, 7.78, 15.0, 4.0, 0.72),
    "M10": (10.0, 1.5, 9.78, 18.5, 5.0, 0.74),
}
_ISO_SOCKET_CAP = {
    "M4": (4.0, 0.7, 4.0, 7.0, 4.0, 0.65),
    "M5": (5.0, 0.8, 5.0, 8.5, 5.0, 0.65),
    "M6": (6.0, 1.0, 6.0, 10.0, 6.0, 0.68),
    "M8": (8.0, 1.25, 8.0, 13.0, 8.0, 0.7),
    "M10": (10.0, 1.5, 10.0, 16.0, 10.0, 0.72),
}
```

Add a `generate_from_iso(spec: str, head_type: str, length: float) -> RAGCase` method that uses these tables as the ground truth for product dimensions, then derives process plan and die parameters from engineering rules. This produces far more accurate synthetic data than the current random approach.

---

## Task 3: Seed Script

### File: `backend/scripts/seed_rag.py` (new)

CLI script to generate and index synthetic cases. Run once after `docker compose up`:

```
python -m scripts.seed_rag --n 250 --chroma-url http://localhost:8000 --clear
```

Implementation:
1. Parse args: `--n` (default 250), `--chroma-url`, `--clear` (wipe collection first), `--dry-run`
2. If `--clear`: delete and recreate ChromaDB collection
3. Generate cases:
   - 60% from ISO tables (`generate_from_iso`) covering all sizes × head types × lengths
   - 40% from random generator (`generate_rag_case`) for variety
4. Batch upsert to RAG in groups of 20 (Voyage rate limit)
5. Print summary: cases indexed, confidence distribution, sizes covered
6. Exit with code 1 if fewer than 80% of cases indexed successfully

Also add a `docker-compose.yml` service override to run seed on startup:
```yaml
backend:
  ...
  command: >
    sh -c "uv run python -m scripts.seed_rag --n 250 --chroma-url http://chromadb:8000 &&
           uv run uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload"
```
Make this conditional: only seed if `SEED_ON_STARTUP=true` env var is set.

---

## Task 4: RAG Stats Endpoint

### File: `backend/app/api/v1/designs.py`

Add a quick debug endpoint:
```
GET /api/v1/rag/stats
→ { "total_cases": 247, "by_size": {"M6": 52, "M8": 41, ...}, "by_head_type": {...} }
```

This lets you verify seeding worked without connecting to ChromaDB directly.

---

## Acceptance Criteria

- [ ] `docker compose exec backend /app/.venv/bin/python -c "import cadquery; print(cadquery.__version__)"` succeeds
- [ ] `python -m scripts.seed_rag --n 250` completes in < 120s
- [ ] `GET /api/v1/rag/stats` returns `total_cases >= 200`
- [ ] Generate a design for M6×33 flat head bolt → `retrieval_quality` is `exact_match` or `relaxed` (not `no_match`)
- [ ] Retrieved cases show correct part descriptions in ReasoningPanel
- [ ] Generated die OD is always ≥ 2.5× bore diameter (check logs)
- [ ] No `cadquery_not_available_using_trimesh` warnings in backend logs

## Files Modified
- `backend/Dockerfile.dev`
- `backend/app/data/synthetic.py`
- `backend/scripts/seed_rag.py` (new)
- `backend/app/api/v1/designs.py` (add stats endpoint)
- `docker-compose.yml` (add SEED_ON_STARTUP)
