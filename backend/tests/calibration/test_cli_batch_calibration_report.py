"""CLI behavior for offline batch calibration aggregation."""

import json
import subprocess
from pathlib import Path


def test_cli_writes_batch_calibration_report_from_manifest(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.json"
    predicted = Path(
        "experiments/square_t_cap_holdout/runs/"
        "official_opus47_thinking_compact_20260511/process_parameters.json"
    )
    manifest.write_text(
        json.dumps(
            {
                "eval_id": "batch-smoke",
                "cases": [
                    {
                        "case_id": "DJGS-25-8-B001-0358-四方T帽-106S-过模图",
                        "predicted": str(predicted),
                        "retrieved_case_ids": ["DJGS-22-2-四方通孔-105S-过模图"],
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    out = tmp_path / "batch_calibration_report.json"

    result = subprocess.run(
        [
            "python",
            "-m",
            "scripts.build_batch_calibration_report",
            "--manifest",
            str(manifest),
            "--out",
            str(out),
        ],
        check=False,
        cwd=Path(__file__).resolve().parents[2],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    report = json.loads(out.read_text(encoding="utf-8"))
    assert report["eval_id"] == "batch-smoke"
    assert report["case_count"] == 1
    assert report["failure_tag_counts"]["wrong_precedence"] == 1
    metric_names = {metric["metric_name"] for metric in report["metric_means"]}
    assert "required_operation_recall_mean" in metric_names
    assert report["case_reports"][0]["case_id"] == "DJGS-25-8-B001-0358-四方T帽-106S-过模图"


def test_cli_batch_uses_teacher_rationale_file_when_provided(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.json"
    predicted = Path(
        "experiments/square_t_cap_holdout/runs/"
        "official_opus47_thinking_compact_20260511/process_parameters.json"
    )
    rationale = tmp_path / "teacher_rationale.json"
    rationale.write_text(
        json.dumps(
            {
                "case_id": "DJGS-25-8-B001-0358-四方T帽-106S-过模图",
                "required_operations": [
                    {
                        "operation": "backward_extrusion",
                        "why_zh": "测试用持久化 checkpoint",
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    manifest.write_text(
        json.dumps(
            {
                "eval_id": "batch-rationale-smoke",
                "cases": [
                    {
                        "case_id": "DJGS-25-8-B001-0358-四方T帽-106S-过模图",
                        "predicted": str(predicted),
                        "teacher_rationale": str(rationale),
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    out = tmp_path / "batch_calibration_report.json"

    result = subprocess.run(
        [
            "python",
            "-m",
            "scripts.build_batch_calibration_report",
            "--manifest",
            str(manifest),
            "--out",
            str(out),
        ],
        check=False,
        cwd=Path(__file__).resolve().parents[2],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    report = json.loads(out.read_text(encoding="utf-8"))
    recall = next(
        metric
        for metric in report["case_reports"][0]["metrics"]
        if metric["metric_name"] == "required_operation_recall"
    )
    assert recall["notes"] == "missing: backward_extrusion"


def test_cli_accepts_experiment_manifest_notes_list(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.json"
    predicted = Path(
        "experiments/square_t_cap_holdout/runs/"
        "official_opus47_thinking_compact_20260511/process_parameters.json"
    )
    manifest.write_text(
        json.dumps(
            {
                "experiment": "square_t_cap_holdout",
                "ground_truth": {
                    "case_record": "experiments/square_t_cap_holdout/ground_truth/case_record_ground_truth.json"
                },
                "prediction": str(predicted),
                "excluded_from_runtime_knowledge": "DJGS-25-8-B001-0358-四方T帽-106S-过模图",
                "notes": ["first note", "second note"],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    out = tmp_path / "batch_calibration_report.json"

    result = subprocess.run(
        [
            "python",
            "-m",
            "scripts.build_batch_calibration_report",
            "--manifest",
            str(manifest),
            "--out",
            str(out),
        ],
        check=False,
        cwd=Path(__file__).resolve().parents[2],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    report = json.loads(out.read_text(encoding="utf-8"))
    assert report["eval_id"] == "square_t_cap_holdout"
    assert report["case_count"] == 1
    assert report["notes"] == "first note\nsecond note"
