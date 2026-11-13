"""Rebuild the formal one-row panels for figures 11 and 16.

The scientific paths are copied from the frozen, complete source PDFs. Only
text is removed before axis labels and saved numerical annotations are laid
out at the physical size used by the current, unchanged LaTeX files.
No statistical result, curve, point, error bar or denominator is recomputed.
"""
from pathlib import Path
import hashlib
import json

import fitz
import numpy as np
from matplotlib import font_manager

HERE = Path(__file__).resolve().parent
PACKAGE = HERE.parents[1]
SRC = PACKAGE / "source/input_figures"
OUT = PACKAGE / "panels"
FONT = Path(font_manager.findfont("DejaVu Sans"))
BOLD = Path(font_manager.findfont(font_manager.FontProperties(family="DejaVu Sans", weight="bold")))
INK = (.08, .10, .12)
SECONDARY = (.30, .34, .37)
REPORT = {"scope": "fig11 and fig16 formal panels only; no TeX edits", "sources": [], "panels": []}


def graphics_only(name):
    path = SRC / name
    doc = fitz.open(path)
    p = doc[0]
    before = p.get_drawings()
    p.add_redact_annot(p.rect, fill=None, cross_out=False)
    p.apply_redactions(images=0, graphics=0, text=0)
    after = p.get_drawings()
    # This check protects every source vector, including scientific marks.
    assert len(before) == len(after)
    max_coordinate_error = 0.0
    for a, b in zip(before, after):
        assert a["type"] == b["type"] and len(a["items"]) == len(b["items"])
        for sa, sb in zip(a["items"], b["items"]):
            assert sa[0] == sb[0]
            for va, vb in zip(sa[1:], sb[1:]):
                aa, bb = np.asarray(va), np.asarray(vb)
                err = float(np.max(np.abs(aa - bb)))
                max_coordinate_error = max(max_coordinate_error, err)
                assert np.allclose(aa, bb, atol=1e-3, rtol=0)
        for key in ("width", "color", "fill", "fill_opacity", "stroke_opacity", "closePath"):
            assert a[key] == b[key], (key, a[key], b[key])
    assert not p.get_text().strip()
    REPORT["sources"].append({"file": str(path.relative_to(PACKAGE)),
                              "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                              "drawing_count": len(before),
                              "max_coordinate_roundtrip_error_pt": max_coordinate_error,
                              "all_vector_paths_preserved_after_text_removal": True})
    return doc


def page(w, h):
    d = fitz.open()
    p = d.new_page(width=w, height=h)
    p.insert_font(fontname="DV", fontfile=str(FONT))
    p.insert_font(fontname="DVB", fontfile=str(BOLD))
    return d, p


def text(p, x, y, s, size=8, align="left", color=INK, bold=False, rotate=0):
    f = fitz.Font(fontfile=str(BOLD if bold else FONT))
    width = f.text_length(s, fontsize=size)
    if rotate == 0:
        if align == "center":
            x -= width / 2
        elif align == "right":
            x -= width
    elif align == "center":
        y += width / 2
    p.insert_text((x, y), s, fontname="DVB" if bold else "DV", fontsize=size,
                  color=color, rotate=rotate)


def place(p, doc, clip, dest):
    clip, dest = fitz.Rect(clip), fitz.Rect(dest)
    p.show_pdf_page(dest, doc, 0, clip=clip, keep_proportion=False)

    def xy(x, y):
        return (dest.x0 + (x - clip.x0) * dest.width / clip.width,
                dest.y0 + (y - clip.y0) * dest.height / clip.height)
    return xy


def save(doc, fig, panel, clip, dest):
    path = OUT / f"fig{fig:02}" / f"{panel}.pdf"
    path.parent.mkdir(parents=True, exist_ok=True)
    doc.subset_fonts()
    doc.save(path, garbage=4, deflate=True)
    doc.close()
    with fitz.open(path) as check:
        p = check[0]
        p.get_pixmap(dpi=600, alpha=False).save(path.with_suffix(".png"))
        path.with_suffix(".svg").write_text(p.get_svg_image(text_as_path=True))
        spans = [s for b in p.get_text("dict")["blocks"] for l in b.get("lines", []) for s in l["spans"]]
        clipped = [{"text": s["text"], "bbox": list(s["bbox"])} for s in spans
                   if not (p.rect + (-.1, -.1, .1, .1)).contains(fitz.Rect(s["bbox"]))]
        assert not clipped, (str(path), clipped)
        assert not p.get_images()
        REPORT["panels"].append({"file": str(path.relative_to(PACKAGE)),
                                  "source_crop": list(clip), "destination_crop": list(dest),
                                  "width_pt": p.rect.width, "height_pt": p.rect.height,
                                  "min_text_pt": min(s["size"] for s in spans),
                                  "max_text_pt": max(s["size"] for s in spans),
                                  "all_text_within_page": True, "raster_images": 0})


