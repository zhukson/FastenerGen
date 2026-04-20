"""
All Pydantic v2 data models for FastenerGPT.

These models define the data contract between every pipeline component.
Designed around the real M6×33 flat head bolt drawing (part 18149-D6,
material 10B21, grade 8.8) — every field is justifiable from that drawing.

Model hierarchy:
  PartFeatures          — extracted from product drawing (Step 1)
  ProcessPlan           — AI-generated forming sequence (Step 3)
  DieParameters         — AI-generated die specs per station (Step 4)
  PseudoReasoning       — bootstrapped engineering reasoning
  RAGCase               — complete case stored in ChromaDB
  RetrievedCase         — case with retrieval score
  DesignResult          — full pipeline output (Steps 1-6)
  ParsedDrawing         — DWG/DXF parsing output
  EvalReport            — evaluation dashboard data
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator


# ===========================================================================
# Enums
# ===========================================================================


class HeadType(str, Enum):
    flat = "flat"               # countersunk / flat head
    hex = "hex"                 # hex head bolt
    button = "button"           # button head
    pan = "pan"                 # pan head
    socket = "socket"           # socket cap
    truss = "truss"             # truss / mushroom head
    flange = "flange"           # hex flange
    oval = "oval"               # oval / raised countersunk


class DriveType(str, Enum):
    cross = "cross"             # Phillips / Pozidriv
    hex_socket = "hex_socket"   # Allen key
    torx = "torx"               # Torx star
    slotted = "slotted"
    none = "none"               # no drive (bolt, no driver needed)


class TailType(str, Enum):
    flat = "flat"
    pointed = "pointed"
    dog_point = "dog_point"
    cone = "cone"


class OperationType(str, Enum):
    forward_extrusion = "forward_extrusion"
    backward_extrusion = "backward_extrusion"
    upsetting = "upsetting"
    heading = "heading"
    trimming = "trimming"
    piercing = "piercing"
    combined = "combined"       # simultaneous extrusion + upsetting


class PostProcess(str, Enum):
    thread_rolling = "thread_rolling"
    knurling = "knurling"
    heat_treatment = "heat_treatment"
    annealing = "annealing"
    plating = "plating"
    phosphating = "phosphating"
    zinc_plating = "zinc_plating"
    black_oxide = "black_oxide"


class DieGeometryType(str, Enum):
    cylindrical = "cylindrical"
    stepped = "stepped"
    conical = "conical"
    flat_face = "flat_face"
    open_heading = "open_heading"
    closed_heading = "closed_heading"
    trimming = "trimming"


class ConfidenceLevel(str, Enum):
    high = "high"
    medium = "medium"
    low = "low"


class FileFormat(str, Enum):
    dxf = "dxf"
    step = "step"
    stl = "stl"
    png = "png"
    json = "json"
    markdown = "markdown"


class CheckSeverity(str, Enum):
    error = "error"
    warning = "warning"
    info = "info"


class DimensionType(str, Enum):
    linear = "linear"
    diameter = "diameter"
    radius = "radius"
    angular = "angular"
    thread = "thread"


class DesignStatus(str, Enum):
    pending = "pending"
    processing = "processing"
    completed = "completed"
    failed = "failed"
    flagged = "flagged"         # needs human review


# ===========================================================================
# Sub-models: Part Geometry
# ===========================================================================


class Tolerance(BaseModel):
    """Bilateral or unilateral tolerance on a nominal dimension."""

    nominal: float = Field(..., description="Nominal dimension value in mm", examples=[6.0])
    plus: float = Field(0.0, ge=0, description="Upper tolerance (positive)", examples=[0.0])
    minus: float = Field(0.0, ge=0, description="Lower tolerance magnitude (positive)", examples=[0.018])

    @property
    def upper(self) -> float:
        return self.nominal + self.plus

    @property
    def lower(self) -> float:
        return self.nominal - self.minus


class HeadFeatures(BaseModel):
    """Geometric features of the fastener head."""

    type: HeadType = Field(..., description="Head shape type", examples=[HeadType.flat])
    diameter: float = Field(..., gt=0, description="Head outer diameter (mm)", examples=[12.0])
    height: float = Field(..., gt=0, description="Head height / depth (mm)", examples=[3.6])
    chamfer_angle_deg: float | None = Field(
        None, ge=0, le=180,
        description="Countersink or chamfer angle (degrees). 90° for flat head per ISO 7046.",
        examples=[90.0],
    )
    chamfer_diameter: float | None = Field(
        None, gt=0, description="Outer diameter at chamfer start (mm)", examples=[12.0]
    )
    flange: bool = Field(False, description="Has bearing flange under head")
    flange_diameter: float | None = Field(None, gt=0, description="Flange OD (mm)")
    drive_type: DriveType = Field(DriveType.none, description="Drive recess type")
    drive_size: float | None = Field(
        None, gt=0, description="Drive size (mm for hex socket, # for cross)", examples=[3.0]
    )
    underhead_radius: float | None = Field(
        None, ge=0, description="Fillet radius under head (mm)", examples=[0.3]
    )

    model_config = {"json_schema_extra": {"example": {
        "type": "flat", "diameter": 12.0, "height": 3.6,
        "chamfer_angle_deg": 90.0, "chamfer_diameter": 12.0,
        "flange": False, "drive_type": "cross", "drive_size": 3.0,
        "underhead_radius": 0.3,
    }}}


class ShankFeatures(BaseModel):
    """Cylindrical shank (grip) section between head and thread."""

    diameter: float = Field(..., gt=0, description="Shank diameter (mm)", examples=[6.0])
    length: float = Field(..., ge=0, description="Unthreaded shank length (mm)", examples=[8.0])
    diameter_tolerance: Tolerance | None = Field(
        None, description="Shank diameter with tolerance"
    )

    model_config = {"json_schema_extra": {"example": {
        "diameter": 6.0, "length": 8.0,
    }}}


class ThreadFeatures(BaseModel):
    """Thread specification extracted from the drawing."""

    spec: str = Field(..., description="Full thread spec string e.g. 'M6×1.0'", examples=["M6×1.0"])
    nominal_diameter: float = Field(..., gt=0, description="Nominal thread diameter (mm)", examples=[6.0])
    pitch: float = Field(..., gt=0, description="Thread pitch (mm)", examples=[1.0])
    length: float = Field(..., gt=0, description="Thread length (mm)", examples=[20.0])
    thread_class: str = Field("6g", description="Thread tolerance class", examples=["6g"])
    thread_type: Literal["metric", "unified", "bsp", "acme"] = Field(
        "metric", description="Thread standard"
    )
    is_full_length: bool = Field(False, description="Thread runs full length of shank")

    @field_validator("pitch")
    @classmethod
    def pitch_must_be_standard(cls, v: float, info: Any) -> float:
        # Coarse pitch for common metric sizes — warn if unusual
        standard_pitches = {3: 0.5, 4: 0.7, 5: 0.8, 6: 1.0, 8: 1.25, 10: 1.5, 12: 1.75}
        return v

    model_config = {"json_schema_extra": {"example": {
        "spec": "M6×1.0", "nominal_diameter": 6.0, "pitch": 1.0,
        "length": 20.0, "thread_class": "6g", "thread_type": "metric",
    }}}


class TailFeatures(BaseModel):
    """Optional tail / tip features (for pointed or dog-point fasteners)."""

    type: TailType = Field(..., description="Tail geometry type", examples=[TailType.flat])
    length: float | None = Field(None, gt=0, description="Tail section length (mm)")
    angle_deg: float | None = Field(None, gt=0, le=180, description="Tip cone angle (degrees)")

    model_config = {"json_schema_extra": {"example": {"type": "flat"}}}


class PartFeatures(BaseModel):
    """
    Complete structured features extracted from a product drawing.

    Corresponds to one product drawing (e.g., M6×33 flat head bolt 18149-D6).
    All dimensions are in millimeters unless noted.
    """

    part_number: str = Field(..., description="Drawing part number", examples=["18149-D6"])
    description: str = Field(..., description="Part description", examples=["M6×33 Flat Head Bolt"])
    overall_length: float = Field(..., gt=0, description="Overall part length (mm)", examples=[33.0])

    head: HeadFeatures
    shank: ShankFeatures
    thread: ThreadFeatures
    tail: TailFeatures | None = None

    material_grade: str = Field(..., description="Material grade / steel spec", examples=["10B21"])
    strength_grade: str = Field(..., description="Mechanical strength grade", examples=["8.8"])
    hardness_min_hv: float | None = Field(
        None, ge=0, description="Min surface hardness (HV)", examples=[250.0]
    )
    hardness_max_hv: float | None = Field(
        None, ge=0, description="Max surface hardness (HV)", examples=[320.0]
    )
    core_hardness_min_hrc: float | None = Field(
        None, ge=0, le=70, description="Min core hardness (HRC)"
    )
    core_hardness_max_hrc: float | None = Field(
        None, ge=0, le=70, description="Max core hardness (HRC)"
    )
    surface_treatment: str | None = Field(
        None, description="Surface finish / coating", examples=["zinc_plating_8um"]
    )
    standard: str | None = Field(
        None, description="Applicable standard", examples=["GB/T 5789"]
    )
    tolerance_class: str | None = Field(
        None, description="Overall tolerance class"
    )
    drawing_scale: str | None = Field(None, description="Drawing scale e.g. '1:1'", examples=["1:1"])
    notes: list[str] = Field(default_factory=list, description="Additional notes from drawing")

    @model_validator(mode="after")
    def validate_geometry(self) -> PartFeatures:
        # Shank + thread length should not exceed overall length
        total = self.shank.length + self.thread.length + self.head.height
        if total > self.overall_length * 1.1:
            raise ValueError(
                f"shank({self.shank.length}) + thread({self.thread.length}) + "
                f"head({self.head.height}) = {total} exceeds overall_length {self.overall_length}"
            )
        return self

    model_config = {"json_schema_extra": {"example": {
        "part_number": "18149-D6",
        "description": "M6×33 Flat Head Bolt",
        "overall_length": 33.0,
        "head": {"type": "flat", "diameter": 12.0, "height": 3.6,
                 "chamfer_angle_deg": 90.0, "drive_type": "cross", "drive_size": 3.0},
        "shank": {"diameter": 6.0, "length": 10.0},
        "thread": {"spec": "M6×1.0", "nominal_diameter": 6.0, "pitch": 1.0,
                   "length": 20.0, "thread_class": "6g"},
        "material_grade": "10B21",
        "strength_grade": "8.8",
    }}}


# ===========================================================================
# Process Plan
# ===========================================================================


class ShapeDescription(BaseModel):
    """Geometric description of an intermediate workpiece shape at a forming station."""

    overall_length: float = Field(..., gt=0, description="Total length (mm)")
    max_diameter: float = Field(..., gt=0, description="Maximum outer diameter (mm)")
    head_diameter: float | None = Field(None, gt=0, description="Head / upset diameter (mm)")
    head_height: float | None = Field(None, gt=0, description="Head / upset height (mm)")
    shank_diameter: float | None = Field(None, gt=0, description="Shank diameter (mm)")
    shank_length: float | None = Field(None, gt=0, description="Shank length (mm)")
    extrusion_diameter: float | None = Field(
        None, gt=0, description="Extruded section diameter (mm)"
    )
    extrusion_length: float | None = Field(
        None, gt=0, description="Extruded section length (mm)"
    )
    notes: str | None = Field(None, description="Shape description notes")


class StationPlan(BaseModel):
    """Plan for a single forming station."""

    station_number: int = Field(..., ge=1, description="Station number (1-based)")
    operation: OperationType = Field(..., description="Primary forming operation")
    description: str = Field(..., description="Human-readable station description")
    input_shape: ShapeDescription = Field(..., description="Workpiece shape entering this station")
    output_shape: ShapeDescription = Field(..., description="Workpiece shape leaving this station")
    upset_ratio: float | None = Field(
        None, gt=0, le=3.0,
        description="Upset ratio D_out/D_in. Must be ≤ 2.3 per cold-heading limits.",
    )
    area_reduction_pct: float | None = Field(
        None, ge=0, le=100,
        description="Cross-sectional area reduction % for extrusion stations.",
    )
    force_estimate_kn: float | None = Field(
        None, gt=0, description="Estimated forming force (kN)"
    )

    @field_validator("upset_ratio")
    @classmethod
    def check_upset_ratio(cls, v: float | None) -> float | None:
        if v is not None and v > 2.3:
            raise ValueError(f"Upset ratio {v} exceeds cold-heading limit of 2.3")
        return v


class ProcessPlan(BaseModel):
    """
    Complete forming process plan for a fastener.

    Generated by the AI in Step 3 using LLM reasoning with few-shot examples.
    """

    total_stations: int = Field(..., ge=1, le=8, description="Number of forming stations")
    blank_diameter: float = Field(..., gt=0, description="Wire stock diameter (mm)")
    blank_length: float = Field(..., gt=0, description="Wire stock cut length (mm)")
    stations: list[StationPlan] = Field(..., min_length=1)
    post_processes: list[PostProcess] = Field(
        default_factory=list, description="Post-forming operations"
    )
    estimated_cycle_time_s: float | None = Field(
        None, gt=0, description="Estimated cycle time per part (seconds)"
    )
    confidence: ConfidenceLevel = Field(..., description="Process plan confidence level")
    reasoning_summary: str = Field(..., description="Brief explanation of process choices")

    @model_validator(mode="after")
    def validate_station_count(self) -> ProcessPlan:
        if len(self.stations) != self.total_stations:
            raise ValueError(
                f"total_stations={self.total_stations} but {len(self.stations)} station plans provided"
            )
        return self


# ===========================================================================
# Die Design
# ===========================================================================


class DieComponentParams(BaseModel):
    """
    Parameters for a single die component (punch or die insert) at one station.

    Drives parametric 3D generation (CADQuery) and 2D drawing generation (ezdxf).
    """

    component_type: Literal["punch", "die"] = Field(..., description="Component type")
    material: str = Field(
        ..., description="Die steel grade", examples=["SKD11", "DC53", "ASP2030"]
    )
    hardness_hrc_min: float = Field(..., ge=50, le=70, description="Min working hardness (HRC)")
    hardness_hrc_max: float = Field(..., ge=50, le=70, description="Max working hardness (HRC)")
    geometry_type: DieGeometryType = Field(..., description="Primary geometry type")

    # Key dimensions (all in mm)
    outer_diameter: float = Field(..., gt=0, description="Component OD (mm)")
    inner_diameter: float | None = Field(None, gt=0, description="Bore / cavity ID (mm) for dies")
    working_length: float = Field(..., gt=0, description="Active working length (mm)")
    cavity_depth: float | None = Field(None, gt=0, description="Cavity depth (mm) for closed dies")
    shoulder_diameter: float | None = Field(
        None, gt=0, description="Retaining shoulder diameter (mm)"
    )

    # Forming geometry
    approach_angle_deg: float | None = Field(
        None, ge=0, le=90, description="Approach / reduction angle (degrees)"
    )
    land_length: float | None = Field(
        None, gt=0, description="Straight land length at working diameter (mm)"
    )
    relief_angle_deg: float | None = Field(
        None, ge=0, le=30, description="Relief / back-taper angle (degrees)"
    )
    entry_radius: float | None = Field(
        None, ge=0, description="Entry fillet radius (mm)"
    )

    # Surface finish
    surface_roughness_ra: float = Field(
        0.4, gt=0, le=3.2, description="Working surface roughness Ra (μm)"
    )
    surface_treatment: str | None = Field(
        None, description="Coating e.g. TiN, TiCN", examples=["TiN"]
    )
    coating_thickness_um: float | None = Field(
        None, gt=0, description="Coating thickness (μm)"
    )

    key_tolerances: dict[str, Tolerance] = Field(
        default_factory=dict,
        description="Critical dimension tolerances by name e.g. {'inner_dia': Tolerance(...)}"
    )

    model_config = {"json_schema_extra": {"example": {
        "component_type": "punch",
        "material": "SKD11",
        "hardness_hrc_min": 60.0,
        "hardness_hrc_max": 62.0,
        "geometry_type": "conical",
        "outer_diameter": 20.0,
        "working_length": 45.0,
        "approach_angle_deg": 90.0,
        "land_length": 3.0,
        "surface_roughness_ra": 0.2,
        "surface_treatment": "TiN",
        "coating_thickness_um": 3.0,
    }}}


class DieParameters(BaseModel):
    """
    Complete die design for one forming station (punch + die).

    Generated by the AI in Step 4. Drives both 3D model generation
    (CADQuery) and 2D drawing generation (ezdxf).
    """

    station_number: int = Field(..., ge=1)
    punch: DieComponentParams = Field(..., description="Punch parameters")
    die: DieComponentParams = Field(..., description="Die (cavity) parameters")
    clearance_mm: float = Field(
        ..., gt=0, description="Punch-die radial clearance (mm, each side)"
    )
    expected_life_shots: int | None = Field(
        None, gt=0, description="Expected tool life (number of parts before replacement)"
    )
    notes: str | None = Field(None, description="Design notes or special requirements")

    @model_validator(mode="after")
    def validate_components(self) -> DieParameters:
        if self.punch.component_type != "punch":
            raise ValueError("punch field must have component_type='punch'")
        if self.die.component_type != "die":
            raise ValueError("die field must have component_type='die'")
        # Die must be harder than punch (which must be harder than workpiece)
        if self.die.hardness_hrc_min < self.punch.hardness_hrc_min:
            raise ValueError(
                f"Die HRC ({self.die.hardness_hrc_min}) should be ≥ punch HRC ({self.punch.hardness_hrc_min})"
            )
        return self


# ===========================================================================
# RAG / Knowledge Base
# ===========================================================================


class PseudoReasoning(BaseModel):
    """
    LLM-inferred engineering reasoning for a historical product-die pair.

    Generated by the pseudo-reasoning pipeline (3× Claude self-consistency
    + Gemini cross-validation). Only high-confidence entries enter RAG store.
    """

    stock_selection: str = Field(
        ..., description="Reasoning for wire stock diameter and length choice"
    )
    station_count_reasoning: str = Field(
        ..., description="Reasoning for number of stations chosen"
    )
    deformation_sequence: str = Field(
        ..., description="Explanation of the deformation sequence logic"
    )
    die_material_selection: str = Field(
        ..., description="Reasoning for die steel and hardness selection"
    )
    critical_features: list[str] = Field(
        ..., description="Key geometric features that drive the design"
    )
    known_challenges: list[str] = Field(
        ..., description="Known manufacturing challenges for this part type"
    )
    confidence: ConfidenceLevel
    cross_validation_agreement: bool | None = Field(
        None, description="True if Claude and Gemini agree on the reasoning"
    )
    claude_run_count: int = Field(3, description="Number of self-consistency runs performed")
    raw_llm_outputs: list[str] = Field(
        default_factory=list, description="Raw LLM outputs for auditing (not used in prompts)"
    )


class RAGCase(BaseModel):
    """
    Complete case stored in the RAG vector database (ChromaDB).

    Layer 2 of the data architecture. Contains the full product-die pair
    with pseudo-reasoning, ready for retrieval and few-shot formatting.
    """

    case_id: str = Field(..., description="Unique case identifier (UUID)")
    order_id: str = Field(..., description="Source order identifier")
    embedding_text: str = Field(
        ..., description="Dense text used for Voyage embedding (generated by Claude Haiku)"
    )
    part_features: PartFeatures
    process_plan: ProcessPlan
    die_parameters: list[DieParameters]
    pseudo_reasoning: PseudoReasoning
    confidence: ConfidenceLevel
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    source_files: list[str] = Field(
        default_factory=list, description="Object storage paths of source drawings"
    )


class RetrievedCase(BaseModel):
    """A RAGCase retrieved from ChromaDB with similarity and reranking scores."""

    case: RAGCase
    vector_similarity: float = Field(..., ge=0, le=1, description="Cosine similarity (0-1)")
    rerank_score: float | None = Field(None, description="Voyage rerank-2 score")
    rank: int = Field(..., ge=1, description="Final rank after reranking (1 = most similar)")


# ===========================================================================
# Pipeline Output
# ===========================================================================


class OutputFile(BaseModel):
    """A single file in the design output package."""

    file_type: Literal[
        "production_drawing",
        "process_breakdown",
        "punch_drawing",
        "die_drawing",
        "punch_step",
        "die_step",
        "punch_stl",
        "die_stl",
        "workpiece_stl",
        "assembly_preview",
        "parameters",
        "reasoning",
    ] = Field(..., description="File type identifier")
    station_number: int | None = Field(None, description="Station number (None for overall files)")
    file_path: str = Field(..., description="Path in object storage")
    format: FileFormat
    size_bytes: int | None = Field(None, ge=0)
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class VerificationCheck(BaseModel):
    """Result of a single verification check."""

    check_name: str = Field(..., description="Machine-readable check identifier")
    passed: bool
    severity: CheckSeverity = CheckSeverity.error
    message: str = Field(..., description="Human-readable result description")
    expected: str | None = Field(None, description="Expected value (for diagnostic display)")
    actual: str | None = Field(None, description="Actual value found")


class VerificationResult(BaseModel):
    """Aggregated result of all verification checks for a design."""

    passed: bool = Field(..., description="True only if all ERROR-severity checks pass")
    checks: list[VerificationCheck]
    retry_count: int = Field(0, ge=0, description="Number of pipeline retries consumed")
    flagged_for_review: bool = Field(
        False, description="True if design needs mandatory human review"
    )

    @model_validator(mode="after")
    def compute_passed(self) -> VerificationResult:
        error_checks = [c for c in self.checks if c.severity == CheckSeverity.error]
        self.passed = all(c.passed for c in error_checks)
        return self


class DesignResult(BaseModel):
    """
    Complete output of the die design pipeline for one product drawing.

    Created by DesignEngine.run() and stored in PostgreSQL + object storage.
    Drives the engineer review UI.
    """

    design_id: str = Field(..., description="UUID")
    order_id: str
    part_features: PartFeatures
    process_plan: ProcessPlan
    die_parameters: list[DieParameters]
    verification: VerificationResult
    output_files: list[OutputFile] = Field(default_factory=list)
    retrieved_cases: list[RetrievedCase] = Field(
        default_factory=list, description="RAG cases used for few-shot prompting"
    )
    prompt_versions: dict[str, str] = Field(
        default_factory=dict,
        description="Prompt version used per pipeline step e.g. {'drawing_understanding': 'v1.0.0'}",
    )
    llm_cost_usd: float = Field(0.0, ge=0, description="Total LLM API cost for this design")
    processing_time_s: float = Field(0.0, ge=0, description="Total wall-clock processing time")
    confidence: ConfidenceLevel
    status: DesignStatus = DesignStatus.pending
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    engineer_feedback: str | None = Field(
        None, description="Engineer's accept/reject/notes feedback"
    )


# ===========================================================================
# Pseudo-Reasoning Pipeline
# ===========================================================================


class ProductDiePair(BaseModel):
    """Input to the pseudo-reasoning pipeline: a complete product-die design pair."""

    pair_id: str = Field(..., description="Unique identifier for this pair")
    part_features: PartFeatures
    process_plan: ProcessPlan
    die_parameters: list[DieParameters]
    source_order_id: str | None = Field(None, description="Source order ID if from factory data")


class PrimaryReasoning(BaseModel):
    """Structured reasoning output from a single Claude Opus 4.7 run."""

    run_index: int = Field(..., ge=0, lt=3)
    observable_facts: list[str] = Field(..., description="Verifiable facts from the input data")
    stock_selection_reasoning: str = Field(..., description="Why this wire stock was chosen")
    station_count_reasoning: str = Field(..., description="Why this number of stations was chosen")
    deformation_sequence_reasoning: str = Field(..., description="Logic of the forming sequence")
    die_material_reasoning: str = Field(..., description="Why these die materials/hardness were chosen")
    dimensional_compensations: list[str] = Field(
        ..., description="Product→die dimensional differences and why"
    )
    critical_parameters: dict[str, str] = Field(
        ..., description="Critical parameter name → typical acceptable range"
    )
    potential_risks: list[str] = Field(..., description="Failure modes and manufacturing risks")
    section_confidences: dict[str, float] = Field(
        ..., description="Confidence per reasoning section (0-1)"
    )
    overall_confidence: float = Field(..., ge=0, le=1)
    input_tokens: int = Field(0, ge=0)
    output_tokens: int = Field(0, ge=0)
    cost_usd: float = Field(0.0, ge=0)
    prompt_version: str = Field("PR_V1_0_0")


class CrossValidation(BaseModel):
    """Gemini 2.5 Pro cross-validation result."""

    agreements: dict[str, bool] = Field(
        ..., description="Section name → True if Gemini agrees with Claude"
    )
    alternative_reasonings: dict[str, str] = Field(
        default_factory=dict,
        description="Section name → Gemini's alternative reasoning where it disagrees",
    )
    missed_observations: list[str] = Field(
        default_factory=list,
        description="Observations Claude missed that Gemini caught",
    )
    overall_agreement: float = Field(..., ge=0, le=1, description="Fraction of sections agreed on")
    input_tokens: int = Field(0, ge=0)
    output_tokens: int = Field(0, ge=0)
    cost_usd: float = Field(0.0, ge=0)
    prompt_version: str = Field("CV_V1_0_0")


class RuleCheck(BaseModel):
    """Result of a single rule-based verification check."""

    check_name: str = Field(..., description="Machine-readable check identifier")
    passed: bool
    message: str = Field(..., description="Human-readable result")
    actual_value: str | None = None
    expected_range: str | None = None


class RuleVerification(BaseModel):
    """Aggregated rule-based verification for a reasoning output."""

    checks: list[RuleCheck]
    passed: bool = Field(..., description="True only if all checks passed")
    pass_rate: float = Field(..., ge=0, le=1)


class QualityScores(BaseModel):
    """Quality metrics for a pseudo-reasoning output."""

    self_consistency: float = Field(..., ge=0, le=1, description="Agreement across 3 Claude runs")
    cross_model_agreement: float = Field(..., ge=0, le=1, description="Claude-Gemini agreement")
    rule_compliance: float = Field(..., ge=0, le=1, description="Fraction of rules passed")
    geometric_grounding: float = Field(
        ..., ge=0, le=1, description="Reasoning references actual input data"
    )
    overall_confidence: ConfidenceLevel


class ReasoningResult(BaseModel):
    """Final aggregated output of the pseudo-reasoning pipeline for one pair."""

    pair_id: str
    reasoning: PseudoReasoning
    quality: QualityScores
    primaries: list[PrimaryReasoning]
    cross_validation: CrossValidation
    rule_verification: RuleVerification
    total_cost_usd: float = Field(0.0, ge=0)
    total_time_s: float = Field(0.0, ge=0)
    prompt_versions: dict[str, str] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


# ===========================================================================
# Drawing Parsing
# ===========================================================================


class ExtractedDimension(BaseModel):
    """A single dimension entity extracted from a DWG/DXF file."""

    dimension_type: DimensionType
    value: float = Field(..., description="Nominal dimension value (mm or degrees)")
    unit: Literal["mm", "deg", "inch"] = "mm"
    tolerance_plus: float | None = Field(None, ge=0)
    tolerance_minus: float | None = Field(None, ge=0)
    label: str | None = Field(None, description="Dimension text as shown in drawing")
    x: float | None = Field(None, description="X coordinate in drawing space")
    y: float | None = Field(None, description="Y coordinate in drawing space")
    layer: str | None = Field(None, description="DXF layer the entity is on")


class TitleBlock(BaseModel):
    """Structured content of the drawing title block."""

    part_number: str | None = Field(None, examples=["18149-D6"])
    title: str | None = Field(None, examples=["M6×33 FLAT HEAD BOLT"])
    material: str | None = Field(None, examples=["10B21"])
    scale: str | None = Field(None, examples=["1:1"])
    drawn_by: str | None = None
    checked_by: str | None = None
    date: str | None = None
    revision: str | None = Field(None, examples=["A"])
    company: str | None = None
    standard: str | None = Field(None, examples=["GB/T 5789"])
    surface_roughness: str | None = Field(
        None, description="General surface roughness note", examples=["Ra 3.2"]
    )


class ParsedDrawing(BaseModel):
    """Complete structured output of parsing a DWG/DXF file."""

    file_path: str
    file_format: Literal["dwg", "dxf", "pdf", "jpg", "png"]
    dimensions: list[ExtractedDimension] = Field(default_factory=list)
    title_block: TitleBlock = Field(default_factory=TitleBlock)
    layer_names: list[str] = Field(default_factory=list)
    entity_count: int = Field(0, ge=0)
    parse_confidence: ConfidenceLevel = ConfidenceLevel.medium
    raw_text: str | None = Field(None, description="Extracted text (PDF/image only)")
    parse_errors: list[str] = Field(default_factory=list)


# ===========================================================================
# Evaluation
# ===========================================================================


class ExpectedDecisions(BaseModel):
    """
    Expected AI design decisions for a golden test case.

    Used to compute accuracy metrics in automated evaluation.
    """

    expected_station_count: int = Field(..., ge=1)
    expected_blank_diameter: float = Field(..., gt=0)
    expected_blank_length: float = Field(..., gt=0)
    expected_operations: list[OperationType] = Field(..., min_length=1)
    expected_die_materials: list[str] = Field(
        ..., min_length=1,
        description="Expected die steel grades per station"
    )
    confidence_threshold: ConfidenceLevel = ConfidenceLevel.high
    tolerance_station_count: int = Field(0, description="Allowed deviation in station count")
    tolerance_blank_dim_pct: float = Field(
        5.0, gt=0, description="Allowed % deviation for blank dimensions"
    )


class MetricResult(BaseModel):
    """Result of a single evaluation metric."""

    metric_name: str
    value: float
    unit: str | None = None
    threshold: float | None = Field(None, description="Pass/fail threshold")
    passed: bool | None = Field(None, description="None if no threshold defined")
    case_id: str | None = Field(None, description="Case this metric applies to (None = aggregate)")


class EvalReport(BaseModel):
    """Aggregated evaluation report for the golden test set."""

    eval_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    case_count: int = Field(..., ge=0)
    metrics: list[MetricResult]
    pass_rate: float = Field(..., ge=0, le=1, description="Fraction of cases that pass all checks")
    avg_confidence_high_pct: float = Field(
        ..., ge=0, le=100, description="% of cases with high confidence"
    )
    avg_cost_per_case_usd: float = Field(..., ge=0)
    avg_processing_time_s: float = Field(..., ge=0)
    notes: str | None = None
    baseline_comparison: dict[str, float] | None = Field(
        None, description="Delta vs. checked-in baseline for each metric"
    )
