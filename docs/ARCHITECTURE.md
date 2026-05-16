# Architecture

FastenerGen is the upstream reasoning/schema system. It is deliberately small:
Python backend, curated knowledge files, deterministic validation, calibration,
and CLI experiment records.

## Boundary

```text
Product drawing or final product features
        |
        v
PartFeatures
        |
        v
Gong-style reasoning + curated experience library
        |
        v
ProcessForming JSON + reasoning/report sidecars
        |
        v
Calibration reports + teacher-rationale checkpoints
        |
        v
FastenerDrawingEngine renders DXF in a separate repo
```

This repo does not render DXF, manage a frontend, generate 3D, or perform
vector RAG. Those concerns were removed to keep the upstream reasoning loop
fast and testable.

The current production baseline is direct LLM planning. The planned migration is
search-based process planning:

```text
PartFeatures
        |
        v
ManufacturingFeatureGraph
        |
        v
operation grammar + family priors + similar cases
        |
        v
candidate generation
        |
        v
rule/physics filtering + deterministic scoring
        |
        v
LLM top3 ranking and tradeoff explanation
        |
        v
ProcessForming JSON
```

The implementation plan is tracked in `docs/SEARCH_ROADMAP.md`.

## Runtime Components

| Component | Path | Responsibility |
|---|---|---|
| API app | `backend/app/main.py` | Optional FastAPI surface for upload/debug use |
| Drawing reader | `backend/app/ai/drawing_reader.py` | Claude Vision extraction to `PartFeatures` |
| Process designer | `backend/app/ai/process_designer.py` | `PartFeatures` -> `ProcessForming` |
| Knowledge loader | `backend/app/knowledge/loader.py` | Full-context few-shot XML and feature snippets |
| Verifier | `backend/app/ai/verification.py` | Rule checks on generated `ProcessForming` |
| Eval metrics | `backend/app/eval/metrics.py` | Station count, operation sequence, schema readiness |
| Experiment reports | `backend/app/eval/experiment_report.py` | JSON/Markdown record writer |
| Calibration | `backend/app/calibration/` | Teacher-rationale checkpoints, case reports, batch scorecards |
| CLI experiment runner | `backend/scripts/run_gong_experiment.py` | Main current workflow |
| Search roadmap | `docs/SEARCH_ROADMAP.md` | Planned candidate-search architecture and TDD slices |

Planned search modules should live under `backend/app/search/` once built:

