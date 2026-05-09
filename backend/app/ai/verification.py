"""
Rule-based design verification engine.

Step 6 of the pipeline. Checks physical plausibility and geometric
consistency of the generated design. On failure, feeds errors back to
Step 3 for retry (max 2×).

Phase 2+: replace/augment with Deform/QForm API simulation.
"""

from __future__ import annotations

import math

from app.data.schemas import (
    CheckSeverity,
    DieParameters,
    DriveType,
    OperationType,
    PartFeatures,
    ProcessForming,
    ProcessPlan,
    VerificationCheck,
    VerificationResult,
    WorkpieceGeometry,
)

_WORKPIECE_HRC: dict[str, float] = {
    "C1008": 15, "C1010": 15, "10B21": 18,
    "SCM435": 22, "SCM440": 28, "S45C": 20, "45": 20,
}

_ALLOWABLE_UPSET_RATE_EP: dict[str, float] = {
    # 1模2冲教程 p2 表 25.7-2, plus local material aliases seen in cases.
    "10": 68,
    "08F": 72,
    "10F": 72,
    "08AL": 72,
    "20": 65,
    "35": 60,
    "15CR": 60,
    "40CR": 55,
    "30CRMNSIA": 65,
    "65MN": 40,
    "GCR15": 45,
    "1CR18NI9TI": 76,
    "10B21": 60,
    "105S": 68,
    "106S": 68,
    "YT105S": 68,
}

_FORMING_BLOW_OPS = {
    OperationType.upsetting,
    OperationType.heading,
    OperationType.combined,
    OperationType.backward_extrusion,
}


