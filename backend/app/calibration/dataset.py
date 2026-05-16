"""Calibration eval-case construction."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.data.schemas import CaseRecord, PartFeatures, ProcessForming

SourceType = Literal["factory_gt", "standard_part", "gong_textbook"]
TrustLevel = Literal["gold", "reviewed", "llm_extracted"]


class EvalCase(BaseModel):
    case_id: str
    source_type: SourceType
    trust_level: TrustLevel
    input_part_features: PartFeatures
    expected_process_forming: ProcessForming
    tags: list[str] = Field(default_factory=list)
    holdout_case_ids: list[str] = Field(default_factory=list)


def build_case_record_eval_case(record: CaseRecord) -> EvalCase:
    source_type: SourceType = (
        "factory_gt" if record.source_kind == "case_dwg" else "standard_part"
    )
    trust_level: TrustLevel = "gold" if source_type == "factory_gt" else "reviewed"
    return EvalCase(
        case_id=record.case_id,
        source_type=source_type,
        trust_level=trust_level,
        input_part_features=record.part_features,
        expected_process_forming=record.process_forming,
        tags=_tags_for_case_record(record),
        holdout_case_ids=[record.case_id],
    )


def _tags_for_case_record(record: CaseRecord) -> list[str]:
    tags = {record.product_category}
    tags.update(station.operation.value for station in record.process_forming.stations)

    features = record.part_features
    blob = " ".join([features.description, *features.notes]).lower()
    if "四方" in blob or "square" in blob or "t帽" in blob or "t-head" in blob:
        tags.add("square_head")
    if features.thread is not None or "螺纹" in blob or "thread" in blob:
        tags.add("thread")
    if "通孔" in blob or "孔" in blob or "hole" in blob:
        tags.add("hole")
    if features.head and features.head.flange:
        tags.add("flange")
    return sorted(tag for tag in tags if tag)
