# Session 7: Workpiece + Assembly 3D

Read @CLAUDE.md for full project context. Sessions 5–6 must be complete.

## Goal

Every station produces four STL files: `punch.stl`, `die.stl`, `workpiece.stl`, `assembly.stl`. The workpiece at each station shows the correct intermediate shape (blank → partially upset → partially headed → finished). The assembly STL places punch above die with workpiece inside die cavity.

After this session, the 3D viewer can show the full story of metal forming — what the part looks like between each station — not just the tooling.

---

## Task 1: Improve Workpiece Intermediate Shape Generator

### File: `backend/app/geometry/workpiece.py`

Read the existing implementation first. The current `generate_intermediate()` stacks two cylinders — correct concept but geometrically wrong for most shapes.

Rewrite using the revolution profile approach (same as `numpy_templates.py`). For each `ShapeDescription`, build a 2D profile and revolve it.

### Profile rules by stage:

**Blank (wire stock):**
Profile: simple cylinder
```
(0,0) → (d/2, 0) → (d/2, L) → (0, L)
```

**After upsetting station (partially headed):**
Profile: cylinder with wider top (partial head formation)
```
(0, 0) → (shank_r, 0) → (shank_r, shank_len)
→ (head_r, shank_len) → (head_r, shank_len + partial_head_h)
→ (0, shank_len + partial_head_h)
```
Where `partial_head_h = head_height * 0.6` and `head_r = shank_r * upset_ratio * 0.85`

**After heading station (finished head):**
Profile: full bolt with flat head
- For flat head: trapezoid head (chamfer_angle at rim) + shank
- For hex head: approximate as cylinder (revolution solid can't do hex, that's fine for preview)
- For socket cap: dome + shank

```python
def _flat_head_profile(head_r, head_h, chamfer_r, shank_r, shank_len, thread_r, thread_len):
    chamfer_h = (head_r - chamfer_r) / math.tan(math.radians(30))  # 30° underhead
    return [
        (0.0, 0.0),                              # tip center
        (thread_r, 0.0),                          # thread root
        (shank_r, thread_len),                    # shank/thread junction
        (shank_r, shank_len + thread_len),        # underhead
        (chamfer_r, shank_len + thread_len),      # chamfer start
        (head_r, shank_len + thread_len + chamfer_h),  # head rim
        (head_r, shank_len + thread_len + head_h),     # head top rim
        (0.0, shank_len + thread_len + head_h),        # top center
    ]
```

**After forward extrusion (reduced diameter section):**
Profile: cylinder with smaller diameter section at tip
```
(0,0) → (ext_r, 0) → (ext_r, ext_len) → (body_r, ext_len + transition) → (body_r, total_len) → (0, total_len)
```

### ShapeDescription to profile mapping:

```python
def _build_profile(shape: ShapeDescription) -> list[tuple[float, float]]:
    shank_r = (shape.shank_diameter or shape.max_diameter) / 2
    head_r = (shape.head_diameter or shape.max_diameter) / 2
    head_h = shape.head_height or 0.0
    total = shape.overall_length
    shank_len = total - head_h

    if head_r <= shank_r * 1.05:
        # Essentially cylindrical (blank or extruded section)
        return [(0, 0), (shank_r, 0), (shank_r, total), (0, total)]

    # Has a head
    profile = [
        (0.0, 0.0),
        (shank_r, 0.0),
        (shank_r, shank_len),
        (head_r, shank_len),
        (head_r, total),
        (0.0, total),
    ]
    return profile
```

Add both CADQuery path and numpy/trimesh path:
```python
def generate_intermediate(self, shape: ShapeDescription) -> Any:
    try:
        return self._cadquery_intermediate(shape)
    except (ImportError, Exception):
        return self._trimesh_intermediate(shape)

def _trimesh_intermediate(self, shape: ShapeDescription) -> "trimesh.Trimesh":
    from app.geometry.numpy_templates import _revolve_profile
    profile = self._build_profile(shape)
    return _revolve_profile(profile, sections=48)
```

---

## Task 2: Assembly STL Builder

### File: `backend/app/geometry/assembly.py`

Read existing implementation. Add a numpy/trimesh path alongside the CADQuery path.

### Assembly positioning logic:

```
Z-axis layout (trimesh path):

  punch:     positioned at Z = die_length + gap (10mm above die top)
  workpiece: positioned at Z = (die_length - workpiece_length) / 2 (centered in die)
  die:       positioned at Z = 0 (reference)
```

Implement `build_station_assembly_trimesh(punch_mesh, die_mesh, workpiece_mesh, gap_mm=10.0)`:

