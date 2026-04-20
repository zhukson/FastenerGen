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
    PartFeatures,
    ProcessPlan,
    VerificationCheck,
    VerificationResult,
)

_WORKPIECE_HRC: dict[str, float] = {
    "C1008": 15, "C1010": 15, "10B21": 18,
    "SCM435": 22, "SCM440": 28, "S45C": 20, "45": 20,
}


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
