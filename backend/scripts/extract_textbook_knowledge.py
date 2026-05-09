"""Extract textbook rules or textbook cases from rendered textbook pages.

Prerequisite:
    uv run python -m scripts.ingest_textbook_pdfs

Examples:
    # See which pages would be sent
    uv run python -m scripts.extract_textbook_knowledge --source-id gong_maoliang_Page21_26 --pages 22-23 --kind rules --dry-run

    # Extract a textbook case JSON from one page
    uv run python -m scripts.extract_textbook_knowledge --source-id gong_maoliang_Page371_374 --pages 371 --kind case --out-name gong_8_30

The output is deliberately separate from CaseRecord. Factory DWG cases remain
the high-trust answer keys; textbook extraction is lower-trust reference
knowledge with explicit provenance.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

import anthropic

from app.core.env import load_local_env

REPO_ROOT = Path(__file__).resolve().parents[2]
load_local_env(REPO_ROOT / "backend")

MANIFEST_PATH = REPO_ROOT / "backend" / "app" / "knowledge" / "textbook_sources" / "manifest.json"
TEXTBOOK_RULES_DIR = REPO_ROOT / "backend" / "app" / "knowledge" / "textbook_rules"
TEXTBOOK_CASES_DIR = REPO_ROOT / "backend" / "app" / "knowledge" / "textbook_cases"
OCR_DIR = REPO_ROOT / "fasternerGenData" / "textbook_ocr"
DEFAULT_RULE_MODEL = os.getenv("ANTHROPIC_TEXTBOOK_RULE_MODEL", "claude-haiku-4-5-20251001")
DEFAULT_CASE_MODEL = os.getenv(
    "ANTHROPIC_TEXTBOOK_CASE_MODEL",
    os.getenv("ANTHROPIC_TEXTBOOK_MODEL", "claude-sonnet-4-6"),
)


SYSTEM_PROMPT = """\
You are a senior cold-heading (冷镦) engineer extracting knowledge from a
scanned Chinese textbook/tutorial page for FastenerGPT.

Rules:
  - Summarize and structure. Do not transcribe long passages.
  - Keep formulas, numeric thresholds, table values, and station sequences.
  - Mark uncertainty explicitly when a dimension or label is hard to read.
  - Output either Markdown rules or a compact JSON textbook case, depending on
    the user's requested kind.
  - This is lower-trust textbook knowledge, not a factory answer key.
"""


def _slugify(value: str) -> str:
    s = re.sub(r"\s+", "_", value.strip())
    s = re.sub(r"[^A-Za-z0-9_\-一-鿿]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return s or "textbook_extract"


def _load_manifest() -> dict[str, Any]:
    if not MANIFEST_PATH.exists():
        raise FileNotFoundError(f"{MANIFEST_PATH} missing; run scripts.ingest_textbook_pdfs first")
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def _parse_pages(spec: str) -> set[int]:
    pages: set[int] = set()
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            start_s, end_s = part.split("-", 1)
            start, end = int(start_s), int(end_s)
            pages.update(range(start, end + 1))
        else:
            pages.add(int(part))
    return pages


def _select_pages(manifest: dict[str, Any], *, source_id: str, pages: str) -> list[dict[str, Any]]:
    wanted = _parse_pages(pages)
    source = next((s for s in manifest["sources"] if s["source_id"] == source_id), None)
    if source is None:
        known = ", ".join(s["source_id"] for s in manifest["sources"])
        raise ValueError(f"Unknown source_id {source_id!r}. Known: {known}")

    selected: list[dict[str, Any]] = []
    for page in source["pages"]:
        logical = page.get("logical_page")
        one_based = page["page_index"] + 1
        if logical in wanted or one_based in wanted:
            item = {**page, "source_id": source_id, "source_kind": source["source_kind"]}
            selected.append(item)
    if not selected:
        raise ValueError(f"No pages matched {pages!r} in {source_id}")
    return selected


def _encode_image(path: Path) -> str:
    return base64.standard_b64encode(path.read_bytes()).decode("ascii")


def _ocr_text_for_page(page: dict[str, Any]) -> str:
    image_path = Path(page["image_path"])
    ocr_path = OCR_DIR / page["source_id"] / f"{image_path.stem}.txt"
    if not ocr_path.exists():
        return ""
    return ocr_path.read_text(encoding="utf-8").strip()


def _format_ocr_block(selected: list[dict[str, Any]]) -> str:
    blocks: list[str] = []
    for page in selected:
        text = _ocr_text_for_page(page)
        if not text:
            continue
        ref = f"{page['source_id']}:{page.get('logical_page') or page['page_index'] + 1}"
        blocks.append(f"--- OCR text for {ref} ---\n{text[:5000]}\n--- end OCR text ---")
    return "\n\n".join(blocks)


def _build_prompt(kind: str, selected: list[dict[str, Any]]) -> str:
    page_refs = ", ".join(
        f"{p['source_id']}:{p.get('logical_page') or p['page_index'] + 1}" for p in selected
    )
    ocr_block = _format_ocr_block(selected)
    ocr_note = (
        "\n\nThe following OCR text is noisy. Prefer exact numeric values only when the OCR and image agree.\n"
        f"{ocr_block}\n"
        if ocr_block
        else "\n\nNo OCR text sidecar was available; rely on attached images.\n"
    )
    if kind == "rules":
        return f"""\
