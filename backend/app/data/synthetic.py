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
# ISO dimension tables
# ---------------------------------------------------------------------------
# (nominal_dia, pitch, shank_dia, head_dia, head_height, thread_length_ratio)

_ISO_HEX_BOLTS: dict[str, tuple[float, float, float, float, float, float]] = {
    "M4":  (4.0,  0.7,  3.82,  7.0,  2.8, 0.60),
    "M5":  (5.0,  0.8,  4.82,  8.0,  3.5, 0.60),
    "M6":  (6.0,  1.0,  5.82, 10.0,  4.0, 0.65),
    "M8":  (8.0,  1.25, 7.78, 13.0,  5.3, 0.65),
    "M10": (10.0, 1.5,  9.78, 16.0,  6.4, 0.70),
    "M12": (12.0, 1.75, 11.73, 18.0, 7.5, 0.70),
}

_ISO_FLAT_HEAD: dict[str, tuple[float, float, float, float, float, float]] = {
    "M4":  (4.0,  0.7,  3.82,  8.0,  2.2, 0.70),
    "M5":  (5.0,  0.8,  4.82,  9.5,  2.5, 0.70),
    "M6":  (6.0,  1.0,  5.82, 11.5,  3.0, 0.72),
    "M8":  (8.0,  1.25, 7.78, 15.0,  4.0, 0.72),
    "M10": (10.0, 1.5,  9.78, 18.5,  5.0, 0.74),
}

_ISO_SOCKET_CAP: dict[str, tuple[float, float, float, float, float, float]] = {
    "M4":  (4.0,  0.7,  4.0,  7.0,  4.0, 0.65),
    "M5":  (5.0,  0.8,  5.0,  8.5,  5.0, 0.65),
    "M6":  (6.0,  1.0,  6.0, 10.0,  6.0, 0.68),
    "M8":  (8.0,  1.25, 8.0, 13.0,  8.0, 0.70),
    "M10": (10.0, 1.5, 10.0, 16.0, 10.0, 0.72),
}

# (head_type → (table, drive_type, chamfer_angle_deg))
_ISO_TABLES: dict[str, tuple[dict, HeadType, DriveType, float]] = {
    "hex":    (_ISO_HEX_BOLTS,  HeadType.hex,    DriveType.none,       0.0),
    "flat":   (_ISO_FLAT_HEAD,  HeadType.flat,   DriveType.cross,     90.0),
    "socket": (_ISO_SOCKET_CAP, HeadType.socket, DriveType.hex_socket, 0.0),
}

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
    ("SKD11",   60.0, 62.0),
    ("DC53",    62.0, 64.0),
    ("SKH51",   64.0, 66.0),
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

# Station sequences by station count
# For bolts where shank_diameter < blank_diameter × 0.85: add forward_extrusion
_STATION_SEQUENCES: dict[int, list[str]] = {
    1: ["heading"],
    2: ["upsetting", "heading"],
    3: ["upsetting", "heading", "forward_extrusion"],
    4: ["upsetting", "cone_preform", "heading", "forward_extrusion"],
}


def _part_volume(head_d: float, head_h: float, shank_d: float, shank_len: float,
                 thread_d: float, thread_len: float) -> float:
    v_head = math.pi / 4 * head_d**2 * head_h
    v_shank = math.pi / 4 * shank_d**2 * shank_len
    v_thread = math.pi / 4 * thread_d**2 * thread_len
    return v_head + v_shank + v_thread


def _blank_diameter_from_shank(shank_dia: float, rng: random.Random) -> float:
    """Pick blank wire diameter ≥ shank_dia, from standard wire sizes."""
    standard_sizes = [4.0, 4.5, 5.0, 5.5, 5.8, 6.0, 6.2, 6.5, 7.0, 7.5, 8.0, 8.5, 9.0, 10.0, 12.0]
    candidates = [s for s in standard_sizes if s >= shank_dia and s <= shank_dia * 1.12]
    if candidates:
        return rng.choice(candidates)
    # Fallback: next size up
    for s in standard_sizes:
        if s >= shank_dia:
            return s
    return shank_dia * 1.05


