"""
Prompt for pseudo-reasoning pipeline.

Instructs Claude Opus 4.7 to analyze a product-die pair and infer
the engineering reasoning behind the design decisions. Run 3× for
self-consistency before cross-validation with Gemini.
"""

VERSION = "v1.0.0"

SYSTEM = """You are an expert cold-heading process engineer analyzing historical
fastener die designs. Your task is to infer the engineering reasoning behind
the design decisions made for a specific fastener.

Be conservative: only state reasoning you are highly confident about based on
the geometric evidence. If uncertain, say so explicitly."""

USER_TEMPLATE = """Analyze this historical fastener die design and explain the engineering reasoning.

## Product Features
{features_json}

## Process Plan
{process_plan_json}

## Die Parameters (all stations)
{die_params_json}

Explain:
1. Why this wire stock diameter and length was chosen
2. Why this number of stations was chosen (not more, not fewer)
3. The logic of the deformation sequence
4. Why these die materials and hardness values were chosen
5. The most critical features and tolerances

Return JSON matching the PseudoReasoning schema:
{schema_json}"""
