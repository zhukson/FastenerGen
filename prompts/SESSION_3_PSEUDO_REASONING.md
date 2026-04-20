# Session 3: Pseudo-Reasoning Pipeline

Read @CLAUDE.md for project context. Sessions 1-2 must be complete.

## Goal

Build the pipeline that generates engineering reasoning for product-to-die design pairs without a domain expert. This is the knowledge bootstrap: Claude Opus 4.7 analyzes each pair to infer WHY the design decisions were made, cross-validated by Gemini and rule-based checks.

## Why This Matters

Our RAG system returns similar historical cases as few-shot examples. Without reasoning, these examples are just "input shape → output shape" with no explanation. The LLM can copy the pattern but can't adapt it to differences. With reasoning ("3 stations because upset ratio 2.3 exceeds safe single-blow limit for SCM435"), the LLM can adjust decisions for new situations.

## Task 1: Prompt Design

Create all prompts in `backend/app/ai/prompts/pseudo_reasoning.py`.

Every prompt has: version string, docstring, input/output schema reference.

### Primary Reasoning Prompt (Claude Opus 4.7)

Input: product features + die parameters + geometric diff (all JSON).
Output: structured analysis with confidence levels.

The prompt must instruct the LLM to:
1. List **observable facts** from the data (no inference, just what's visible)
2. Infer **likely reasoning** for each major design decision, using hedged language ("likely because", "suggests that", "consistent with")
3. Identify **critical parameters** with typical acceptable ranges
4. Analyze **dimensional compensations** (product → die differences)
5. Flag **potential risks** and failure modes
6. Self-assess **confidence** per section and overall

Rules embedded in prompt:
- Never fabricate numbers not present in input data
- Always qualify inferences with confidence level
- Explicitly flag ambiguities
- Reference specific cold-heading engineering principles

### Cross-Validation Prompt (Gemini 2.5 Pro)

Input: same data pair + Claude's primary reasoning.
Output: agreement/disagreement per section, alternative reasoning if disagreeing, missed observations.

### Version both prompts: `PR_V1_0_0`, `CV_V1_0_0`.

## Task 2: Pipeline Implementation

Create `backend/app/ai/reasoning.py`:

```python
class PseudoReasoningPipeline:
    """
    Generate pseudo-reasoning for product-die pairs.
    
    1. Claude Opus 4.7 × 3 runs (self-consistency)
    2. Gemini 2.5 Pro × 1 run (cross-validation)
    3. Rule-based verifier (physics + data grounding)
    4. Aggregate → confidence score → ReasoningResult
    """
    
    async def generate(self, pair: ProductDiePair) -> ReasoningResult: ...
    async def _run_primary(self, pair, run_index: int) -> PrimaryReasoning: ...
    async def _run_cross_validation(self, pair, primary) -> CrossValidation: ...
    def _run_rule_verifier(self, pair, reasoning) -> RuleVerification: ...
    def _aggregate(self, primaries, cross_val, rules) -> ReasoningResult: ...
```

Implementation requirements:
- **Async** with proper rate limiting for both APIs
- **Retry** with exponential backoff (3 attempts per call)
- **Caching** in Redis (key = hash of input pair, invalidate on prompt version change)
- **Cost tracking**: log input/output tokens, calculate USD cost per call and cumulative
- **Timeout**: 90 seconds per LLM call, 300 seconds total per pair
- **Structured output**: Use Anthropic tool_use or JSON mode for schema compliance
- **Parallel execution**: Run 3 Claude calls in parallel, then Gemini, then rules

## Task 3: Quality Scoring

Create `backend/app/ai/quality.py`:

```python
class QualityScorer:
    def score(self, primaries, cross_val, rules) -> QualityScores:
        """
        Compute quality metrics:
        - self_consistency: float (0-1) — do 3 Claude runs agree on key decisions?
        - cross_model_agreement: float (0-1) — does Gemini agree?
        - rule_compliance: float (0-1) — fraction of rules passed
        - geometric_grounding: float (0-1) — reasoning references actual input data?
        - overall_confidence: "high" | "medium" | "low"
        
        Thresholds:
        - high: all scores > 0.8
        - medium: all scores > 0.5
        - low: anything else
        """
```

Self-consistency check details:
- Station count: must be identical across 3 runs
- Material choices: must be identical
- Key numerical parameters: within 15% of each other
- Risk mentions: at least 2/3 overlap

## Task 4: Rule-Based Verifier

Part of the quality pipeline but important enough to call out:

```python
class RuleVerifier:
    """Physics and data grounding checks."""
    
    def verify(self, pair, reasoning) -> RuleVerification:
        checks = [
            self._no_hallucinated_numbers(pair, reasoning),
            self._upset_ratio_valid(reasoning),    # typically < 3.5 for cold heading
            self._material_compatibility(reasoning), # die material harder than workpiece
            self._station_count_plausible(pair, reasoning),
            self._volume_conservation(pair, reasoning),
            self._dimensions_consistent(reasoning),
        ]
        return RuleVerification(checks=checks, passed=all(c.passed for c in checks))
```

## Task 5: Batch Processing

Create `backend/scripts/batch_pseudo_reasoning.py`:

```bash
python -m scripts.batch_pseudo_reasoning \
  --input-dir /data/pairs/ \
  --output-dir /data/reasoned/ \
  --concurrency 3 \
  --max-cost-usd 100 \
  --dry-run  # estimate cost without running
  --resume   # skip completed pairs
```

Features:
- Progress bar (tqdm) + structured logs
- Checkpoint after each completed pair (resume on interrupt)
- Cost estimation in dry-run mode
- Summary report: total pairs, pass/fail/skip counts, total cost, confidence distribution
- Error isolation: failed pair → log error → skip → continue

## Task 6: Testing

Create synthetic test pairs (from Session 2's generator) and run the full pipeline:

- 10 synthetic pairs minimum
- Verify: schema compliance, reasonable confidence distribution, cost tracking accuracy
- Test: resume after interruption
- Test: cache hit on repeated run

## Verification Checklist

- [ ] Pipeline generates valid ReasoningResult for 10 synthetic pairs
- [ ] Self-consistency: 3 Claude runs produce comparable results
- [ ] Cross-validation: Gemini call succeeds and produces structured output
- [ ] Rule verifier catches: hallucinated numbers, impossible upset ratios
- [ ] Quality scores compute correctly
- [ ] Cost tracking matches actual API spend (within 10%)
- [ ] Batch script: dry-run shows cost estimate
- [ ] Batch script: resume skips completed pairs
- [ ] All prompts versioned and documented
- [ ] Results cached in Redis (second run is instant)
