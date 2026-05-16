# Development Guide

## Prerequisites

- Python 3.12 or 3.13
- `uv`
- `ANTHROPIC_API_KEY` for real LLM runs
- Optional: Docker for the backend API

No Node/frontend setup is required. The frontend was removed until the
FastenerDrawingEngine renderer is ready for an integrated UI.

The main development loop is CLI-first:

```text
write or update schemas/rules
  -> run focused pytest
  -> run a holdout/search experiment
  -> inspect Markdown/JSON reports
```

## Install

```bash
cd backend
uv sync
```

## Test

```bash
cd backend
uv run pytest -q
```

Targeted checks:

```bash
uv run pytest tests/knowledge/test_loader_holdout.py tests/eval/test_experiment_report.py -q
uv run pytest tests/calibration -q
uv run pytest tests/api/test_core_surface.py tests/drawings/test_parser.py -q
```

When the search modules are added, use focused TDD slices first:

```bash
uv run pytest tests/search -q
```

## Run API

The API is useful for upload/debug flows, but CLI experiments are the current
primary workflow.

```bash
cd backend
uv run uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload
```

Docs: `http://localhost:8080/api/docs`

Docker:

```bash
docker-compose up backend
```

## Run Experiments

Use pre-extracted final product features:

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

Use a product drawing and Claude Vision first:

```bash
uv run python -m scripts.run_gong_experiment \
  --experiment-id manual_pdf \
  --product-drawing /path/to/product.pdf \
  --self-consistency-runs 1 \
  --candidate-count 1 \
  --max-design-attempts 1
```

Outputs are written under `backend/experiments/<experiment_id>/runs/<run_id>/`.

## Planned Search Experiments

The search path is not implemented yet. The implementation plan is in
`../docs/SEARCH_ROADMAP.md`.

The intended future CLI shape is:

```bash
cd backend
uv run python -m scripts.run_search_experiment \
  --experiment-id square_t_cap_search_holdout \
  --part-features experiments/square_t_cap_holdout/input/part_features.json \
  --expected experiments/square_t_cap_holdout/ground_truth/process_parameters_ground_truth.json \
  --exclude-case DJGS-25-8-B001-0358-四方T帽-106S-过模图 \
  --prefer-family square_T_head \
  --top-k 3
```

Expected future artifacts:

- `feature_graph.json`
- `candidate_plans.json`
- `candidate_report.md`
- `selected_process_parameters.json`
- `search_calibration_report.json`

Do not replace `scripts.run_gong_experiment` until search reports clearly beat
the current direct LLM baseline.

## Run Calibration

Calibration reuses existing predictions and does not call an LLM. Use it to
score one case, export teacher rationale checkpoints, or aggregate multiple
case reports.

Single-case report:

```bash
cd backend
uv run python -m scripts.build_calibration_report \
  --case-id DJGS-25-8-B001-0358-四方T帽-106S-过模图 \
  --predicted experiments/square_t_cap_holdout/runs/official_opus47_thinking_compact_20260511/process_parameters.json \
  --teacher-rationale app/knowledge/teacher_rationales/factory/DJGS-25-8-B001-0358-四方T帽-106S-过模图.json \
  --out experiments/square_t_cap_holdout/runs/official_opus47_thinking_compact_20260511/calibration_report.json
```

Teacher rationale / pseudo reasoning checkpoint export:

```bash
uv run python -m scripts.export_teacher_rationale \
  --case-id DJGS-25-8-B001-0358-四方T帽-106S-过模图 \
  --out experiments/square_t_cap_holdout/ground_truth/teacher_rationale.json
```

Batch report:

```bash
uv run python -m scripts.build_batch_calibration_report \
  --manifest experiments/square_t_cap_holdout/runs/official_opus47_thinking_compact_20260511/batch_manifest.json \
  --out experiments/square_t_cap_holdout/runs/official_opus47_thinking_compact_20260511/batch_calibration_report.json
```

Factory 8-case checkpoint export and dataset:

