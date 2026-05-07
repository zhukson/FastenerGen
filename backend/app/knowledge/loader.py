"""Tier 1 经验库 (Experience Library) loader.

Discovers, validates, and formats all CaseRecord JSONs + rules.md files into
an XML few-shot block injected into Step 3 (Process Forming Design).

At N=8 worked cases this is the entire knowledge layer — no embeddings, no
vector retrieval. The LLM sees every case in every call.

Usage:
    from app.knowledge.loader import load_library, format_for_prompt

    lib = load_library()
    xml = format_for_prompt(lib, prefer_category="hex_bolt_DIN933")
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path

from pydantic import ValidationError

from app.data.schemas import CaseRecord

logger = logging.getLogger(__name__)

KNOWLEDGE_DIR = Path(__file__).resolve().parent
CASES_DIR = KNOWLEDGE_DIR / "cases"
STANDARDS_DIR = KNOWLEDGE_DIR / "standards"
RULES_DIR = KNOWLEDGE_DIR / "rules"


@dataclass
class Library:
    cases: list[CaseRecord]                 # 异形件
    standards: list[CaseRecord]             # standard parts (DIN912, DIN933, ...)
    rules: dict[str, str]                   # filename stem -> markdown text
    skipped: list[tuple[Path, str]]         # (path, reason) — invalid JSONs

    @property
    def all_records(self) -> list[CaseRecord]:
        return self.cases + self.standards

    @property
    def count(self) -> int:
        return len(self.cases) + len(self.standards)


def _load_record_file(path: Path) -> CaseRecord | tuple[Path, str]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return CaseRecord.model_validate(data)
    except (json.JSONDecodeError, ValidationError) as exc:
        return (path, f"{type(exc).__name__}: {str(exc)[:200]}")


def load_library() -> Library:
    """Load every case + standard + rules.md from backend/app/knowledge/.

    Invalid records are skipped and reported in `skipped`; we never fail-hard
    here because the loader runs on every Step 3 call.
    """
    cases: list[CaseRecord] = []
    standards: list[CaseRecord] = []
    skipped: list[tuple[Path, str]] = []

    for path in sorted(CASES_DIR.glob("*.json")):
        result = _load_record_file(path)
        if isinstance(result, CaseRecord):
            cases.append(result)
        else:
            skipped.append(result)
            logger.warning("Skipping invalid case %s: %s", *result)

    for path in sorted(STANDARDS_DIR.glob("*.json")):
        result = _load_record_file(path)
        if isinstance(result, CaseRecord):
            standards.append(result)
        else:
            skipped.append(result)
            logger.warning("Skipping invalid standard %s: %s", *result)

    rules: dict[str, str] = {}
    if RULES_DIR.exists():
        for path in sorted(RULES_DIR.glob("*.md")):
            rules[path.stem] = path.read_text(encoding="utf-8")

    return Library(cases=cases, standards=standards, rules=rules, skipped=skipped)


# ---------------------------------------------------------------------------
# Prompt formatting
# ---------------------------------------------------------------------------


def _xml_escape(s: str) -> str:
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _format_workpiece(w: dict) -> str:
    parts = [f'type="{w["type"]}"']
    for k in (
        "overall_length_mm",
        "max_diameter_mm",
        "head_diameter_mm",
        "head_height_mm",
        "shank_diameter_mm",
        "shank_length_mm",
    ):
        v = w.get(k)
        if v is not None:
            parts.append(f'{k}="{v}"')
    extras = w.get("extra_dims_mm") or {}
    if extras:
        extra_str = ", ".join(f"{k}={v}" for k, v in extras.items())
        parts.append(f'extra="{_xml_escape(extra_str)}"')
    notes = w.get("notes_zh")
    if notes:
        return f"<workpiece {' '.join(parts)}>{_xml_escape(notes)}</workpiece>"
    return f"<workpiece {' '.join(parts)}/>"


def _format_case(rec: CaseRecord) -> str:
    pf = rec.process_forming.model_dump(exclude_none=True, mode="json")
    feats = rec.part_features.model_dump(exclude_none=True, mode="json")

    feat_lines = [
        f"  <part_number>{_xml_escape(feats.get('part_number', ''))}</part_number>",
        f"  <description>{_xml_escape(feats.get('description', ''))}</description>",
        f"  <overall_length_mm>{feats.get('overall_length', '')}</overall_length_mm>",
        f"  <material_grade>{_xml_escape(feats.get('material_grade', ''))}</material_grade>",
    ]
    if feats.get("strength_grade"):
        feat_lines.append(
            f"  <strength_grade>{_xml_escape(feats['strength_grade'])}</strength_grade>"
        )
    if feats.get("standard"):
        feat_lines.append(f"  <standard>{_xml_escape(feats['standard'])}</standard>")
    if feats.get("thread"):
        t = feats["thread"]
        feat_lines.append(
            f"  <thread spec=\"{_xml_escape(t.get('spec', ''))}\" "
            f"nominal_diameter=\"{t.get('nominal_diameter', '')}\" "
            f"pitch=\"{t.get('pitch', '')}\" length=\"{t.get('length', '')}\"/>"
        )
    if feats.get("head"):
        h = feats["head"]
        feat_lines.append(
            f"  <head type=\"{h.get('type', '')}\" diameter=\"{h.get('diameter', '')}\" "
            f"height=\"{h.get('height', '')}\"/>"
        )
    if feats.get("shank"):
        s = feats["shank"]
        feat_lines.append(
            f"  <shank diameter=\"{s.get('diameter', '')}\" length=\"{s.get('length', '')}\"/>"
        )

    station_lines: list[str] = []
    for st in pf["stations"]:
        kd = st.get("key_dimensions") or {}
        kd_attrs = " ".join(f'{k}="{v}"' for k, v in kd.items())
        wp = _format_workpiece(st["workpiece"])
        notes = _xml_escape(st.get("notes_zh", "") or "")
        station_lines.append(
            f"    <station n=\"{st['n']}\" operation=\"{st['operation']}\" {kd_attrs}>\n"
            f"      {wp}\n"
            f"      <notes>{notes}</notes>\n"
            f"    </station>"
        )

    blank_xml = _format_workpiece(pf["blank"])
    post = ", ".join(pf.get("post_processes") or [])

    return (
        f'<case id="{_xml_escape(rec.case_id)}" '
        f'category="{_xml_escape(rec.product_category)}" '
        f'source="{rec.source_kind}" '
        f'extracted_by="{rec.extracted_by}">\n'
        f'  <part_name_zh>{_xml_escape(rec.product_name_zh)}</part_name_zh>\n'
        f'  <material>{_xml_escape(rec.material)}</material>\n'
        f"  <part_features>\n"
        + "\n".join(feat_lines)
        + "\n  </part_features>\n"
        f"  <process_forming station_count=\"{len(pf['stations'])}\">\n"
        f"    <blank>{blank_xml}</blank>\n"
        f"    <stations>\n"
        + "\n".join(station_lines)
        + "\n    </stations>\n"
        f"    <post_processes>{_xml_escape(post)}</post_processes>\n"
        f"    <reasoning_zh>{_xml_escape(pf['reasoning_zh'])}</reasoning_zh>\n"
        f"  </process_forming>\n"
        f"</case>"
    )


def format_for_prompt(
    lib: Library,
    *,
    prefer_category: str | None = None,
    only_human_reviewed: bool = False,
) -> str:
    """Format the entire library as one XML block for Step 3 few-shot.

    Args:
        prefer_category: place cases matching this category first (the LLM
            tends to weight earlier examples more heavily).
        only_human_reviewed: drop extracted_by="llm_draft" records. Default
            False so the demo can run before manual review is complete.
    """
    records = lib.all_records
    if only_human_reviewed:
        records = [r for r in records if r.extracted_by == "human_reviewed"]

    if prefer_category:
        matching = [r for r in records if r.product_category == prefer_category]
        rest = [r for r in records if r.product_category != prefer_category]
        records = matching + rest

    case_xml = "\n\n".join(_format_case(r) for r in records)

    rule_xml_parts: list[str] = []
    for name, body in lib.rules.items():
        rule_xml_parts.append(
            f'<rule_set name="{_xml_escape(name)}">\n{_xml_escape(body)}\n</rule_set>'
        )
    rule_xml = "\n\n".join(rule_xml_parts) if rule_xml_parts else "<!-- no rules curated yet -->"

    return (
        "<knowledge_library>\n"
        f"  <rules>\n{rule_xml}\n  </rules>\n"
        f"  <cases count=\"{len(records)}\">\n{case_xml}\n  </cases>\n"
        "</knowledge_library>"
    )
