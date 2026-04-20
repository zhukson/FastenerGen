"""
Synthetic fastener data generator.

Generates random but physically plausible product-die pairs for testing
and RAG pre-seeding. Used before real factory data is available.

All generated cases follow real cold-heading engineering constraints:
- Head diameter ≥ 1.6× shank diameter (typical cold-heading rule)
- Upset ratio D/d ≤ 2.3 per station
- Volume conservation (blank ≈ finished part)
- Material/hardness combinations that actually exist
"""

from __future__ import annotations

import math
import random
import uuid
from datetime import UTC, datetime
from typing import Any

from app.data.schemas import (
    ConfidenceLevel,
    DieComponentParams,
    DieGeometryType,
    DieParameters,
    DriveType,
    HeadFeatures,
    HeadType,
    OperationType,
    PartFeatures,
    PostProcess,
    ProcessPlan,
    PseudoReasoning,
    RAGCase,
    ShankFeatures,
    ShapeDescription,
    StationPlan,
    TailFeatures,
    TailType,
    ThreadFeatures,
    Tolerance,
)

# ---------------------------------------------------------------------------
# Engineering data tables
# ---------------------------------------------------------------------------

# (nominal_dia, pitch, head_ratio, shank_tol)
_METRIC_SIZES: list[tuple[float, float, float, float]] = [
    (3.0, 0.5, 1.7, 0.014),
    (4.0, 0.7, 1.8, 0.018),
    (5.0, 0.8, 1.9, 0.018),
    (6.0, 1.0, 2.0, 0.022),
    (8.0, 1.25, 2.0, 0.027),
    (10.0, 1.5, 2.1, 0.027),
    (12.0, 1.75, 2.0, 0.033),
]

_HEAD_TYPES: list[tuple[HeadType, DriveType, float]] = [
    # (head_type, drive, chamfer_angle)
    (HeadType.flat, DriveType.cross, 90.0),
    (HeadType.hex, DriveType.none, 0.0),
    (HeadType.button, DriveType.hex_socket, 0.0),
    (HeadType.pan, DriveType.cross, 0.0),
    (HeadType.socket, DriveType.hex_socket, 0.0),
    (HeadType.flange, DriveType.none, 0.0),
]

_MATERIAL_MAP: dict[str, str] = {
    "4.8": "C1008",
    "5.8": "C1010",
    "6.8": "10B21",
    "8.8": "10B21",
    "10.9": "SCM435",
    "12.9": "SCM440",
}

_STRENGTH_GRADES = list(_MATERIAL_MAP.keys())

_DIE_MATERIALS: list[tuple[str, float, float]] = [
    # (material, hrc_min, hrc_max)
    ("SKD11", 60.0, 62.0),
    ("DC53",  62.0, 64.0),
    ("SKH51", 64.0, 66.0),
    ("ASP2030", 66.0, 68.0),
]

_SURFACE_TREATMENTS = [
    "三价蓝白锌8μm",
    "镀锌钝化",
    "达克罗",
    "磷化",
    "发黑",
    None,
]


