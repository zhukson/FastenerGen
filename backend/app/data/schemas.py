"""Core Pydantic models for FastenerGen.

This repo now owns the upstream workflow:

    customer/product drawing -> PartFeatures -> ProcessForming schema

DXF rendering is handled by the separate FastenerDrawingEngine repository.
The models below intentionally exclude old die-design, 3D, synthetic, and
vector-RAG contracts.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Literal

from pydantic import AliasChoices, BaseModel, Field, field_validator, model_validator


class HeadType(str, Enum):
    flat = "flat"
    hex = "hex"
    button = "button"
    pan = "pan"
    socket = "socket"
    truss = "truss"
    flange = "flange"
    oval = "oval"


class DriveType(str, Enum):
    cross = "cross"
    hex_socket = "hex_socket"
    torx = "torx"
    slotted = "slotted"
    none = "none"


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
    combined = "combined"


class PostProcess(str, Enum):
    thread_rolling = "thread_rolling"
    thread_tapping = "thread_tapping"
    knurling = "knurling"
    heat_treatment = "heat_treatment"
    annealing = "annealing"
    plating = "plating"
    phosphating = "phosphating"
    zinc_plating = "zinc_plating"
    black_oxide = "black_oxide"
    passivation = "passivation"
    saponification = "saponification"
    oxalate_coating = "oxalate_coating"
    hardness_inspection = "hardness_inspection"


class ConfidenceLevel(str, Enum):
    high = "high"
    medium = "medium"
    low = "low"


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


class Tolerance(BaseModel):
    nominal: float = Field(..., description="Nominal dimension value in mm")
    plus: float = Field(0.0, ge=0)
    minus: float = Field(0.0, ge=0)

    @property
    def upper(self) -> float:
        return self.nominal + self.plus

    @property
    def lower(self) -> float:
        return self.nominal - self.minus


class HeadFeatures(BaseModel):
    type: HeadType
    diameter: float = Field(..., gt=0)
    height: float = Field(..., gt=0)
    chamfer_angle_deg: float | None = Field(None, ge=0, le=180)
    chamfer_diameter: float | None = Field(None, gt=0)
    flange: bool = False
    flange_diameter: float | None = Field(None, gt=0)
    drive_type: DriveType = DriveType.none
    drive_size: float | None = Field(None, gt=0)
    underhead_radius: float | None = Field(None, ge=0)


class ShankFeatures(BaseModel):
    diameter: float = Field(..., gt=0)
    length: float = Field(..., ge=0)
    diameter_tolerance: Tolerance | None = None


class ThreadFeatures(BaseModel):
    spec: str
    nominal_diameter: float = Field(..., gt=0)
    pitch: float | None = Field(None, gt=0)
    length: float = Field(..., gt=0)
    thread_class: str | None = None
    thread_type: Literal["metric", "unified", "bsp", "acme", "self_tap", "trade_name"] = (
        "metric"
    )
    is_full_length: bool = False

    @field_validator("pitch")
    @classmethod
    def pitch_must_be_positive_when_present(cls, value: float | None) -> float | None:
        return value


class TailFeatures(BaseModel):
    type: TailType
    length: float | None = Field(None, gt=0)
    angle_deg: float | None = Field(None, gt=0, le=180)


class PartFeatures(BaseModel):
    """Features extracted from the customer/product drawing."""

    part_number: str
    description: str
    overall_length: float = Field(..., gt=0)
    head: HeadFeatures | None = None
    shank: ShankFeatures | None = None
    thread: ThreadFeatures | None = None
    tail: TailFeatures | None = None
    material_grade: str = "10B21"
    strength_grade: str = "8.8"
    hardness_min_hv: float | None = Field(None, ge=0)
    hardness_max_hv: float | None = Field(None, ge=0)
    core_hardness_min_hrc: float | None = Field(None, ge=0, le=70)
    core_hardness_max_hrc: float | None = Field(None, ge=0, le=70)
    surface_treatment: str | None = None
    standard: str | None = None
    tolerance_class: str | None = None
    drawing_scale: str | None = None
    notes: list[str] = Field(default_factory=list)


class ExtractedDimension(BaseModel):
    dimension_type: DimensionType
    value: float
    unit: Literal["mm", "deg", "inch"] = "mm"
    tolerance_plus: float | None = Field(None, ge=0)
    tolerance_minus: float | None = Field(None, ge=0)
    label: str | None = None
    x: float | None = None
    y: float | None = None
    layer: str | None = None


class TitleBlock(BaseModel):
    part_number: str | None = None
    title: str | None = None
    material: str | None = None
    scale: str | None = None
    drawn_by: str | None = None
    checked_by: str | None = None
    date: str | None = None
    revision: str | None = None
    company: str | None = None
    standard: str | None = None
    surface_roughness: str | None = None


class ParsedDrawing(BaseModel):
    file_path: str
    file_format: Literal["dwg", "dxf", "pdf", "jpg", "jpeg", "png"]
    dimensions: list[ExtractedDimension] = Field(default_factory=list)
    title_block: TitleBlock = Field(default_factory=TitleBlock)
    layer_names: list[str] = Field(default_factory=list)
    entity_count: int = Field(0, ge=0)
    parse_confidence: ConfidenceLevel = ConfidenceLevel.medium
    raw_text: str | None = None
    parse_errors: list[str] = Field(default_factory=list)


class VerificationCheck(BaseModel):
    check_name: str
    passed: bool
    severity: CheckSeverity = CheckSeverity.error
    message: str
    expected: str | None = None
    actual: str | None = None


class VerificationResult(BaseModel):
    passed: bool
    checks: list[VerificationCheck]
    retry_count: int = Field(0, ge=0)
    flagged_for_review: bool = False

    @model_validator(mode="after")
    def compute_passed(self) -> VerificationResult:
        errors = [c for c in self.checks if c.severity == CheckSeverity.error]
        self.passed = all(c.passed for c in errors)
        return self


class ProfileSegment(BaseModel):
    label_zh: str | None = None
    length_mm: float = Field(..., ge=0)
    diameter_mm: float = Field(..., ge=0)
    end_diameter_mm: float | None = Field(None, ge=0)
    fillet_r_mm: float | None = Field(
        None,
        ge=0,
        validation_alias=AliasChoices("fillet_R_mm", "fillet_r_mm"),
        serialization_alias="fillet_R_mm",
    )
    chamfer_c_mm: float | None = Field(
        None,
        ge=0,
        validation_alias=AliasChoices("chamfer_C_mm", "chamfer_c_mm"),
        serialization_alias="chamfer_C_mm",
    )


class WorkpieceGeometry(BaseModel):
    """Semantic geometry leaving one forming station.

    This is not a CAD coordinate schema. The downstream renderer turns this
    semantic profile into drawing entities.
    """

    type: Literal[
        "cylinder",
        "stepped",
        "headed",
        "tapered",
        "square_head",
        "T_head",
        "flanged",
        "pin",
        "custom",
    ]
    overall_length_mm: float = Field(..., ge=0)
    max_diameter_mm: float = Field(..., ge=0)
    head_diameter_mm: float | None = Field(None, ge=0)
    head_height_mm: float | None = Field(None, ge=0)
    shank_diameter_mm: float | None = Field(None, ge=0)
    shank_length_mm: float | None = Field(None, ge=0)
    head_recess_diameter_mm: float | None = Field(None, ge=0)
    head_recess_depth_mm: float | None = Field(None, ge=0)
    through_hole_diameter_mm: float | None = Field(None, ge=0)
    corner_radius_mm: float | None = Field(None, ge=0)
    chamfer_c_mm: float | None = Field(
        None,
        ge=0,
        validation_alias=AliasChoices("chamfer_C_mm", "chamfer_c_mm"),
        serialization_alias="chamfer_C_mm",
    )
    fillet_r_mm: float | None = Field(
        None,
        ge=0,
        validation_alias=AliasChoices("fillet_R_mm", "fillet_r_mm"),
        serialization_alias="fillet_R_mm",
    )
    profile_segments: list[ProfileSegment] = Field(default_factory=list)
    extra_dims_mm: dict[str, float | str | int] = Field(default_factory=dict)
    notes_zh: str | None = None


class StationStep(BaseModel):
    n: int = Field(..., ge=1)
    operation: OperationType
    workpiece: WorkpieceGeometry
    key_dimensions: dict[str, float] = Field(default_factory=dict)
    notes_zh: str | None = None


class ProcessForming(BaseModel):
    """Gong system output consumed by FastenerDrawingEngine."""

    part_name_zh: str
    material: str
    blank: WorkpieceGeometry
    stations: list[StationStep] = Field(..., min_length=1, max_length=8)
    post_processes: list[PostProcess] = Field(default_factory=list)
    reasoning_zh: str
    cited_case_ids: list[str] = Field(default_factory=list)
    confidence: ConfidenceLevel

    @property
    def station_count(self) -> int:
        return len(self.stations)


class CaseRecord(BaseModel):
    """One worked example in the curated experience library."""

    case_id: str
    source_kind: Literal["case_dwg", "standard_pdf"]
    source_file: str
    product_name_zh: str
    product_category: str
    standard_ref: str | None = None
    material: str
    part_features: PartFeatures
    process_forming: ProcessForming
    extraction_confidence: ConfidenceLevel
    extracted_by: Literal["llm_draft", "human_reviewed"]
    notes_zh: str | None = None


class GongMetricResult(BaseModel):
    """One eval metric for ProcessForming reasoning quality."""

    metric_name: str
    value: float
    passed: bool | None = None
    threshold: float | None = None
    case_id: str | None = None
    notes: str | None = None


class GongEvalReport(BaseModel):
    """Aggregated leave-one-out eval report for the Gong reasoning system."""

    eval_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    case_count: int = Field(..., ge=0)
    metrics: list[GongMetricResult] = Field(default_factory=list)
    notes: str | None = None
