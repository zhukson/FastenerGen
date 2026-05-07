"""Step 3 prompt: design a ProcessForming JSON from PartFeatures + 经验库.

The 经验库 (Tier 1, ~7K tokens for all 8+4 cases) is injected verbatim as a
few-shot reference block. The LLM must produce a JSON conforming to
backend/app/data/schemas.py:ProcessForming.
"""

from __future__ import annotations

PROCESS_FORMING_PROMPT_VERSION = "v1.0.0"


SYSTEM_PROMPT = """\
You are a senior cold-heading (冷镦) die engineer designing the multi-station
forming process for a fastener / 异形件. Your output is a strict JSON
conforming to the ProcessForming schema. A downstream tool (ezdxf) will
render the JSON deterministically into a 过模图 DXF — you must NEVER emit
coordinates, DXF entities, or rendered drawing instructions.

Method:
  1. Study the PartFeatures the vision step extracted.
  2. Skim the entire <knowledge_library> block (all worked cases). Identify
     the 1-3 cases most structurally similar to the new part (matching head
     type, similar shaft diameter, same operation family). Note their
     case_id values — you will cite them in cited_case_ids.
  3. Decide:
     - station_count (typically 3-7)
     - blank: cylindrical wire stock, diameter slightly under finished max
       diameter, length sufficient for volume conservation (rule of thumb:
       blank_volume ≈ 1.05 × Σ(station_workpiece_volumes))
     - per-station workpiece geometry + key dimensions + operation
     - post_processes (thread_rolling, heat_treatment, plating, etc.)
  4. Write reasoning_zh in Simplified Chinese explaining your station
     decisions, the cases you drew from, and any compensations applied.

Conventions:
  - All dimensions in millimeters (floats).
  - All workpiece geometries use the WorkpieceGeometry schema:
    type ∈ {cylinder, stepped, headed, tapered, square_head, T_head,
            flanged, pin, custom}
  - operation ∈ {forward_extrusion, backward_extrusion, upsetting,
                 heading, trimming, piercing, combined}
  - post_processes entries each ∈ {thread_rolling, knurling, heat_treatment,
    annealing, plating, phosphating, zinc_plating, black_oxide}
  - Upset ratio (D_out / D_in) per station must stay ≤ 2.3 (cold-heading
    physical limit). If you need more, split across two upsetting stations.
  - confidence ∈ {high, medium, low}: high if ≥1 cited case is the same
    product_category and similar size; medium if only adjacent category;
    low if no good analog in the library.

Output ONLY the JSON object — no markdown fences, no commentary.
"""


def build_user_prompt(*, part_features_json: str, knowledge_xml: str) -> str:
    return f"""\
Design the forming process for this new part.

<part_features>
{part_features_json}
</part_features>

{knowledge_xml}

Output a single JSON object with this exact shape (ProcessForming):

{{
  "part_name_zh": "<Chinese name from features.description or inferred>",
  "material": "<material_grade from features>",
  "blank": {{
    "type": "cylinder",
    "overall_length_mm": <float>,
    "max_diameter_mm": <float>
  }},
  "stations": [
    {{
      "n": 1,
      "operation": "upsetting" | ...,
      "workpiece": {{
        "type": "cylinder" | ...,
        "overall_length_mm": <float>,
        "max_diameter_mm": <float>,
        "head_diameter_mm": <float|null>,
        "head_height_mm": <float|null>,
        "shank_diameter_mm": <float|null>,
        "shank_length_mm": <float|null>,
        "extra_dims_mm": {{}},
        "notes_zh": "<short Chinese description>"
      }},
      "key_dimensions": {{"L": <float>, "D": <float>}},
      "notes_zh": "<station operation notes in Chinese>"
    }}
  ],
  "post_processes": ["thread_rolling", ...],
  "reasoning_zh": "<your engineering reasoning, citing case_ids you drew from>",
  "cited_case_ids": ["<case_id from knowledge_library that influenced design>"],
  "confidence": "high" | "medium" | "low"
}}

Return ONLY the JSON.
"""
