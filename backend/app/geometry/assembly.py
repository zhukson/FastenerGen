"""
Assembly positioning for punch + die + workpiece.

Positions individual 3D solids into a per-station assembly view
aligned on the forming axis. Used to generate assembly preview renders
and for interference checking.

Two paths:
- CADQuery (build_station_assembly): returns cq.Assembly for STEP export
- Trimesh (generate_assembly_stl): no CQ needed, exports combined preview STL
"""

from __future__ import annotations
from pathlib import Path

try:
    import cadquery as cq

    CADQUERY_AVAILABLE = True
except ImportError:
    CADQUERY_AVAILABLE = False

from app.data.schemas import DieParameters, ShapeDescription
from app.geometry.die_templates import build_die
from app.geometry.punch_templates import build_punch
from app.geometry.workpiece import WorkpieceGenerator


def _require_cadquery() -> None:
    if not CADQUERY_AVAILABLE:
        raise ImportError("cadquery is not installed.")


class AssemblyBuilder:
    """Position punch + die + workpiece for 3D visualization and interference check."""

    _wp_gen = WorkpieceGenerator()

    def build_station_assembly(
        self,
        die_params: DieParameters,
        workpiece_shape: ShapeDescription,
        gap_mm: float = 5.0,
    ) -> "cq.Assembly":
        """
        Build a positioned CADQuery assembly for a single forming station.

        Layout (Z-axis = forming axis):
          - Die body at Z = 0 (fixed)
          - Workpiece inside die bore
          - Punch above workpiece, gap_mm clearance from die face

        Args:
            die_params: Punch + die parameters for this station.
            workpiece_shape: Intermediate workpiece shape at this station.
            gap_mm: Gap between punch face and die entry face.
        """
        _require_cadquery()

        punch_solid = build_punch(die_params.punch)
        die_solid = build_die(die_params.die)
        workpiece_solid = self._wp_gen.generate_intermediate(workpiece_shape)

        die_length = die_params.die.working_length
        punch_length = die_params.punch.working_length
        wp_length = workpiece_shape.overall_length

        assembly = (
            cq.Assembly()
            .add(die_solid, name="die", loc=cq.Location((0, 0, 0)))
            .add(
                workpiece_solid,
                name="workpiece",
                loc=cq.Location((0, 0, die_length - wp_length)),
            )
            .add(
                punch_solid,
                name="punch",
                loc=cq.Location((0, 0, die_length + gap_mm)),
            )
        )
        return assembly

    def build_full_assembly(
        self,
        station_assemblies: list["cq.Assembly"],
        spacing_mm: float = 30.0,
    ) -> "cq.Assembly":
        """
        Arrange all station assemblies side-by-side along the X-axis.

        Args:
            station_assemblies: List of single-station assemblies.
            spacing_mm: X-axis gap between station centers.
        """
        _require_cadquery()

        full = cq.Assembly()
        for i, assy in enumerate(station_assemblies):
            full.add(assy, name=f"station_{i + 1}", loc=cq.Location((i * spacing_mm, 0, 0)))
        return full

    def build_station_assembly_stls(
        self,
        die_params: DieParameters,
        workpiece_shape: ShapeDescription,
        output_dir: Path,
        gap_mm: float = 5.0,
    ) -> dict[str, Path]:
        """
        Generate positioned STL meshes for a station assembly using trimesh.

        No CADQuery required. Positions:
          - die at Z = 0
          - workpiece top aligned with die top face
          - punch above die with gap_mm clearance

        Returns dict of {"punch": path, "die": path, "workpiece": path,
                         "assembly_preview": path}.
        """
        import trimesh
        from app.geometry.numpy_templates import (
            build_punch_mesh,
            build_die_mesh,
            _revolve_profile,
            export_stl,
        )
        from app.geometry.workpiece import _build_profile

        output_dir.mkdir(parents=True, exist_ok=True)

        die_len = die_params.die.working_length
        wp_len = workpiece_shape.overall_length

        punch_mesh = build_punch_mesh(die_params.punch)
        die_mesh = build_die_mesh(die_params.die)
        wp_mesh = _revolve_profile(_build_profile(workpiece_shape), sections=48)

        # Position workpiece so its top aligns with die top face
        wp_offset = max(0.0, die_len - wp_len)
        wp_positioned = wp_mesh.copy()
        wp_positioned.apply_translation([0, 0, wp_offset])

        # Position punch above die entry face
        punch_positioned = punch_mesh.copy()
        punch_positioned.apply_translation([0, 0, die_len + gap_mm])

        result: dict[str, Path] = {}
        result["punch"] = export_stl(punch_positioned, output_dir / "punch.stl")
        result["die"] = export_stl(die_mesh, output_dir / "die.stl")
        result["workpiece"] = export_stl(wp_positioned, output_dir / "workpiece.stl")

        try:
            combined = trimesh.util.concatenate([die_mesh, wp_positioned, punch_positioned])
            result["assembly_preview"] = export_stl(combined, output_dir / "assembly_preview.stl")
        except Exception:
            pass

        return result

    def check_interference(
        self, die_params: DieParameters, tolerance_mm: float = 0.0
    ) -> bool:
        """
        Check that the punch fits inside the die bore with at least clearance_mm on each side.

        Returns True if no interference (punch fits), False if interference detected.
        Simple check: punch OD + 2×clearance ≤ die ID.
        """
        punch_od = die_params.punch.outer_diameter
        die_id = die_params.die.inner_diameter or 0.0
        required_clearance = die_params.clearance_mm

        actual_clearance = (die_id - punch_od) / 2
        return actual_clearance >= (required_clearance - tolerance_mm)
