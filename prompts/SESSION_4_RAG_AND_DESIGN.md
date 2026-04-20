# Session 4: RAG + Design Engine + Full Pipeline

Read @CLAUDE.md for project context. Sessions 1-3 must be complete.

## Goal

Wire everything together into the core product: upload a drawing → AI designs dies → output 2D drawings + 3D models. This session builds the RAG, the design reasoning engine, the output generation pipeline, and the frontend design experience.

## Task 1: Embedding Service

Create `backend/app/ai/embeddings.py`:

```python
class EmbeddingService:
    async def embed(self, text: str) -> List[float]:
        """Embed single text via Voyage-3-large. Cache by text hash in Redis."""
    
    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Batch embed with rate limiting."""
    
    async def generate_embedding_text(self, features: PartFeatures) -> str:
        """
        Use Claude Haiku 4.5 to generate a 2-3 sentence natural language
        description of the part optimized for semantic search.
        
        Example: "M6×33 flat head bolt with compound chamfer head (45°/60°)
        and flanged base (Φ16mm), 10B21 carbon boron steel, grade 8.8 with
        HRC 22-32 hardness, blue-white zinc plated. Three-station cold heading
        with post-process knurling and thread rolling."
        
        Cache aggressively — same features → same text.
        """
```

## Task 2: RAG Store

Create `backend/app/ai/rag.py`.

Custom Hybrid RAG. No frameworks. Direct SDK calls.

```python
class FastenerRAG:
    """
    ~100 lines of code. That's it.
    
    Retrieval strategy:
    1. Generate embedding text from query features
    2. Embed with Voyage
    3. Vector search top-20 in ChromaDB
    4. Metadata filter (material, size range, confidence)
    5. Rerank with Voyage rerank-2
    6. Diversity filter (no near-duplicates)
    7. Return top-3
    """
    
    async def add_case(self, case: RAGCase) -> None: ...
    async def add_batch(self, cases: List[RAGCase]) -> None: ...
    
    async def retrieve(
        self,
        query: PartFeatures,
        top_k: int = 3,
        min_confidence: str = "high"
    ) -> List[RetrievedCase]: ...
    
    async def retrieve_with_fallback(
        self, query: PartFeatures, top_k: int = 3
    ) -> Tuple[List[RetrievedCase], str]:
        """
        Graceful degradation:
        1. High-conf + strict filters → "exact_match"
        2. High-conf + relaxed filters → "relaxed"
        3. Medium-conf → "medium_confidence"
        4. Empty → "no_match"
        
        The quality tag is passed to the designer so it knows
        how much to trust the examples.
        """
    
    def get_stats(self) -> dict:
        """Return collection stats: total cases, confidence distribution, etc."""
```

## Task 3: Few-Shot Formatter

Create `backend/app/ai/fewshot.py`:

Convert RAG payloads to XML optimized for Claude:

```python
class FewShotFormatter:
    def format_cases(self, cases: List[RetrievedCase]) -> str:
        """
        Format cases for prompt insertion.
        Sort: least similar first → most similar last (exploit recency bias).
        Each case in XML with: part_description, process_plan, die_spec,
        reasoning (with confidence tag), key_parameters.
        """
    
    def _format_single(self, case: RetrievedCase, index: int) -> str:
        """
        <case index="1" similarity="0.87">
          <part_description>M6×33 flat head bolt, 10B21, 8.8 grade...</part_description>
          <process_plan>3-station cold heading: upsetting → pre-form → finish</process_plan>
          <die_spec>Die: SKD11 HRC60-62, Punch: SKH9...</die_spec>
          <reasoning confidence="high">[AI-inferred] 3 stations because...</reasoning>
          <key_parameters>upset_ratio=2.3, corner_R=0.3</key_parameters>
        </case>
        """
```

## Task 4: Design Engine

Create `backend/app/ai/designer.py`.

The core agentic workflow — single LLM, structured steps, not multi-agent.

```python
class DieDesigner:
    async def design(
        self,
        part: PartFeatures,
        similar_cases: List[RetrievedCase],
        retrieval_quality: str
    ) -> DesignResult:
        """
        Full design pipeline:
        1. Process planning (LLM)
        2. Die parameter calculation (LLM)
        3. 3D model generation (CADQuery)
        4. 2D drawing generation (ezdxf)
        5. Verification (rule-based)
        6. Retry if verification fails (max 2)
        7. Return DesignResult with all files
        """
```

### Process Planning Prompt (`prompts/process_planning.py`)

```python
PROCESS_PLANNING_PROMPT = """
<role>Senior cold-heading die designer, 30 years experience.</role>

<similar_cases>
{few_shot_cases_xml}
</similar_cases>

<new_part>
{part_features}
</new_part>

<retrieval_quality>{retrieval_quality}</retrieval_quality>

<instructions>
Design the forming process:
1. Determine station count and sequence
2. Calculate blank dimensions (diameter × length)
3. For each station: operation type, intermediate shape, deformation ratio
4. Post-forming processes (thread rolling, knurling, etc.)
5. Explain reasoning for each decision
6. Flag risks and areas needing human verification

If retrieval_quality is "no_match", rely on general cold-heading principles 
and be conservative. Flag confidence as medium or low.
</instructions>

<output_schema>{schema}</output_schema>
"""
```

### Die Design Prompt (`prompts/die_design.py`)

