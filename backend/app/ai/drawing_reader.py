"""
Multi-modal drawing understanding via Claude Opus 4.7 Vision API.

Step 1 of the pipeline: reads a product drawing (PDF/DWG/JPG/PNG) and
extracts all features as a validated PartFeatures JSON.

Self-consistency: runs extraction 3× and returns the majority-vote result.
Handles Chinese+English text, standard dimension notation, tolerance
expressions, material codes (10B21, SCM435, SUS304), and Chinese process
annotations (冷镦, 搓花, 搓牙).

Prompt version: DU_V1_0_0
"""

from __future__ import annotations

import base64
import json
import re
from pathlib import Path

import anthropic

from app.core.config import settings
from app.core.logging import get_logger
from app.data.schemas import PartFeatures

logger = get_logger(__name__)

# Prompt version tracked with every generated output
PROMPT_VERSION = "DU_V1_0_0"

_SYSTEM_PROMPT = """You are an expert mechanical engineer specializing in cold-heading fastener manufacturing.
You will analyze engineering drawings (product drawings for cold-heading fasteners like bolts and screws)
and extract ALL features into a structured JSON format.

The drawings may contain Chinese or English text, or both. Common Chinese terms you may encounter:
- 材料 = material
- 热处理 = heat treatment
- 表面处理 = surface treatment
- 硬度 = hardness
- 螺纹 = thread
- 冷镦 = cold heading
- 搓花 = knurling
- 搓牙 = thread rolling
- 三价蓝白锌 = trivalent blue-white zinc (plating)
- 达克罗 = Dacromet coating
- 磷化 = phosphating

Dimensional notation:
- ⌀ or φ = diameter
- Tolerances: ±0.15, +0.05/-0.10, h6, g6, 6g, etc.
- M6-1.0P = M6 thread with 1.0mm pitch
- HRC 22-32 = Rockwell hardness range

Material codes:
- 10B21: boron steel (most common for 8.8 grade)
- SCM435: chrome-moly steel (for 10.9 grade)
- SUS304: stainless steel 304
- C1008, C1010: low carbon steel

Strength grades (强度等级): 4.8, 5.8, 6.8, 8.8, 10.9, 12.9

CRITICAL: Return ONLY valid JSON matching the schema below. No explanation, no markdown fences.
If a field is unclear or missing from the drawing, use null for optional fields.
For material_grade use "10B21" as default if not specified.
For strength_grade use "8.8" as default if not specified.
Never guess dimensions — only extract what is clearly visible in the drawing.

Output schema (strict JSON, all dimensions in mm):
{
  "part_number": string or null,
  "description": string,
  "overall_length": number,
  "head": {
    "type": "flat"|"hex"|"button"|"pan"|"socket"|"truss"|"flange"|"oval",
    "diameter": number,
    "height": number,
    "chamfer_angle_deg": number or null,
    "chamfer_diameter": number or null,
    "flange": boolean,
    "flange_diameter": number or null,
    "drive_type": "cross"|"hex_socket"|"torx"|"slotted"|"none",
    "drive_size": number or null,
    "underhead_radius": number or null
  },
  "shank": {
    "diameter": number,
    "length": number
  },
  "thread": {
    "spec": string,
    "nominal_diameter": number,
    "pitch": number,
    "length": number,
    "thread_class": string,
    "thread_type": "metric"|"unified"|"bsp"|"acme",
    "is_full_length": boolean
  },
  "tail": null or {
    "type": "flat"|"pointed"|"dog_point"|"cone",
    "length": number or null,
    "angle_deg": number or null
  },
  "material_grade": string,
  "strength_grade": string,
  "hardness_min_hv": number or null,
  "hardness_max_hv": number or null,
  "core_hardness_min_hrc": number or null,
  "core_hardness_max_hrc": number or null,
  "surface_treatment": string or null,
  "standard": string or null,
  "notes": [string]
}"""

_USER_TEMPLATE = """Analyze this cold-heading fastener product drawing and extract all features.

The drawing shows part: {hint}

Extract every dimension, tolerance, and specification visible in the drawing.
Pay special attention to:
1. All diameter dimensions (shank, head, thread)
2. All length dimensions (total, shank, thread, head height)
3. Thread specification with pitch and tolerance class
4. Material code and strength grade
5. Surface treatment and hardness requirements
6. Any Chinese or English annotations

Return ONLY valid JSON matching the schema in the system prompt."""


