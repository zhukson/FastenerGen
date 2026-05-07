"""v2 4-step pipeline orchestrator: input drawing -> 过模图 DXF.

Replaces the v1 designer.py orchestration. Produces ONE output artifact.

Steps:
  1. Drawing Understanding       (DrawingReader, Claude Opus 4.7 vision)
  2. Knowledge Retrieval         (knowledge.loader — load all 经验库 cases)
  3. Process Forming Design      (Claude Opus 4.7 + few-shot)
  4. 过模图 DXF Generation        (process_forming_generator, ezdxf)
  5. (Optional) Verification — wired in v3
"""

from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass
from pathlib import Path

import anthropic
from pydantic import ValidationError

from app.ai.drawing_reader import DrawingReader
from app.ai.prompts.process_forming_design import (
    PROCESS_FORMING_PROMPT_VERSION,
    SYSTEM_PROMPT,
    build_user_prompt,
)
from app.data.schemas import PartFeatures, ProcessForming
from app.drawings.process_forming_generator import render_process_forming_dxf
from app.knowledge.loader import format_for_prompt, load_library

logger = logging.getLogger(__name__)

DEFAULT_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-opus-4-7")


@dataclass
class DesignArtifacts:
    """Everything produced by one full pipeline run."""

    part_features: PartFeatures
    process_forming: ProcessForming
    dxf_path: Path
    parameters_path: Path
    reasoning_path: Path
    cited_case_ids: list[str]
    prompt_version: str = PROCESS_FORMING_PROMPT_VERSION


