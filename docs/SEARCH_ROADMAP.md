# Search-Based Gong Reasoning Roadmap

This document is the working plan for migrating FastenerGen from "LLM writes one
complete ProcessForming" to a scalable search-and-rank process-planning system.

## Why This Pivot

The current `ProcessDesigner` can produce a plausible `ProcessForming`, but it
is still too dependent on one LLM pass and prompt wording. The failure mode is
clear in the square T-cap holdout: station count is right, but operation order
and required operation coverage are not reliable enough.

The target system should behave more like a knowledge-based process planning
tool:

```text
PartFeatures / product drawing
  -> semantic manufacturing feature graph
  -> similar-case and textbook priors
  -> operation grammar search
  -> physics and Gong-rule filters
  -> deterministic scoring
  -> LLM ranks top candidates and explains tradeoffs
  -> ProcessForming schema
```

The renderer remains downstream in `FastenerDrawingEngine`. FastenerGen should
emit semantic features and forming intent, not DXF entities.

## Core Principle

Do not hard-code one full process template per part. Templates should be search
priors, not answers.

The scalable abstraction is:

```text
ManufacturingFeatureGraph
  = geometry primitives
  + topology/relations
  + dimensions/tolerances/material
  + forming semantics
  + operation reachability
```

Examples of feature nodes:

- `cylindrical_shank`
- `flange`
- `square_head`
- `hex_head`
- `recess`
- `through_hole`
- `blind_hole`
- `thread_blank`
- `neck`
- `step`
- `fillet`
- `chamfer`

Examples of operations:

- `cutoff`
- `upsetting`
- `pre_upsetting`
- `forward_extrusion`
- `backward_extrusion`
- `heading`
- `flange_forming`
- `polygon_head_forming`
- `socket_forming`
- `piercing`
- `trimming`
- `sizing`
- `thread_rolling`

## Target Modules

Keep these modules under `backend/app/search/` once implementation starts:

```text
backend/app/search/
  features.py          # ManufacturingFeatureGraph, feature nodes, relations
  operations.py        # Operation definitions and pre/post conditions
  templates.py         # Family priors and reusable skeletons
  family_matcher.py    # PartFeatures -> candidate families
  candidate.py         # CandidatePlan and SearchTrace contracts
  generator.py         # DFS / beam-search candidate generation
  constraints.py       # physics + Gong-rule pruning
  scoring.py           # deterministic score breakdown
  ranker.py            # LLM top-N rank/explanation, not raw generation
  reports.py           # candidate search report writer
```

The first implementation should not replace `ProcessDesigner` all at once. It
should run as a parallel path, then become the default after reports are better
than the direct LLM path.

## New Contracts

### ManufacturingFeatureGraph

Input to the search engine. It can be derived from `PartFeatures` first, then
later enriched by Claude Vision or a product-drawing extractor.

Minimum fields:

```text
part_id
material
overall_length_mm
wire_or_blank_hints
features[]
relations[]
source_confidence
```

Each feature should carry:

```text
feature_id
kind
dimensions
tolerances
position_hint
source
confidence
```

### CandidatePlan

Intermediate search result before final `ProcessForming`.

Minimum fields:

```text
candidate_id
family
template_id
feature_graph_id
station_count
station_sequence
operation_sequence
parameter_set
source_case_ids
constraint_results
score_breakdown
search_trace
```

### SearchTrace

Audit trail for why a candidate exists or was rejected.

Minimum fields:

```text
generated_by
matched_features
applied_template_priors
operation_choices
pruned_reasons
warnings
```

## Metrics

Every search experiment should report:

- `station_count_match`
- `required_operation_recall`
- `operation_sequence_similarity`
- `precedence_constraint_recall`
- `invalid_candidate_filter_rate`
- `gt_in_top3` when GT exists
- `top1_gt_similarity`
- `renderer_schema_readiness`
- `score_breakdown_complete`

For process planning, `gt_in_top3` matters more than strict top1 accuracy
because real factories may have more than one workable process.

## Step-by-Step Plan

### Phase 0: Slim And Freeze Boundaries

Goal: keep FastenerGen focused on upstream reasoning.

Tasks:

