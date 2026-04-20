"""
Voyage AI embedding service.

EmbeddingService wraps:
  - Voyage-3-large for semantic embeddings
  - Claude Haiku 4.5 for embedding text generation from PartFeatures
  - Redis for caching (key = sha256(text))

Voyage SDK is synchronous; wrapped in asyncio.to_thread for async callers.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
from typing import Any

import anthropic
import structlog

from app.core.config import settings
from app.data.schemas import PartFeatures

logger = structlog.get_logger()

_HAIKU_IN_COST_PER_M = 0.8   # USD per million input tokens (Haiku 4.5)
_HAIKU_OUT_COST_PER_M = 4.0  # USD per million output tokens

_EMBED_TEXT_SYSTEM = """\
You are a technical search specialist. Convert part features into a dense 2-3 sentence
natural language description optimised for semantic similarity search.
Emphasise: part type, thread spec, head geometry, material/grade, key dimensions, process characteristics.
Do NOT mention part numbers. Return only the description text — no labels, no JSON.
"""

_EMBED_TEXT_USER = """\
Generate a search-optimised description for this fastener:
{features_json}
"""


class EmbeddingService:
    """Voyage-3-large embeddings with Redis caching and Claude Haiku text generation."""

    VOYAGE_MODEL = "voyage-3-large"
    RERANK_MODEL = "rerank-2"

    def __init__(
        self,
        redis_client: Any | None = None,
        anthropic_client: anthropic.AsyncAnthropic | None = None,
    ) -> None:
        self._redis = redis_client
        self._claude = anthropic_client or anthropic.AsyncAnthropic(
            api_key=settings.anthropic_api_key
        )
        self._voyage: Any | None = None

    def _get_voyage(self) -> Any:
        if self._voyage is None:
            import voyageai  # optional dep — not needed in test env

            self._voyage = voyageai.Client(api_key=settings.voyage_api_key)
        return self._voyage

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def embed(self, text: str) -> list[float]:
        """Embed a single text string. Results cached in Redis by text hash."""
        cache_key = f"emb:{hashlib.sha256(text.encode()).hexdigest()}"
        if self._redis:
            cached = await self._redis.get(cache_key)
            if cached:
                return json.loads(cached)

        vo = self._get_voyage()
        result = await asyncio.to_thread(
            vo.embed, [text], model=self.VOYAGE_MODEL, input_type="document"
        )
        embedding: list[float] = result.embeddings[0]

        if self._redis:
            await self._redis.set(cache_key, json.dumps(embedding), ex=86400 * 30)

        return embedding

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Batch embed. Voyage handles batching natively; rate-limited to 100 texts/call."""
        if not texts:
            return []

        # Split into chunks of 100 (Voyage rate limit per call)
        chunk_size = 100
        all_embeddings: list[list[float]] = []
        vo = self._get_voyage()

        for i in range(0, len(texts), chunk_size):
            chunk = texts[i : i + chunk_size]
            result = await asyncio.to_thread(
                vo.embed, chunk, model=self.VOYAGE_MODEL, input_type="document"
            )
            all_embeddings.extend(result.embeddings)

        return all_embeddings

    async def embed_query(self, text: str) -> list[float]:
        """Embed a query string (uses query input_type for better retrieval)."""
        vo = self._get_voyage()
        result = await asyncio.to_thread(
            vo.embed, [text], model=self.VOYAGE_MODEL, input_type="query"
        )
        return result.embeddings[0]

    async def rerank(
        self, query: str, documents: list[str], top_k: int = 5
    ) -> list[tuple[int, float]]:
        """
        Rerank documents using Voyage rerank-2.

        Returns list of (original_index, score) sorted by score descending.
        """
        if not documents:
            return []

        vo = self._get_voyage()
        result = await asyncio.to_thread(
            vo.rerank, query, documents, model=self.RERANK_MODEL, top_k=min(top_k, len(documents))
        )
        return [(r.index, r.relevance_score) for r in result.results]

    async def generate_embedding_text(self, features: PartFeatures) -> str:
        """
        Use Claude Haiku to generate a 2-3 sentence description optimised for
        semantic search. Cached by feature hash so same features → same text.
        """
        features_json = features.model_dump_json()
        cache_key = f"embtxt:{hashlib.sha256(features_json.encode()).hexdigest()}"

        if self._redis:
            cached = await self._redis.get(cache_key)
            if cached:
                return cached.decode() if isinstance(cached, bytes) else cached

        response = await self._claude.messages.create(
            model=settings.aux_model,
            max_tokens=256,
            system=_EMBED_TEXT_SYSTEM,
            messages=[{"role": "user", "content": _EMBED_TEXT_USER.format(features_json=features_json)}],
        )
        text = response.content[0].text.strip()  # type: ignore[union-attr]

        input_tok = response.usage.input_tokens
        output_tok = response.usage.output_tokens
        cost = input_tok * _HAIKU_IN_COST_PER_M / 1_000_000 + output_tok * _HAIKU_OUT_COST_PER_M / 1_000_000
        logger.debug("embedding_text_generated", chars=len(text), cost_usd=round(cost, 6))

        if self._redis:
            await self._redis.set(cache_key, text, ex=86400 * 30)

        return text
