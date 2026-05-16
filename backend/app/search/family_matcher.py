"""Family matching from primitive manufacturing feature graphs."""

from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel, Field

from app.search.features import FeatureKind, ManufacturingFeatureGraph


@dataclass(frozen=True)
class FamilyPrior:
    """Feature-based prior used to rank candidate part families."""

    family: str
    required: frozenset[FeatureKind]
    optional: frozenset[FeatureKind] = frozenset()
    expected_but_optional: frozenset[FeatureKind] = frozenset()


class FamilyMatch(BaseModel):
    """One ranked family match."""

    family: str
    score: float = Field(..., ge=0, le=1)
    matched_features: list[str] = Field(default_factory=list)
    missing_required: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


FAMILY_PRIORS: tuple[FamilyPrior, ...] = (
    FamilyPrior(
        family="square_T_head",
        required=frozenset(
            {
                FeatureKind.cylindrical_shank,
                FeatureKind.square_head,
            }
        ),
        optional=frozenset(
            {
                FeatureKind.flange,
                FeatureKind.corner_radius,
                FeatureKind.cross_recess,
                FeatureKind.through_hole,
            }
        ),
        expected_but_optional=frozenset({FeatureKind.through_hole}),
    ),
    FamilyPrior(
        family="socket_cap_screw",
        required=frozenset(
            {
                FeatureKind.cylindrical_shank,
                FeatureKind.round_head,
                FeatureKind.hex_socket,
            }
        ),
        optional=frozenset({FeatureKind.thread, FeatureKind.chamfer, FeatureKind.fillet}),
    ),
    FamilyPrior(
        family="hex_bolt",
        required=frozenset(
            {
                FeatureKind.cylindrical_shank,
                FeatureKind.hex_head,
            }
        ),
        optional=frozenset({FeatureKind.thread, FeatureKind.chamfer, FeatureKind.fillet}),
    ),
)


def match_families(graph: ManufacturingFeatureGraph) -> list[FamilyMatch]:
    """Rank likely families using primitive feature coverage."""

    present = {feature.kind for feature in graph.features}
    matches = [_score_prior(prior, present) for prior in FAMILY_PRIORS]
    return sorted(matches, key=lambda match: match.score, reverse=True)


def _score_prior(prior: FamilyPrior, present: set[FeatureKind]) -> FamilyMatch:
    matched_required = prior.required & present
    missing_required = prior.required - present
    matched_optional = prior.optional & present

    required_score = len(matched_required) / len(prior.required) if prior.required else 1.0
    optional_score = len(matched_optional) / len(prior.optional) if prior.optional else 0.0
    score = round((required_score * 0.75) + (optional_score * 0.25), 4)

    if missing_required:
        score = round(score * 0.4, 4)

    warnings = [
        f"missing {feature.value} feature"
        for feature in sorted(prior.expected_but_optional - present, key=lambda item: item.value)
    ]

    matched_features = sorted(
        [feature.value for feature in matched_required | matched_optional]
    )
    return FamilyMatch(
        family=prior.family,
        score=score,
        matched_features=matched_features,
        missing_required=sorted(feature.value for feature in missing_required),
        warnings=warnings,
    )

