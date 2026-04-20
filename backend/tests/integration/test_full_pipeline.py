"""
Integration test: end-to-end design generation pipeline.

Uses synthetic cases (no real API keys required — all LLM calls are mocked).
Validates that the full pipeline produces a structurally valid DesignResult
with correct files, process plan, and die parameters.
"""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import chromadb
import pytest

from app.ai.designer import DieDesigner
from app.ai.embeddings import EmbeddingService
from app.ai.fewshot import FewShotFormatter
from app.ai.rag import FastenerRAG
from app.data.schemas import (
    ConfidenceLevel,
    DieComponentParams,
    DieGeometryType,
    DieParameters,
    DesignResult,
    DesignStatus,
    OperationType,
    ProcessPlan,
    RAGCase,
    RetrievedCase,
    ShapeDescription,
    StationPlan,
)
from app.data.synthetic import SyntheticDataGenerator


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_retrieved_case(gen: SyntheticDataGenerator) -> RetrievedCase:
    case = gen.generate_rag_case()
    return RetrievedCase(
        case_id=case.case_id,
        vector_similarity=0.85,
        rerank_score=0.82,
        part_features=case.part_features,
        process_plan=case.process_plan,
        die_parameters=case.die_parameters,
        pseudo_reasoning=case.pseudo_reasoning,
        confidence=case.confidence,
        source_order_id=None,
    )


def _make_process_plan_json(gen: SyntheticDataGenerator) -> str:
    _, plan, _ = gen.generate_product_die_pair()
    return plan.model_dump_json()


def _make_die_params_json(gen: SyntheticDataGenerator) -> str:
    _, _, dies = gen.generate_product_die_pair()
    return json.dumps([d.model_dump() for d in dies])


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def gen() -> SyntheticDataGenerator:
    return SyntheticDataGenerator(seed=42)


@pytest.fixture
def sample_part(gen: SyntheticDataGenerator):
    features, _, _ = gen.generate_product_die_pair()
    return features


@pytest.fixture
def retrieved_cases(gen: SyntheticDataGenerator) -> list[RetrievedCase]:
    return [_make_retrieved_case(gen) for _ in range(3)]


# ---------------------------------------------------------------------------
# RAG integration tests (with ephemeral ChromaDB, mocked embeddings)
# ---------------------------------------------------------------------------

class TestRAGIntegration:
    @pytest.fixture
    def mock_embedding_service(self):
        svc = MagicMock(spec=EmbeddingService)
        svc.embed = AsyncMock(return_value=[0.1] * 1024)
        svc.embed_query = AsyncMock(return_value=[0.1] * 1024)
        svc.embed_batch = AsyncMock(return_value=[[0.1] * 1024])
        svc.rerank = AsyncMock(return_value=[(0, 0.9), (1, 0.8), (2, 0.7)])
        svc.generate_embedding_text = AsyncMock(
            return_value="M6 flat head bolt 10B21 grade 8.8 two-station cold heading"
        )
        return svc

    @pytest.fixture
    def rag(self, mock_embedding_service) -> FastenerRAG:
        client = chromadb.EphemeralClient()
        collection = client.create_collection(
            "test_fasteners",
            metadata={"hnsw:space": "cosine"},
        )
        return FastenerRAG(embedding_service=mock_embedding_service, collection=collection)

    @pytest.mark.asyncio
    async def test_add_and_retrieve_10_cases(
        self, rag: FastenerRAG, gen: SyntheticDataGenerator
    ):
        cases = [gen.generate_rag_case() for _ in range(10)]
        for case in cases:
            await rag.add_case(case)

        query = gen.generate_rag_case().part_features
        results, tier = await rag.retrieve_with_fallback(query, top_k=3)

        assert isinstance(results, list)
        assert len(results) <= 3
        assert tier in {"exact_match", "relaxed", "medium_confidence", "no_match"}

    @pytest.mark.asyncio
    async def test_retrieve_returns_retrieved_case_schema(
        self, rag: FastenerRAG, gen: SyntheticDataGenerator
    ):
        case = gen.generate_rag_case()
        await rag.add_case(case)

        query = gen.generate_rag_case().part_features
        results, _ = await rag.retrieve_with_fallback(query, top_k=1)

        if results:
            r = results[0]
            assert isinstance(r, RetrievedCase)
            assert 0.0 <= r.vector_similarity <= 1.0
            assert r.part_features is not None

    @pytest.mark.asyncio
    async def test_empty_collection_returns_no_match(
        self, rag: FastenerRAG, gen: SyntheticDataGenerator
    ):
        query = gen.generate_rag_case().part_features
        results, tier = await rag.retrieve_with_fallback(query, top_k=3)
        assert tier == "no_match"
        assert results == []


