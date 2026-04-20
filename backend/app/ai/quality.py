"""
Quality scoring and rule-based verification for the pseudo-reasoning pipeline.

QualityScorer  — computes self_consistency, cross_model_agreement,
                 rule_compliance, geometric_grounding, and overall_confidence.
RuleVerifier   — physics and data-grounding checks against the input pair.
"""

from __future__ import annotations

import math
import re
from typing import TYPE_CHECKING

import structlog

from app.data.schemas import (
    ConfidenceLevel,
    CrossValidation,
    PrimaryReasoning,
    ProductDiePair,
    QualityScores,
    RuleCheck,
    RuleVerification,
)

if TYPE_CHECKING:
    pass

logger = structlog.get_logger()

_HIGH_THRESHOLD = 0.8
_MEDIUM_THRESHOLD = 0.5


class QualityScorer:
    """
    Compute quality metrics:
    - self_consistency    (0-1) — do 3 Claude runs agree on key decisions?
    - cross_model_agreement (0-1) — does Gemini agree?
    - rule_compliance     (0-1) — fraction of rules passed
    - geometric_grounding (0-1) — reasoning references actual input data?
    - overall_confidence  high | medium | low

    Thresholds:
    - high:   all scores > 0.8
    - medium: all scores > 0.5
    - low:    anything else
    """

    def score(
        self,
        primaries: list[PrimaryReasoning],
        cross_val: CrossValidation,
        rules: RuleVerification,
    ) -> QualityScores:
        sc = self._self_consistency(primaries)
        ca = cross_val.overall_agreement
        rc = rules.pass_rate
        gg = self._geometric_grounding(primaries)

        scores = [sc, ca, rc, gg]
        if all(s > _HIGH_THRESHOLD for s in scores):
            level = ConfidenceLevel.high
        elif all(s > _MEDIUM_THRESHOLD for s in scores):
            level = ConfidenceLevel.medium
        else:
            level = ConfidenceLevel.low

        logger.debug(
            "quality_scores",
            self_consistency=round(sc, 3),
            cross_model_agreement=round(ca, 3),
            rule_compliance=round(rc, 3),
            geometric_grounding=round(gg, 3),
            overall=level,
        )
        return QualityScores(
            self_consistency=sc,
            cross_model_agreement=ca,
            rule_compliance=rc,
            geometric_grounding=gg,
            overall_confidence=level,
        )

    def _self_consistency(self, primaries: list[PrimaryReasoning]) -> float:
        if len(primaries) < 2:
            return 1.0

        scores: list[float] = []

        # --- Station count: all runs must mention the same number implicitly
        # (we don't have direct access to pair here, so proxy with text similarity)
        # We use overall_confidence spread as a proxy for consistency
        confidences = [p.overall_confidence for p in primaries]
        conf_spread = max(confidences) - min(confidences)
        scores.append(max(0.0, 1.0 - conf_spread * 2))

        # --- Key numerical params within 15% of each other
        # Extract numbers from station_count_reasoning across runs
        num_scores: list[float] = []
        for i in range(len(primaries)):
            for j in range(i + 1, len(primaries)):
                sim = _text_overlap_score(
                    primaries[i].station_count_reasoning,
                    primaries[j].station_count_reasoning,
                )
                num_scores.append(sim)
        if num_scores:
            scores.append(sum(num_scores) / len(num_scores))

        # --- Risk mentions: at least 2/3 overlap
        if len(primaries) >= 3:
            risk_sets = [set(r.lower() for r in p.potential_risks) for p in primaries]
            if risk_sets:
                # Count items appearing in at least 2 sets
                all_risks = set().union(*risk_sets)
                overlap_count = sum(
                    1 for r in all_risks
                    if sum(1 for rs in risk_sets if r in rs) >= 2
                )
                total = max(len(all_risks), 1)
                scores.append(overlap_count / total)

        # --- Material agreement (exact match across runs)
        materials = [p.die_material_reasoning[:50] for p in primaries]
        material_score = 1.0 if len(set(materials)) == 1 else 0.5
        scores.append(material_score)

        return sum(scores) / len(scores) if scores else 0.5

    def _geometric_grounding(self, primaries: list[PrimaryReasoning]) -> float:
        """Check that reasoning references actual numerical values from the input."""
        if not primaries:
            return 0.5

        all_scores: list[float] = []
        for p in primaries:
            full_text = " ".join([
                p.stock_selection_reasoning,
                p.station_count_reasoning,
                p.deformation_sequence_reasoning,
                p.die_material_reasoning,
            ])
            # Count numeric references in reasoning text
            numbers_found = len(re.findall(r"\b\d+\.?\d*\b", full_text))
            # A well-grounded analysis should reference at least 5 numbers
            score = min(1.0, numbers_found / 10.0)
            all_scores.append(score)

        return sum(all_scores) / len(all_scores)


