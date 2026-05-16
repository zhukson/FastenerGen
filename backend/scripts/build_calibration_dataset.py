"""Build a calibration dataset manifest from curated library records."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Literal

from app.calibration.dataset import build_case_record_eval_case
from app.data.schemas import CaseRecord
from app.knowledge.loader import load_library

Source = Literal["factory", "standard", "all"]


def main() -> None:
    args = _parse_args()
    records = _records_for_source(args.source)
    cases = [_manifest_item(record, args.teacher_rationale_dir) for record in records]
    payload = {
        "source": args.source,
        "case_count": len(cases),
        "cases": cases,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {args.out}")


def _manifest_item(
    record: CaseRecord,
    teacher_rationale_dir: Path | None,
) -> dict[str, object]:
    eval_case = build_case_record_eval_case(record)
    teacher_rationale = None
    if teacher_rationale_dir is not None:
        teacher_rationale = str(
            teacher_rationale_dir / f"{_safe_case_filename(record.case_id)}.json"
        )
    return {
        "case_id": eval_case.case_id,
        "source_type": eval_case.source_type,
        "trust_level": eval_case.trust_level,
        "product_name_zh": record.product_name_zh,
        "product_category": record.product_category,
        "part_number": record.part_features.part_number,
        "holdout_case_ids": eval_case.holdout_case_ids,
        "tags": eval_case.tags,
        "teacher_rationale": teacher_rationale,
        "suggested_command": _suggested_command(record),
    }


def _suggested_command(record: CaseRecord) -> str:
    return (
        "uv run python -m scripts.run_gong_experiment "
        f"--experiment-id calibration_{_safe_case_filename(record.case_id)} "
        "--part-features path/to/part_features.json "
        "--expected path/to/process_parameters_ground_truth.json "
        f"--exclude-case {record.case_id} "
        f"--prefer-category {record.product_category} "
        "--candidate-count 1 --max-design-attempts 1"
    )


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
    parser.add_argument("--teacher-rationale-dir", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    return parser.parse_args()


if __name__ == "__main__":
    main()
