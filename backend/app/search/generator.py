"""Template-guided candidate skeleton generation."""

from __future__ import annotations

from app.data.schemas import ConfidenceLevel, OperationType, WorkpieceGeometry
from app.search.candidate import CandidatePlan, CandidateStation, ScoreBreakdown, SearchTrace
from app.search.family_matcher import FamilyMatch
from app.search.features import FeatureKind, ManufacturingFeatureGraph
from app.search.operations import OperationCapability, OperationRequirements


def generate_candidate_skeletons(
    *,
    graph: ManufacturingFeatureGraph,
    family: FamilyMatch,
    requirements: OperationRequirements,
    max_candidates: int = 3,
) -> list[CandidatePlan]:
    """Generate a small set of candidate station skeletons.

    This is intentionally not a parameter optimizer yet. It emits a conservative
    first skeleton that covers required operation capabilities in a plausible
    precedence order so later constraint/scoring layers have something concrete
    to evaluate.
    """

    if max_candidates <= 0:
        return []

    if family.family == "square_T_head":
        return [_generate_square_t_head_skeleton(graph, family, requirements)]

    return [_generate_generic_skeleton(graph, family, requirements)]


def _generate_square_t_head_skeleton(
    graph: ManufacturingFeatureGraph,
    family: FamilyMatch,
    requirements: OperationRequirements,
) -> CandidatePlan:
    required = {item.capability for item in requirements.required}
    stations: list[CandidateStation] = []

    if OperationCapability.material_gathering in required:
        stations.append(
            _station(
                len(stations) + 1,
                OperationType.upsetting,
                graph,
                "聚集头部/法兰材料",
            )
        )
    if OperationCapability.forward_extrusion in required:
        stations.append(
            _station(
                len(stations) + 1,
                OperationType.forward_extrusion,
                graph,
                "正挤形成杆部与头部台阶坯",
            )
        )
    if OperationCapability.flange_forming in required:
        stations.append(
            _station(
                len(stations) + 1,
                OperationType.heading,
                graph,
                "镦粗/压扁形成头部或法兰预形",
            )
        )

    combined_capabilities = {
        OperationCapability.polygon_head_forming,
        OperationCapability.recess_forming,
    }
    if required & combined_capabilities:
        stations.append(
            _station(
                len(stations) + 1,
                OperationType.combined,
                graph,
                "四方头成形并压印凹槽特征",
            )
        )

    if OperationCapability.trimming_or_sizing in required:
        stations.append(
            _station(
                len(stations) + 1,
                OperationType.trimming,
                graph,
                "切边/整形控制四方对边与角部 R",
            )
        )

    if OperationCapability.piercing in required:
        stations.append(
            _station(
                len(stations) + 1,
                OperationType.piercing,
                graph,
                "冲孔形成通孔或螺纹底孔",
            )
        )

    trace_warnings = list(requirements.warnings)
    if OperationCapability.piercing not in required:
        trace_warnings.append("piercing optional: through_hole not present")

    return CandidatePlan(
        candidate_id=f"{graph.part_id}/square_T_head/default_skeleton",
        family=family.family,
        template_id="square_T_head/default_skeleton",
        part_name_zh=_infer_part_name(graph),
        material=graph.material,
        blank=_blank_from_graph(graph),
        stations=stations,
        source_case_ids=[],
        score_breakdown=_initial_score(family.score),
        search_trace=SearchTrace(
            generated_by="template_guided_skeleton_generator",
            matched_features=family.matched_features,
            applied_template_priors=[
                "square_T_head: material gathering before forward extrusion/head finishing",
                "polygon/recess features can share a combined forming station",
            ],
            operation_choices=[
                f"station {station.n}: {station.operation.value}" for station in stations
            ],
            warnings=trace_warnings,
        ),
        rationale_zh="由四方T头 primitive features 推导的首版候选站序骨架。",
        confidence=ConfidenceLevel.medium,
    )


def _generate_generic_skeleton(
    graph: ManufacturingFeatureGraph,
    family: FamilyMatch,
    requirements: OperationRequirements,
) -> CandidatePlan:
    stations = [
        _station(1, OperationType.upsetting, graph, "按 feature graph 生成的通用预成形站")
    ]
    return CandidatePlan(
        candidate_id=f"{graph.part_id}/{family.family}/generic_skeleton",
        family=family.family,
        template_id=f"{family.family}/generic_skeleton",
        part_name_zh=_infer_part_name(graph),
        material=graph.material,
        blank=_blank_from_graph(graph),
        stations=stations,
        score_breakdown=_initial_score(family.score),
        search_trace=SearchTrace(
            generated_by="template_guided_skeleton_generator",
            matched_features=family.matched_features,
            applied_template_priors=[],
            operation_choices=[f"station 1: {OperationType.upsetting.value}"],
            warnings=list(requirements.warnings),
        ),
        rationale_zh="通用候选站序骨架，等待 family-specific generator 扩展。",
    )


def _station(
    n: int,
    operation: OperationType,
    graph: ManufacturingFeatureGraph,
    purpose_zh: str,
) -> CandidateStation:
    return CandidateStation(
        n=n,
        operation=operation,
        workpiece=_final_like_workpiece(graph),
        purpose_zh=purpose_zh,
    )


def _blank_from_graph(graph: ManufacturingFeatureGraph) -> WorkpieceGeometry:
    shank = _feature_dims(graph, FeatureKind.cylindrical_shank)
    diameter = shank.get("diameter", 1.0)
    return WorkpieceGeometry(
        type="cylinder",
        overall_length_mm=graph.overall_length_mm,
        max_diameter_mm=diameter,
    )


def _final_like_workpiece(graph: ManufacturingFeatureGraph) -> WorkpieceGeometry:
    shank = _feature_dims(graph, FeatureKind.cylindrical_shank)
    head = _feature_dims(graph, FeatureKind.square_head) or _feature_dims(graph, FeatureKind.flange)
    shank_d = shank.get("diameter")
    shank_l = shank.get("length")
    head_d = head.get("flat_width") or head.get("diameter")
    head_h = head.get("height")
    return WorkpieceGeometry(
        type="flanged" if head_d else "stepped",
        overall_length_mm=graph.overall_length_mm,
        max_diameter_mm=max(value for value in (shank_d, head_d) if value is not None),
        head_diameter_mm=head_d,
        head_height_mm=head_h,
        shank_diameter_mm=shank_d,
        shank_length_mm=shank_l,
        corner_radius_mm=head.get("corner_radius"),
    )


def _feature_dims(graph: ManufacturingFeatureGraph, kind: FeatureKind) -> dict[str, float]:
    for feature in graph.features:
        if feature.kind == kind:
            return feature.dimensions_mm
    return {}


def _initial_score(family_score: float) -> ScoreBreakdown:
    return ScoreBreakdown(
        operation_coverage=0.75,
        precedence=0.7,
        deformation_safety=0.5,
        feature_progression=0.5,
        case_similarity=family_score,
        renderer_readiness=0.6,
    )


def _infer_part_name(graph: ManufacturingFeatureGraph) -> str:
    return graph.description