Extract reusable cold-heading rules from these textbook pages.

Page refs: {page_refs}
{ocr_note}

Return Markdown with:
- provenance
- key formulas or numeric limits
- station-sequence rules
- how FastenerGPT Step 3 should use the rule
- uncertainty notes

Keep it concise and do not quote long source text.
"""
    return f"""\
Extract one compact textbook_case JSON from these textbook pages.

Page refs: {page_refs}
{ocr_note}

Return ONLY JSON with this shape:
{{
  "id": "<stable snake_case id>",
  "source": "{page_refs}",
  "status": "llm_draft_low_confidence",
  "title_zh": "...",
  "product_category": "...",
  "why_it_matters": "...",
  "visible_process_summary_zh": "...",
  "visible_dimensions": {{}},
  "station_sequence": [
    {{"n": 0, "label_zh": "下料", "geometry_zh": "...", "dimensions": {{}}}}
  ],
  "usage_in_prompt": "..."
}}

Do not pretend unreadable dimensions are precise. Use strings like "unclear" if needed.
"""


def _call_model(
    client: anthropic.Anthropic,
    *,
    kind: str,
    selected: list[dict[str, Any]],
    model: str,
    include_images: bool,
) -> str:
    if len(selected) > 8:
        raise ValueError("Send at most 8 pages per extraction call; split larger ranges.")
    content: list[dict[str, Any]] = []
    if include_images:
        for page in selected:
            image_path = REPO_ROOT / page["image_path"]
            content.append(
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/png",
                        "data": _encode_image(image_path),
                    },
                }
            )
    content.append({"type": "text", "text": _build_prompt(kind, selected)})

    msg = client.messages.create(
        model=model,
        max_tokens=6000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": content}],
    )
    return "".join(block.text for block in msg.content if hasattr(block, "text")).strip()


def _extract_first_json_object(text: str) -> str:
    """Return the first balanced JSON object from a model response."""
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.MULTILINE).strip()
    start = text.find("{")
    if start < 0:
        raise json.JSONDecodeError("No JSON object found", text, 0)

    depth = 0
    in_string = False
    escape = False
    for idx in range(start, len(text)):
        ch = text[idx]
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : idx + 1]
    raise json.JSONDecodeError("Unterminated JSON object", text, start)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-id", required=True)
    parser.add_argument(
        "--pages", required=True, help="Logical pages or 1-based PDF pages: 22-23,371"
    )
    parser.add_argument("--kind", choices=["rules", "case"], required=True)
    parser.add_argument("--out-name", help="Output filename stem")
    parser.add_argument(
        "--model",
        help=(
            "Anthropic model for extraction. Defaults to Haiku 4.5 for rules "
            "and Sonnet 4.6 for image textbook cases."
        ),
    )
    parser.add_argument(
        "--text-only",
        action="store_true",
        help="Send OCR text only, no page images. Good for cheap rule extraction.",
    )
    parser.add_argument(
        "--include-images",
        action="store_true",
        help="Force image input. By default, cases include images and rules use OCR text only.",
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    manifest = _load_manifest()
    selected = _select_pages(manifest, source_id=args.source_id, pages=args.pages)
    model = args.model or (DEFAULT_RULE_MODEL if args.kind == "rules" else DEFAULT_CASE_MODEL)

    out_stem = _slugify(args.out_name or f"{args.source_id}_{args.pages}_{args.kind}")
    out_dir = TEXTBOOK_RULES_DIR if args.kind == "rules" else TEXTBOOK_CASES_DIR
    suffix = ".md" if args.kind == "rules" else ".json"
    out_path = out_dir / f"{out_stem}{suffix}"

    include_images = args.include_images or (args.kind == "case" and not args.text_only)
    print(f"Model: {model}")
    print(f"Mode: {'image+ocr' if include_images else 'ocr-text-only'}")
    print("Selected pages:")
    for page in selected:
        ocr_chars = len(_ocr_text_for_page(page))
        print(
            f"  - {page['source_id']} logical={page.get('logical_page')} "
            f"ocr_chars={ocr_chars} image={page['image_path']}"
        )
    print(f"Output: {out_path.relative_to(REPO_ROOT)}")

    if args.dry_run:
        return 0
    if not os.getenv("ANTHROPIC_API_KEY"):
        print("ERROR: ANTHROPIC_API_KEY not set", file=sys.stderr)
        return 2
    if out_path.exists() and not args.overwrite:
        print(f"ERROR: {out_path} exists; pass --overwrite", file=sys.stderr)
        return 2

    out_dir.mkdir(parents=True, exist_ok=True)
    text = _call_model(
        anthropic.Anthropic(),
        kind=args.kind,
        selected=selected,
        model=model,
        include_images=include_images,
    )
    if args.kind == "case":
        stripped = _extract_first_json_object(text)
        json.loads(stripped)
        text = stripped
    out_path.write_text(text + "\n", encoding="utf-8")
    print(f"Saved: {out_path.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
