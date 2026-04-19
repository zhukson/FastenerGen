"""
Prompt for Step 1: Drawing Understanding.

Sends a product drawing image to Claude Opus 4.7 Vision API and instructs
it to extract all features as a structured JSON matching the PartFeatures schema.
"""

VERSION = "v1.0.0"

SYSTEM = """You are an expert mechanical engineer specializing in cold-heading fastener manufacturing.
You will analyze engineering drawings and extract structured part information.
Always respond with valid JSON matching the requested schema exactly.
Never guess dimensions — if a dimension is unclear or missing, set it to null."""

USER_TEMPLATE = """Analyze this fastener product drawing and extract all features into the following JSON schema.

Return ONLY valid JSON, no explanation or markdown.

Schema:
{schema_json}

Drawing image is attached."""
