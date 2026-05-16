"""Build a feature-indexed sub-process pattern library (优化 3).

Reads all CaseRecord-style JSONs (cases/, standards/, textbook_cases/) and
emits ``app/knowledge/feature_index.json`` mapping each detected feature to
the list of (case_id, station_n, operation) tuples that demonstrate it.

The loader can then inject **only the relevant sub-process patterns** into
the LLM prompt based on the input PartFeatures, instead of forcing it to
look at every case as a monolithic blob.

This is a deterministic keyword/numeric tagger — no LLM needed. Quality is
~80% which is enough for demo. Re-run with ``--llm`` later (when API is
available) to refine via Haiku.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
KNOWLEDGE_ROOT = ROOT / "app" / "knowledge"
OUTPUT = KNOWLEDGE_ROOT / "feature_index.json"

# Feature taxonomy: each tuple = (feature_id, [keyword regexes])
# Keywords match against station notes, geometry descriptions, and reasoning text.
FEATURE_KEYWORDS: dict[str, list[str]] = {
    # === Head shapes ===
    "internal_hex_head": [r"内六角", r"hex socket", r"hex_socket", r"socket_head"],
    "internal_torx_head": [r"内梅花", r"torx", r"梅花孔"],
    "internal_recess": [r"凹头", r"内凹", r"recess"],
    "external_hex_head": [r"外六角", r"hex bolt", r"hex_bolt", r"hex_flange"],
    "external_square_head": [r"四方头", r"方头", r"square_head", r"square head", r"T头", r"四方T", r"T帽"],
    "external_pan_head": [r"圆头", r"半圆头", r"pan head", r"pan_head", r"round_head"],
    "external_ball_head": [r"球头", r"ball_head", r"球面"],
    "external_flange_head": [r"法兰", r"flange_head", r"flange head"],
    # === Body / shank features ===
    "shoulder_step": [r"阶梯", r"台阶", r"step", r"shouldered", r"stepped"],
    "taper_end": [r"倒锥", r"倒角", r"chamfer", r"taper_end", r"45°锥", r"30°锥", r"圆弧过渡"],
    "long_thin_shank": [],  # filled by numeric rule below (L/D > 5)
    "thread_external": [r"外螺纹", r"螺纹", r"thread_rolling", r"M\d+×", r"M\d+x"],
    "thread_internal": [r"内螺纹", r"攻丝", r"thread_tapping", r"内攻"],
    "through_hole": [r"通孔", r"through_hole", r"through hole", r"空心", r"内孔", r"bore", r"hollow"],
    "rivet_tail": [r"铆接", r"铆钉", r"riveting"],
    # === Process features (operations seen in stations) ===
    "op_predeform_conical": [r"预镦", r"聚料", r"锥形过渡", r"锥形预成形"],
    "op_backward_extrude_socket": [r"反挤", r"backward_extrusion", r"内六角", r"六角孔", r"hex"],
    "op_forward_extrude_taper": [r"正挤", r"forward_extrusion"],
    "op_trim_polygon": [r"切边", r"修边", r"修方", r"修六角", r"trimming"],
    "op_pierce_through": [r"冲通孔", r"冲孔", r"piercing"],
    "op_two_blow_upset": [r"两道镦粗", r"二段镦粗", r"二次镦粗", r"分二道"],
}


def detect_features(record: dict[str, Any]) -> list[str]:
    """Run keyword + numeric rules over a CaseRecord-shaped dict."""
    blob_parts: list[str] = []
    for key in ("part_name_zh", "product_category", "title_zh", "description"):
        v = record.get(key)
        if isinstance(v, str):
            blob_parts.append(v)

    pf = record.get("process_forming") or {}
    blob_parts.append(pf.get("part_name_zh", "") or "")
    blob_parts.append(pf.get("reasoning_zh", "") or "")
    for st in pf.get("stations", []):
        blob_parts.append(st.get("notes_zh", "") or "")
        blob_parts.append(st.get("operation", "") or "")

    # textbook case format
    blob_parts.append(record.get("visible_process_summary_zh", "") or "")
    for st in record.get("station_sequence", []):
        blob_parts.append(st.get("label_zh", "") or "")
        blob_parts.append(st.get("geometry_zh", "") or "")

    blob = " ".join(p for p in blob_parts if p)
    detected: list[str] = []
    for feature, patterns in FEATURE_KEYWORDS.items():
        for pat in patterns:
            if re.search(pat, blob, flags=re.IGNORECASE):
                detected.append(feature)
                break

    # Numeric rule: long_thin_shank if L/D > 5 on the FINAL station
    final_st = (pf.get("stations") or [{}])[-1] if pf.get("stations") else {}
    wp = (final_st.get("workpiece") or {}) if final_st else {}
    length = wp.get("overall_length_mm") or 0
    diameter = wp.get("max_diameter_mm") or 0
    if length > 0 and diameter > 0 and length / diameter > 5.0:
        detected.append("long_thin_shank")

    return sorted(set(detected))


def collect_station_features(record: dict[str, Any], record_id: str) -> list[dict[str, Any]]:
    """Return one entry per station with that station's specific feature tags."""
    pf = record.get("process_forming") or {}
    out: list[dict[str, Any]] = []
    for st in pf.get("stations", []):
        n = st.get("n")
        op = st.get("operation", "")
        notes = st.get("notes_zh", "") or ""
        blob = f"{op} {notes}"
        st_features: list[str] = []
        for feature, patterns in FEATURE_KEYWORDS.items():
            if not feature.startswith("op_"):
                # Station-level tagging only tracks process-flavor features
                continue
            for pat in patterns:
                if re.search(pat, blob, flags=re.IGNORECASE):
                    st_features.append(feature)
                    break
        # Also tag by literal operation
        if op:
            st_features.append(f"raw_op:{op}")
        out.append({
            "case_id": record_id,
            "station_n": n,
            "operation": op,
            "features": sorted(set(st_features)),
            "summary": notes[:200],
        })

    for st in record.get("station_sequence", []):
        n = st.get("n")
        label = st.get("label_zh", "") or ""
        geometry = st.get("geometry_zh", "") or ""
        blob = f"{label} {geometry}"
        operation = _infer_operation(blob)
        st_features: list[str] = []
        for feature, patterns in FEATURE_KEYWORDS.items():
            if not feature.startswith("op_"):
                continue
            for pat in patterns:
                if re.search(pat, blob, flags=re.IGNORECASE):
                    st_features.append(feature)
                    break
        if operation:
            st_features.append(f"raw_op:{operation}")
        out.append({
            "case_id": record_id,
            "station_n": n,
            "operation": operation,
            "features": sorted(set(st_features)),
            "summary": blob[:200],
        })
    return out