1. Remove generated caches, orphan scripts, duplicate package stubs, and empty
   legacy directories.
2. Keep upload/drawing input parsing because it supports future Vision tests.
3. Keep calibration, teacher rationale, knowledge, and experiment reports.
4. Do not reintroduce frontend, DXF rendering, 3D/CADQuery, vector RAG, or
   synthetic ISO generation.

Validation:

```bash
cd backend
uv run pytest -q
```

Done when the repo imports cleanly and docs describe the current boundary.

### Phase 1: CandidatePlan Tracer Bullet

Goal: create the smallest public contract for search candidates.

Tasks:

1. Add `backend/app/search/candidate.py`.
2. Add Pydantic models for `CandidatePlan`, `CandidateStation`,
   `ConstraintResult`, `ScoreBreakdown`, and `SearchTrace`.
3. Write one behavior test: a candidate with required fields validates and can
   be serialized to JSON.
4. Add a small adapter that can convert a winning `CandidatePlan` skeleton to a
   basic `ProcessForming`.

Validation:

```bash
cd backend
uv run pytest tests/search -q
```

Done when no LLM call is needed to construct and inspect a candidate.

### Phase 2: Feature Graph From Existing PartFeatures

Goal: represent final product geometry in scalable primitive/feature terms.

Tasks:

1. Add `ManufacturingFeatureGraph`.
2. Convert existing `PartFeatures` into graph nodes for head, shank, thread,
   tail, holes/recesses where available.
3. Add square T-cap fixture manually from the existing holdout
   `part_features.json`.
4. Add graph completeness warnings when a feature is implied but missing
   dimensions.

Validation:

```bash
uv run pytest tests/search/test_feature_graph.py -q
```

Done when the square T-cap input becomes a feature graph containing shank,
flange/head, square/polygon feature, recess/slot when present, and critical
dimensions.

### Phase 3: Operation Grammar

Goal: encode operations as reusable manufacturing actions, not one-off prompt
phrases.

Tasks:

1. Define operations with produced features, consumed prerequisites, risk
   notes, and rough deformation constraints.
2. Start with a compact operation set:
   `cutoff`, `upsetting`, `pre_upsetting`, `forward_extrusion`, `heading`,
   `flange_forming`, `polygon_head_forming`, `piercing`, `trimming`, `sizing`,
   `thread_rolling`.
3. Add precedence helpers such as:
   - material gathering before large head finishing
   - forward extrusion before long reduced shank where needed
   - piercing before final sizing for through holes
   - polygon forming after enough head stock exists
4. Keep textbook/Gong provenance in operation notes where possible.

Validation:

```bash
uv run pytest tests/search/test_operations.py -q
```

Done when each operation has typed pre/post conditions and precedence rules can
be checked without an LLM.

### Phase 4: Template Priors, Not Template Answers

Goal: use family templates to guide search without killing generalization.

Tasks:

1. Add family priors for the first few important groups:
   - `square_T_head`
   - `rivet_screw`
   - `pin_shaft`
   - `socket_cap_screw`
   - `hex_bolt`
   - `nut`
2. For each family, define:
   - likely feature patterns
   - common station count range
   - required/optional operations
   - precedence constraints
   - common failure modes
   - useful source cases/textbook pages
3. Keep priors parameterized. Do not encode exact GT station dimensions as the
   only allowed answer.

Validation:

```bash
uv run pytest tests/search/test_family_matcher.py -q
```

Done when square T-cap matches `square_T_head` strongly but can still expose
secondary candidates if features are ambiguous.

### Phase 5: DFS / Beam Candidate Generation

Goal: generate multiple plausible process plans before any LLM ranking.

Tasks:

1. Implement template-guided DFS first.
2. Limit branching with:
   - max station count
   - required operation coverage
   - family precedence constraints
   - simple deformation bounds
3. Add beam search if DFS produces too many variants.
4. Emit pruned candidates with reasons in `SearchTrace`.

Validation:

```bash
uv run pytest tests/search/test_generator.py -q
```

Done when square T-cap produces a small candidate set, ideally 5-20 candidates,
and obvious bad orders are pruned.

### Phase 6: Constraint Engine

