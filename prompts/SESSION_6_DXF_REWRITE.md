# Session 6: DXF Drawing Rewrite

Read @CLAUDE.md for full project context. Session 5 must be complete (CADQuery working).

## Goal

Rewrite the DXF generator so output files open in AutoCAD/LibreCAD as actual engineering drawings — driven dimension entities with arrows and leaders, proper ANSI31 cross-section hatching, tolerances on critical dimensions, and a clean layout following GB/T 4458 conventions.

Current state: generator draws polylines and plain text. The result opens in AutoCAD but looks like a hand-sketch, not an engineering drawing. An engineer cannot use it.

Target: an engineer opens the DXF, sees proper dimension chains with tolerances, a cross-section hatch, centerlines, and can immediately understand all critical dimensions without modification.

---

## Task 1: Dimension Style Setup

### File: `backend/app/drawings/standards.py`

Extend `setup_dimension_style()` to configure a proper GB-standard dim style named `"GB"`:

```python
dimstyle = doc.dimstyles.new("GB")
dimstyle.set_arrows(blk="ARCHTICK", size=2.5)   # architectural tick arrows
dimstyle.dxf.dimtxt = 3.5        # text height mm
dimstyle.dxf.dimgap = 1.5        # gap between extension line and text
dimstyle.dxf.dimexe = 2.0        # extension line extension beyond dim line
dimstyle.dxf.dimexo = 1.0        # extension line offset from origin
dimstyle.dxf.dimdli = 8.0        # dimension line increment (baseline dims)
dimstyle.dxf.dimtol = 0          # tolerances off by default (set per-dim)
dimstyle.dxf.dimlunit = 2        # decimal units
dimstyle.dxf.dimrnd = 0.001      # round to 0.001mm
dimstyle.dxf.dimtfac = 0.6       # tolerance text scale factor
dimstyle.dxf.dimclrd = 5         # dim line color: blue
dimstyle.dxf.dimclre = 5         # ext line color: blue
dimstyle.dxf.dimclrt = 7         # text color: white/black
```

Also add a center mark style and a `setup_text_styles()` function that registers:
- `"GB_TITLE"`: height 7.0, font "isocp.shx" or "txt" (AutoCAD standard)
- `"GB_NOTE"`: height 3.5
- `"GB_DIM"`: height 3.5, oblique 0

---

## Task 2: Rewrite Die Component Drawing

### File: `backend/app/drawings/generator.py`

Full rewrite of `_draw_die_component_view()`, `_add_section_hatch()`, and `_add_die_annotations()`.

### 2a: Cross-Section View with Proper Hatch

Replace `_add_section_hatch()` with `_add_hatch(msp, boundary_pts, layer="HATCH")`:

```python
def _add_hatch(self, msp, boundary_pts: list[tuple], layer: str = "HATCH") -> None:
    hatch = msp.add_hatch(color=8, dxfattribs={"layer": layer})
    hatch.set_pattern_fill("ANSI31", scale=1.5, angle=45)
    path = hatch.paths.add_polyline_path(
        [(x, y) for x, y in boundary_pts],
        is_closed=True
    )
```

Call this separately for the left half and right half of the cross-section (die is symmetric — hatch both sides of the wall separately).

### 2b: Driven Dimension Entities

Replace all `msp.add_text(f"⌀{od}...")` calls with proper dimension entities.

Key rule: **always call `dim.render()` after adding a dimension or the geometry won't appear.**

Implement `_add_linear_dim(msp, p1, p2, offset, label_override=None)`:
```python
def _add_linear_dim(self, msp, p1, p2, offset, tol_upper=None, tol_lower=None):
    dim = msp.add_linear_dim(
        base=(p1[0], p2[1] + offset),
        p1=p1, p2=p2,
        dimstyle="GB",
        override={"dimtol": 1, "dimtp": tol_upper or 0, "dimtm": tol_lower or 0}
        if (tol_upper or tol_lower) else {}
    )
    dim.render()
    return dim
```

Implement `_add_diameter_dim(msp, center, radius, angle_deg, tol_upper=None, tol_lower=None)`:
```python
def _add_diameter_dim(self, msp, center, radius, angle_deg=0):
    dim = msp.add_diameter_dim(
        center=center,
        radius=radius,
        angle=angle_deg,
        dimstyle="GB",
    )
    dim.render()
    return dim
```

### 2c: Die Drawing Layout (for punch component)

Draw the punch as a proper front sectional view. Profile from bottom (working face) to top (shank):

```
Coordinate system: origin at (cx, cy), Y-axis up, symmetric about X=cx

Profile points (right half, outer boundary):
  (cx, cy)                                    ← tip / working face center
  (cx + wd/2, cy)                             ← working face outer edge
  (cx + wd/2, cy + working_len)               ← shoulder start
  (cx + sd/2, cy + working_len)               ← shoulder step-up
  (cx + sd/2, cy + working_len + shoulder_h)  ← top
  (cx, cy + working_len + shoulder_h)          ← top center

Mirror for left half.
```

For conical punch (heading): add taper between working face and body:
```
  (cx, cy)                              ← tip
  (cx + tip_r, cy)                      ← tip edge (tip_r = land_length/2 or 1mm)
  (cx + wd/2, cy + cone_height)         ← where cone meets body
  (cx + wd/2, cy + working_len)         ← body top
  ... shoulder as above
```

