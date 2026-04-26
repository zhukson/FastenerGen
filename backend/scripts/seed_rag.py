"""
RAG seeding script.

Generates and indexes synthetic cases into ChromaDB so the design pipeline
has real anchors for every common fastener type instead of guessing.

Usage:
    python -m scripts.seed_rag --n 250 --chroma-url http://localhost:8000 --clear

    # Docker:
    docker compose exec backend uv run python -m scripts.seed_rag --n 250 --clear
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from itertools import product as iterproduct

# ---------------------------------------------------------------------------
# ISO combinations to generate (60% of total)
# ---------------------------------------------------------------------------

_ISO_SPECS = ["M4", "M5", "M6", "M8", "M10", "M12"]
_ISO_HEAD_TYPES = ["hex", "flat", "socket"]
_ISO_LENGTHS: dict[str, list[float]] = {
    "M4":  [10, 16, 20, 25, 30],
    "M5":  [12, 16, 20, 25, 30, 40],
    "M6":  [16, 20, 25, 30, 35, 40, 50],
    "M8":  [20, 25, 30, 35, 40, 50, 60],
    "M10": [25, 30, 40, 50, 60, 70],
    "M12": [30, 40, 50, 60, 80],
}
_ISO_GRADES = ["4.8", "5.8", "8.8", "10.9", "12.9"]


def _build_iso_combinations() -> list[tuple[str, str, float, str]]:
    """Build (spec, head_type, length, grade) combos, avoiding sizes not in ISO tables."""
    from app.data.synthetic import _ISO_TABLES  # noqa: PLC0415
    combos = []
    for spec in _ISO_SPECS:
        for head_type in _ISO_HEAD_TYPES:
            table, *_ = _ISO_TABLES[head_type]
            if spec not in table:
                continue
            for length in _ISO_LENGTHS.get(spec, [20, 30, 40]):
                grade = None  # will be randomized per case
                combos.append((spec, head_type, float(length), grade))
    return combos


async def seed(
    n: int,
    chroma_url: str,
    clear: bool,
    dry_run: bool,
    batch_size: int = 20,
) -> int:
    """Seed ChromaDB with n synthetic cases. Returns count actually indexed."""
    import chromadb

    from app.ai.embeddings import EmbeddingService
    from app.ai.rag import FastenerRAG
    from app.core.config import settings
    from app.data.synthetic import SyntheticDataGenerator

    print(f"[seed_rag] Connecting to ChromaDB at {chroma_url}")
    host_port = chroma_url.replace("http://", "").replace("https://", "")
    host, _, port_str = host_port.partition(":")
    port = int(port_str) if port_str else 8000

    try:
        client = chromadb.HttpClient(host=host, port=port)
        client.heartbeat()
    except Exception as exc:
        print(f"[seed_rag] ERROR: Cannot connect to ChromaDB: {exc}", file=sys.stderr)
        return 0

    collection_name = settings.chroma_collection_name

    if clear:
        try:
            client.delete_collection(collection_name)
            print(f"[seed_rag] Cleared collection '{collection_name}'")
        except Exception:
            pass

    collection = client.get_or_create_collection(
        name=collection_name,
        metadata={"hnsw:space": "cosine"},
    )

    emb_service = EmbeddingService()
    rag = FastenerRAG(embedding_service=emb_service, collection=collection)
    gen = SyntheticDataGenerator(seed=42)

    # Build case list: 60% ISO, 40% random
    iso_combos = _build_iso_combinations()
    n_iso = int(n * 0.6)
    n_random = n - n_iso

    print(f"[seed_rag] Generating {n_iso} ISO cases + {n_random} random cases = {n} total")

    cases = []

    # ISO cases — cycle through combinations
    for i in range(n_iso):
        spec, head_type, length, _ = iso_combos[i % len(iso_combos)]
        try:
            case = gen.generate_iso_case(spec, head_type, length)
            cases.append(case)
        except Exception as exc:
            print(f"[seed_rag] Warning: ISO case {spec}/{head_type}/{length} failed: {exc}")

    # Random cases
    for i in range(n_random):
        try:
            case = gen.generate_complete_case(seed=1000 + i)
            cases.append(case)
        except Exception as exc:
            print(f"[seed_rag] Warning: random case {i} failed: {exc}")

    if dry_run:
        print(f"[seed_rag] DRY RUN — would index {len(cases)} cases")
        _print_summary(cases)
        return len(cases)

    # Batch upsert with retry/backoff for Voyage rate limits (3 RPM free tier)
    import time

    indexed = 0
    failed = 0
    for batch_start in range(0, len(cases), batch_size):
        batch = cases[batch_start : batch_start + batch_size]
        batch_num = batch_start // batch_size + 1
        retries = 3
        for attempt in range(retries):
            try:
                await rag.add_batch(batch)
                indexed += len(batch)
                print(f"[seed_rag] Indexed {indexed}/{len(cases)} (batch {batch_num})")
                # Rate-limit courtesy sleep: Voyage free tier = 3 RPM
                if batch_start + batch_size < len(cases):
                    await asyncio.sleep(22)
                break
            except Exception as exc:
                err_str = str(exc)
                if "rate" in err_str.lower() or "429" in err_str or "payment" in err_str.lower():
                    wait = 25 * (attempt + 1)
                    print(f"[seed_rag] Rate limited — waiting {wait}s before retry {attempt + 1}/{retries}")
                    await asyncio.sleep(wait)
                else:
                    print(f"[seed_rag] Batch {batch_num} failed: {err_str}", file=sys.stderr)
                    failed += len(batch)
                    break
        else:
            print(f"[seed_rag] Batch {batch_num} exhausted retries — skipping", file=sys.stderr)
            failed += len(batch)

    print(f"\n[seed_rag] Done: {indexed} indexed, {failed} failed")
    _print_summary(cases)

    return indexed


def _print_summary(cases: list) -> None:
    from collections import Counter

    by_size: Counter = Counter()
    by_head: Counter = Counter()
    by_conf: Counter = Counter()

    for c in cases:
        nom = c.part_features.thread.nominal_diameter
        by_size[f"M{nom:.0f}"] += 1
        by_head[c.part_features.head.type.value] += 1
        by_conf[c.confidence.value] += 1

    print("\n  By size:      ", dict(sorted(by_size.items())))
    print("  By head type: ", dict(sorted(by_head.items())))
    print("  By confidence:", dict(by_conf))


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed ChromaDB with synthetic fastener cases")
    parser.add_argument("--n", type=int, default=250, help="Number of cases to generate")
    parser.add_argument("--chroma-url", default="http://localhost:8000", help="ChromaDB URL")
    parser.add_argument("--clear", action="store_true", help="Clear existing collection first")
    parser.add_argument("--dry-run", action="store_true", help="Generate but don't index")
    parser.add_argument("--batch-size", type=int, default=20, help="Upsert batch size")
    args = parser.parse_args()

    indexed = asyncio.run(
        seed(
            n=args.n,
            chroma_url=args.chroma_url,
            clear=args.clear,
            dry_run=args.dry_run,
            batch_size=args.batch_size,
        )
    )

    min_required = int(args.n * 0.8)
    if not args.dry_run and indexed < min_required:
        print(
            f"[seed_rag] FAIL: only {indexed}/{args.n} cases indexed (need ≥ {min_required})",
            file=sys.stderr,
        )
        sys.exit(1)

    print(f"[seed_rag] Success: {indexed} cases indexed")


if __name__ == "__main__":
    main()