class ProcessDesigner:
    """The v2 pipeline: drawing -> PartFeatures -> ProcessForming -> 过模图.

    No vector retrieval (Tier 1 is full-context few-shot at N=12).
    """

    def __init__(
        self,
        *,
        client: anthropic.AsyncAnthropic | None = None,
        sync_client: anthropic.Anthropic | None = None,
        model: str = DEFAULT_MODEL,
    ) -> None:
        self.async_client = client or anthropic.AsyncAnthropic()
        self.sync_client = sync_client or anthropic.Anthropic()
        self.model = model
        self._reader = DrawingReader(client=self.async_client)
        self._library = load_library()
        if self._library.skipped:
            logger.warning(
                "Knowledge library skipped %d invalid records: %s",
                len(self._library.skipped),
                [str(p) for p, _ in self._library.skipped],
            )

    # -----------------------------------------------------------------
    # Public entry point
    # -----------------------------------------------------------------

    async def design(
        self,
        *,
        product_drawing_path: Path,
        output_dir: Path,
        prefer_category: str | None = None,
        self_consistency_runs: int = 3,
    ) -> DesignArtifacts:
        """Run the full pipeline and write artifacts to output_dir."""
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # Step 1
        part_features = await self._reader.read_drawing(
            file_path=product_drawing_path,
            self_consistency_runs=self_consistency_runs,
        )
        logger.info("Step 1 complete: %s", part_features.description)

        # Step 2 — load full library (deterministic, no LLM call)
        knowledge_xml = format_for_prompt(
            self._library, prefer_category=prefer_category
        )
        logger.info(
            "Step 2 complete: %d cases + %d standards + %d rules in context (~%d tokens)",
            len(self._library.cases),
            len(self._library.standards),
            len(self._library.rules),
            len(knowledge_xml) // 4,
        )

        # Step 3
        process_forming = await self._design_process_forming(
            part_features=part_features, knowledge_xml=knowledge_xml
        )
        logger.info(
            "Step 3 complete: %d stations, confidence=%s, cited %s",
            process_forming.station_count,
            process_forming.confidence,
            process_forming.cited_case_ids,
        )

        # Step 4
        dxf_path = output_dir / "process_forming.dxf"
        render_process_forming_dxf(
            process_forming,
            output_path=dxf_path,
            case_id=part_features.part_number,
        )

        # Persist JSON + reasoning sidecars
        params_path = output_dir / "process_parameters.json"
        params_path.write_text(
            process_forming.model_dump_json(indent=2),
            encoding="utf-8",
        )
        reasoning_path = output_dir / "design_reasoning.md"
        reasoning_path.write_text(
            self._format_reasoning_md(part_features, process_forming),
            encoding="utf-8",
        )
        logger.info("Step 4 complete: %s", dxf_path)

        return DesignArtifacts(
            part_features=part_features,
            process_forming=process_forming,
            dxf_path=dxf_path,
            parameters_path=params_path,
            reasoning_path=reasoning_path,
            cited_case_ids=list(process_forming.cited_case_ids),
        )

    # -----------------------------------------------------------------
    # Step 3 internals
    # -----------------------------------------------------------------

    async def _design_process_forming(
        self,
        *,
        part_features: PartFeatures,
        knowledge_xml: str,
        max_attempts: int = 2,
    ) -> ProcessForming:
        """Step 3: call Claude with PartFeatures + library, parse + validate."""
        last_error: Exception | None = None
        last_text: str = ""
        for attempt in range(1, max_attempts + 1):
            user_prompt = build_user_prompt(
                part_features_json=part_features.model_dump_json(indent=2, exclude_none=True),
                knowledge_xml=knowledge_xml,
            )
            if attempt > 1 and last_error is not None:
                user_prompt += (
                    f"\n\nPrevious attempt failed validation: {last_error}\n"
                    "Re-emit the JSON, fixing the issue. Output ONLY the JSON."
                )

            msg = await self.async_client.messages.create(
                model=self.model,
                max_tokens=8000,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_prompt}],
            )
            text = "".join(b.text for b in msg.content if hasattr(b, "text")).strip()
            last_text = text
            text = self._strip_fences(text)
            try:
                obj = json.loads(text)
                return ProcessForming.model_validate(obj)
            except (json.JSONDecodeError, ValidationError) as exc:
                last_error = exc
                logger.warning("Step 3 attempt %d failed: %s", attempt, exc)

        raise RuntimeError(
            f"ProcessForming generation failed after {max_attempts} attempts. "
            f"Last error: {last_error}\nLast model text (first 400):\n{last_text[:400]}"
        )

    # -----------------------------------------------------------------
    # Helpers
    # -----------------------------------------------------------------

    @staticmethod
    def _strip_fences(text: str) -> str:
        if text.startswith("```"):
            return re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.MULTILINE).strip()
        return text

    @staticmethod
    def _format_reasoning_md(
        part_features: PartFeatures, pf: ProcessForming
    ) -> str:
        lines = [
            f"# 过模图 设计理由 / Design Reasoning",
            "",
            f"**零件 / Part:** {pf.part_name_zh}  (`{part_features.part_number}`)",
            f"**材料 / Material:** {pf.material}",
            f"**工位数 / Station count:** {pf.station_count}",
            f"**信心 / Confidence:** {pf.confidence.value}",
            "",
            "## Cited reference cases",
            "",
        ]
        if pf.cited_case_ids:
            for cid in pf.cited_case_ids:
                lines.append(f"- `{cid}`")
        else:
            lines.append("_(none — design extrapolated without direct analog in library)_")
        lines += [
            "",
            "## 推理 / Reasoning",
            "",
            pf.reasoning_zh,
            "",
            "## 工位概览 / Station overview",
            "",
            "| # | 操作 | 工件几何 | L (mm) | D (mm) | 备注 |",
            "|---|---|---|---|---|---|",
        ]
        lines.append(
            f"| 0 | (blank) | {pf.blank.type} | "
            f"{pf.blank.overall_length_mm} | {pf.blank.max_diameter_mm} | 原料下料 |"
        )
        for st in pf.stations:
            lines.append(
                f"| {st.n} | {st.operation.value} | {st.workpiece.type} | "
                f"{st.workpiece.overall_length_mm} | {st.workpiece.max_diameter_mm} | "
                f"{(st.notes_zh or '').replace('|', '/')} |"
            )
        lines.append("")
        if pf.post_processes:
            lines += [
                "## 后处理 / Post-processes",
                "",
                ", ".join(p.value for p in pf.post_processes),
                "",
            ]
        return "\n".join(lines)
