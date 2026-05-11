"""Run a CLI Gong reasoning experiment and write traceable reports.

Examples:
    uv run python -m scripts.run_gong_experiment \
      --part-features experiments/square_t_cap_holdout/input/part_features.json \
      --expected experiments/square_t_cap_holdout/ground_truth/process_parameters_ground_truth.json \
      --exclude-case DJGS-25-8-B001-0358-四方T帽-106S-过模图 \
      --prefer-category square_T_head \
      --out-dir experiments/square_t_cap_holdout/runs/manual
"""

from __future__ import annotations

import argparse
import asyncio
import json
import uuid
from pathlib import Path

from app.ai.process_designer import ProcessDesigner
from app.core.config import settings
from app.data.schemas import PartFeatures
from app.eval.experiment_report import (
    build_experiment_report,
    load_expected_process,
    write_experiment_report,
)


def main() -> None:
    args = _parse_args()
    asyncio.run(_run(args))


async def _run(args: argparse.Namespace) -> None:
    if not settings.anthropic_api_key:
        raise SystemExit("ANTHROPIC_API_KEY is not configured")

    output_dir = args.out_dir
    if output_dir is None:
        output_dir = Path("experiments") / args.experiment_id / "runs" / uuid.uuid4().hex[:12]
    output_dir.mkdir(parents=True, exist_ok=True)

    model = settings.primary_model if args.design_model == "opus" else settings.claude_model_die_design
    designer = ProcessDesigner(model=model)
    expected = load_expected_process(args.expected)

    if args.part_features:
        part_features = PartFeatures.model_validate(
            json.loads(args.part_features.read_text(encoding="utf-8"))
        )
        artifacts = await designer.design_from_part_features(
            part_features=part_features,
            output_dir=output_dir,
            prefer_category=args.prefer_category,
            exclude_case_ids=args.exclude_case,
            candidate_count=args.candidate_count,
            max_design_attempts=args.max_design_attempts,
        )
        input_path = args.part_features
    elif args.product_drawing:
        artifacts = await designer.design(
            product_drawing_path=args.product_drawing,
            output_dir=output_dir,
            prefer_category=args.prefer_category,
            self_consistency_runs=args.self_consistency_runs,
            exclude_case_ids=args.exclude_case,
            candidate_count=args.candidate_count,
            max_design_attempts=args.max_design_attempts,
            include_step3_images=args.include_step3_images,
        )
        input_path = args.product_drawing
    else:
        raise SystemExit("Provide --part-features or --product-drawing")

    report = build_experiment_report(
        experiment_id=args.experiment_id,
        input_path=input_path,
        output_dir=output_dir,
        artifacts=artifacts,
        holdout_case_id=", ".join(args.exclude_case) if args.exclude_case else None,
        prefer_category=args.prefer_category,
        expected=expected,
        renderer_repo=args.renderer_repo,
    )
    json_path, md_path = write_experiment_report(report, output_dir)
    print(f"Wrote {artifacts.parameters_path}")
    print(f"Wrote {artifacts.reasoning_path}")
    print(f"Wrote {artifacts.gong_review_path}")
    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument(
        "--part-features",
        type=Path,
        help="Pre-extracted PartFeatures JSON. Skips Claude Vision.",
    )
    input_group.add_argument(
        "--product-drawing",
        type=Path,
        help="PDF/DWG/DXF/image product drawing. Runs Claude Vision first.",
    )
    parser.add_argument("--experiment-id", default="manual_gong_experiment")
    parser.add_argument("--out-dir", type=Path)
    parser.add_argument("--expected", type=Path, help="Optional held-out ProcessForming JSON")
    parser.add_argument("--exclude-case", action="append", default=[])
    parser.add_argument("--prefer-category")
    parser.add_argument("--self-consistency-runs", type=int, default=1)
    parser.add_argument("--candidate-count", type=int, default=1)
    parser.add_argument("--max-design-attempts", type=int, default=1)
    parser.add_argument("--include-step3-images", action="store_true")
    parser.add_argument("--design-model", choices=("sonnet", "opus"), default="sonnet")
    parser.add_argument(
        "--renderer-repo",
        type=Path,
        default=Path("/Users/bobchen/FastenerDrawingEngine"),
    )
    return parser.parse_args()


if __name__ == "__main__":
    main()