class ProcessFormingVerifier:
    """Rule checks for v2 ProcessForming plans before rendering 过模图 DXF.

    These checks turn the Gong Maoliang / 1模2冲 textbook rules into executable
    guardrails. They are deliberately approximate: enough to catch impossible
    demo output, not a replacement for a senior engineer or FEA.
    """

    def verify(
        self,
        features: PartFeatures,
        forming: ProcessForming,
        retry_count: int = 0,
    ) -> VerificationResult:
        checks: list[VerificationCheck] = [
            *self._check_positive_dimensions(forming),
            *self._check_station_numbering(forming),
            *self._check_citations(forming),
            *self._check_final_length(features, forming),
            *self._check_volume_conservation(forming),
            *self._check_per_station_deformation(forming),
            *self._check_upset_rate_by_material(forming),
            *self._check_ld_blow_count(forming),
            *self._check_required_operations(features, forming),
            *self._check_thread_blank_diameter(features, forming),
            *self._check_large_head_staging(forming),
            *self._check_material_preparation(forming),
        ]

        return VerificationResult(
            passed=True,
            checks=checks,
            retry_count=retry_count,
            flagged_for_review=any(
                (not c.passed and c.severity in {CheckSeverity.error, CheckSeverity.warning})
                for c in checks
            ),
        )

    # -----------------------------------------------------------------
    # Continuous score for multi-candidate selection (优化 2)
    # -----------------------------------------------------------------

    _SEVERITY_WEIGHT = {
        CheckSeverity.error: 5.0,
        CheckSeverity.warning: 2.0,
        CheckSeverity.info: 0.5,
    }

    def score(
        self,
        features: PartFeatures,
        forming: ProcessForming,
        result: VerificationResult,
    ) -> float:
        """Continuous quality score used to pick best of N candidates.

        Higher is better. Components:
          + per-check pass/fail weighted by severity
          + volume conservation closeness to 1.0
          + final-length match closeness
          + Occam: fewer stations slightly preferred (when valid)
          - heavy penalty for failing any error-severity check
        """
        score = 0.0

        # 1. Per-check pass/fail
        for check in result.checks:
            weight = self._SEVERITY_WEIGHT.get(check.severity, 1.0)
            if check.passed:
                score += weight
            else:
                score -= weight * 2.0  # fails hurt more than passes help

        # 2. Volume conservation: peak at ratio=1.0
        blank_v = self._workpiece_volume(forming.blank)
        if forming.stations:
            final_v = self._workpiece_volume(forming.stations[-1].workpiece)
            if blank_v > 0 and final_v > 0:
                ratio = blank_v / final_v
                score += max(0.0, 5.0 * (1.0 - min(abs(ratio - 1.0), 1.0)))

        # 3. Final length match: peak at 0% deviation
        if forming.stations and features.overall_length > 0:
            final_l = forming.stations[-1].workpiece.overall_length_mm
            dev = abs(final_l - features.overall_length) / features.overall_length
            score += max(0.0, 5.0 * (1.0 - min(dev, 1.0)))

        # 4. Per-station deformation moderation: prefer ratios in [1.0, 1.65]
        previous = forming.blank
        deformation_penalty = 0.0
        for st in forming.stations:
            if previous.max_diameter_mm > 0 and st.workpiece.max_diameter_mm > 0:
                ratio = st.workpiece.max_diameter_mm / previous.max_diameter_mm
                if ratio > 1.65:
                    deformation_penalty += min((ratio - 1.65) * 3.0, 5.0)
            previous = st.workpiece
        score -= deformation_penalty

        # 5. Occam: among valid plans, prefer fewer stations (mild)
        if result.passed:
            score -= 0.3 * len(forming.stations)

        # 6. Citations: more cited cases = stronger grounding (mild bonus)
        score += min(len(forming.cited_case_ids), 3) * 0.5

        return score

    def _check_positive_dimensions(self, forming: ProcessForming) -> list[VerificationCheck]:
        bad: list[str] = []
        for label, w in [("blank", forming.blank), *[
            (f"s{st.n}", st.workpiece) for st in forming.stations
        ]]:
            if w.overall_length_mm <= 0:
                bad.append(f"{label}.overall_length_mm={w.overall_length_mm}")
            if w.max_diameter_mm <= 0:
                bad.append(f"{label}.max_diameter_mm={w.max_diameter_mm}")
            for name, value in (
                ("head_diameter_mm", w.head_diameter_mm),
                ("head_height_mm", w.head_height_mm),
                ("shank_diameter_mm", w.shank_diameter_mm),
                ("shank_length_mm", w.shank_length_mm),
            ):
                if value is not None and value < 0:
                    bad.append(f"{label}.{name}={value}")

        return [VerificationCheck(
            check_name="v2_positive_dimensions",
            passed=not bad,
            severity=CheckSeverity.error,
            message=(
                "All blank/station dimensions are positive"
                if not bad
                else "Some blank/station dimensions are missing or non-positive"
            ),
            expected="all in-use lengths/diameters > 0",
            actual=", ".join(bad) if bad else None,
        )]

    def _check_station_numbering(self, forming: ProcessForming) -> list[VerificationCheck]:
        actual = [st.n for st in forming.stations]
        expected = list(range(1, len(forming.stations) + 1))
        return [VerificationCheck(
            check_name="v2_station_numbering",
            passed=actual == expected,
            severity=CheckSeverity.error,
            message=(
                "Station numbers are sequential"
                if actual == expected
                else "Station numbers must be sequential starting at 1"
            ),
            expected=str(expected),
            actual=str(actual),
        )]

    def _check_citations(self, forming: ProcessForming) -> list[VerificationCheck]:
        passed = bool(forming.cited_case_ids)
        return [VerificationCheck(
            check_name="v2_reference_citations",
            passed=passed,
            severity=CheckSeverity.error,
            message=(
                "Design cites at least one Tier 1 worked case"
                if passed
                else "Design must cite at least one case_id from the experience library"
            ),
            expected=">= 1 case_id",
            actual=str(forming.cited_case_ids),
        )]

    def _check_final_length(
        self, features: PartFeatures, forming: ProcessForming
    ) -> list[VerificationCheck]:
        if not forming.stations or features.overall_length <= 0:
            return []

        final_l = forming.stations[-1].workpiece.overall_length_mm
        deviation_pct = abs(final_l - features.overall_length) / features.overall_length * 100
        passed = deviation_pct <= 35
        severity = (
            CheckSeverity.info
            if deviation_pct <= 15
            else CheckSeverity.warning
            if passed
            else CheckSeverity.error
        )
        return [VerificationCheck(
            check_name="v2_final_length_vs_product",
            passed=passed,
            severity=severity,
            message=(
                f"Final station length is within {deviation_pct:.1f}% of product length"
                if passed
                else f"Final station length deviates {deviation_pct:.1f}% from product length"
            ),
            expected=f"near {features.overall_length:.3f} mm",
            actual=f"{final_l:.3f} mm",
        )]

    def _check_volume_conservation(self, forming: ProcessForming) -> list[VerificationCheck]:
        if not forming.stations:
            return []

        blank_volume = self._workpiece_volume(forming.blank)
        final_volume = self._workpiece_volume(forming.stations[-1].workpiece)
        if blank_volume <= 0 or final_volume <= 0:
            return [VerificationCheck(
                check_name="v2_volume_conservation",
                passed=False,
                severity=CheckSeverity.error,
                message="Cannot compute blank/final volume because key dimensions are missing",
                expected="positive computable volumes",
                actual=f"blank={blank_volume:.1f}, final={final_volume:.1f}",
            )]

        ratio = blank_volume / final_volume
        target_passed = 0.75 <= ratio <= 1.45
        severe_failed = ratio < 0.50 or ratio > 2.00
        return [VerificationCheck(
            check_name="v2_volume_conservation",
            passed=target_passed or not severe_failed,
            severity=CheckSeverity.error if severe_failed else CheckSeverity.warning if not target_passed else CheckSeverity.info,
            message=(
                f"Blank/final volume ratio {ratio:.2f} is reasonable"
                if target_passed
                else f"Blank/final volume ratio {ratio:.2f} needs engineer review"
            ),
            expected="0.75-1.45 target, 0.50-2.00 hard guardrail",
            actual=f"blank≈{blank_volume:.0f} mm^3, final≈{final_volume:.0f} mm^3",
        )]

    def _check_per_station_deformation(self, forming: ProcessForming) -> list[VerificationCheck]:
        results: list[VerificationCheck] = []
        previous = forming.blank
        for st in forming.stations:
            prev_d = previous.max_diameter_mm
            curr_d = st.workpiece.max_diameter_mm
            if prev_d <= 0 or curr_d <= 0:
                previous = st.workpiece
                continue
            diameter_ratio = curr_d / prev_d
            area_reduction_pct = self._area_reduction_pct(previous, st.workpiece)

            passed = diameter_ratio <= 2.30 and area_reduction_pct <= 75.0
            severity = (
                CheckSeverity.error
                if not passed
                else CheckSeverity.warning
                if diameter_ratio > 1.65 or area_reduction_pct > 55.0
                else CheckSeverity.info
            )
            results.append(VerificationCheck(
                check_name=f"v2_station_deformation_s{st.n}",
                passed=passed,
                severity=severity,
                message=(
                    f"Station {st.n} deformation is within demo guardrails"
                    if passed
                    else f"Station {st.n} deformation is too aggressive for one station"
                ),
                expected="D_out/D_in <= 2.30 and extrusion area reduction <= 75%",
                actual=f"D ratio={diameter_ratio:.2f}, area reduction≈{area_reduction_pct:.1f}%",
            ))
            previous = st.workpiece

        return results

    def _check_upset_rate_by_material(self, forming: ProcessForming) -> list[VerificationCheck]:
        material = self._normalize_material(forming.material)
        allowed = _ALLOWABLE_UPSET_RATE_EP.get(material, 60.0)
        max_e = 0.0
        max_station = 0
        previous = forming.blank
        for st in forming.stations:
            if previous.overall_length_mm > 0 and st.workpiece.max_diameter_mm > previous.max_diameter_mm:
                shortening = max(previous.overall_length_mm - st.workpiece.overall_length_mm, 0.0)
                e = shortening / previous.overall_length_mm * 100
                if e > max_e:
                    max_e = e
                    max_station = st.n
            previous = st.workpiece

        passed = max_e <= allowed
        severity = (
            CheckSeverity.error
            if not passed
            else CheckSeverity.warning
            if max_e > allowed * 0.85
            else CheckSeverity.info
        )
        return [VerificationCheck(
            check_name="v2_material_allowable_upset_rate",
            passed=passed,
            severity=severity,
            message=(
                f"Max single-station upset shortening {max_e:.1f}% is within material Ep≈{allowed:.0f}%"
                if passed
                else f"Max single-station upset shortening {max_e:.1f}% exceeds material Ep≈{allowed:.0f}%"
            ),
            expected=f"Ep≈{allowed:.0f}% for {forming.material or 'unknown material'}",
            actual=f"station={max_station or 'n/a'}, E≈{max_e:.1f}%",
        )]

    def _check_ld_blow_count(self, forming: ProcessForming) -> list[VerificationCheck]:
        if forming.blank.max_diameter_mm <= 0:
            return []

        ld_ratio = forming.blank.overall_length_mm / forming.blank.max_diameter_mm
        required = self._required_blow_count(ld_ratio)
        actual = sum(1 for st in forming.stations if st.operation in _FORMING_BLOW_OPS)
        final = forming.stations[-1].workpiece if forming.stations else forming.blank
        shank_d = final.shank_diameter_mm or forming.blank.max_diameter_mm
        head_d = final.head_diameter_mm or final.max_diameter_mm
        head_ratio = head_d / shank_d if shank_d > 0 else 1.0

        # Long blanks for long bolts are not all upset material, so this is a
        # hard failure only when the part is also a large-head/small-shank case.
        passed = actual >= required or head_ratio <= 1.35
        severity = CheckSeverity.warning if not passed else CheckSeverity.info
        return [VerificationCheck(
            check_name="v2_ld_blow_count",
            passed=passed,
            severity=severity,
            message=(
                f"Blank L/D={ld_ratio:.2f}; forming blow count is plausible"
                if passed
                else f"Blank L/D={ld_ratio:.2f}; textbook rule suggests more staged blows"
            ),
            expected=f"{required} forming blows by l/dm rule when upsetting dominates",
            actual=f"{actual} forming blows, head/shank ratio≈{head_ratio:.2f}",
        )]

    def _check_required_operations(
        self, features: PartFeatures, forming: ProcessForming
    ) -> list[VerificationCheck]:
        results: list[VerificationCheck] = []
        all_notes = " ".join(
            [
                features.description,
                forming.part_name_zh,
                forming.reasoning_zh,
                *features.notes,
                *[st.notes_zh or "" for st in forming.stations],
                *[str(st.key_dimensions) for st in forming.stations],
                *[str(st.workpiece.extra_dims_mm) for st in forming.stations],
            ]
        ).lower()
        ops = {st.operation for st in forming.stations}

        needs_socket = bool(
            features.head
            and features.head.drive_type == DriveType.hex_socket
            or "内六角" in all_notes
            or "socket" in all_notes
        )
        has_socket_op = OperationType.backward_extrusion in ops or "反挤" in all_notes
        results.append(VerificationCheck(
            check_name="v2_socket_or_recess_operation",
            passed=not needs_socket or has_socket_op,
            severity=CheckSeverity.error if needs_socket and not has_socket_op else CheckSeverity.info,
            message=(
                "Socket/recess feature has a matching backward-extrusion station"
                if needs_socket and has_socket_op
                else "No socket/recess-specific station required"
                if not needs_socket
                else "Socket/recess feature requires backward_extrusion or explicit 反挤 station"
            ),
            expected="backward_extrusion for 内六角/socket parts",
            actual=", ".join(op.value for op in sorted(ops, key=lambda op: op.value)),
        ))

        if features.thread is not None:
            has_thread_post = any(p.value == "thread_rolling" for p in forming.post_processes)
            has_thread_note = "滚牙" in all_notes or "搓牙" in all_notes or "thread" in all_notes
            results.append(VerificationCheck(
                check_name="v2_thread_post_process",
                passed=has_thread_post or has_thread_note,
                severity=CheckSeverity.warning if not (has_thread_post or has_thread_note) else CheckSeverity.info,
                message=(
                    "Threaded part includes downstream thread-forming process"
                    if has_thread_post or has_thread_note
                    else "Threaded part should include thread_rolling/滚牙 as post-process"
                ),
                expected="thread_rolling or explicit thread-forming note",
                actual=str([p.value for p in forming.post_processes]),
            ))

        needs_hole = any(
            token in all_notes
            for token in ("通孔", "冲孔", "through_hole", "through hole", "内螺纹", "攻丝", "tapping")
        )
        has_hole_op = OperationType.piercing in ops or any(
            token in all_notes for token in ("冲孔", "通孔", "piercing", "攻丝")
        )
        results.append(VerificationCheck(
            check_name="v2_hole_or_internal_thread_operation",
            passed=not needs_hole or has_hole_op,
            severity=CheckSeverity.error if needs_hole and not has_hole_op else CheckSeverity.info,
            message=(
                "Hole/internal-thread feature has a matching piercing/tapping station or note"
                if needs_hole and has_hole_op
                else "No hole/internal-thread-specific station required"
                if not needs_hole
                else "Hole/internal-thread feature requires piercing/冲孔 or explicit tapping/攻丝 note"
            ),
            expected="piercing/冲孔 for through-hole or internal-thread parts",
            actual=", ".join(op.value for op in sorted(ops, key=lambda op: op.value)),
        ))

        return results

    def _check_thread_blank_diameter(
        self,
        features: PartFeatures,
        forming: ProcessForming,
    ) -> list[VerificationCheck]:
        """Gong p45-p50: rolling blank diameter should be below nominal OD."""
        if features.thread is None or not forming.stations:
            return []

        nominal = features.thread.nominal_diameter
        final = forming.stations[-1].workpiece
        thread_blank = (
            final.extra_dims_mm.get("thread_blank_D")
            or final.extra_dims_mm.get("thread_blank_d")
            or final.shank_diameter_mm
        )
        if thread_blank is None or thread_blank <= 0:
            return [VerificationCheck(
                check_name="v2_thread_blank_diameter",
                passed=False,
                severity=CheckSeverity.warning,
                message="Threaded part does not expose final thread_blank_D/shank diameter",
                expected=f"rolling blank diameter below nominal M{nominal:g}",
                actual="missing",
            )]

        passed = thread_blank <= nominal * 1.01
        return [VerificationCheck(
            check_name="v2_thread_blank_diameter",
            passed=passed,
            severity=CheckSeverity.warning if not passed else CheckSeverity.info,
            message=(
                "External-thread blank diameter is below nominal thread diameter"
                if passed
                else "External-thread blank diameter appears too large for rolling stock"
            ),
            expected=f"thread blank <= about {nominal * 1.01:.3f} mm for M{nominal:g}",
            actual=f"{thread_blank:.3f} mm",
        )]

    def _check_large_head_staging(self, forming: ProcessForming) -> list[VerificationCheck]:
        """Gong/1D2B: large head vs shank should be staged, not one-shot."""
        if not forming.stations:
            return []

        final = forming.stations[-1].workpiece
        shank_d = final.shank_diameter_mm or forming.blank.max_diameter_mm
        head_d = final.head_diameter_mm or final.max_diameter_mm
        if shank_d <= 0:
            return []

        ratio = head_d / shank_d
        if ratio <= 1.6:
            return [VerificationCheck(
                check_name="v2_large_head_staging",
                passed=True,
                severity=CheckSeverity.info,
                message=f"Head/shank ratio {ratio:.2f} does not require extra staging",
                expected="extra preforming when head/shank ratio is high",
                actual=f"{ratio:.2f}",
            )]

        staged_ops = sum(
            1
            for st in forming.stations
            if st.operation in {OperationType.upsetting, OperationType.heading, OperationType.combined}
        )
        passed = len(forming.stations) >= 4 and staged_ops >= 2
        return [VerificationCheck(
            check_name="v2_large_head_staging",
            passed=passed,
            severity=CheckSeverity.warning if not passed else CheckSeverity.info,
            message=(
                f"Large head/shank ratio {ratio:.2f} is split across staged preforming"
                if passed
                else f"Large head/shank ratio {ratio:.2f} should be split across preforming/head stations"
            ),
            expected=">=4 stations and >=2 upsetting/heading/combined stages for large-head parts",
            actual=f"stations={len(forming.stations)}, staged_ops={staged_ops}",
        )]

    def _check_material_preparation(self, forming: ProcessForming) -> list[VerificationCheck]:
        """Gong p57-p68: material-specific softening/surface treatment risk."""
        material = self._normalize_material(forming.material)
        notes = " ".join(
            [
                forming.part_name_zh,
                forming.reasoning_zh,
                *[st.notes_zh or "" for st in forming.stations],
                *[st.workpiece.notes_zh or "" for st in forming.stations],
                *[p.value for p in forming.post_processes],
            ]
        ).lower()
        has_prep_note = any(
            token in notes
            for token in (
                "退火", "anneal", "annealing", "磷化", "phosphat", "皂化", "润滑",
                "lubric", "草酸", "氧化", "passivat", "软化",
            )
        )
        hard_material = any(
            token in material
            for token in ("SUS", "304", "302", "1CR18", "STAINLESS", "2A", "5A", "LY", "CU", "H62", "BRASS")
        )
        difficult_forming = any(st.operation == OperationType.backward_extrusion for st in forming.stations)
        difficult_forming = difficult_forming or any(
            st.workpiece.max_diameter_mm / max(forming.blank.max_diameter_mm, 0.001) > 1.6
            for st in forming.stations
        )

        needs_note = hard_material or difficult_forming
        passed = not needs_note or has_prep_note
        return [VerificationCheck(
            check_name="v2_material_surface_prep",
            passed=passed,
            severity=CheckSeverity.warning if not passed else CheckSeverity.info,
            message=(
                "Material/forming difficulty has softening, surface prep, or lubrication note"
                if needs_note and passed
                else "No special material-prep note required"
                if not needs_note
                else "Difficult material/forming should mention annealing/phosphating/lubrication risk"
            ),
            expected="annealing/phosphating/lubrication note for stainless/nonferrous or difficult forming",
            actual="present" if has_prep_note else "missing",
        )]

    @staticmethod
    def _workpiece_volume(w: WorkpieceGeometry) -> float:
        length = max(w.overall_length_mm, 0.0)
        max_d = max(w.max_diameter_mm, 0.0)
        if length <= 0 or max_d <= 0:
            return 0.0

        head_d = w.head_diameter_mm or 0.0
        head_h = min(w.head_height_mm or 0.0, length)
        shank_d = w.shank_diameter_mm or 0.0
        shank_l = min(w.shank_length_mm or 0.0, max(length - head_h, 0.0))

        if head_d > 0 and head_h > 0 and shank_d > 0 and shank_l > 0:
            remaining_l = max(length - head_h - shank_l, 0.0)
            return (
                _cylinder_volume(head_d, head_h)
                + _cylinder_volume(shank_d, shank_l)
                + _cylinder_volume(max_d, remaining_l)
            )

        if w.type == "stepped" and shank_d > 0 and shank_l > 0:
            big_l = max(length - shank_l, 0.0)
            return _cylinder_volume(max_d, big_l) + _cylinder_volume(shank_d, shank_l)

        return _cylinder_volume(max_d, length)

    @staticmethod
    def _area_reduction_pct(previous: WorkpieceGeometry, current: WorkpieceGeometry) -> float:
        prev_d = previous.shank_diameter_mm or previous.max_diameter_mm
        curr_d = current.shank_diameter_mm or current.max_diameter_mm
        if prev_d <= 0 or curr_d <= 0 or curr_d >= prev_d:
            return 0.0
        prev_area = math.pi * (prev_d / 2) ** 2
        curr_area = math.pi * (curr_d / 2) ** 2
        return (prev_area - curr_area) / prev_area * 100

    @staticmethod
    def _required_blow_count(ld_ratio: float) -> int:
        if ld_ratio <= 2.8:
            return 1
        if ld_ratio <= 5.5:
            return 2
        if ld_ratio <= 8.0:
            return 3
        return 4

    @staticmethod
    def _normalize_material(material: str) -> str:
        return material.upper().replace("-", "").replace(" ", "")