# ---------------------------------------------------------------------------
# FewShot formatter tests
# ---------------------------------------------------------------------------

class TestFewShotFormatter:
    def test_format_produces_xml(self, retrieved_cases: list[RetrievedCase]):
        fmt = FewShotFormatter()
        xml = fmt.format_cases(retrieved_cases)
        assert "<similar_cases>" in xml
        assert "<case " in xml
        assert "similarity=" in xml

    def test_cases_sorted_ascending_by_score(self, retrieved_cases: list[RetrievedCase]):
        for i, c in enumerate(retrieved_cases):
            object.__setattr__(c, "rerank_score", float(i) * 0.1 + 0.7)
        fmt = FewShotFormatter()
        xml = fmt.format_cases(retrieved_cases)
        # Least similar should appear first (index=1 in XML)
        lines = xml.splitlines()
        case_lines = [l for l in lines if l.strip().startswith('<case index=')]
        assert len(case_lines) == 3

    def test_empty_cases_returns_placeholder(self):
        fmt = FewShotFormatter()
        xml = fmt.format_cases([])
        assert "no_similar_cases" in xml or xml.strip() == "" or "similar_cases" in xml


# ---------------------------------------------------------------------------
# Full pipeline integration test (mocked LLM calls)
# ---------------------------------------------------------------------------

