"""Prompt for extracting a CaseRecord from a drawing PNG.

Used by scripts/extract_case_from_drawing.py against:
  - 异形件过模图 DWG -> DXF -> PNG  (kind="case_dwg")
  - 标准件全套图 PDF -> PNG          (kind="standard_pdf")

The LLM produces a *draft* JSON conforming to backend/app/data/schemas.py:CaseRecord.
Drafts are saved with extracted_by="llm_draft" and require human review before
being used as Tier 1 few-shot examples.
"""

from __future__ import annotations

EXTRACTION_PROMPT_VERSION = "v1.0.0"


SYSTEM_PROMPT = """\
You are a senior cold-heading (冷镦) die engineer assisting in building
FastenerGPT's 经验库 (experience library). You are looking at one engineering
drawing and must distill it into a strict JSON record.

Two drawing kinds:

  1. 过模图 (process forming drawing) — shows the multi-station progression
     of intermediate workpiece shapes for a special-shape (异形件) fastener.
     The drawing has N stations laid out left-to-right; each station shows the
     workpiece shape AT THAT STATION (output) with key dimensions. Read each
     station's geometry, dimensions, and infer the operation type (cutoff,
     upsetting, forward/backward extrusion, heading, trimming, piercing,
     combined). The blank is usually the leftmost shape (often a plain
     cylinder) labeled 下料 / 原料.

  2. Standard part full drawing (DIN912, DIN933, etc.) — shows the FINAL
     product only (no station progression). For these, infer a plausible
     forming process from textbook practice for that standard:
       - DIN912 socket cap: typically 4-5 stations
         (cutoff -> upset -> head form -> socket pierce -> extrude shank)
       - DIN933 hex bolt: typically 3-4 stations
         (cutoff -> upset -> hex head form -> trim/extrude)
     Mark confidence accordingly (medium for inferred process).

Conventions (must follow):
  - All dimensions in millimeters (mm). Use floats.
  - Material codes: keep the Chinese designations as-is (106S, 105S, YT105S,
    10B21, etc.). Do NOT translate.
  - All natural-language fields ending in `_zh` must be in Simplified Chinese.
  - Use empty string "" or null for non-numeric fields when not visible.
  - For numeric workpiece dimensions (overall_length_mm, max_diameter_mm,
    head_*_mm, shank_*_mm): make a best-effort engineering estimate from what
    you CAN see (e.g., for a socket cap screw: blank wire near shank dia, blank
    length ~5× shank length is typical). If you truly cannot estimate, use
    0.0 as a placeholder — humans will correct in review. Never invent
    fictitious precise dimensions like 14.7 when you have no basis.
  - EVERY workpiece (blank + each station) must have non-null
    overall_length_mm and max_diameter_mm fields, even if the value is 0.0.
  - station_count must equal len(stations).
  - operation must be one of: forward_extrusion, backward_extrusion, upsetting,
    heading, trimming, piercing, combined.
  - workpiece.type must be one of: cylinder, stepped, headed, tapered,
    square_head, T_head, flanged, pin, custom.
  - post_processes entries must each be one of (omit any that don't apply):
    thread_rolling, knurling, heat_treatment, annealing, plating,
    phosphating, zinc_plating, black_oxide. Do NOT use compound strings
    like "heat_treatment_8.8" or invent new categories like "chamfering" /
    "surface_treatment" — express those in `reasoning_zh` instead.
  - extracted_by must be "llm_draft".
  - extraction_confidence: high if every field came directly from the drawing;
    medium if some inference; low if the drawing is unclear.

Output ONLY the JSON object — no markdown fences, no commentary.
"""


def build_user_prompt(
    *,
    case_id: str,
    source_kind: str,
    source_file: str,
    suggested_category: str | None = None,
    suggested_standard_ref: str | None = None,
) -> str:
    """Build the per-drawing user prompt.

    Args mirror the CaseRecord fields the caller has already determined from
    the filename, so the LLM doesn't have to guess them.
    """
    hints: list[str] = [
        f"case_id: {case_id}",
        f"source_kind: {source_kind}",
        f"source_file: {source_file}",
    ]
    if suggested_category:
        hints.append(f"product_category (suggested from filename): {suggested_category}")
    if suggested_standard_ref:
        hints.append(f"standard_ref (suggested from filename): {suggested_standard_ref}")

    hint_block = "\n".join(f"  - {h}" for h in hints)

    return f"""\
Extract a CaseRecord from this drawing.

Pre-determined fields (use these verbatim):
{hint_block}

Output a single JSON object with this exact shape (CaseRecord):

{{
  "case_id": "...",
  "source_kind": "case_dwg" | "standard_pdf",
  "source_file": "...",
  "product_name_zh": "...",
  "product_category": "...",
  "standard_ref": "DIN912" | "DIN933" | null,
  "material": "...",
  "part_features": {{
    "part_number": "<from drawing title block; if absent, reuse case_id>",
    "description": "<short English description, e.g. 'socket cap screw, DIN912'>",
    "overall_length": <float, mm — total length of finished part>,
    "material_grade": "<as on drawing, e.g. '10B21', '106S'>",
    "strength_grade": "<e.g. '8.8', '10.9', or empty string if not shown>",
    "head": {{ "type": "<flat|hex|button|pan|socket|truss|flange|oval>", "diameter": <float>, "height": <float>, ... }} | null,
    "shank": {{ "diameter": <float>, "length": <float> }} | null,
    "thread": {{ "spec": "<e.g. 'M16×2.0'>", "nominal_diameter": <float>, "pitch": <float>, "length": <float>, "thread_class": "6g", "thread_type": "metric", "is_full_length": false }} | null,
    "tail": null,
    "hardness_min_hv": <float|null>,
    "hardness_max_hv": <float|null>,
    "surface_treatment": "<e.g. 'zinc_plating_8um' or null>",
    "standard": "<e.g. 'DIN 912' or null>",
    "tolerance_class": null,
    "drawing_scale": "<e.g. '1:1' or null>",
    "notes": []
  }},
  "process_forming": {{
    "part_name_zh": "...",
    "material": "...",
    "blank": {{
      "type": "cylinder",
      "overall_length_mm": 0.0,
      "max_diameter_mm": 0.0,
      ...
    }},
    "stations": [
      {{
        "n": 1,
        "operation": "...",
        "workpiece": {{ ... WorkpieceGeometry ... }},
        "key_dimensions": {{"L": 0.0, "D": 0.0}},
        "notes_zh": "..."
      }}
    ],
    "post_processes": ["thread_rolling"],
    "reasoning_zh": "...",
    "cited_case_ids": [],
    "confidence": "high" | "medium" | "low"
  }},
  "extraction_confidence": "high" | "medium" | "low",
  "extracted_by": "llm_draft",
  "notes_zh": null
}}

For PartFeatures, fill the sub-objects you can read from the drawing
(head, shank, thread, tail, plus the top-level fields). Refer to
backend/app/data/schemas.py:PartFeatures for exact field names — do not
invent fields. If a sub-object cannot be determined, omit it (the schema
allows None for optional sub-blocks).

Return ONLY the JSON.
"""
