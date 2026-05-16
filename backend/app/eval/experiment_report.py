"""Experiment report writer for CLI-based Gong reasoning tests."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.ai.process_designer import DesignArtifacts
from app.data.schemas import ProcessForming
from app.eval.metrics import compute_process_forming_metrics

SCHEMA_CONTRACT_NOTE = (
    "FastenerGen emits ProcessForming JSON. FastenerDrawingEngine accepts this "
    "base schema and can produce better drawings when stations also include "
    "geometry_25d and optional drawing views/tables."
)


def build_experiment_report(
    *,
    experiment_id: str,
    input_path: Path,
    output_dir: Path,
    artifacts: DesignArtifacts,
    holdout_case_id: str | None = None,
    prefer_category: str | None = None,
    expected: ProcessForming | None = None,
    renderer_repo: Path | None = None,
) -> dict[str, Any]:
    """Build a JSON-serializable report for one completed experiment."""
    metrics = compute_process_forming_metrics(artifacts.process_forming, expected)
    return {
        "experiment_id": experiment_id,
        "input_path": str(input_path),
        "output_dir": str(output_dir),
        "holdout_case_id": holdout_case_id,
        "prefer_category": prefer_category,
        "schema_contract": {
            "producer": "FastenerGen",
            "consumer": "FastenerDrawingEngine",
            "renderer_repo": str(renderer_repo) if renderer_repo else None,
            "note": SCHEMA_CONTRACT_NOTE,
            "base_schema_path": "backend/app/data/schemas.py::ProcessForming",
            "renderer_schema_path": (
                "src/fastener_drawing_engine/schema/process.py::ProcessForming"
            ),
        },
        "summary": {
            "part_name_zh": artifacts.process_forming.part_name_zh,
            "material": artifacts.process_forming.material,
            "station_count": artifacts.process_forming.station_count,
            "confidence": artifacts.process_forming.confidence.value,
            "llm_self_reported_confidence": artifacts.llm_self_reported_confidence,
            "cited_case_ids": artifacts.cited_case_ids,
            "verification_passed": artifacts.verification.passed,
            "flagged_for_review": artifacts.verification.flagged_for_review,
        },
        "metrics": [metric.model_dump(mode="json") for metric in metrics],
        "confidence_signal": artifacts.confidence_signal,
        "verification": artifacts.verification.model_dump(mode="json"),
        "artifacts": {
            "process_parameters": str(artifacts.parameters_path),
            "design_reasoning": str(artifacts.reasoning_path),
            "gong_review": str(artifacts.gong_review_path) if artifacts.gong_review_path else None,
        },
        "expected_summary": _expected_summary(expected),
    }


def write_experiment_report(report: dict[str, Any], output_dir: Path) -> tuple[Path, Path]:
    """Write JSON and Markdown report files into ``output_dir``."""
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "experiment_report.json"
    md_path = output_dir / "experiment_report.md"
    json_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    md_path.write_text(format_experiment_markdown(report), encoding="utf-8")
    return json_path, md_path


def format_experiment_markdown(report: dict[str, Any]) -> str:
    """Human-readable summary for experiment notebooks / commit review."""
    summary = report["summary"]
    lines = [
        f"# Experiment Report: {report['experiment_id']}",
        "",
        f"- Input: `{report['input_path']}`",
        f"- Output dir: `{report['output_dir']}`",
        f"- Holdout case: `{report.get('holdout_case_id') or '(none)'}`",
        f"- Prefer category: `{report.get('prefer_category') or '(none)'}`",
        "",
        "## Result",
        "",
        f"- Part: {summary['part_name_zh']}",
        f"- Material: {summary['material']}",
        f"- Stations: {summary['station_count']}",
        f"- Confidence: {summary['confidence']}",
        f"- Verification passed: {summary['verification_passed']}",
        f"- Cited cases: {', '.join(summary['cited_case_ids']) or '(none)'}",
        "",
        "## Metrics",
        "",
        "| Metric | Value | Pass | Threshold |",
        "|---|---:|---|---:|",
    ]
    for metric in report["metrics"]:
        threshold = metric.get("threshold")
        lines.append(
            f"| `{metric['metric_name']}` | {metric['value']:.3f} | "
            f"{_pass_text(metric.get('passed'))} | "
            f"{threshold if threshold is not None else ''} |"
        )

    expected = report.get("expected_summary")
    if expected:
        lines += [
            "",
            "## Expected",
            "",
            f"- Part: {expected['part_name_zh']}",
            f"- Stations: {expected['station_count']}",
            f"- Operations: {', '.join(expected['operations'])}",
        ]

    lines += [
        "",
        "## Renderer Handoff",
        "",
        report["schema_contract"]["note"],
        "",
        "Artifacts:",
        f"- `process_parameters.json`: `{report['artifacts']['process_parameters']}`",
        f"- `design_reasoning.md`: `{report['artifacts']['design_reasoning']}`",
        f"- `gong_review.md`: `{report['artifacts']['gong_review']}`",
        "",
    ]
    return "\n".join(lines)


def load_expected_process(path: Path | None) -> ProcessForming | None:
    """Load an optional held-out ProcessForming answer key."""
    if path is None:
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    if "process_forming" in data:
        data = data["process_forming"]
    return ProcessForming.model_validate(data)


def _expected_summary(expected: ProcessForming | None) -> dict[str, Any] | None:
    if expected is None:
        return None
    return {
        "part_name_zh": expected.part_name_zh,
        "station_count": expected.station_count,
        "operations": [station.operation.value for station in expected.stations],
    }


def _pass_text(value: bool | None) -> str:
    if value is None:
        return ""
    return "yes" if value else "no"
