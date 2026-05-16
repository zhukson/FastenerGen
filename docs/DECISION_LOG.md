# Decision Log

| Date | Decision | Rationale |
|---|---|---|
| 2026-04-18 | Python backend | Python is the fastest path for LLM orchestration, Pydantic schemas, ezdxf input parsing, and experiment scripts. |
| 2026-04-18 | No LangChain/LlamaIndex | Direct SDK calls and explicit prompts are easier to debug for this small, high-stakes domain. |
| 2026-05-01 | Use curated experience library instead of vector case RAG | With only 8 factory cases, embeddings add noise. Full-context few-shot is auditable and fits in context. |
| 2026-05-01 | Replace synthetic/pseudo reasoning with real worked cases | Factory 过模图 cases are more valuable than generated ISO examples. |
| 2026-05-09 | Move DXF rendering to `FastenerDrawingEngine` | Drawing fidelity is its own renderer/orchestration problem and should be developed/tested independently. |
| 2026-05-10 | FastenerGen owns upstream Gong reasoning/schema only | The repo is now focused on `PartFeatures -> ProcessForming`, knowledge, verification, and eval. |
| 2026-05-10 | Remove old 3D, die-design, renderer, synthetic, pseudo-reasoning, and vector-RAG code | These paths distracted from the core bottleneck and caused dependency/runtime churn. |
| 2026-05-11 | Remove frontend from FastenerGen | Until the renderer is mature, CLI experiments with durable reports are more useful than maintaining a placeholder UI. |
| 2026-05-11 | Add CLI experiment reports | Every test run should write `process_parameters.json`, reasoning, Gong review, and JSON/Markdown metrics. |
| 2026-05-11 | Add square T-cap holdout experiment | Tests upstream reasoning by excluding the matching case and using final product features as input. |
| 2026-05-11 | Make holdout exclusion apply to confidence signal | Prevent answer-key leakage in reports, not just in LLM prompt context. |
| 2026-05-12 | Add calibration pipeline with teacher-rationale checkpoints | The system needs repeatable 30+ case scoring and explicit failure diagnosis before prompt/rule tuning. |
| 2026-05-12 | Treat pseudo reasoning as auditable checkpoints, not hidden chain-of-thought | Store feature observations, required operations, precedence constraints, and common failure modes that can be validated against GT. |
| 2026-05-16 | Migrate next architecture toward search-based process planning | Direct LLM generation is useful as a baseline but does not scale reliably for operation order. The next path is manufacturing feature graph -> operation grammar search -> rule filtering -> deterministic scoring -> LLM top3 ranking. |
| 2026-05-16 | Treat family templates as priors, not fixed answers | NAGFORM-like scalability comes from primitives/features, operation rules, simplified analysis, and reusable priors. Hard-coding one exact process per family would overfit the 8 GT drawings. |

## Current Open Decisions

- Whether upstream should emit `geometry_25d` directly, or whether a separate
  product-feature extraction engine should enrich `PartFeatures` before Gong
  reasoning.
- Which Gong/textbook rules should become executable verifier checks.
- How to generate richer teacher rationale from Gong textbook cases while
  enforcing that required operations and precedence remain GT-grounded.
- How much of `ManufacturingFeatureGraph` should come from product-drawing
  extraction versus deterministic conversion from existing `PartFeatures`.
- When search-mode reports are strong enough to replace the direct
  `ProcessDesigner` baseline.
