"""Teacher-rationale checkpoints for Gong calibration.

These are not hidden model chain-of-thought. They are explicit, auditable
engineering checkpoints derived from GT cases: required operations,
precedence constraints, and common failure modes.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.calibration.dataset import EvalCase
from app.data.schemas import (
    GongMetricResult,
    OperationType,
    ProcessForming,
    StationStep,
)


class OperationCheckpoint(BaseModel):
    operation: OperationType
    why_zh: str


class PrecedenceCheckpoint(BaseModel):
    before: OperationType
    after: OperationType
    why_zh: str


class FeatureObservation(BaseModel):
    feature_key: str
    evidence_zh: str
    expected_inference: list[str] = Field(default_factory=list)


class TeacherRationale(BaseModel):
    case_id: str
    feature_observations: list[FeatureObservation] = Field(default_factory=list)
    required_operations: list[OperationCheckpoint] = Field(default_factory=list)
    precedence_constraints: list[PrecedenceCheckpoint] = Field(default_factory=list)
    common_failure_modes: list[str] = Field(default_factory=list)


def score_teacher_rationale_alignment(
    predicted: ProcessForming,
    rationale: TeacherRationale,
) -> list[GongMetricResult]:
    """Score whether a prediction covers teacher-rationale checkpoints."""
    return [
        score_required_operation_recall(predicted, rationale),
        score_precedence_constraint_recall(predicted, rationale),
    ]


def build_teacher_rationale_from_eval_case(eval_case: EvalCase) -> TeacherRationale:
    """Build an auditable baseline rationale directly from the GT sequence.

    This is intentionally deterministic. LLM-generated teacher rationales can
    add richer feature evidence later, but this baseline guarantees that every
    calibration case has required-operation and precedence checkpoints aligned
    with the answer key.
    """
    operations = [station.operation for station in eval_case.expected_process_forming.stations]
    unique_operations = list(dict.fromkeys(operations))
    return TeacherRationale(
        case_id=eval_case.case_id,
        feature_observations=_feature_observations_for_eval_case(eval_case),
        required_operations=[
            OperationCheckpoint(
                operation=operation,
                why_zh=_operation_why(eval_case, operation),
            )
            for operation in unique_operations
        ],
        precedence_constraints=[
            PrecedenceCheckpoint(
                before=before,
                after=after,
                why_zh=_precedence_why(eval_case, before, after),
            )
            for before, after in zip(operations, operations[1:], strict=False)
            if before != after
        ],
        common_failure_modes=[
            "不要把 combined 当作万能工序来掩盖正挤、反挤、切边、冲孔等具体成形机制。",
            "复杂头部件需要同时解释材料聚集、杆部/孔槽成形和最终外轮廓控制。",
        ],
    )


def _operation_why(eval_case: EvalCase, operation: OperationType) -> str:
    stations = [
        station
        for station in eval_case.expected_process_forming.stations
        if station.operation == operation
    ]
    station_evidence = _station_evidence(stations)
    feature_evidence = _feature_evidence_for_operation(eval_case, operation)
    logic = _operation_logic(operation)
    parts = [part for part in [feature_evidence, logic, station_evidence] if part]
    return "；".join(parts)


def _precedence_why(
    eval_case: EvalCase,
    before: OperationType,
    after: OperationType,
) -> str:
    feature_text = "；".join(
        observation.evidence_zh
        for observation in _feature_observations_for_eval_case(eval_case)
    )
    if before == OperationType.upsetting and after == OperationType.forward_extrusion:
        return "先镦粗聚集头部/局部体积，再正挤杆部或台阶，避免材料不足导致杆部尺寸不稳。"
    if before == OperationType.forward_extrusion and after == OperationType.heading:
        return "先通过正挤确定杆部直径和长度，再镦头/终成形头部，便于控制头杆体积分配。"
    if before == OperationType.heading and after == OperationType.backward_extrusion:
        return "先形成足够头部体积和外形，再反挤内孔/内六角，避免孔槽成形时头部材料不足。"
    if before == OperationType.heading and after == OperationType.combined:
        return "先完成基础头部成形，再用复合工序压印、凹槽或局部整形。"
    if before == OperationType.combined and after == OperationType.trimming:
        return "复合成形会产生或保留外轮廓余量，之后切边/整形控制最终方形或六角外轮廓。"
    if before == OperationType.trimming and after == OperationType.piercing:
        return "先切边稳定外轮廓和定位基准，再冲孔，避免孔位受后续切边变形影响。"
    if before == OperationType.backward_extrusion and after == OperationType.forward_extrusion:
        return "先完成头部孔槽/内六角特征，再正挤或校准杆部，保持头部功能区不被后续聚料破坏。"
    if feature_text:
        return f"由产品特征和相邻工位几何演变决定先 {before.value} 后 {after.value}：{feature_text}"
    return f"相邻工位显示先 {before.value} 后 {after.value}，用于保持材料流动和尺寸基准连续。"


def _feature_evidence_for_operation(
    eval_case: EvalCase,
    operation: OperationType,
) -> str:
    observations = _feature_observations_for_eval_case(eval_case)
    matched: list[str] = []
    for observation in observations:
        joined = " ".join(observation.expected_inference)
        if operation.value in joined:
            matched.append(observation.evidence_zh)

    if matched:
        return "产品特征依据：" + "；".join(dict.fromkeys(matched))

    features = eval_case.input_part_features
    if operation == OperationType.upsetting and features.head:
        return "产品有头部/法兰体积需求，需要先聚料。"
    if operation == OperationType.heading and features.head:
        return "产品头部需要形成稳定外形和头高，需要镦头/终镦。"
    if operation == OperationType.trimming:
        desc = " ".join([features.description, *features.notes])
        if any(token in desc for token in ("四方", "六角", "hex", "square")):
            return "产品最终外轮廓包含非圆形头部，需要切边或整形控制外轮廓。"
    if operation in (OperationType.piercing, OperationType.backward_extrusion):
        desc = " ".join([features.description, *features.notes])
        if any(token in desc for token in ("孔", "槽", "凹", "内六角", "socket", "recess")):
            return "产品包含孔、槽、凹穴或内六角功能特征，需要专门孔槽成形工序。"
    return ""


def _operation_logic(operation: OperationType) -> str:
    return {
        OperationType.combined: "复合工序用于把局部成形、压印、整形或下料校正合并到同一站。",
        OperationType.upsetting: "镦粗用于轴向压缩并把材料聚集到头部或局部增厚区域。",
        OperationType.forward_extrusion: "正挤用于让材料沿轴向流动，形成较长杆部、缩径段或台阶过渡。",
        OperationType.backward_extrusion: "反挤用于在头部形成内孔、内六角、凹穴等向内的功能结构。",
        OperationType.heading: "镦头/终镦用于形成主要头部外形、头径和头高。",
        OperationType.trimming: "切边/修边用于把圆形预成形头修成六角、四方等最终外轮廓。",
        OperationType.piercing: "冲孔用于打开通孔或为后续攻牙/功能孔准备孔形。",
    }[operation]


def _station_evidence(stations: list[StationStep]) -> str:
    chunks: list[str] = []
    for station in stations:
        dimensions = ", ".join(
            f"{key}={value:g}" for key, value in station.key_dimensions.items()
        )
        workpiece = station.workpiece
        geometry = ", ".join(
            part
            for part in [
                f"type={workpiece.type}",
                (
                    f"L={workpiece.overall_length_mm:g}"
                    if workpiece.overall_length_mm is not None
                    else ""
                ),
                (
                    f"Dmax={workpiece.max_diameter_mm:g}"
                    if workpiece.max_diameter_mm is not None
                    else ""
                ),
                (
                    f"headD={workpiece.head_diameter_mm:g}"
                    if workpiece.head_diameter_mm is not None
                    else ""
                ),
                (
                    f"shankD={workpiece.shank_diameter_mm:g}"
                    if workpiece.shank_diameter_mm is not None
                    else ""
                ),
                (
                    f"holeD={workpiece.through_hole_diameter_mm:g}"
                    if workpiece.through_hole_diameter_mm is not None
                    else ""
                ),
                (
                    f"recessD={workpiece.head_recess_diameter_mm:g}"
                    if workpiece.head_recess_diameter_mm is not None
                    else ""
                ),
            ]
            if part
        )
        note = station.notes_zh or ""
        chunks.append(
            f"{station.n}工位证据：{note}"
            + (f"；关键尺寸 {dimensions}" if dimensions else "")
            + (f"；几何 {geometry}" if geometry else "")
        )
    return "；".join(chunks)


def _feature_observations_for_eval_case(eval_case: EvalCase) -> list[FeatureObservation]:
    features = eval_case.input_part_features
    description_blob = " ".join([features.description, *features.notes])
    operations = {station.operation for station in eval_case.expected_process_forming.stations}
    observations: list[FeatureObservation] = []

    if any(token in description_blob for token in ("四方", "T帽", "T头")):
        observations.append(
            FeatureObservation(
                feature_key="square_or_t_head",
                evidence_zh="产品特征包含四方/T 头外形，最终外轮廓不是单纯圆形镦头。",
                expected_inference=[
                    "需要考虑 trimming/cutting/form-calibration 控制方形外轮廓",
                    "不要只用 heading 或 combined 概括最终外形",
                ],
            )
        )

    if features.head and features.shank:
        head_diameter = features.head.flange_diameter or features.head.diameter
        if head_diameter / features.shank.diameter >= 1.8:
            observations.append(
                FeatureObservation(
                    feature_key="large_head_volume",
                    evidence_zh="头部或法兰直径明显大于杆部直径，需要前序聚料和体积分配。",
                    expected_inference=[
                        "需要 upsetting 聚集头部材料",
                        "若存在细长杆/台阶，需考虑 forward_extrusion 或缩径类工序",
                    ],
                )
            )

    has_hole_or_recess_text = any(
        token in description_blob
        for token in ("孔", "槽", "凹", "hole", "recess", "internal")
    )
    has_hole_or_recess_process = bool(
        operations & {OperationType.piercing, OperationType.backward_extrusion}
    )
    if (
        features.head
        and features.head.drive_type.value != "none"
        or has_hole_or_recess_text
        or has_hole_or_recess_process
    ):
        observations.append(
            FeatureObservation(
                feature_key="hole_or_recess",
                evidence_zh="头部存在槽/孔/驱动结构，通常不是纯外形成形即可完成。",
                expected_inference=[
                    "需要安排 piercing/backward_extrusion/压印类工序形成孔槽结构",
                    "孔槽类工序应与外形稳定顺序配合，避免过早破坏材料流动",
                ],
            )
        )

    if features.thread:
        observations.append(
            FeatureObservation(
                feature_key="threaded_function",
                evidence_zh="产品包含螺纹功能，冷镦成形后通常还需要搓牙/攻牙等后处理。",
                expected_inference=[
                    "ProcessForming 应区分冷镦工位与 post_processes",
                    "不要把螺纹最终形态误当成每站都要直接画出的冷镦实体",
                ],
            )
        )

    return observations


def score_required_operation_recall(
    predicted: ProcessForming,
    rationale: TeacherRationale,
) -> GongMetricResult:
    required = [checkpoint.operation for checkpoint in rationale.required_operations]
    predicted_ops = {station.operation for station in predicted.stations}
    if not required:
        return GongMetricResult(
            metric_name="required_operation_recall",
            value=1.0,
            passed=True,
            threshold=1.0,
            case_id=rationale.case_id,
            notes="no required operation checkpoints",
        )

    missing = [op for op in required if op not in predicted_ops]
    value = (len(required) - len(missing)) / len(required)
    notes = (
        "missing: " + ", ".join(op.value for op in missing)
        if missing
        else "all required operations present"
    )
    return GongMetricResult(
        metric_name="required_operation_recall",
        value=value,
        passed=value >= 1.0,
        threshold=1.0,
        case_id=rationale.case_id,
        notes=notes,
    )


def score_precedence_constraint_recall(
    predicted: ProcessForming,
    rationale: TeacherRationale,
) -> GongMetricResult:
    constraints = rationale.precedence_constraints
    if not constraints:
        return GongMetricResult(
            metric_name="precedence_constraint_recall",
            value=1.0,
            passed=True,
            threshold=1.0,
            case_id=rationale.case_id,
            notes="no precedence checkpoints",
        )

    first_index: dict[OperationType, int] = {}
    for index, station in enumerate(predicted.stations):
        first_index.setdefault(station.operation, index)

    failures: list[str] = []
    for constraint in constraints:
        before_index = first_index.get(constraint.before)
        after_index = first_index.get(constraint.after)
        if before_index is None or after_index is None or before_index >= after_index:
            failures.append(f"{constraint.before.value} before {constraint.after.value}")

    value = (len(constraints) - len(failures)) / len(constraints)
    notes = (
        "violated: " + ", ".join(failures)
        if failures
        else "all precedence constraints satisfied"
    )
    return GongMetricResult(
        metric_name="precedence_constraint_recall",
        value=value,
        passed=value >= 1.0,
        threshold=1.0,
        case_id=rationale.case_id,
        notes=notes,
    )
