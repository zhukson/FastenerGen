"""Experiment report behavior for CLI-based Gong tests."""

from pathlib import Path

from app.ai.process_designer import DesignArtifacts
from app.data.schemas import (
    CheckSeverity,
    ConfidenceLevel,
    OperationType,
    PartFeatures,
    ProcessForming,
    StationStep,
    VerificationCheck,
    VerificationResult,
    WorkpieceGeometry,
)
from app.eval.experiment_report import build_experiment_report, write_experiment_report


def test_experiment_report_records_metrics_and_renderer_handoff(tmp_path: Path) -> None:
    predicted = _process_forming("predicted", [OperationType.combined, OperationType.upsetting])
    expected = _process_forming("expected", [OperationType.combined, OperationType.heading])
    artifacts = DesignArtifacts(
        part_features=PartFeatures(
            part_number="T-001",
            description="test fastener",
            overall_length=10,
        ),
        process_forming=predicted,
        verification=VerificationResult(
            passed=True,
            checks=[
                VerificationCheck(
                    check_name="fixture",
                    passed=True,
                    severity=CheckSeverity.error,
                    message="ok",
                )
            ],
        ),
        parameters_path=tmp_path / "process_parameters.json",
        reasoning_path=tmp_path / "design_reasoning.md",
        gong_review_path=tmp_path / "gong_review.md",
        cited_case_ids=["case-a"],
        confidence_signal={"confidence": "medium", "score": 3},
        llm_self_reported_confidence="high",
    )

    report = build_experiment_report(
        experiment_id="fixture",
        input_path=tmp_path / "input.pdf",
        output_dir=tmp_path,
        artifacts=artifacts,
        holdout_case_id="case-a",
        prefer_category="fixture_category",
        expected=expected,
        renderer_repo=Path("/tmp/FastenerDrawingEngine"),
    )

    metric_names = {metric["metric_name"] for metric in report["metrics"]}
    assert "station_count_error" in metric_names
    assert "station_operation_alignment" in metric_names
    assert "key_dimension_coverage" in metric_names
    assert "renderer_geometry_readiness" in metric_names
    assert report["schema_contract"]["consumer"] == "FastenerDrawingEngine"
    assert report["expected_summary"]["station_count"] == 2

    json_path, md_path = write_experiment_report(report, tmp_path)
    assert json_path.exists()
    markdown = md_path.read_text(encoding="utf-8")
    assert "Renderer Handoff" in markdown
    assert "FastenerDrawingEngine" in markdown


def _process_forming(name: str, operations: list[OperationType]) -> ProcessForming:
    stations = [
        StationStep(
            n=index,
            operation=operation,
            workpiece=WorkpieceGeometry(
                type="cylinder",
                overall_length_mm=10 - index,
                max_diameter_mm=5 + index,
                profile_segments=[
                    {
                        "label_zh": "段",
                        "length_mm": 10 - index,
                        "diameter_mm": 5 + index,
                    }
                ],
            ),
            key_dimensions={"L": 10 - index, "D": 5 + index},
        )
        for index, operation in enumerate(operations, start=1)
    ]
    return ProcessForming(
        part_name_zh=name,
        material="10B21",
        blank=WorkpieceGeometry(type="cylinder", overall_length_mm=10, max_diameter_mm=5),
        stations=stations,
        post_processes=[],
        reasoning_zh="fixture",
        cited_case_ids=["case-a"],
        confidence=ConfidenceLevel.medium,
    )
