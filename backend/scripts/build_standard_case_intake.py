"""Build an intake manifest for standard forming-process PNG cases."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from app.knowledge.loader import load_library


def main() -> None:
    args = _parse_args()
    source_dir = args.source_dir
    pngs = sorted(source_dir.glob("*/*.png"))
    existing_records = load_library().standards
    cases = [
        _case_item(path, source_dir, ocr_dir=args.ocr_dir, existing_records=existing_records)
        for path in pngs
    ]
    payload = {
        "source_dir": str(source_dir),
        "case_count": len(cases),
        "cases": cases,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {args.out}")


def _case_item(
    path: Path,
    source_dir: Path,
    *,
    ocr_dir: Path | None,
    existing_records: list[Any],
) -> dict[str, Any]:
    parsed = _parse_standard_png_name(path.stem)
    standard = parsed["standard_ref"]
    case_id = _case_id(parsed)
    ocr_text_file = None
    if ocr_dir is not None:
        candidate = ocr_dir / f"{case_id}.ocr.txt"
        if candidate.exists():
            ocr_text_file = str(candidate)

    existing_case_ids = _matching_existing_standard_case_ids(parsed, existing_records)
    return {
        "case_id": case_id,
        "source_file": str(path),
        "relative_source_file": str(path.relative_to(source_dir)),
        "standard_ref": standard,
        "product_category": _category_for_standard(standard),
        "nominal_diameter_mm": parsed["nominal_diameter_mm"],
        "pitch_mm": parsed["pitch_mm"],
        "length_range_mm": parsed["length_range_mm"],
        "ocr_text_file": ocr_text_file,
        "existing_standard_case_ids": existing_case_ids,
        "status": (
            "needs_review_existing_overlap"
            if existing_case_ids
            else "pending_extraction"
        ),
    }


def _parse_standard_png_name(stem: str) -> dict[str, Any]:
    normalized = re.sub(r"\s+", " ", stem.strip())
    match = re.search(
        r"DIN\s*(?P<std>912|933)\s*M(?P<diam>\d+)\s*P(?P<pitch>\d+(?:\.\d+)?)x"
        r"(?P<start>\d+)-(?P<end>\d+)L",
        normalized,
        flags=re.IGNORECASE,
    )
    if not match:
        raise SystemExit(f"Cannot parse standard PNG filename: {stem}")
    return {
        "standard_ref": f"DIN{match.group('std')}",
        "nominal_diameter_mm": int(match.group("diam")),
        "pitch_mm": float(match.group("pitch")),
        "length_range_mm": [int(match.group("start")), int(match.group("end"))],
    }


def _case_id(parsed: dict[str, Any]) -> str:
    start, end = parsed["length_range_mm"]
    return (
        f"STD-{parsed['standard_ref']}-M{parsed['nominal_diameter_mm']}"
        f"-P{parsed['pitch_mm']:.1f}-{start}-{end}L"
    )


def _category_for_standard(standard: str) -> str:
    if standard == "DIN912":
        return "socket_cap_screw_DIN912"
    if standard == "DIN933":
        return "hex_bolt_DIN933"
    return "standard_part"


def _matching_existing_standard_case_ids(
    parsed: dict[str, Any],
    existing_records: list[Any],
) -> list[str]:
    matches: list[str] = []
    for record in existing_records:
        features = record.part_features
        thread = features.thread
        if record.standard_ref != parsed["standard_ref"] or thread is None:
            continue
        if int(thread.nominal_diameter) != parsed["nominal_diameter_mm"]:
            continue
        if thread.pitch is None or abs(thread.pitch - parsed["pitch_mm"]) > 1e-6:
            continue
        matches.append(record.case_id)
    return sorted(matches)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--ocr-dir", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    return parser.parse_args()


if __name__ == "__main__":
    main()
