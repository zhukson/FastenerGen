"""Build a batch-calibration manifest from a dataset and prediction map."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def main() -> None:
    args = _parse_args()
    dataset = json.loads(args.dataset.read_text(encoding="utf-8"))
    prediction_map = json.loads(args.prediction_map.read_text(encoding="utf-8"))

    cases = []
    for item in dataset.get("cases", []):
        case_id = item["case_id"]
        prediction = prediction_map.get(case_id)
        if prediction is None:
            continue
        case_item: dict[str, Any] = {
            "case_id": case_id,
            "predicted": prediction,
        }
        if item.get("teacher_rationale"):
            case_item["teacher_rationale"] = item["teacher_rationale"]
        if item.get("retrieved_case_ids"):
            case_item["retrieved_case_ids"] = item["retrieved_case_ids"]
        cases.append(case_item)

    manifest = {
        "eval_id": args.eval_id or dataset.get("source") or args.dataset.stem,
        "cases": cases,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {args.out}")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--prediction-map", type=Path, required=True)
    parser.add_argument("--eval-id")
    parser.add_argument("--out", type=Path, required=True)
    return parser.parse_args()


if __name__ == "__main__":
    main()
