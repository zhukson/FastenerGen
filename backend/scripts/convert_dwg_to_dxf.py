"""
Convert DWG files in fasternerGenData/ to DXF.

ezdxf cannot read DWG natively. Two paths supported:

  1. ODA File Converter (recommended)
     Free download: https://www.opendesign.com/guestfiles/oda_file_converter
     macOS installs to: /Applications/ODAFileConverter.app
     CLI:  ODAFileConverter <inDir> <outDir> <outVer> <outFmt> <recurse> <audit> [filter]

  2. Manual fallback
     Open each .dwg in LibreCAD / AutoCAD / DraftSight, "Save As" → DXF (R2018).

Usage:
    python -m scripts.convert_dwg_to_dxf

Reads:  fasternerGenData/*.dwg
Writes: fasternerGenData/dxf/*.dxf
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = REPO_ROOT / "fasternerGenData"
OUT_DIR = SRC_DIR / "dxf"

ODA_MAC_PATH = Path(
    "/Applications/ODAFileConverter.app/Contents/MacOS/ODAFileConverter"
)


def find_oda() -> Path | None:
    if ODA_MAC_PATH.exists():
        return ODA_MAC_PATH
    on_path = shutil.which("ODAFileConverter")
    return Path(on_path) if on_path else None


def convert_with_oda(oda: Path, src: Path, out: Path) -> None:
    """Run ODAFileConverter on a directory.

    Args: <inDir> <outDir> <outVer> <outFmt> <recurse> <audit> [filter]
    outVer: ACAD2018 (most compatible)
    outFmt: DXF
    """
    out.mkdir(parents=True, exist_ok=True)
    cmd = [str(oda), str(src), str(out), "ACAD2018", "DXF", "0", "1", "*.DWG"]
    print(f"$ {' '.join(cmd)}")
    subprocess.run(cmd, check=True)


def main() -> int:
    if not SRC_DIR.exists():
        print(f"ERROR: source dir not found: {SRC_DIR}", file=sys.stderr)
        return 2

    dwgs = sorted(SRC_DIR.glob("*.dwg"))
    if not dwgs:
        print(f"No .dwg files in {SRC_DIR}", file=sys.stderr)
        return 1

    print(f"Found {len(dwgs)} DWG files in {SRC_DIR}:")
    for p in dwgs:
        print(f"  - {p.name}")

    oda = find_oda()
    if oda is None:
        print(
            "\nODA File Converter not found.\n"
            "Install it (free, GUI installer):\n"
            "  https://www.opendesign.com/guestfiles/oda_file_converter\n"
            "After install, expected path:\n"
            f"  {ODA_MAC_PATH}\n"
            "Then re-run this script.\n"
            "\nManual fallback: open each .dwg in LibreCAD / AutoCAD,\n"
            f"save as DXF (R2018) into {OUT_DIR}.",
            file=sys.stderr,
        )
        return 3

    print(f"\nUsing ODA: {oda}")
    convert_with_oda(oda, SRC_DIR, OUT_DIR)

    produced = sorted(OUT_DIR.glob("*.dxf"))
    print(f"\nProduced {len(produced)} DXF files in {OUT_DIR}:")
    for p in produced:
        print(f"  - {p.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
