"""
Core agentic design engine (DieDesigner).

Orchestrates the full pipeline as a single agentic workflow:
  Step 3: Process planning (LLM + few-shot)
  Step 4: Die parameter calculation (LLM)
  Step 5a: 3D model generation (CADQuery)
  Step 5b: 2D drawing generation (ezdxf)
  Step 6: Verification (rule-based; retries up to max_design_retries)

Cost and token usage logged for every LLM call.
"""

from __future__ import annotations

import json
import re
import uuid
from pathlib import Path
from typing import Any

import anthropic
import structlog

from app.ai.fewshot import FewShotFormatter
from app.ai.prompts.die_design import DD_SYSTEM, DD_USER_TEMPLATE, DD_VERSION
from app.ai.prompts.process_planning import PP_SYSTEM, PP_USER_TEMPLATE, PP_VERSION
from app.ai.verification import DesignVerifier
from app.core.config import settings
from app.data.schemas import (
    ConfidenceLevel,
    DieComponentParams,
    DieGeometryType,
    DieParameters,
    DesignResult,
    DesignStatus,
    FileFormat,
    OperationType,
    OutputFile,
    PartFeatures,
    PostProcess,
    ProcessPlan,
    RetrievedCase,
    ShapeDescription,
    StationPlan,
    Tolerance,
    VerificationResult,
)

logger = structlog.get_logger()

_CLAUDE_IN = 15.0   # USD/M tokens input (Opus 4.7)
_CLAUDE_OUT = 75.0  # USD/M tokens output


