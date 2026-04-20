# FastenerGPT — AI-Powered Die Design for Cold-Heading Fasteners

## What We Build

An AI system that takes customer product drawings (2D PDF/DWG) and generates:

1. **Production drawings** (2D DWG, editable in AutoCAD)
2. **Die drawings** for each forming station — punch + die (2D DWG, editable)
3. **3D models** of all dies and intermediate workpiece shapes (STEP + STL for preview)

Engineers receive draft drawings + 3D preview, review and refine in their CAD software, then proceed to manufacturing.

**One-liner**: "Upload a screw drawing, get production-ready die designs in 30 minutes instead of 7 days."

## What We Do NOT Build

- NOT a quoting tool (quotes are a byproduct; drawings are the core deliverable)
- NOT a simulation tool (Deform/QForm handle simulation; we handle design generation)
- NOT replacing engineers (we generate 70-80% drafts; engineers refine the remaining 20-30%)

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
  1. Engineer reads product drawing, understands requirements
  2. Engineer calculates stock/blank dimensions
  3. Engineer plans forming process (how many stations, deformation sequence)
  4. Engineer designs intermediate shapes for each station
  5. Engineer designs die drawings (punch + die per station)
  6. Engineer creates production drawing with process compensations
  7. Optional: Engineer runs Deform/QForm simulation to verify
  8. Engineer revises based on simulation → repeat steps 5-7
  9. Cost estimation and quote

WITH FASTENERGPT (target: 30 min + engineer review):
  1. Upload product drawing (PDF/DWG/image)
  2. AI understands drawing (multi-modal LLM vision)
  3. AI retrieves similar historical cases (Hybrid RAG)
  4. AI plans forming process (LLM reasoning with few-shot examples)
  5. AI generates die parameters + 3D geometry + 2D drawings
  6. AI runs basic verification checks
  7. Engineer reviews 3D preview, modifies 2D DWG as needed
  8. Optional: Export to Deform/QForm for full simulation
  9. Approve → manufacture
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

- **Stage**: Pre-data. Negotiating with factory owners for drawing data.
- **Expected data**: Several thousand product-to-die design pairs (2D DWG + PDF)
- **No domain expert yet**: Using LLM pseudo-reasoning with multi-verifier cross-validation
- **Target**: 8-12 weeks to demo → Pre-seed funding → hire domain expert
- **Key constraint**: H1B status (founder); company structure: Delaware C-Corp + China WFOE

---

## Tech Stack

| Layer              | Choice                                         | Why                                                            |
| ------------------ | ---------------------------------------------- | -------------------------------------------------------------- |
| **Backend**        | Python 3.12+, FastAPI                          | PythonOCC/ezdxf/CADQuery all Python; AI/ML ecosystem is Python |
| **Frontend**       | TypeScript, Next.js 15, React 19               | Three.js for 3D; best frontend DX                              |
| **Drawing I/O**    | ezdxf                                          | Read existing DWG/DXF; write output DWG/DXF drawings           |
| **3D geometry**    | CADQuery (primary), PythonOCC-core (fallback)  | Parametric 3D generation from parameters                       |
| **3D export**      | STEP (for CAD), STL (for web preview)          | Standard formats                                               |
| **3D frontend**    | Three.js (@react-three/fiber) + occt-import-js | Browser-based 3D viewer                                        |
| **LLM primary**    | Claude Opus 4.7 (reasoning + vision)           | Best reasoning; can directly read engineering drawings         |
| **LLM auxiliary**  | Claude Haiku 4.5                               | Fast tasks: embedding text generation, classification          |
| **LLM cross-val**  | Gemini 2.5 Pro                                 | Independent verification of pseudo-reasoning                   |
| **Embeddings**     | Voyage-3-large                                 | Best for technical/engineering content                         |
| **Reranking**      | Voyage rerank-2                                | Paired with Voyage embeddings                                  |
| **Vector DB**      | ChromaDB (Phase 1) → Qdrant (Phase 2+)         | Zero-config now, production-grade later                        |
| **Database**       | PostgreSQL 16                                  | Metadata, structured data, audit trail                         |
| **Object storage** | S3-compatible (MinIO local, GCS prod)          | CAD file storage                                               |
| **Task queue**     | Celery + Redis                                 | Async processing for large files                               |
| **Deployment**     | GCP Cloud Run (backend), Vercel (frontend)     | Cost-effective, scalable                                       |

### Explicitly NOT Using

