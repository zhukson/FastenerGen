# Session 11: E2E Test + Demo Readiness

Read @CLAUDE.md for full project context. Sessions 5–10 must be complete.

## Goal

The system is demo-ready. A 10-minute live demo can be run without surprises. All critical paths have automated tests that catch regressions. The demo script is written and rehearsed.

After this session: upload any M6 bolt drawing → get production-quality output in < 2 minutes, with 3D viewer showing full forming sequence, downloadable DXF/STL files, and AI reasoning visible.

---

## Task 1: E2E Integration Test Suite

### File: `backend/tests/integration/test_e2e_pipeline.py`

Full pipeline tests using real LLM calls (requires `ANTHROPIC_API_KEY` in env). Mark with `@pytest.mark.integration` so they can be skipped in CI:

```python
pytestmark = pytest.mark.integration

@pytest.mark.asyncio
async def test_m6_flat_head_bolt_full_pipeline():
    """Golden path: M6×33 flat head bolt → complete design package."""
    designer = DesignEngine()
    part = PartFeatures(
        part_type="bolt",
        thread=ThreadSpec(nominal_diameter=6.0, pitch=1.0, standard="ISO"),
        shank=ShankSpec(diameter=5.82, length=27.0),
        head=HeadSpec(type="flat", diameter=11.5, height=3.0),
        overall_length=33.0,
        material_grade="10B21",
        surface_treatment="zinc_phosphate",
    )

    result = await designer.design(part)

    # Basic completeness
    assert result.process_plan is not None
    assert len(result.process_plan.stations) >= 2
    assert result.process_plan.blank_diameter >= 5.82

    # Die parameters produced
    assert len(result.die_parameters) == len(result.process_plan.stations)

    # Verification passed
    assert result.verification_result.passed, \
        f"Verification failed: {[c.message for c in result.verification_result.checks if not c.passed]}"

    # Output files generated
    file_types = {f.file_type for f in result.output_files}
    assert "punch_stl" in file_types
    assert "die_stl" in file_types
    assert "punch_drawing" in file_types

    # Volume conservation
    plan = result.process_plan
    import math
    v_blank = math.pi / 4 * plan.blank_diameter**2 * plan.blank_length
    v_part = _calc_part_volume(part)
    assert v_blank >= v_part * 0.97, f"Volume conservation violated: blank {v_blank:.0f} < part {v_part:.0f}"

    # Upset ratio in reasoning
    assert any(
        str(round(part.head.diameter / plan.blank_diameter, 2)) in r
        for r in [result.reasoning_summary]
    ), "Upset ratio not mentioned in reasoning"
```

### Additional test cases:

```python
@pytest.mark.asyncio
async def test_m8_hex_bolt_3_stations():
    """M8 hex bolt — should generate 3 stations."""
    ...
    assert len(result.process_plan.stations) == 3

@pytest.mark.asyncio
async def test_m10_socket_cap_4_stations():
    """M10 socket cap — complex geometry, 4 stations."""
    ...
    assert len(result.process_plan.stations) >= 3

@pytest.mark.asyncio
async def test_retry_recovery():
    """Inject a bad die parameter, verify retry produces correct output."""
    ...
    assert result.verification_result.attempt <= 2

@pytest.mark.asyncio
async def test_concurrent_designs():
    """5 concurrent M6 designs complete under 90 seconds."""
    import asyncio, time
    start = time.time()
    results = await asyncio.gather(*[designer.design(m6_part) for _ in range(5)])
    elapsed = time.time() - start
    assert elapsed < 90
    assert all(r.verification_result.passed for r in results)
```

---

## Task 2: Drawing Upload E2E Test

### File: `backend/tests/integration/test_upload_pipeline.py`

Test the full drawing upload → parse → design flow via the HTTP API:

```python
@pytest.mark.asyncio
async def test_upload_and_parse_pdf():
    """Upload a real M6 bolt PDF, expect PartFeatures JSON back."""
    async with httpx.AsyncClient(base_url="http://localhost:8080") as client:
        with open("tests/test_data/m6_flat_head_bolt.jpg", "rb") as f:
            resp = await client.post(
                "/api/v1/drawings/upload",
                files={"file": ("drawing.jpg", f, "image/jpeg")},
                timeout=60,
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["features"]["thread"]["nominal_diameter"] == pytest.approx(6.0, abs=0.5)
        assert data["features"]["overall_length"] > 20

@pytest.mark.asyncio
async def test_generate_design_from_features():
    """POST features → poll → complete design."""
    async with httpx.AsyncClient(base_url="http://localhost:8080") as client:
        resp = await client.post(
            "/api/v1/designs/generate",
            json={"features": M6_FLAT_HEAD_FEATURES},
            timeout=120,
        )
        assert resp.status_code == 200
        design = resp.json()
        assert design["status"] == "complete"
        assert len(design["output_files"]) >= 8
```

