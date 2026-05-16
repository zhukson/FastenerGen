"""CLI behavior for offline standard CaseRecord extraction."""

import json
import subprocess
from pathlib import Path


def test_cli_extracts_m14_din912_case_record_offline(tmp_path: Path) -> None:
    ocr = tmp_path / "STD-DIN912-M14-P2.0-40-60L.ocr.txt"
    ocr.write_text(
        "DIN 912 M14P2.0x40-60 L MARK=TASK 8.8\n"
        "50 L 65.6 49.6 49.4 49.5-50.5\n"
        "PUNCH=@20.7 DIE=@20.6\n"
        "DIE: 12.55 MATERIAL | 10B21\n"
        "MACHINE NAME JBF-19B-4SL\n",
        encoding="utf-8",
    )
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "case_count": 1,
                "cases": [
                    {
                        "case_id": "STD-DIN912-M14-P2.0-40-60L",
                        "source_file": "/tmp/DIN 912 M14P2.0x40-60L.png",
                        "standard_ref": "DIN912",
                        "product_category": "socket_cap_screw_DIN912",
                        "nominal_diameter_mm": 14,
                        "pitch_mm": 2.0,
                        "length_range_mm": [40, 60],
                        "ocr_text_file": str(ocr),
                        "status": "pending_extraction",
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    out_dir = tmp_path / "extracted"

    result = subprocess.run(
        [
            "python",
            "-m",
            "scripts.extract_standard_cases_offline",
            "--manifest",
            str(manifest),
            "--out-dir",
            str(out_dir),
        ],
        check=False,
        cwd=Path(__file__).resolve().parents[2],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    record = json.loads(
        (out_dir / "STD-DIN912-M14-P2.0-40-60L.json").read_text(encoding="utf-8")
    )
    assert record["standard_ref"] == "DIN912"
    assert record["part_features"]["thread"]["spec"] == "M14×2.0"
    assert record["part_features"]["material_grade"] == "10B21"
    assert record["part_features"]["head"]["drive_type"] == "hex_socket"
    assert record["process_forming"]["blank"]["overall_length_mm"] == 65.6
    assert [s["operation"] for s in record["process_forming"]["stations"]] == [
        "combined",
        "upsetting",
        "backward_extrusion",
        "forward_extrusion",
    ]
    station_2 = record["process_forming"]["stations"][1]
    assert station_2["key_dimensions"]["D_socket_outer"] == 18.5
    assert station_2["key_dimensions"]["D_socket_mid"] == 14.8
    assert station_2["key_dimensions"]["D_socket_core"] == 10.5
    assert "local_visual_read_from_png" in record["part_features"]["notes"]

    report = json.loads((out_dir / "validation_report.json").read_text(encoding="utf-8"))
    assert report["passed"] is True
    assert report["cases"][0]["passed"] is True


def test_cli_uses_local_visual_lo_table_when_ocr_misses_length_row(
    tmp_path: Path,
) -> None:
    ocr = tmp_path / "STD-DIN912-M14-P2.0-40-60L.ocr.txt"
    ocr.write_text(
        "DIN 912 M14P2.0x40-60 L MARK=TASK 8.8\n"
        "PUNCH=@20.7 DIE=@20.6\n"
        "DIE: 12.55 MATERIAL | 10B21\n"
        "MACHINE NAME JBF-19B-4SL\n",
        encoding="utf-8",
    )
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "case_count": 1,
                "cases": [
                    {
                        "case_id": "STD-DIN912-M14-P2.0-40-60L",
                        "source_file": "/tmp/DIN 912 M14P2.0x40-60L.png",
                        "standard_ref": "DIN912",
                        "product_category": "socket_cap_screw_DIN912",
                        "nominal_diameter_mm": 14,
                        "pitch_mm": 2.0,
                        "length_range_mm": [40, 60],
                        "ocr_text_file": str(ocr),
                        "status": "pending_extraction",
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    out_dir = tmp_path / "extracted"

    result = subprocess.run(
        [
            "python",
            "-m",
            "scripts.extract_standard_cases_offline",
            "--manifest",
            str(manifest),
            "--out-dir",
            str(out_dir),
        ],
        check=False,
        cwd=Path(__file__).resolve().parents[2],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    record = json.loads(
        (out_dir / "STD-DIN912-M14-P2.0-40-60L.json").read_text(encoding="utf-8")
    )
    assert record["process_forming"]["blank"]["overall_length_mm"] == 65.6