| Rejected                   | Why                                                                                                                                                                                               |
| -------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **LangChain / LlamaIndex** | Over-abstraction for our use case. Our RAG is ~100 lines of direct SDK calls — simpler, faster, transparent, no lock-in. Industry consensus in 2025-2026 is against frameworks for production AI. |
| **Multi-agent (Phase 1)**  | Single LLM agentic workflow is faster, cheaper, more predictable. Multi-agent deferred to Phase 3+.                                                                                               |
| **Streamlit / Gradio**     | Not suitable for production frontend. Next.js gives real product UX.                                                                                                                              |

---

## Architecture Phases

| Phase | Time     | Architecture                                   | Data                    | Goal              |
| ----- | -------- | ---------------------------------------------- | ----------------------- | ----------------- |
| **1** | 0-6 mo   | RAG + Pseudo-reasoning + Parametric generation | 200-500 annotated pairs | Demo + Pre-seed   |
| **2** | 6-15 mo  | + Fine-tuned models + Deform/QForm integration | 1K-3K pairs             | Alpha product     |
| **3** | 15-30 mo | Hybrid specialized models per sub-task         | 5K-15K pairs            | Beta / commercial |
| **4** | 30-48 mo | Domain Foundation Model ("FastenerGPT")        | 30K-100K pairs          | Scale             |
| **5** | 48+ mo   | End-to-end neural CAD generation               | 100K+ pairs             | Market leader     |

**Rule**: Phase 1 code must support Phase 2 evolution. Components are loosely coupled and independently swappable.

---

## Demo Roadmap (Sessions 1–11)

Phase 1 demo target: upload M6 bolt drawing → complete die design package in < 2 min.

| Session | Focus                        | Key Deliverable                                              | File                                        |
| ------- | ---------------------------- | ------------------------------------------------------------ | ------------------------------------------- |
| **1**   | Project init                 | Skeleton: FastAPI + Next.js + Docker + ChromaDB              | *(done)*                                    |
| **2**   | Core pipeline                | Drawing upload → LLM parse → process plan → die params       | *(done)*                                    |
| **3**   | Pseudo-reasoning             | RAG seeding pipeline, self-consistency, cross-validation     | `prompts/SESSION_3_PSEUDO_REASONING.md`     |
| **4**   | RAG + eval                   | ChromaDB hybrid search, eval harness, golden test set        | `prompts/SESSION_4_RAG_AND_DESIGN.md`       |
| **5**   | RAG seed + Docker fix        | 200+ ISO cases in ChromaDB, CADQuery working in Docker       | `prompts/SESSION_5_RAG_SEED_AND_DOCKER.md`  |
| **6**   | DXF rewrite                  | Real DIMENSION entities, ANSI31 hatch, tolerances            | `prompts/SESSION_6_DXF_REWRITE.md`          |
| **7**   | Workpiece + assembly 3D      | Intermediate workpiece shapes + assembly STL per station     | `prompts/SESSION_7_WORKPIECE_AND_ASSEMBLY_3D.md` |
| **8**   | Frontend assembly viewer     | Three.js multi-mesh viewer, Process Story strip              | `prompts/SESSION_8_FRONTEND_ASSEMBLY_VIEWER.md`  |
| **9**   | Prompt + parameter quality   | Chain-of-thought arithmetic, computed constraints, ≥80% pass | `prompts/SESSION_9_PROMPT_AND_PARAMETER_QUALITY.md` |
| **10**  | Frontend polish              | Case cards, SVG flow diagram, DXF preview, grouped downloads | `prompts/SESSION_10_FRONTEND_POLISH.md`     |
| **11**  | E2E test + demo              | Full integration tests, demo script, CI pipeline             | `prompts/SESSION_11_E2E_TEST_AND_DEMO.md`   |

### Demo Acceptance Gate (Session 11)

- Upload M6×33 flat head bolt drawing → complete package in < 120s
- 3D viewer shows punch (blue) + die (grey transparent) + workpiece (orange) per station
- Process Story strip shows all intermediate shapes
- ≥ 16/20 M6 designs pass verification on first attempt
- DXF files open in LibreCAD with real dimension entities
- Total output files ≥ 14 for a 3-station design

---

## Core Pipeline (Phase 1 Detail)