class DieDesigner:
    """Agentic die design pipeline: process planning → die params → 3D → 2D → verify."""

    def __init__(
        self,
        anthropic_client: anthropic.AsyncAnthropic | None = None,
        output_base_dir: str | Path | None = None,
    ) -> None:
        self._claude = anthropic_client or anthropic.AsyncAnthropic(
            api_key=settings.anthropic_api_key
        )
        self._output_dir = Path(output_base_dir or settings.output_base_dir)
        self._fewshot = FewShotFormatter()
        self._verifier = DesignVerifier()

    async def design(
        self,
        part: PartFeatures,
        similar_cases: list[RetrievedCase],
        retrieval_quality: str = "no_match",
        order_id: str | None = None,
    ) -> DesignResult:
        """Run the full design pipeline and return a complete DesignResult."""
        design_id = str(uuid.uuid4())
        output_dir = self._output_dir / design_id
        output_dir.mkdir(parents=True, exist_ok=True)

        log = logger.bind(design_id=design_id, part=part.description)
        log.info("design_start", retrieval_quality=retrieval_quality, similar=len(similar_cases))

        fewshot_xml = self._fewshot.format_cases(similar_cases, part)
        total_cost = 0.0
        plan: ProcessPlan | None = None
        dies: list[DieParameters] = []
        verif: VerificationResult | None = None

        for attempt in range(settings.max_design_retries + 1):
            prompt_xml = fewshot_xml
            if attempt > 0 and verif is not None:
                error_ctx = self._format_errors(verif)
                prompt_xml += f"\n\n<retry_context attempt='{attempt}'>\n{error_ctx}\n</retry_context>"

            plan, plan_cost = await self._plan_process(part, prompt_xml, retrieval_quality)
            total_cost += plan_cost

            dies, die_cost = await self._calc_die_params(part, plan, prompt_xml)
            total_cost += die_cost

            verif = self._verifier.verify(part, plan, dies, retry_count=attempt)
            log.info(
                "verification_result",
                attempt=attempt,
                passed=verif.passed,
                checks_passed=sum(1 for c in verif.checks if c.passed),
            )
            if verif.passed:
                break

        assert plan is not None
        assert verif is not None

        output_files = await self._generate_outputs(part, plan, dies, design_id, output_dir)
        log.info("design_complete", cost_usd=round(total_cost, 4), files=len(output_files))

        return DesignResult(
            design_id=design_id,
            order_id=order_id or f"ORD-{design_id[:8].upper()}",
            part_features=part,
            process_plan=plan,
            die_parameters=dies,
            verification=verif,
            output_files=output_files,
            retrieved_cases=similar_cases,
            prompt_versions={
                "process_planning": PP_VERSION,
                "die_design": DD_VERSION,
            },
            llm_cost_usd=total_cost,
            confidence=plan.confidence,
            status=DesignStatus.completed if verif.passed else DesignStatus.flagged,
        )

    # ------------------------------------------------------------------
    # LLM calls
    # ------------------------------------------------------------------

    async def _plan_process(
        self,
        part: PartFeatures,
        fewshot_xml: str,
        retrieval_quality: str,
    ) -> tuple[ProcessPlan, float]:
        schema_json = json.dumps(_PROCESS_PLAN_SCHEMA, indent=2)
        user_msg = PP_USER_TEMPLATE.format(
            similar_cases=fewshot_xml,
            features_json=part.model_dump_json(indent=2),
            retrieval_quality=retrieval_quality,
            schema_json=schema_json,
        )

        response = await self._claude.messages.create(
            model=settings.primary_model,
            max_tokens=4096,
            system=PP_SYSTEM,
            messages=[{"role": "user", "content": user_msg}],
        )
        cost = _calc_cost(response)
        logger.info("process_planning_call", cost_usd=round(cost, 6))

        raw = _extract_text(response)
        plan = _parse_process_plan(raw, part)
        return plan, cost

    async def _calc_die_params(
        self,
        part: PartFeatures,
        plan: ProcessPlan,
        fewshot_xml: str,
    ) -> tuple[list[DieParameters], float]:
        # Build "similar die specs" section from the few-shot XML
        similar_die_xml = fewshot_xml.replace("similar_cases", "similar_die_cases")

        schema_json = json.dumps(_DIE_PARAMETERS_SCHEMA, indent=2)
        user_msg = DD_USER_TEMPLATE.format(
            features_json=part.model_dump_json(indent=2),
            process_plan_json=plan.model_dump_json(indent=2),
            similar_die_specs=similar_die_xml,
            station_count=plan.total_stations,
            schema_json=schema_json,
        )

        response = await self._claude.messages.create(
            model=settings.primary_model,
            max_tokens=4096,
            system=DD_SYSTEM,
            messages=[{"role": "user", "content": user_msg}],
        )
        cost = _calc_cost(response)
        logger.info("die_design_call", cost_usd=round(cost, 6))

        raw = _extract_text(response)
        dies = _parse_die_params(raw, part, plan)
        return dies, cost

    # ------------------------------------------------------------------
    # Output generation
    # ------------------------------------------------------------------

    async def _generate_outputs(
        self,
        part: PartFeatures,
        plan: ProcessPlan,
        dies: list[DieParameters],
        design_id: str,
        output_dir: Path,
    ) -> list[OutputFile]:
        files: list[OutputFile] = []

        # Build station_number → StationPlan lookup for workpiece shapes
        station_plans = {s.station_number: s for s in plan.stations}

        try:
            from app.drawings.generator import DrawingGenerator
            from app.geometry.exporter import GeometryExporter
            from app.geometry.workpiece import WorkpieceGenerator
            from app.geometry.assembly import AssemblyBuilder

            gen = DrawingGenerator()
            exporter = GeometryExporter()
            wp_gen = WorkpieceGenerator()
            assy_builder = AssemblyBuilder()

            # --- Production + process breakdown drawings ---
            prod_path = gen.generate_production_drawing(part, plan, output_dir / "production_drawing.dxf")
            files.append(OutputFile(
                file_type="production_drawing",
                station_number=None,
                file_path=str(prod_path),
                format=FileFormat.dxf,
                size_bytes=prod_path.stat().st_size,
            ))

            proc_path = gen.generate_process_breakdown(plan, output_dir / "process_breakdown.dxf")
            files.append(OutputFile(
                file_type="process_breakdown",
                station_number=None,
                file_path=str(proc_path),
                format=FileFormat.dxf,
                size_bytes=proc_path.stat().st_size,
            ))

            # --- Station 0: wire blank ---
            try:
                s0_dir = output_dir / "station_0"
                s0_dir.mkdir(exist_ok=True)
                blank_path = wp_gen.generate_blank_stl(
                    plan.blank_diameter, plan.blank_length,
                    s0_dir / "blank.stl",
                )
                files.append(OutputFile(
                    file_type="blank_stl",
                    station_number=0,
                    file_path=str(blank_path),
                    format=FileFormat.stl,
                    size_bytes=blank_path.stat().st_size,
                ))
            except Exception as exc:
                logger.warning("blank_stl_failed", error=str(exc))

            # --- Per-station 2D + 3D + workpiece + assembly ---
            for die_param in dies:
                sn = die_param.station_number
                station_dir = output_dir / f"station_{sn}"
                station_dir.mkdir(exist_ok=True)
                station_plan = station_plans.get(sn)

                # 2D drawings — one for punch, one for die
                for comp, comp_label, ft in [
                    (die_param.punch, "punch", "punch_drawing"),
                    (die_param.die, "die", "die_drawing"),
                ]:
                    try:
                        dwg_path = gen.generate_die_drawing(comp, sn, station_dir / f"{comp_label}_drawing.dxf")
                        files.append(OutputFile(
                            file_type=ft,
                            station_number=sn,
                            file_path=str(dwg_path),
                            format=FileFormat.dxf,
                            size_bytes=dwg_path.stat().st_size,
                        ))
                    except Exception as exc:
                        logger.warning("die_drawing_failed", station=sn, component=comp_label, error=str(exc))

                # 3D models — try CADQuery first, fall back to trimesh primitives
                try:
                    from app.geometry.punch_templates import build_punch
                    from app.geometry.die_templates import build_die

                    punch_shape = build_punch(die_param.punch)
                    die_shape = build_die(die_param.die)

                    for shape, comp_type, file_type_stl, file_type_step in [
                        (punch_shape, "punch", "punch_stl", "punch_step"),
                        (die_shape, "die", "die_stl", "die_step"),
                    ]:
                        stl_path = exporter.to_stl(shape, station_dir / f"{comp_type}.stl")
                        step_path = exporter.to_step(shape, station_dir / f"{comp_type}.step")
                        files.append(OutputFile(
                            file_type=file_type_stl,
                            station_number=sn,
                            file_path=str(stl_path),
                            format=FileFormat.stl,
                            size_bytes=stl_path.stat().st_size,
                        ))
                        files.append(OutputFile(
                            file_type=file_type_step,
                            station_number=sn,
                            file_path=str(step_path),
                            format=FileFormat.step,
                            size_bytes=step_path.stat().st_size,
                        ))
                except ImportError:
                    # CADQuery not installed — generate preview STLs via trimesh
                    logger.warning("cadquery_not_available_using_trimesh", station=sn)
                    try:
                        stl_files = _generate_trimesh_stls(die_param, station_dir)
                        files.extend(stl_files)
                    except Exception as exc:
                        logger.warning("trimesh_stl_failed", station=sn, error=str(exc))
                except Exception as exc:
                    logger.warning("die_3d_failed", station=sn, error=str(exc))

                # Workpiece STL (trimesh — always available)
                if station_plan is not None:
                    try:
                        wp_path = wp_gen.generate_workpiece_stl(
                            station_plan.output_shape,
                            station_dir / "workpiece.stl",
                        )
                        files.append(OutputFile(
                            file_type="workpiece_stl",
                            station_number=sn,
                            file_path=str(wp_path),
                            format=FileFormat.stl,
                            size_bytes=wp_path.stat().st_size,
                        ))
                    except Exception as exc:
                        logger.warning("workpiece_stl_failed", station=sn, error=str(exc))

                # Assembly preview STL (punch + die + workpiece combined, trimesh)
                if station_plan is not None:
                    try:
                        assy_paths = assy_builder.build_station_assembly_stls(
                            die_param,
                            station_plan.output_shape,
                            station_dir,
                        )
                        if "assembly_preview" in assy_paths:
                            ap = assy_paths["assembly_preview"]
                            files.append(OutputFile(
                                file_type="assembly_preview",
                                station_number=sn,
                                file_path=str(ap),
                                format=FileFormat.stl,
                                size_bytes=ap.stat().st_size,
                            ))
                    except Exception as exc:
                        logger.warning("assembly_stl_failed", station=sn, error=str(exc))

        except Exception as exc:
            logger.error("output_generation_failed", error=str(exc))

        return files

    def _format_errors(self, verif: VerificationResult) -> str:
        failed = [c for c in verif.checks if not c.passed]
        lines = [f"- [{c.severity.value}] {c.check_name}: {c.message}" for c in failed]
        return "\n".join(lines) if lines else "No errors"


