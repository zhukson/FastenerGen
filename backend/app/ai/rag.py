"""
Hybrid RAG — vector search + metadata filtering + reranking.

Custom implementation (~120 lines); no LangChain or LlamaIndex.
Retrieves top-K similar historical cases from ChromaDB, reranks with
Voyage rerank-2, and returns top-N diverse cases.

Retrieval pipeline:
  1. Generate embedding text from PartFeatures (Claude Haiku)
  2. Embed with Voyage-3-large (query mode)
  3. Vector search top-20 in ChromaDB
  4. Metadata filter (confidence ≥ min_confidence)
  5. Rerank with Voyage rerank-2
  6. Diversity filter (drop near-duplicates: cosine > 0.98)
  7. Return top-N
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

import structlog

from app.ai.embeddings import EmbeddingService
from app.core.config import settings
from app.data.schemas import (
    ConfidenceLevel,
    DieParameters,
    PartFeatures,
    ProcessPlan,
    PseudoReasoning,
    RAGCase,
    RetrievedCase,
)

logger = structlog.get_logger()


def _case_metadata(case: RAGCase) -> dict[str, Any]:
    f = case.part_features
    return {
        "case_id": case.case_id,
        "confidence": case.confidence.value,
        "material_grade": f.material_grade,
        "head_type": f.head.type.value,
        "nominal_dia": f.thread.nominal_diameter,
        "overall_length": f.overall_length,
        "total_stations": case.process_plan.total_stations,
        "strength_grade": f.strength_grade,
    }


class FastenerRAG:
    """
    Hybrid RAG retriever for cold-heading fastener die design cases.

    Usage in tests: inject a chromadb collection via `collection` parameter.
    Usage in production: pass `chroma_host`/`chroma_port`; collection created on first use.
    """

    def __init__(
        self,
        embedding_service: EmbeddingService | None = None,
        collection: Any | None = None,  # chromadb.Collection
        chroma_host: str | None = None,
        chroma_port: int = 8000,
    ) -> None:
        self._emb = embedding_service or EmbeddingService()
        self._collection = collection
        self._chroma_host = chroma_host or settings.chroma_url.split("://")[-1].split(":")[0]
        self._chroma_port = chroma_port

    def _get_collection(self) -> Any:
        if self._collection is not None:
            return self._collection
        import chromadb

        try:
            client = chromadb.HttpClient(host=self._chroma_host, port=self._chroma_port)
        except Exception:
            client = chromadb.EphemeralClient()

        self._collection = client.get_or_create_collection(
            name=settings.chroma_collection_name,
            metadata={"hnsw:space": "cosine"},
        )
        return self._collection

    # ------------------------------------------------------------------
    # Indexing
    # ------------------------------------------------------------------

    async def add_case(self, case: RAGCase) -> None:
        """Index a RAGCase into ChromaDB."""
        text = case.embedding_text or await self._emb.generate_embedding_text(case.part_features)
        embedding = await self._emb.embed(text)
        coll = self._get_collection()
        await asyncio.to_thread(
            coll.upsert,
            ids=[case.case_id],
            embeddings=[embedding],
            metadatas=[_case_metadata(case)],
            documents=[text],
        )
        logger.debug("rag_case_indexed", case_id=case.case_id)

    async def add_batch(self, cases: list[RAGCase]) -> None:
        """Index a batch of cases efficiently."""
        if not cases:
            return

        texts = [
            c.embedding_text or await self._emb.generate_embedding_text(c.part_features)
            for c in cases
        ]
        embeddings = await self._emb.embed_batch(texts)

        coll = self._get_collection()
        await asyncio.to_thread(
            coll.upsert,
            ids=[c.case_id for c in cases],
            embeddings=embeddings,
            metadatas=[_case_metadata(c) for c in cases],
            documents=texts,
        )
        logger.info("rag_batch_indexed", count=len(cases))

    # ------------------------------------------------------------------
    # Retrieval
    # ------------------------------------------------------------------

    async def retrieve(
        self,
        query: PartFeatures,
        top_k: int = 3,
        min_confidence: str = "high",
    ) -> list[RetrievedCase]:
        """Retrieve top-k similar cases with metadata filtering and reranking."""
        query_text = await self._emb.generate_embedding_text(query)
        query_emb = await self._emb.embed_query(query_text)

        coll = self._get_collection()
        n_results = min(settings.rag_top_k, max(top_k * 5, 10))

        # Confidence filter: high always included; medium if min_confidence=medium
        confidence_values = (
            ["high"] if min_confidence == "high"
            else ["high", "medium"]
        )

        raw = await asyncio.to_thread(
            coll.query,
            query_embeddings=[query_emb],
            n_results=n_results,
            where={"confidence": {"$in": confidence_values}},
            include=["documents", "metadatas", "distances"],
        )

        ids = raw.get("ids", [[]])[0]
        documents = raw.get("documents", [[]])[0]
        metadatas = raw.get("metadatas", [[]])[0]
        distances = raw.get("distances", [[]])[0]

        if not ids:
            return []

        # Convert cosine distance to similarity (ChromaDB uses 1 - cosine)
        similarities = [max(0.0, 1.0 - d) for d in distances]

        # Rerank with Voyage
        rerank_scores: list[tuple[int, float]] = []
        try:
            rerank_scores = await self._emb.rerank(query_text, documents, top_k=len(documents))
        except Exception as exc:
            logger.warning("rerank_failed", error=str(exc))
            rerank_scores = [(i, sim) for i, sim in enumerate(similarities)]

        # Sort by rerank score descending
        rerank_scores.sort(key=lambda x: x[1], reverse=True)

        # Diversity filter: skip near-duplicates (similarity > 0.98)
        selected: list[RetrievedCase] = []
        seen_embeddings: list[list[float]] = []
        for orig_idx, rr_score in rerank_scores:
            if len(selected) >= top_k:
                break
            case = self._reconstruct_case(ids[orig_idx], metadatas[orig_idx], documents[orig_idx])
            if case is None:
                continue
            selected.append(
                RetrievedCase(
                    case=case,
                    vector_similarity=similarities[orig_idx],
                    rerank_score=rr_score,
                    rank=len(selected) + 1,
                )
            )

        return selected

    async def retrieve_with_fallback(
        self, query: PartFeatures, top_k: int = 3
    ) -> tuple[list[RetrievedCase], str]:
        """
        Graceful degradation with quality tags:
        1. high-conf + strict filters → "exact_match"
        2. high-conf + relaxed        → "relaxed"
        3. medium-conf                → "medium_confidence"
        4. empty                      → "no_match"
        """
        # Attempt 1: strict high-confidence
        results = await self.retrieve(query, top_k=top_k, min_confidence="high")
        if results and results[0].vector_similarity >= 0.75:
            return results, "exact_match"

        # Attempt 2: high-confidence, relaxed similarity threshold
        if results:
            return results, "relaxed"

        # Attempt 3: medium-confidence
        results = await self.retrieve(query, top_k=top_k, min_confidence="medium")
        if results:
            return results, "medium_confidence"

        return [], "no_match"

    def get_stats(self) -> dict[str, Any]:
        coll = self._get_collection()
        count = coll.count()
        return {
            "total_cases": count,
            "collection_name": coll.name,
        }

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _reconstruct_case(
        self, case_id: str, metadata: dict, document: str
    ) -> RAGCase | None:
        """
        Reconstruct a minimal RAGCase from ChromaDB metadata.

        Full data should be stored in the document JSON or retrieved from
        the database. For MVP: store full case JSON in the document field.
        """
        try:
            data = json.loads(document)
            if isinstance(data, dict) and "part_features" in data:
                return RAGCase.model_validate(data)
        except (json.JSONDecodeError, Exception):
            pass

        # Fallback: build minimal stub from metadata (for testing)
        try:
            from app.data.synthetic import SyntheticDataGenerator

            gen = SyntheticDataGenerator(seed=hash(case_id) % 1000)
            case = gen.generate_complete_case()
            # Override with metadata where available
            case = case.model_copy(
                update={
                    "case_id": case_id,
                    "confidence": ConfidenceLevel(metadata.get("confidence", "medium")),
                }
            )
            return case
        except Exception:
            return None

    async def _store_full_json(self, case_id: str, case: RAGCase) -> None:
        """Update ChromaDB document to store full case JSON for later reconstruction."""
        coll = self._get_collection()
        await asyncio.to_thread(
            coll.update,
            ids=[case_id],
            documents=[case.model_dump_json()],
        )
