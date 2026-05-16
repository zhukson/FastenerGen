"""Candidate process-plan contract for search-based Gong reasoning."""

from __future__ import annotations

from pydantic import BaseModel, Field, computed_field, field_validator

from app.data.schemas import (
    ConfidenceLevel,
    OperationType,
    PostProcess,
    ProcessForming,
    StationStep,
    WorkpieceGeometry,
)


class ConstraintResult(BaseModel):
    """One deterministic constraint check applied to a candidate plan."""

    name: str
    passed: bool
    message: str
    severity: str = "error"
    expected: str | None = None
    actual: str | None = None


class ScoreBreakdown(BaseModel):
    """Deterministic scoring components before LLM top-N ranking."""

    operation_coverage: float = Field(..., ge=0, le=1)
    precedence: float = Field(..., ge=0, le=1)
    deformation_safety: float = Field(..., ge=0, le=1)
    feature_progression: float = Field(..., ge=0, le=1)
    case_similarity: float = Field(..., ge=0, le=1)
    renderer_readiness: float = Field(..., ge=0, le=1)

    @computed_field
    @property
    def total(self) -> float:
        values = [
            self.operation_coverage,
            self.precedence,
            self.deformation_safety,
            self.feature_progression,
            self.case_similarity,
            self.renderer_readiness,
        ]
        return round(sum(values) / len(values), 4)


class SearchTrace(BaseModel):
    """Audit trail for why a candidate was generated."""

    generated_by: str
    matched_features: list[str] = Field(default_factory=list)
    applied_template_priors: list[str] = Field(default_factory=list)
    operation_choices: list[str] = Field(default_factory=list)
    pruned_reasons: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class CandidateStation(BaseModel):
    """One station in a candidate plan before final ProcessForming emission."""

    n: int = Field(..., ge=1)
    operation: OperationType
    workpiece: WorkpieceGeometry
    purpose_zh: str | None = None
    key_dimensions: dict[str, float] = Field(default_factory=dict)
    notes_zh: str | None = None

    def to_station_step(self) -> StationStep:
        note_parts = [part for part in (self.purpose_zh, self.notes_zh) if part]
        return StationStep(
            n=self.n,
            operation=self.operation,
            workpiece=self.workpiece,
            key_dimensions=self.key_dimensions,
            notes_zh="；".join(note_parts) if note_parts else None,
        )


class CandidatePlan(BaseModel):
    """Search intermediate that can be scored, ranked, and emitted."""

    candidate_id: str
    family: str
    template_id: str
    part_name_zh: str
    material: str
    blank: WorkpieceGeometry
    stations: list[CandidateStation] = Field(..., min_length=1, max_length=8)
    post_processes: list[PostProcess] = Field(default_factory=list)
    source_case_ids: list[str] = Field(default_factory=list)
    constraint_results: list[ConstraintResult] = Field(default_factory=list)
    score_breakdown: ScoreBreakdown
    search_trace: SearchTrace
    rationale_zh: str
    confidence: ConfidenceLevel = ConfidenceLevel.medium

    @field_validator("stations")
    @classmethod
    def station_numbers_must_be_contiguous(
        cls,
        value: list[CandidateStation],
    ) -> list[CandidateStation]:
        expected = list(range(1, len(value) + 1))
        actual = [station.n for station in value]
        if actual != expected:
            raise ValueError(f"station numbers must be contiguous from 1: {actual}")
        return value

    def to_process_forming(self) -> ProcessForming:
        """Emit the current baseline schema consumed by FastenerDrawingEngine."""
        return ProcessForming(
            part_name_zh=self.part_name_zh,
            material=self.material,
            blank=self.blank,
            stations=[station.to_station_step() for station in self.stations],
            post_processes=self.post_processes,
            reasoning_zh=self.rationale_zh,
            cited_case_ids=self.source_case_ids,
            confidence=self.confidence,
        )

