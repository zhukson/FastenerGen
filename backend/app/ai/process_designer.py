"""Gong-style process-forming schema orchestrator.

Produces ProcessForming JSON plus reasoning sidecars. DXF rendering lives in
the separate FastenerDrawingEngine repository.

Steps:
  1. Drawing Understanding       (DrawingReader, Claude Opus 4.7 vision)
  2. Knowledge Retrieval         (knowledge.loader — load all 经验库 cases)
  3. Process Forming Design      (Claude Opus 4.7 + few-shot)
  4. Rule verification           (textbook formula guardrails + retry)
  5. Persist schema/reasoning    (renderer consumes ProcessForming JSON)
"""

from __future__ import annotations

import asyncio
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
from app.ai.verification import ProcessFormingVerifier
from app.core.anthropic_client import create_anthropic_client, create_async_anthropic_client
from app.core.config import settings
from app.data.schemas import (
    CheckSeverity,
    ConfidenceLevel,
    PartFeatures,
    ProcessForming,
    VerificationResult,
)
from app.knowledge.loader import compute_neighbor_density, format_for_prompt, load_library

logger = logging.getLogger(__name__)

DEFAULT_MODEL = os.getenv("ANTHROPIC_MODEL", settings.primary_model)


@dataclass
class DesignArtifacts:
    """Everything produced by one full pipeline run."""

    part_features: PartFeatures
    process_forming: ProcessForming
    verification: VerificationResult
    parameters_path: Path
    reasoning_path: Path
    cited_case_ids: list[str]
    confidence_signal: dict | None = None  # neighbor-density breakdown (优化 4)
    llm_self_reported_confidence: str | None = None
    gong_review: str = ""  # P1.5 — free-form Gong-style critique from Step 3
    gong_review_path: Path | None = None
    prompt_version: str = PROCESS_FORMING_PROMPT_VERSION