def composition():
    source = graphics_only("composition_replacement_rev11.pdf")
    d, p = page(170, 132)
    clip, dest = (30.5, 30, 242, 92.5), (30, 12, 168, 87)
    xy = place(p, source, clip, dest)
    counts = ["1/11/0", "1/10/1", "1/9/2", "1/8/3", "1/7/4"]
    teams = [10, 224, 420, 224, 28]
    tick_x = [52.55662536621094, 94.86927795410156, 137.18191528320312,
              179.49456787109375, 221.8072052001953]
    for x, count, n in zip(tick_x, counts, teams):
        xx, _ = xy(x, 0)
        text(p, xx, 101, count, 7.3, align="center")
        text(p, xx, 113, str(n), 7.3, align="center", color=SECONDARY)
    for v, y in [(40, 81.86567687988281), (60, 65.8736572265625),
                 (80, 49.881629943847656), (100, 33.88960266113281)]:
        text(p, 26, xy(0, y)[1] + 2.5, str(v), 7.5, align="right")
    text(p, 8, 48, "Team Q", 8, align="center", rotate=90)
    text(p, 17, 113, "n", 7.3, color=SECONDARY)
    text(p, 100, 128, "C1 / C2 / C3 counts", 8, align="center")
    save(d, 11, "a", clip, dest)

    # The source PDF's exact axis positions are retained; these numerical
    # labels are copied from its text, not recomputed from personnel data.
    for name, clip, mean, positive in [
            ("b", (296.5, 44.04062, 505, 93.54062), "+3.441", "50/69"),
            ("c", (296.5, 171.46380, 505, 220.96380), "+6.712", "65/69")]:
        d, p = page(170, 132)
        dest = (13, 25, 168, 87)
        xy = place(p, source, clip, dest)
        text(p, 90, 15, f"Mean {mean}", 8.6, align="center", bold=True)
        for v, x in [(-20, 300.81243896484375), (0, 363.23480224609375),
                     (20, 425.6571044921875), (40, 488.0794677734375)]:
            text(p, xy(x, 0)[0], 101, str(v).replace("-", "−"), 7.5, align="center")
        text(p, 168, 114, positive + " images positive", 7.7, align="right")
        text(p, 90, 128, "Difference (Q points)", 8, align="center")
        save(d, 11, name, clip, dest)
    source.close()


def doorway():
    source = graphics_only("doorway_absolute_curves_trimmed.pdf")
    # Saved scientific source coordinates, including original short tick marks.
    # In (a,b) every curve uses the same 17-image whole-space comparison.
    # In (c,d) members and references differ across assigned target pools.
    specs = [
        ("a", (30.870079, 15.685028, 223.627350, 95.469666), "Q",
         [(3, 41.9954071), (6, 89.0426636), (10, 151.7723389), (14, 214.5020142)],
         [("37.5", 75.6652069), ("40.0", 57.4038239), ("42.5", 39.1424408), ("45.0", 20.8810425)]),
        ("b", (300.325409, 15.685028, 493.082672, 95.469666), "Complete (%)",
         [(3, 311.4507446), (6, 358.4979858), (10, 421.2276611), (14, 483.9573364)],
         [("60", 83.4667969), ("70", 63.9682159), ("80", 44.4696198), ("90", 24.9710388)]),
        ("c", (30.870079, 148.522446, 223.627350, 228.307083), "Q",
         [(3, 41.9954071), (6, 85.1220627), (9, 128.2487183), (12, 171.3753662), (15, 214.5020142)],
         [("20", 216.4545288), ("40", 198.8209076), ("60", 181.1872864), ("80", 163.5536499)]),
        ("d", (300.325409, 148.522446, 493.082672, 228.307083), "Complete (%)",
         [(3, 311.4507446), (6, 354.5773926), (9, 397.7040405), (12, 440.8306885), (15, 483.9573364)],
         [("70", 217.1025696), ("80", 195.5726013), ("90", 174.0426331), ("100", 152.5126495)])]
    for name, clip, ylab, xticks, yticks in specs:
        d, p = page(126, 122)
        dest = (33, 8, 124, 94)
        xy = place(p, source, clip, dest)
        for value, x in xticks:
            text(p, xy(x, 0)[0], 106, str(value), 7.5, align="center")
        for value, y in yticks:
            text(p, 30, xy(0, y)[1] + 2.5, value, 7.5, align="right")
        text(p, 78, 119, "Annotators", 8, align="center")
        text(p, 7.5, 51, ylab, 8, align="center", rotate=90)
        save(d, 16, name, clip, dest)
    source.close()
    # The separate legend_ab and legend_cd PDFs are already legible at their
    # native TeX widths and remain byte-identical to the accepted version.


if __name__ == "__main__":
    composition()
    doorway()
    (HERE / "layout_verification.json").write_text(json.dumps(REPORT, ensure_ascii=False, indent=2))
    print(json.dumps({"panels_written": len(REPORT["panels"]),
                      "fig11_height_pt": 132, "fig16_height_pt": 122,
                      "scientific_paths_preserved": True}, indent=2))
