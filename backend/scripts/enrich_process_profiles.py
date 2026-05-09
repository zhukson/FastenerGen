"""Deterministically add profile_segments to ProcessForming knowledge cases.

The first v2 schema only had coarse workpiece primitives (overall L/D,
head/shank D/L). Real 过模图s are segment drawings: each station is a small
axial profile with shoulders, necks, heads, grooves, and tapered sections.

This script backfills a conservative profile_segments list from dimensions we
already trust in the case JSON. It does not call an LLM and it does not invent
new source cases. Re-run after case extraction to make the few-shot examples
teach the renderer/LLM the fine-grained shape contract.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
KNOWLEDGE_ROOT = ROOT / "app" / "knowledge"


def _num(*values: Any) -> float | None:
    for value in values:
        if isinstance(value, int | float):
            return float(value)
        if isinstance(value, str):
            cleaned = value.replace("φ", "").replace("Φ", "").replace("ø", "")
            try:
                return float(cleaned)
            except ValueError:
                continue
    return None


def _get(w: dict[str, Any], key_dims: dict[str, Any], *names: str) -> float | None:
    extra = w.get("extra_dims_mm") or {}
    for name in names:
        value = _num(w.get(name))
        if value is not None:
            return value
    for name in names:
        value = _num(key_dims.get(name))
        if value is not None:
            return value
    for name in names:
        value = _num(extra.get(name))
        if value is not None:
            return value
    return None


def _seg(label: str, length: float, diameter: float, end_diameter: float | None = None) -> dict[str, Any]:
    item: dict[str, Any] = {
        "label_zh": label,
        "length_mm": round(max(length, 0.0), 3),
        "diameter_mm": round(max(diameter, 0.0), 3),
    }
    if end_diameter is not None and abs(end_diameter - diameter) > 0.01:
        item["end_diameter_mm"] = round(max(end_diameter, 0.0), 3)
    return item


def infer_profile_segments(w: dict[str, Any], key_dims: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Infer a conservative left-to-right axial profile from existing dims."""
    key_dims = key_dims or {}
    if w.get("profile_segments"):
        return list(w["profile_segments"])

    length = _get(w, key_dims, "overall_length_mm", "L", "total_L")
    max_d = _get(w, key_dims, "max_diameter_mm", "D", "max_D", "flat_W", "head_W")
    if not length or length <= 0 or not max_d or max_d <= 0:
        return []

    typ = str(w.get("type") or "cylinder")
    head_h = _get(w, key_dims, "head_height_mm", "head_H", "H", "H_head")
    head_d = _get(
        w,
        key_dims,
        "head_diameter_mm",
        "head_D",
        "D_head",
        "D_head_circ",
        "head_C",
        "head_W",
        "flat_W",
    )
    shank_l = _get(w, key_dims, "shank_length_mm", "shank_L", "thread_L")
    shank_d = _get(w, key_dims, "shank_diameter_mm", "shank_D", "D_shank", "thread_blank_D")

    if typ == "cylinder":
        return [_seg("直杆/坯料", length, max_d)]

    if typ == "tapered":
        tail_d = _get(w, key_dims, "tail_D", "tip_D") or 0.0
        return [_seg("锥形段", length, max_d, tail_d)]

    if typ == "pin":
        chamfer = _get(w, key_dims, "chamfer_c_mm", "chamfer_C_mm", "C") or min(length * 0.08, max_d * 0.12)
        body_l = max(length - chamfer * 2, length * 0.7)
        return [
            _seg("左倒角", chamfer, max(max_d - chamfer * 2, max_d * 0.7), max_d),
            _seg("销体", body_l, max_d),
            _seg("右倒角", chamfer, max_d, max(max_d - chamfer * 2, max_d * 0.7)),
        ]

    if typ in {"stepped", "headed", "square_head", "T_head", "flanged", "custom"}:
        shank_d = shank_d or min(max_d * 0.72, head_d or max_d)
        if shank_l is None:
            shank_l = max(length - (head_h or length * 0.28), length * 0.45)
        shank_l = min(max(shank_l, 0.0), length)
        remaining = max(length - shank_l, 0.0)

        if head_h is None:
            head_h = remaining if remaining > 0 else length * 0.28
        head_h = min(max(head_h, 0.0), length)
        head_d = head_d or max_d

        segs: list[dict[str, Any]] = []
        if shank_l > 0.05:
            segs.append(_seg("杆部", shank_l, shank_d))

        transition_l = max(length - shank_l - head_h, 0.0)
        if transition_l > 0.05:
            segs.append(_seg("过渡台阶", transition_l, shank_d, min(head_d, max_d)))

        head_len = max(length - sum(s["length_mm"] for s in segs), 0.0)
        if head_len > 0.05:
            head_label = "头部/法兰" if typ in {"flanged", "T_head", "square_head"} else "头部"
            segs.append(_seg(head_label, head_len, max(head_d, max_d if typ == "flanged" else head_d)))

        return segs or [_seg("轮廓", length, max_d)]

    return [_seg("轮廓", length, max_d)]


def enrich_record(record: dict[str, Any]) -> int:
    pf = record.get("process_forming") or {}
    changed = 0

    blank = pf.get("blank")
    if isinstance(blank, dict) and not blank.get("profile_segments"):
        inferred = infer_profile_segments(blank, {})
        if inferred:
            blank["profile_segments"] = inferred
            changed += 1

    for station in pf.get("stations") or []:
        if not isinstance(station, dict):
            continue
        w = station.get("workpiece")
        if not isinstance(w, dict) or w.get("profile_segments"):
            continue
        inferred = infer_profile_segments(w, station.get("key_dimensions") or {})
        if inferred:
            w["profile_segments"] = inferred
            changed += 1
    return changed


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true", help="Write JSON files in-place")
    parser.add_argument(
        "--roots",
        nargs="*",
        default=["cases", "standards"],
        choices=["cases", "standards"],
        help="Knowledge subdirectories to enrich",
    )
    args = parser.parse_args()

    total_files = 0
    total_workpieces = 0
    for root_name in args.roots:
        for path in sorted((KNOWLEDGE_ROOT / root_name).glob("*.json")):
            data = json.loads(path.read_text(encoding="utf-8"))
            changed = enrich_record(data)
            total_files += 1
            total_workpieces += changed
            if changed and args.write:
                path.write_text(
                    json.dumps(data, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                )
            print(f"{path.relative_to(ROOT)}: +{changed} profile workpieces")

    mode = "wrote" if args.write else "dry-run"
    print(f"{mode}: files={total_files}, enriched_workpieces={total_workpieces}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
