"""Summarize a batch calibration report JSON as Markdown."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def main() -> None:
    args = _parse_args()
    report = json.loads(args.report.read_text(encoding="utf-8"))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(_render_markdown(report), encoding="utf-8")
    print(f"Wrote {args.out}")


def _render_markdown(report: dict[str, Any]) -> str:
    lines = [
        f"# Calibration Summary: {report.get('eval_id', 'unknown')}",
        "",
        f"- Cases: `{report.get('case_count', 0)}`",
        "",
        "## Metric Means",
        "",
        "| Metric | Value |",
        "|---|---:|",
    ]
    for metric in report.get("metric_means", []):
        lines.append(f"| `{metric['metric_name']}` | {metric['value']:.3f} |")

    lines.extend(
        [
            "",
            "## Failure Tags",
            "",
            "| Tag | Count |",
            "|---|---:|",
        ]
    )
    for tag, count in sorted((report.get("failure_tag_counts") or {}).items()):
        lines.append(f"| `{tag}` | {count} |")

    lines.extend(
        [
            "",
            "## Case Notes",
            "",
            "| Case | Failure Tags | Metric Notes |",
            "|---|---|---|",
        ]
    )
    for case_report in report.get("case_reports", []):
        notes = [
            metric["notes"]
            for metric in case_report.get("metrics", [])
            if metric.get("notes")
        ]
        lines.append(
            "| "
            + str(case_report.get("case_id", "unknown"))
            + " | "
            + ", ".join(f"`{tag}`" for tag in case_report.get("failure_tags", []))
            + " | "
            + "; ".join(notes)
            + " |"
        )

    return "\n".join(lines) + "\n"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    return parser.parse_args()


if __name__ == "__main__":
    main()