class SyntheticDataGenerator:
    """Generate random but physically plausible cold-heading fastener cases."""

    def __init__(self, seed: int | None = None) -> None:
        self._rng = random.Random(seed)

    def generate_part_features(self, seed: int | None = None) -> PartFeatures:
        """Generate random but valid fastener PartFeatures."""
        rng = random.Random(seed) if seed is not None else self._rng

        nom, pitch, head_ratio, shank_tol = rng.choice(_METRIC_SIZES)
        head_type, drive_type, chamfer_angle = rng.choice(_HEAD_TYPES)
        grade = rng.choice(_STRENGTH_GRADES)
        material = _MATERIAL_MAP[grade]

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

    def generate_from_iso(
        self,
        spec: str,
        head_type: str,
        length: float,
        grade: str | None = None,
        surface: str | None = None,
    ) -> PartFeatures:
        """
        Generate PartFeatures from ISO dimension tables.

        Uses exact ISO dimensions as ground truth rather than random values,
        producing physically accurate cases for RAG seeding.

        spec: "M6", "M8", etc.
        head_type: "hex", "flat", "socket"
        length: overall bolt length in mm
        """
        table, h_type, drive, chamfer = _ISO_TABLES[head_type]
        if spec not in table:
            raise ValueError(f"No ISO data for {spec} {head_type} bolt")

        nom, pitch, shank_dia, head_dia, head_height, tl_ratio = table[spec]

        # Ensure thread + head doesn't exceed total length
        thread_len = round(length * tl_ratio, 1)
        available = length - head_height
        if available <= 0:
            # Length too short — pad it
            length = round(head_height * 2.0, 1)
            thread_len = round(length * tl_ratio, 1)
            available = length - head_height
        thread_len = min(thread_len, round(available * 0.9, 1))
        shank_len = max(0.0, round(length - head_height - thread_len, 1))
        grade = grade or self._rng.choice(_STRENGTH_GRADES)
        material = _MATERIAL_MAP.get(grade, "10B21")
        shank_tol = 0.014 + (nom - 3.0) * 0.003

        return PartFeatures(
            part_number=f"ISO-{spec}-{head_type.upper()}-{int(length)}",
            description=f"{spec}×{int(length)} {h_type.value.title()} Head Bolt ({head_type})",
            overall_length=length,
            head=HeadFeatures(
                type=h_type,
                diameter=head_dia,
                height=head_height,
                chamfer_angle_deg=chamfer if chamfer > 0 else None,
                chamfer_diameter=head_dia if chamfer > 0 else None,
                drive_type=drive,
                drive_size=nom * 0.5 if drive != DriveType.none else None,
                underhead_radius=round(nom * 0.05, 2),
            ),
            shank=ShankFeatures(
                diameter=shank_dia,
                length=shank_len,
                diameter_tolerance=Tolerance(
                    nominal=nom, plus=0.0, minus=round(shank_tol, 3)
                ),
            ),
            thread=ThreadFeatures(
                spec=f"{spec}×{pitch}",
                nominal_diameter=nom,
                pitch=pitch,
                length=thread_len,
                thread_class="6g",
            ),
            material_grade=material,
            strength_grade=grade,
            core_hardness_min_hrc=22.0 if grade >= "8.8" else None,
            core_hardness_max_hrc=32.0 if grade >= "8.8" else None,
            surface_treatment=surface or self._rng.choice(_SURFACE_TREATMENTS),
            standard="ISO 4017" if head_type == "hex" else "ISO 10642" if head_type == "flat" else "ISO 4762",
        )

    def generate_process_plan(self, features: PartFeatures) -> ProcessPlan:
        """Generate a plausible forming process plan for the given part features."""
        nom = features.thread.nominal_diameter
        head_d = features.head.diameter
        shank_d = features.shank.diameter

        # Bug fix: use proper blank wire selection from standard sizes
        blank_dia = _blank_diameter_from_shank(shank_d, self._rng)

        # Determine upset ratio and station count
        upset_ratio = head_d / blank_dia
        if upset_ratio <= 2.3:
            n_stations = 2
        elif upset_ratio <= 3.8:
            n_stations = 3
        else:
            n_stations = 4

        # Bug fix: add forward_extrusion if shank is significantly reduced from blank
        needs_extrusion = shank_d < blank_dia * 0.92
        if needs_extrusion and n_stations < 3:
            n_stations = 3

        # Volume conservation for blank length
        head_vol = math.pi / 4 * head_d**2 * features.head.height
        shank_vol = math.pi / 4 * shank_d**2 * (features.shank.length + features.thread.length)
        total_vol = head_vol + shank_vol
        blank_length = round(total_vol / (math.pi / 4 * blank_dia**2) * 1.02, 1)
        blank_length = max(blank_length, features.overall_length * 1.05)

        # Station sequence
        sequence = _STATION_SEQUENCES.get(n_stations, _STATION_SEQUENCES[3])

        blank_shape = ShapeDescription(
            overall_length=blank_length,
            max_diameter=blank_dia,
            shank_diameter=blank_dia,
            shank_length=blank_length,
        )

        stations: list[StationPlan] = []
        prev_shape = blank_shape

        for i, op_name in enumerate(sequence):
            frac = (i + 1) / len(sequence)
            is_extrusion = "extrusion" in op_name
            is_last = i == len(sequence) - 1

            if is_extrusion:
                op = OperationType.forward_extrusion
                out_shank_d = shank_d
                out_head_d = head_d * min(frac, 0.8)
                out_head_h = features.head.height * min(frac, 0.8)
            elif op_name == "cone_preform":
                op = OperationType.upsetting
                out_shank_d = max(shank_d, blank_dia - (blank_dia - shank_d) * 0.3)
                out_head_d = head_d * 0.6
                out_head_h = features.head.height * 0.4
            elif op_name == "upsetting":
                op = OperationType.upsetting
                out_shank_d = max(shank_d, blank_dia - (blank_dia - shank_d) * 0.3)
                out_head_d = head_d * 0.7
                out_head_h = features.head.height * 0.5
            else:
                op = OperationType.heading
                out_shank_d = shank_d
                out_head_d = head_d
                out_head_h = features.head.height

            out_length = features.overall_length * 0.95 + blank_length * 0.05 * (1 - frac)
            out_shape = ShapeDescription(
                overall_length=round(out_length, 1),
                max_diameter=round(max(out_head_d, out_shank_d), 2),
                head_diameter=round(out_head_d, 2),
                head_height=round(out_head_h, 2),
                shank_diameter=round(out_shank_d, 3),
                shank_length=round(out_length - out_head_h, 1),
            )

            station_upset_ratio = round(
                out_shape.max_diameter / prev_shape.max_diameter, 2
            ) if prev_shape.max_diameter > 0 else 1.0

            stations.append(StationPlan(
                station_number=i + 1,
                operation=op,
                description=f"Station {i + 1}: {op.value.replace('_', ' ').title()}",
                input_shape=prev_shape,
                output_shape=out_shape,
                upset_ratio=min(station_upset_ratio, 2.3),
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
            reasoning_summary=(
                f"Auto-generated: {n_stations}-station process for M{nom:.0f} {features.head.type.value} head, "
                f"upset_ratio={upset_ratio:.2f}, blank={blank_dia}mm wire"
            ),
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
            op = station.operation

            bore_id = round(plan.blank_diameter * 1.008, 3)

            # Bug fix 4: die OD must be 2.8–3.6× bore ID (never < 2.5×)
            die_od = round(bore_id * self._rng.uniform(2.8, 3.6), 1)

            # Bug fix 2: punch OD by operation type
            if op == OperationType.heading:
                punch_od = round(head_d * self._rng.uniform(0.988, 0.992), 3)
                punch_geo = DieGeometryType.conical
                punch_approach = round(self._rng.uniform(30.0, 60.0), 1)
            elif op == OperationType.forward_extrusion:
                punch_od = round(shank_d * self._rng.uniform(1.000, 1.005), 3)
                punch_geo = DieGeometryType.flat_face
                punch_approach = None
            else:
                # upsetting / cone_preform
                punch_od = round(head_d * self._rng.uniform(0.988, 0.992), 3)
                punch_geo = DieGeometryType.flat_face
                punch_approach = None

            # Bug fix 1: approach_angle by die type
            if op == OperationType.forward_extrusion:
                die_geo = DieGeometryType.conical
                die_approach = round(self._rng.uniform(10.0, 15.0), 1)
            elif op == OperationType.heading:
                die_geo = DieGeometryType.closed_heading
                die_approach = round(self._rng.uniform(40.0, 70.0), 1)
            else:
                die_geo = DieGeometryType.open_heading
                die_approach = None

            # Bug fix 5: working length must be longer than part
            working_length = round(features.overall_length * self._rng.uniform(1.1, 1.4), 1)

            coating = self._rng.choice(["TiN", "TiCN", None])

            punch = DieComponentParams(
                component_type="punch",
                material=die_mat,
                hardness_hrc_min=hrc_min,
                hardness_hrc_max=hrc_max,
                geometry_type=punch_geo,
                outer_diameter=punch_od,
                working_length=working_length,
                approach_angle_deg=punch_approach,
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
                geometry_type=die_geo,
                outer_diameter=die_od,
                inner_diameter=bore_id,
                working_length=working_length,
                cavity_depth=round(head_h * 1.05, 2) if op == OperationType.heading else None,
                approach_angle_deg=die_approach,
                land_length=round(shank_d * 0.8, 1),
                surface_roughness_ra=0.2,
                surface_treatment=coating,
                coating_thickness_um=3.0 if coating else None,
            )

            clearance = round(shank_d * self._rng.uniform(0.003, 0.008), 3)
            clearance = max(clearance, 0.005)

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
        features = self.generate_part_features(seed)
        plan = self.generate_process_plan(features)
        die_params = self.generate_die_parameters(features, plan)
        return self._assemble_case(features, plan, die_params)

    def generate_iso_case(
        self,
        spec: str,
        head_type: str,
        length: float,
        grade: str | None = None,
    ) -> RAGCase:
        """
        Generate a complete case from ISO tables.

        Produces higher-quality seed data than pure random generation
        because dimensions match real ISO standards.
        """
        features = self.generate_from_iso(spec, head_type, length, grade)
        plan = self.generate_process_plan(features)
        die_params = self.generate_die_parameters(features, plan)
        return self._assemble_case(features, plan, die_params, confidence=ConfidenceLevel.high)

    def _assemble_case(
        self,
        features: PartFeatures,
        plan: ProcessPlan,
        die_params: list[DieParameters],
        confidence: ConfidenceLevel = ConfidenceLevel.medium,
    ) -> RAGCase:
        upset_ratio = features.head.diameter / plan.blank_diameter

        embedding_text = (
            f"{features.head.type.value} head bolt {features.thread.spec} "
            f"L={features.overall_length}mm material={features.material_grade} "
            f"grade={features.strength_grade} stations={plan.total_stations} "
            f"blank={plan.blank_diameter}dia×{plan.blank_length}L "
            f"upset_ratio={upset_ratio:.2f}"
        )

        reasoning = PseudoReasoning(
            stock_selection=(
                f"Wire dia {plan.blank_diameter}mm chosen for M{features.thread.nominal_diameter:.0f} "
                f"(shank {features.shank.diameter}mm); within 1.12× limit"
            ),
            station_count_reasoning=(
                f"Upset ratio {upset_ratio:.2f}× → "
                f"{'1 station' if upset_ratio <= 2.3 else '2 stations (preform + finish)' if upset_ratio <= 3.8 else '3+ stations'}"
            ),
            deformation_sequence=" → ".join(s.operation.value for s in plan.stations),
            die_material_selection=f"{die_params[0].die.material} selected for {features.strength_grade} grade workpiece",
            critical_features=[f"Head diameter ⌀{features.head.diameter}", f"Thread {features.thread.spec}"],
            known_challenges=["Head fill", "Dimensional consistency"],
            confidence=confidence,
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
            confidence=confidence,
            created_at=datetime.now(UTC),
        )

    def generate_batch(self, n: int) -> list[RAGCase]:
        """Generate n diverse synthetic cases."""
        return [self.generate_complete_case(seed=i) for i in range(n)]
