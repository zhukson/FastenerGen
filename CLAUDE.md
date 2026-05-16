# FastenerGen Claude Guide

This file mirrors `AGENTS.md` for Claude Code sessions. Keep it short and
aligned with the current repo boundary.

## Current Role

FastenerGen is the upstream Gong Maoliang reasoning and schema-generation repo.
It owns `PartFeatures -> ProcessForming`, knowledge, verification, experiment
reports, and calibration.

It does not render DXF. Rendering belongs to:

```text
/Users/bobchen/FastenerDrawingEngine
https://github.com/zhukson/FastenerDrawingEngine
```

## Do Not Reintroduce

- frontend UI
- DXF renderer code
- old 3D/STEP/STL/CADQuery code
- old die/punch drawing generation
- synthetic ISO data generation
- Chroma/Voyage/vector-RAG case retrieval
- Redis/Celery/Postgres/MinIO as required local services

Upload and drawing parsing may stay because they support Claude Vision product
drawing tests.

## Current Baseline

```text
Product drawing or PartFeatures JSON
  -> optional DrawingReader Claude Vision
  -> knowledge.loader full-context curated library
  -> ProcessDesigner Gong-style reasoning
  -> ProcessFormingVerifier
  -> experiment/calibration reports
  -> FastenerDrawingEngine handoff
```

Important code:

- `backend/app/data/schemas.py`
- `backend/app/ai/drawing_reader.py`
- `backend/app/ai/process_designer.py`
- `backend/app/knowledge/loader.py`
- `backend/app/ai/verification.py`
- `backend/app/eval/`
- `backend/app/calibration/`
- `backend/scripts/run_gong_experiment.py`

## Next Architecture

The planned migration is search-based process planning:

```text
PartFeatures / product drawing
  -> ManufacturingFeatureGraph
  -> similar case and textbook priors
  -> operation grammar search
  -> physics/Gong-rule filters
  -> deterministic scoring
  -> LLM ranks top3 and explains tradeoffs
  -> ProcessForming
```

Detailed plan:

```text
docs/SEARCH_ROADMAP.md
```

Build this in parallel with the current direct LLM baseline. Do not delete the
baseline until search-mode reports are clearly better.

## Commands

```bash
cd backend
uv sync
uv run pytest -q
```

Square T-cap baseline:

```bash
cd backend
uv run python -m scripts.run_gong_experiment \
  --experiment-id square_t_cap_holdout \
  --part-features experiments/square_t_cap_holdout/input/part_features.json \
  --expected experiments/square_t_cap_holdout/ground_truth/process_parameters_ground_truth.json \
  --exclude-case DJGS-25-8-B001-0358-四方T帽-106S-过模图 \
  --prefer-category square_T_head \
  --candidate-count 1 \
  --max-design-attempts 1 \
  --design-model sonnet
```

## Calibration

`teacher_rationale.json` stores explicit checkpoints: feature observations,
required operations, precedence constraints, and common failure modes. It is
not hidden model chain-of-thought.

Factory calibration assets live under:

```text
backend/app/knowledge/teacher_rationales/factory/
backend/experiments/factory_calibration/
```
