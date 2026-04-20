"""
Batch pseudo-reasoning generator.

Processes all product-die pairs in an input directory, runs the full
PseudoReasoningPipeline, and writes ReasoningResult JSON files to the
output directory.

Usage:
    python -m scripts.batch_pseudo_reasoning \\
        --input-dir /data/pairs/ \\
        --output-dir /data/reasoned/ \\
        --concurrency 3 \\
        --max-cost-usd 100 \\
        --dry-run \\
        --resume
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
import time
import uuid
from pathlib import Path

import structlog

# ---------------------------------------------------------------------------
# Setup logging before any local imports
# ---------------------------------------------------------------------------
logging.basicConfig(level=logging.WARNING, stream=sys.stderr)
structlog.configure(
    wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
    logger_factory=structlog.PrintLoggerFactory(sys.stderr),
)

from app.ai.reasoning import PseudoReasoningPipeline  # noqa: E402
from app.data.schemas import (  # noqa: E402
    ConfidenceLevel,
    DieParameters,
    PartFeatures,
    ProcessPlan,
    ProductDiePair,
    ReasoningResult,
)

logger = structlog.get_logger()

# Cost per pair estimate (3× Claude Opus + 1× Gemini, ~2K tokens each)
_ESTIMATED_COST_PER_PAIR_USD = 0.25


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Batch pseudo-reasoning generation for product-die pairs"
    )
    p.add_argument("--input-dir", required=True, type=Path, help="Directory of pair JSON files")
    p.add_argument("--output-dir", required=True, type=Path, help="Directory for ReasoningResult JSON output")
    p.add_argument("--concurrency", type=int, default=3, help="Max parallel pipeline runs")
    p.add_argument("--max-cost-usd", type=float, default=100.0, help="Abort if cumulative cost exceeds this")
    p.add_argument("--dry-run", action="store_true", help="Estimate cost without calling LLMs")
    p.add_argument("--resume", action="store_true", help="Skip pairs that already have output files")
    return p.parse_args()


def _load_pair(path: Path) -> ProductDiePair:
    """Load a ProductDiePair from a JSON file.

    Accepts two formats:
    1. A direct ProductDiePair JSON (pair_id, part_features, process_plan, die_parameters)
    2. A RAGCase JSON (case_id, part_features, process_plan, die_parameters, …)
    """
    data = json.loads(path.read_text())

    if "pair_id" in data:
        return ProductDiePair.model_validate(data)

    # Treat as RAGCase — map fields
    return ProductDiePair(
        pair_id=data.get("case_id", str(uuid.uuid4())),
        part_features=PartFeatures.model_validate(data["part_features"]),
        process_plan=ProcessPlan.model_validate(data["process_plan"]),
        die_parameters=[DieParameters.model_validate(d) for d in data["die_parameters"]],
        source_order_id=data.get("order_id"),
    )


def _confidence_dist(results: list[ReasoningResult]) -> dict[str, int]:
    dist: dict[str, int] = {c.value: 0 for c in ConfidenceLevel}
    for r in results:
        dist[r.quality.overall_confidence.value] += 1
    return dist


class _Progress:
    """Simple progress tracker (no external deps needed)."""

    def __init__(self, total: int) -> None:
        self.total = total
        self.done = 0
        self.start = time.monotonic()

    def update(self, desc: str = "") -> None:
        self.done += 1
        elapsed = time.monotonic() - self.start
        rate = self.done / elapsed if elapsed > 0 else 0
        eta = (self.total - self.done) / rate if rate > 0 else 0
        pct = 100 * self.done / self.total
        print(
            f"\r[{self.done}/{self.total}] {pct:.0f}%  "
            f"elapsed={elapsed:.0f}s  eta={eta:.0f}s  {desc}",
            end="",
            flush=True,
        )

    def close(self) -> None:
        print()  # newline after last update


async def _process_pair(
    pipeline: PseudoReasoningPipeline,
    pair: ProductDiePair,
    output_dir: Path,
) -> ReasoningResult | None:
    out_path = output_dir / f"{pair.pair_id}.json"
    try:
        result = await pipeline.generate(pair)
        out_path.write_text(result.model_dump_json(indent=2))
        return result
    except Exception as exc:
        logger.error("pair_failed", pair_id=pair.pair_id, error=str(exc))
        error_path = output_dir / f"{pair.pair_id}.error.json"
        error_path.write_text(json.dumps({"pair_id": pair.pair_id, "error": str(exc)}))
        return None


async def run(args: argparse.Namespace) -> None:
    input_dir: Path = args.input_dir
    output_dir: Path = args.output_dir
    concurrency: int = args.concurrency
    max_cost: float = args.max_cost_usd
    dry_run: bool = args.dry_run
    resume: bool = args.resume

    if not input_dir.exists():
        print(f"ERROR: input-dir does not exist: {input_dir}", file=sys.stderr)
        sys.exit(1)

    output_dir.mkdir(parents=True, exist_ok=True)

    pair_files = sorted(input_dir.glob("*.json"))
    if not pair_files:
        print("No JSON files found in input-dir.", file=sys.stderr)
        sys.exit(1)

    # Filter out error files
    pair_files = [f for f in pair_files if not f.name.endswith(".error.json")]

    if resume:
        completed_ids = {f.stem for f in output_dir.glob("*.json") if not f.name.endswith(".error.json")}
        before = len(pair_files)
        pair_files = [f for f in pair_files if Path(f).stem not in completed_ids]
        skipped = before - len(pair_files)
        print(f"Resume: skipping {skipped} already-completed pairs.")

    total = len(pair_files)
    print(f"Found {total} pairs to process.")

    # --- Dry-run mode ---
    if dry_run:
        estimated_cost = total * _ESTIMATED_COST_PER_PAIR_USD
        print(f"\nDry-run estimate:")
        print(f"  Pairs:          {total}")
        print(f"  Cost/pair:     ~${_ESTIMATED_COST_PER_PAIR_USD:.2f}")
        print(f"  Total est.:    ~${estimated_cost:.2f}")
        print(f"  Max allowed:    ${max_cost:.2f}")
        if estimated_cost > max_cost:
            print(f"  WARNING: estimated cost exceeds --max-cost-usd ${max_cost:.2f}")
        print("\nDry-run complete. Use without --dry-run to execute.")
        return

    if total * _ESTIMATED_COST_PER_PAIR_USD > max_cost:
        print(
            f"WARNING: estimated cost ${total * _ESTIMATED_COST_PER_PAIR_USD:.2f} "
            f"exceeds --max-cost-usd ${max_cost:.2f}. Proceeding anyway — "
            f"pipeline will abort when limit is reached.",
            file=sys.stderr,
        )

    # Load all pairs
    pairs: list[ProductDiePair] = []
    load_errors: list[str] = []
    for pf in pair_files:
        try:
            pairs.append(_load_pair(pf))
        except Exception as exc:
            load_errors.append(f"{pf.name}: {exc}")

    if load_errors:
        print(f"WARNING: {len(load_errors)} files failed to load:", file=sys.stderr)
        for e in load_errors[:10]:
            print(f"  {e}", file=sys.stderr)

    pipeline = PseudoReasoningPipeline()
    sem = asyncio.Semaphore(concurrency)
    progress = _Progress(len(pairs))

    cumulative_cost = 0.0
    results: list[ReasoningResult] = []
    errors = 0
    aborted = False

    async def _guarded(pair: ProductDiePair) -> None:
        nonlocal cumulative_cost, errors, aborted
        if aborted:
            return
        async with sem:
            if aborted:
                return
            result = await _process_pair(pipeline, pair, output_dir)
            if result:
                cumulative_cost += result.total_cost_usd
                results.append(result)
                if cumulative_cost >= max_cost:
                    aborted = True
                    logger.warning("cost_limit_reached", cost_usd=cumulative_cost)
            else:
                errors += 1
            progress.update(f"${cumulative_cost:.3f} spent")

    await asyncio.gather(*[_guarded(p) for p in pairs])
    progress.close()

    # --- Summary report ---
    dist = _confidence_dist(results)
    print("\n" + "=" * 60)
    print("BATCH SUMMARY")
    print("=" * 60)
    print(f"  Total pairs:    {len(pairs)}")
    print(f"  Completed:      {len(results)}")
    print(f"  Errors/skipped: {errors}")
    print(f"  Aborted early:  {aborted}")
    print(f"  Total cost:     ${cumulative_cost:.4f}")
    print(f"  Output dir:     {output_dir}")
    print()
    print("  Confidence distribution:")
    for level, count in dist.items():
        pct = 100 * count / len(results) if results else 0
        print(f"    {level:8s}: {count:4d}  ({pct:.0f}%)")
    print("=" * 60)

    if aborted:
        print(f"\nABORTED: cost limit ${max_cost:.2f} reached at ${cumulative_cost:.4f}.")
        sys.exit(2)


def main() -> None:
    args = _parse_args()
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
