"""
Pseudo-reasoning pipeline for bootstrapping cold-heading domain knowledge.

For each product-die data pair:
  1. Claude Opus 4.7 × 3 runs (parallel, self-consistency)
  2. Gemini 2.5 Pro × 1 run (cross-validation)
  3. Rule-based verifier (physics + data grounding)
  4. Aggregate → ReasoningResult with QualityScores

Only high-confidence results are accepted into the RAG store.
Redis-cached by SHA-256 of (pair JSON + prompt versions).
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import math
import time
from collections.abc import Callable, Coroutine
from typing import Any

import anthropic
import structlog

from app.ai.prompts.pseudo_reasoning import (
    CV_USER_TEMPLATE,
    CV_VERSION,
    PR_SYSTEM,
    PR_TOOL_SCHEMA,
    PR_USER_TEMPLATE,
    PR_VERSION,
)
from app.ai.quality import QualityScorer, RuleVerifier
from app.core.config import settings
from app.data.schemas import (
    ConfidenceLevel,
    CrossValidation,
    DieParameters,
    PartFeatures,
    PrimaryReasoning,
    ProcessPlan,
    ProductDiePair,
    PseudoReasoning,
    QualityScores,
    ReasoningResult,
    RuleVerification,
)

logger = structlog.get_logger()

# LLM cost constants (USD per million tokens)
_CLAUDE_IN_COST_PER_M = 15.0    # Opus 4.7 input
_CLAUDE_OUT_COST_PER_M = 75.0   # Opus 4.7 output
_GEMINI_IN_COST_PER_M = 1.25    # Gemini 2.5 Pro input
_GEMINI_OUT_COST_PER_M = 10.0   # Gemini 2.5 Pro output

_CALL_TIMEOUT_S = 90.0
_TOTAL_TIMEOUT_S = 300.0


class PseudoReasoningPipeline:
    """
    Generate pseudo-reasoning for product-die pairs.

    1. Claude Opus 4.7 × 3 runs (self-consistency)
    2. Gemini 2.5 Pro × 1 run (cross-validation)
    3. Rule-based verifier (physics + data grounding)
    4. Aggregate → confidence score → ReasoningResult
    """

    def __init__(
        self,
        anthropic_client: anthropic.AsyncAnthropic | None = None,
        redis_client: Any | None = None,
    ) -> None:
        self._claude = anthropic_client or anthropic.AsyncAnthropic(
            api_key=settings.anthropic_api_key
        )
        self._redis = redis_client
        self._quality = QualityScorer()
        self._rules = RuleVerifier()

    async def generate(self, pair: ProductDiePair) -> ReasoningResult:
        """Run the full pipeline for one product-die pair."""
        start = time.monotonic()
        log = logger.bind(pair_id=pair.pair_id)

        cache_key = self._cache_key(pair)
        if self._redis:
            cached = await self._redis.get(cache_key)
            if cached:
                log.info("pseudo_reasoning_cache_hit")
                return ReasoningResult.model_validate_json(cached)

        async with asyncio.timeout(_TOTAL_TIMEOUT_S):
            primaries = list(
                await asyncio.gather(
                    *[self._run_primary(pair, i) for i in range(3)]
                )
            )
            cross_val = await self._run_cross_validation(pair, primaries[0])
            rules = self._run_rule_verifier(pair, primaries)
            result = self._aggregate(primaries, cross_val, rules, pair.pair_id)

        result.total_time_s = time.monotonic() - start

        if self._redis:
            await self._redis.set(cache_key, result.model_dump_json(), ex=86400 * 7)

        log.info(
            "pseudo_reasoning_complete",
            cost_usd=result.total_cost_usd,
            time_s=round(result.total_time_s, 2),
            confidence=result.quality.overall_confidence,
        )
        return result

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _cache_key(self, pair: ProductDiePair) -> str:
        data = pair.model_dump_json() + PR_VERSION + CV_VERSION
        return f"pseudo_reasoning:{hashlib.sha256(data.encode()).hexdigest()}"

    async def _with_retry(
        self,
        fn: Callable[[], Coroutine[Any, Any, Any]],
        max_attempts: int = 3,
    ) -> Any:
        last_exc: Exception | None = None
        for attempt in range(max_attempts):
            try:
                async with asyncio.timeout(_CALL_TIMEOUT_S):
                    return await fn()
            except Exception as exc:
                last_exc = exc
                logger.warning(
                    "llm_call_failed",
                    attempt=attempt + 1,
                    error=str(exc),
                )
                if attempt < max_attempts - 1:
                    await asyncio.sleep(2.0 ** attempt)
        raise last_exc  # type: ignore[misc]

    def _build_primary_user_msg(self, pair: ProductDiePair) -> str:
        blank_d = pair.process_plan.blank_diameter
        shank_d = pair.part_features.shank.diameter
        head_d = pair.part_features.head.diameter
        blank_vol = math.pi * (blank_d / 2) ** 2 * pair.process_plan.blank_length
        return PR_USER_TEMPLATE.format(
            features_json=pair.part_features.model_dump_json(indent=2),
            process_plan_json=pair.process_plan.model_dump_json(indent=2),
            die_params_json=json.dumps(
                [p.model_dump() for p in pair.die_parameters], indent=2
            ),
            blank_diameter=blank_d,
            shank_diameter=shank_d,
            reduction_ratio=shank_d / blank_d if blank_d else 1.0,
            head_upset_ratio=head_d / blank_d if blank_d else 1.0,
            station_count=pair.process_plan.total_stations,
            blank_volume=blank_vol,
        )

    async def _run_primary(self, pair: ProductDiePair, run_index: int) -> PrimaryReasoning:
        user_msg = self._build_primary_user_msg(pair)

        async def _call() -> PrimaryReasoning:
            response = await self._claude.messages.create(
                model=settings.primary_model,
                max_tokens=4096,
                system=PR_SYSTEM,
                tools=[PR_TOOL_SCHEMA],  # type: ignore[list-item]
                tool_choice={"type": "any"},
                messages=[{"role": "user", "content": user_msg}],
            )
            input_tok = response.usage.input_tokens
            output_tok = response.usage.output_tokens
            cost = (
                input_tok * _CLAUDE_IN_COST_PER_M / 1_000_000
                + output_tok * _CLAUDE_OUT_COST_PER_M / 1_000_000
            )
            logger.info(
                "claude_primary_call",
                run_index=run_index,
                input_tokens=input_tok,
                output_tokens=output_tok,
                cost_usd=round(cost, 6),
            )

            # Extract tool_use block
            tool_block = next(
                (b for b in response.content if b.type == "tool_use"), None
            )
            if tool_block is None:
                raise ValueError(f"No tool_use block in Claude response (run {run_index})")

            data: dict[str, Any] = tool_block.input  # type: ignore[union-attr]

            # Normalise section_confidences — fill missing keys with 0.5
            default_sections = {
                "stock_selection": 0.5,
                "station_count": 0.5,
                "deformation_sequence": 0.5,
                "die_material": 0.5,
                "dimensional_compensations": 0.5,
                "potential_risks": 0.5,
            }
            sc = default_sections | (data.get("section_confidences") or {})

            return PrimaryReasoning(
                run_index=run_index,
                observable_facts=data.get("observable_facts", []),
                stock_selection_reasoning=data.get("stock_selection_reasoning", ""),
                station_count_reasoning=data.get("station_count_reasoning", ""),
                deformation_sequence_reasoning=data.get("deformation_sequence_reasoning", ""),
                die_material_reasoning=data.get("die_material_reasoning", ""),
                dimensional_compensations=data.get("dimensional_compensations", []),
                critical_parameters=data.get("critical_parameters", {}),
                potential_risks=data.get("potential_risks", []),
                section_confidences=sc,
                overall_confidence=float(data.get("overall_confidence", 0.5)),
                input_tokens=input_tok,
                output_tokens=output_tok,
                cost_usd=cost,
                prompt_version=PR_VERSION,
            )

        return await self._with_retry(_call)

    async def _run_cross_validation(
        self, pair: ProductDiePair, primary: PrimaryReasoning
    ) -> CrossValidation:
        user_msg = CV_USER_TEMPLATE.format(
            features_json=pair.part_features.model_dump_json(indent=2),
            process_plan_json=pair.process_plan.model_dump_json(indent=2),
            die_params_json=json.dumps(
                [p.model_dump() for p in pair.die_parameters], indent=2
            ),
            primary_reasoning_json=primary.model_dump_json(indent=2),
        )

        async def _call() -> CrossValidation:
            import google.generativeai as genai  # local import — optional dependency

            genai.configure(api_key=settings.google_api_key)
            model = genai.GenerativeModel(
                model_name=settings.cross_val_model,
            )

            # Run in thread since google-generativeai is synchronous
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: model.generate_content(
                    f"System: {_CV_SYSTEM_BLOCK}\n\n{user_msg}",
                    generation_config={"temperature": 0.2},  # type: ignore[arg-type]
                ),
            )

            raw_text = response.text.strip()

            # Strip markdown fences if present
            if raw_text.startswith("```"):
                raw_text = raw_text.split("```", 2)[1]
                if raw_text.startswith("json"):
                    raw_text = raw_text[4:]
                raw_text = raw_text.rsplit("```", 1)[0].strip()

            data = json.loads(raw_text)

            # Estimate token counts from character length (Gemini doesn't always return usage)
            in_tok = len(user_msg) // 4
            out_tok = len(raw_text) // 4
            cost = (
                in_tok * _GEMINI_IN_COST_PER_M / 1_000_000
                + out_tok * _GEMINI_OUT_COST_PER_M / 1_000_000
            )

            agreements: dict[str, bool] = {
                k: bool(v) for k, v in (data.get("agreements") or {}).items()
            }
            agreement_values = list(agreements.values())
            overall = (
                sum(1 for v in agreement_values if v) / len(agreement_values)
                if agreement_values
                else 0.5
            )

            logger.info(
                "gemini_cross_val_call",
                input_tokens=in_tok,
                output_tokens=out_tok,
                cost_usd=round(cost, 6),
                overall_agreement=round(overall, 3),
            )

            return CrossValidation(
                agreements=agreements,
                alternative_reasonings=data.get("alternative_reasonings") or {},
                missed_observations=data.get("missed_observations") or [],
                overall_agreement=float(data.get("overall_agreement", overall)),
                input_tokens=in_tok,
                output_tokens=out_tok,
                cost_usd=cost,
                prompt_version=CV_VERSION,
            )

        return await self._with_retry(_call)

    def _run_rule_verifier(
        self, pair: ProductDiePair, primaries: list[PrimaryReasoning]
    ) -> RuleVerification:
        return self._rules.verify(pair, primaries)

    def _aggregate(
        self,
        primaries: list[PrimaryReasoning],
        cross_val: CrossValidation,
        rules: RuleVerification,
        pair_id: str,
    ) -> ReasoningResult:
        quality = self._quality.score(primaries, cross_val, rules)

        # Pick the primary run with the highest overall_confidence
        best = max(primaries, key=lambda p: p.overall_confidence)

        # Map critical_parameters dict to list[str] for critical_features
        critical_features = list(best.critical_parameters.keys())
        if not critical_features:
            critical_features = best.observable_facts[:3]

        reasoning = PseudoReasoning(
            stock_selection=best.stock_selection_reasoning,
            station_count_reasoning=best.station_count_reasoning,
            deformation_sequence=best.deformation_sequence_reasoning,
            die_material_selection=best.die_material_reasoning,
            critical_features=critical_features,
            known_challenges=best.potential_risks[:5],
            confidence=quality.overall_confidence,
            cross_validation_agreement=cross_val.overall_agreement >= 0.6,
            claude_run_count=len(primaries),
            raw_llm_outputs=[
                p.model_dump_json() for p in primaries
            ],
        )

        total_cost = (
            sum(p.cost_usd for p in primaries) + cross_val.cost_usd
        )

        return ReasoningResult(
            pair_id=pair_id,
            reasoning=reasoning,
            quality=quality,
            primaries=primaries,
            cross_validation=cross_val,
            rule_verification=rules,
            total_cost_usd=total_cost,
            total_time_s=0.0,  # filled by caller
            prompt_versions={"primary": PR_VERSION, "cross_val": CV_VERSION},
        )


# Used in _run_cross_validation but defined here to avoid circular import
_CV_SYSTEM_BLOCK = """\
You are an independent cold-heading process engineer reviewing another
engineer's analysis of a fastener die design.
Your task: evaluate the primary analysis, note agreements and disagreements,
provide alternative reasoning where you disagree, and flag missed observations.
Return only valid JSON — no markdown, no prose outside the JSON object.
"""