```python
DIE_DESIGN_PROMPT = """
<role>Senior die design engineer.</role>

<part>{part_features}</part>
<process_plan>{process_plan}</process_plan>
<similar_case_dies>{similar_die_specs}</similar_case_dies>

<task>
For each station, design:
1. Punch: geometry description, key dimensions, material, hardness, surface treatment
2. Die: cavity geometry, key dimensions, material, hardness, surface treatment
3. Expected tool life (shots)
4. Critical tolerances
5. Assembly notes

Apply standard compensations:
- Spring-back (material-dependent)
- Shrinkage (if heat treatment follows)
- Die wear allowance

Output JSON per station matching DieParameters schema.
</task>
"""
```

## Task 5: Verification Engine

Create `backend/app/ai/verification.py`:

```python
class DesignVerifier:
    def verify(self, part, plan, dies) -> VerificationResult:
        """
        Rule-based checks (no LLM calls):
        1. Dimensional consistency: sum of segment lengths ≈ total length
        2. Volume conservation: blank volume ≈ product volume (±5%)
        3. Upset ratios: each station < 3.5 (cold heading limit)
        4. Material compatibility: die HRC > workpiece HRC
        5. Completeness: every station has both punch and die
        6. Station sequence: dimensions progress logically
        7. Tolerance chain: final tolerances achievable
        """
```

## Task 6: Output Generation Pipeline

Create `backend/app/api/v1/designs.py`:

```python
@router.post("/api/v1/designs/generate")
async def generate_design(request: DesignRequest) -> DesignResult:
    """
    Complete pipeline endpoint.
    
    1. Load part features (from Session 2 extraction)
    2. Retrieve similar cases (RAG)
    3. Format few-shot examples
    4. Run DieDesigner.design()
       - Process planning (LLM)
       - Die parameter calc (LLM)
       - 3D generation (CADQuery) → STEP + STL
       - 2D drawing generation (ezdxf) → DXF
       - Verification
       - Retry if needed
    5. Store all output files in MinIO
    6. Return DesignResult with file URLs
    """

@router.get("/api/v1/designs/{id}")
async def get_design(id: str) -> DesignResult: ...

@router.get("/api/v1/designs/{id}/files/{file_type}")
async def download_file(id: str, file_type: str) -> FileResponse: ...

@router.post("/api/v1/designs/{id}/feedback")
async def submit_feedback(id: str, feedback: DesignFeedback) -> None:
    """Capture user feedback (accept/reject/modify) for future training."""
```

## Task 7: Frontend — Design Experience

### Design Detail Page (`/designs/[id]`)

**Layout**: Two-column. Left: 3D viewer (60% width). Right: info panels (40% width).

**Left panel — 3D Viewer**:
- Load STL files per station
- Station selector: tabs "Station 1 | Station 2 | Station 3 | Assembly"
- Each station shows: punch (steel gray) + die (dark gray) + workpiece (blue/copper)
- Orbit controls, zoom, reset view button
- Toggle: wireframe / solid / section view
- Screenshot button (download PNG)

**Right panel — Info Panels** (scrollable, collapsible sections):
1. **Process Plan**: Station flow diagram (horizontal cards with arrows)
2. **Extracted Features**: From the original product drawing
3. **Die Specifications**: Table per station (material, hardness, life, key dims)
4. **AI Reasoning**: Collapsible text with confidence badges
5. **Similar Cases Used**: Which historical cases were referenced (expandable)
6. **Downloads**: Buttons for each file (DXF drawings, STEP 3D, STL, parameters JSON)
7. **Feedback**: "Accept Design" / "Needs Changes" / "Reject" buttons with optional text input

### Upload Page Update
- After analysis, show "Generate Die Design" button
- When clicked: show progress (Step 1: Retrieving cases... Step 2: Planning process... etc.)
- On completion: redirect to design detail page

### Designs List Page (`/designs`)
- Table/card view of all generated designs
- Columns: part name, spec, date, station count, confidence, status (pending/accepted/rejected)
- Click → design detail page
- Filter by: confidence level, status, date range

## Task 8: Integration Test

Create `backend/tests/integration/test_full_pipeline.py`:

End-to-end test with synthetic data:
1. Generate 10 synthetic cases → populate RAG
2. Generate 1 new synthetic part (not in RAG)
3. Run full pipeline: features → RAG → design → verify → generate files
4. Assert: DesignResult is valid, all files exist, verification passes
5. Assert: DXF files are valid (ezdxf can re-read them)
6. Assert: STL/STEP files are valid (trimesh can load STL)
7. Assert: total latency < 120 seconds
8. Assert: total cost < $5

## Verification Checklist

- [ ] RAG retrieves relevant cases from 10+ synthetic cases
- [ ] Few-shot formatter produces clean XML
- [ ] Design engine generates complete DesignResult
- [ ] 3D models generated for each station (punch + die + workpiece)
- [ ] 2D DXF drawings generated with proper annotations
- [ ] Verification catches invalid designs (test with impossible input)
- [ ] All files downloadable via API
- [ ] Frontend 3D viewer shows die assemblies per station
- [ ] Frontend shows process flow, reasoning, downloads
- [ ] Feedback capture works
- [ ] Integration test passes end-to-end
- [ ] Total pipeline latency < 120 seconds
- [ ] Total pipeline cost < $5
