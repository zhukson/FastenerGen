"""CLI behavior for standard forming-process PNG intake."""

import json
import subprocess
from pathlib import Path


def test_cli_builds_standard_case_intake_manifest(tmp_path: Path) -> None:
    source = tmp_path / "标准件"
    (source / "din912").mkdir(parents=True)
    (source / "din933").mkdir(parents=True)
    (source / "din912" / "DIN 912 M16P2.0x60-140L.png").write_bytes(b"fake")
    (source / "din933" / "DIN 933 M22 P2.5x40-150L.png").write_bytes(b"fake")
    out = tmp_path / "manifest.json"

    result = subprocess.run(
        [
            "python",
            "-m",
            "scripts.build_standard_case_intake",
            "--source-dir",
            str(source),
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
    assert data["case_count"] == 2
    assert data["source_dir"] == str(source)

    din912 = next(item for item in data["cases"] if item["standard_ref"] == "DIN912")
    assert din912["case_id"] == "STD-DIN912-M16-P2.0-60-140L"
    assert din912["product_category"] == "socket_cap_screw_DIN912"
    assert din912["nominal_diameter_mm"] == 16
    assert din912["pitch_mm"] == 2.0
    assert din912["length_range_mm"] == [60, 140]
    assert din912["status"] == "pending_extraction"

    din933 = next(item for item in data["cases"] if item["standard_ref"] == "DIN933")
    assert din933["case_id"] == "STD-DIN933-M22-P2.5-40-150L"
    assert din933["product_category"] == "hex_bolt_DIN933"


def test_cli_manifest_can_reference_ocr_sidecars_and_existing_records(tmp_path: Path) -> None:
    source = tmp_path / "标准件"
    (source / "din912").mkdir(parents=True)
    (source / "din912" / "DIN 912 M20P2.5x80-200L.png").write_bytes(b"fake")
    ocr_dir = tmp_path / "ocr"
    ocr_dir.mkdir()
    (ocr_dir / "STD-DIN912-M20-P2.5-80-200L.ocr.txt").write_text("OCR", encoding="utf-8")
    out = tmp_path / "manifest.json"

    result = subprocess.run(
        [
            "python",
            "-m",
            "scripts.build_standard_case_intake",
            "--source-dir",
            str(source),
            "--ocr-dir",
            str(ocr_dir),
            "--out",
            str(out),
        ],
        check=False,
        cwd=Path(__file__).resolve().parents[2],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    item = json.loads(out.read_text(encoding="utf-8"))["cases"][0]
    assert item["ocr_text_file"].endswith("STD-DIN912-M20-P2.5-80-200L.ocr.txt")
    assert item["existing_standard_case_ids"] == ["BG30060-P03-DIN912-M20-P2-5"]
    assert item["status"] == "needs_review_existing_overlap"


def test_cli_writes_standard_case_ocr_sidecars(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.json"
    image = tmp_path / "DIN 912 M14P2.0x60-140L.png"
    image.write_bytes(b"fake")
    manifest.write_text(
        json.dumps(
            {
                "case_count": 1,
                "cases": [
                    {
                        "case_id": "STD-DIN912-M14-P2.0-60-140L",
                        "source_file": str(image),
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    out_dir = tmp_path / "ocr"

    result = subprocess.run(
        [
            "python",
            "-m",
            "scripts.ocr_standard_case_intake",
            "--manifest",
            str(manifest),
            "--out-dir",
            str(out_dir),
            "--dry-run",
        ],
        check=False,
        cwd=Path(__file__).resolve().parents[2],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    sidecar = out_dir / "STD-DIN912-M14-P2.0-60-140L.ocr.txt"
    assert sidecar.exists()
    assert "DRY RUN OCR placeholder" in sidecar.read_text(encoding="utf-8")
