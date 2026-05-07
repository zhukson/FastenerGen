"""
Render drawings (DXF + PDF) in fasternerGenData/ to PNG previews.

Used by the case-extraction pipeline so Claude vision sees a uniform PNG.

  - .dxf  -> rendered via ezdxf + matplotlib (modelspace, full extents)
  - .pdf  -> first page rendered via pypdfium2 (scale tuned to keep <5MB)

Usage:
    python -m scripts.render_drawings_to_png
"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import pypdfium2
from ezdxf import recover
from ezdxf.addons.drawing import Frontend, RenderContext
from ezdxf.addons.drawing.matplotlib import MatplotlibBackend

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = REPO_ROOT / "fasternerGenData"
# DXFs may live either at the top of fasternerGenData/ (where the user dropped
# them after manual DWG→DXF conversion) or under fasternerGenData/dxf/ (output
# of scripts/convert_dwg_to_dxf.py). We discover from both.
DXF_DIR = SRC_DIR / "dxf"
OUT_DIR = SRC_DIR / "png"

PDF_RENDER_SCALE = 1.5  # ~under Claude's 5MB base64 limit per project conventions


def _pick_richest_layout(doc) -> object:
    """These DWGs put 过模图 content in paperspace layouts (布局1/布局2),
    not modelspace. Choose the layout with the most entities.
    """
    candidates = [doc.modelspace()] + [doc.layouts.get(name) for name in doc.layouts.names() if name != "Model"]
    best = max(candidates, key=lambda lay: len(list(lay)))
    return best


def render_dxf(dxf_path: Path, out_path: Path) -> None:
    doc, _ = recover.readfile(str(dxf_path))
    layout = _pick_richest_layout(doc)

    fig = plt.figure(figsize=(28, 20), dpi=220)
    ax = fig.add_axes((0, 0, 1, 1))
    ax.set_axis_off()
    ctx = RenderContext(doc)
    out = MatplotlibBackend(ax)
    Frontend(ctx, out).draw_layout(layout, finalize=True)

    fig.savefig(str(out_path), dpi=220, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    _dump_dxf_summary(doc, out_path.with_suffix(".txt"))


def _dump_dxf_summary(doc, out_path: Path) -> None:
    """Write a text summary of DIMENSION entities + line bbox.

    Matplotlib doesn't render DIMENSION text reliably (Chinese fonts), so the
    extraction LLM gets these numeric values via a sidecar text file. The
    (x, y) positions let it correlate with the visual layout in the PNG.
    """
    msp = doc.modelspace()
    lines = []
    lines.append(f"# DXF entity summary  (layouts={doc.layouts.names()})")
    lines.append("")

    # Aggregate LINE bounds — useful for station-cluster discovery
    xs, ys = [], []
    for e in msp.query("LINE"):
        xs.extend([e.dxf.start.x, e.dxf.end.x])
        ys.extend([e.dxf.start.y, e.dxf.end.y])
    if xs:
        lines.append(
            f"# Line geometry bbox: x=[{min(xs):.1f}, {max(xs):.1f}]  "
            f"y=[{min(ys):.1f}, {max(ys):.1f}]  ({len(xs) // 2} lines)"
        )
        lines.append("")

    # Dimensions sorted by x then y so station groupings are apparent
    dims = []
    for d in msp.query("DIMENSION"):
        try:
            val = d.get_measurement()
        except Exception:
            val = None
        text = (d.dxf.text or "").strip()
        defp = d.dxf.defpoint
        dims.append((defp.x, defp.y, text, val, d.dxf.layer))
    dims.sort()
    lines.append(f"# {len(dims)} DIMENSION entities (sorted by x,y)")
    lines.append("# format: x,y  text='<override>'  measurement=<computed>  layer=<name>")
    for x, y, text, val, layer in dims:
        val_s = f"{val:.3f}" if isinstance(val, (int, float)) else "?"
        lines.append(f"  {x:8.1f},{y:8.1f}  text='{text}'  measurement={val_s}  layer={layer}")

    # Any MTEXT/TEXT (annotations)
    texts = []
    for t in msp.query("MTEXT"):
        texts.append(("MTEXT", t.dxf.insert.x, t.dxf.insert.y, t.text))
    for t in msp.query("TEXT"):
        texts.append(("TEXT", t.dxf.insert.x, t.dxf.insert.y, t.dxf.text))
    if texts:
        lines.append("")
        lines.append(f"# {len(texts)} MTEXT/TEXT annotations")
        for kind, x, y, txt in sorted(texts, key=lambda r: (r[1], r[2])):
            txt_clean = txt.replace("\n", " ").strip()
            lines.append(f"  {kind:5s}  {x:8.1f},{y:8.1f}  {txt_clean!r}")

    out_path.write_text("\n".join(lines), encoding="utf-8")


def render_pdf(pdf_path: Path, out_path: Path) -> None:
    pdf = pypdfium2.PdfDocument(str(pdf_path))
    page = pdf[0]
    bitmap = page.render(scale=PDF_RENDER_SCALE)
    pil = bitmap.to_pil()
    pil.save(str(out_path), "PNG", optimize=True)


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    dxf_paths: dict[str, Path] = {}
    for p in sorted(SRC_DIR.glob("*.dxf")):
        dxf_paths[p.stem] = p
    if DXF_DIR.exists():
        for p in sorted(DXF_DIR.glob("*.dxf")):
            dxf_paths.setdefault(p.stem, p)
    dxfs = list(dxf_paths.values())
    pdfs = sorted(SRC_DIR.glob("*.pdf"))

    if not dxfs and not pdfs:
        print(
            f"No DXF in {DXF_DIR} and no PDF in {SRC_DIR}.\n"
            "Run scripts/convert_dwg_to_dxf.py first if you have only DWGs.",
            file=sys.stderr,
        )
        return 1

    rendered: list[Path] = []

    for src in dxfs:
        out = OUT_DIR / (src.stem + ".png")
        try:
            render_dxf(src, out)
        except Exception as exc:  # noqa: BLE001 - surface and skip
            print(f"  ! DXF render failed for {src.name}: {exc}", file=sys.stderr)
            continue
        rendered.append(out)
        print(f"  DXF -> PNG: {out.name}")

    for src in pdfs:
        out = OUT_DIR / (src.stem + ".png")
        try:
            render_pdf(src, out)
        except Exception as exc:  # noqa: BLE001
            print(f"  ! PDF render failed for {src.name}: {exc}", file=sys.stderr)
            continue
        rendered.append(out)
        print(f"  PDF -> PNG: {out.name}")

    print(f"\nRendered {len(rendered)} PNG files into {OUT_DIR}")
    return 0 if rendered else 1


if __name__ == "__main__":
    sys.exit(main())
