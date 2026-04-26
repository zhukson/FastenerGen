# Session — Template Library Expansion

## Goal

Move the geometry library from "stacked cylinders" to "looks like a real die." The LLM still emits the same `DieComponentParams`, but the parameters now drive richer 3D solids and 2D drawings that share a single source of truth.

## Why

Current state ([punch_templates.py](backend/app/geometry/punch_templates.py), [die_templates.py](backend/app/geometry/die_templates.py), [numpy_templates.py](backend/app/geometry/numpy_templates.py)):
- 3 punch CADQuery classes — each is essentially two stacked cylinders.
- 3 die CADQuery classes — each is a cylinder with one bore.
- Trimesh fallback (the path Docker actually uses) has **one** punch profile and **one** die profile — geometry_type is ignored.
- 2D punch/die drawings build their own profile inline, so 2D and 3D drift over time.
- Schema fields like `relief_angle_deg`, `cavity_depth`, `entry_radius` are accepted by the LLM but never visualized.

Engineers looking at the demo see "this is just bullets and pipes." Even at Phase-1 fidelity we can do meaningfully better.

## Architecture

Single source of truth for axisymmetric profiles:

```
                     ┌───────────────────────────┐
                     │ geometry/profiles.py      │
                     │  build_punch_profile(...) │
                     │  build_die_profile(...)   │
                     │  → list[(r, z)]            │
                     └─────────────┬─────────────┘
                                   │
                ┌──────────────────┼──────────────────┐
                ▼                  ▼                  ▼
       numpy_templates       drawings/generator   punch/die_templates
       (3D revolution        (2D side view)       (CADQuery STEP)
        STL meshes)
```

Both 2D drawings and 3D meshes consume the same profile. CADQuery STEP path (only used when conda image has cadquery) gets the same set of geometry types via parallel implementation.

## Scope

### In scope
1. New module `backend/app/geometry/profiles.py` with profile-builder functions.
2. Refactor `numpy_templates.py` to delegate to `profiles.py`. Add a generic `_revolve_closed_polygon` helper so dies can have non-trivial cross-sections (entry cone + land + relief bore).
3. Refactor `_draw_punch_view` / `_draw_die_view` in `drawings/generator.py` to use the same profile.
4. Update CADQuery templates so STEP exports match (when CADQuery is available).
5. Add automatic feature dimensioning (countersink angle, sphere radius, relief callout).
6. Generate fresh M5 Torx + M6 flat-head designs and visually verify.

### Out of scope (deliberate cuts)
- GD&T tolerance frames (concentricity boxes etc.)
- Two-body insert + case-ring dies
- Trimming-die polygon apertures (hex/square)
- Schema/enum changes (use existing fields creatively instead)
- Unit tests (smoke-tested via render only)

## New geometry archetypes

### Punch (5 profiles)

| Selector                                    | Profile                                                              | Use case                          |
|---------------------------------------------|----------------------------------------------------------------------|-----------------------------------|
| `flat_face` + approach=90                   | working ⌀ → 90° flat face                                            | Pre-form / upsetting              |
| `flat_face` + approach<90                   | working ⌀ → conical countersink face (e.g. 100°)                     | Flat-head finish punch            |
| `closed_heading`                            | working ⌀ → spherical face (R = workingD/2)                          | Button / pan / round head         |
| `conical` (extrusion punch)                 | long body + tapered face                                              | Forward extrusion punch           |
| any + drive_pocket detected (via pp_extra)  | base profile minus axial pocket on face (hex/torx/cross via metadata) | Drive-forming finish punch        |

All include: shoulder transition with under-shoulder fillet, ejector-pin recess at the rear (concave dimple, R=workingD×0.15).

### Die (4 profiles)

