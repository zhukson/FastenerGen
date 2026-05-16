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

    return [_generate_dfs_skeleton(graph, family, requirements)]


def _generate_dfs_skeleton(
    graph: ManufacturingFeatureGraph,
    family: FamilyMatch,
    requirements: OperationRequirements,
) -> CandidatePlan:
    capability_order = _topological_capability_order(requirements)
    stations: list[CandidateStation] = []

    idx = 0
    while idx < len(capability_order):
        capability = capability_order[idx]
        if (
            capability == OperationCapability.polygon_head_forming
            and idx + 1 < len(capability_order)
            and capability_order[idx + 1] == OperationCapability.recess_forming
        ):
            stations.append(
                _station(
                    len(stations) + 1,
                    OperationType.combined,
                    graph,
                    "多边形头部成形并压印凹槽特征",
                )
            )
            idx += 2
            continue

        operation = _operation_for_capability(capability)
        if operation is not None:
            stations.append(
                _station(
                    len(stations) + 1,
                    operation,
                    graph,
                    _purpose_for_capability(capability),
                )
            )
        idx += 1

    if not stations:
        stations.append(
            _station(
                len(stations) + 1,
                OperationType.upsetting,
                graph,
                "通用预成形站",
            )
        )

    required = set(capability_order)
    trace_warnings = list(requirements.warnings)
    if OperationCapability.piercing not in required:
        trace_warnings.append("piercing optional: through_hole not present")

    return CandidatePlan(
        candidate_id=f"{graph.part_id}/{family.family}/dfs_skeleton",
        family=family.family,
        template_id=f"{family.family}/dfs_skeleton",
        part_name_zh=_infer_part_name(graph),
        material=graph.material,
        blank=_blank_from_graph(graph),
        stations=stations,
        source_case_ids=[],
        score_breakdown=_initial_score(family.score),
        search_trace=SearchTrace(
            generated_by="generic_dfs_skeleton_generator",
            matched_features=family.matched_features,
            applied_template_priors=[
                "operation requirements sorted by precedence constraints",
                "compatible polygon/recess capabilities may share a combined station",
            ],
            operation_choices=[
                f"station {station.n}: {station.operation.value}" for station in stations
            ],
            warnings=trace_warnings,
        ),
        rationale_zh="由 primitive features 和 operation precedence 推导的候选站序骨架。",
        confidence=ConfidenceLevel.medium,
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
    max_d = max((value for value in (shank_d, head_d) if value is not None), default=1.0)
    return WorkpieceGeometry(
        type="flanged" if head_d else "stepped",
        overall_length_mm=graph.overall_length_mm,
        max_diameter_mm=max_d,
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


def _topological_capability_order(
    requirements: OperationRequirements,
) -> list[OperationCapability]:
    remaining = {item.capability: item for item in requirements.required}
    ordered: list[OperationCapability] = []

    while remaining:
        ready = [
            capability
            for capability, item in remaining.items()
            if all(dep in ordered or dep not in remaining for dep in item.precedence_after)
        ]
        if not ready:
            raise ValueError("operation precedence cycle detected")
        ready.sort(key=_capability_sort_key)
        selected = ready[0]
        ordered.append(selected)
        del remaining[selected]

    return ordered


def _capability_sort_key(capability: OperationCapability) -> int:
    preferred = [
        OperationCapability.material_gathering,
        OperationCapability.forward_extrusion,
        OperationCapability.backward_extrusion,
        OperationCapability.flange_forming,
        OperationCapability.polygon_head_forming,
        OperationCapability.recess_forming,
        OperationCapability.piercing,
        OperationCapability.trimming_or_sizing,
        OperationCapability.thread_forming,
    ]
    try:
        return preferred.index(capability)
    except ValueError:
        return len(preferred)


def _operation_for_capability(capability: OperationCapability) -> OperationType | None:
    mapping = {
        OperationCapability.material_gathering: OperationType.upsetting,
        OperationCapability.forward_extrusion: OperationType.forward_extrusion,
        OperationCapability.backward_extrusion: OperationType.backward_extrusion,
        OperationCapability.flange_forming: OperationType.heading,
        OperationCapability.polygon_head_forming: OperationType.heading,
        OperationCapability.recess_forming: OperationType.combined,
        OperationCapability.piercing: OperationType.piercing,
        OperationCapability.trimming_or_sizing: OperationType.trimming,
    }
    return mapping.get(capability)


def _purpose_for_capability(capability: OperationCapability) -> str:
    purposes = {
        OperationCapability.material_gathering: "聚集头部/法兰材料",
        OperationCapability.forward_extrusion: "正挤形成杆部与头部台阶坯",
        OperationCapability.backward_extrusion: "反挤形成孔腔或内凹结构",
        OperationCapability.flange_forming: "镦粗/压扁形成头部或法兰预形",
        OperationCapability.polygon_head_forming: "多边形头部成形",
        OperationCapability.recess_forming: "压印凹槽特征",
        OperationCapability.piercing: "冲孔形成通孔或螺纹底孔",
        OperationCapability.trimming_or_sizing: "切边/整形控制关键尺寸",
        OperationCapability.thread_forming: "后续螺纹成形",
    }
    return purposes.get(capability, capability.value)
