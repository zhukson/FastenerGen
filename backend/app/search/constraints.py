"""Deterministic constraints for search candidate plans."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.data.schemas import OperationType
from app.search.candidate import CandidatePlan, ConstraintResult
from app.search.operations import OperationCapability, OperationRequirements


class CandidateConstraintReport(BaseModel):
    """Constraint evaluation summary for one candidate."""

    passed: bool
    checks: list[ConstraintResult] = Field(default_factory=list)
    covered_capabilities: set[OperationCapability] = Field(default_factory=set)
    missing_capabilities: set[OperationCapability] = Field(default_factory=set)
    failure_tags: list[str] = Field(default_factory=list)


def evaluate_candidate_constraints(
    candidate: CandidatePlan,
    requirements: OperationRequirements,
) -> CandidateConstraintReport:
    """Evaluate required operation coverage and precedence constraints."""

    covered = _covered_capabilities(candidate)
    required = {item.capability for item in requirements.required}
    missing = required - covered

    checks: list[ConstraintResult] = []
    failure_tags: list[str] = []

    if missing:
        checks.append(
            ConstraintResult(
                name="required_operation_coverage",
                passed=False,
                message="candidate does not cover all required operation capabilities",
                expected=", ".join(sorted(capability.value for capability in required)),
                actual=", ".join(sorted(capability.value for capability in covered)),
            )
        )
        failure_tags.append("missing_required_operation")
    else:
        checks.append(
            ConstraintResult(
                name="required_operation_coverage",
                passed=True,
                message="candidate covers all required operation capabilities",
            )
        )

    precedence_violations = _precedence_violations(candidate, requirements)
    if precedence_violations:
        checks.append(
            ConstraintResult(
                name="operation_precedence",
                passed=False,
                message="candidate violates operation precedence constraints",
                actual="; ".join(precedence_violations),
            )
        )
        failure_tags.append("wrong_precedence")
    else:
        checks.append(
            ConstraintResult(
                name="operation_precedence",
                passed=True,
                message="candidate satisfies operation precedence constraints",
            )
        )

    passed = all(check.passed for check in checks)
    candidate.constraint_results = checks
    return CandidateConstraintReport(
        passed=passed,
        checks=checks,
        covered_capabilities=covered,
        missing_capabilities=missing,
        failure_tags=failure_tags,
    )


def _covered_capabilities(candidate: CandidatePlan) -> set[OperationCapability]:
    covered: set[OperationCapability] = set()
    operations = [station.operation for station in candidate.stations]
    for operation in operations:
        covered.update(_capabilities_for_operation(operation))
    return covered


def _capabilities_for_operation(operation: OperationType) -> set[OperationCapability]:
    mapping = {
        OperationType.upsetting: {OperationCapability.material_gathering},
        OperationType.forward_extrusion: {OperationCapability.forward_extrusion},
        OperationType.backward_extrusion: {OperationCapability.backward_extrusion},
        OperationType.heading: {
            OperationCapability.flange_forming,
            OperationCapability.polygon_head_forming,
        },
        OperationType.combined: {
            OperationCapability.polygon_head_forming,
            OperationCapability.recess_forming,
        },
        OperationType.trimming: {OperationCapability.trimming_or_sizing},
        OperationType.piercing: {OperationCapability.piercing},
    }
    return mapping.get(operation, set())


def _precedence_violations(
    candidate: CandidatePlan,
    requirements: OperationRequirements,
) -> list[str]:
    positions = _capability_positions(candidate)
    violations: list[str] = []
    for requirement in requirements.required:
        current_position = positions.get(requirement.capability)
        if current_position is None:
            continue
        for dependency in requirement.precedence_after:
            dependency_position = positions.get(dependency)
            if dependency_position is None:
                continue
            if dependency_position > current_position:
                violations.append(
                    f"{requirement.capability.value} appears before {dependency.value}"
                )
        for successor in requirement.precedence_before:
            successor_position = positions.get(successor)
            if successor_position is None:
                continue
            if successor_position < current_position:
                violations.append(
                    f"{requirement.capability.value} appears after {successor.value}"
                )
    return violations


def _capability_positions(candidate: CandidatePlan) -> dict[OperationCapability, int]:
    positions: dict[OperationCapability, int] = {}
    for idx, station in enumerate(candidate.stations):
        for capability in _capabilities_for_operation(station.operation):
            positions.setdefault(capability, idx)
    return positions

