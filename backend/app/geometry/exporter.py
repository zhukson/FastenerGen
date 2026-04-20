"""
STEP / STL / PNG export for 3D geometry.

Exports CADQuery Workplane or Assembly objects to standard formats:
- STEP: for CAD software and Deform/QForm import
- STL: for web 3D viewer (Three.js)
- PNG: assembly preview renders (via trimesh if pyVista unavailable)
"""

from __future__ import annotations

from pathlib import Path

from app.core.logging import get_logger

logger = get_logger(__name__)

try:
    import cadquery as cq

    CADQUERY_AVAILABLE = True
except ImportError:
    CADQUERY_AVAILABLE = False

try:
    import trimesh

    TRIMESH_AVAILABLE = True
except ImportError:
    TRIMESH_AVAILABLE = False


class GeometryExporter:
    """Export 3D geometry to STEP, STL, and PNG formats."""

    def to_step(self, shape: "cq.Workplane | cq.Assembly", output_path: str | Path) -> Path:
        """
        Export to STEP AP214 format.

        Args:
            shape: CADQuery Workplane or Assembly to export.
            output_path: Destination .step file path.

        Returns:
            Path to the written STEP file.
        """
        if not CADQUERY_AVAILABLE:
            raise ImportError("cadquery is required for STEP export.")

        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        if isinstance(shape, cq.Assembly):
            shape.save(str(path))
        else:
            cq.exporters.export(shape, str(path), cq.exporters.ExportTypes.STEP)

        size = path.stat().st_size
        logger.info("step_exported", path=str(path), bytes=size)
        return path

    def to_stl(
        self,
        shape: "cq.Workplane | cq.Assembly",
        output_path: str | Path,
        tolerance: float = 0.01,
        angular_tolerance: float = 0.1,
    ) -> Path:
        """
        Export to binary STL for web preview.

        Args:
            shape: CADQuery Workplane or Assembly.
            output_path: Destination .stl file path.
            tolerance: Linear tessellation tolerance (mm).
            angular_tolerance: Angular tessellation tolerance (degrees).

        Returns:
            Path to the written STL file.
        """
        if not CADQUERY_AVAILABLE:
            raise ImportError("cadquery is required for STL export.")

        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        if isinstance(shape, cq.Assembly):
            # Export assembly: combine all solids into one STL
            compound = shape.toCompound()
            cq.exporters.export(
                cq.Workplane().add(compound),
                str(path),
                cq.exporters.ExportTypes.STL,
                tolerance=tolerance,
                angularTolerance=angular_tolerance,
            )
        else:
            cq.exporters.export(
                shape,
                str(path),
                cq.exporters.ExportTypes.STL,
                tolerance=tolerance,
                angularTolerance=angular_tolerance,
            )

        size = path.stat().st_size
        logger.info("stl_exported", path=str(path), bytes=size)
        return path

    def to_preview_png(
        self,
        shape: "cq.Workplane | cq.Assembly",
        output_path: str | Path,
        resolution: tuple[int, int] = (1200, 900),
    ) -> Path:
        """
        Render a preview PNG using trimesh.

        For production rendering, replace with PyVista or OCC offline renderer.

        Args:
            shape: CADQuery Workplane or Assembly.
            output_path: Destination .png file path.
            resolution: (width, height) in pixels.

        Returns:
            Path to the written PNG file.
        """
        if not CADQUERY_AVAILABLE:
            raise ImportError("cadquery is required for PNG export.")
        if not TRIMESH_AVAILABLE:
            raise ImportError("trimesh is required for PNG preview export.")

        import io
        import tempfile

        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        # Export to STL first, then load with trimesh for rendering
        with tempfile.NamedTemporaryFile(suffix=".stl", delete=False) as f:
            stl_path = Path(f.name)

        self.to_stl(shape, stl_path)
        mesh = trimesh.load_mesh(str(stl_path))
        stl_path.unlink(missing_ok=True)

        if isinstance(mesh, trimesh.Scene):
            scene = mesh
        else:
            scene = trimesh.scene.scene.Scene(geometry={"part": mesh})

        # isometric-ish view
        scene.set_camera(angles=(0.6, 0, 0.8), distance=max(mesh.bounds[1]) * 3 if hasattr(mesh, "bounds") else 200)

        try:
            png_bytes = scene.save_image(resolution=resolution, visible=True)
            path.write_bytes(png_bytes)
        except Exception as e:
            logger.warning("png_render_failed", error=str(e))
            # Write placeholder 1×1 white PNG
            path.write_bytes(
                b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00"
                b"\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8"
                b"\xff\xff?\x00\x05\xfe\x02\xfe\xdc\xccY\xe7\x00\x00\x00\x00IEND\xaeB`\x82"
            )

        logger.info("png_exported", path=str(path))
        return path