class DrawingReader:
    """Extract structured PartFeatures from a product drawing using Claude Vision."""

    def __init__(self, client: anthropic.AsyncAnthropic | None = None) -> None:
        self._client = client or anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    async def read_drawing(
        self,
        file_path: str | Path,
        self_consistency_runs: int = 3,
        hint: str = "",
    ) -> PartFeatures:
        """
        Extract PartFeatures from a product drawing.

        Converts the drawing to base64 image(s), sends to Claude Opus 4.7
        Vision API, parses JSON response into PartFeatures. Runs
        `self_consistency_runs` times and returns the majority-vote result.

        Args:
            file_path: Path to PDF, DWG, DXF, JPG, or PNG file.
            self_consistency_runs: Number of Claude calls for self-consistency.
            hint: Optional hint about the part (e.g. "M6×33 flat head bolt").

        Returns:
            Validated PartFeatures model.
        """
        path = Path(file_path)
        images = await self._to_images(path)

        results: list[PartFeatures] = []
        errors: list[str] = []

        for run_idx in range(self_consistency_runs):
            try:
                features = await self._extract_once(images, hint=hint, run=run_idx)
                results.append(features)
                logger.info(
                    "drawing_extraction_run",
                    run=run_idx + 1,
                    part_number=features.part_number,
                    overall_length=features.overall_length,
                )
            except Exception as e:
                errors.append(str(e))
                logger.warning("drawing_extraction_run_failed", run=run_idx + 1, error=str(e))

        if not results:
            raise RuntimeError(
                f"All {self_consistency_runs} extraction runs failed: {errors}"
            )

        # Majority vote: use the most common overall_length as tiebreaker
        # (For 3 runs, pick the first result that matches the most common value)
        chosen = self._majority_vote(results)
        logger.info(
            "drawing_extraction_complete",
            file=path.name,
            runs_succeeded=len(results),
            chosen_length=chosen.overall_length,
            prompt_version=PROMPT_VERSION,
        )
        return chosen

    async def _extract_once(
        self, images: list[dict[str, str]], hint: str, run: int
    ) -> PartFeatures:
        """Single Claude Vision extraction call."""
        content: list[dict[str, object]] = []

        for img in images[:4]:  # Cap at 4 images to limit tokens
            content.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": img["media_type"],
                    "data": img["data"],
                },
            })

        content.append({
            "type": "text",
            "text": _USER_TEMPLATE.format(hint=hint or "unknown"),
        })

        response = await self._client.messages.create(
            model=settings.primary_model,
            max_tokens=4096,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": content}],
        )

        raw_text = response.content[0].text if response.content else ""

        # Log cost
        input_tokens = response.usage.input_tokens
        output_tokens = response.usage.output_tokens
        cost_usd = input_tokens * 15e-6 + output_tokens * 75e-6  # Opus 4.7 pricing
        logger.info(
            "llm_call",
            step="drawing_understanding",
            run=run,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=round(cost_usd, 4),
            prompt_version=PROMPT_VERSION,
        )

        return self._parse_response(raw_text)

    def _parse_response(self, raw: str) -> PartFeatures:
        """Parse Claude's JSON response into a validated PartFeatures model."""
        # Strip markdown fences if present (Claude sometimes adds them)
        cleaned = re.sub(r"```(?:json)?\s*", "", raw).strip().rstrip("```").strip()

        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError as e:
            # Try to extract JSON object from surrounding text
            match = re.search(r"\{.*\}", cleaned, re.DOTALL)
            if match:
                data = json.loads(match.group())
            else:
                raise ValueError(f"Claude returned non-JSON response: {raw[:200]}") from e

        # Ensure required string fields have defaults
        data.setdefault("description", data.get("part_number", "Unknown Part"))
        data.setdefault("notes", [])

        return PartFeatures(**data)

    def _majority_vote(self, results: list[PartFeatures]) -> PartFeatures:
        """
        Select the 'best' result from multiple extraction runs.

        Strategy:
        1. Group by overall_length (rounded to 0.5mm)
        2. Pick the group with the most members
        3. Within that group, prefer the result with most non-null fields
        """
        if len(results) == 1:
            return results[0]

        # Group by rounded overall_length
        groups: dict[float, list[PartFeatures]] = {}
        for r in results:
            key = round(r.overall_length * 2) / 2  # round to nearest 0.5
            groups.setdefault(key, []).append(r)

        # Pick largest group
        best_group = max(groups.values(), key=len)

        # Within group, pick result with most non-null top-level fields
        def non_null_count(f: PartFeatures) -> int:
            return sum(
                1
                for v in f.model_dump().values()
                if v is not None and v != [] and v != {}
            )

        return max(best_group, key=non_null_count)

    async def _to_images(self, path: Path) -> list[dict[str, str]]:
        """
        Convert a drawing file to base64-encoded image(s).

        Handles: JPG, PNG (direct), DXF (ezdxf render), PDF (pdftoppm or fallback).
        """
        suffix = path.suffix.lower()

        if suffix in (".jpg", ".jpeg"):
            return [{"media_type": "image/jpeg", "data": self._encode_file(path)}]

        if suffix == ".png":
            return [{"media_type": "image/png", "data": self._encode_file(path)}]

        if suffix in (".dxf", ".dwg"):
            return await self._dxf_to_images(path)

        if suffix == ".pdf":
            return await self._pdf_to_images(path)

        raise ValueError(f"Unsupported file format: {suffix}")

    def _encode_file(self, path: Path) -> str:
        return base64.standard_b64encode(path.read_bytes()).decode()

    async def _dxf_to_images(self, path: Path) -> list[dict[str, str]]:
        """Render a DXF file to PNG using ezdxf's matplotlib backend."""
        try:
            import ezdxf
            from ezdxf.addons.drawing import RenderContext, Frontend
            from ezdxf.addons.drawing.matplotlib import MatplotlibBackend
            import matplotlib.pyplot as plt
            import io

            doc = ezdxf.readfile(str(path))
            msp = doc.modelspace()
            fig = plt.figure()
            ax = fig.add_axes([0, 0, 1, 1])
            ctx = RenderContext(doc)
            out = MatplotlibBackend(ax)
            Frontend(ctx, out).draw_layout(msp)

            buf = io.BytesIO()
            fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
            plt.close(fig)
            buf.seek(0)
            data = base64.standard_b64encode(buf.read()).decode()
            return [{"media_type": "image/png", "data": data}]
        except Exception as e:
            logger.warning("dxf_render_failed", error=str(e), path=str(path))
            raise

    async def _pdf_to_images(self, path: Path) -> list[dict[str, str]]:
        """Convert PDF pages to PNG images using pdf2image or pypdfium2."""
        try:
            import pypdfium2 as pdfium
            import io

            pdf = pdfium.PdfDocument(str(path))
            images = []
            for i in range(min(len(pdf), 4)):  # max 4 pages
                page = pdf[i]
                bitmap = page.render(scale=1.5)  # ~110 DPI — good for text, under 5MB
                pil_image = bitmap.to_pil()
                buf = io.BytesIO()
                # JPEG keeps size well under 5MB; quality=90 preserves dimension text
                pil_image.convert("RGB").save(buf, format="JPEG", quality=90, optimize=True)
                if buf.tell() > 4 * 1024 * 1024:  # if still >4MB, drop quality
                    buf = io.BytesIO()
                    pil_image.convert("RGB").save(buf, format="JPEG", quality=70, optimize=True)
                buf.seek(0)
                data = base64.standard_b64encode(buf.read()).decode()
                images.append({"media_type": "image/jpeg", "data": data})
            return images
        except ImportError:
            pass

        # Fallback: try pdf2image
        try:
            from pdf2image import convert_from_path
            import io

            pages = convert_from_path(str(path), dpi=150, first_page=1, last_page=4)
            images = []
            for page in pages:
                buf = io.BytesIO()
                page.save(buf, format="PNG")
                buf.seek(0)
                data = base64.standard_b64encode(buf.read()).decode()
                images.append({"media_type": "image/png", "data": data})
            return images
        except ImportError:
            pass

        raise RuntimeError(
            "Cannot convert PDF to images. Install pypdfium2 or pdf2image+poppler:\n"
            "  pip install pypdfium2\n"
            "  # or: pip install pdf2image && brew install poppler"
        )
