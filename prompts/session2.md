# Session 2: Drawings, 3D Geometry, and Drawing Understanding

Read @CLAUDE.md for project context. Session 1 must be complete.

## Goal

Build the three foundational capabilities: (1) read/write 2D engineering drawings, (2) generate 3D die models from parameters, (3) understand product drawings using multi-modal LLM. These three capabilities are the "I/O layer" of the entire system.

## Task 1: DWG/DXF Parser

Create `backend/app/drawings/parser.py`.

Read DWG/DXF files with ezdxf and extract structured data:

```python
class DrawingParser:
    def parse(self, file_path: str) -> ParsedDrawing:
        """
        Parse a DWG/DXF file into structured data.

        Extracts:
        - All DIMENSION entities → ExtractedDimension (value, tolerance, type)
        - LINE, ARC, CIRCLE, LWPOLYLINE → geometric entities
        - TEXT, MTEXT → annotations (material specs, notes, requirements)
        - INSERT blocks → title block data
        - Identify drawing type: product, punch, die, assembly

        Handles: R2010-R2018, Chinese+English text, missing entities.
        """
```

Output: `ParsedDrawing` model from schemas.

Test with: 3-5 public DXF files downloaded from online CAD libraries + 2-3 programmatically created test DXF files.

## Task 2: Drawing Standards

Create `backend/app/drawings/standards.py`.

Define constants and helpers for Chinese engineering drawing standards (GB/T):

```python
# Paper sizes, margins
DRAWING_SIZES = {"A4": (210, 297), "A3": (420, 297), "A2": (594, 420)}

# Standard layer definitions (name, color, linetype, lineweight)
STANDARD_LAYERS = {
    "OUTLINE":   {"color": 7, "linetype": "Continuous", "lineweight": 50},
    "CENTER":    {"color": 1, "linetype": "CENTER",     "lineweight": 25},
    "DIMENSION": {"color": 3, "linetype": "Continuous", "lineweight": 25},
    "HIDDEN":    {"color": 5, "linetype": "DASHED",     "lineweight": 25},
    "HATCH":     {"color": 8, "linetype": "Continuous", "lineweight": 13},
    "TEXT":      {"color": 7, "linetype": "Continuous", "lineweight": 25},
    "TITLEBLOCK":{"color": 7, "linetype": "Continuous", "lineweight": 35},
}

class TitleBlockTemplate:
    """Draw standard title block at given position. Supports Chinese text."""
    def draw(self, msp, position, data: TitleBlock): ...

class DrawingFrame:
    """Draw standard drawing frame for given paper size with border."""
    def draw(self, msp, paper_size: str): ...

def setup_dimension_styles(doc):
    """Configure dimension styles matching GB/T standards."""
    # Arrow size, text height, tolerance display format, decimal places
```

## Task 3: DWG/DXF Generator

Create `backend/app/drawings/generator.py`.

Generate complete, properly formatted engineering drawings from parameters:

```python
class DrawingGenerator:
    def generate_die_drawing(
        self,
        die_params: DieComponentParams,
        station_number: int,
        component_type: str,  # "punch" or "die"
        output_path: str,
        paper_size: str = "A3"
    ) -> str:
        """
        Generate a complete die drawing.

        1. Create new DXF document
        2. Set up layers (standards.py)
        3. Draw frame and title block
        4. Draw main view (front/profile)
        5. Draw side/section view
        6. Add all dimensions with tolerances
        7. Add material, hardness, treatment annotations
        8. Add technical requirements notes
        9. Save as DXF
        """

    def generate_production_drawing(
        self,
        part_features: PartFeatures,
        process_plan: ProcessPlan,
        output_path: str
    ) -> str:
        """Generate production drawing with process compensations."""

    def generate_process_breakdown(
        self,
        process_plan: ProcessPlan,
        output_path: str
    ) -> str:
        """Generate process breakdown showing intermediate shapes per station."""
```

Must handle: Chinese text, proper dimension annotations with tolerances, section hatching, multiple views on one sheet.

## Task 4: 3D Parametric Die Templates

Create the 3D geometry generation modules.

### `backend/app/geometry/punch_templates.py`

```python
class PunchTemplateBase(ABC):
    """Base for all parametric punch 3D models."""
    @abstractmethod
    def generate(self, params: DieComponentParams) -> Any:
        """Generate 3D solid model. Returns CADQuery Workplane or OCC shape."""

class FlatPunchTemplate(PunchTemplateBase):
    """Flat-bottom punch for upsetting operations.
    Geometry: cylindrical shank → transition → flat working face.
    Parameters: shank_dia, shank_length, face_dia, face_length, transition_angle."""

class PreformPunchTemplate(PunchTemplateBase):
    """Pre-forming punch with cavity profile.
    Geometry: shank → transition → profiled cavity.
    Parameters: shank_dia, cavity_profile (list of points/arcs), depth."""

class FinishPunchTemplate(PunchTemplateBase):
    """Finishing punch with final product negative shape.
    Geometry: shank → transition → detailed cavity matching product head."""
```

