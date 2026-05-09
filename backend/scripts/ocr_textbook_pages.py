"""OCR rendered textbook pages with Tesseract.

Prerequisite:
    brew install tesseract tesseract-lang
    uv run python -m scripts.ingest_textbook_pdfs

The OCR output is a generated aid under fasternerGenData/textbook_ocr/. It is
not trusted directly in prompts; use it to speed up manual/LLM distillation
into backend/app/knowledge/textbook_rules/ and textbook_cases/.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = REPO_ROOT / "backend" / "app" / "knowledge" / "textbook_sources" / "manifest.json"
OCR_DIR = REPO_ROOT / "fasternerGenData" / "textbook_ocr"


def _load_manifest() -> dict[str, Any]:
    if not MANIFEST_PATH.exists():
        raise FileNotFoundError(f"{MANIFEST_PATH} missing; run scripts.ingest_textbook_pdfs first")
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def _parse_pages(spec: str | None) -> set[int] | None:
    if not spec:
        return None
    pages: set[int] = set()
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            start_s, end_s = part.split("-", 1)
            pages.update(range(int(start_s), int(end_s) + 1))
        else:
            pages.add(int(part))
    return pages


def _iter_pages(
    manifest: dict[str, Any], *, source_id: str | None, pages: set[int] | None
) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    for source in manifest["sources"]:
        if source_id and source["source_id"] != source_id:
            continue
        for page in source["pages"]:
            logical = page.get("logical_page")
            one_based = page["page_index"] + 1
            if pages is not None and logical not in pages and one_based not in pages:
                continue
            selected.append({**page, "source_id": source["source_id"]})
    return selected


def _ocr_page(image_path: Path, *, lang: str, psm: int) -> str:
    cmd = [
        "tesseract",
        str(image_path),
        "stdout",
        "-l",
        lang,
        "--psm",
        str(psm),
    ]
    proc = subprocess.run(cmd, check=False, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or f"tesseract exited {proc.returncode}")
    return proc.stdout.strip()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-id", help="Limit to one manifest source_id")
    parser.add_argument("--pages", help="Logical pages or 1-based PDF pages, e.g. 1-5,371")
    parser.add_argument("--lang", default="chi_sim+eng")
    parser.add_argument("--psm", type=int, default=6)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--max-pages", type=int)
    args = parser.parse_args()

    if shutil.which("tesseract") is None:
        print(
            "ERROR: tesseract not found. Run: brew install tesseract tesseract-lang",
            file=sys.stderr,
        )
        return 2

    manifest = _load_manifest()
    selected = _iter_pages(manifest, source_id=args.source_id, pages=_parse_pages(args.pages))
    if args.max_pages:
        selected = selected[: args.max_pages]
    if not selected:
        print("No pages selected.", file=sys.stderr)
        return 1

    OCR_DIR.mkdir(parents=True, exist_ok=True)
    ok = 0
    failed: list[tuple[str, str]] = []

    for page in selected:
        image_path = REPO_ROOT / page["image_path"]
        source_dir = OCR_DIR / page["source_id"]
        out_path = source_dir / (image_path.stem + ".txt")
        if out_path.exists() and not args.force:
            ok += 1
            print(f"skip {out_path.relative_to(REPO_ROOT)}")
            continue

        try:
            text = _ocr_page(image_path, lang=args.lang, psm=args.psm)
            source_dir.mkdir(parents=True, exist_ok=True)
            out_path.write_text(text + "\n", encoding="utf-8")
            ok += 1
            print(
                f"ocr {page['source_id']} logical={page.get('logical_page')} "
                f"chars={len(text)} -> {out_path.relative_to(REPO_ROOT)}"
            )
        except Exception as exc:  # noqa: BLE001 - continue OCR batch
            failed.append((str(image_path), str(exc)[:200]))
            print(f"FAILED {image_path}: {exc}", file=sys.stderr)

    print(f"\nOCR complete: ok={ok} failed={len(failed)}")
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
