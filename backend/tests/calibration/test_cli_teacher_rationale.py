"""CLI behavior for exporting deterministic teacher rationales."""

import json
import subprocess
from pathlib import Path


def test_cli_exports_teacher_rationale_for_case(tmp_path: Path) -> None:
    out = tmp_path / "teacher_rationale.json"

    result = subprocess.run(
        [
            "python",
            "-m",
            "scripts.export_teacher_rationale",
            "--case-id",
            "DJGS-25-8-B001-0358-四方T帽-106S-过模图",
            "--out",
            str(out),
        ],
        check=False,
        cwd=Path(__file__).resolve().parents[2],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["case_id"] == "DJGS-25-8-B001-0358-四方T帽-106S-过模图"
    assert [item["operation"] for item in data["required_operations"]] == [
        "upsetting",
        "forward_extrusion",
        "heading",
        "combined",
        "trimming",
        "piercing",
    ]
    assert {
        (item["before"], item["after"]) for item in data["precedence_constraints"]
    } >= {
        ("upsetting", "forward_extrusion"),
        ("trimming", "piercing"),
    }
