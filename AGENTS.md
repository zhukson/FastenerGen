# FastenerGen Agent Guide

## Current Role

FastenerGen is the upstream Gong Maoliang reasoning and schema-generation repo.
It does not render DXF drawings.

It produces:

- `PartFeatures` from product/final-station data or optional drawing upload
- `ProcessForming` schema
- `design_reasoning.md`
- `gong_review.md`
- `experiment_report.json/md`
- `calibration_report.json` / `batch_calibration_report.json`
- `teacher_rationale.json` checkpoint files

DXF rendering belongs to the sibling repo:

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

Upload and input drawing parsing may remain because they support Claude Vision
and future product-drawing tests.

## Current Baseline

The current working path is direct Gong-style LLM planning:

```text
Product drawing or PartFeatures JSON
  -> optional DrawingReader Claude Vision
  -> knowledge.loader full-context curated library
  -> ProcessDesigner Gong-style reasoning
  -> ProcessFormingVerifier
  -> experiment/calibration reports
  -> FastenerDrawingEngine handoff
```

Main code:

- `backend/app/data/schemas.py`: Pydantic contracts
- `backend/app/ai/drawing_reader.py`: optional drawing understanding
- `backend/app/ai/process_designer.py`: baseline `PartFeatures -> ProcessForming`
- `backend/app/knowledge/loader.py`: curated knowledge and holdout-safe prompt formatting
- `backend/app/ai/verification.py`: rule checks
- `backend/app/eval/metrics.py`: Gong/eval metrics
- `backend/app/eval/experiment_report.py`: report writer
- `backend/app/calibration/`: teacher-rationale checkpoints and calibration scorecards
- `backend/scripts/run_gong_experiment.py`: primary current CLI workflow

## Next Architecture

The next major direction is search-based process planning:

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

Do not replace `ProcessDesigner` directly. Build the search path in parallel,
with focused TDD slices under planned modules:

```text
backend/app/search/
  features.py
  operations.py
  templates.py
  family_matcher.py
  candidate.py
  generator.py
  constraints.py
  scoring.py
  ranker.py
  reports.py
```

## Knowledge Assets

Current knowledge under `backend/app/knowledge/`:

- 8 factory cases
- 3 standard cases
- 3 textbook rule files
- 27 textbook cases
- 1 pattern file
- `feature_index.json` with station snippets

New standard PNG intake is staged here and is not loaded as trusted knowledge
until converted to reviewed CaseRecord JSON:

```text
backend/experiments/standard_case_intake/manifest.json
backend/experiments/standard_case_intake/ocr/*.ocr.txt
```

Leave-one-out experiments must pass `exclude_case_ids`. Exclusion must apply to
full-context case XML, relevant station snippets, and confidence/neighbor
signals.

## Current Experiments

Square T-cap holdout:

```text
backend/experiments/square_t_cap_holdout/
```

Clean run:

```text
backend/experiments/square_t_cap_holdout/runs/8d87dfca5bdb/
```

Result:

- station count matched: `6`
- operation sequence similarity: `0.500`
- operation alignment: `0.500`
- schema readiness metrics passed

Interpretation: the model understands station-count complexity but needs
stronger operation grammar, precedence checks, and candidate scoring.

Factory calibration assets:

```text
backend/app/knowledge/teacher_rationales/factory/
backend/app/knowledge/teacher_rationales/factory/calibration_dataset.json
backend/experiments/factory_calibration/
```

`teacher_rationale.json` stores explicit feature observations, required
operations, precedence constraints, and common failure modes. It is not hidden
model chain-of-thought.

## Commands

Install/test:

```bash
cd backend
uv sync
uv run pytest -q
```

Run square T-cap holdout:

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

Optional API:

```bash
cd backend
uv run uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload
```

## Renderer Schema Alignment

FastenerGen base schema:

```text
backend/app/data/schemas.py::ProcessForming
```

Renderer schema:

```text
/Users/bobchen/FastenerDrawingEngine/src/fastener_drawing_engine/schema/process.py::ProcessForming
```

The renderer accepts the base shape and can use optional `geometry_25d` and
`drawing` extensions. Upstream should emit semantic geometry/features and true
dimensions, not raw DXF entities.