### `backend/app/geometry/die_templates.py`

```python
class StraightDieTemplate:
    """Straight cylindrical bore die.
    For simple upsetting stations.
    Parameters: outer_dia, bore_dia, bore_length, body_length."""

class TaperedDieTemplate:
    """Tapered bore die for extrusion/reduction.
    Parameters: outer_dia, entry_dia, exit_dia, taper_angle, body_length."""

class FormingDieTemplate:
    """Forming die with profiled cavity.
    For head forming stations. Cavity profile matches desired intermediate shape.
    Parameters: outer_dia, cavity_profile, cavity_depth, body_length."""
```

### `backend/app/geometry/workpiece.py`

```python
class WorkpieceGenerator:
    """Generate 3D models of intermediate workpiece shapes."""

    def generate_blank(self, diameter: float, length: float) -> Any:
        """Wire blank (cylinder)."""

    def generate_intermediate(self, station_plan: StationPlan) -> Any:
        """Intermediate shape after a forming station.
        Approximated as revolution solid from 2D profile."""
```

### `backend/app/geometry/assembly.py`

```python
class AssemblyBuilder:
    """Position punch + die + workpiece for visualization."""

    def build_station_assembly(
        self, punch_3d, die_3d, workpiece_3d, station_plan: StationPlan
    ) -> Any:
        """Position components: die at bottom, workpiece inside, punch above."""

    def build_full_assembly(self, stations: list) -> Any:
        """Side-by-side view of all stations."""
```

### `backend/app/geometry/exporter.py`

```python
class GeometryExporter:
    """Export 3D geometry to various formats."""

    def to_step(self, shape, output_path: str) -> str: ...
    def to_stl(self, shape, output_path: str) -> str: ...
    def to_preview_png(self, shape, output_path: str,
                       view_angle: tuple = (45, 35)) -> str:
        """Render to PNG for thumbnails. Use trimesh or PyVista."""
```

### `backend/app/geometry/projector.py`

```python
class ViewProjector:
    """Project 3D geometry to 2D views for drawing generation."""

    def project_front(self, shape) -> List[GeometricEntity2D]: ...
    def project_side(self, shape) -> List[GeometricEntity2D]: ...
    def project_section(self, shape, plane) -> List[GeometricEntity2D]: ...
```

For Phase 1, start with simple parametric shapes (cylinders, cones, revolution profiles). Complex free-form surfaces come later with more data.

Test: Generate a flat punch and a straight die, export to STEP+STL, verify files are valid.

## Task 5: Multi-Modal Drawing Understanding

Create `backend/app/ai/drawing_reader.py`.

Use Claude Opus 4.7 Vision to read and understand product drawings:

```python
class DrawingReader:
    async def read_drawing(self, file_path: str) -> PartFeatures:
        """
        1. Convert to image(s): PDF→images (pdftoppm), DWG→images (ezdxf render)
        2. Send to Claude Vision with extraction prompt
        3. Parse JSON response into PartFeatures
        4. Validate (sanity checks: M6 thread → ~6mm dia, etc.)
        5. Return PartFeatures
        """

    def _build_extraction_prompt(self) -> str:
        """
        Comprehensive prompt for extracting ALL information from a
        cold-heading fastener product drawing.

        The prompt must handle:
        - Chinese and English text
        - Standard dimension notation
        - Tolerance expressions (±0.15, +0.05/-0, etc.)
        - Material codes (10B21, SCM435, SUS304, etc.)
        - Process annotations (冷镦, 搓花, 搓牙, etc.)
        - Performance specs (8.8级, HRC 22-32, salt spray, etc.)
        - Surface treatments (三价蓝白锌, 达克罗, etc.)
        - Thread specifications (M6-1.0P-6g/6h)

        Output: strict JSON matching PartFeatures schema.
        Prompt version: DU_V1_0_0
        """
```

The prompt design is critical. Reference the real PDF sample (18149-D6 M6×33 10B21) — the prompt must successfully extract everything we manually identified from that drawing.

## Task 6: Drawing Understanding Evaluation

Create `backend/app/eval/drawing_eval.py`.

Hand-annotate expected extraction results for our real PDF:

