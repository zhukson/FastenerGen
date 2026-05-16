"""Build an offline batch calibration report from existing predictions.

Manifest format:

{
  "eval_id": "factory-holdout-smoke",
  "notes": "optional",
  "cases": [
    {
      "case_id": "DJGS-25-8-B001-0358-四方T帽-106S-过模图",
      "predicted": "experiments/.../process_parameters.json",
      "retrieved_case_ids": ["..."]
    }
  ]
}
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from app.calibration.dataset import build_case_record_eval_case
from app.calibration.report import (
    build_batch_calibration_report,
    build_calibration_report,
)
from app.calibration.teacher_rationale import TeacherRationale
from app.data.schemas import ProcessForming
from app.knowledge.loader import load_library


def main() -> None:
    args = _parse_args()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    records = {record.case_id: record for record in load_library().all_records}
    case_items = _case_items_from_manifest(manifest)

    case_reports = []
    for item in case_items:
        case_reports.append(_build_case_report(item, records, args.manifest.parent))

    report = build_batch_calibration_report(
        eval_id=manifest.get("eval_id") or manifest.get("experiment") or args.manifest.stem,
        case_reports=case_reports,
        notes=_normalize_notes(manifest.get("notes")),
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(report.model_dump_json(indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {args.out}")


def _case_items_from_manifest(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    if "cases" in manifest:
        return list(manifest["cases"])

    case_id = manifest.get("excluded_from_runtime_knowledge")
    prediction = manifest.get("prediction")
    if case_id and prediction:
        return [{"case_id": case_id, "predicted": prediction}]
    return []


def _normalize_notes(notes: Any) -> str | None:
    if notes is None:
        return None
    if isinstance(notes, list):
        return "\n".join(str(note) for note in notes)
    return str(notes)


def _build_case_report(
    item: dict[str, Any],
    records: dict[str, Any],
    manifest_dir: Path,
):
    case_id = item["case_id"]
    record = records.get(case_id)
    if record is None:
        raise SystemExit(f"Unknown case_id: {case_id}")

    predicted_path = _resolve_input_path(Path(item["predicted"]), manifest_dir)
    predicted = ProcessForming.model_validate(
        json.loads(predicted_path.read_text(encoding="utf-8"))
    )
    teacher_rationale = None
    if item.get("teacher_rationale"):
        rationale_path = _resolve_input_path(
            Path(item["teacher_rationale"]),
            manifest_dir,
        )
        teacher_rationale = TeacherRationale.model_validate(
            json.loads(rationale_path.read_text(encoding="utf-8"))
        )
    return build_calibration_report(
        eval_case=build_case_record_eval_case(record),
        predicted=predicted,
        retrieved_case_ids=item.get("retrieved_case_ids", []),
        teacher_rationale=teacher_rationale,
    )


def _resolve_input_path(path: Path, manifest_dir: Path) -> Path:
    if path.is_absolute() or path.exists():
        return path
    return manifest_dir / path


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    return parser.parse_args()


if __name__ == "__main__":
    main()
