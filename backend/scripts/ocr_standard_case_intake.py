"""Run OCR for standard forming-process intake PNGs."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any


def main() -> None:
    args = _parse_args()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    args.out_dir.mkdir(parents=True, exist_ok=True)

    for item in manifest.get("cases", []):
        out_path = args.out_dir / f"{item['case_id']}.ocr.txt"
        text = _ocr_case(item, dry_run=args.dry_run, lang=args.lang, psm=args.psm)
        out_path.write_text(text.rstrip() + "\n", encoding="utf-8")
        print(f"Wrote {out_path}")


def _ocr_case(
    item: dict[str, Any],
    *,
    dry_run: bool,
    lang: str,
    psm: int,
) -> str:
    source_file = item["source_file"]
    if dry_run:
        return f"DRY RUN OCR placeholder for {source_file}"

    result = subprocess.run(
        [
            "tesseract",
            source_file,
            "stdout",
            "-l",
            lang,
            "--psm",
            str(psm),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise SystemExit(result.stderr.strip())
    return result.stdout


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--lang", default="eng+chi_tra+chi_sim")
    parser.add_argument("--psm", type=int, default=6)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


if __name__ == "__main__":
    main()