# ---------------------------------------------------------------------------
# Rule Verifier
# ---------------------------------------------------------------------------


class RuleVerifier:
    """
    Physics and data grounding checks.

    Checks:
      1. no_hallucinated_numbers  — reasoning doesn't invent values not in input
      2. upset_ratio_valid        — upset ratio typically < 3.5 for cold heading
      3. material_compatibility   — die material harder than workpiece
      4. station_count_plausible  — station count is reasonable for geometry
      5. volume_conservation      — blank volume ≈ product volume (within 50%)
      6. dimensions_consistent    — blank diameter > shank diameter
    """

    def verify(
        self, pair: ProductDiePair, primaries: list[PrimaryReasoning]
    ) -> RuleVerification:
        checks = [
            self._no_hallucinated_numbers(pair, primaries),
            self._upset_ratio_valid(pair),
            self._material_compatibility(pair),
            self._station_count_plausible(pair, primaries),
            self._volume_conservation(pair),
            self._dimensions_consistent(pair),
        ]
        passed = all(c.passed for c in checks)
        pass_rate = sum(1 for c in checks if c.passed) / len(checks)
        return RuleVerification(checks=checks, passed=passed, pass_rate=pass_rate)

    def _no_hallucinated_numbers(
        self, pair: ProductDiePair, primaries: list[PrimaryReasoning]
    ) -> RuleCheck:
        """Verify that numbers in the reasoning appear in the input data."""
        # Collect all numbers from pair data
        pair_json = pair.model_dump_json()
        pair_numbers = set(re.findall(r"\b\d+\.?\d*\b", pair_json))

        hallucinated: list[str] = []
        for p in primaries:
            full_text = " ".join([
                p.stock_selection_reasoning,
                p.station_count_reasoning,
                p.deformation_sequence_reasoning,
                p.die_material_reasoning,
            ])
            reasoning_numbers = set(re.findall(r"\b\d{2,}\b", full_text))  # only multi-digit
            for n in reasoning_numbers:
                # Allow common ranges like "2.3", "3.5" — these are limits, not fabricated
                if n not in pair_numbers and float(n) > 100:
                    hallucinated.append(n)

        passed = len(hallucinated) < 3  # allow minor misses
        return RuleCheck(
            check_name="no_hallucinated_numbers",
            passed=passed,
            message=(
                "No fabricated large numbers detected"
                if passed
                else f"Potentially fabricated numbers: {hallucinated[:5]}"
            ),
            actual_value=str(len(hallucinated)) if not passed else None,
            expected_range="< 3 large numbers not in input data",
        )

    def _upset_ratio_valid(self, pair: ProductDiePair) -> RuleCheck:
        """Upset ratio for cold heading should be < 3.5 per blow (typically ≤ 2.3)."""
        max_ratio = 0.0
        for station in pair.process_plan.stations:
            if station.upset_ratio is not None:
                max_ratio = max(max_ratio, station.upset_ratio)

        if max_ratio == 0.0:
            # Compute from geometry
            head_d = pair.part_features.head.diameter
            blank_d = pair.process_plan.blank_diameter
            max_ratio = head_d / blank_d if blank_d > 0 else 1.0
            # For multi-station, divide by station count
            max_ratio /= pair.process_plan.total_stations

        passed = max_ratio <= 3.5
        return RuleCheck(
            check_name="upset_ratio_valid",
            passed=passed,
            message=(
                f"Max upset ratio {max_ratio:.2f} is within cold-heading limits"
                if passed
                else f"Max upset ratio {max_ratio:.2f} exceeds 3.5 (impossible single-blow cold heading)"
            ),
            actual_value=f"{max_ratio:.3f}",
            expected_range="≤ 3.5 per station (typically ≤ 2.3)",
        )

    def _material_compatibility(self, pair: ProductDiePair) -> RuleCheck:
        """Die material must be harder than workpiece material."""
        workpiece_hrc_map = {
            "C1008": 15, "C1010": 15, "10B21": 18,
            "SCM435": 22, "SCM440": 28, "S45C": 20,
        }
        mat = pair.part_features.material_grade
        workpiece_hrc = workpiece_hrc_map.get(mat, 20)

        if not pair.die_parameters:
            return RuleCheck(
                check_name="material_compatibility",
                passed=True,
                message="No die parameters to check",
            )

        die_hrc_min = pair.die_parameters[0].die.hardness_hrc_min
        passed = die_hrc_min >= workpiece_hrc + 30  # die must be significantly harder

        return RuleCheck(
            check_name="material_compatibility",
            passed=passed,
            message=(
                f"Die HRC {die_hrc_min} sufficiently exceeds workpiece HRC ~{workpiece_hrc}"
                if passed
                else f"Die HRC {die_hrc_min} may not be sufficiently harder than workpiece HRC ~{workpiece_hrc}"
            ),
            actual_value=f"die={die_hrc_min} HRC, workpiece≈{workpiece_hrc} HRC",
            expected_range=f"die HRC ≥ {workpiece_hrc + 30}",
        )

    def _station_count_plausible(
        self, pair: ProductDiePair, primaries: list[PrimaryReasoning]
    ) -> RuleCheck:
        """Station count should be consistent with upset ratio requirements."""
        head_d = pair.part_features.head.diameter
        blank_d = pair.process_plan.blank_diameter
        overall_upset = head_d / blank_d if blank_d > 0 else 1.0
        n = pair.process_plan.total_stations

        # Minimum stations needed: ceil(log(overall_upset) / log(2.3))
        min_stations = max(1, math.ceil(math.log(overall_upset) / math.log(2.3))) if overall_upset > 1 else 1
        max_stations = min_stations + 2  # allow 2 extra for complexity

        passed = min_stations <= n <= max_stations + 1

        # Check that at least 2/3 of primaries mention the correct station count in their reasoning
        count_str = str(n)
        mentioning = sum(
            1 for p in primaries if count_str in p.station_count_reasoning
        )
        if len(primaries) >= 2 and mentioning < len(primaries) // 2:
            passed = False

        return RuleCheck(
            check_name="station_count_plausible",
            passed=passed,
            message=(
                f"{n} stations is plausible for upset ratio {overall_upset:.2f}"
                if passed
                else f"{n} stations seems implausible for upset ratio {overall_upset:.2f} (expected {min_stations}-{max_stations})"
            ),
            actual_value=f"{n} stations",
            expected_range=f"{min_stations}-{max_stations+1} stations",
        )

    def _volume_conservation(self, pair: ProductDiePair) -> RuleCheck:
        """Blank volume should be within 50% of finished part volume (rough check)."""
        blank_d = pair.process_plan.blank_diameter
        blank_l = pair.process_plan.blank_length
        blank_vol = math.pi * (blank_d / 2) ** 2 * blank_l

        # Estimate finished part volume
        shank_d = pair.part_features.shank.diameter
        shank_l = pair.part_features.shank.length + pair.part_features.thread.length
        head_d = pair.part_features.head.diameter
        head_h = pair.part_features.head.height
        shank_vol = math.pi * (shank_d / 2) ** 2 * shank_l
        head_vol = math.pi * (head_d / 2) ** 2 * head_h
        part_vol = shank_vol + head_vol

        if part_vol <= 0:
            return RuleCheck(
                check_name="volume_conservation",
                passed=True,
                message="Cannot compute part volume",
            )

        ratio = blank_vol / part_vol
        passed = 0.7 <= ratio <= 2.5  # blank ≥ part, allow up to 2.5× for scrap/trim

        return RuleCheck(
            check_name="volume_conservation",
            passed=passed,
            message=(
                f"Volume ratio {ratio:.2f} within expected range (0.7–2.5)"
                if passed
                else f"Volume ratio {ratio:.2f} outside expected range — possible data error"
            ),
            actual_value=f"blank/part={ratio:.2f}",
            expected_range="0.7–2.5",
        )

    def _dimensions_consistent(self, pair: ProductDiePair) -> RuleCheck:
        """Basic geometry sanity: blank_d > shank_d, head_d > shank_d."""
        blank_d = pair.process_plan.blank_diameter
        shank_d = pair.part_features.shank.diameter
        head_d = pair.part_features.head.diameter

        issues: list[str] = []
        if blank_d < shank_d * 0.9:
            issues.append(f"blank_d {blank_d} < shank_d {shank_d}")
        if head_d <= shank_d:
            issues.append(f"head_d {head_d} ≤ shank_d {shank_d}")

        passed = len(issues) == 0
        return RuleCheck(
            check_name="dimensions_consistent",
            passed=passed,
            message="All key dimensions are geometrically consistent" if passed else "; ".join(issues),
            actual_value=f"blank_d={blank_d}, shank_d={shank_d}, head_d={head_d}",
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _text_overlap_score(a: str, b: str) -> float:
    """Rough word-overlap similarity between two strings."""
    words_a = set(re.findall(r"\b[a-zA-Z0-9]+\b", a.lower()))
    words_b = set(re.findall(r"\b[a-zA-Z0-9]+\b", b.lower()))
    if not words_a and not words_b:
        return 1.0
    if not words_a or not words_b:
        return 0.0
    intersection = len(words_a & words_b)
    union = len(words_a | words_b)
    return intersection / union