class ProcessDesigner:
    """The v2 pipeline: drawing -> PartFeatures -> ProcessForming schema.

    No vector retrieval (Tier 1 is full-context few-shot at N=12).
    """

    def __init__(
        self,
        *,
        client: anthropic.AsyncAnthropic | None = None,
        sync_client: anthropic.Anthropic | None = None,
        model: str = DEFAULT_MODEL,
    ) -> None:
        self.async_client = client or create_async_anthropic_client()
        self.sync_client = sync_client or create_anthropic_client()
        self.model = model
        self._reader = DrawingReader(client=self.async_client)
        self._library = load_library()
        self._verifier = ProcessFormingVerifier()
        self._last_gong_review: str = ""
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
        exclude_case_ids: list[str] | None = None,
        candidate_count: int = 1,
        max_design_attempts: int = 1,
        include_step3_images: bool = False,
    ) -> DesignArtifacts:
        """Run drawing understanding + process design and write artifacts."""
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        part_features = await self._reader.read_drawing(
            file_path=product_drawing_path,
            self_consistency_runs=self_consistency_runs,
        )
        logger.info("Step 1 complete: %s", part_features.description)

        # P1 — render the input drawing once for reuse in Step 3 multimodal.
        # Step 3 sees the original image, not just the vision step's PartFeatures
        # JSON, so it can self-correct vision misreads (SW6 vs hex socket etc.).
        drawing_images = []
        if include_step3_images:
            try:
                drawing_images = await self._reader._to_images(product_drawing_path)
            except Exception as exc:
                logger.warning("P1_image_for_step3_failed", error=str(exc))

        return await self.design_from_part_features(
            part_features=part_features,
            output_dir=output_dir,
            prefer_category=prefer_category,
            exclude_case_ids=exclude_case_ids,
            candidate_count=candidate_count,
            max_design_attempts=max_design_attempts,
            drawing_images=drawing_images,
        )

    async def design_from_part_features(
        self,
        *,
        part_features: PartFeatures,
        output_dir: Path,
        prefer_category: str | None = None,
        exclude_case_ids: list[str] | None = None,
        candidate_count: int = 1,
        max_design_attempts: int = 1,
        drawing_images: list[dict] | None = None,
    ) -> DesignArtifacts:
        """Run process design from already-extracted product/final-station features."""
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # Step 2 — load full library + feature-targeted sub-process snippets (优化 3)
        knowledge_xml = format_for_prompt(
            self._library,
            prefer_category=prefer_category,
            part_features=part_features,
            exclude_case_ids=exclude_case_ids,
            compact=True,
        )
        logger.info(
            "Step 2 complete: %d cases + %d standards + %d rules + %d textbook rules + %d textbook cases + %d patterns in context (~%d tokens), excluded=%s",
            len(self._library.cases),
            len(self._library.standards),
            len(self._library.rules),
            len(self._library.textbook_rules),
            len(self._library.textbook_cases),
            len(self._library.patterns),
            len(knowledge_xml) // 4,
            exclude_case_ids or [],
        )

        # Step 3
        process_forming, verification = await self._design_process_forming(
            part_features=part_features,
            knowledge_xml=knowledge_xml,
            drawing_images=drawing_images,
            candidate_count=candidate_count,
            max_attempts=max_design_attempts,
        )
        logger.info(
            "Step 3 complete: %d stations, llm_confidence=%s, cited %s, verification=%s",
            process_forming.station_count,
            process_forming.confidence,
            process_forming.cited_case_ids,
            verification.passed,
        )

        # 优化 4 — override LLM-reported confidence with measurable neighbor density.
        llm_confidence = process_forming.confidence.value
        density_signal = compute_neighbor_density(
            self._library,
            part_features,
            exclude_case_ids=exclude_case_ids,
        )
        measured_confidence = ConfidenceLevel(density_signal["confidence"])
        if measured_confidence != process_forming.confidence:
            logger.info(
                "confidence_overridden llm=%s measured=%s rationale=%s",
                llm_confidence,
                measured_confidence.value,
                density_signal["rationale"],
            )
        process_forming.confidence = measured_confidence

        # Persist JSON + reasoning sidecars. DXF rendering is intentionally
        # outside this repo; pass `process_parameters.json` to FastenerDrawingEngine.
        params_path = output_dir / "process_parameters.json"
        params_path.write_text(
            process_forming.model_dump_json(indent=2),
            encoding="utf-8",
        )
        reasoning_path = output_dir / "design_reasoning.md"
        gong_review = self._last_gong_review or ""
        reasoning_path.write_text(
            self._format_reasoning_md(
                part_features, process_forming, verification,
                density_signal=density_signal,
                llm_confidence=llm_confidence,
                gong_review=gong_review,
            ),
            encoding="utf-8",
        )
        # P1.5 — also save the raw <gong_review> as its own sidecar so CLI
        # experiment reports can link the full free-form analysis.
        gong_review_path = output_dir / "gong_review.md"
        if gong_review:
            gong_review_path.write_text(
                "# 龚茂良式工艺审查 / Gong-style Engineering Review\n\n"
                f"Part: {process_forming.part_name_zh}\n"
                f"Drawing: {part_features.part_number}\n\n"
                "---\n\n"
                f"{gong_review}\n",
                encoding="utf-8",
            )
        else:
            gong_review_path.write_text(
                "# 龚茂良式工艺审查 / Gong-style Engineering Review\n\n"
                "_(LLM did not emit a <gong_review> block this run; "
                "see design_reasoning.md for the condensed reasoning.)_\n",
                encoding="utf-8",
            )
        logger.info("Step 4 complete: %s", params_path)

        return DesignArtifacts(
            part_features=part_features,
            process_forming=process_forming,
            verification=verification,
            parameters_path=params_path,
            reasoning_path=reasoning_path,
            cited_case_ids=list(process_forming.cited_case_ids),
            confidence_signal=density_signal,
            llm_self_reported_confidence=llm_confidence,
            gong_review=gong_review,
            gong_review_path=gong_review_path,
        )

    # -----------------------------------------------------------------
    # Step 3 internals
    # -----------------------------------------------------------------

    # 优化 2 — multi-candidate prompt variants.
    #
    # Opus 4.7 doesn't accept a non-default `temperature`; sampling diversity
    # has to come from the prompt itself. These three suffixes elicit
    # semantically different plans (conservative / balanced / thorough) so the
    # verifier has genuine choices to pick from rather than near-identical
    # samples.
    _CANDIDATE_VARIANTS: tuple[tuple[str, str], ...] = (
        ("conservative",
         "\n\n---\nCandidate variant: CONSERVATIVE.\n"
         "Among plans that satisfy all constraints, prefer the FEWEST stations. "
         "Combine operations into a single station whenever upset/extrude limits allow. "
         "Do not add an extra station 'just to be safe'."),
        ("balanced",
         ""),  # default framing, no suffix
        ("thorough",
         "\n\n---\nCandidate variant: THOROUGH.\n"
         "When in doubt, prefer adding ONE extra integrity station "
         "(e.g. predeform, trim, or final calibration) to guarantee dimensional "
         "accuracy and surface quality. Cite an extra textbook case if you do."),
    )

    async def _design_process_forming(
        self,
        *,
        part_features: PartFeatures,
        knowledge_xml: str,
        drawing_images: list[dict] | None = None,
        candidate_count: int = 1,
        max_attempts: int = 2,
    ) -> tuple[ProcessForming, VerificationResult]:
        """Step 3: generate N semantic-variant candidates, pick best by verifier score.

        Each candidate runs in parallel with a different prompt suffix
        (conservative / balanced / thorough). After validate+verify+score, we
        return the highest-scoring plan that passes error-severity checks. If
        none pass, the best failure's errors are fed back as retry feedback.
        """
        last_error: Exception | None = None
        last_text: str = ""
        variants = self._candidate_variants(candidate_count)
        for attempt in range(1, max_attempts + 1):
            base_prompt = build_user_prompt(
                part_features_json=part_features.model_dump_json(indent=2, exclude_none=True),
                knowledge_xml=knowledge_xml,
            )
            if attempt > 1 and last_error is not None:
                base_prompt += (
                    f"\n\nPrevious attempt's best candidate failed: {last_error}\n"
                    "Re-emit the JSON, fixing the issue. Output ONLY the JSON."
                )

            results = await asyncio.gather(
                *[
                    self._generate_candidate(
                        base_prompt + suffix,
                        variant=name,
                        part_features=part_features,
                        drawing_images=drawing_images,
                    )
                    for (name, suffix) in variants
                ],
                return_exceptions=True,
            )

            scored_valid: list[tuple[float, ProcessForming, VerificationResult, str]] = []
            scored_invalid: list[tuple[float, VerificationResult, str]] = []

            for idx, result in enumerate(results):
                variant_name = variants[idx][0]
                if isinstance(result, Exception):
                    logger.warning(
                        "candidate_failed attempt=%d variant=%s exc=%s",
                        attempt, variant_name, result,
                    )
                    last_error = result
                    continue
                forming, verification, raw_text, gong_review = result
                last_text = raw_text
                score = self._verifier.score(part_features, forming, verification)
                logger.info(
                    "candidate_scored attempt=%d variant=%s stations=%d passed=%s "
                    "score=%.2f review_chars=%d",
                    attempt, variant_name, forming.station_count,
                    verification.passed, score, len(gong_review),
                )
                if verification.passed:
                    scored_valid.append(
                        (score, forming, verification, variant_name, gong_review)
                    )
                else:
                    scored_invalid.append(
                        (score, verification, self._format_verification_errors(verification))
                    )

            if scored_valid:
                scored_valid.sort(key=lambda x: x[0], reverse=True)
                (
                    best_score, best_forming, best_verification,
                    best_variant, best_review,
                ) = scored_valid[0]
                best_verification.retry_count = attempt - 1
                logger.info(
                    "candidate_selected attempt=%d variant=%s score=%.2f "
                    "stations=%d candidates_valid=%d review_chars=%d",
                    attempt, best_variant, best_score,
                    best_forming.station_count, len(scored_valid),
                    len(best_review),
                )
                # Stash the review so design() can persist it to a sidecar.
                self._last_gong_review = best_review
                return best_forming, best_verification

            # All candidates failed verification → take best-scoring failure as
            # retry feedback (highest score = closest to valid).
            if scored_invalid:
                scored_invalid.sort(key=lambda x: x[0], reverse=True)
                _, _, err_msg = scored_invalid[0]
                last_error = RuntimeError(err_msg)
                logger.warning(
                    "Step 3 attempt %d: all %d candidates failed verification; best error: %s",
                    attempt, len(scored_invalid), err_msg,
                )

        raise RuntimeError(
            f"ProcessForming generation failed after {max_attempts} attempts. "
            f"Last error: {last_error}\nLast model text (first 400):\n{last_text[:400]}"
        )

    @classmethod
    def _candidate_variants(cls, candidate_count: int) -> tuple[tuple[str, str], ...]:
        """Return prompt variants for cheap/default/quality modes."""
        if candidate_count <= 1:
            return (("balanced", ""),)
        if candidate_count == 2:
            return cls._CANDIDATE_VARIANTS[:2]
        return cls._CANDIDATE_VARIANTS

    # P1 — adaptive thinking. DEFAULT OFF until we have a reliable production
    # config. Why off: with thinking enabled, adaptive can eat 4-7K tokens of
    # the max_tokens budget, leaving the JSON output truncated → parse errors.
    # Each truncated candidate still costs ~$0.50 in output tokens. Three
    # candidates × 2 retry attempts can burn $3-5 with no usable output.
    #
    # Enable per-run with FASTENERGEN_THINKING=1. When enabled we crank
    # max_tokens to 24000 (≈ 16K thinking + 8K JSON safety margin) and keep
    # the request timeout at 180s.
    _USE_THINKING = os.getenv("FASTENERGEN_THINKING", "0") == "1"
    _MAX_OUTPUT_TOKENS = 24000 if _USE_THINKING else 8000

    async def _generate_candidate(
        self,
        user_prompt: str,
        *,
        variant: str,
        part_features: PartFeatures,
        drawing_images: list[dict] | None = None,
    ) -> tuple[ProcessForming, VerificationResult, str, str]:
        """Single-candidate generation: API call → parse → verify.

        Variant is for log traceability; diversity comes from the prompt suffix
        in ``user_prompt``. Extended thinking is enabled (P1) so the model can
        reason freely before committing to JSON. Drawing images (P1) are
        attached so the model can self-verify the upstream vision step.
        """
        # Build content blocks: optional images first, then text prompt
        content: list[dict] = []
        if drawing_images:
            for img in drawing_images:
                content.append({
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": img["media_type"],
                        "data": img["data"],
                    },
                })
        content.append({"type": "text", "text": user_prompt})

        # 180s timeout per candidate — generous for Opus + adaptive thinking
        # + 35K-token prompt + image. Without an explicit timeout the SDK
        # silently retries forever if the upstream stalls. Set to 0 / None to
        # disable. Thinking is opt-in: see _USE_THINKING.
        kwargs: dict = {
            "model": self.model,
            "max_tokens": self._MAX_OUTPUT_TOKENS,
            "system": SYSTEM_PROMPT,
            "messages": [{"role": "user", "content": content}],
        }
        if self._USE_THINKING:
            kwargs["thinking"] = {"type": "adaptive"}
        msg = await self.async_client.with_options(timeout=180.0).messages.create(
            **kwargs,
        )
        # With thinking enabled, response has ThinkingBlock(s) then TextBlock(s).
        # Be permissive: accept any block that exposes a non-empty `.text`
        # attribute and is NOT a thinking block. Adaptive thinking on different
        # Claude versions has used slightly different block-type strings, so
        # filtering on type='text' alone has occasionally missed real output.
        text_pieces: list[str] = []
        block_types: list[str] = []
        for b in msg.content:
            btype = getattr(b, "type", None)
            block_types.append(btype or type(b).__name__)
            if btype in ("thinking", "redacted_thinking"):
                continue
            t = getattr(b, "text", None)
            if isinstance(t, str) and t:
                text_pieces.append(t)
        text = "".join(text_pieces).strip()

        # Detect truncation early — saves $$ by short-circuiting before retry.
        # When stop_reason == "max_tokens" the JSON output was cut off and any
        # retry with the same budget will hit the same wall.
        stop_reason = getattr(msg, "stop_reason", None)
        usage = getattr(msg, "usage", None)
        in_tokens = getattr(usage, "input_tokens", "?") if usage else "?"
        out_tokens = getattr(usage, "output_tokens", "?") if usage else "?"
        if stop_reason == "max_tokens":
            logger.error(
                "candidate_TRUNCATED variant=%s stop_reason=%s "
                "input_tokens=%s output_tokens=%s max_tokens=%s "
                "block_types=%s — bump _MAX_OUTPUT_TOKENS or disable thinking",
                variant, stop_reason, in_tokens, out_tokens,
                self._MAX_OUTPUT_TOKENS, block_types,
            )
            raise RuntimeError(
                f"candidate truncated (stop_reason=max_tokens, "
                f"output_tokens={out_tokens}/{self._MAX_OUTPUT_TOKENS}). "
                "JSON unparseable. Increase _MAX_OUTPUT_TOKENS or set "
                "FASTENERGEN_THINKING=0 to disable adaptive thinking."
            )

        if not text:
            logger.warning(
                "candidate_empty_text variant=%s stop_reason=%s "
                "out_tokens=%s block_types=%s",
                variant, stop_reason, out_tokens, block_types,
            )
        raw_text = text

        # P1.5 — extract <gong_review> free-form analysis (if present),
        # then strip it and parse the JSON object that follows. Even if the
        # model forgot the review tags, fall through to plain JSON extraction.
        gong_review, json_text = self._split_review_and_json(text)

        try:
            obj = json.loads(json_text)
            forming = ProcessForming.model_validate(obj)
        except (json.JSONDecodeError, ValidationError) as exc:
            raise RuntimeError(f"candidate parse/validation failed: {exc}") from exc

        verification = self._verifier.verify(
            features=part_features,
            forming=forming,
            retry_count=0,
        )
        return forming, verification, raw_text, gong_review

    # -----------------------------------------------------------------
    # Helpers
    # -----------------------------------------------------------------

    @staticmethod
    def _strip_fences(text: str) -> str:
        if text.startswith("```"):
            return re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.MULTILINE).strip()
        return text

    @staticmethod
    def _split_review_and_json(text: str) -> tuple[str, str]:
        """Extract optional <gong_review>...</gong_review> + the JSON object.

        The prompt asks the model to emit:
          <gong_review> ...free-form Gong-style critique... </gong_review>
          { ...JSON conforming to ProcessForming... }

        We tolerate the review being missing; in that case we just return
        the entire stripped JSON-fenced text and an empty review string.
        """
        review = ""
        review_match = re.search(
            r"<gong_review>(.*?)</gong_review>", text, flags=re.DOTALL | re.IGNORECASE
        )
        if review_match:
            review = review_match.group(1).strip()
            # Remove the entire <gong_review>...</gong_review> block so what's
            # left is (ideally) just the JSON object.
            text = (
                text[: review_match.start()] + text[review_match.end():]
            ).strip()

        # Strip ```json fences if present
        text = ProcessDesigner._strip_fences(text)

        # Locate the outermost JSON object: from the first '{' to the last '}'.
        # Robust against trailing prose after the JSON. Falls back to the raw
        # text so json.loads can raise a useful error.
        start = text.find("{")
        end = text.rfind("}")
        json_text = (
            text[start : end + 1]
            if start != -1 and end != -1 and end > start
            else text
        )

        return review, json_text

    @staticmethod
    def _format_verification_errors(verif: VerificationResult) -> str:
        failed = [
            c for c in verif.checks
            if not c.passed and c.severity == CheckSeverity.error
        ]
        return "; ".join(f"{c.check_name}: {c.message} ({c.actual or 'no actual'})" for c in failed)

    @staticmethod
    def _format_reasoning_md(
        part_features: PartFeatures,
        pf: ProcessForming,
        verification: VerificationResult,
        *,
        density_signal: dict | None = None,
        llm_confidence: str | None = None,
        gong_review: str = "",
    ) -> str:
        lines = [
            "# 过模图 设计理由 / Design Reasoning",
            "",
            f"**零件 / Part:** {pf.part_name_zh}  (`{part_features.part_number}`)",
            f"**材料 / Material:** {pf.material}",
            f"**工位数 / Station count:** {pf.station_count}",
            f"**信心 / Confidence (measured):** {pf.confidence.value}",
        ]
        if llm_confidence and llm_confidence != pf.confidence.value:
            lines.append(
                f"**LLM self-reported confidence:** {llm_confidence} "
                "(overridden by measured neighbor density)"
            )
        if density_signal:
            lines += [
                "",
                "### 信心信号 / Confidence rationale (measurable)",
                "",
                f"- score: **{density_signal.get('score', '?')}**",
                f"- detected input features: `{density_signal.get('detected_features') or []}`",
                f"- same-category factory cases: {density_signal.get('same_category_cases') or '(none)'}",
                f"- geometric neighbors (±67% L/D): {density_signal.get('geometric_neighbors') or '(none)'}",
                f"- rationale: {density_signal.get('rationale', '')}",
            ]
        if gong_review:
            lines += [
                "",
                "## 龚茂良式审查 / Gong-style Engineering Review",
                "",
                "_(Free-form analysis the LLM produced before committing to "
                "the JSON plan — covers feature reading, station-count "
                "derivation, physical-limit checks, material prep, and "
                "cited-case justification.)_",
                "",
                gong_review,
            ]
        lines += [
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
            "## 推理摘要 / Condensed Reasoning",
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
        lines += [
            "## 规则校验 / Rule checks",
            "",
            "| Check | Severity | Result | Message |",
            "|---|---|---|---|",
        ]
        for check in verification.checks:
            result = "pass" if check.passed else "review"
            message = check.message.replace("|", "/")
            lines.append(
                f"| `{check.check_name}` | {check.severity.value} | {result} | {message} |"
            )
        lines.append("")
        return "\n".join(lines)
