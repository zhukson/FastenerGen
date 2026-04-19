# Architecture

## System Overview

```
┌─────────────────────────────────────────────────────────┐
│                    Engineer Browser                      │
│                    Next.js 15 + Three.js                 │
└──────────────────────┬──────────────────────────────────┘
                       │ HTTP (REST)
┌──────────────────────▼──────────────────────────────────┐
│              FastAPI Backend (Python 3.12)               │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌────────┐  │
│  │ Drawing  │  │   RAG    │  │ Designer │  │  Eval  │  │
│  │ Reader   │  │ Retrieval│  │ Engine   │  │        │  │
│  └──────────┘  └──────────┘  └──────────┘  └────────┘  │
│  ┌──────────────────────────────────────────────────┐   │
│  │             Verification Engine                   │   │
│  └──────────────────────────────────────────────────┘   │
│  ┌─────────────┐        ┌─────────────────────────┐     │
│  │  CADQuery   │        │        ezdxf             │     │
│  │  3D models  │        │     2D drawings          │     │
│  └─────────────┘        └─────────────────────────┘     │
└──────────────────────────────────────────────────────────┘
       │           │           │           │
   PostgreSQL   ChromaDB     Redis       MinIO
   (metadata)  (vectors)   (queue)    (CAD files)
```

## Pipeline Data Flow

```
Input: Customer drawing (PDF/DWG/JPG)

Step 1 — Drawing Understanding
  Claude Opus 4.7 Vision → PartFeatures (JSON)

Step 2 — RAG Retrieval
  PartFeatures → embedding text (Claude Haiku)
  → Voyage-3-large embedding
  → ChromaDB vector search (top-20)
  → metadata filter + Voyage rerank-2
  → top-3 RetrievedCase

Step 3 — Process Planning
  PartFeatures + few-shot XML → Claude Opus 4.7
  → ProcessPlan (JSON, schema-validated)

Step 4 — Die Parameter Calculation
  PartFeatures + ProcessPlan + few-shot → Claude Opus 4.7
  → List[DieParameters] (JSON, schema-validated)

Step 5a — 3D Model Generation
  DieParameters → CADQuery parametric templates
  → punch.step, die.step, workpiece.step (per station)
  → punch.stl, die.stl (for web viewer)

Step 5b — 2D Drawing Generation
  DieParameters → ezdxf templates
  → punch_drawing.dxf, die_drawing.dxf (per station)
  → production_drawing.dxf, process_breakdown.dxf

Step 6 — Verification
  Rule-based engine checks:
  - Dimensional consistency
  - Upset ratios ≤ 2.3
  - Volume conservation ± 3%
  - Material compatibility (die HRC > workpiece)
  - Completeness + interference
  → On failure: retry Steps 3-5 (max 2×)
```

## Data Architecture (3 Layers)

| Layer | Storage | Purpose |
|-------|---------|---------|
| Source of Truth | MinIO (S3) | Raw DWG/PDF files, never modified |
| RAG Store | ChromaDB | Vector + metadata + full case JSON |
| Few-shot Format | In-memory | XML derived from RAG at query time |

## Key Design Decisions

- **LLM decides parameters, code generates geometry** — Claude outputs JSON, CADQuery builds 3D
- **No LangChain/LlamaIndex** — direct Anthropic SDK calls, ~100 lines of RAG
- **Phase 1 = single agentic workflow** — not multi-agent; simpler and more predictable
- **Every output verified** — physical + geometric rules; human review always required
- **Confidence is mandatory** — every inference has high/medium/low; low is prominently flagged