Hatch the right-half profile. Mirror as outline only. Draw center line.

Add dimensions:
- OD: linear dim from (cx - wd/2, cy + working_len * 0.3) to (cx + wd/2, same), offset +10
- Shoulder OD: same at shoulder level
- Working length: linear dim on the right side, p1=(cx + sd/2 + 5, cy), p2=(same, cy+working_len), vertical
- Total length: another vertical dim for shoulder portion
- Approach angle (if present): angular dim on the taper

### 2d: Die Drawing Layout (for die component)

Draw the die as a half-section view showing:
- Outer cylinder wall (solid line, OUTLINE layer)
- Bore/cavity (solid line inside, OUTLINE layer — it's a section view)
- Entry chamfer/taper at top
- ANSI31 hatch on the wall cross-section (between outer edge and bore)

Hatch boundary for die wall (right half):
```
outer_bottom (cx + od/2, cy)
outer_top    (cx + od/2, cy + length)
inner_top    (cx + id/2, cy + length)   # or chamfer start
inner_bottom (cx + id/2, cy)
close back to outer_bottom
```

For `conical` die (extrusion): add the tapered bore profile:
```
bore entry (cx + id_entry/2, cy + length)   ← top, larger
bore land  (cx + id_exit/2, cy + land_len)   ← land start
bore exit  (cx + id_exit/2, cy)              ← bottom, smaller
```

Add dimensions:
- OD: diameter dim at mid-height
- Bore ID: diameter dim inside bore
- Total length: vertical linear dim on right side
- Land length: linear dim for land portion
- Approach angle: angular dim on taper
- Tolerances on bore ID: `+{clearance_mm:.3f} / 0.000` (H7 fit)

---

## Task 3: Production Drawing Improvements

### File: `backend/app/drawings/generator.py`

Rewrite `_draw_fastener_profile()` to draw a proper half-section view of the fastener:

For flat-head bolts:
- Head: trapezoid (top flat, sides at 90° chamfer angle)
- Drive recess: blind bore (dashed lines) if drive_type is cross or hex_socket
- Shank: rectangle
- Thread: show as root/crest lines (thin lines at thread_pitch spacing for 10mm of thread)
- Knurl section: diagonal crosshatch if present

Replace `_add_part_dimensions()` with proper dimension calls:
- Diameter chain: shank ⌀, head ⌀
- Length chain: head height, shank length, thread length, total length
- Thread callout: leader line pointing to thread area with text `M6×1.0-6g`
- Material and grade as a note block (not dimension entities)

---

## Task 4: Process Breakdown Sheet

### File: `backend/app/drawings/generator.py`

Rewrite `_draw_workpiece_silhouette()` to use accurate intermediate shapes:

Each silhouette should show:
- Proper head profile matching the operation type (blank = full cylinder, S1 = partially upset, etc.)
- Dimension annotation: `⌀{max_d}×{length}L` below each shape
- Shading (diagonal lines) to indicate material

The station label above each shape should include:
- Station number
- Operation type in English + Chinese (e.g., "S2 Heading 镦头")
- Key parameter (upset_ratio or reduction %)

---

## Task 5: Verification — Open in LibreCAD

After implementing, test the DXF output:

```python
# Test script: backend/tests/drawings/test_dxf_quality.py
import ezdxf

def test_die_drawing_has_dimensions():
    doc = ezdxf.readfile("test_output/station_1/punch_drawing.dxf")
    msp = doc.modelspace()
    dims = [e for e in msp if e.dxftype() == "DIMENSION"]
    assert len(dims) >= 4, f"Expected >= 4 dimensions, got {len(dims)}"

def test_die_drawing_has_hatch():
    doc = ezdxf.readfile("test_output/station_1/punch_drawing.dxf")
    msp = doc.modelspace()
    hatches = [e for e in msp if e.dxftype() == "HATCH"]
    assert len(hatches) >= 1

def test_dimensions_are_rendered():
    doc = ezdxf.readfile("test_output/station_1/punch_drawing.dxf")
    # Rendered dimensions produce BLOCK entities with the dim geometry
    blocks = list(doc.blocks)
    dim_blocks = [b for b in blocks if b.name.startswith("*D")]
    assert len(dim_blocks) >= 4
```

---

## Acceptance Criteria

- [ ] DXF files open in LibreCAD without errors
- [ ] Punch drawing has ≥ 4 DIMENSION entities (OD, shoulder OD, working length, total length)
- [ ] Die drawing has ≥ 4 DIMENSION entities (OD, bore ID with tolerance, length, land length)
- [ ] Both drawings have ≥ 1 HATCH entity with ANSI31 pattern
- [ ] All dimensions have `.render()` called (verified by `*D` blocks existing)
- [ ] Tolerances appear on bore ID: format `+0.015 / 0.000`
- [ ] Production drawing shows shank ⌀, head ⌀, total length, thread callout
- [ ] Process breakdown sheet shows all intermediate shapes with labels

## Files Modified
- `backend/app/drawings/generator.py` (major rewrite)
- `backend/app/drawings/standards.py` (extend dim style setup)
- `backend/tests/drawings/test_dxf_quality.py` (new test)
