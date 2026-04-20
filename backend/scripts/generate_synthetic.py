"""
CLI script: generate N synthetic cases and save to a directory.

Usage:
    uv run python scripts/generate_synthetic.py --n 100 --output data/synthetic/
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.data.synthetic import SyntheticDataGenerator


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate synthetic FastenerGPT training cases")
    parser.add_argument("--n", type=int, default=100, help="Number of cases to generate")
    parser.add_argument("--output", type=str, default="data/synthetic", help="Output directory")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    args = parser.parse_args()

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    gen = SyntheticDataGenerator(seed=args.seed)

    print(f"Generating {args.n} synthetic cases → {output_dir}/")

    cases = gen.generate_batch(args.n)
    for i, case in enumerate(cases):
        case_path = output_dir / f"case_{i:04d}_{case.case_id[:8]}.json"
        case_path.write_text(case.model_dump_json(indent=2))

    print(f"Done. {len(cases)} cases saved.")

    # Summary statistics
    head_types: dict[str, int] = {}
    for case in cases:
        ht = case.part_features.head.type.value
        head_types[ht] = head_types.get(ht, 0) + 1

    print("\nHead type distribution:")
    for ht, count in sorted(head_types.items(), key=lambda x: -x[1]):
        print(f"  {ht}: {count} ({100 * count / len(cases):.1f}%)")


if __name__ == "__main__":
    main()
