"""CLI behavior for summarizing a batch calibration JSON as Markdown."""

import json
import subprocess
from pathlib import Path


def test_cli_summarizes_batch_calibration_report(tmp_path: Path) -> None:
    report = tmp_path / "batch_calibration_report.json"
    report.write_text(
        json.dumps(
            {
                "eval_id": "factory-smoke",
                "case_count": 1,
                "metric_means": [
                    {
                        "metric_name": "required_operation_recall_mean",
                        "value": 0.8333333333,
                    },
                    {
                        "metric_name": "precedence_constraint_recall_mean",
                        "value": 0.2,
                    },
                ],
                "failure_tag_counts": {"wrong_precedence": 1},
                "case_reports": [
                    {
                        "case_id": "CASE-A",
                        "failure_tags": ["wrong_precedence"],
                        "metrics": [
                            {
                                "metric_name": "required_operation_recall",
                                "value": 0.8333333333,
                                "notes": "missing: forward_extrusion",
                            }
                        ],
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    out = tmp_path / "summary.md"

    result = subprocess.run(
        [
            "python",
            "-m",
            "scripts.summarize_batch_calibration",
            "--report",
            str(report),
            "--out",
            str(out),
        ],
        check=False,
        cwd=Path(__file__).resolve().parents[2],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    text = out.read_text(encoding="utf-8")
    assert "# Calibration Summary: factory-smoke" in text
    assert "| `required_operation_recall_mean` | 0.833 |" in text
    assert "| `wrong_precedence` | 1 |" in text
    assert "missing: forward_extrusion" in text
