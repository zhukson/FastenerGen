"""CLI behavior for exporting teacher rationales in bulk."""

import json
import subprocess
from pathlib import Path


def test_cli_exports_factory_teacher_rationales_in_bulk(tmp_path: Path) -> None:
    out_dir = tmp_path / "teacher_rationales"

    result = subprocess.run(
        [
            "python",
            "-m",
            "scripts.export_teacher_rationales",
            "--source",
            "factory",
            "--out-dir",
            str(out_dir),
        ],
        check=False,
        cwd=Path(__file__).resolve().parents[2],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    files = sorted(path for path in out_dir.glob("*.json") if path.name != "manifest.json")
    assert len(files) == 8

    manifest = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["source"] == "factory"
    assert manifest["case_count"] == 8
    assert all(item["teacher_rationale"] for item in manifest["cases"])

    square = out_dir / "DJGS-25-8-B001-0358-四方T帽-106S-过模图.json"
    assert square.exists()
    data = json.loads(square.read_text(encoding="utf-8"))
    assert data["case_id"] == "DJGS-25-8-B001-0358-四方T帽-106S-过模图"
    assert data["feature_observations"]
