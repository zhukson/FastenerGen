# Session 5: Evaluation Infrastructure

Read @CLAUDE.md for project context. Sessions 1-4 must be complete.

## Goal

Build comprehensive eval so every code change is measured. Without eval, you're flying blind. This session creates: golden test set, automated metrics, LLM-as-judge, regression testing, A/B testing for prompts, and an eval dashboard.

## Task 1: Golden Test Set

Create 25+ hand-crafted test cases in `backend/app/eval/datasets/golden/`.

Each case is a JSON file:

```json
{
  "id": "golden_001",
  "description": "Standard M6 hex bolt, simple case",
  "difficulty": "easy",
  "input": { /* PartFeatures JSON */ },
  "expected": {
    "station_count_range": [2, 3],
    "blank_diameter_range_mm": [5.0, 6.0],
    "expected_post_processes": ["thread_rolling"],
    "die_material_options": ["SKD11", "DC53"],
    "must_mention_risks": ["upset_ratio"],
    "must_not_do": ["single_station_for_complex_head"]
  },
  "notes": "Baseline case. Should always pass."
}
```

Categories:
- **Easy** (10): Standard hex bolts, pan heads, simple flanges
- **Medium** (7): Compound heads, unusual materials, tight tolerances
- **Hard** (5): Multi-feature heads, borderline upset ratios, very small/large sizes
- **Adversarial** (3): Missing data, impossible specs, ambiguous drawings
- **Real** (1+): The actual 18149-D6 PDF if we can determine expected process plan

Golden cases are immutable once added. Store in git. Only add, never remove or modify.

## Task 2: Automated Metrics

Create `backend/app/eval/metrics.py`:

```python
class DesignMetrics:
    def evaluate(self, result: DesignResult, expected: ExpectedDecisions) -> MetricsReport:
        """
        Metrics (each returns MetricResult with name, passed, actual, expected, message):
        
        1. station_count_correct: within expected range
        2. blank_size_reasonable: within expected range  
        3. material_appropriate: die material in allowed list
        4. post_processes_correct: expected processes present
        5. risks_identified: must-mention risks are mentioned
        6. no_violations: must_not_do items absent
        7. schema_valid: output matches Pydantic schema
        8. verification_passed: internal verification passed
        9. files_complete: all expected output files exist
        10. dwg_valid: generated DXF can be re-parsed by ezdxf
        11. stl_valid: generated STL can be loaded by trimesh
        
        Overall score: fraction of passed metrics (0.0 - 1.0)
        """
```

## Task 3: LLM-as-Judge

Create `backend/app/eval/judge.py`:

```python
class LLMJudge:
    """Use Claude Opus 4.7 as a senior engineer reviewer."""
    
    JUDGE_PROMPT = """
    You are a senior cold-heading die design engineer reviewing a design proposal.
    
    Product: {part_features}
    Proposed design: {design_result}
    
    Rate 1-5 on each criterion with brief justification:
    1. Process feasibility (would this work in production?)
    2. Station count appropriateness
    3. Die material selection
    4. Dimensional accuracy (compensations reasonable?)
    5. Risk identification quality
    6. Overall engineering quality
    
    Would you approve for production? (yes / yes_with_mods / no)
    """
    
    async def judge(self, result: DesignResult) -> JudgeReport:
        """Run judge, return structured scores."""
```

## Task 4: Regression Testing

Create `backend/app/eval/regression.py`:

```python
class RegressionTester:
    async def run_full_eval(self) -> EvalSuiteResult:
        """Run all golden cases through pipeline, collect all metrics."""
    
    def compare_to_baseline(self, current, baseline_path) -> ComparisonReport:
        """
        Alert if:
        - Overall score drops > 5%
        - Any case flips from pass → fail
        - LLM judge average drops > 0.5
        """
    
    def save_baseline(self, result, path="eval/baseline.json"): ...
```

CI integration: run eval on main branch pushes (when API keys available).

## Task 5: Prompt A/B Testing

Create `backend/app/eval/ab_testing.py`:

```python
class PromptABTest:
    """Compare two prompt versions on golden test cases."""
    
    async def run(self, variant_a: str, variant_b: str) -> ABTestReport:
        """
        Run both variants on all golden cases.
        Statistical comparison (paired t-test).
        Recommendation: which is better and by how much.
        """
```

## Task 6: Eval Dashboard (Frontend)

Create `/eval` page:
- Summary card: overall score, trend, last run date
- Score history: line chart (Recharts) over time
- Case table: all golden cases with pass/fail, score, difficulty
- Click case: see input → expected → actual comparison
- Trigger eval run button (admin)

## Task 7: Eval API

```
GET  /api/v1/eval/latest           # Latest eval results
GET  /api/v1/eval/history          # Historical scores
GET  /api/v1/eval/cases            # List golden cases  
GET  /api/v1/eval/cases/{id}       # Case detail
POST /api/v1/eval/run              # Trigger eval run
```

## Verification Checklist

- [ ] 25+ golden cases defined and loading correctly
- [ ] Automated metrics compute for synthetic pipeline output
- [ ] LLM judge returns structured scores
- [ ] Regression tester detects quality drops
- [ ] A/B test framework compares two prompt versions
- [ ] Eval dashboard shows scores and history
- [ ] Baseline saved and checked into `eval/baseline.json`
- [ ] CI workflow includes eval step (conditional on API key availability)
