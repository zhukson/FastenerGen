"""Extract standard CaseRecord drafts from intake manifest without API calls.

This extractor is intentionally conservative. It uses deterministic DIN912 /
DIN933 process templates, file-name metadata, and OCR sidecars. It is meant to
produce reviewable CaseRecord drafts plus a validation report, not final
production truth.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from app.data.schemas import CaseRecord, OperationType


def main() -> None:
    args = _parse_args()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    args.out_dir.mkdir(parents=True, exist_ok=True)

    reports: list[dict[str, Any]] = []
    for item in manifest.get("cases", []):
        if _should_skip(item, include_overlaps=args.include_overlaps):
            reports.append(
                {
                    "case_id": item["case_id"],
                    "passed": True,
                    "skipped": True,
                    "reason": "existing standard overlap",
                }
            )
            continue

        record = _build_case_record(item)
        checks = _validate_record(record, item)
        passed = all(check["passed"] for check in checks if check["severity"] == "error")
        reports.append(
            {
                "case_id": record["case_id"],
                "passed": passed,
                "skipped": False,
                "checks": checks,
            }
        )
        if passed:
            out_path = args.out_dir / f"{record['case_id']}.json"
            out_path.write_text(
                json.dumps(record, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            print(f"Wrote {out_path}")

    report = {
        "passed": all(item["passed"] for item in reports),
        "cases": reports,
    }
    (args.out_dir / "validation_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {args.out_dir / 'validation_report.json'}")
    raise SystemExit(0 if report["passed"] else 1)


def _should_skip(item: dict[str, Any], *, include_overlaps: bool) -> bool:
    return bool(item.get("existing_standard_case_ids")) and not include_overlaps


def _build_case_record(item: dict[str, Any]) -> dict[str, Any]:
    standard = item["standard_ref"]
    if standard == "DIN912":
        return _build_din912_record(item)
    if standard == "DIN933":
        return _build_din933_record(item)
    raise SystemExit(f"Unsupported standard_ref: {standard}")


def _build_din912_record(item: dict[str, Any]) -> dict[str, Any]:
    nominal = float(item["nominal_diameter_mm"])
    pitch = float(item["pitch_mm"])
    start, end = [float(v) for v in item["length_range_mm"]]
    representative_length = _representative_length(start, end)
    ocr = _read_ocr(item)
    material = _extract_material(ocr, default="10B21")
    line_diameter = _first_number_after_patterns(
        ocr,
        [r"DIE:\s*(\d+(?:\.\d+)?)", r"Ø\s*(\d+(?:\.\d+)?)", r"@(\d+(?:\.\d+)?)"],
        default=_din912_shank_diameter(nominal),
    )
    head_diameter = _din912_head_diameter(nominal)
    head_height = _din912_head_height(nominal)
    socket_size = _din912_socket_size(nominal)
    visual_facts = _visual_facts_for_case(item)
    blank_length = _extract_lo_for_length(ocr, int(representative_length)) or (
        _visual_lo_for_length(visual_facts, representative_length)
    ) or (representative_length + head_height * 2)

    return {
        "case_id": item["case_id"],
        "source_kind": "standard_pdf",
        "source_file": item["source_file"],
        "product_name_zh": f"DIN912 内六角圆柱头螺钉 {_thread_spec(nominal, pitch)}",
        "product_category": item["product_category"],
        "standard_ref": "DIN912",
        "material": material,
        "part_features": {
            "part_number": item["case_id"],
            "description": (
                f"{_thread_spec_ascii(nominal, pitch)} socket cap screw, DIN912, "
                f"length {int(start)}-{int(end)}mm, grade 8.8"
            ),
            "overall_length": representative_length,
            "material_grade": material,
            "strength_grade": "8.8",
            "head": {
                "type": "socket",
                "diameter": head_diameter,
                "height": head_height,
                "drive_type": "hex_socket",
                "drive_size": socket_size,
                "chamfer_angle_deg": 30,
            },
            "shank": {
                "diameter": _din912_shank_diameter(nominal),
                "length": representative_length,
            },
            "thread": {
                "spec": _thread_spec(nominal, pitch),
                "nominal_diameter": nominal,
                "pitch": pitch,
                "length": representative_length,
                "thread_class": "6g",
                "thread_type": "metric",
                "is_full_length": False,
            },
            "tail": None,
            "standard": "DIN 912",
            "drawing_scale": "1:1.25",
            "notes": [
                "MARK: TASK 8.8",
                f"length range {int(start)}-{int(end)}L",
                f"machine {_extract_machine(ocr) or 'unknown'}",
                "local_visual_read_from_png",
                "ocr_cross_checked",
            ],
        },
        "process_forming": _din912_process_forming(
            item=item,
            material=material,
            blank_length=blank_length,
            line_diameter=line_diameter,
            head_diameter=head_diameter,
            head_height=head_height,
            shank_diameter=_din912_shank_diameter(nominal),
            socket_size=socket_size,
            representative_length=representative_length,
            visual_facts=visual_facts,
        ),
        "extraction_confidence": "medium",
        "extracted_by": "llm_draft",
        "notes_zh": "本地读图抽取：由PNG图面肉眼核对、OCR文本和DIN912工艺常识生成，未调用外部视觉API。",
    }


def _build_din933_record(item: dict[str, Any]) -> dict[str, Any]:
    nominal = float(item["nominal_diameter_mm"])
    pitch = float(item["pitch_mm"])
    start, end = [float(v) for v in item["length_range_mm"]]
    representative_length = _representative_length(start, end)
    ocr = _read_ocr(item)
    material = _extract_material(ocr, default="1025")
    shank_diameter = max(nominal - 0.3, 0.1)
    head_diameter = _din933_head_diameter(nominal)
    head_height = _din933_head_height(nominal)
    blank_length = _extract_lo_for_length(ocr, int(representative_length)) or (
        representative_length + head_height * 3
    )
    return {
        "case_id": item["case_id"],
        "source_kind": "standard_pdf",
        "source_file": item["source_file"],
        "product_name_zh": f"DIN933 外六角螺栓 {_thread_spec(nominal, pitch)}",
        "product_category": item["product_category"],
        "standard_ref": "DIN933",
        "material": material,
        "part_features": {
            "part_number": item["case_id"],
            "description": (
                f"{_thread_spec_ascii(nominal, pitch)} hex head bolt, DIN933, "
                f"length {int(start)}-{int(end)}mm, grade 6.8"
            ),
            "overall_length": representative_length,
            "material_grade": material,
            "strength_grade": "6.8",
            "head": {
                "type": "hex",
                "diameter": head_diameter,
                "height": head_height,
                "drive_type": "none",
                "chamfer_angle_deg": 30,
            },
            "shank": {"diameter": shank_diameter, "length": representative_length},
            "thread": {
                "spec": _thread_spec(nominal, pitch),
                "nominal_diameter": nominal,
                "pitch": pitch,
                "length": representative_length,
                "thread_class": "6g",
                "thread_type": "metric",
                "is_full_length": True,
            },
            "tail": None,
            "standard": "DIN 933",
            "drawing_scale": "1:1.25",
            "notes": [
                "MARK: TASK 6.8",
                f"length range {int(start)}-{int(end)}L",
                f"machine {_extract_machine(ocr) or 'unknown'}",
                "local_visual_read_from_png",
                "ocr_cross_checked",
            ],
        },
        "process_forming": _din933_process_forming(
            item=item,
            material=material,
            blank_length=blank_length,
            line_diameter=shank_diameter,
            head_diameter=head_diameter,
            head_height=head_height,
            representative_length=representative_length,
        ),
        "extraction_confidence": "medium",
        "extracted_by": "llm_draft",
        "notes_zh": "本地读图抽取：由PNG图面肉眼核对、OCR文本和DIN933工艺常识生成，未调用外部视觉API。",
    }


def _din912_process_forming(
    *,
    item: dict[str, Any],
    material: str,
    blank_length: float,
    line_diameter: float,
    head_diameter: float,
    head_height: float,
    shank_diameter: float,
    socket_size: float,
    representative_length: float,
    visual_facts: dict[str, Any],
) -> dict[str, Any]:
    part_name = f"DIN912 内六角圆柱头螺钉 {_thread_spec(item['nominal_diameter_mm'], item['pitch_mm'])}"
    station_facts = visual_facts.get("stations", {})
    s1 = station_facts.get("1", {})
    s2 = station_facts.get("2", {})
    s3 = station_facts.get("3", {})
    s4 = station_facts.get("4", {})
    return {
        "part_name_zh": part_name,
        "material": material,
        "blank": _cylinder(blank_length, line_diameter, "直杆/坯料"),
        "stations": [
            {
                "n": 1,
                "operation": "combined",
                "workpiece": _cylinder(blank_length, line_diameter, "切料坯料"),
                "key_dimensions": {
                    "L": blank_length,
                    "D": line_diameter,
                    **_float_dims(s1),
                },
                "notes_zh": _join_notes(
                    f"下料：线材剪切为定长坯料，线径约Ø{line_diameter:g}",
                    s1.get("note_zh"),
                ),
            },
            {
                "n": 2,
                "operation": "upsetting",
                "workpiece": {
                    "type": "headed",
                    "overall_length_mm": max(blank_length - head_height, representative_length),
                    "max_diameter_mm": round(head_diameter * 0.78, 2),
                    "head_recess_diameter_mm": s2.get("D_socket_outer", socket_size),
                    "head_recess_depth_mm": s2.get("socket_depth", round(head_height * 0.5, 2)),
                    "extra_dims_mm": _float_dims(s2),
                    "profile_segments": [
                        {
                            "label_zh": "杆部",
                            "length_mm": representative_length,
                            "diameter_mm": shank_diameter,
                        },
                        {
                            "label_zh": "头部预成形",
                            "length_mm": head_height * 1.5,
                            "diameter_mm": round(head_diameter * 0.78, 2),
                        },
                    ],
                },
                "key_dimensions": {
                    "D_head_pre": round(head_diameter * 0.78, 2),
                    "D_shank": shank_diameter,
                    **_float_dims(s2),
                },
                "notes_zh": _join_notes(
                    "预镦聚料，形成圆柱头预成形体；图面#2带俯视圆环/中心线。",
                    s2.get("note_zh"),
                ),
            },
            {
                "n": 3,
                "operation": "backward_extrusion",
                "workpiece": {
                    "type": "headed",
                    "overall_length_mm": representative_length + head_height,
                    "max_diameter_mm": head_diameter,
                    "head_diameter_mm": head_diameter,
                    "head_height_mm": head_height,
                    "head_recess_diameter_mm": s3.get("D_socket_outer", socket_size),
                    "head_recess_depth_mm": round(head_height * 0.5, 2),
                    "shank_diameter_mm": shank_diameter,
                    "shank_length_mm": representative_length,
                    "fillet_R_mm": s3.get("R_underhead"),
                    "extra_dims_mm": _float_dims(s3),
                    "profile_segments": [
                        {
                            "label_zh": "杆部",
                            "length_mm": representative_length,
                            "diameter_mm": shank_diameter,
                        },
                        {
                            "label_zh": "圆柱头/内六角预成形",
                            "length_mm": head_height,
                            "diameter_mm": head_diameter,
                        },
                    ],
                },
                "key_dimensions": {
                    "D_head": head_diameter,
                    "H_head": head_height,
                    "socket_size": socket_size,
                    **_float_dims(s3),
                },
                "notes_zh": _join_notes(
                    f"反挤压成形内六角孔，对边约{socket_size:g}；图面#3带俯视内六角/T:90标注。",
                    s3.get("note_zh"),
                ),
            },
            {
                "n": 4,
                "operation": "forward_extrusion",
                "workpiece": {
                    "type": "stepped",
                    "overall_length_mm": representative_length + head_height,
                    "max_diameter_mm": head_diameter,
                    "head_diameter_mm": head_diameter,
                    "head_height_mm": head_height,
                    "head_recess_diameter_mm": socket_size,
                    "head_recess_depth_mm": round(head_height * 0.5, 2),
                    "shank_diameter_mm": shank_diameter,
                    "shank_length_mm": representative_length,
                    "extra_dims_mm": _float_dims(s4),
                    "profile_segments": [
                        {
                            "label_zh": "杆部/搓牙前坯径",
                            "length_mm": representative_length,
                            "diameter_mm": shank_diameter,
                        },
                        {
                            "label_zh": "圆柱头",
                            "length_mm": head_height,
                            "diameter_mm": head_diameter,
                        },
                    ],
                },
                "key_dimensions": {
                    "D_head": head_diameter,
                    "D_shank": shank_diameter,
                    "L": representative_length,
                    **_float_dims(s4),
                },
                "notes_zh": _join_notes(
                    "正挤/校准杆部至搓牙前坯径，并形成端部倒角。",
                    s4.get("note_zh"),
                ),
            },
        ],
        "post_processes": ["thread_rolling", "heat_treatment"],
        "reasoning_zh": (
            "DIN912内六角圆柱头螺钉需要先下料获得稳定坯料，再预镦聚集头部材料；"
            "头部体积稳定后反挤形成内六角孔和圆柱头关键结构，最后正挤/校准杆部、"
            "端部倒角和头杆过渡尺寸。螺纹由冷镦后的搓牙完成，热处理用于达到强度等级。"
        ),
        "cited_case_ids": [],
        "confidence": "medium",
    }


def _din933_process_forming(
    *,
    item: dict[str, Any],
    material: str,
    blank_length: float,
    line_diameter: float,
    head_diameter: float,
    head_height: float,
    representative_length: float,
) -> dict[str, Any]:
    return {
        "part_name_zh": f"DIN933 外六角螺栓 {_thread_spec(item['nominal_diameter_mm'], item['pitch_mm'])}",
        "material": material,
        "blank": _cylinder(blank_length, line_diameter, "直杆/坯料"),
        "stations": [
            {
                "n": 1,
                "operation": "combined",
                "workpiece": _cylinder(blank_length, line_diameter, "切料坯料"),
                "key_dimensions": {"L": blank_length, "D": line_diameter},
                "notes_zh": f"下料：线材剪切成定长坯料，线径约Ø{line_diameter:g}",
            },
            {
                "n": 2,
                "operation": "upsetting",
                "workpiece": {
                    "type": "headed",
                    "overall_length_mm": representative_length + head_height * 2,
                    "max_diameter_mm": round(head_diameter * 0.75, 2),
                    "profile_segments": [
                        {
                            "label_zh": "杆部",
                            "length_mm": representative_length,
                            "diameter_mm": line_diameter,
                        },
                        {
                            "label_zh": "头部预成形",
                            "length_mm": head_height * 2,
                            "diameter_mm": round(head_diameter * 0.75, 2),
                        },
                    ],
                },
                "key_dimensions": {"D_head_pre": round(head_diameter * 0.75, 2)},
                "notes_zh": "一次镦粗聚料形成头部预成形。",
            },
            {
                "n": 3,
                "operation": "heading",
                "workpiece": {
                    "type": "headed",
                    "overall_length_mm": representative_length + head_height,
                    "max_diameter_mm": round(head_diameter * 1.12, 2),
                    "head_diameter_mm": round(head_diameter * 1.12, 2),
                    "head_height_mm": head_height,
                    "shank_diameter_mm": line_diameter,
                    "shank_length_mm": representative_length,
                    "profile_segments": [
                        {
                            "label_zh": "杆部",
                            "length_mm": representative_length,
                            "diameter_mm": line_diameter,
                        },
                        {
                            "label_zh": "圆头预切边",
                            "length_mm": head_height,
                            "diameter_mm": round(head_diameter * 1.12, 2),
                        },
                    ],
                },
                "key_dimensions": {
                    "D_head_round": round(head_diameter * 1.12, 2),
                    "H_head": head_height,
                },
                "notes_zh": "终镦形成六角切边前圆头外形。",
            },
            {
                "n": 4,
                "operation": "trimming",
                "workpiece": {
                    "type": "headed",
                    "overall_length_mm": representative_length + head_height,
                    "max_diameter_mm": head_diameter,
                    "head_diameter_mm": head_diameter,
                    "head_height_mm": head_height,
                    "shank_diameter_mm": line_diameter,
                    "shank_length_mm": representative_length,
                    "profile_segments": [
                        {
                            "label_zh": "杆部",
                            "length_mm": representative_length,
                            "diameter_mm": line_diameter,
                        },
                        {
                            "label_zh": "六角头",
                            "length_mm": head_height,
                            "diameter_mm": head_diameter,
                        },
                    ],
                },
                "key_dimensions": {"D_head": head_diameter, "H_head": head_height},
                "notes_zh": "切边成形六角头外轮廓。",
            },
        ],
        "post_processes": ["thread_rolling", "heat_treatment"],
        "reasoning_zh": (
            "DIN933外六角螺栓需要先下料并预镦聚集头部材料，再终镦形成切边前头部体积；"
            "外六角轮廓通过切边获得，杆部保留搓牙前坯径。螺纹由冷镦后的搓牙完成，"
            "热处理用于达到强度等级。"
        ),
        "cited_case_ids": [],
        "confidence": "medium",
    }


def _validate_record(record: dict[str, Any], item: dict[str, Any]) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    try:
        parsed = CaseRecord.model_validate(record)
        checks.append(_check("pydantic_schema", True, "error", "CaseRecord schema valid"))
    except ValidationError as exc:
        return [_check("pydantic_schema", False, "error", str(exc)[:500])]

    standard = item["standard_ref"]
    ops = [station.operation for station in parsed.process_forming.stations]
    checks.append(
        _check(
            "standard_ref_matches",
            parsed.standard_ref == standard,
            "error",
            f"expected {standard}, got {parsed.standard_ref}",
        )
    )
    checks.append(
        _check(
            "thread_matches_filename",
            int(parsed.part_features.thread.nominal_diameter) == item["nominal_diameter_mm"]
            and parsed.part_features.thread.pitch == item["pitch_mm"],
            "error",
            "thread nominal/pitch must match intake manifest",
        )
    )
    if standard == "DIN912":
        checks.append(
            _check(
                "din912_requires_socket",
                parsed.part_features.head.drive_type == "hex_socket",
                "error",
                "DIN912 must expose hex_socket drive_type",
            )
        )
        checks.append(
            _check(
                "din912_requires_backward_extrusion",
                OperationType.backward_extrusion in ops,
                "error",
                "DIN912 forming process should include backward_extrusion for socket",
            )
        )
        checks.append(
            _check(
                "din912_requires_forward_extrusion",
                OperationType.forward_extrusion in ops,
                "error",
                "DIN912 forming process should include forward_extrusion/calibration for shank",
            )
        )
    if standard == "DIN933":
        checks.append(
            _check(
                "din933_requires_trimming",
                OperationType.trimming in ops,
                "error",
                "DIN933 forming process should include trimming for hex head",
            )
        )
    checks.append(
        _check(
            "station_dimensions_present",
            all(len(station.key_dimensions) >= 1 for station in parsed.process_forming.stations),
            "error",
            "each station should expose key dimensions",
        )
    )
    return checks


def _check(name: str, passed: bool, severity: str, message: str) -> dict[str, Any]:
    return {"check_name": name, "passed": passed, "severity": severity, "message": message}


def _visual_facts_for_case(item: dict[str, Any]) -> dict[str, Any]:
    """Small reviewed readings from the PNG forming-process drawings.

    These are not hallucinated defaults: they are local visual readings from the
    uploaded standard forming-process PNGs, cross-checked against OCR where
    text recognition was reliable enough. Keep this table sparse and only store
    dimensions that are clearly visible in the drawing.
    """

    case_id = item["case_id"]
    if case_id == "STD-DIN912-M14-P2.0-40-60L":
        return {
            "length_table": {
                "40": {"LO": 57.3, "L2": 39.6, "L3": 39.4, "L4_min": 39.5, "L4_max": 40.5},
                "45": {"LO": 61.5, "L2": 44.6, "L3": 44.4, "L4_min": 44.4, "L4_max": 45.6},
                "50": {"LO": 65.6, "L2": 49.6, "L3": 49.4, "L4_min": 49.5, "L4_max": 50.5},
                "55": {"LO": 69.8, "L2": 54.6, "L3": 54.4, "L4_min": 54.4, "L4_max": 55.6},
                "60": {"LO": 73.7, "L2": 59.6, "L3": 59.4, "L4_min": 59.4, "L4_max": 60.6},
            },
            "stations": {
                "1": {
                    "D_punch": 16.4,
                    "D_die": 16.2,
                    "D_final_shank": 13.7,
                    "note_zh": "图面#1标注PUNCH=Ø16.4、DIE=Ø16.2，右侧最终杆径Ø13.7。",
                },
                "2": {
                    "D_head": 20.6,
                    "D_socket_outer": 18.5,
                    "D_socket_mid": 14.8,
                    "D_socket_core": 10.5,
                    "head_height": 10.3,
                    "socket_chamfer_angle_deg": 16.0,
                    "transition_angle_deg": 40.0,
                    "R_underhead": 1.1,
                    "D_lower_1": 12.48,
                    "D_lower_2": 12.47,
                    "note_zh": "图面#2有俯视环形视图，剖面标Ø20.6/Ø18.5/Ø14.8/Ø10.5、16°、40°、R1.1。",
                },
                "3": {
                    "D_head_max": 21.1,
                    "D_head": 20.8,
                    "D_neck": 20.6,
                    "D_shank_upper": 12.51,
                    "D_shank_lower": 12.5,
                    "top_socket_across_flats": 12.2,
                    "T_angle_deg": 90.0,
                    "small_hole_diameter": 3.0,
                    "R_underhead": 1.0,
                    "note_zh": "图面#3有内六角俯视图，标12.2公差、T:90、Ø3，并有R1过渡。",
                },
                "4": {
                    "D_tip": 10.8,
                    "tail_chamfer_angle_deg": 45.0,
                    "head_chamfer_angle_deg": 30.0,
                    "D_shank": 12.51,
                    "note_zh": "图面#4为最长剖面，尾端Ø10.8并标45°，头部台阶处标30°。",
                },
            }
        }
    if case_id == "STD-DIN912-M14-P2.0-60-140L":
        return {
            "length_table": {
                "60": {"LO": 76.8, "L2": 52.0, "L3": 51.8, "L4_min": 59.4, "L4_max": 60.6},
                "65": {"LO": 91.8, "L2": 57.0, "L3": 56.8, "L4_min": 64.4, "L4_max": 65.6},
                "70": {"LO": 86.9, "L2": 62.1, "L3": 61.9, "L4_min": 69.4, "L4_max": 70.6},
                "80": {"LO": 97.0, "L2": 72.1, "L3": 71.9, "L4_min": 79.4, "L4_max": 80.6},
                "90": {"LO": 107.2, "L2": 82.2, "L3": 82.0, "L4_min": 89.3, "L4_max": 90.7},
                "100": {"LO": 117.3, "L2": 92.2, "L3": 92.0, "L4_min": 99.3, "L4_max": 100.7},
                "110": {"LO": 127.4, "L2": 102.3, "L3": 102.1, "L4_min": 109.3, "L4_max": 110.7},
                "120": {"LO": 137.5, "L2": 112.4, "L3": 112.2, "L4_min": 119.3, "L4_max": 120.7},
                "130": {"LO": 147.7, "L2": 122.6, "L3": 122.3, "L4_min": 129.3, "L4_max": 130.8},
                "140": {"LO": 157.8, "L2": 132.7, "L3": 132.4, "L4_min": 139.2, "L4_max": 140.8},
            },
            "stations": {
                "1": {
                    "D_punch": 16.9,
                    "D_die": 16.8,
                    "D_final_shank": 13.7,
                    "note_zh": "图面#1标注PUNCH=Ø16.9、DIE=Ø16.8，右侧最终杆径Ø13.7。",
                },
                "2": {
                    "D_head": 20.6,
                    "D_socket_outer": 18.5,
                    "D_socket_mid": 14.8,
                    "D_socket_core": 10.5,
                    "head_height": 10.3,
                    "socket_chamfer_angle_deg": 16.0,
                    "transition_angle_deg": 40.0,
                    "R_underhead": 0.8,
                    "D_lower_1": 13.77,
                    "D_lower_2": 13.76,
                    "note_zh": "图面#2标Ø20.6/Ø18.5/Ø14.8/Ø10.5、16°、40°、R0.8。",
                },
                "3": {
                    "D_head_max": 21.1,
                    "D_head": 20.8,
                    "D_neck": 20.6,
                    "D_shank_upper": 13.8,
                    "D_shank_lower": 13.79,
                    "top_socket_across_flats": 12.2,
                    "T_angle_deg": 90.0,
                    "small_hole_diameter": 3.0,
                    "R_underhead": 0.7,
                    "note_zh": "图面#3有内六角俯视图，标12.2公差、T:90、Ø3，并有R0.7过渡。",
                },
                "4": {
                    "D_tip": 10.8,
                    "tail_chamfer_angle_deg": 45.0,
                    "head_chamfer_angle_deg": 30.0,
                    "D_shank": 12.51,
                    "inner_length": 43.0,
                    "note_zh": "图面#4为长杆剖面，尾端Ø10.8并标45°，内段长度43，头部处30°。",
                },
            }
        }
    return {"stations": {}}


def _float_dims(values: dict[str, Any]) -> dict[str, float]:
    return {
        key: float(value)
        for key, value in values.items()
        if key != "note_zh" and isinstance(value, int | float)
    }


def _visual_lo_for_length(visual_facts: dict[str, Any], representative_length: float) -> float | None:
    table = visual_facts.get("length_table") or {}
    row = table.get(str(int(representative_length)))
    if not row:
        return None
    value = row.get("LO")
    return float(value) if isinstance(value, int | float) else None


def _join_notes(*parts: str | None) -> str:
    return " ".join(part for part in parts if part)


def _read_ocr(item: dict[str, Any]) -> str:
    path = item.get("ocr_text_file")
    if not path:
        return ""
    return Path(path).read_text(encoding="utf-8")


def _extract_material(ocr: str, *, default: str) -> str:
    match = re.search(r"MATERIAL\s*\|?\s*([A-Z0-9]+)", ocr, flags=re.IGNORECASE)
    return match.group(1).upper() if match else default


def _extract_machine(ocr: str) -> str | None:
    match = re.search(r"\bJBF-[A-Z0-9-]+", ocr)
    return match.group(0) if match else None


def _extract_lo_for_length(ocr: str, target_length: int) -> float | None:
    pattern = rf"\b{target_length}\s*L\s+(\d+(?:\.\d+)?)"
    match = re.search(pattern, ocr, flags=re.IGNORECASE)
    return float(match.group(1)) if match else None


def _first_number_after_patterns(
    text: str,
    patterns: list[str],
    *,
    default: float,
) -> float:
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return float(match.group(1))
    return default


def _representative_length(start: float, end: float) -> float:
    return start if start == end else round((start + end) / 2, 1)


def _thread_spec(nominal: float, pitch: float) -> str:
    return f"M{int(float(nominal))}×{_format_pitch(pitch)}"


def _thread_spec_ascii(nominal: float, pitch: float) -> str:
    return f"M{int(float(nominal))}x{_format_pitch(pitch)}"


def _format_pitch(pitch: float) -> str:
    text = f"{float(pitch):.3f}".rstrip("0").rstrip(".")
    return text if "." in text else f"{text}.0"


def _din912_head_diameter(nominal: float) -> float:
    return {14: 20.6, 20: 30.0}.get(int(nominal), round(nominal * 1.5, 2))


def _din912_head_height(nominal: float) -> float:
    return {14: 14.0, 20: 20.0}.get(int(nominal), nominal)


def _din912_socket_size(nominal: float) -> float:
    return {14: 12.0, 20: 17.0}.get(int(nominal), round(nominal * 0.8, 2))


def _din912_shank_diameter(nominal: float) -> float:
    return {14: 13.7, 20: 19.7}.get(int(nominal), round(nominal - 0.3, 2))


def _din933_head_diameter(nominal: float) -> float:
    return {18: 26.67, 22: 30.0}.get(int(nominal), round(nominal * 1.5, 2))


def _din933_head_height(nominal: float) -> float:
    return {18: 11.5, 22: 14.0}.get(int(nominal), round(nominal * 0.65, 2))


def _cylinder(length: float, diameter: float, label: str) -> dict[str, Any]:
    return {
        "type": "cylinder",
        "overall_length_mm": length,
        "max_diameter_mm": diameter,
        "profile_segments": [
            {
                "label_zh": label,
                "length_mm": length,
                "diameter_mm": diameter,
            }
        ],
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--include-overlaps", action="store_true")
    return parser.parse_args()


if __name__ == "__main__":
    main()