| Selector                                | Cross-section                                                            | Use case                              |
|-----------------------------------------|--------------------------------------------------------------------------|---------------------------------------|
| `cylindrical` / default                 | OD × length, single straight bore + entry chamfer                         | Trim / pierce                         |
| `conical` + relief_angle_deg            | 3-zone bore: entry cone (approach°) → land → relief cone (relief_angle°) | Forward-extrusion die                 |
| `closed_heading`                        | Through bore lower 60% + closed forming cavity upper 40%                  | Heading die (head cavity)             |
| `flat_face`                             | Through bore + flat-bottom forming pocket                                 | Heading die for flat-head formation   |

All dies include a 45° entry chamfer (top edge), and the wall is shown as a closed cross-section so the relief is visible in side view.

## File-by-file changes

### New
- **[backend/app/geometry/profiles.py](backend/app/geometry/profiles.py)** — pure functions, no trimesh/CADQuery import. Returns lists of (r, z) tuples for revolution. ~250 lines.

### Modified
- **[backend/app/geometry/numpy_templates.py](backend/app/geometry/numpy_templates.py)**
  - `build_punch_mesh` → delegates to `profiles.build_punch_profile` then `_revolve_profile`.
  - `build_die_mesh` → delegates to `profiles.build_die_wall` (closed polygon) then new `_revolve_closed_polygon`.
  - Add `_revolve_closed_polygon(polygon, sections)` helper for closed wall cross-sections.
  - Keep existing `_revolve_profile` for axis-anchored profiles (punches).

- **[backend/app/drawings/generator.py](backend/app/drawings/generator.py)**
  - `_draw_punch_view`: replace inline profile with `profiles.build_punch_profile`. Auto-dimension features detected in profile (sphere R, conical face °, pocket).
  - `_draw_die_view`: replace inline wall profile with `profiles.build_die_wall`. Add zone labels (Entry / Land / Relief).
  - Add surface-roughness ▽ symbol at working face for punches and bore for dies (uses `params.surface_roughness_ra`).
  - Add zoomed drive-recess detail box on production drawing (~3× actual size).

- **[backend/app/geometry/punch_templates.py](backend/app/geometry/punch_templates.py)** & **[die_templates.py](backend/app/geometry/die_templates.py)**
  - Add new template classes for the new archetypes, wired through the existing `_TEMPLATE_MAP` dispatcher. CADQuery solids built via `Workplane.revolve()` of a 2D wire (which can be built straight from the profile list).

### Untouched
- Schemas — existing fields are sufficient.
- Designer / RAG / verification — same `DieComponentParams` flow.
- Assembly builder — its `_build_profile` already lives in `workpiece.py` and uses its own profile; not changing.
- Frontend.

## Implementation order

1. **profiles.py** — write all 5 punch + 4 die profile functions with sensible defaults.
2. **numpy_templates.py refactor** — switch mesh generators to delegate; add `_revolve_closed_polygon`.
3. **Smoke test 3D path** — generate one design, render assembly STL in viewer.
4. **generator.py 2D refactor** — switch punch/die views to delegated profiles.
5. **2D extras** — surface-finish symbol, drive recess detail, zone labels.
6. **CADQuery templates** — port the new archetypes (only matters when CADQuery is installed; trimesh path was the demo path).
7. **Visual verification** — render production + station 1 punch + station 1 die for M5 Torx; eyeball against the prior renders.

## Verification checklist

- [ ] Production drawing: drive-recess detail zoom is legible (≥2× actual size).
- [ ] Station 1 punch DXF: working face shape matches geometry_type — flat for upsetting, sphere for round head, cone for flat-head.
- [ ] Station 1 die DXF: 3 zones visible if extrusion; closed cavity visible if heading.
- [ ] 3D viewer: punch.stl looks like a punch (shoulder + ejector dimple visible); die.stl looks like a die (relief bore visible from end view).
- [ ] All previous test designs still complete without errors (no schema breakage).
- [ ] Type-check + lint clean.

## Time budget

This is one focused session. If we hit complexity in step 6 (CADQuery parity), we ship steps 1-5 and document step 6 as follow-up — Docker uses trimesh so STEP files for new archetypes can wait.
