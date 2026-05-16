"""Build a calibration report from an existing ProcessForming prediction.

This is offline: it does not call an LLM. It loads a GT case from the current
knowledge library, compares the predicted ProcessForming JSON, and writes a
teacher-rationale + GT metric report.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.calibration.dataset import build_case_record_eval_case
from app.calibration.report import build_calibration_report
from app.calibration.teacher_rationale import TeacherRationale
from app.data.schemas import ProcessForming
from app.knowledge.loader import load_library


def main() -> None:
    args = _parse_args()
    library = load_library()
    records = library.cases + library.standards
    record = next((r for r in records if r.case_id == args.case_id), None)
    if record is None:
        raise SystemExit(f"Unknown case_id: {args.case_id}")

    eval_case = build_case_record_eval_case(record)
    predicted = ProcessForming.model_validate(
        json.loads(args.predicted.read_text(encoding="utf-8"))
    )
    teacher_rationale = (
        TeacherRationale.model_validate(
            json.loads(args.teacher_rationale.read_text(encoding="utf-8"))
        )
        if args.teacher_rationale
        else None
    )
    report = build_calibration_report(
        eval_case=eval_case,
        predicted=predicted,
        retrieved_case_ids=args.retrieved_case,
        teacher_rationale=teacher_rationale,
    )

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        report.model_dump_json(indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {args.out}")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--predicted", type=Path, required=True)
    parser.add_argument("--teacher-rationale", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--retrieved-case", action="append", default=[])
    return parser.parse_args()


if __name__ == "__main__":
    main()
