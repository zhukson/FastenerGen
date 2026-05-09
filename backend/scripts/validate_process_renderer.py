"""Batch-render knowledge cases and report process-DXF visual entity metrics."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import ezdxf

from app.data.schemas import CaseRecord
from app.drawings.process_forming_generator import render_process_forming_dxf

ROOT = Path(__file__).resolve().parents[1]
KNOWLEDGE_ROOT = ROOT / "app" / "knowledge"
DEFAULT_OUT = ROOT.parent / "fasternerGenData" / "test_data" / "renderer_batch_v2"


def _entity_counts(path: Path) -> dict[str, int]:
    doc = ezdxf.readfile(path)
    counts: dict[str, int] = {}
    for entity in doc.modelspace():
        typ = entity.dxftype()
        counts[typ] = counts.get(typ, 0) + 1
    return counts


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--fail-on-regression", action="store_true")
    args = parser.parse_args()

    args.out_dir.mkdir(parents=True, exist_ok=True)
    rows: list[tuple[str, dict[str, int], int]] = []

    for root in [KNOWLEDGE_ROOT / "cases", KNOWLEDGE_ROOT / "standards"]:
        for path in sorted(root.glob("*.json")):
            record = CaseRecord.model_validate(json.loads(path.read_text(encoding="utf-8")))
            out_path = args.out_dir / f"{path.stem}.dxf"
            render_process_forming_dxf(
                record.process_forming,
                output_path=out_path,
                case_id=record.case_id,
            )
            counts = _entity_counts(out_path)
            rows.append((path.stem, counts, out_path.stat().st_size))

    print("name\tLINE\tARC\tCIRCLE\tDIMENSION\tHATCH\tTEXT\tbytes")
    failed = False
    for name, counts, size in rows:
        text_count = counts.get("TEXT", 0) + counts.get("MTEXT", 0)
        print(
            f"{name}\t{counts.get('LINE', 0)}\t{counts.get('ARC', 0)}\t"
            f"{counts.get('CIRCLE', 0)}\t{counts.get('DIMENSION', 0)}\t"
            f"{counts.get('HATCH', 0)}\t{text_count}\t{size}"
        )
        if args.fail_on_regression:
            if counts.get("HATCH", 0) != 0:
                failed = True
            if text_count > 8:
                failed = True
            if counts.get("DIMENSION", 0) < 18:
                failed = True

    if failed:
        print("renderer regression detected")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