```python
GOLDEN_DRAWING_CASES = [
    {
        "id": "real_001_18149_D6",
        "file": "tests/test_data/18149-D6_M6X33_10B21.pdf",
        "expected": {
            "part_type": "flat_head_bolt",
            "spec": "M6x33",
            "material": "10B21",
            "grade": "8.8",
            "surface_treatment": "三价蓝白锌",
            "head_diameter_mm": (10.5, 16.0),  # inner and flange
            "shank_diameter_range": (5.83, 5.96),
            "thread_spec": "M6-1.0P",
            "thread_length_mm": 22.0,
            "total_length_mm": 33.0,
            "head_height_mm": 3.0,
            "process_steps": ["冷镦", "搓花", "搓牙"],
            "hardness_range": "HRC22-32",
            "blank_diameter_mm": 5.25,
        }
    }
]
```

Build automated accuracy evaluation: per-field comparison, overall score.

Copy the real PDF to `backend/tests/test_data/`.

## Task 7: Synthetic Data Generator

Create `backend/app/data/synthetic.py`.

Generate synthetic fastener data for testing (when real data isn't available):

```python
class SyntheticDataGenerator:
    def generate_part_features(self, seed: int = None) -> PartFeatures:
        """Random but realistic fastener features."""
        # Randomly pick: hex bolt, flange bolt, socket cap, pan head, etc.
        # Random but valid: M3-M16, various materials, various grades
        # All dimensions consistent (head dia > shank dia, lengths add up)

    def generate_process_plan(self, features: PartFeatures) -> ProcessPlan:
        """Plausible process plan for given features."""
        # Station count based on upset ratio
        # Reasonable deformation ratios

    def generate_die_parameters(
        self, features: PartFeatures, plan: ProcessPlan
    ) -> List[DieParameters]:
        """Plausible die specs for given plan."""

    def generate_complete_case(self, seed: int = None) -> RAGCase:
        """Generate a complete synthetic case for testing."""

    def generate_batch(self, n: int) -> List[RAGCase]:
        """Generate n synthetic cases with diverse coverage."""
```

Also create `backend/scripts/generate_synthetic.py` CLI that generates N cases and saves to a directory.

## Task 8: API Integration

Wire up the endpoints:

```
POST /api/v1/drawings/upload
  Accept: multipart/form-data (PDF, DWG, DXF, JPG, PNG)
  Store file in MinIO
  Return: {drawing_id, filename, file_type, upload_time}

POST /api/v1/drawings/{id}/understand
  Run DrawingReader (Claude Vision)
  Store PartFeatures in PostgreSQL
  Return: PartFeatures JSON

GET /api/v1/drawings/{id}/features
  Return stored PartFeatures

GET /api/v1/drawings/{id}/preview
  Generate/return preview image of the uploaded drawing

POST /api/v1/geometry/preview
  Input: DieComponentParams JSON
  Generate 3D model, export STL
  Return: STL file URL for frontend 3D viewer
```

## Task 9: Frontend Updates

### Upload Page (`/upload`)

- Drag-and-drop file upload
- Supported formats badge: PDF, DWG, DXF, JPG, PNG
- Upload progress bar
- After upload: show drawing preview image
- "Analyze Drawing" button → calls understand endpoint
- After analysis: show extracted features in organized panels
  - Part Info (type, spec, material, grade)
  - Dimensions (all extracted dims in a table)
  - Process Info (if annotated on drawing)
  - Uncertain fields highlighted in yellow
- "Generate Die Design" button (placeholder → wired in Session 4)

### 3D Viewer Component

- `ThreeDViewer.tsx`: Load and display STL file
  - Orbit controls (rotate, zoom, pan)
  - Grid helper
  - Ambient + directional lighting
  - Multiple color options (steel gray for die, blue for workpiece)
- `StationViewer.tsx`: Show per-station assembly
  - Tabs or carousel to switch between stations
  - Show: punch (top) + die (bottom) + workpiece (middle)

Test the 3D viewer with a simple generated STL (cylinder or cone from CADQuery).

## Verification Checklist

- [ ] DWG/DXF parser extracts dimensions and text from test DXF files
- [ ] Drawing generator creates valid DXF with layers, dimensions, title block, Chinese text
- [ ] Generated DXF opens correctly in LibreCAD or online DXF viewer
- [ ] CADQuery generates valid STEP and STL for basic punch and die shapes
- [ ] 3D preview renders correctly in frontend Three.js viewer
- [ ] Claude Vision extracts >80% of dimensions from sample PDF correctly
- [ ] Synthetic data generator produces valid, diverse PartFeatures
- [ ] Upload → Understand → Features flow works end-to-end
- [ ] All tests pass
