"""
Voyage AI embedding service.

Wraps the Voyage-3-large embedding model for semantic search over
engineering case data. Also handles embedding text generation via
Claude Haiku for structured PartFeatures → text conversion.

Implemented in Session 3.
"""

from app.data.schemas import PartFeatures


class EmbeddingService:
    """Voyage-3-large embeddings for engineering case retrieval."""

    MODEL = "voyage-3-large"

    async def embed(self, text: str) -> list[float]:
        """Embed a single text string."""
        raise NotImplementedError("Implemented in Session 3")

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of texts efficiently."""
        raise NotImplementedError("Implemented in Session 3")

    async def features_to_embedding_text(self, features: PartFeatures) -> str:
        """
        Convert PartFeatures to a dense embedding text string via Claude Haiku.

        The embedding text captures key geometric and material properties in
        a format optimized for semantic similarity search.
        """
        raise NotImplementedError("Implemented in Session 3")
