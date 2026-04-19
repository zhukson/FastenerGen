"""
Raw data ingestion pipeline.

Processes raw factory data (DWG + PDF pairs) from object storage:
  1. Parse product drawing (ezdxf / Claude Vision)
  2. Parse die drawings (ezdxf)
  3. Run pseudo-reasoning pipeline
  4. Validate and score confidence
  5. Store high-confidence cases in ChromaDB

Implemented in Session 5.
"""

from pathlib import Path

from app.data.schemas import RAGCase


async def ingest_order(order_id: str, data_dir: Path) -> RAGCase | None:
    """
    Ingest a single order's drawing data and index into RAG store.

    Returns the created RAGCase if confidence is high, None otherwise.
    """
    raise NotImplementedError("Implemented in Session 5")


async def batch_ingest(data_dir: Path) -> dict[str, int]:
    """
    Batch ingest all orders from a data directory.

    Returns summary: {'total': N, 'indexed': M, 'skipped': K, 'errors': E}
    """
    raise NotImplementedError("Implemented in Session 5")
