"""Primitive manufacturing feature graph for search-based process planning."""

from __future__ import annotations

import re
from enum import StrEnum

from pydantic import BaseModel, Field

from app.data.schemas import ConfidenceLevel, HeadType, PartFeatures


class FeatureKind(StrEnum):
    """Reusable product/manufacturing features used by operation search."""

    cylindrical_shank = "cylindrical_shank"
    flange = "flange"
    square_head = "square_head"
    hex_head = "hex_head"
    round_head = "round_head"
    thread = "thread"
    tail = "tail"
    corner_radius = "corner_radius"
    cross_recess = "cross_recess"
    hex_socket = "hex_socket"
    through_hole = "through_hole"
    blind_hole = "blind_hole"
    chamfer = "chamfer"
    fillet = "fillet"


class ManufacturingFeature(BaseModel):
    """One primitive/semantic feature extracted from final product data."""

    feature_id: str
    kind: FeatureKind
    dimensions_mm: dict[str, float] = Field(default_factory=dict)
    source: str
    confidence: ConfidenceLevel = ConfidenceLevel.medium
    notes: list[str] = Field(default_factory=list)


class FeatureRelation(BaseModel):
    """Directed relation between two manufacturing features."""

    source_feature_id: str
    relation: str
    target_feature_id: str


class ManufacturingFeatureGraph(BaseModel):
    """Primitive feature graph consumed by operation grammar/search."""

    part_id: str
    description: str
    material: str
    overall_length_mm: float
    features: list[ManufacturingFeature] = Field(default_factory=list)
    relations: list[FeatureRelation] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    def require_feature(self, kind: FeatureKind) -> ManufacturingFeature:
        for feature in self.features:
            if feature.kind == kind:
                return feature
        raise KeyError(f"feature not found: {kind}")

    def has_relation(
        self,
        source_feature_id: str,
        relation: str,
        target_feature_id: str,
    ) -> bool:
        return any(
            item.source_feature_id == source_feature_id
            and item.relation == relation
            and item.target_feature_id == target_feature_id
            for item in self.relations
        )


_CORNER_RADIUS_RE = re.compile(r"(?:R|r)\s*(\d+(?:\.\d+)?)")


def build_feature_graph(part: PartFeatures) -> ManufacturingFeatureGraph:
    """Convert existing PartFeatures into reusable primitive features.

    This adapter is intentionally conservative: it extracts only features that
    are directly represented by typed fields or explicit drawing notes.
    """

    features: list[ManufacturingFeature] = []
    relations: list[FeatureRelation] = []
    warnings: list[str] = []

    notes_text = "\n".join(part.notes)
    corner_radius = _parse_corner_radius(notes_text)

    if part.shank is not None:
        features.append(
            ManufacturingFeature(
                feature_id="cylindrical_shank",
                kind=FeatureKind.cylindrical_shank,
                dimensions_mm={
                    "diameter": part.shank.diameter,
                    "length": part.shank.length,
                },
                source="part_features.shank",
                confidence=ConfidenceLevel.high,
            )
        )
    else:
        warnings.append("missing shank feature")

    if part.head is not None:
        if part.head.type == HeadType.flange or part.head.flange:
            features.append(
                ManufacturingFeature(
                    feature_id="flange",
                    kind=FeatureKind.flange,
                    dimensions_mm={
                        "diameter": part.head.flange_diameter or part.head.diameter,
                        "height": part.head.height,
                    },
                    source="part_features.head",
                    confidence=ConfidenceLevel.high,
                )
            )

        if _mentions_square_head(notes_text):
            dimensions = {
                "flat_width": part.head.diameter,
                "height": part.head.height,
            }
            if corner_radius is not None:
                dimensions["corner_radius"] = corner_radius
            features.append(
                ManufacturingFeature(
                    feature_id="square_head",
                    kind=FeatureKind.square_head,
                    dimensions_mm=dimensions,
                    source="part_features.head+notes",
                    confidence=ConfidenceLevel.medium,
                    notes=["square/polygon head inferred from drawing notes"],
                )
            )
        elif part.head.type == HeadType.hex:
            features.append(
                ManufacturingFeature(
                    feature_id="hex_head",
                    kind=FeatureKind.hex_head,
                    dimensions_mm={
                        "flat_width": part.head.diameter,
                        "height": part.head.height,
                    },
                    source="part_features.head",
                    confidence=ConfidenceLevel.high,
                )
            )
        else:
            features.append(
                ManufacturingFeature(
                    feature_id="round_head",
                    kind=FeatureKind.round_head,
                    dimensions_mm={
                        "diameter": part.head.diameter,
                        "height": part.head.height,
                    },
                    source="part_features.head",
                    confidence=ConfidenceLevel.medium,
                )
            )
    else:
        warnings.append("missing head feature")

    if corner_radius is not None:
        features.append(
            ManufacturingFeature(
                feature_id="corner_radius",
                kind=FeatureKind.corner_radius,
                dimensions_mm={
                    "radius": corner_radius,
                    "count": 4.0 if "4" in notes_text else 1.0,
                },
                source="notes",
                confidence=ConfidenceLevel.medium,
            )
        )

    if _mentions_cross_recess(notes_text):
        features.append(
            ManufacturingFeature(
                feature_id="cross_recess",
                kind=FeatureKind.cross_recess,
                dimensions_mm={},
                source="notes",
                confidence=ConfidenceLevel.medium,
            )
        )

    if part.thread is not None:
        features.append(
            ManufacturingFeature(
                feature_id="thread",
                kind=FeatureKind.thread,
                dimensions_mm={
                    "nominal_diameter": part.thread.nominal_diameter,
                    "length": part.thread.length,
                },
                source="part_features.thread",
                confidence=ConfidenceLevel.high,
            )
        )

    feature_ids = {feature.feature_id for feature in features}
    if "square_head" in feature_ids and "cylindrical_shank" in feature_ids:
        relations.append(
            FeatureRelation(
                source_feature_id="square_head",
                relation="sits_on",
                target_feature_id="cylindrical_shank",
            )
        )
    if "flange" in feature_ids and "cylindrical_shank" in feature_ids:
        relations.append(
            FeatureRelation(
                source_feature_id="flange",
                relation="sits_on",
                target_feature_id="cylindrical_shank",
            )
        )
    if "cross_recess" in feature_ids and "square_head" in feature_ids:
        relations.append(
            FeatureRelation(
                source_feature_id="cross_recess",
                relation="formed_in",
                target_feature_id="square_head",
            )
        )

    return ManufacturingFeatureGraph(
        part_id=part.part_number,
        description=part.description,
        material=part.material_grade,
        overall_length_mm=part.overall_length,
        features=features,
        relations=relations,
        warnings=warnings,
    )


def _parse_corner_radius(text: str) -> float | None:
    match = _CORNER_RADIUS_RE.search(text)
    return float(match.group(1)) if match else None


def _mentions_square_head(text: str) -> bool:
    return "四方" in text or "方头" in text or "square" in text.lower()


def _mentions_cross_recess(text: str) -> bool:
    lowered = text.lower()
    return "十字" in text or "cross" in lowered

