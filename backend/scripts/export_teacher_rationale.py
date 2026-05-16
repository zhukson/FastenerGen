"""Export deterministic teacher rationale checkpoints for one library case."""

from __future__ import annotations

import argparse
from pathlib import Path

from app.calibration.dataset import build_case_record_eval_case
from app.calibration.teacher_rationale import build_teacher_rationale_from_eval_case
from app.knowledge.loader import load_library


def main() -> None:
    args = _parse_args()
    records = {record.case_id: record for record in load_library().all_records}
    record = records.get(args.case_id)
    if record is None:
        raise SystemExit(f"Unknown case_id: {args.case_id}")

    rationale = build_teacher_rationale_from_eval_case(
        build_case_record_eval_case(record)
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        rationale.model_dump_json(indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {args.out}")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--out", type=Path, required=True)
    return parser.parse_args()


if __name__ == "__main__":
    main()
