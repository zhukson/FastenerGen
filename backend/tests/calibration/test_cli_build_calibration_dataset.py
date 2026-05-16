"""CLI behavior for building a calibration dataset manifest."""

import json
import subprocess
from pathlib import Path


def test_cli_builds_factory_calibration_dataset_manifest(tmp_path: Path) -> None:
    out = tmp_path / "factory_calibration_dataset.json"

    result = subprocess.run(
        [
            "python",
            "-m",
            "scripts.build_calibration_dataset",
            "--source",
            "factory",
            "--teacher-rationale-dir",
            "app/knowledge/teacher_rationales/factory",
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
    assert data["source"] == "factory"
    assert data["case_count"] == 8

    square = next(
        item
        for item in data["cases"]
        if item["case_id"] == "DJGS-25-8-B001-0358-四方T帽-106S-过模图"
    )
    assert square["source_type"] == "factory_gt"
    assert square["trust_level"] == "gold"
    assert square["holdout_case_ids"] == ["DJGS-25-8-B001-0358-四方T帽-106S-过模图"]
    assert square["teacher_rationale"].endswith(
        "DJGS-25-8-B001-0358-四方T帽-106S-过模图.json"
    )
    assert "square_head" in square["tags"]
    assert "run_gong_experiment" in square["suggested_command"]