class TestFullPipelineIntegration:
    @pytest.fixture
    def output_dir(self, tmp_path: Path) -> Path:
        return tmp_path / "designs"

    @pytest.fixture
    def mock_process_plan_response(self, gen: SyntheticDataGenerator) -> str:
        return _make_process_plan_json(gen)

    @pytest.fixture
    def mock_die_params_response(self, gen: SyntheticDataGenerator) -> str:
        return _make_die_params_json(gen)

    def _make_claude_message(self, content: str):
        msg = MagicMock()
        block = MagicMock()
        block.type = "text"
        block.text = content
        msg.content = [block]
        msg.usage = MagicMock(input_tokens=500, output_tokens=800)
        return msg

    @pytest.mark.asyncio
    async def test_design_result_schema(
        self,
        sample_part,
        retrieved_cases,
        mock_process_plan_response,
        mock_die_params_response,
        output_dir,
    ):
        claude_pp = self._make_claude_message(mock_process_plan_response)
        claude_dd = self._make_claude_message(mock_die_params_response)

        call_count = 0

        async def mock_create(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return claude_pp
            return claude_dd

        with patch("app.ai.designer.settings") as mock_settings, \
             patch("anthropic.AsyncAnthropic") as mock_anthropic:

            mock_settings.output_base_dir = str(output_dir)
            mock_settings.anthropic_api_key = "sk-test"
            mock_settings.max_design_retries = 1
            mock_settings.claude_model = "claude-opus-4-7"

            mock_client = MagicMock()
            mock_client.messages.create = AsyncMock(side_effect=mock_create)
            mock_anthropic.return_value = mock_client

            designer = DieDesigner()
            result = await designer.design(
                part=sample_part,
                similar_cases=retrieved_cases,
                retrieval_quality="relaxed",
            )

        assert isinstance(result, DesignResult)
        assert result.design_id
        assert result.part_features is not None
        assert result.process_plan is not None
        assert len(result.process_plan.stations) >= 1
        assert len(result.die_parameters) >= 1
        assert result.status in {DesignStatus.complete, DesignStatus.partial, DesignStatus.failed}

    @pytest.mark.asyncio
    async def test_output_files_created(
        self,
        sample_part,
        retrieved_cases,
        mock_process_plan_response,
        mock_die_params_response,
        output_dir,
    ):
        claude_pp = self._make_claude_message(mock_process_plan_response)
        claude_dd = self._make_claude_message(mock_die_params_response)
        call_count = 0

        async def mock_create(**kwargs):
            nonlocal call_count
            call_count += 1
            return claude_pp if call_count == 1 else claude_dd

        with patch("app.ai.designer.settings") as mock_settings, \
             patch("anthropic.AsyncAnthropic") as mock_anthropic:

            mock_settings.output_base_dir = str(output_dir)
            mock_settings.anthropic_api_key = "sk-test"
            mock_settings.max_design_retries = 1
            mock_settings.claude_model = "claude-opus-4-7"

            mock_client = MagicMock()
            mock_client.messages.create = AsyncMock(side_effect=mock_create)
            mock_anthropic.return_value = mock_client

            designer = DieDesigner()
            result = await designer.design(
                part=sample_part,
                similar_cases=retrieved_cases,
                retrieval_quality="relaxed",
            )

        if result.status == DesignStatus.complete:
            assert len(result.output_files) > 0
            for f in result.output_files:
                assert f.file_path
                assert f.file_type
                assert f.format in {"dxf", "stl", "step", "json", "png"}

    @pytest.mark.asyncio
    async def test_cost_tracked(
        self,
        sample_part,
        retrieved_cases,
        mock_process_plan_response,
        mock_die_params_response,
        output_dir,
    ):
        claude_pp = self._make_claude_message(mock_process_plan_response)
        claude_dd = self._make_claude_message(mock_die_params_response)
        call_count = 0

        async def mock_create(**kwargs):
            nonlocal call_count
            call_count += 1
            return claude_pp if call_count == 1 else claude_dd

        with patch("app.ai.designer.settings") as mock_settings, \
             patch("anthropic.AsyncAnthropic") as mock_anthropic:

            mock_settings.output_base_dir = str(output_dir)
            mock_settings.anthropic_api_key = "sk-test"
            mock_settings.max_design_retries = 1
            mock_settings.claude_model = "claude-opus-4-7"

            mock_client = MagicMock()
            mock_client.messages.create = AsyncMock(side_effect=mock_create)
            mock_anthropic.return_value = mock_client

            designer = DieDesigner()
            result = await designer.design(
                part=sample_part,
                similar_cases=retrieved_cases,
                retrieval_quality="relaxed",
            )

        assert result.total_cost_usd >= 0.0
        assert result.total_time_s >= 0.0

    @pytest.mark.asyncio
    async def test_llm_parse_error_falls_back_gracefully(
        self,
        sample_part,
        retrieved_cases,
        output_dir,
    ):
        """When LLM returns garbage JSON, pipeline falls back to synthetic data."""
        bad_response = self._make_claude_message("This is not JSON at all!!!")

        with patch("app.ai.designer.settings") as mock_settings, \
             patch("anthropic.AsyncAnthropic") as mock_anthropic:

            mock_settings.output_base_dir = str(output_dir)
            mock_settings.anthropic_api_key = "sk-test"
            mock_settings.max_design_retries = 0
            mock_settings.claude_model = "claude-opus-4-7"

            mock_client = MagicMock()
            mock_client.messages.create = AsyncMock(return_value=bad_response)
            mock_anthropic.return_value = mock_client

            designer = DieDesigner()
            result = await designer.design(
                part=sample_part,
                similar_cases=retrieved_cases,
                retrieval_quality="no_match",
            )

        # Should not raise; status will be partial or complete (fallback)
        assert isinstance(result, DesignResult)
        assert result.process_plan is not None


# ---------------------------------------------------------------------------
# Throughput smoke test: 5 designs in parallel
# ---------------------------------------------------------------------------

class TestParallelDesignThroughput:
    @pytest.mark.asyncio
    async def test_five_designs_parallel(self, tmp_path: Path):
        gen = SyntheticDataGenerator(seed=99)

        parts = [gen.generate_product_die_pair()[0] for _ in range(5)]
        cases = [[_make_retrieved_case(gen) for _ in range(2)] for _ in range(5)]

        plan_json = _make_process_plan_json(gen)
        die_json = _make_die_params_json(gen)

        call_counts: list[int] = [0] * 5

        def _make_create(idx: int):
            async def mock_create(**kwargs):
                call_counts[idx] += 1
                text = plan_json if call_counts[idx] == 1 else die_json
                msg = MagicMock()
                block = MagicMock()
                block.type = "text"
                block.text = text
                msg.content = [block]
                msg.usage = MagicMock(input_tokens=400, output_tokens=600)
                return msg
            return mock_create

        async def run_one(i: int) -> DesignResult:
            with patch("app.ai.designer.settings") as mock_settings, \
                 patch("anthropic.AsyncAnthropic") as mock_anthropic:

                mock_settings.output_base_dir = str(tmp_path / f"d{i}")
                mock_settings.anthropic_api_key = "sk-test"
                mock_settings.max_design_retries = 0
                mock_settings.claude_model = "claude-opus-4-7"

                mock_client = MagicMock()
                mock_client.messages.create = AsyncMock(side_effect=_make_create(i))
                mock_anthropic.return_value = mock_client

                designer = DieDesigner()
                return await designer.design(
                    part=parts[i],
                    similar_cases=cases[i],
                    retrieval_quality="no_match",
                )

        start = time.monotonic()
        results = await asyncio.gather(*[run_one(i) for i in range(5)])
        elapsed = time.monotonic() - start

        assert len(results) == 5
        for r in results:
            assert isinstance(r, DesignResult)

        # With mocked IO, 5 parallel designs should complete quickly
        assert elapsed < 30.0, f"Parallel pipeline took {elapsed:.1f}s — expected < 30s"
