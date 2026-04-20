"""
Few-shot XML formatter for LLM prompt injection.

Converts RAGCase payloads (Layer 2) into XML few-shot examples (Layer 3).
Never stored — always derived at query time.

Sort order: least similar first → most similar last (exploit Claude's recency bias).
"""

from __future__ import annotations

from app.data.schemas import PartFeatures, RetrievedCase


class FewShotFormatter:
    """Convert retrieved RAG cases to XML few-shot examples for prompt injection."""

    def format_cases(self, cases: list[RetrievedCase], target: PartFeatures | None = None) -> str:
        """
        Format retrieved cases as XML.

        Sort: least similar first → most similar last so the most relevant
        example is freshest in the model's context window.
        """
        if not cases:
            return "<similar_cases>No similar cases found in knowledge base.</similar_cases>"

        sorted_cases = sorted(
            cases,
            key=lambda c: c.rerank_score if c.rerank_score is not None else c.vector_similarity,
        )
        parts = [self._format_single(c, i + 1) for i, c in enumerate(sorted_cases)]
        return "<similar_cases>\n" + "\n\n".join(parts) + "\n</similar_cases>"

    def _format_single(self, case: RetrievedCase, index: int) -> str:
        f = case.case.part_features
        p = case.case.process_plan
        d = case.case.die_parameters
        r = case.case.pseudo_reasoning
        sim = case.rerank_score if case.rerank_score is not None else case.vector_similarity

        # Build die spec summary per station
        die_lines: list[str] = []
        for die_param in d:
            die_lines.append(
                f"  Station {die_param.station_number}: "
                f"punch={die_param.punch.material} HRC{die_param.punch.hardness_hrc_min:.0f}-"
                f"{die_param.punch.hardness_hrc_max:.0f} OD{die_param.punch.outer_diameter}mm, "
                f"die={die_param.die.material} HRC{die_param.die.hardness_hrc_min:.0f}-"
                f"{die_param.die.hardness_hrc_max:.0f} ID{die_param.die.inner_diameter or '?'}mm, "
                f"clearance={die_param.clearance_mm}mm"
            )
        die_spec_str = "\n".join(die_lines) if die_lines else "  (no die parameters)"

        # Build station flow summary
        station_ops = " → ".join(
            f"S{s.station_number}:{s.operation.value}" for s in p.stations
        )

        key_params_parts = [
            f"upset_ratio_max={max((s.upset_ratio or 0) for s in p.stations):.2f}",
            f"blank=⌀{p.blank_diameter}×{p.blank_length}mm",
            f"stations={p.total_stations}",
        ]

        return (
            f'<case index="{index}" similarity="{sim:.3f}">\n'
            f"  <part_description>"
            f"{f.description} | {f.thread.spec} L={f.overall_length}mm | "
            f"head={f.head.type.value} ⌀{f.head.diameter}×{f.head.height}mm | "
            f"material={f.material_grade} grade={f.strength_grade}"
            f"</part_description>\n"
            f"  <process_plan>"
            f"{p.total_stations}-station: {station_ops} | "
            f"blank ⌀{p.blank_diameter}×{p.blank_length}mm"
            f"</process_plan>\n"
            f"  <die_spec>\n{die_spec_str}\n  </die_spec>\n"
            f'  <reasoning confidence="{r.confidence.value}">'
            f"[AI-inferred] {r.stock_selection} | "
            f"Stations: {r.station_count_reasoning} | "
            f"Material: {r.die_material_selection}"
            f"</reasoning>\n"
            f"  <key_parameters>{', '.join(key_params_parts)}</key_parameters>\n"
            f"</case>"
        )


# Module-level convenience function for backward compatibility
def payload_to_fewshot(cases: list[RetrievedCase], target: PartFeatures) -> str:
    return FewShotFormatter().format_cases(cases, target)