Add `tests/test_data/m6_flat_head_bolt.jpg` — a simple hand-drawn or synthetic bolt drawing for testing (create with PIL if needed).

---

## Task 3: Frontend Playwright Tests

### File: `frontend/tests/e2e/demo_flow.spec.ts`

```typescript
import { test, expect } from "@playwright/test";

test("upload page loads", async ({ page }) => {
  await page.goto("/upload");
  await expect(page.getByText("Upload Drawing")).toBeVisible();
  await expect(page.getByText("Drag and drop")).toBeVisible();
});

test("design detail page renders 3D viewer", async ({ page }) => {
  // Use a pre-generated design ID from fixtures
  await page.goto(`/designs/${FIXTURE_DESIGN_ID}`);
  await expect(page.locator("canvas")).toBeVisible();
  await expect(page.getByText("Station 1")).toBeVisible();
});

test("station tabs switch correctly", async ({ page }) => {
  await page.goto(`/designs/${FIXTURE_DESIGN_ID}`);
  await page.getByText("Station 2").click();
  await expect(page.getByText("Heading")).toBeVisible();
});

test("download button triggers file download", async ({ page }) => {
  await page.goto(`/designs/${FIXTURE_DESIGN_ID}`);
  const downloadPromise = page.waitForEvent("download");
  await page.getByText("punch.dxf").click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toContain(".dxf");
});
```

Add `playwright.config.ts` with `baseURL: "http://localhost:3000"`, `testDir: "./tests/e2e"`.

---

## Task 4: Performance Benchmarks

### File: `backend/tests/test_performance.py`

```python
@pytest.mark.benchmark
def test_3d_geometry_generation_speed(benchmark):
    """STL generation for 4-station M6 bolt under 10 seconds."""
    from app.geometry.numpy_templates import build_punch_mesh, build_die_mesh

    def generate_all():
        for _ in range(4):
            build_punch_mesh(sample_punch_params)
            build_die_mesh(sample_die_params)

    result = benchmark(generate_all)
    assert benchmark.stats.mean < 2.5  # < 2.5s per station

@pytest.mark.benchmark
def test_rag_retrieval_speed(benchmark):
    """RAG retrieval under 2 seconds end-to-end."""
    rag = RAGRetriever()
    result = benchmark(lambda: asyncio.run(rag.retrieve(sample_features, top_k=3)))
    assert benchmark.stats.mean < 2.0
```

---

## Task 5: Demo Script + Seed Drawing

### File: `docs/DEMO_SCRIPT.md`

Write a 10-minute demo script:

```markdown
# FastenerGPT Demo Script (10 min)

## Setup (before demo)
- [ ] Docker compose up, all services healthy
- [ ] ChromaDB seeded (250 cases)
- [ ] Frontend running at localhost:3000
- [ ] Test design pre-generated (warm cache)
- [ ] Screen: 1920×1080, browser at 100% zoom

## Flow (10 min)

### 1. Problem statement (1 min)
"A factory receives a customer drawing like this [show PDF].
Today it takes 3-7 days for an engineer to design the dies.
We do it in 30 minutes."

### 2. Upload drawing (2 min)
- Open localhost:3000/upload
- Drag in the M6 flat head bolt drawing
- Show parsing result: "Look — it reads M6×33, flat head, 10B21 steel"
- Click "Generate Die Design"

### 3. While generating: explain the AI (1 min)
"It's retrieving similar historical cases from our database,
then reasoning about how many forming stations are needed..."

### 4. Review results (4 min)
- Show ProcessFlowDiagram: "3 stations — upset, head, extrusion"
- Click Station 1 in 3D viewer: "Punch above, die below, workpiece orange"
- Click Process Story thumbnails: "Watch the metal being progressively formed"
- Show ReasoningPanel: "Upset ratio 1.98 — within single-station limit"
- Show retrieved cases: "Found a similar M6×30 bolt — very high confidence"

### 5. Download outputs (1 min)
- Click punch.dxf → opens in LibreCAD (pre-open)
- Show dimension entities: "Real engineering drawing, not just lines"
- Click punch.stl: "Ready for Deform/QForm simulation"

### 6. Close (1 min)
"Engineer reviews, makes 20% adjustments, approves.
30 minutes instead of 7 days."
```