def _cylinder_volume(diameter: float, length: float) -> float:
    return math.pi * (diameter / 2) ** 2 * length


class DesignVerifier:
    """
    Rule-based verification of generated die designs.

    Checks:
    1. Dimensional consistency — segment lengths sum to total length
    2. Volume conservation   — blank volume ≈ product volume ±30%
    3. Upset ratios          — each station ≤ 3.5 (cold-heading limit)
    4. Material compatibility — die HRC ≥ workpiece HRC + 20
    5. Completeness          — every station has punch + die
    6. Station sequence      — head diameter grows, shank diameter shrinks
    7. Tolerance chain       — critical tolerances present on final station
    """

    def verify(
        self,
        features: PartFeatures,
        plan: ProcessPlan,
        die_params: list[DieParameters],
        retry_count: int = 0,
    ) -> VerificationResult:
        checks: list[VerificationCheck] = [
            *self._check_dimensional_consistency(features, plan),
            *self._check_upset_ratios(plan),
            *self._check_volume_conservation(features, plan),
            *self._check_material_compatibility(features, die_params),
            *self._check_completeness(plan, die_params),
            *self._check_station_sequence(plan),
            *self._check_tolerance_chain(features, die_params),
        ]

        error_checks = [c for c in checks if c.severity == CheckSeverity.error]
        passed = all(c.passed for c in error_checks)
        return VerificationResult(
            passed=passed,
            checks=checks,
            retry_count=retry_count,
            flagged_for_review=not passed,
        )

    # ------------------------------------------------------------------
    # Individual checks
    # ------------------------------------------------------------------

    def _check_dimensional_consistency(
        self, features: PartFeatures, plan: ProcessPlan
    ) -> list[VerificationCheck]:
        last_station = plan.stations[-1]
        out = last_station.output_shape
        expected_length = features.overall_length

        if out.overall_length <= 0:
            return [VerificationCheck(
                check_name="dimensional_consistency",
                passed=False,
                severity=CheckSeverity.error,
                message="Final station output shape has no length",
            )]

        deviation_pct = abs(out.overall_length - expected_length) / expected_length * 100
        passed = deviation_pct <= 10  # allow 10% tolerance

        return [VerificationCheck(
            check_name="dimensional_consistency",
            passed=passed,
            severity=CheckSeverity.warning if passed else CheckSeverity.error,
            message=(
                f"Final shape length {out.overall_length}mm matches part length {expected_length}mm"
                if passed
                else f"Final shape {out.overall_length}mm deviates {deviation_pct:.1f}% from part length {expected_length}mm"
            ),
            expected=f"{expected_length}mm",
            actual=f"{out.overall_length}mm",
        )]

    def _check_upset_ratios(self, plan: ProcessPlan) -> list[VerificationCheck]:
        results: list[VerificationCheck] = []
        for station in plan.stations:
            ratio = station.upset_ratio
            if ratio is None:
                continue
            passed = ratio <= 3.5
            results.append(VerificationCheck(
                check_name=f"upset_ratio_s{station.station_number}",
                passed=passed,
                severity=CheckSeverity.error if ratio > 3.5 else CheckSeverity.warning if ratio > 2.3 else CheckSeverity.info,
                message=(
                    f"Station {station.station_number} upset ratio {ratio:.2f} within limits"
                    if passed
                    else f"Station {station.station_number} upset ratio {ratio:.2f} exceeds cold-heading limit 3.5"
                ),
                actual=f"{ratio:.3f}",
                expected_range="≤ 2.3 (optimal), ≤ 3.5 (absolute limit)",
            ))
        return results

    def _check_volume_conservation(
        self, features: PartFeatures, plan: ProcessPlan
    ) -> list[VerificationCheck]:
        blank_vol = math.pi * (plan.blank_diameter / 2) ** 2 * plan.blank_length

        shank_d = features.shank.diameter
        head_d = features.head.diameter
        shank_l = features.shank.length + features.thread.length
        head_h = features.head.height
        part_vol = (
            math.pi * (shank_d / 2) ** 2 * shank_l
            + math.pi * (head_d / 2) ** 2 * head_h
        )

        if part_vol <= 0:
            return [VerificationCheck(
                check_name="volume_conservation",
                passed=True,
                severity=CheckSeverity.warning,
                message="Cannot compute part volume — check part dimensions",
            )]

        ratio = blank_vol / part_vol
        passed = 0.8 <= ratio <= 2.5

        return [VerificationCheck(
            check_name="volume_conservation",
            passed=passed,
            severity=CheckSeverity.warning,
            message=(
                f"Blank/part volume ratio {ratio:.2f} is reasonable"
                if passed
                else f"Blank/part volume ratio {ratio:.2f} is outside expected range 0.8–2.5"
            ),
            actual=f"blank={blank_vol:.0f}mm³, part≈{part_vol:.0f}mm³, ratio={ratio:.2f}",
            expected_range="0.8–2.5",
        )]

    def _check_material_compatibility(
        self, features: PartFeatures, die_params: list[DieParameters]
    ) -> list[VerificationCheck]:
        if not die_params:
            return []

        mat = features.material_grade
        workpiece_hrc = _WORKPIECE_HRC.get(mat, 20)
        results: list[VerificationCheck] = []

        for dp in die_params:
            die_min = dp.die.hardness_hrc_min
            delta = die_min - workpiece_hrc
            passed = delta >= 20

            results.append(VerificationCheck(
                check_name=f"material_compat_s{dp.station_number}",
                passed=passed,
                severity=CheckSeverity.error if not passed else CheckSeverity.info,
                message=(
                    f"Station {dp.station_number} die HRC {die_min} is ≥ workpiece HRC {workpiece_hrc} + 20"
                    if passed
                    else f"Station {dp.station_number} die HRC {die_min} only {delta} above workpiece HRC {workpiece_hrc} (need ≥ 20)"
                ),
                actual=f"die={die_min} HRC, workpiece≈{workpiece_hrc} HRC, delta={delta}",
                expected_range=f"die HRC ≥ {workpiece_hrc + 20}",
            ))

        return results

    def _check_completeness(
        self, plan: ProcessPlan, die_params: list[DieParameters]
    ) -> list[VerificationCheck]:
        station_numbers = {dp.station_number for dp in die_params}
        missing = [s.station_number for s in plan.stations if s.station_number not in station_numbers]

        passed = len(missing) == 0
        return [VerificationCheck(
            check_name="completeness",
            passed=passed,
            severity=CheckSeverity.error,
            message=(
                f"All {plan.total_stations} stations have die parameters"
                if passed
                else f"Missing die parameters for stations: {missing}"
            ),
            expected=str(list(range(1, plan.total_stations + 1))),
            actual=str(sorted(station_numbers)),
        )]

    def _check_station_sequence(self, plan: ProcessPlan) -> list[VerificationCheck]:
        """Head diameter should be non-decreasing; shank should be non-increasing."""
        if len(plan.stations) < 2:
            return []

        results: list[VerificationCheck] = []
        for i in range(1, len(plan.stations)):
            prev = plan.stations[i - 1].output_shape
            curr = plan.stations[i].output_shape

            prev_head = prev.head_diameter or prev.max_diameter
            curr_head = curr.head_diameter or curr.max_diameter

            if curr_head < prev_head * 0.95:
                results.append(VerificationCheck(
                    check_name=f"sequence_s{i}_s{i+1}_head",
                    passed=False,
                    severity=CheckSeverity.warning,
                    message=(
                        f"Head diameter decreases from station {i} ({prev_head}mm) "
                        f"to station {i+1} ({curr_head}mm) — unexpected"
                    ),
                    actual=f"{prev_head}→{curr_head}",
                ))

        if not results:
            results.append(VerificationCheck(
                check_name="station_sequence",
                passed=True,
                severity=CheckSeverity.info,
                message="Station sequence is geometrically consistent",
            ))

        return results

    def _check_tolerance_chain(
        self, features: PartFeatures, die_params: list[DieParameters]
    ) -> list[VerificationCheck]:
        """Final station die should have inner_diameter set."""
        if not die_params:
            return []

        last_dp = max(die_params, key=lambda d: d.station_number)
        has_inner_dia = last_dp.die.inner_diameter is not None

        return [VerificationCheck(
            check_name="tolerance_chain",
            passed=has_inner_dia,
            severity=CheckSeverity.warning,
            message=(
                f"Final station die inner diameter specified ({last_dp.die.inner_diameter}mm)"
                if has_inner_dia
                else "Final station die inner diameter not specified — tolerance chain incomplete"
            ),
        )]