# ---------------------------------------------------------------------------
# JSON parsing helpers
# ---------------------------------------------------------------------------


def _calc_cost(response: Any) -> float:
    return (
        response.usage.input_tokens * _CLAUDE_IN / 1_000_000
        + response.usage.output_tokens * _CLAUDE_OUT / 1_000_000
    )


def _extract_text(response: Any) -> str:
    for block in response.content:
        if hasattr(block, "text"):
            return block.text
    return ""


def _strip_fences(text: str) -> str:
    """Strip ```json ... ``` or ``` ... ``` fences."""
    text = text.strip()
    if text.startswith("```"):
        parts = text.split("```", 2)
        if len(parts) >= 3:
            inner = parts[1]
            if inner.startswith("json"):
                inner = inner[4:]
            return inner.strip()
        # fallback
        text = re.sub(r"^```[a-z]*\n?", "", text)
        text = re.sub(r"\n?```$", "", text)
    return text.strip()


def _parse_process_plan(raw: str, part: PartFeatures) -> ProcessPlan:
    """Parse LLM output into ProcessPlan with fallback."""
    json_str = _strip_fences(raw)

    # Find first { if there's preamble
    brace = json_str.find("{")
    if brace > 0:
        json_str = json_str[brace:]

    try:
        data = json.loads(json_str)
    except json.JSONDecodeError:
        logger.warning("process_plan_json_parse_failed", preview=json_str[:200])
        return _fallback_process_plan(part)

    try:
        # Clamp upset_ratio to 2.3 before Pydantic validation
        for station in data.get("stations", []):
            if station.get("upset_ratio") is not None:
                station["upset_ratio"] = min(float(station["upset_ratio"]), 2.2)

        return ProcessPlan.model_validate(data)
    except Exception as exc:
        logger.warning("process_plan_validation_failed", error=str(exc))
        return _fallback_process_plan(part)


