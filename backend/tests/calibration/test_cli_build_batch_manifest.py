"""CLI behavior for building a batch manifest from completed runs."""

import json
import subprocess
from pathlib import Path


def test_cli_builds_batch_manifest_from_dataset_and_prediction_map(tmp_path: Path) -> None:
    dataset = tmp_path / "dataset.json"
    prediction = Path(
        "experiments/square_t_cap_holdout/runs/"
        "official_opus47_thinking_compact_20260511/process_parameters.json"
    )
    dataset.write_text(
        json.dumps(
            {
                "source": "factory",
                "case_count": 1,
                "cases": [
                    {
                        "case_id": "DJGS-25-8-B001-0358-四方T帽-106S-过模图",
                        "teacher_rationale": "teacher.json",
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    prediction_map = tmp_path / "prediction_map.json"
    prediction_map.write_text(
        json.dumps(
            {
                "DJGS-25-8-B001-0358-四方T帽-106S-过模图": str(prediction),
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    out = tmp_path / "batch_manifest.json"

    result = subprocess.run(
        [
            "python",
            "-m",
            "scripts.build_batch_manifest",
            "--dataset",
            str(dataset),
            "--prediction-map",
            str(prediction_map),
            "--eval-id",
            "factory-completed",
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
    assert data["eval_id"] == "factory-completed"
    assert data["cases"] == [
        {
            "case_id": "DJGS-25-8-B001-0358-四方T帽-106S-过模图",
            "predicted": str(prediction),
            "teacher_rationale": "teacher.json",
        }
    ]
