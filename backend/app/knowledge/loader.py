"""Tier 1 经验库 (Experience Library) loader.

Discovers, validates, and formats all CaseRecord JSONs + rules.md files into
an XML few-shot block injected into Step 3 (Process Forming Design).

At N=8 worked cases this is the entire knowledge layer — no embeddings, no
vector retrieval. The LLM sees every case in every call.

Usage:
    from app.knowledge.loader import load_library, format_for_prompt

    lib = load_library()
    xml = format_for_prompt(lib, prefer_category="hex_bolt_DIN933")
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from app.data.schemas import CaseRecord

logger = logging.getLogger(__name__)

KNOWLEDGE_DIR = Path(__file__).resolve().parent
CASES_DIR = KNOWLEDGE_DIR / "cases"
STANDARDS_DIR = KNOWLEDGE_DIR / "standards"
RULES_DIR = KNOWLEDGE_DIR / "rules"
TEXTBOOK_RULES_DIR = KNOWLEDGE_DIR / "textbook_rules"
TEXTBOOK_CASES_DIR = KNOWLEDGE_DIR / "textbook_cases"
PATTERNS_DIR = KNOWLEDGE_DIR / "patterns"


@dataclass
class Library:
    cases: list[CaseRecord]  # 异形件
    standards: list[CaseRecord]  # standard parts (DIN912, DIN933, ...)
    rules: dict[str, str]  # filename stem -> markdown text
    textbook_rules: dict[str, str]  # textbook/tutorial distilled principles
    textbook_cases: list[dict[str, Any]]  # textbook examples, not factory answer keys
    patterns: list[dict[str, Any]]  # reusable operation/shape patterns
    skipped: list[tuple[Path, str]]  # (path, reason) — invalid JSONs
    feature_index: dict[str, Any]  # 优化 3 — feature → station snippets

    @property
    def all_records(self) -> list[CaseRecord]:
        return self.cases + self.standards

    @property
    def count(self) -> int:
        return len(self.cases) + len(self.standards)


def _load_record_file(path: Path) -> CaseRecord | tuple[Path, str]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return CaseRecord.model_validate(data)
    except (json.JSONDecodeError, ValidationError) as exc:
        return (path, f"{type(exc).__name__}: {str(exc)[:200]}")


def load_library() -> Library:
    """Load every case + standard + rules.md from backend/app/knowledge/.

    Invalid records are skipped and reported in `skipped`; we never fail-hard
    here because the loader runs on every Step 3 call.
    """
    cases: list[CaseRecord] = []
    standards: list[CaseRecord] = []
    skipped: list[tuple[Path, str]] = []

    for path in sorted(CASES_DIR.glob("*.json")):
        result = _load_record_file(path)
        if isinstance(result, CaseRecord):
            cases.append(result)
        else:
            skipped.append(result)
            logger.warning("Skipping invalid case %s: %s", *result)

    for path in sorted(STANDARDS_DIR.glob("*.json")):
        result = _load_record_file(path)
        if isinstance(result, CaseRecord):
            standards.append(result)
        else:
            skipped.append(result)
            logger.warning("Skipping invalid standard %s: %s", *result)

    rules: dict[str, str] = {}
    if RULES_DIR.exists():
        for path in sorted(RULES_DIR.glob("*.md")):
            rules[path.stem] = path.read_text(encoding="utf-8")

    textbook_rules: dict[str, str] = {}
    if TEXTBOOK_RULES_DIR.exists():
        for path in sorted(TEXTBOOK_RULES_DIR.glob("*.md")):
            textbook_rules[path.stem] = path.read_text(encoding="utf-8")

    textbook_cases: list[dict[str, Any]] = []
    if TEXTBOOK_CASES_DIR.exists():
        for path in sorted(TEXTBOOK_CASES_DIR.glob("*.json")):
            try:
                textbook_cases.append(json.loads(path.read_text(encoding="utf-8")))
            except json.JSONDecodeError as exc:
                skipped.append((path, f"JSONDecodeError: {str(exc)[:200]}"))

    patterns: list[dict[str, Any]] = []
    if PATTERNS_DIR.exists():
        for path in sorted(PATTERNS_DIR.glob("*.json")):
            try:
                patterns.append(json.loads(path.read_text(encoding="utf-8")))
            except json.JSONDecodeError as exc:
                skipped.append((path, f"JSONDecodeError: {str(exc)[:200]}"))

    feature_index: dict[str, Any] = {}
    feature_index_path = KNOWLEDGE_DIR / "feature_index.json"
    if feature_index_path.exists():
        try:
            feature_index = json.loads(feature_index_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            skipped.append((feature_index_path, f"JSONDecodeError: {str(exc)[:200]}"))

    return Library(
        cases=cases,
        standards=standards,
        rules=rules,
        textbook_rules=textbook_rules,
        textbook_cases=textbook_cases,
        patterns=patterns,
        skipped=skipped,
        feature_index=feature_index,
    )


# ---------------------------------------------------------------------------
# Prompt formatting
# ---------------------------------------------------------------------------


def _xml_escape(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


# ---------------------------------------------------------------------------
# 优化 3 — feature-based sub-process retrieval
# ---------------------------------------------------------------------------

# Mirror of build_feature_index.py's FEATURE_KEYWORDS, but only the few we
# detect on incoming PartFeatures (not full case records). Keep in sync.
_INPUT_FEATURE_PATTERNS: dict[str, list[str]] = {
    "internal_hex_head": [r"内六角", r"hex socket", r"hex_socket", r"socket"],
    "internal_torx_head": [r"内梅花", r"torx", r"梅花孔"],
    "internal_recess": [r"凹头", r"recess"],
    "external_hex_head": [r"外六角", r"hex bolt", r"hex_flange"],
    "external_square_head": [r"四方", r"square_head", r"T头", r"T帽"],
    "external_pan_head": [r"圆头", r"pan_head"],
    "external_ball_head": [r"球头", r"ball_head"],
    "external_flange_head": [r"法兰", r"flange"],
    "shoulder_step": [r"阶梯", r"台阶", r"step"],
    "taper_end": [r"倒锥", r"45°", r"30°"],
    "thread_external": [r"螺纹", r"thread", r"M\d+"],
    "thread_internal": [r"内螺纹", r"攻丝"],
    "through_hole": [r"通孔", r"through"],
    "rivet_tail": [r"铆"],
}


def detect_input_features(part_features: Any) -> list[str]:
    """Return feature tags for a PartFeatures pydantic model (or dict).

    Used by Step 3 to ask the loader for relevant sub-process patterns. We
    look at description + notes + structural fields. Numeric ratios are
    derived directly here.
    """
    if hasattr(part_features, "model_dump"):
        data = part_features.model_dump(exclude_none=True, mode="json")
    else:
        data = dict(part_features or {})

    blob_parts: list[str] = []
    for key in ("description",):
        v = data.get(key)
        if isinstance(v, str):
            blob_parts.append(v)
    for note in data.get("notes") or []:
        blob_parts.append(str(note))
    head = data.get("head") or {}
    if head:
        blob_parts.append(str(head.get("type") or ""))
        blob_parts.append(str(head.get("drive_type") or ""))
    if data.get("thread"):
        blob_parts.append("thread")
    blob = " ".join(p for p in blob_parts if p)

    detected: list[str] = []
    for feature, patterns in _INPUT_FEATURE_PATTERNS.items():
        for pat in patterns:
            if re.search(pat, blob, flags=re.IGNORECASE):
                detected.append(feature)
                break

    # Numeric: long_thin_shank if final L/D > 5
    length_mm = data.get("overall_length") or 0
    diameter_mm = (data.get("shank") or {}).get("diameter") or 0
    if length_mm > 0 and diameter_mm > 0 and length_mm / diameter_mm > 5.0:
        detected.append("long_thin_shank")

    # Drive-type derived
    drive = (head or {}).get("drive_type") or ""
    if drive == "hex_socket":
        detected.append("internal_hex_head")
    elif drive == "torx":
        detected.append("internal_torx_head")
    elif drive == "external_hex":
        detected.append("external_hex_head")

    return sorted(set(detected))


def compute_neighbor_density(
    library: Library,
    part_features: Any,
    *,
    exclude_case_ids: list[str] | set[str] | None = None,
) -> dict[str, Any]:
    """Replace LLM-reported confidence with a measurable, explainable signal.

    Counts library evidence for the input part along three axes:
      1. Same-category cases (strongest signal)
      2. Cases that share each detected feature (medium signal)
      3. Cases with similar overall geometry (head/shank/length range)

    Returns a dict with confidence level + per-axis breakdown so callers can
    show "why" the system is (un)sure, instead of trusting the LLM's
    self-report.
    """
    excluded = set(exclude_case_ids or [])
    detected = detect_input_features(part_features)
    needed = set(detected)

    if hasattr(part_features, "model_dump"):
        data = part_features.model_dump(exclude_none=True, mode="json")
    else:
        data = dict(part_features or {})

    # Axis 1: same-category cases
    same_cat = []
    head_data = data.get("head") or {}
    head_type_str = str(head_data.get("type") or "").lower()
    drive_str = str(head_data.get("drive_type") or "").lower()
    desc = (data.get("description") or "").lower()

    # build a heuristic "category bag"
    cat_keywords: list[str] = []
    if "socket" in drive_str or "hex_socket" in drive_str:
        cat_keywords.append("socket_cap_screw")
    if head_type_str == "hex" or "hex bolt" in desc or "外六角" in desc:
        cat_keywords.append("hex_bolt")
    if "ball" in desc or "球头" in desc:
        cat_keywords.append("ball_head")
    if "rivet" in desc or "铆" in desc:
        cat_keywords.append("rivet")
    if "通孔" in desc or "through_hole" in desc:
        cat_keywords.append("through_hole")
    if "T帽" in desc or "T头" in desc or "四方" in desc:
        cat_keywords.append("square_T_head")

    by_case = {
        case_id: features
        for case_id, features in (library.feature_index.get("by_case") or {}).items()
        if case_id not in excluded
    }
    records = [r for r in library.cases + library.standards if r.case_id not in excluded]
    for record in records:
        cat = (record.product_category or "").lower()
        if any(kw in cat for kw in cat_keywords):
            same_cat.append(record.case_id)

    # Axis 2: feature overlap
    feature_hits: dict[str, int] = {}
    for case_id, feats in by_case.items():
        overlap = needed & set(feats)
        if overlap:
            feature_hits[case_id] = len(overlap)
    feature_coverage = sum(feature_hits.values())

    # Axis 3: geometric similarity
    target_l = data.get("overall_length") or 0
    target_d = (data.get("shank") or {}).get("diameter") or 0
    geom_neighbors: list[str] = []
    if target_l > 0 and target_d > 0:
        for record in records:
            feats = record.part_features
            if feats.overall_length <= 0:
                continue
            shank_d = feats.shank.diameter if feats.shank else 0
            if shank_d <= 0:
                continue
            l_ratio = target_l / feats.overall_length
            d_ratio = target_d / shank_d
            if 0.6 <= l_ratio <= 1.66 and 0.6 <= d_ratio <= 1.66:
                geom_neighbors.append(record.case_id)

    # Score: weighted sum
    score = (
        len(same_cat) * 4
        + feature_coverage * 1
        + len(geom_neighbors) * 2
    )

    # High requires strong evidence on at least 2 axes (avoid "1 keyword match
    # = high confidence" false positives).
    has_strong_category = len(same_cat) >= 2
    has_strong_features = feature_coverage >= 5
    has_strong_geometry = len(geom_neighbors) >= 3
    strong_axes = sum([has_strong_category, has_strong_features, has_strong_geometry])

    if strong_axes >= 2:
        confidence = "high"
    elif len(same_cat) >= 1 or feature_coverage >= 3 or len(geom_neighbors) >= 2:
        confidence = "medium"
    else:
        confidence = "low"

    rationale_parts: list[str] = []
    if same_cat:
        rationale_parts.append(f"{len(same_cat)} same-category case(s): {same_cat[:3]}")
    else:
        rationale_parts.append("no same-category factory case")
    if feature_hits:
        top_feats = sorted(feature_hits.items(), key=lambda kv: -kv[1])[:3]
        rationale_parts.append(
            "feature overlap: " + ", ".join(f"{cid}({n})" for cid, n in top_feats)
        )
    if geom_neighbors:
        rationale_parts.append(
            f"{len(geom_neighbors)} case(s) within ±67% L/D: {geom_neighbors[:3]}"
        )
    else:
        rationale_parts.append("no geometric neighbor in ±67% L/D window")

    return {
        "confidence": confidence,
        "score": score,
        "detected_features": detected,
        "same_category_cases": same_cat,
        "feature_coverage": feature_coverage,
        "feature_hits": feature_hits,
        "geometric_neighbors": geom_neighbors,
        "rationale": "; ".join(rationale_parts),
    }


def select_relevant_subprocesses(
    library: Library,
    part_features: Any,
    *,
    max_per_feature: int = 3,
    exclude_case_ids: set[str] | None = None,
) -> list[dict[str, Any]]:
    """Return sub-process snippets relevant to the input part's features.

    Each snippet is one station from one case that demonstrates a feature
    the input part needs. The LLM uses these as targeted few-shot rather
    than scanning the full library every time.
    """
    if not library.feature_index:
        return []

    needed = set(detect_input_features(part_features))
    if not needed:
        return []

    excluded = exclude_case_ids or set()
    station_index = [
        entry for entry in (library.feature_index.get("station_index") or [])
        if entry.get("case_id") not in excluded
    ]
    out: list[dict[str, Any]] = []
    seen: set[tuple[str, int]] = set()

    for needed_feature in sorted(needed):
        op_feature = None
        # Map input features → station-level features (op_*)
        op_map = {
            "internal_hex_head": "op_backward_extrude_socket",
            "internal_torx_head": "op_backward_extrude_socket",
            "internal_recess": "op_backward_extrude_socket",
            "external_square_head": "op_trim_polygon",
            "external_flange_head": "op_trim_polygon",
            "shoulder_step": "op_forward_extrude_taper",
            "taper_end": "op_forward_extrude_taper",
            "through_hole": "op_pierce_through",
        }
        op_feature = op_map.get(needed_feature)
        if not op_feature:
            continue

        matches = [
            entry for entry in station_index
            if op_feature in (entry.get("features") or [])
        ]
        primary_matches = matches[:max_per_feature]
        textbook_supplements = [
            entry for entry in matches
            if entry.get("kind") == "textbook_cases"
        ][:1]
        for m in [*primary_matches, *textbook_supplements]:
            key = (m["case_id"], m["station_n"])
            if key in seen:
                continue
            seen.add(key)
            out.append({
                "trigger_feature": needed_feature,
                **m,
            })

    return out


def _format_workpiece(w: dict) -> str:
    parts = [f'type="{w["type"]}"']
    for k in (
        "overall_length_mm",
        "max_diameter_mm",
        "head_diameter_mm",
        "head_height_mm",
        "shank_diameter_mm",
        "shank_length_mm",
        "head_recess_diameter_mm",
        "head_recess_depth_mm",
        "through_hole_diameter_mm",
        "corner_radius_mm",
        "chamfer_C_mm",
        "fillet_R_mm",
    ):
        v = w.get(k)
        if v is not None:
            parts.append(f'{k}="{v}"')
    profile = w.get("profile_segments") or []
    if profile:
        profile_bits = []
        for seg in profile[:6]:
            label = seg.get("label_zh") or "段"
            length = seg.get("length_mm", "")
            diameter = seg.get("diameter_mm", "")
            end_diameter = seg.get("end_diameter_mm")
            if end_diameter is not None and end_diameter != diameter:
                profile_bits.append(f"{label}:L{length},D{diameter}->{end_diameter}")
            else:
                profile_bits.append(f"{label}:L{length},D{diameter}")
        parts.append(f'profile="{_xml_escape("; ".join(profile_bits))}"')
    extras = w.get("extra_dims_mm") or {}
    if extras:
        extra_str = ", ".join(f"{k}={v}" for k, v in extras.items())
        parts.append(f'extra="{_xml_escape(extra_str)}"')
    notes = w.get("notes_zh")
    if notes:
        return f"<workpiece {' '.join(parts)}>{_xml_escape(notes)}</workpiece>"
    return f"<workpiece {' '.join(parts)}/>"


def _format_case(rec: CaseRecord) -> str:
    pf = rec.process_forming.model_dump(exclude_none=True, mode="json")
    feats = rec.part_features.model_dump(exclude_none=True, mode="json")

    feat_lines = [
        f"  <part_number>{_xml_escape(feats.get('part_number', ''))}</part_number>",
        f"  <description>{_xml_escape(feats.get('description', ''))}</description>",
        f"  <overall_length_mm>{feats.get('overall_length', '')}</overall_length_mm>",
        f"  <material_grade>{_xml_escape(feats.get('material_grade', ''))}</material_grade>",
    ]
    if feats.get("strength_grade"):
        feat_lines.append(
            f"  <strength_grade>{_xml_escape(feats['strength_grade'])}</strength_grade>"
        )
    if feats.get("standard"):
        feat_lines.append(f"  <standard>{_xml_escape(feats['standard'])}</standard>")
    if feats.get("thread"):
        t = feats["thread"]
        feat_lines.append(
            f'  <thread spec="{_xml_escape(t.get("spec", ""))}" '
            f'nominal_diameter="{t.get("nominal_diameter", "")}" '
            f'pitch="{t.get("pitch", "")}" length="{t.get("length", "")}"/>'
        )
    if feats.get("head"):
        h = feats["head"]
        feat_lines.append(
            f'  <head type="{h.get("type", "")}" diameter="{h.get("diameter", "")}" '
            f'height="{h.get("height", "")}"/>'
        )
    if feats.get("shank"):
        s = feats["shank"]
        feat_lines.append(
            f'  <shank diameter="{s.get("diameter", "")}" length="{s.get("length", "")}"/>'
        )

    station_lines: list[str] = []
    for st in pf["stations"]:
        kd = st.get("key_dimensions") or {}
        kd_attrs = " ".join(f'{k}="{v}"' for k, v in kd.items())
        wp = _format_workpiece(st["workpiece"])
        notes = _xml_escape(st.get("notes_zh", "") or "")
        station_lines.append(
            f'    <station n="{st["n"]}" operation="{st["operation"]}" {kd_attrs}>\n'
            f"      {wp}\n"
            f"      <notes>{notes}</notes>\n"
            f"    </station>"
        )

    blank_xml = _format_workpiece(pf["blank"])
    post = ", ".join(pf.get("post_processes") or [])

    return (
        f'<case id="{_xml_escape(rec.case_id)}" '
        f'category="{_xml_escape(rec.product_category)}" '
        f'source="{rec.source_kind}" '
        f'extracted_by="{rec.extracted_by}">\n'
        f"  <part_name_zh>{_xml_escape(rec.product_name_zh)}</part_name_zh>\n"
        f"  <material>{_xml_escape(rec.material)}</material>\n"
        f"  <part_features>\n" + "\n".join(feat_lines) + "\n  </part_features>\n"
        f'  <process_forming station_count="{len(pf["stations"])}">\n'
        f"    <blank>{blank_xml}</blank>\n"
        f"    <stations>\n" + "\n".join(station_lines) + "\n    </stations>\n"
        f"    <post_processes>{_xml_escape(post)}</post_processes>\n"
        f"    <reasoning_zh>{_xml_escape(pf['reasoning_zh'])}</reasoning_zh>\n"
        f"  </process_forming>\n"
        f"</case>"
    )


def _format_json_record(tag: str, rec: dict[str, Any]) -> str:
    """Format a loose textbook/pattern JSON record as XML-wrapped JSON."""
    source = rec.get("source") or rec.get("source_id") or "unknown"
    record_id = rec.get("id") or rec.get("case_id") or rec.get("pattern_id") or source
    body = json.dumps(rec, ensure_ascii=False, indent=2)
    return (
        f'<{tag} id="{_xml_escape(str(record_id))}" '
        f'source="{_xml_escape(str(source))}">\n'
        f"{_xml_escape(body)}\n"
        f"</{tag}>"
    )


def format_for_prompt(
    lib: Library,
    *,
    prefer_category: str | None = None,
    only_human_reviewed: bool = False,
    part_features: Any = None,
    exclude_case_ids: list[str] | set[str] | None = None,
) -> str:
    """Format the entire library as one XML block for Step 3 few-shot.

    Args:
        prefer_category: place cases matching this category first (the LLM
            tends to weight earlier examples more heavily).
        only_human_reviewed: drop extracted_by="llm_draft" records. Default
            False so the demo can run before manual review is complete.
        exclude_case_ids: leave-one-out evaluation support. Excluded cases are
            removed from both the full case dump and relevant station snippets.
    """
    excluded = set(exclude_case_ids or [])
    records = lib.all_records
    if excluded:
        records = [r for r in records if r.case_id not in excluded]
    if only_human_reviewed:
        records = [r for r in records if r.extracted_by == "human_reviewed"]

    if prefer_category:
        matching = [r for r in records if r.product_category == prefer_category]
        rest = [r for r in records if r.product_category != prefer_category]
        records = matching + rest

    case_xml = "\n\n".join(_format_case(r) for r in records)

    rule_xml_parts: list[str] = []
    for name, body in lib.rules.items():
        rule_xml_parts.append(
            f'<rule_set name="{_xml_escape(name)}">\n{_xml_escape(body)}\n</rule_set>'
        )
    rule_xml = "\n\n".join(rule_xml_parts) if rule_xml_parts else "<!-- no rules curated yet -->"

    textbook_rule_parts: list[str] = []
    for name, body in lib.textbook_rules.items():
        textbook_rule_parts.append(
            f'<textbook_rule name="{_xml_escape(name)}">\n{_xml_escape(body)}\n</textbook_rule>'
        )
    textbook_rule_xml = (
        "\n\n".join(textbook_rule_parts)
        if textbook_rule_parts
        else "<!-- no textbook rules distilled yet -->"
    )

    textbook_case_xml = (
        "\n\n".join(_format_json_record("textbook_case", rec) for rec in lib.textbook_cases)
        or "<!-- no textbook cases distilled yet -->"
    )

    pattern_xml = (
        "\n\n".join(_format_json_record("pattern", rec) for rec in lib.patterns)
        or "<!-- no reusable patterns distilled yet -->"
    )

    relevant_xml = "<!-- no input features provided -->"
    if part_features is not None:
        snippets = select_relevant_subprocesses(
            lib,
            part_features,
            exclude_case_ids=excluded,
        )
        if snippets:
            # Build a map of case_id → CaseRecord for richer station lookups
            record_by_id = {
                r.case_id: r for r in lib.cases + lib.standards
                if r.case_id not in excluded
            }
            textbook_by_id = {
                str(rec.get("id") or rec.get("case_id") or rec.get("source") or ""): rec
                for rec in lib.textbook_cases
            }
            lines = []
            for s in snippets:
                rec = record_by_id.get(s["case_id"])
                # Pull the actual station JSON from the record so the LLM
                # gets dimensions, not just a 240-char summary.
                station_json = ""
                if rec is not None:
                    pf = rec.process_forming.model_dump(exclude_none=True, mode="json")
                    target = next(
                        (st for st in pf.get("stations") or [] if st.get("n") == s["station_n"]),
                        None,
                    )
                    if target is not None:
                        station_json = json.dumps(target, ensure_ascii=False, indent=2)
                else:
                    textbook_rec = textbook_by_id.get(s["case_id"])
                    if textbook_rec is not None:
                        target = next(
                            (
                                st for st in textbook_rec.get("station_sequence", [])
                                if st.get("n") == s["station_n"]
                            ),
                            None,
                        )
                        if target is not None:
                            station_json = json.dumps(target, ensure_ascii=False, indent=2)
                lines.append(
                    f'<relevant_station '
                    f'trigger_feature="{_xml_escape(s["trigger_feature"])}" '
                    f'case_id="{_xml_escape(s["case_id"])}" '
                    f'station_n="{s["station_n"]}" '
                    f'operation="{_xml_escape(s["operation"])}">\n'
                    f"<summary>{_xml_escape((s.get('summary') or '')[:240])}</summary>\n"
                    f"<station_data>{_xml_escape(station_json)}</station_data>\n"
                    f"</relevant_station>"
                )
            relevant_xml = "\n".join(lines)
        else:
            input_feats = detect_input_features(part_features)
            relevant_xml = (
                f"<!-- detected input features: {', '.join(input_feats) or 'none'} "
                "but no matching station snippets in feature_index -->"
            )

    # 优化 3 fix: relevant_subprocesses placed FIRST so the LLM reads it before
    # being distracted by the bulk <cases> dump. Prompt v1.2.0 explicitly
    # tells the LLM to start here and cite its case_ids.
    return (
        "<knowledge_library>\n"
        f"  <relevant_subprocesses>\n{relevant_xml}\n  </relevant_subprocesses>\n"
        f"  <rules>\n{rule_xml}\n  </rules>\n"
        f"  <textbook_knowledge>\n{textbook_rule_xml}\n  </textbook_knowledge>\n"
        f"  <patterns>\n{pattern_xml}\n  </patterns>\n"
        f'  <cases count="{len(records)}">\n{case_xml}\n  </cases>\n'
        f'  <textbook_cases count="{len(lib.textbook_cases)}">\n{textbook_case_xml}\n  </textbook_cases>\n'
        "</knowledge_library>"
    )
