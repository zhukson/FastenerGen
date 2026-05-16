"""Export deterministic teacher rationale checkpoints for many library cases."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Literal

from app.calibration.dataset import build_case_record_eval_case
from app.calibration.teacher_rationale import build_teacher_rationale_from_eval_case
from app.data.schemas import CaseRecord
from app.knowledge.loader import load_library

Source = Literal["factory", "standard", "all"]


def main() -> None:
    args = _parse_args()
    records = _records_for_source(args.source)
    args.out_dir.mkdir(parents=True, exist_ok=True)

    manifest_cases = []
    for record in records:
        rationale = build_teacher_rationale_from_eval_case(
            build_case_record_eval_case(record)
        )
        out_path = args.out_dir / f"{_safe_case_filename(record.case_id)}.json"
        out_path.write_text(rationale.model_dump_json(indent=2) + "\n", encoding="utf-8")
        manifest_cases.append(
            {
                "case_id": record.case_id,
                "source_kind": record.source_kind,
                "product_category": record.product_category,
                "teacher_rationale": out_path.name,
                "holdout_case_ids": [record.case_id],
            }
        )

    manifest = {
        "source": args.source,
        "case_count": len(manifest_cases),
        "cases": manifest_cases,
    }
    (args.out_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {len(manifest_cases)} teacher rationales to {args.out_dir}")


def _records_for_source(source: Source) -> list[CaseRecord]:
    library = load_library()
    if source == "factory":
        return library.cases
    if source == "standard":
        return library.standards
    return library.all_records


def _safe_case_filename(case_id: str) -> str:
    return re.sub(r'[\\/:*?"<>|]+', "-", case_id)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", choices=["factory", "standard", "all"], default="all")
    parser.add_argument("--out-dir", type=Path, required=True)
    return parser.parse_args()


if __name__ == "__main__":
    main()