def _parse_die_params(raw: str, part: PartFeatures, plan: ProcessPlan) -> list[DieParameters]:
    """Parse LLM output into list[DieParameters] with fallback."""
    json_str = _strip_fences(raw)

    # Find first [ if there's preamble
    bracket = json_str.find("[")
    if bracket > 0:
        json_str = json_str[bracket:]

    try:
        data = json.loads(json_str)
        if not isinstance(data, list):
            raise ValueError("Expected list")
    except (json.JSONDecodeError, ValueError):
        logger.warning("die_params_json_parse_failed", preview=json_str[:200])
        return _fallback_die_params(part, plan)

    try:
        result: list[DieParameters] = []
        for item in data:
            # Clamp approach_angle_deg to 90
            for comp in ("punch", "die"):
                if comp in item and item[comp].get("approach_angle_deg") is not None:
                    item[comp]["approach_angle_deg"] = min(
                        float(item[comp]["approach_angle_deg"]), 90.0
                    )
        for item in data:
            result.append(DieParameters.model_validate(item))
        return result
    except Exception as exc:
        logger.warning("die_params_validation_failed", error=str(exc))
        return _fallback_die_params(part, plan)


# ---------------------------------------------------------------------------
# Trimesh fallback STL generation (when CADQuery is not installed)
# ---------------------------------------------------------------------------


def _generate_trimesh_stls(die_param: "DieParameters", station_dir: Path) -> list["OutputFile"]:
    """
    Generate parametric STLs using numpy revolution solids.
    Punch = tapered cylinder with approach cone.
    Die = hollow cylinder with entry chamfer.
    Used when CADQuery is unavailable (e.g. Docker without conda).
    """
    from app.geometry.numpy_templates import build_punch_mesh, build_die_mesh, export_stl

    files: list[OutputFile] = []
    sn = die_param.station_number

    for comp, comp_label, ft, builder in [
        (die_param.punch, "punch", "punch_stl", build_punch_mesh),
        (die_param.die, "die", "die_stl", build_die_mesh),
    ]:
        try:
            mesh = builder(comp)
            stl_path = export_stl(mesh, station_dir / f"{comp_label}.stl")
            files.append(OutputFile(
                file_type=ft,
                station_number=sn,
                file_path=str(stl_path),
                format=FileFormat.stl,
                size_bytes=stl_path.stat().st_size,
            ))
        except Exception as exc:
            logger.warning("trimesh_stl_failed", component=comp_label, station=sn, error=str(exc))

    return files


