# FastenerGen

Upstream Gong-style cold-heading reasoning for fastener process-forming.

This repo reads product/final-station fastener information, uses the curated
Gong Maoliang knowledge base and factory cases to infer a forming sequence, and
writes a `ProcessForming` schema plus auditable reasoning records.

Current baseline: direct Gong-style LLM planning plus deterministic
verification/calibration.

Next architecture: search-based process planning using manufacturing feature
graphs, operation grammar, rule filtering, deterministic scoring, and LLM
top-candidate ranking. See `docs/SEARCH_ROADMAP.md`.

DXF drawing/rendering is intentionally outside this repo. The downstream
renderer is the sibling repo:

```text
/Users/bobchen/FastenerDrawingEngine
https://github.com/zhukson/FastenerDrawingEngine
```

## Current Scope

FastenerGen owns:

- drawing upload and optional Claude Vision extraction to `PartFeatures`
- Gong-style process reasoning from `PartFeatures`
- `ProcessForming` schema generation
- curated knowledge loading from factory cases, standards, Gong textbook rules, and textbook cases
- rule verification and leave-one-out experiment reports
- calibration reports with teacher-rationale checkpoints for operation-order tuning
- the upcoming search/ranking layer before final `ProcessForming` emission

FastenerGen does not own:

- frontend UI
- DXF rendering
- old die/punch drawing generation
- 3D STEP/STL/CADQuery generation
- vector RAG/Chroma/Voyage case retrieval
- pseudo-reasoning or synthetic ISO case generation

## Data Snapshot

Current knowledge assets under `backend/app/knowledge/`:

- 8 factory case JSONs from real 过模图 DXF/DWG data
- 3 standard-part case JSONs
- 3 Gong/textbook rule files
- 27 textbook case JSONs
- 1 reusable pattern file
- `feature_index.json` with indexed station snippets

New standard forming-process PNGs are staged under:

```text
backend/experiments/standard_case_intake/
```

They are not yet trusted knowledge records. The intake manifest tracks 8 PNGs,
OCR sidecars, and overlap with existing standard JSONs.

## Current Direction

The old one-shot path is the baseline:

```text
PartFeatures
  -> curated knowledge prompt
  -> ProcessDesigner LLM plan
  -> ProcessFormingVerifier
  -> experiment/calibration reports
```

The next path will run in parallel first:

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

The detailed step-by-step plan is in:

```text
docs/SEARCH_ROADMAP.md
```

## Quick Start

```bash
cd backend
uv sync
export ANTHROPIC_API_KEY=...
uv run pytest -q
```

Run the backend API when upload endpoints are useful:

```bash
cd backend
uv run uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload
```

API docs: `http://localhost:8080/api/docs`

## CLI Experiments

The preferred current workflow is command-line experimentation with recorded
outputs.

Square T-cap leave-one-out, using final product features as input and excluding
the matching factory case from runtime knowledge:

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

Each run writes:

- `process_parameters.json`
- `design_reasoning.md`
- `gong_review.md`
- `experiment_report.json`
- `experiment_report.md`

Latest clean square T-cap run:

```text
backend/experiments/square_t_cap_holdout/runs/8d87dfca5bdb/
```

It matched station count (`6`) but missed operation order quality
(`operation_sequence_similarity=0.500`). This is the right next optimization
target for the search/rule/scoring migration.

## Calibration Pipeline

Calibration is the current way to improve Gong reasoning without calling it
"training" too early. It compares a generated `ProcessForming` against a held
out factory/standard answer key, then records both numeric scores and failure
tags.

Single-case calibration from an existing prediction:

```bash
cd backend
uv run python -m scripts.build_calibration_report \
  --case-id DJGS-25-8-B001-0358-四方T帽-106S-过模图 \
  --predicted experiments/square_t_cap_holdout/runs/official_opus47_thinking_compact_20260511/process_parameters.json \
  --teacher-rationale app/knowledge/teacher_rationales/factory/DJGS-25-8-B001-0358-四方T帽-106S-过模图.json \
  --out experiments/square_t_cap_holdout/runs/official_opus47_thinking_compact_20260511/calibration_report.json
```

Batch aggregation from existing predictions:

```bash
cd backend
uv run python -m scripts.build_batch_calibration_report \
  --manifest experiments/square_t_cap_holdout/runs/official_opus47_thinking_compact_20260511/batch_manifest.json \
  --out experiments/square_t_cap_holdout/runs/official_opus47_thinking_compact_20260511/batch_calibration_report.json
```

Teacher rationale / pseudo reasoning is stored as explicit checkpoints, not
hidden chain-of-thought. Current square T-cap artifact:

```text
backend/experiments/square_t_cap_holdout/ground_truth/teacher_rationale.json
```

It contains feature observations, required operations, precedence constraints,
and common failure modes. These checkpoints explain why a generated plan failed
and provide the next targets for prompt/rule improvement.

Factory calibration dataset:

```text
backend/app/knowledge/teacher_rationales/factory/
backend/app/knowledge/teacher_rationales/factory/calibration_dataset.json
backend/experiments/factory_calibration/
```

The factory dataset currently has 8 GT cases and 8 exported teacher rationale
files. `backend/experiments/factory_calibration/prediction_map.json` maps
completed prediction files into a batch manifest; as more holdout runs finish,
add them there and regenerate:

```bash
cd backend
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

## Schema Handoff

Base contract:

```text
backend/app/data/schemas.py::ProcessForming
```

Renderer contract:

```text
/Users/bobchen/FastenerDrawingEngine/src/fastener_drawing_engine/schema/process.py::ProcessForming
```

The renderer accepts FastenerGen's base `ProcessForming`. For high-fidelity
drawings it benefits from optional `geometry_25d` on station workpieces and
optional top-level `drawing` views/tables. FastenerGen should emit semantic
features and dimensions, not raw DXF coordinates.