### Demo fixture drawing

Create `backend/tests/test_data/m6_flat_head_33_bolt.jpg`:
- Use PIL to generate a simple 2D engineering drawing of an M6×33 flat head bolt
- Dimensions labeled: M6×1.0, Ø5.82 shank, Ø11.5 head, 3.0 head height, 33 total
- White drawing on dark background (mimics real CAD output)

```python
# backend/scripts/create_demo_drawing.py
from PIL import Image, ImageDraw, ImageFont
import math

def draw_m6_bolt(path="tests/test_data/m6_flat_head_33_bolt.jpg"):
    img = Image.new("RGB", (800, 600), color=(20, 20, 20))
    draw = ImageDraw.Draw(img)

    # Draw bolt profile (simplified, centered)
    cx, cy = 400, 300
    scale = 8  # 1mm = 8px

    # Shank
    draw.rectangle([cx - 23, cy - 108, cx + 23, cy + 108], outline=(220, 220, 220), width=2)
    # Head (flat)
    draw.rectangle([cx - 46, cy - 108, cx + 46, cy - 84], outline=(220, 220, 220), width=2)

    # Dimension annotations
    draw.text((470, 280), "M6×1.0", fill=(180, 180, 180))
    draw.text((470, 300), "Ø5.82", fill=(180, 180, 180))
    draw.text((470, 320), "Ø11.5 HD", fill=(180, 180, 180))
    draw.text((470, 340), "L=33", fill=(180, 180, 180))
    draw.text((470, 360), "10B21", fill=(180, 180, 180))

    img.save(path, "JPEG", quality=90)
    print(f"Saved demo drawing to {path}")
```

---

## Task 6: CI Configuration

### File: `.github/workflows/ci.yml`

```yaml
name: CI

on: [push, pull_request]

jobs:
  backend-test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16
        env:
          POSTGRES_DB: fastenergpt
          POSTGRES_USER: dev
          POSTGRES_PASSWORD: devpassword
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v4
        with:
          python-version: "3.12"

      - name: Install system dependencies
        run: |
          sudo apt-get update && sudo apt-get install -y \
            libgl1 libglib2.0-0 libxrender1 libxext6 libx11-6 \
            libfontconfig1 libxi6 libxrandr2 libgomp1

      - name: Install Python deps
        working-directory: backend
        run: uv sync

      - name: Run unit tests
        working-directory: backend
        run: uv run pytest tests/ -m "not integration and not benchmark" -v --tb=short

  frontend-test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: "20"
          cache: "npm"
          cache-dependency-path: frontend/package-lock.json

      - name: Install deps
        working-directory: frontend
        run: npm ci

      - name: Type check
        working-directory: frontend
        run: npx tsc --noEmit

      - name: Run tests
        working-directory: frontend
        run: npm test -- --run
```

---

## Acceptance Criteria

- [ ] `pytest tests/ -m "not integration"` passes with 0 failures
- [ ] `pytest tests/ -m integration` passes (with API keys set) for M6, M8, M10 test cases
- [ ] Playwright `demo_flow.spec.ts` passes against running local stack
- [ ] 10-minute demo script can be followed start to finish without errors
- [ ] Demo fixture drawing (`m6_flat_head_33_bolt.jpg`) is checked in
- [ ] GitHub Actions CI passes on push
- [ ] Full pipeline for M6 bolt completes in < 120 seconds (cold, no cache)
- [ ] `GET /api/v1/rag/stats` returns `total_cases >= 200` after seeding

## Files Created/Modified
- `backend/tests/integration/test_e2e_pipeline.py` (new)
- `backend/tests/integration/test_upload_pipeline.py` (new)
- `backend/tests/test_performance.py` (new)
- `backend/tests/test_data/m6_flat_head_33_bolt.jpg` (new — demo fixture)
- `backend/scripts/create_demo_drawing.py` (new)
- `frontend/tests/e2e/demo_flow.spec.ts` (new)
- `frontend/playwright.config.ts` (new)
- `docs/DEMO_SCRIPT.md` (new)
- `.github/workflows/ci.yml` (new)