```text
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

## Knowledge Layer

Active knowledge is file-based and loaded in-process:

- `knowledge/cases/`: 8 real factory cases
- `knowledge/standards/`: 3 standard-part cases
- `knowledge/textbook_rules/`: Gong Maoliang and 1D2B distilled rules
- `knowledge/textbook_cases/`: 27 textbook examples
- `knowledge/patterns/`: reusable sequence patterns
- `knowledge/feature_index.json`: indexed station snippets

There is no Chroma/Voyage/vector retrieval in this repo. With this data scale,
full-context curated knowledge is more reliable and easier to audit.

Standard PNG intake is staged separately:

```text
backend/experiments/standard_case_intake/manifest.json
backend/experiments/standard_case_intake/ocr/*.ocr.txt
```

These files describe newly supplied DIN912/DIN933 forming-process PNGs and OCR
sidecars. They are not loaded as knowledge until converted into reviewed
`CaseRecord` JSONs under `knowledge/standards/`.

## Main CLI Flow

```text
scripts.run_gong_experiment
  -> load PartFeatures JSON or run DrawingReader on product drawing
  -> ProcessDesigner.design_from_part_features/design
  -> knowledge.loader.format_for_prompt(exclude_case_ids=...)
  -> Claude process planning
  -> ProcessFormingVerifier
  -> process_parameters.json
  -> design_reasoning.md
  -> gong_review.md
  -> experiment_report.json/md
```

The `exclude_case_ids` argument removes held-out cases from both the full case
dump and the feature-indexed station snippets. The confidence signal also
respects the same exclusion so reports do not leak held-out answers.

## Planned Search Flow

The search flow will initially run next to the direct LLM flow, not replace it.
This keeps the current square T-cap and calibration reports as a baseline.

```text
PartFeatures
  -> ManufacturingFeatureGraph
  -> family matcher
  -> operation grammar
  -> DFS / beam candidate generation
  -> constraint filtering
  -> deterministic scoring
  -> optional LLM top3 ranker
  -> selected ProcessForming
```

Key contracts to add:

- `ManufacturingFeatureGraph`: semantic geometry/features from product/final
  station data.
- `CandidatePlan`: a candidate station sequence with operations, parameters,
  score breakdown, and search trace.
- `SearchTrace`: why a candidate was generated, pruned, or ranked.

The key evaluation question changes from "did one model answer match the GT
exactly?" to "did the GT-like or engineering-valid plan survive filtering and
appear in top3?"

## Calibration Flow

Calibration is offline and can run on existing predictions without another LLM
call:

```text
ProcessForming prediction + held-out CaseRecord
  -> build_case_record_eval_case
  -> load persisted teacher_rationale.json when present
  -> otherwise build_teacher_rationale_from_eval_case
  -> compute_process_forming_metrics
  -> score_teacher_rationale_alignment
  -> calibration_report.json
```

Teacher rationale is not model chain-of-thought. It is a deterministic,
auditable set of engineering checkpoints:

- `feature_observations`: what product features should trigger which forming
  inferences
- `required_operations`: operations that appear in the GT process
- `precedence_constraints`: operation order implied by the GT station sequence
- `common_failure_modes`: known ways the model can get this family wrong

Batch calibration wraps multiple case reports and emits:

- metric means
- metric pass rates
- failure tag counts
- embedded per-case reports

Current scripts:

```text
backend/scripts/build_calibration_report.py
backend/scripts/build_batch_calibration_report.py
backend/scripts/build_batch_manifest.py
backend/scripts/build_calibration_dataset.py
backend/scripts/export_teacher_rationale.py
backend/scripts/export_teacher_rationales.py
backend/scripts/summarize_batch_calibration.py
```

Factory calibration assets:

```text
backend/app/knowledge/teacher_rationales/factory/
backend/app/knowledge/teacher_rationales/factory/calibration_dataset.json
backend/experiments/factory_calibration/prediction_map.json
backend/experiments/factory_calibration/batch_manifest.json
backend/experiments/factory_calibration/batch_calibration_report.json
backend/experiments/factory_calibration/batch_calibration_report.md
```

The dataset includes all 8 factory GT cases. The current completed-prediction
batch report includes the square T-cap run; add new completed holdout
predictions to `prediction_map.json` to expand the aggregate scorecard.

## Schema Contract

FastenerGen base schema:

```text
backend/app/data/schemas.py::ProcessForming
```

FastenerDrawingEngine compatible schema:

```text
/Users/bobchen/FastenerDrawingEngine/src/fastener_drawing_engine/schema/process.py::ProcessForming
```

The renderer accepts the base fields:

- `part_name_zh`
- `material`
- `blank`
- `stations[]`
- `post_processes`
- `reasoning_zh`
- `cited_case_ids`
- `confidence`

For better drawings, upstream should eventually add semantic `geometry_25d`
details and optional `drawing` layout/view specifications. These must remain
semantic engineering features, not raw DXF line endpoints.

## Current Evaluation

The current key experiment is:

```text
backend/experiments/square_t_cap_holdout/
```

Latest clean run:

```text
backend/experiments/square_t_cap_holdout/runs/8d87dfca5bdb/
```

Result:

- station count matched: `6`
- operation sequence similarity: `0.500`
- operation alignment: `0.500`
- schema readiness metrics passed

Interpretation: the system understands the complexity and final geometry
requirements, but still needs stronger operation grammar, precedence rules, and
candidate scoring.

Additional Opus/thinking square T-cap run:

```text
backend/experiments/square_t_cap_holdout/runs/official_opus47_thinking_compact_20260511/
```

Current calibration diagnosis:

- station count matched: `6`
- required operation recall: `0.833`, missing `forward_extrusion`
- precedence constraint recall: `0.200`
- failure tags: `missing_required_operation`, `wrong_precedence`,
  `wrong_operation_sequence`, `station_alignment_error`

Teacher rationale checkpoint file:

```text
backend/experiments/square_t_cap_holdout/ground_truth/teacher_rationale.json
```
