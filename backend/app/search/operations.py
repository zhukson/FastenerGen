"""Operation grammar over primitive manufacturing features."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field

from app.search.features import FeatureKind, ManufacturingFeatureGraph


class OperationCapability(StrEnum):
    """Search-level operation capabilities before station sequencing."""

    material_gathering = "material_gathering"
    forward_extrusion = "forward_extrusion"
    backward_extrusion = "backward_extrusion"
    flange_forming = "flange_forming"
    polygon_head_forming = "polygon_head_forming"
    recess_forming = "recess_forming"
    piercing = "piercing"
    trimming_or_sizing = "trimming_or_sizing"
    thread_forming = "thread_forming"


class OperationRequirement(BaseModel):
    """One required or optional operation capability inferred from features."""

    capability: OperationCapability
    triggered_by_features: list[str] = Field(default_factory=list)
    rationale_zh: str
    precedence_after: list[OperationCapability] = Field(default_factory=list)
    precedence_before: list[OperationCapability] = Field(default_factory=list)


class OperationRequirements(BaseModel):
    """Operation capabilities required by a feature graph."""

    family: str
    required: list[OperationRequirement] = Field(default_factory=list)
    optional: list[OperationRequirement] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    def require(self, capability: OperationCapability) -> OperationRequirement:
        for item in self.required:
            if item.capability == capability:
                return item
        raise KeyError(f"required operation not found: {capability}")


def infer_operation_requirements(
    graph: ManufacturingFeatureGraph,
    *,
    family: str,
) -> OperationRequirements:
    """Infer required operation capabilities from primitive features."""

    present = {feature.kind for feature in graph.features}
    required: list[OperationRequirement] = []
    optional: list[OperationRequirement] = []
    warnings: list[str] = []

    if FeatureKind.flange in present or FeatureKind.square_head in present:
        required.append(
            OperationRequirement(
                capability=OperationCapability.material_gathering,
                triggered_by_features=_feature_values(
                    present,
                    FeatureKind.flange,
                    FeatureKind.square_head,
                ),
                rationale_zh=f"{family}: 大头/法兰需要先聚料，避免一次成形变形过大。",
            )
        )

    if FeatureKind.cylindrical_shank in present and (
        FeatureKind.flange in present or FeatureKind.square_head in present
    ):
        required.append(
            OperationRequirement(
                capability=OperationCapability.forward_extrusion,
                triggered_by_features=[FeatureKind.cylindrical_shank.value],
                rationale_zh=f"{family}: 头部聚料与较小杆部并存，通常需要正挤/缩杆建立阶梯坯。",
                precedence_after=[OperationCapability.material_gathering],
                precedence_before=[
                    OperationCapability.flange_forming,
                    OperationCapability.polygon_head_forming,
                ],
            )
        )

    if FeatureKind.flange in present:
        required.append(
            OperationRequirement(
                capability=OperationCapability.flange_forming,
                triggered_by_features=[FeatureKind.flange.value],
                rationale_zh=f"{family}: 法兰/头部盘形特征需要镦粗或压扁成形。",
                precedence_after=[
                    OperationCapability.material_gathering,
                    OperationCapability.forward_extrusion,
                ],
            )
        )

    if FeatureKind.square_head in present:
        required.append(
            OperationRequirement(
                capability=OperationCapability.polygon_head_forming,
                triggered_by_features=[FeatureKind.square_head.value],
                rationale_zh=f"{family}: 四方/多边形头需要专门成形或切边整形。",
                precedence_after=[OperationCapability.flange_forming],
            )
        )
        required.append(
            OperationRequirement(
                capability=OperationCapability.trimming_or_sizing,
                triggered_by_features=_feature_values(
                    present,
                    FeatureKind.square_head,
                    FeatureKind.corner_radius,
                ),
                rationale_zh=f"{family}: 四方头和圆角需要切边或整形保证对边尺寸与角部 R。",
                precedence_after=[OperationCapability.polygon_head_forming],
            )
        )

    if FeatureKind.cross_recess in present:
        required.append(
            OperationRequirement(
                capability=OperationCapability.recess_forming,
                triggered_by_features=[FeatureKind.cross_recess.value],
                rationale_zh=f"{family}: 十字/槽形凹陷需要压印或冲压成形。",
                precedence_after=[OperationCapability.flange_forming],
            )
        )

    if FeatureKind.through_hole in present:
        required.append(
            OperationRequirement(
                capability=OperationCapability.piercing,
                triggered_by_features=[FeatureKind.through_hole.value],
                rationale_zh=f"{family}: 通孔需要冲孔/穿孔，并在最终整形前后控制毛刺和孔径。",
                precedence_after=[OperationCapability.flange_forming],
            )
        )
    else:
        optional.append(
            OperationRequirement(
                capability=OperationCapability.piercing,
                triggered_by_features=[],
                rationale_zh=f"{family}: 当前 feature graph 未确认通孔，冲孔只能作为可选待确认能力。",
            )
        )
        if family == "square_T_head":
            warnings.append("through_hole not present; piercing remains optional")

    if FeatureKind.thread in present:
        required.append(
            OperationRequirement(
                capability=OperationCapability.thread_forming,
                triggered_by_features=[FeatureKind.thread.value],
                rationale_zh=f"{family}: 螺纹特征需要后续搓牙/攻牙。",
            )
        )

    return OperationRequirements(
        family=family,
        required=_dedupe_requirements(required),
        optional=_dedupe_requirements(optional),
        warnings=warnings,
    )


def _feature_values(present: set[FeatureKind], *features: FeatureKind) -> list[str]:
    return [feature.value for feature in features if feature in present]


def _dedupe_requirements(items: list[OperationRequirement]) -> list[OperationRequirement]:
    deduped: dict[OperationCapability, OperationRequirement] = {}
    for item in items:
        if item.capability not in deduped:
            deduped[item.capability] = item
            continue
        existing = deduped[item.capability]
        existing.triggered_by_features = sorted(
            set(existing.triggered_by_features) | set(item.triggered_by_features)
        )
        existing.precedence_after = sorted(
            set(existing.precedence_after) | set(item.precedence_after),
            key=lambda capability: capability.value,
        )
        existing.precedence_before = sorted(
            set(existing.precedence_before) | set(item.precedence_before),
            key=lambda capability: capability.value,
        )
    return list(deduped.values())

