"""
Multi-modal drawing understanding via Claude Opus 4.7 Vision API.

Step 1 of the pipeline: reads a product drawing (image/PDF) and extracts
all features as a structured PartFeatures JSON. Runs 3× for self-consistency.

Implemented in Session 2.
"""

from pathlib import Path

from app.data.schemas import PartFeatures


class DrawingReader:
    """Extract structured part features from a product drawing using LLM vision."""

    PROMPT_VERSION = "v1.0.0"

    async def read(self, drawing_path: Path) -> PartFeatures:
        """
        Extract PartFeatures from a product drawing.

        Encodes the drawing as base64, sends to Claude Opus 4.7 vision API,
        and parses the response into a validated PartFeatures model.
        Runs 3× for self-consistency; returns the majority-vote result.
        """
        raise NotImplementedError("Implemented in Session 2")

    async def _encode_image(self, path: Path) -> str:
        """Encode a drawing file to base64 for the Vision API."""
        raise NotImplementedError("Implemented in Session 2")