Goal: reject physically or Gong-rule impossible plans before scoring.

Tasks:

1. Reuse existing `ProcessFormingVerifier` checks where possible.
2. Add candidate-level checks before conversion to `ProcessForming`:
   - operation prerequisites
   - station count bounds
   - required operation coverage
   - major deformation staged before finishing
   - thread/process compatibility
3. Add failure tags aligned with calibration:
   `missing_required_operation`, `wrong_precedence`,
   `station_alignment_error`, `deformation_risk`, `schema_incomplete`.

Validation:

```bash
uv run pytest tests/search/test_constraints.py -q
```

Done when invalid square T-cap plans fail deterministically with useful tags.

### Phase 7: Deterministic Scoring

Goal: rank candidates numerically before asking an LLM.

Tasks:

1. Add score components:
   - `operation_coverage_score`
   - `precedence_score`
   - `deformation_safety_score`
   - `feature_progression_score`
   - `case_similarity_score`
   - `renderer_readiness_score`
2. Store all components in `score_breakdown`.
3. Sort candidates by total score.
4. Add report output showing top candidates and rejected reasons.

Validation:

```bash
uv run pytest tests/search/test_scoring.py -q
```

Done when the GT-like square T-cap sequence scores above intentionally flawed
variants without using an LLM.

### Phase 8: LLM Top-3 Ranking

Goal: shrink LLM responsibility to engineering judgment and explanation.

Tasks:

1. Give the LLM only top 3-5 candidates plus compact evidence.
2. Ask it to rank, explain tradeoffs, and flag risks.
3. Forbid it from inventing a new process outside the candidate set in the
   first version.
4. Persist `candidate_ranking.md` and machine-readable ranking JSON.

Validation:

```bash
uv run pytest tests/search/test_ranker_prompt.py -q
```

Done when a run is auditable: each top candidate has a deterministic score and
an LLM explanation.

### Phase 9: Search Experiment CLI

Goal: run leave-one-out search experiments without touching the old direct LLM
path.

Tasks:

1. Add `scripts/run_search_experiment.py`.
2. Inputs:
   - `--part-features`
   - `--expected`
   - `--exclude-case`
   - `--prefer-family`
   - `--top-k`
3. Outputs:
   - `feature_graph.json`
   - `candidate_plans.json`
   - `candidate_report.md`
   - `selected_process_parameters.json`
   - `search_calibration_report.json`
4. Reuse existing calibration metrics where possible.

Validation:

```bash
uv run python -m scripts.run_search_experiment \
  --experiment-id square_t_cap_search_holdout \
  --part-features experiments/square_t_cap_holdout/input/part_features.json \
  --expected experiments/square_t_cap_holdout/ground_truth/process_parameters_ground_truth.json \
  --exclude-case DJGS-25-8-B001-0358-四方T帽-106S-过模图 \
  --prefer-family square_T_head \
  --top-k 3
```

Done when search-mode reports can be compared against the existing direct LLM
square T-cap report.

### Phase 10: Expand Cases

Goal: evaluate whether the search system generalizes.

Order:

1. Factory 8 cases.
2. Standard DIN912/DIN933 cases.
3. Manually reviewed Gong textbook cases.
4. Remaining Gong pages after manual visual review.

Validation:

```bash
uv run python -m scripts.build_batch_calibration_report ...
```

Done when the aggregate report shows better required operation recall and
precedence recall than direct LLM generation.

## When To Consider GA

Do not start with genetic algorithms. GA is useful only after these pieces are
stable:

- feature graph
- operation grammar
- constraints
- scoring
- candidate report

Then GA can optimize parameter values or station variants inside a controlled
search space. Without that structure it will generate many process-like but
engineering-invalid plans.

## Immediate Next Slice

The next implementation slice should use TDD:

```text
RED: test CandidatePlan serializes and carries score/trace
GREEN: implement minimal CandidatePlan models
RED: test square T-cap PartFeatures -> feature graph
GREEN: implement feature graph adapter
RED: test square T-cap family match
GREEN: implement first family matcher
```

Do not modify `ProcessDesigner` until these pieces exist and have focused
tests. The old path remains the baseline for comparison.