def _infer_operation(blob: str) -> str:
    """Infer an OperationType-ish string for loose textbook station records."""
    if re.search(r"反挤|内六角|六角孔|backward", blob, flags=re.IGNORECASE):
        return "backward_extrusion"
    if re.search(r"正挤|缩径|forward", blob, flags=re.IGNORECASE):
        return "forward_extrusion"
    if re.search(r"冲孔|通孔|pierc", blob, flags=re.IGNORECASE):
        return "piercing"
    if re.search(r"切边|修边|trim", blob, flags=re.IGNORECASE):
        return "trimming"
    if re.search(r"终镦|终成形|精整|heading", blob, flags=re.IGNORECASE):
        return "heading"
    if re.search(r"镦|预成形|upset", blob, flags=re.IGNORECASE):
        return "upsetting"
    if re.search(r"切料|下料", blob, flags=re.IGNORECASE):
        return "combined"
    return ""


def main() -> None:
    by_feature: dict[str, list[dict[str, Any]]] = {}
    by_case: dict[str, list[str]] = {}
    station_index: list[dict[str, Any]] = []

    sources = [
        ("cases", KNOWLEDGE_ROOT / "cases"),
        ("standards", KNOWLEDGE_ROOT / "standards"),
        ("textbook_cases", KNOWLEDGE_ROOT / "textbook_cases"),
    ]

    counts = {"cases": 0, "standards": 0, "textbook_cases": 0, "skipped": 0}

    for kind, root in sources:
        for fp in sorted(root.glob("*.json")):
            if fp.name.endswith(".hidden") or fp.name == "feature_index.json":
                continue
            if fp.name.endswith("_index.json"):
                continue
            try:
                rec = json.loads(fp.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                counts["skipped"] += 1
                continue
            case_id = (
                rec.get("case_id")
                or rec.get("standard_id")
                or rec.get("id")
                or fp.stem
            )
            features = detect_features(rec)
            by_case[case_id] = features
            for f in features:
                by_feature.setdefault(f, []).append({"case_id": case_id, "kind": kind})
            station_entries = collect_station_features(rec, case_id)
            for entry in station_entries:
                entry["kind"] = kind
            station_index.extend(station_entries)
            counts[kind] += 1

    payload = {
        "version": "feature_index_v1",
        "counts": counts,
        "by_feature": by_feature,
        "by_case": by_case,
        "station_index": station_index,
    }
    OUTPUT.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Wrote {OUTPUT.relative_to(ROOT)}")
    print(f"  counts: {counts}")
    print(f"  features detected: {len(by_feature)}")
    print(f"  cases covered: {len(by_case)}")
    print(f"  station entries: {len(station_index)}")
    # Top 5 feature coverage
    top = sorted(by_feature.items(), key=lambda kv: -len(kv[1]))[:8]
    print("  top features by coverage:")
    for f, refs in top:
        print(f"    {f:30s} → {len(refs)} cases")


if __name__ == "__main__":
    main()
