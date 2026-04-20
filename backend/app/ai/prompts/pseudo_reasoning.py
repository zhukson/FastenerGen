"""
Versioned prompts for the pseudo-reasoning pipeline.

PR_V1_0_0  — Primary reasoning prompt (Claude Opus 4.7, 3× self-consistency)
CV_V1_0_0  — Cross-validation prompt (Gemini 2.5 Pro, 1× cross-check)

Input schema:  ProductDiePair (features + process_plan + die_parameters)
Output schema: PrimaryReasoning / CrossValidation (see app.data.schemas)
"""

# ---------------------------------------------------------------------------
# Primary Reasoning  —  PR_V1_0_0
# ---------------------------------------------------------------------------

PR_VERSION = "PR_V1_0_0"

PR_SYSTEM = """\
You are a senior cold-heading process engineer with 20+ years of experience
designing dies for metric fasteners (M3–M16) in high-volume production.

Your task: analyze a historical product-die design pair and infer the
engineering reasoning behind every major design decision.

Strict rules:
- NEVER fabricate numbers not present in the input data.
- ALL inferences must use hedged language: "likely because", "suggests that",
  "consistent with", "typically required when".
- ALWAYS flag ambiguities explicitly.
- Reference specific cold-heading engineering principles (upset ratio limits,
  volume conservation, die material hardness hierarchy, etc.).
- Confidence: assign 0.0–1.0 per section and overall. Be conservative.
"""

PR_USER_TEMPLATE = """\
Analyze this cold-heading fastener die design and explain the engineering
reasoning behind each decision.

## Product Features
{features_json}

## Process Plan
{process_plan_json}

## Die Parameters (all stations)
{die_params_json}

## Geometric Differential (product → die)
- Blank diameter: {blank_diameter}mm  →  shank diameter: {shank_diameter}mm
  (reduction ratio: {reduction_ratio:.3f})
- Head upset ratio: {head_upset_ratio:.3f}  (limit: 2.3 per single-blow)
- Station count: {station_count}
- Blank volume (approx): {blank_volume:.1f} mm³

Produce your analysis using the `record_reasoning` tool.
Follow the schema exactly. Use hedged language for all inferences.
"""

# Anthropic tool_use schema — defines the structured output format
PR_TOOL_SCHEMA: dict = {
    "name": "record_reasoning",
    "description": "Record the engineering reasoning for this product-die pair.",
    "input_schema": {
        "type": "object",
        "properties": {
            "observable_facts": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of verifiable facts directly from the input data (no inference).",
            },
            "stock_selection_reasoning": {
                "type": "string",
                "description": "Why this wire stock diameter and blank length were chosen. Reference upset ratio, volume conservation, and any standard wire size constraints.",
            },
            "station_count_reasoning": {
                "type": "string",
                "description": "Why exactly this number of stations (not more, not fewer). Reference upset ratio limits per blow, material ductility, and geometric complexity.",
            },
            "deformation_sequence_reasoning": {
                "type": "string",
                "description": "Logic of the deformation sequence across stations. Why operations are in this order.",
            },
            "die_material_reasoning": {
                "type": "string",
                "description": "Why these die steel grades and hardness ranges were chosen. Reference workpiece material, production volume, and hardness hierarchy rule.",
            },
            "dimensional_compensations": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Each significant product→die dimensional difference and the engineering reason for it (springback, shrinkage, tolerance stack-up, etc.).",
            },
            "critical_parameters": {
                "type": "object",
                "additionalProperties": {"type": "string"},
                "description": "Map of critical parameter name to its typical acceptable range, e.g. {'upset_ratio': '≤ 2.3 per station for cold heading'}.",
            },
            "potential_risks": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Failure modes or manufacturing challenges to watch for with this design.",
            },
            "section_confidences": {
                "type": "object",
                "properties": {
                    "stock_selection": {"type": "number"},
                    "station_count": {"type": "number"},
                    "deformation_sequence": {"type": "number"},
                    "die_material": {"type": "number"},
                    "dimensional_compensations": {"type": "number"},
                    "potential_risks": {"type": "number"},
                },
                "description": "Confidence score 0.0–1.0 for each reasoning section.",
            },
            "overall_confidence": {
                "type": "number",
                "description": "Overall confidence in this analysis (0.0–1.0). Be conservative.",
            },
        },
        "required": [
            "observable_facts",
            "stock_selection_reasoning",
            "station_count_reasoning",
            "deformation_sequence_reasoning",
            "die_material_reasoning",
            "dimensional_compensations",
            "critical_parameters",
            "potential_risks",
            "section_confidences",
            "overall_confidence",
        ],
    },
}


# ---------------------------------------------------------------------------
# Cross-Validation  —  CV_V1_0_0
# ---------------------------------------------------------------------------

CV_VERSION = "CV_V1_0_0"

CV_SYSTEM = """\
You are an independent cold-heading process engineer reviewing another
engineer's analysis of a fastener die design.

Your task: critically evaluate the primary analysis, note agreements and
disagreements, provide alternative reasoning where you disagree, and flag
any observations the primary analysis missed.

Be specific. Reference engineering principles. Do not simply agree for the
sake of agreement — challenge any unsupported inferences.
"""

CV_USER_TEMPLATE = """\
Review the following cold-heading die design analysis.

## Product-Die Pair Data

### Product Features
{features_json}

### Process Plan
{process_plan_json}

### Die Parameters
{die_params_json}

## Primary Analysis to Review
{primary_reasoning_json}

For each section of the primary analysis, indicate whether you agree or
disagree, provide alternative reasoning if you disagree, and list any
observations the primary analysis missed.

Return a JSON object with exactly this structure:
{{
  "agreements": {{
    "stock_selection": true/false,
    "station_count": true/false,
    "deformation_sequence": true/false,
    "die_material": true/false,
    "dimensional_compensations": true/false,
    "potential_risks": true/false
  }},
  "alternative_reasonings": {{
    "<section_name>": "<your alternative reasoning for sections you disagree with>"
  }},
  "missed_observations": [
    "<observation 1 the primary analysis missed>",
    ...
  ],
  "overall_agreement": <float 0.0-1.0>
}}
"""