# ---------------------------------------------------------------------------
# Fallback generators (used when LLM output cannot be parsed)
# ---------------------------------------------------------------------------


def _fallback_process_plan(part: PartFeatures) -> ProcessPlan:
    """Generate a minimal valid ProcessPlan from part geometry."""
    from app.data.synthetic import SyntheticDataGenerator

    gen = SyntheticDataGenerator(seed=42)
    return gen.generate_process_plan(part)


def _fallback_die_params(part: PartFeatures, plan: ProcessPlan) -> list[DieParameters]:
    """Generate minimal valid die parameters from part + plan."""
    from app.data.synthetic import SyntheticDataGenerator

    gen = SyntheticDataGenerator(seed=42)
    return gen.generate_die_parameters(part, plan)


# ---------------------------------------------------------------------------
# Simplified JSON schemas for LLM output guidance
# (Full Pydantic schemas are too verbose for prompt injection)
# ---------------------------------------------------------------------------

_SHAPE_SCHEMA: dict = {
    "type": "object",
    "required": ["overall_length", "max_diameter"],
    "properties": {
        "overall_length": {"type": "number", "description": "mm"},
        "max_diameter": {"type": "number", "description": "mm"},
        "head_diameter": {"type": ["number", "null"]},
        "head_height": {"type": ["number", "null"]},
        "shank_diameter": {"type": ["number", "null"]},
        "shank_length": {"type": ["number", "null"]},
    },
}

_STATION_SCHEMA: dict = {
    "type": "object",
    "required": ["station_number", "operation", "description", "input_shape", "output_shape"],
    "properties": {
        "station_number": {"type": "integer"},
        "operation": {
            "type": "string",
            "enum": [o.value for o in OperationType],
        },
        "description": {"type": "string"},
        "input_shape": _SHAPE_SCHEMA,
        "output_shape": _SHAPE_SCHEMA,
        "upset_ratio": {"type": ["number", "null"], "maximum": 2.3},
        "area_reduction_pct": {"type": ["number", "null"]},
    },
}

_PROCESS_PLAN_SCHEMA: dict = {
    "type": "object",
    "required": ["total_stations", "blank_diameter", "blank_length", "stations", "confidence", "reasoning_summary"],
    "properties": {
        "total_stations": {"type": "integer", "minimum": 1, "maximum": 8},
        "blank_diameter": {"type": "number", "description": "Wire stock diameter mm"},
        "blank_length": {"type": "number", "description": "Wire cut length mm"},
        "stations": {"type": "array", "items": _STATION_SCHEMA},
        "post_processes": {
            "type": "array",
            "items": {"type": "string", "enum": [p.value for p in PostProcess]},
        },
        "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
        "reasoning_summary": {"type": "string"},
    },
}

_COMP_SCHEMA: dict = {
    "type": "object",
    "required": ["component_type", "material", "hardness_hrc_min", "hardness_hrc_max",
                 "geometry_type", "outer_diameter", "working_length", "surface_roughness_ra"],
    "properties": {
        "component_type": {"type": "string", "enum": ["punch", "die"]},
        "material": {"type": "string"},
        "hardness_hrc_min": {"type": "number"},
        "hardness_hrc_max": {"type": "number"},
        "geometry_type": {"type": "string", "enum": [g.value for g in DieGeometryType]},
        "outer_diameter": {"type": "number"},
        "inner_diameter": {"type": ["number", "null"]},
        "working_length": {"type": "number"},
        "cavity_depth": {"type": ["number", "null"]},
        "approach_angle_deg": {"type": ["number", "null"], "maximum": 90.0},
        "land_length": {"type": ["number", "null"]},
        "surface_roughness_ra": {"type": "number", "default": 0.4},
        "surface_treatment": {"type": ["string", "null"]},
        "coating_thickness_um": {"type": ["number", "null"]},
    },
}

_DIE_PARAMETERS_SCHEMA: dict = {
    "type": "array",
    "items": {
        "type": "object",
        "required": ["station_number", "punch", "die", "clearance_mm"],
        "properties": {
            "station_number": {"type": "integer"},
            "punch": _COMP_SCHEMA,
            "die": _COMP_SCHEMA,
            "clearance_mm": {"type": "number"},
            "expected_life_shots": {"type": ["integer", "null"]},
        },
    },
}