```bash
uv run python -m scripts.export_teacher_rationales \
  --source factory \
  --out-dir app/knowledge/teacher_rationales/factory

uv run python -m scripts.build_calibration_dataset \
  --source factory \
  --teacher-rationale-dir app/knowledge/teacher_rationales/factory \
  --out app/knowledge/teacher_rationales/factory/calibration_dataset.json
```

Aggregate completed factory predictions:

```bash
uv run python -m scripts.build_batch_manifest \
  --dataset app/knowledge/teacher_rationales/factory/calibration_dataset.json \
  --prediction-map experiments/factory_calibration/prediction_map.json \
  --eval-id factory_calibration_completed_predictions \
  --out experiments/factory_calibration/batch_manifest.json

uv run python -m scripts.build_batch_calibration_report \
  --manifest experiments/factory_calibration/batch_manifest.json \
  --out experiments/factory_calibration/batch_calibration_report.json

uv run python -m scripts.summarize_batch_calibration \
  --report experiments/factory_calibration/batch_calibration_report.json \
  --out experiments/factory_calibration/batch_calibration_report.md
```

For future 30+ case calibration, create a manifest with:

```json
{
  "eval_id": "factory-standard-gong-calibration",
  "cases": [
    {
      "case_id": "CASE_ID",
      "predicted": "experiments/.../process_parameters.json",
      "teacher_rationale": "app/knowledge/teacher_rationales/factory/CASE_ID.json",
      "retrieved_case_ids": []
    }
  ]
}
```

## Intake New Standard PNG Cases

New factory standard forming-process PNGs should be staged before they enter
`backend/app/knowledge/standards/`.

```bash
cd backend
uv run python -m scripts.build_standard_case_intake \
  --source-dir /Users/bobchen/FastenerGen/fasternerGenData/标准件 \
  --out experiments/standard_case_intake/manifest.json

uv run python -m scripts.ocr_standard_case_intake \
  --manifest experiments/standard_case_intake/manifest.json \
  --out-dir experiments/standard_case_intake/ocr

uv run python -m scripts.build_standard_case_intake \
  --source-dir /Users/bobchen/FastenerGen/fasternerGenData/标准件 \
  --ocr-dir experiments/standard_case_intake/ocr \
  --out experiments/standard_case_intake/manifest.json
```

`manifest.json` records each source PNG, parsed DIN/M/P/length range, OCR
sidecar path, and any overlap with existing standard records. Items marked
`needs_review_existing_overlap` should be reviewed before overwriting or adding
new CaseRecord JSONs.

## Add A New Holdout Experiment

1. Create `backend/experiments/<name>/input/part_features.json`.
2. Create `backend/experiments/<name>/ground_truth/process_parameters_ground_truth.json`.
3. Run `scripts.run_gong_experiment` with `--exclude-case <case_id>`.
4. Inspect `experiment_report.md`.
5. Build `calibration_report.json` for the run.
6. Export or update `teacher_rationale.json` when the GT should become a
   durable calibration checkpoint.
7. Commit meaningful experiment inputs and summaries, not large generated noise.

## Slim Repo Rules

Keep this repo focused on upstream reasoning:

- keep `app/ai`, `app/knowledge`, `app/calibration`, `app/eval`, and schema code
- keep upload/drawing parsing only where it supports `PartFeatures` extraction
- keep tests and experiment summaries that explain current progress
- do not add frontend, DXF rendering, CADQuery, 3D export, vector-RAG services,
  Redis/Celery/Postgres/MinIO, or synthetic ISO generators

Renderer work belongs in:

```text
/Users/bobchen/FastenerDrawingEngine
```

## Lint / Type Check

```bash
cd backend
uv run ruff check .
uv run ruff format .
uv run mypy app
```

## Working With FastenerDrawingEngine

Renderer repo:

```text
/Users/bobchen/FastenerDrawingEngine
```

Validate/render a generated schema there, not in FastenerGen:

```bash
cd /Users/bobchen/FastenerDrawingEngine
uv run python -m fastener_drawing_engine.cli validate-schema \
  /Users/bobchen/FastenerGen/backend/experiments/square_t_cap_holdout/runs/8d87dfca5bdb/process_parameters.json
```

FastenerGen should emit semantic process/geometry data. It should not emit raw
DXF entities or drawing coordinates except optional high-level layout hints.
