"""
Extract draft CaseRecord JSONs from rendered drawing PNGs.

For each PNG in fasternerGenData/png/ this script:
  1. Determines source_kind + suggested category from the filename.
  2. Sends the PNG + extraction prompt to Claude Opus 4.7 vision.
  3. Validates the JSON against `CaseRecord`.
  4. Writes draft to backend/app/knowledge/{cases,standards}/<case_id>.json.

Drafts are marked extracted_by="llm_draft". You (the human) must review and
flip the marker to "human_reviewed" before they're trusted as Tier 1 few-shot.

Usage:
    # Extract all
    python -m scripts.extract_case_from_drawing

    # Extract one (matches by filename stem substring)
    python -m scripts.extract_case_from_drawing --only DIN912
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import sys
from pathlib import Path

import anthropic
from pydantic import ValidationError

from app.ai.prompts.case_extraction import (
    EXTRACTION_PROMPT_VERSION,
    SYSTEM_PROMPT,
    build_user_prompt,
)
from app.core.anthropic_client import create_anthropic_client
from app.core.env import load_local_env
from app.data.schemas import CaseRecord, PostProcess

ALLOWED_POST_PROCESSES = {p.value for p in PostProcess}
load_local_env(Path(__file__).resolve().parents[1])


def sanitize_post_processes(obj: dict) -> dict:
    """Drop unknown post_processes values rather than fail validation.

    The LLM occasionally emits compound strings (e.g. 'heat_treatment_8.8')
    or out-of-enum categories (e.g. 'chamfering'). Discard these — they
    belong in reasoning_zh, not the typed enum list.
    """
    pf = obj.get("process_forming") or {}
    raw = pf.get("post_processes") or []
    pf["post_processes"] = [p for p in raw if p in ALLOWED_POST_PROCESSES]
    obj["process_forming"] = pf
    return obj


def sanitize_thread(obj: dict) -> dict:
    """Drop a placeholder thread block when the part isn't really threaded.

    The LLM sometimes emits {pitch:0, length:0, thread_type:''} rather than
    null for unthreaded parts (rivets, pins, T-caps). Pydantic rejects those
    because pitch/length are gt=0 and thread_type is enum-restricted.
    """
    pf = obj.get("part_features") or {}
    th = pf.get("thread")
    if not th:
        return obj
    pitch = th.get("pitch") or 0.0
    length = th.get("length") or 0.0
    spec = (th.get("spec") or "").strip()
    if pitch <= 0 or length <= 0 or not spec:
        pf["thread"] = None
        obj["part_features"] = pf
    return obj


REPO_ROOT = Path(__file__).resolve().parents[2]
PNG_DIR = REPO_ROOT / "fasternerGenData" / "png"
KNOWLEDGE_DIR = REPO_ROOT / "backend" / "app" / "knowledge"
CASES_DIR = KNOWLEDGE_DIR / "cases"
STANDARDS_DIR = KNOWLEDGE_DIR / "standards"

MODEL = os.getenv("ANTHROPIC_MODEL", "claude-opus-4-7")


def slugify_case_id(stem: str) -> str:
    """Make a stable case_id from a PNG filename stem."""
    s = re.sub(r"\s+", "-", stem.strip())
    s = re.sub(r"[^A-Za-z0-9_\-一-鿿]+", "-", s)
    s = re.sub(r"-+", "-", s).strip("-")
    return s


def classify_filename(stem: str) -> tuple[str, str, str | None, str | None]:
    """Return (source_kind, suggested_category, suggested_standard_ref, out_dir_kind).

    out_dir_kind is "cases" or "standards" (which subfolder to write to).
    """
    upper = stem.upper()
    # Standard-part PDFs follow DIN912/DIN933 pattern
    if "DIN912" in upper:
        return ("standard_pdf", "socket_cap_screw_DIN912", "DIN912", "standards")
    if "DIN933" in upper:
        return ("standard_pdf", "hex_bolt_DIN933", "DIN933", "standards")
    # Everything else is treated as 异形件 case (incl. 球头)
    cat = "special_shape"
    if "四方T帽" in stem or "方头" in stem:
        cat = "square_T_head"
    elif "铆接螺钉" in stem:
        cat = "riveting_screw"
    elif "通孔" in stem:
        cat = "through_hole_part"
    elif "轴销" in stem or "销" in stem:
        cat = "rivet_pin"
    elif "球头" in stem:
        cat = "ball_head"
    return ("case_dwg", cat, None, "cases")


def encode_png(path: Path) -> str:
    return base64.standard_b64encode(path.read_bytes()).decode("ascii")


def call_extraction(client: anthropic.Anthropic, png: Path, *, dry_run: bool) -> dict:
    case_id = slugify_case_id(png.stem)
    source_kind, suggested_cat, suggested_std, _ = classify_filename(png.stem)
    sidecar = png.with_suffix(".txt")
    sidecar_text = sidecar.read_text(encoding="utf-8") if sidecar.exists() else ""
    user_prompt = build_user_prompt(
        case_id=case_id,
        source_kind=source_kind,
        source_file=png.stem,
        suggested_category=suggested_cat,
        suggested_standard_ref=suggested_std,
    )
    if sidecar_text:
        # Cap at 30K chars so we don't blow the context.
        capped = sidecar_text[:30000]
        user_prompt += (
            "\n\n--- DXF entity sidecar (precise dimension values, since the "
            "rendered PNG may not show numeric dim labels clearly) ---\n"
            f"{capped}\n--- end sidecar ---\n"
        )
    if dry_run:
        return {
            "_dry_run": True,
            "case_id": case_id,
            "prompt_chars": len(user_prompt),
            "sidecar_chars": len(sidecar_text),
        }

    img_b64 = encode_png(png)
    msg = client.messages.create(
        model=MODEL,
        max_tokens=8000,
        system=SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/png",
                            "data": img_b64,
                        },
                    },
                    {"type": "text", "text": user_prompt},
                ],
            }
        ],
    )
    text = "".join(b.text for b in msg.content if hasattr(b, "text"))
    text = text.strip()
    if text.startswith("```"):
        # strip markdown fence if model added one
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.MULTILINE)
    return json.loads(text)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="Substring filter on PNG filename")
    ap.add_argument("--dry-run", action="store_true", help="Skip API call; print plan only")
    ap.add_argument("--overwrite", action="store_true", help="Overwrite existing JSONs")
    args = ap.parse_args()

    if not PNG_DIR.exists():
        print(
            f"ERROR: {PNG_DIR} does not exist. Run render_drawings_to_png.py first.",
            file=sys.stderr,
        )
        return 2

    pngs = sorted(PNG_DIR.glob("*.png"))
    if args.only:
        pngs = [p for p in pngs if args.only in p.name]
    if not pngs:
        print("No matching PNGs.", file=sys.stderr)
        return 1

    if not args.dry_run and not os.getenv("ANTHROPIC_API_KEY"):
        print("ERROR: ANTHROPIC_API_KEY not set", file=sys.stderr)
        return 2

    client = create_anthropic_client() if not args.dry_run else None
    CASES_DIR.mkdir(parents=True, exist_ok=True)
    STANDARDS_DIR.mkdir(parents=True, exist_ok=True)

    print(f"Extraction prompt version: {EXTRACTION_PROMPT_VERSION}")
    print(f"Model: {MODEL}")
    print(f"PNGs to process: {len(pngs)}\n")

    saved: list[Path] = []
    failed: list[tuple[str, str]] = []

    for png in pngs:
        case_id = slugify_case_id(png.stem)
        _, _, _, out_kind = classify_filename(png.stem)
        out_dir = CASES_DIR if out_kind == "cases" else STANDARDS_DIR
        out_path = out_dir / f"{case_id}.json"
        if out_path.exists() and not args.overwrite:
            print(f"  - skip (exists): {out_path.relative_to(REPO_ROOT)}")
            continue
        print(f"  + extract: {png.name}")

        try:
            obj = call_extraction(client, png, dry_run=args.dry_run)
            if args.dry_run:
                print(f"    dry-run plan: {obj}")
                continue
            obj = sanitize_post_processes(obj)
            obj = sanitize_thread(obj)
            # Validate against CaseRecord (fail loudly if drift)
            CaseRecord.model_validate(obj)
            out_path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
            saved.append(out_path)
            print(f"    -> {out_path.relative_to(REPO_ROOT)}")
        except (ValidationError, json.JSONDecodeError, anthropic.APIError) as exc:
            failed.append((png.name, str(exc)[:300]))
            print(f"    ! FAILED: {type(exc).__name__}: {str(exc)[:200]}", file=sys.stderr)

    print(
        f"\nSaved: {len(saved)}    Failed: {len(failed)}    Skipped existing: {len(pngs) - len(saved) - len(failed)}"
    )
    if failed:
        print("\nFailures:")
        for name, err in failed:
            print(f"  - {name}: {err}")
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
