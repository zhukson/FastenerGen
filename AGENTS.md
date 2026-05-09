# FastenerGPT — AI-Powered 过模图 Generation for Cold-Heading Fasteners

> **Strategy pivot 2026-05-01**: scope narrowed to **single-output 过模图 generation** + **curated 经验库** (replaces vector RAG over synthetic cases). See Decision Log entries dated 2026-05-01 for rationale.

## What We Build (v2, current)

An AI system that takes a customer product drawing (2D PDF/DWG/image) and generates **one artifact**:

1. **过模图 (Process Forming Drawing)** — DXF, editable in AutoCAD/LibreCAD. Shows the multi-station progression of intermediate workpiece shapes with key dimensions, GB-style title block, layers, and dim styles.

That's it. Engineers receive the draft 过模图, refine in their CAD software, then proceed to per-station tooling design (manual today; future Phase 2 unlock).

**One-liner**: "Upload a screw drawing, get a process-forming drawing (过模图) in minutes instead of days."

## What We Do NOT Build (v2)

- **NOT** per-station punch / die drawings — deferred to Phase 2 (derived from 过模图)
- **NOT** 3D STEP/STL models or assembly previews — deferred to Phase 2
- **NOT** a separate production drawing — the 过模图 carries the process-compensated geometry
- **NOT** a quoting tool (quotes are a byproduct)
- **NOT** a simulation tool (Deform/QForm handle simulation in Phase 2+)
- **NOT** replacing engineers (we generate ~70% draft 过模图; engineers refine the rest)

## Competitive Landscape

| Tool                 | What It Does                                                                 | What It Does NOT Do                                                        |
| -------------------- | ---------------------------------------------------------------------------- | -------------------------------------------------------------------------- |
| **Deform**           | Simulates metal flow given existing die 3D models; predicts defects          | Does NOT generate die designs; needs dies as input                         |
| **QForm**            | Same as Deform; QForm Direct can auto-generate preform dies from finish dies | Does NOT go from product drawing to die design                             |
| **Cimatron CAD-AI**  | AI feature detection for mold CAD/CAM                                        | Focused on injection molds, not cold heading                               |
| **Fictiv DFM**       | Automated manufacturability feedback for injection molding                   | No die design generation                                                   |
| **Us (FastenerGPT)** | Product drawing → complete die design (drawings + 3D)                        | Does NOT do FEA simulation (integrates with Deform/QForm for verification) |

**Our position**: We are the "design generation" layer. Deform/QForm are the "verification" layer. We complement each other. In Phase 2+, we integrate Deform/QForm APIs as our physics verifier.

## Real-World Workflow We Automate

```
Customer sends product drawing (2D PDF/DWG)
  "I need this special screw, quote me and make it"

TODAY (manual, 3-7 days per project):
  1. Engineer reads product drawing
  2. Engineer plans forming process (# stations, intermediate shapes)
  3. Engineer drafts the 过模图 (process forming drawing)
  4. Engineer designs per-station punch + die drawings (downstream of 过模图)
  5. Engineer creates production drawing with process compensations
  6. Optional: Deform/QForm simulation to verify
  7. Cost estimation and quote

WITH FASTENERGPT v2 (target: < 2 min + engineer review):
  1. Upload product drawing (PDF/DWG/image)
  2. AI reads drawing (Codex Opus 4.7 vision) → PartFeatures
  3. AI loads ALL 经验库 cases as few-shot context (Tier 1 knowledge)
  4. AI designs the forming process (Codex Opus 4.7) → ProcessForming JSON
  5. ezdxf renders the 过模图 DXF deterministically from the JSON
  6. Rule-based verification; retry up to 2× on failure
  7. Engineer downloads DXF, refines, then proceeds with downstream tooling design

  Phase 2 unlocks (deferred): per-station punch/die drawings, 3D STEP/STL,
  textbook RAG (Tier 2), Deform/QForm integration.
```

## Target Market