```
[Input: Customer product drawing — PDF / DWG / JPG]
       │
       ▼
[Step 1: Drawing Understanding]
  Tool: Claude Opus 4.7 Vision API
  Input: Drawing image(s) — base64 encoded
  Process: Multi-modal LLM reads the drawing visually
  Output: PartFeatures JSON
    - Part type, spec (e.g., M6×33 flat head bolt)
    - All dimensions with tolerances
    - Material, grade, hardness requirements
    - Surface treatment
    - Thread specification
    - Special features
    - Manufacturing process notes (if annotated on drawing)
       │
       ▼
[Step 2: RAG Retrieval]
  Tool: Custom Hybrid RAG (vector + metadata + rerank)
  Input: PartFeatures from Step 1
  Process:
    1. Generate embedding text from features (Claude Haiku)
    2. Embed with Voyage-3-large
    3. Vector search top-20 in ChromaDB
    4. Metadata filter (material category, size range, confidence≥high)
    5. Rerank with Voyage rerank-2
    6. Diversity check (no near-duplicates)
  Output: Top-3 similar historical cases with:
    - Product features
    - Process plan (stations, parameters)
    - Die parameters (punch + die per station)
    - Pseudo-reasoning
       │
       ▼
[Step 3: Process Planning — THE HARDEST STEP]
  Tool: Claude Opus 4.7 with few-shot prompt
  Input: New part features + 3 similar cases (XML-formatted)
  Process: LLM reasons about:
    - Number of forming stations
    - Stock/blank dimensions (diameter, length)
    - Each station's operation and intermediate shape
    - Deformation ratios and limits
    - Post-forming processes (thread rolling, knurling)
  Output: ProcessPlan JSON (structured, schema-validated)
       │
       ▼
[Step 4: Die Parameter Calculation]
  Tool: Claude Opus 4.7 + engineering rules
  Input: PartFeatures + ProcessPlan + similar case die specs
  Process: For each station, determine:
    - Punch geometry (profile, dimensions, tolerances)
    - Die cavity geometry (profile, compensations)
    - Material selection (die steel grade, hardness)
    - Surface treatment (TiN, TiCN, etc.)
    - Expected tool life
  Output: List[DieParameters] JSON (one per station)
       │
       ▼
[Step 5a: 3D Model Generation]
  Tool: CADQuery / PythonOCC
  Input: DieParameters per station
  Process:
    - Select parametric template per die type
    - Build 3D solid from parameters
    - Generate assembly (punch + die + workpiece positioned)
  Output per station:
    - punch.step, punch.stl
    - die.step, die.stl
    - workpiece_intermediate.step, workpiece_intermediate.stl
  Also: assembly preview renders (PNG)
       │
       ▼
[Step 5b: 2D Drawing Generation]
  Tool: ezdxf
  Input: DieParameters + 3D geometry (for view projection)
  Process:
    - Select drawing template (frame, title block, layers)
    - Generate standard views (front, side, section)
    - Add dimension annotations with tolerances
    - Add material, hardness, surface treatment notes
    - Fill title block
  Output per station:
    - punch_drawing.dxf
    - die_drawing.dxf
  Also:
    - production_drawing.dxf (product with process compensations)
    - process_breakdown.dxf (intermediate shapes visualization)
       │
       ▼
[Step 6: Verification]
  Tool: Rule-based engine (Phase 1); Deform/QForm API (Phase 2+)
  Checks:
    - Dimensional consistency (dimensions sum correctly)
    - Physical plausibility (upset ratios within limits)
    - Material compatibility (die harder than workpiece)
    - Volume conservation (blank volume ≈ product volume)
    - Completeness (all stations have punch + die)
    - 3D interference check (punch fits in die with clearance)
  If fail → feed errors to Step 3 → retry (max 2 attempts)
       │
       ▼
[Output Package]
  ├── production_drawing.dxf
  ├── process_breakdown.dxf
  ├── station_1/
  │   ├── punch.dxf        # 2D editable drawing
  │   ├── die.dxf           # 2D editable drawing
  │   ├── punch.step        # 3D model (for CAD / Deform import)
  │   ├── die.step           # 3D model
  │   ├── punch.stl         # 3D preview (for web viewer)
  │   └── die.stl
  ├── station_2/ ...
  ├── station_N/ ...
  ├── assembly_preview.png
  ├── process_parameters.json
  └── design_reasoning.md   # AI's explanation
```

---

## Data Architecture (3 Layers)

### Layer 1 — Source of Truth

Raw files in object storage. Never modified after ingestion.

```
s3://data/orders/{order_id}/
  ├── product_drawing.dwg
  ├── production_drawing.dwg
  ├── die_drawings/*.dwg
  ├── process_card.pdf (if available)
  └── metadata.json
```

### Layer 2 — RAG Store

ChromaDB records, each with:

1. **Vector**: Voyage embedding of `embedding_text`
2. **Metadata**: Flat dict for filtering (material, size, head_type, station_count, confidence)
3. **Payload**: Full case JSON (product features, process plan, die parameters, pseudo-reasoning)

### Layer 3 — Few-shot Format

Dynamically generated XML from Layer 2 payload via `payload_to_fewshot()`. Optimized for LLM reading. Never stored — always derived at query time.

---

## Pseudo-Reasoning Strategy

No domain expert available yet. We bootstrap knowledge using LLM analysis:

1. For each product-die data pair, Claude Opus 4.7 analyzes the geometric relationship and infers likely engineering reasoning (run 3× for self-consistency)
2. Gemini 2.5 Pro independently cross-validates
3. Rule-based verifier checks physical plausibility and no hallucinated numbers
4. Geometric verifier confirms reasoning references actual features in the data
5. Results aggregated → confidence score (high / medium / low)
6. Only high-confidence cases enter RAG store

**Post-funding plan**: Hire 1-2 retired die engineers to review and correct pseudo-reasoning. This upgrades data quality from ~75% to ~90%+ accuracy.

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
│   │   ├── drawings/                 # 2D DWG/DXF read/write
│   │   │   ├── parser.py             # Read existing drawings (ezdxf)
│   │   │   ├── generator.py          # Generate new 2D drawings (ezdxf)
│   │   │   ├── templates/            # Drawing templates (frame, title block)
│   │   │   └── standards.py          # Layer defs, dim styles, GB standards
│   │   ├── geometry/                 # 3D model generation
│   │   │   ├── punch_templates.py    # Parametric 3D punch models (CADQuery)
│   │   │   ├── die_templates.py      # Parametric 3D die models (CADQuery)
│   │   │   ├── workpiece.py          # Intermediate workpiece shapes
│   │   │   ├── assembly.py           # Assembly positioning
│   │   │   ├── exporter.py           # STEP/STL/PNG export
│   │   │   └── projector.py          # 3D → 2D view projection
│   │   ├── ai/
│   │   │   ├── drawing_reader.py     # Multi-modal drawing understanding
│   │   │   ├── rag.py                # Hybrid RAG (custom, no frameworks)
│   │   │   ├── embeddings.py         # Voyage embedding service
│   │   │   ├── fewshot.py            # Payload → few-shot XML formatter
│   │   │   ├── designer.py           # Core design engine (agentic workflow)
│   │   │   ├── reasoning.py          # Pseudo-reasoning pipeline
│   │   │   ├── quality.py            # Quality scoring + verification
│   │   │   ├── verification.py       # Rule-based design verification
│   │   │   └── prompts/              # All prompts (versioned)
│   │   │       ├── drawing_understanding.py
│   │   │       ├── process_planning.py
│   │   │       ├── die_design.py
│   │   │       └── pseudo_reasoning.py
│   │   ├── data/
│   │   │   ├── schemas.py            # All Pydantic models
│   │   │   ├── ingestion.py          # Raw data → structured records
│   │   │   └── synthetic.py          # Synthetic data generation
│   │   └── eval/
│   │       ├── golden_set.py         # Golden test cases
│   │       ├── datasets/golden/      # Test case JSON files
│   │       ├── metrics.py            # Automated quality metrics
│   │       ├── judge.py              # LLM-as-Judge evaluator
│   │       └── regression.py         # Regression testing
│   ├── scripts/
│   │   ├── batch_pseudo_reasoning.py
│   │   ├── ingest_factory_data.py
│   │   ├── inventory_data.py
│   │   ├── select_priority_data.py
│   │   └── generate_synthetic.py
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
│   │   │   ├── ThreeDViewer.tsx      # 3D model viewer (Three.js)
│   │   │   ├── StationViewer.tsx     # Per-station 3D view
│   │   │   ├── ProcessFlowDiagram.tsx # Station flow visualization
│   │   │   ├── FeaturePanel.tsx      # Extracted features display
│   │   │   ├── ReasoningPanel.tsx    # AI reasoning display
│   │   │   ├── FileDownloadPanel.tsx # Download DWG/STEP/STL
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
├── CLAUDE.md                         # THIS FILE
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
8. **Phase 1 code, Phase 2 ready**: Abstractions that allow swapping Claude for fine-tuned Llama, ChromaDB for Qdrant, rule-based verification for Deform API.

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
| 2026-04-19 | pypdfium2 for PDF→JPEG, scale=1.5, quality=90     | Stay under Claude's 5MB base64 limit; scale=2.0 produced 6MB+ files  |

---

## Open Items

- [ ] Data arrival timeline from factory partners
- [ ] Data format confirmation (all DWG? DWG+PDF mix? any 3D?)
- [ ] CEO decision (H1B constraint)
- [ ] Legal: Delaware C-Corp + China WFOE — need lawyer
- [ ] Data compliance: IP ownership of factory drawings
- [ ] Domain expert hiring plan post-funding
- [ ] Sessions 5–11 implementation (see `prompts/` folder for detailed specs)
- [ ] ChromaDB seed with 250 ISO-derived cases (Session 5)
- [ ] DXF rewrite with real DIMENSION entities (Session 6)
- [ ] Demo recording for investor deck