```python
def build_station_assembly_trimesh(punch_mesh, die_mesh, workpiece_mesh, gap_mm=10.0):
    import trimesh
    import numpy as np

    die_h = die_mesh.bounds[1][2] - die_mesh.bounds[0][2]
    wp_h  = workpiece_mesh.bounds[1][2] - workpiece_mesh.bounds[0][2]

    # Workpiece: translate so its center is inside die
    wp_offset = (die_h - wp_h) * 0.6
    workpiece_t = workpiece_mesh.copy()
    workpiece_t.apply_translation([0, 0, wp_offset])

    # Punch: above die
    punch_h = punch_mesh.bounds[1][2] - punch_mesh.bounds[0][2]
    punch_t = punch_mesh.copy()
    punch_t.apply_translation([0, 0, die_h + gap_mm])

    return trimesh.util.concatenate([die_mesh, workpiece_t, punch_t])
```

---

## Task 3: Wire Up in Designer

### File: `backend/app/ai/designer.py`

In `_generate_outputs()`, the current loop is:
```python
for die_param in dies:
```

Change to zip with the process plan stations so you have access to `ShapeDescription`:
```python
for die_param, station_plan in zip(dies, plan.stations):
    sn = die_param.station_number
```

After generating punch.stl and die.stl for a station, add:

```python
# Workpiece intermediate shape
from app.geometry.workpiece import WorkpieceGenerator
from app.geometry.assembly import AssemblyBuilder

wp_gen = WorkpieceGenerator()
wp_mesh = wp_gen.generate_intermediate(station_plan.output_shape)
wp_path = export_stl(wp_mesh, station_dir / "workpiece.stl")
files.append(OutputFile(
    file_type="workpiece_stl",
    station_number=sn,
    file_path=str(wp_path),
    format=FileFormat.stl,
    size_bytes=wp_path.stat().st_size,
))

# Assembly preview
punch_m = build_punch_mesh(die_param.punch)
die_m   = build_die_mesh(die_param.die)
asm_mesh = build_station_assembly_trimesh(punch_m, die_m, wp_mesh)
asm_path = export_stl(asm_mesh, station_dir / "assembly.stl")
files.append(OutputFile(
    file_type="assembly_preview",
    station_number=sn,
    file_path=str(asm_path),
    format=FileFormat.stl,
    size_bytes=asm_path.stat().st_size,
))
```

Also generate the blank workpiece (wire stock) for station 0:
```python
blank_shape = plan.stations[0].input_shape
blank_mesh = wp_gen.generate_intermediate(blank_shape)
blank_dir = output_dir / "station_0"
blank_dir.mkdir(exist_ok=True)
blank_path = export_stl(blank_mesh, blank_dir / "workpiece.stl")
files.append(OutputFile(
    file_type="workpiece_stl",
    station_number=0,
    file_path=str(blank_path),
    format=FileFormat.stl,
    size_bytes=blank_path.stat().st_size,
))
```

### Update OutputFile schema validation

### File: `backend/app/data/schemas.py`

If `"workpiece_stl"` and `"assembly_preview"` are not already in the `file_type` Literal, add them. Check line ~570 for `OutputFile.file_type`.

---

## Task 4: Projector — 2D from 3D

### File: `backend/app/geometry/projector.py`

Read the existing implementation. This module should provide a `project_to_dxf()` function that takes a 3D mesh and generates a 2D projection. Used by Session 6's DXF generator to get accurate cross-sections.

If it's a stub, implement the minimal version:
1. Take the trimesh mesh
2. Compute front view (XZ plane) by projecting all triangles
3. Return the outline as a list of (x, y) polyline segments
4. This gives the DXF generator accurate outer profile instead of hand-coded geometry

This is optional for Session 7 but enables Session 6 to have perfectly accurate 2D views.

---

## Acceptance Criteria

- [ ] Each station directory contains `punch.stl`, `die.stl`, `workpiece.stl`, `assembly.stl`
- [ ] Station 0 (blank) directory contains `workpiece.stl` (wire cylinder)
- [ ] Workpiece at final station clearly shows head profile (wider than shank)
- [ ] Assembly STL: punch is positioned above die, workpiece is partially inside die
- [ ] Generation time for 4-station M6 bolt stays under 15 seconds (trimesh path)
- [ ] No Python exceptions during workpiece/assembly generation
- [ ] `total_files >= 14` in `design_complete` log for a 4-station design (2 DXF + blank + 4×(punch+die+workpiece+assembly) = 2+1+16=19)

## Files Modified
- `backend/app/geometry/workpiece.py` (major rewrite)
- `backend/app/geometry/assembly.py` (add trimesh path)
- `backend/app/geometry/numpy_templates.py` (add `build_assembly_stl`)
- `backend/app/ai/designer.py` (zip with station_plan, add workpiece+assembly generation)
- `backend/app/data/schemas.py` (add file_type literals if missing)
