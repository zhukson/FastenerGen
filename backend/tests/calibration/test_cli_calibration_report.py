"""CLI behavior for offline calibration report generation."""

import json
import subprocess
from pathlib import Path


def test_cli_writes_calibration_report_for_existing_prediction(tmp_path: Path) -> None:
    predicted = Path(
        "experiments/square_t_cap_holdout/runs/"
        "official_opus47_thinking_compact_20260511/process_parameters.json"
    )
    out = tmp_path / "calibration_report.json"

    result = subprocess.run(
        [
            "python",
            "-m",
            "scripts.build_calibration_report",
            "--case-id",
            "DJGS-25-8-B001-0358-四方T帽-106S-过模图",
            "--predicted",
            str(predicted),
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
    assert report["case_id"] == "DJGS-25-8-B001-0358-四方T帽-106S-过模图"
    assert "required_operation_recall" in {metric["metric_name"] for metric in report["metrics"]}
    assert "wrong_operation_sequence" in report["failure_tags"]


def test_cli_uses_teacher_rationale_file_when_provided(tmp_path: Path) -> None:
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
    out = tmp_path / "calibration_report.json"

    result = subprocess.run(
        [
            "python",
            "-m",
            "scripts.build_calibration_report",
            "--case-id",
            "DJGS-25-8-B001-0358-四方T帽-106S-过模图",
            "--predicted",
            str(predicted),
            "--teacher-rationale",
            str(rationale),
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
        for metric in report["metrics"]
        if metric["metric_name"] == "required_operation_recall"
    )
    assert recall["notes"] == "missing: backward_extrusion"
