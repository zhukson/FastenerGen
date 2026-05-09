"""Prepare textbook/tutorial PDFs for FastenerGPT's knowledge layer.

This script does the non-LLM part of textbook ingestion:

  1. Inventory Gong Maoliang excerpts and the 1模2冲 / 紧固件模具 tutorial.
  2. Render each scanned PDF page to PNG for later vision/OCR extraction.
  3. Write a manifest JSON under backend/app/knowledge/textbook_sources/.

It intentionally does NOT write CaseRecord JSONs. Factory DWG cases are
answer keys; textbook examples are lower-weight references and should be
distilled into textbook_rules/, patterns/, or textbook_cases/.

Usage:
    uv run python -m scripts.ingest_textbook_pdfs
    uv run python -m scripts.ingest_textbook_pdfs --source gong --max-pages 8
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pypdfium2

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RAW_DATA_DIR = Path("/Users/bobchen/Desktop/fasternerData")
GENERATED_PAGE_DIR = REPO_ROOT / "fasternerGenData" / "textbook_pages"
MANIFEST_DIR = REPO_ROOT / "backend" / "app" / "knowledge" / "textbook_sources"
MANIFEST_PATH = MANIFEST_DIR / "manifest.json"


def _slugify(value: str) -> str:
    s = re.sub(r"\s+", "_", value.strip())
    s = re.sub(r"[^A-Za-z0-9_\-一-鿿]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return s or "source"


def _logical_range(path: Path) -> tuple[int | None, int | None]:
    """Parse filenames like Page355~358.pdf into a logical book page range."""
    match = re.search(r"[Pp]age(\d+)\s*~\s*(\d+)", path.stem)
    if not match:
        return None, None
    return int(match.group(1)), int(match.group(2))


def _discover_sources(raw_data_dir: Path, source: str) -> list[dict[str, Any]]:
    sources: list[dict[str, Any]] = []

    if source in {"all", "gong"}:
        gong_dir = raw_data_dir / "gong mao liang"
        for pdf in sorted(gong_dir.glob("*.pdf")):
            start, end = _logical_range(pdf)
            source_id = f"gong_maoliang_{_slugify(pdf.stem)}"
            sources.append(
                {
                    "source_id": source_id,
                    "source_kind": "gong_maoliang_excerpt",
                    "title_zh": "龚茂良紧固件冷镦资料摘页",
                    "path": str(pdf),
                    "logical_page_start": start,
                    "logical_page_end": end,
                }
            )

    if source in {"all", "tutorial"}:
        tutorial_pdf = raw_data_dir / "紧固件模具.pdf"
        if tutorial_pdf.exists():
            sources.append(
                {
                    "source_id": "one_die_two_blow_tutorial",
                    "source_kind": "one_die_two_blow_tutorial",
                    "title_zh": "1模2冲紧固件模具教程",
                    "path": str(tutorial_pdf),
                    "logical_page_start": 1,
                    "logical_page_end": None,
                }
            )

    return sources


def _page_count(pdf_path: Path) -> int:
    pdf = pypdfium2.PdfDocument(str(pdf_path))
    return len(pdf)


def _render_page(pdf_path: Path, page_index: int, out_path: Path, *, scale: float) -> None:
    pdf = pypdfium2.PdfDocument(str(pdf_path))
    page = pdf[page_index]
    bitmap = page.render(scale=scale)
    pil = bitmap.to_pil().convert("RGB")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    pil.save(str(out_path), "PNG", optimize=True)


def _build_source_manifest(
    src: dict[str, Any],
    *,
    render: bool,
    force: bool,
    scale: float,
    max_pages: int | None,
) -> dict[str, Any]:
    pdf_path = Path(src["path"])
    page_count = _page_count(pdf_path)
    render_count = min(page_count, max_pages) if max_pages else page_count
    logical_start = src.get("logical_page_start")

    source_out_dir = GENERATED_PAGE_DIR / src["source_id"]
    pages: list[dict[str, Any]] = []
    for page_index in range(render_count):
        logical_page = logical_start + page_index if isinstance(logical_start, int) else None
        image_name = f"p{page_index + 1:03d}"
        if logical_page is not None:
            image_name += f"_book{logical_page}"
        image_path = source_out_dir / f"{image_name}.png"
        if render and (force or not image_path.exists()):
            _render_page(pdf_path, page_index, image_path, scale=scale)
        pages.append(
            {
                "page_index": page_index,
                "logical_page": logical_page,
                "image_path": str(image_path.relative_to(REPO_ROOT)),
                "rendered": image_path.exists(),
            }
        )

    return {
        **src,
        "page_count": page_count,
        "rendered_page_count": len(pages),
        "render_scale": scale if render else None,
        "pages": pages,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--raw-data-dir",
        type=Path,
        default=DEFAULT_RAW_DATA_DIR,
        help="Root directory containing gong mao liang/, 标准件/, 异型件dwg案例/, 紧固件模具.pdf",
    )
    parser.add_argument(
        "--source",
        choices=["all", "gong", "tutorial"],
        default="all",
        help="Which textbook source group to ingest",
    )
    parser.add_argument("--no-render", action="store_true", help="Only write manifest")
    parser.add_argument("--force", action="store_true", help="Re-render existing page PNGs")
    parser.add_argument("--scale", type=float, default=1.35, help="PDF render scale")
    parser.add_argument("--max-pages", type=int, help="Limit pages per PDF for debugging")
    args = parser.parse_args()

    sources = _discover_sources(args.raw_data_dir, args.source)
    if not sources:
        print(f"No sources found under {args.raw_data_dir}", file=sys.stderr)
        return 1

    MANIFEST_DIR.mkdir(parents=True, exist_ok=True)
    GENERATED_PAGE_DIR.mkdir(parents=True, exist_ok=True)

    source_manifests: list[dict[str, Any]] = []
    for src in sources:
        print(f"+ ingest {src['source_id']}: {src['path']}")
        source_manifest = _build_source_manifest(
            src,
            render=not args.no_render,
            force=args.force,
            scale=args.scale,
            max_pages=args.max_pages,
        )
        source_manifests.append(source_manifest)
        print(
            f"  pages={source_manifest['page_count']} "
            f"rendered={source_manifest['rendered_page_count']}"
        )

    manifest = {
        "generated_at": datetime.now(UTC).isoformat(),
        "raw_data_dir": str(args.raw_data_dir),
        "generated_page_dir": str(GENERATED_PAGE_DIR.relative_to(REPO_ROOT)),
        "sources": source_manifests,
    }
    MANIFEST_PATH.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"\nManifest: {MANIFEST_PATH.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