class SyntheticDataGenerator:
    """Generate random but physically plausible cold-heading fastener cases."""

    def __init__(self, seed: int | None = None) -> None:
        self._rng = random.Random(seed)

    def generate_part_features(self, seed: int | None = None) -> PartFeatures:
        """Generate random but valid fastener PartFeatures."""
        rng = random.Random(seed) if seed is not None else self._rng

        # Pick random size and head type
        nom, pitch, head_ratio, shank_tol = rng.choice(_METRIC_SIZES)
        head_type, drive_type, chamfer_angle = rng.choice(_HEAD_TYPES)
        grade = rng.choice(_STRENGTH_GRADES)
        material = _MATERIAL_MAP[grade]

        # Length: 10-80mm for M3-M12
        total_length = rng.uniform(nom * 3, nom * 15)
        total_length = round(total_length / 0.5) * 0.5

        head_d = round(nom * head_ratio * rng.uniform(0.95, 1.05), 1)
        head_h = round(nom * rng.uniform(0.55, 0.75), 1)

        shank_length = max(0.0, round(total_length * rng.uniform(0.15, 0.35), 1))
        thread_length = round(total_length - head_h - shank_length, 1)
        thread_length = max(thread_length, nom * 1.5)

        return PartFeatures(
            part_number=f"SYN-{nom:.0f}-{int(total_length):03d}",
            description=f"M{nom:.0f}×{int(total_length)} {head_type.value.title()} Head Bolt",
            overall_length=total_length,
            head=HeadFeatures(
                type=head_type,
                diameter=head_d,
                height=head_h,
                chamfer_angle_deg=chamfer_angle if chamfer_angle > 0 else None,
                chamfer_diameter=head_d if chamfer_angle > 0 else None,
                drive_type=drive_type,
                drive_size=nom * 0.5 if drive_type != DriveType.none else None,
                underhead_radius=round(nom * 0.05, 2),
            ),
            shank=ShankFeatures(
                diameter=nom,
                length=shank_length,
                diameter_tolerance=Tolerance(
                    nominal=nom, plus=0.0, minus=shank_tol
                ),
            ),
            thread=ThreadFeatures(
                spec=f"M{nom:.0f}×{pitch}",
                nominal_diameter=nom,
                pitch=pitch,
                length=thread_length,
                thread_class="6g",
            ),
            material_grade=material,
            strength_grade=grade,
            core_hardness_min_hrc=22.0 if grade >= "8.8" else None,
            core_hardness_max_hrc=32.0 if grade >= "8.8" else None,
            surface_treatment=rng.choice(_SURFACE_TREATMENTS),
            standard=rng.choice(["GB/T 5789", "GB/T 70.1", "DIN 912", None]),
        )

    def generate_process_plan(self, features: PartFeatures) -> ProcessPlan:
        """Generate a plausible forming process plan for the given part features."""
        nom = features.thread.nominal_diameter
        head_d = features.head.diameter
        shank_d = features.shank.diameter

        # Blank diameter: slightly larger than shank (wire stock)
        blank_dia = round(shank_d * self._rng.uniform(1.02, 1.06), 2)
        blank_vol = math.pi * (blank_dia / 2) ** 2 * 200  # rough estimate

        # Determine station count based on upset ratio
        max_upset = head_d / blank_dia
        if max_upset <= 2.2:
            n_stations = 2
        elif max_upset <= 2.8:
            n_stations = 3
        else:
            n_stations = 4

        # Blank volume ≈ finished part volume (rough)
        shank_vol = math.pi * (shank_d / 2) ** 2 * (features.shank.length + features.thread.length)
        head_vol = math.pi * (head_d / 2) ** 2 * features.head.height
        total_vol = shank_vol + head_vol
        blank_length = round(total_vol / (math.pi * (blank_dia / 2) ** 2) * 1.02, 1)  # +2% for scrap
        blank_length = max(blank_length, features.overall_length * 1.05)

        # Build stations
        blank_shape = ShapeDescription(
            overall_length=blank_length,
            max_diameter=blank_dia,
            shank_diameter=blank_dia,
            shank_length=blank_length,
        )

        stations: list[StationPlan] = []
        prev_shape = blank_shape

        for i in range(n_stations):
            frac = (i + 1) / n_stations
            out_head_d = head_d * frac if i < n_stations - 1 else head_d
            out_head_h = features.head.height * frac if i < n_stations - 1 else features.head.height
            out_shank_d = max(shank_d, blank_dia - (blank_dia - shank_d) * frac)
            out_length = features.overall_length * 0.95 + blank_length * 0.05 * (1 - frac)

            out_shape = ShapeDescription(
                overall_length=round(out_length, 1),
                max_diameter=round(max(out_head_d, out_shank_d), 2),
                head_diameter=round(out_head_d, 2),
                head_height=round(out_head_h, 2),
                shank_diameter=round(out_shank_d, 3),
                shank_length=round(out_length - out_head_h, 1),
            )

            op = OperationType.upsetting if i == 0 else OperationType.heading
            upset_ratio = round(out_head_d / prev_shape.max_diameter, 2)
            upset_ratio = min(upset_ratio, 2.2)

            stations.append(StationPlan(
                station_number=i + 1,
                operation=op,
                description=f"Station {i + 1}: {op.value.replace('_', ' ').title()}",
                input_shape=prev_shape,
                output_shape=out_shape,
                upset_ratio=upset_ratio,
            ))
            prev_shape = out_shape

        post: list[PostProcess] = [PostProcess.thread_rolling]
        surface = features.surface_treatment
        if surface:
            if "锌" in surface or "zinc" in surface.lower():
                post.append(PostProcess.zinc_plating)
            elif "磷" in surface:
                post.append(PostProcess.phosphating)

        return ProcessPlan(
            total_stations=n_stations,
            blank_diameter=blank_dia,
            blank_length=blank_length,
            stations=stations,
            post_processes=post,
            confidence=ConfidenceLevel.medium,
            reasoning_summary=f"Auto-generated: {n_stations}-station process for M{nom:.0f} {features.head.type.value} head",
        )

    def generate_die_parameters(
        self, features: PartFeatures, plan: ProcessPlan
    ) -> list[DieParameters]:
        """Generate plausible die parameters for each station in the plan."""
        params: list[DieParameters] = []
        die_mat, hrc_min, hrc_max = self._rng.choice(_DIE_MATERIALS)

        for station in plan.stations:
            shank_d = station.output_shape.shank_diameter or features.shank.diameter
            head_d = station.output_shape.head_diameter or features.head.diameter
            head_h = station.output_shape.head_height or features.head.height

            # Die OD: much larger than head for structural integrity
            die_od = round(head_d * self._rng.uniform(2.5, 3.5), 1)
            punch_od = round(head_d * self._rng.uniform(1.1, 1.4), 1)
            punch_wd = punch_od

            is_last = station.station_number == plan.total_stations
            geo = DieGeometryType.closed_heading if is_last else DieGeometryType.open_heading
            punch_geo = DieGeometryType.conical if is_last else DieGeometryType.flat_face
            approach = 90.0  # approach_angle_deg max is 90 per schema
            coating = self._rng.choice(["TiN", "TiCN", None])

            punch = DieComponentParams(
                component_type="punch",
                material=die_mat,
                hardness_hrc_min=hrc_min,
                hardness_hrc_max=hrc_max,
                geometry_type=punch_geo,
                outer_diameter=punch_od,
                working_length=round(features.overall_length * 1.2, 1),
                approach_angle_deg=approach if is_last else None,
                land_length=round(shank_d * 0.5, 1),
                surface_roughness_ra=0.2,
                surface_treatment=coating,
                coating_thickness_um=3.0 if coating else None,
            )
            die = DieComponentParams(
                component_type="die",
                material=die_mat,
                hardness_hrc_min=hrc_min,
                hardness_hrc_max=hrc_max,
                geometry_type=geo,
                outer_diameter=die_od,
                inner_diameter=round(shank_d * 1.02, 3),
                working_length=round(features.overall_length * 1.1, 1),
                cavity_depth=round(head_h * 1.05, 2) if is_last else None,
                approach_angle_deg=approach if is_last else 15.0,
                land_length=round(shank_d * 0.8, 1),
                surface_roughness_ra=0.2,
                surface_treatment=coating,
                coating_thickness_um=3.0 if coating else None,
            )

            clearance = round(shank_d * self._rng.uniform(0.008, 0.015), 3)

            params.append(DieParameters(
                station_number=station.station_number,
                punch=punch,
                die=die,
                clearance_mm=clearance,
                expected_life_shots=self._rng.randint(60_000, 200_000),
            ))

        return params

    def generate_complete_case(self, seed: int | None = None) -> RAGCase:
        """Generate a complete synthetic case suitable for RAG indexing."""
        rng = random.Random(seed) if seed is not None else self._rng

        features = self.generate_part_features(seed)
        plan = self.generate_process_plan(features)
        die_params = self.generate_die_parameters(features, plan)

        embedding_text = (
            f"{features.head.type.value} head bolt {features.thread.spec} "
            f"L={features.overall_length}mm material={features.material_grade} "
            f"grade={features.strength_grade} stations={plan.total_stations} "
            f"blank={plan.blank_diameter}dia×{plan.blank_length}L"
        )

        reasoning = PseudoReasoning(
            stock_selection=f"Wire dia {plan.blank_diameter}mm chosen for M{features.thread.nominal_diameter:.0f} with {plan.total_stations}-station process",
            station_count_reasoning=f"Upset ratio {features.head.diameter / plan.blank_diameter:.2f}× requires {plan.total_stations} stations",
            deformation_sequence=" → ".join(s.operation.value for s in plan.stations),
            die_material_selection=f"{die_params[0].die.material} selected for {features.strength_grade} grade workpiece",
            critical_features=[f"Head diameter ⌀{features.head.diameter}", f"Thread {features.thread.spec}"],
            known_challenges=["Head fill", "Dimensional consistency"],
            confidence=ConfidenceLevel.medium,
            cross_validation_agreement=None,
        )

        return RAGCase(
            case_id=str(uuid.uuid4()),
            order_id=f"SYN-{uuid.uuid4().hex[:8].upper()}",
            embedding_text=embedding_text,
            part_features=features,
            process_plan=plan,
            die_parameters=die_params,
            pseudo_reasoning=reasoning,
            confidence=ConfidenceLevel.medium,
            created_at=datetime.now(UTC),
        )

    def generate_batch(self, n: int) -> list[RAGCase]:
        """Generate n diverse synthetic cases."""
        return [self.generate_complete_case(seed=i) for i in range(n)]