- Cold-heading fastener factories producing custom/special-shape screws and bolts
- Starting point: Stanley Black & Decker supply chain (father's network as GM)
- Global fastener market: ~$100B; China: 30%+ of global production
- Typical customer: factory receiving 10-50 quote requests per day, each requiring engineering time

## Team

- **Founder (me)**: Google SDE, technical lead, AI/ML architecture
- **Co-founder**: SDE, infrastructure + frontend
- **Industry advisor / CEO candidate**: Father, former GM at Stanley Black & Decker
- **To hire post-funding**: 1-2 senior die engineers (for data quality + product validation)

## Current Stage & Constraints

- **Stage**: Early data. 13 real files in `fasternerGenData/` — 8 异形件过模图 DWGs + 4 standard-part PDFs (DIN912 M14/M20, DIN933 M18/M22) + 1 球头 DWG.
- **Data scarcity drives the architecture**: at N=8 worked cases, vector RAG is noise; we use a curated 经验库 with full-context few-shot instead.
- **Expected next data tranche**: more 异形件 DWGs from factory partners; possibly 1–2 cold-heading textbooks (would unlock Tier 2 textbook RAG).
- **No domain expert yet**: real worked examples (the 8 DWGs) replace synthetic pseudo-reasoning as the knowledge bootstrap.
- **Target**: 8–12 weeks to a credible 过模图 demo → Pre-seed funding → hire domain expert.
- **Key constraint**: H1B status (founder); company structure: Delaware C-Corp + China WFOE.

---

## Tech Stack

| Layer              | Choice                                         | Status (v2) | Why                                                            |
| ------------------ | ---------------------------------------------- | ----------- | -------------------------------------------------------------- |
| **Backend**        | Python 3.12+, FastAPI                          | Active      | ezdxf and AI/ML ecosystem are Python                           |
| **Frontend**       | TypeScript, Next.js 15, React 19               | Active      | Best frontend DX; DXF preview via Konva                        |
| **Drawing I/O**    | ezdxf                                          | Active (core) | Read DWG/DXF input; write 过模图 DXF output                    |
| **DXF preview**    | Konva (`DxfStage.tsx`) for web                 | Active      | 2D canvas preview of generated DXF                             |
| **LLM primary**    | Codex Opus 4.7 (reasoning + vision)           | Active      | Step 1 (drawing understanding) and Step 3 (process design)     |
| **LLM auxiliary**  | Codex Haiku 4.5                               | Available   | Fast classification / extraction helpers                       |
| **Database**       | PostgreSQL 16                                  | Active      | Metadata, audit trail                                          |
| **Object storage** | S3-compatible (MinIO local, GCS prod)          | Active      | DXF file storage                                               |
| **Task queue**     | Celery + Redis                                 | Active      | Async pipeline + LLM response cache                            |
| **Deployment**     | GCP Cloud Run (backend), Vercel (frontend)     | Planned     | Cost-effective, scalable                                       |
| **3D geometry**    | CADQuery / trimesh                             | **Dormant** | Phase 2 (per-station punch/die 3D). Code retained, not wired.  |
| **3D frontend**    | Three.js (@react-three/fiber)                  | **Dormant** | Phase 2 (3D viewer). Component retained, not surfaced.         |
| **STEP / STL export** | OCCT / trimesh                              | **Dormant** | Phase 2                                                        |
| **Vector DB**      | ChromaDB                                       | **Dormant (Tier 2 reserved)** | Repurposed for textbook RAG when books arrive. Not used for case retrieval (N=8 too small). |
| **Embeddings**     | Voyage-3-large                                 | **Dormant (Tier 2 reserved)** | Same — for textbook chunks                                     |
| **Reranking**      | Voyage rerank-2                                | **Dormant (Tier 2 reserved)** | Same                                                           |
| **Gemini 2.5 Pro** | Cross-validation of pseudo-reasoning           | **Deprecated** | v1 pseudo-reasoning replaced by real worked cases              |

### Explicitly NOT Using

| Rejected                   | Why                                                                                                                                                                                               |
| -------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **LangChain / LlamaIndex** | Over-abstraction for our use case. Our RAG is ~100 lines of direct SDK calls — simpler, faster, transparent, no lock-in. Industry consensus in 2025-2026 is against frameworks for production AI. |
| **Multi-agent (Phase 1)**  | Single LLM agentic workflow is faster, cheaper, more predictable. Multi-agent deferred to Phase 3+.                                                                                               |
| **Streamlit / Gradio**     | Not suitable for production frontend. Next.js gives real product UX.                                                                                                                              |

---

## Architecture Phases (v2)

| Phase | Time     | Architecture                                                            | Data                          | Goal              |
| ----- | -------- | ----------------------------------------------------------------------- | ----------------------------- | ----------------- |
| **1** | now      | 经验库 (full-context few-shot) + Opus 4.7 + ezdxf 过模图                | 8 cases + 4 standards         | Credible demo + Pre-seed |
| **2** | 6-15 mo  | + Tier 2 textbook RAG; per-station punch/die DXF; 3D STEP/STL revival   | 30-100 cases + 1-2 textbooks  | Alpha product     |
| **3** | 15-30 mo | Fine-tuned models + Deform/QForm integration                            | 1K-3K cases                   | Beta / commercial |
| **4** | 30-48 mo | Domain Foundation Model ("FastenerGPT")                                 | 30K+ cases                    | Scale             |
| **5** | 48+ mo   | End-to-end neural CAD generation                                        | 100K+ cases                   | Market leader     |

**Rule**: Phase 1 code must keep clean seams for Phase 2 (knowledge loader interface accepts both Tier 1 cases and Tier 2 chunks; pipeline orchestrator can plug additional output generators for punch/die downstream).

---

## Demo Roadmap (v2 — collapsed to 6 milestones)

Phase 1 demo target: **upload a fastener product drawing → output one 过模图 DXF in < 2 min**.

| # | Milestone                    | Key Deliverable                                                       |
| - | ---------------------------- | --------------------------------------------------------------------- |
| **M1** | DWG→DXF conversion       | Convert all 8 异形件 DWGs to DXF; render PNG previews                 |
| **M2** | 经验库 extraction         | 8 case JSONs + 4 standard JSONs in `backend/app/knowledge/`; rules.md |
| **M3** | Schema + loader refactor  | New `ProcessForming` / `CaseRecord` models; `knowledge/loader.py`     |
| **M4** | 过模图 generator          | `process_forming_generator.py` produces valid DXF from JSON           |
| **M5** | 4-step pipeline wired     | New orchestrator replaces `designer.py`; API returns single DXF       |
| **M6** | E2E demo                  | Held-out case test passes; frontend shows DXF preview + reasoning     |

### Demo Acceptance Gate (M6)

- Upload one of the 4 PDF standard parts (e.g., DIN912 M14) → output a 过模图 DXF in < 120s
- Upload a held-out 异形件 product drawing (one of the 8 DWGs, with its case removed from the 经验库) → output a 过模图 DXF that **visually resembles** the original (qualitative human review)
- DXF opens cleanly in LibreCAD with real DIMENSION entities, Chinese title block, GB layers
- `reasoning.md` cites which cases from the 经验库 the design drew from

---

## Core Pipeline (v2 — 4 steps, 1 output)

```
[Input: Customer product drawing — PDF / DWG / JPG]
       │
       ▼
[Step 1: Drawing Understanding]
  Tool: Codex Opus 4.7 Vision
  Output: PartFeatures JSON
    - Part type/category (e.g., 四方T帽, 铆接螺钉, hex bolt DIN933)
    - All dimensions with tolerances
    - Material, grade, hardness, surface treatment
    - Thread spec, special features
       │
       ▼
[Step 2: Knowledge Retrieval]
  Tier 1 (active): load ALL 经验库 cases + rules.md (deterministic, in-process)
    - 8 case JSONs + 4 standard part JSONs
    - Optional pre-filter by product_category to put closest matches first
  Tier 2 (deferred, when textbooks arrive): vector search top-k chunks via ChromaDB
       │
       ▼
[Step 3: Process Forming Design — THE HARDEST STEP]
  Tool: Codex Opus 4.7 with full few-shot context
  Input: PartFeatures + ALL Tier 1 cases (XML-formatted) + rules
  Process: LLM reasons about:
    - Number of forming stations
    - Blank dimensions (diameter, length)
    - Each station's workpiece geometry + key dimensions + operation
    - Deformation ratios and limits
    - Post-forming processes (thread rolling, etc.)
  Output: ProcessForming JSON (structured, schema-validated)
       │
       ▼
[Step 4: 过模图 DXF Generation]
  Tool: ezdxf (deterministic; LLM never emits coordinates)
  Process:
    - Layout N intermediate workpiece shapes left-to-right
    - Add key dimensions + leaders per station
    - Chinese title block, GB layers, ANSI31 hatch on sections
    - Fill metadata: 零件名, 材料, 工位数, 日期
  Output: process_forming.dxf
       │
       ▼
[Step 5: Verification]
  Tool: Rule-based engine
  Checks:
    - Dimensional consistency (chains sum correctly)
    - Physical plausibility (upset ratios within limits)
    - Volume conservation (blank ≈ Σ stations)
    - Reference cases were actually consulted (cited in reasoning)
  If fail → feed errors back to Step 3 → retry (max 2 attempts)
       │
       ▼
[Output Package]
  ├── process_forming.dxf          # THE deliverable
  ├── process_parameters.json      # The ProcessForming JSON (for traceability)
  └── design_reasoning.md          # Cited cases + LLM reasoning

  Phase 2 unlocks: per-station/punch_die.dxf, station_*/punch.step, die.step,
  workpiece_*.stl, assembly_preview.png
```

---

## Two-Tier Knowledge Architecture

| Tier | Source | Storage | Retrieval | Status |
|---|---|---|---|---|
| **Tier 1: 经验库** | 8 real DWG cases + 4 standard PDFs (worked examples) | `backend/app/knowledge/cases/*.json` (flat files) | Load **all** into prompt as few-shot every call | Active |
| **Tier 2: Textbook RAG** | Cold-heading textbooks (principles, formulas, limits) | ChromaDB vector store via `rag.py` + `embeddings.py` | Semantic top-k retrieval per query | Deferred (awaiting books) |

**Why this split is correct at our data scale:**
- Worked cases at N=8 → embeddings add noise; full context is feasible (~30K tokens for all 8 cases). Tells the LLM *"here's how it was actually done."*
- Textbook prose at N=1000s of chunks → embeddings shine; full context impossible. Tells the LLM *"here's the underlying theory."*

### Tier 1 layout

```
backend/app/knowledge/
├── cases/          # one JSON per real DWG (8 异形件 cases)
├── standards/      # one JSON per standard PDF (4: DIN912 M14/M20, DIN933 M18/M22)
├── rules/          # extracted heuristics (general.md, square_head.md, pin.md, ...)
├── patterns/       # reusable intermediate-shape primitives
└── loader.py       # load all into LLM context as few-shot XML
```

### Source of truth (raw drawings)

Raw files in object storage; never modified after ingestion.

```
s3://data/orders/{order_id}/
  ├── product_drawing.{dwg,dxf,pdf}    # input
  ├── process_forming.dxf               # generated 过模图
  ├── process_parameters.json
  └── design_reasoning.md
```

### Few-shot format (derived, never stored)

Generated at query time by `knowledge/loader.py`. Optimized for LLM reading.

---

## Knowledge Bootstrap Strategy (v2)

**Old (v1, deprecated):** generate hundreds of synthetic ISO cases + LLM-inferred pseudo-reasoning + Gemini cross-validation. Justified by data scarcity.

**New (v2):** real worked examples beat synthetic data. The 8 异形件过模图 DWGs in `fasternerGenData/` ARE the answer key. Extraction process:

1. DWG → DXF (ODA File Converter or Python lib)
2. DXF → PNG render (ezdxf + matplotlib)
3. Feed PNG + DXF entity dump to Codex Opus 4.7 with extraction prompt
4. LLM produces draft `case.json` (PartFeatures + station-by-station ProcessForming)
5. Human review & correct → save to `knowledge/cases/`

**Post-funding plan:** hire 1–2 retired die engineers to expand 经验库 from 8 → 50+ real cases and curate `rules/`. This stays small and high-quality, not large and noisy.

---

## File Structure

```
fastener-gpt/
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── core/                     # Config, logging, exceptions
│   │   ├── api/v1/                   # FastAPI routes
│   │   │   ├── health.py
│   │   │   ├── drawings.py           # Upload, parse, preview
│   │   │   ├── designs.py            # Design generation
│   │   │   └── eval.py               # Eval dashboard
│   │   ├── drawings/                 # 2D DXF read/write
│   │   │   ├── parser.py             # Read input drawings (ezdxf)
│   │   │   ├── generator.py          # [DORMANT v1 punch/die DXF; helpers reused]
│   │   │   ├── process_forming_generator.py  # [v2] generate 过模图 DXF
│   │   │   ├── templates/            # Drawing templates (frame, title block)
│   │   │   └── standards.py          # Layer defs, dim styles, GB standards
│   │   ├── geometry/                 # [DORMANT — Phase 2 (3D punch/die models)]
│   │   │   ├── punch_templates.py
│   │   │   ├── die_templates.py
│   │   │   ├── workpiece.py
│   │   │   ├── assembly.py
│   │   │   ├── exporter.py
│   │   │   └── projector.py
│   │   ├── knowledge/                # [v2] Tier 1 经验库
│   │   │   ├── cases/                #   8 case JSONs (extracted from DWGs)
│   │   │   ├── standards/            #   4 standard PDFs as JSON
│   │   │   ├── rules/                #   extracted heuristics .md files
│   │   │   ├── patterns/             #   reusable intermediate-shape primitives
│   │   │   └── loader.py             #   loads all + formats as few-shot XML
│   │   ├── ai/
│   │   │   ├── drawing_reader.py     # Multi-modal drawing understanding (Step 1)
│   │   │   ├── process_designer.py   # [v2] 4-step pipeline orchestrator
│   │   │   ├── verification.py       # Rule-based 过模图 verification (Step 5)
│   │   │   ├── quality.py            # Quality scoring
│   │   │   ├── fewshot.py            # XML formatting helpers
│   │   │   ├── designer.py           # [DEPRECATED v1] kept for reference
│   │   │   ├── rag.py                # [TIER 2 RESERVED] dormant; for textbook RAG
│   │   │   ├── embeddings.py         # [TIER 2 RESERVED] same
│   │   │   ├── reasoning.py          # [DEPRECATED v1] pseudo-reasoning bootstrap
│   │   │   └── prompts/
│   │   │       ├── drawing_understanding.py
│   │   │       ├── process_planning.py    # rewritten for full-context few-shot
│   │   │       ├── die_design.py          # [DEPRECATED v1]
│   │   │       └── pseudo_reasoning.py    # [DEPRECATED v1]
│   │   ├── data/
│   │   │   ├── schemas.py            # Pydantic models (+ ProcessForming, CaseRecord)
│   │   │   ├── ingestion.py          # Raw data → structured records
│   │   │   └── synthetic.py          # [DEPRECATED v1] ISO synthetic data
│   │   └── eval/                     # quality metrics for the 过模图 output
│   │       ├── golden_set.py
│   │       ├── datasets/golden/
│   │       ├── metrics.py
│   │       ├── judge.py
│   │       └── regression.py
│   ├── scripts/
│   │   ├── extract_case_from_dwg.py  # [v2] semi-auto case extractor
│   │   ├── ingest_factory_data.py
│   │   ├── inventory_data.py
│   │   ├── batch_pseudo_reasoning.py # [DEPRECATED v1]
│   │   └── generate_synthetic.py     # [DEPRECATED v1]
│   ├── tests/
│   │   ├── test_data/                # Sample drawings for testing
│   │   ├── drawings/
│   │   ├── geometry/
│   │   ├── ai/
│   │   └── integration/
│   ├── pyproject.toml
│   ├── Dockerfile
│   └── Dockerfile.dev
├── frontend/
│   ├── src/
│   │   ├── app/                      # Next.js App Router pages
│   │   │   ├── page.tsx              # Dashboard
│   │   │   ├── upload/page.tsx       # Drawing upload
│   │   │   ├── designs/
│   │   │   │   ├── page.tsx          # Design list
│   │   │   │   └── [id]/page.tsx     # Design detail + 3D viewer
│   │   │   └── eval/page.tsx         # Eval dashboard
│   │   ├── components/
│   │   │   ├── DrawingUploader.tsx    # Drag-drop upload
│   │   │   ├── DrawingPreview.tsx     # 2D drawing preview
│   │   │   ├── DxfStage.tsx          # [v2 PRIMARY] Konva-based 过模图 preview
│   │   │   ├── ThreeDViewer.tsx      # [DORMANT] 3D viewer — Phase 2
│   │   │   ├── ViewerStage.tsx       # [DORMANT] 3D Canvas wrapper — Phase 2
│   │   │   ├── StationViewer.tsx     # Per-station info panel
│   │   │   ├── ProcessFlowDiagram.tsx # Station flow visualization
│   │   │   ├── FeaturePanel.tsx      # Extracted features display
│   │   │   ├── ReasoningPanel.tsx    # AI reasoning + cited cases
│   │   │   ├── FileDownloadPanel.tsx # Download DXF + JSON + reasoning.md
│   │   │   └── FeedbackButtons.tsx   # Accept/Reject/Modify
│   │   ├── lib/
│   │   └── types/
│   ├── package.json
│   └── Dockerfile
├── templates/                        # DXF drawing templates
├── docs/
│   ├── ARCHITECTURE.md
│   ├── DEVELOPMENT.md
│   └── DECISION_LOG.md
├── eval/
│   └── baseline.json                # Checked-in eval baseline
├── docker-compose.yml
├── AGENTS.md                         # THIS FILE
└── README.md
```

---

## Coding Standards

- **Python**: Ruff (format + lint), strict mypy, Pydantic v2 for ALL data models
- **TypeScript**: Strict mode, Biome (format + lint), Zod for runtime validation
- **Testing**: pytest (Python, >80% coverage on core), Vitest (TS)
- **API**: OpenAPI spec as source of truth; TypeScript types auto-generated
- **Git**: Conventional commits, feature branches
- **Prompts**: Semantic versioning (v1.0.0). Store version with every generated output.
- **Logging**: structlog with structured JSON. Full LLM request/response tracing.
- **Cost tracking**: Every LLM call logs token count and estimated USD cost.

---

## Core Principles

1. **LLM decides, code generates geometry**: LLM outputs parameters and reasoning. CADQuery/ezdxf produce precise 3D models and 2D drawings. Never ask LLM to output coordinates, DXF entities, or STEP data.
2. **Every output is verified**: Geometric consistency, physical plausibility, completeness. Failures retry (max 2×), then flag for human review.
3. **Human-in-the-loop always**: Phase 1 = 100% engineer review. Never target 0%.
4. **Data flywheel from Day 1**: Every user action (upload, modify, accept, reject) is captured as training data. UI designed for implicit feedback collection.
5. **Confidence is mandatory**: Every inference carries high/medium/low. Low-confidence is prominently flagged in UI.
6. **Loosely coupled**: Each component (drawing reader, RAG, designer, geometry generator, drawing writer) has clean interfaces. Any can be swapped independently.
7. **No AI frameworks**: Direct SDK calls (anthropic, google-generativeai, voyageai, chromadb). Our own thin orchestration. Total RAG implementation: ~100-150 lines.
8. **Phase 1 code, Phase 2 ready**: Abstractions that allow swapping Codex for fine-tuned Llama, ChromaDB for Qdrant, rule-based verification for Deform API.

---

## Decision Log

| Date       | Decision                                          | Rationale                                                             |
| ---------- | ------------------------------------------------- | --------------------------------------------------------------------- |
| 2026-04-18 | Python backend + TypeScript frontend              | PythonOCC/ezdxf/CADQuery require Python; Three.js requires JS/TS      |
| 2026-04-18 | No LangChain/LlamaIndex ever                      | Over-abstraction, not for geometric data, lock-in, industry consensus |
| 2026-04-18 | Input = 2D drawings (PDF/DWG), not 3D STEP        | Real factory data is 2D; most factories work in 2D                    |
| 2026-04-18 | Output = 2D DWG + 3D STEP/STL                     | DWG for engineers to edit; 3D for visualization and Deform export     |
| 2026-04-18 | Deform/QForm = verification layer, not competitor | They need die 3D as input; we generate die designs                    |
| 2026-04-18 | Pseudo-reasoning via LLM, no expert yet           | Bootstrap with AI; hire expert after Pre-seed                         |
| 2026-04-18 | Phase 1 = Agentic Workflow, not Multi-Agent       | Simpler, faster, more predictable                                     |
| 2026-04-18 | Docker for local dev from Day 1                   | 3-person team needs consistent environments                           |
| 2026-04-18 | Parametric 3D templates (CADQuery)                | More reliable than free-form generation                               |
| 2026-04-18 | 3-layer data: Source / RAG / Few-shot             | Separate storage / retrieval / LLM presentation                       |
| 2026-04-19 | Revolution solid geometry (numpy+trimesh)         | CADQuery OCCT needs X11 in Docker; trimesh path as reliable fallback  |
| 2026-04-19 | ISO metric tables as synthetic seed data          | No public die design datasets; ISO dims + engineering rules → correct proportions |
| 2026-04-19 | Sonnet for die design, Opus for process planning  | Process planning needs hard reasoning; die params are schema-following with injected constraints |
| 2026-04-19 | Computed constraint injection before LLM call     | General rules like "2.5–4× bore" cause wrong proportions; part-specific pre-computed values force correct geometry |
| 2026-04-19 | pypdfium2 for PDF→JPEG, scale=1.5, quality=90     | Stay under Codex's 5MB base64 limit; scale=2.0 produced 6MB+ files  |
| 2026-05-01 | **Pivot output scope to single 过模图 (DXF only)**  | 8 real DWGs are 过模图 — that's our ground truth. Per-station punch/die + 3D were unfalsifiable; 1 artifact = credible demo + 14× smaller eval surface. Phase 2 adds the rest. |
| 2026-05-01 | **Replace case-RAG with curated 经验库 (full-context few-shot)** | N=8 worked cases too small for vector retrieval; embedding/reranking is noise. All 8 cases (~30K tokens) fit in context. Reintroduce vector RAG when N > 50 or for textbook content. |
| 2026-05-01 | **Repurpose ChromaDB / Voyage stack for Tier 2 textbook RAG** | The existing rag.py + embeddings.py infra is correct for textbooks (large prose, semantic queries). Kept dormant until cold-heading textbooks arrive — better fit than case retrieval. |
| 2026-05-01 | **Deprecate pseudo-reasoning + ISO synthetic seed**  | Real worked examples beat synthetic data with LLM-inferred reasoning. The 8 DWGs replace what 200 synthetic ISO cases were trying to bootstrap. |

---

## Open Items

### v2 implementation (active)
- [ ] DWG→DXF conversion pipeline for the 8 异形件 DWGs
- [ ] Extract 8 case JSONs from DWGs into `backend/app/knowledge/cases/`
- [ ] Extract 4 standard JSONs from PDFs into `backend/app/knowledge/standards/`
- [ ] Curate `backend/app/knowledge/rules/` from patterns across cases
- [ ] Refactor `schemas.py` with `ProcessForming` / `CaseRecord` / `WorkpieceGeometry`
- [ ] Build `backend/app/knowledge/loader.py` (full-context few-shot formatter)
- [ ] Build `backend/app/drawings/process_forming_generator.py` (DXF output)
- [ ] Wire 4-step pipeline in `backend/app/ai/process_designer.py`
- [ ] Update API + frontend to single-DXF flow
- [ ] E2E held-out case test (one DWG removed from 经验库 → regenerate)

### Business / data
- [ ] More 异形件 DWGs from factory partners (target N=30+ for next iteration)
- [ ] Cold-heading textbook PDFs → unlock Tier 2 RAG
- [ ] CEO decision (H1B constraint)
- [ ] Legal: Delaware C-Corp + China WFOE
- [ ] Data compliance: IP ownership of factory drawings
- [ ] Domain expert hiring plan post-funding
- [ ] Demo recording for investor deck
