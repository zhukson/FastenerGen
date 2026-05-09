"""Batch-extract Gong Maoliang chapter 8 textbook cases.

Run this from a shell that has ANTHROPIC_API_KEY set:

    cd /Users/bobchen/FastenerGen/backend
    export ANTHROPIC_TEXTBOOK_CASE_MODEL=claude-sonnet-4-6
    uv run python -m scripts.batch_extract_gong_chapter8 --limit 3
    uv run python -m scripts.batch_extract_gong_chapter8

Each output is a low-trust textbook_case JSON. It does not replace real DWG
cases; it only expands the analogy library for special-shape fasteners.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from dataclasses import dataclass


@dataclass(frozen=True)
class GongCase:
    source_id: str
    page: int
    out_name: str


GONG_CH8_CASES: list[GongCase] = [
    GongCase("gong_maoliang_Page355_358", 355, "gong_8_15_long_pin_large_mid_flange_semi_hollow"),
    GongCase("gong_maoliang_Page355_358", 356, "gong_8_16_double_head_hex_blind_hole_pin_ring"),
    GongCase("gong_maoliang_Page355_358", 357, "gong_8_17_triangular_inclined_support_pin"),
    GongCase("gong_maoliang_Page355_358", 358, "gong_8_18_riveting_bolt"),
    GongCase("gong_maoliang_Page359_362", 359, "gong_8_19_japanese_short_socket_cap_screw_m12"),
    # p360 is key tooling for p359; skip by default because Phase 1 does not output tooling.
    GongCase("gong_maoliang_Page359_362", 361, "gong_8_20_bicycle_brake_through_core_hex_screw"),
    GongCase("gong_maoliang_Page359_362", 362, "gong_8_21_automotive_wheel_nut"),
    GongCase("gong_maoliang_Page363_366", 363, "gong_8_22_furniture_inner_hex_self_tapping_screw"),
    GongCase("gong_maoliang_Page363_366", 364, "gong_8_23_sofa_frame_rivet"),
    GongCase("gong_maoliang_Page363_366", 365, "gong_8_24_m8_rivet_nut"),
    GongCase("gong_maoliang_Page363_366", 366, "gong_8_25_stainless_blind_rivet"),
    GongCase("gong_maoliang_Page367_370", 367, "gong_8_26_stainless_kitchen_bath_nut"),
    GongCase("gong_maoliang_Page367_370", 368, "gong_8_27_stainless_flange_bolt_with_washer"),
    GongCase("gong_maoliang_Page367_370", 369, "gong_8_28_spark_plug_shell"),
    GongCase("gong_maoliang_Page367_370", 370, "gong_8_29_plug_screw"),
    GongCase(
        "gong_maoliang_Page371_374", 371, "gong_8_30_inner_hex_outer_square_flower_socket_tool"
    ),
    GongCase("gong_maoliang_Page371_374", 372, "gong_8_31_audi_wheel_bolt"),
    GongCase("gong_maoliang_Page371_374", 373, "gong_8_32_double_head_rivet"),
    GongCase("gong_maoliang_Page371_374", 374, "gong_8_33_shock_absorber_piston_rod"),
    GongCase("gong_maoliang_Page375_378", 375, "gong_8_34_t_bolt"),
    GongCase("gong_maoliang_Page375_378", 376, "gong_8_35_rivet_gun_hex_through_core_screw"),
    GongCase("gong_maoliang_Page375_378", 377, "gong_8_36_short_tooth_rivet"),
    GongCase("gong_maoliang_Page375_378", 378, "gong_8_37_automotive_lighting_middle_electrode"),
]


def _run_case(case: GongCase, *, model: str | None, overwrite: bool, dry_run: bool) -> int:
    cmd = [
        sys.executable,
        "-m",
        "scripts.extract_textbook_knowledge",
        "--source-id",
        case.source_id,
        "--pages",
        str(case.page),
        "--kind",
        "case",
        "--out-name",
        case.out_name,
    ]
    if model:
        cmd.extend(["--model", model])
    if overwrite:
        cmd.append("--overwrite")
    if dry_run:
        cmd.append("--dry-run")
    print("+", " ".join(cmd))
    if dry_run:
        return subprocess.run(cmd, check=False).returncode
    return subprocess.run(cmd, check=False).returncode


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, help="Only process the first N cases")
    parser.add_argument("--start", type=int, default=0, help="0-based start index")
    parser.add_argument(
        "--model",
        default="claude-sonnet-4-6",
        help="Model for visual textbook case extraction. Default: claude-sonnet-4-6",
    )
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    cases = GONG_CH8_CASES[args.start :]
    if args.limit is not None:
        cases = cases[: args.limit]

    failed = 0
    for case in cases:
        code = _run_case(case, model=args.model, overwrite=args.overwrite, dry_run=args.dry_run)
        if code != 0:
            failed += 1
            print(f"! failed: {case.out_name} exit={code}", file=sys.stderr)

    print(f"\nBatch complete: attempted={len(cases)} failed={failed}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
