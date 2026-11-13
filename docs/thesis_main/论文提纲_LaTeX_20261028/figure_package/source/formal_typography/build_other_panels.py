"""Rebuild the formal Fig. 02, 09, and 14 panels at their fixed TeX widths.

Fig. 02 is a code-drawn diagram with the original information relationships.
Fig. 09/14 use the frozen, existing PDF paths and photographs. Only PDF text
objects are removed before fresh, embedded-font labels are added. Scientific
paths are never rasterized or recomputed. Fig. 14a's detail is translated 8 pt
left and Fig. 14c's plot 13 pt up, without rescaling or changing plotted values.
Original inputs are retained in
input_panels so rerunning this script cannot accumulate edits.

Run from any working directory: python3 build_other_panels.py
Requires PyMuPDF, NumPy, and DejaVu Sans TTF fonts (system or Matplotlib data).
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import fitz
import numpy as np

HERE = Path(__file__).resolve().parent
PACKAGE = HERE.parents[1]
INPUT = HERE / "input_panels"
OUT = PACKAGE / "panels"
QA = HERE / "other_panels_qa.json"


def font_path(bold=False):
    name = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
    candidates = [Path("/usr/share/fonts/truetype/dejavu") / name]
    try:
        import matplotlib
        candidates.append(Path(matplotlib.get_data_path()) / "fonts/ttf" / name)
    except ImportError:
        pass
    for path in candidates:
        if path.is_file():
            return path
    raise FileNotFoundError(f"Install DejaVu Sans or Matplotlib to provide {name}")


REGULAR = font_path()
BOLD = font_path(True)
FONT = fitz.Font(fontfile=str(REGULAR))
FONT_BOLD = fitz.Font(fontfile=str(BOLD))
BLACK = (0.14, 0.17, 0.19)
GRAY = (0.43, 0.49, 0.53)
BLUE = (0.0, 0.4470588, 0.6980392)
ORANGE = (0.8352941, 0.3686275, 0.0)
GREEN = (0.0, 0.54, 0.43)


def setup(page):
    page.insert_font(fontname="FRegular", fontfile=str(REGULAR))
    page.insert_font(fontname="FBold", fontfile=str(BOLD))


def text(page, value, x, y, size, color=BLACK, bold=False, align="left", rotate=0):
    """Write a baseline at x,y, with explicit bounds instead of silent shrinking."""
    font = FONT_BOLD if bold else FONT
    length = font.text_length(value, fontsize=size)
    if rotate == 0:
        if align == "center":
            x -= length / 2
        elif align == "right":
            x -= length
    elif rotate == 90 and align == "center":
        y += length / 2
    page.insert_text((x, y), value, fontname="FBold" if bold else "FRegular",
                     fontsize=size, color=color, rotate=rotate)


def spans(page):
    return [(line["dir"], span)
            for block in page.get_text("dict", clip=page.rect)["blocks"]
            for line in block.get("lines", []) for span in line["spans"]
            if span["text"].strip()]


def remove_visible_text(doc):
    page = doc[0]
    for _, span in spans(page):
        page.add_redact_annot(fitz.Rect(span["bbox"]), fill=False, cross_out=False)
    page.apply_redactions(images=0, graphics=0, text=0)


def original(path):
    return fitz.open(INPUT / path)


def clean_original(path):
    doc = original(path)
    remove_visible_text(doc)
    return doc


def newpage(width, height):
    doc = fitz.open()
    page = doc.new_page(width=width, height=height)
    setup(page)
    return doc, page


def paste(page, doc, clip=None, x=0, y=0):
    clip = fitz.Rect(clip) if clip else doc[0].rect
    page.show_pdf_page(fitz.Rect(x, y, x+clip.width, y+clip.height), doc, 0, clip=clip)


def physical_factor(width_mm, pdf_width):
    return width_mm * 72 / 25.4 / pdf_width


def export(doc, relative, width_mm):
    path = OUT / relative
    doc.subset_fonts()
    doc.save(path, garbage=4, deflate=True)
    page = doc[0]
    path.with_suffix(".svg").write_text(page.get_svg_image(text_as_path=True), encoding="utf-8")
    page.get_pixmap(dpi=600, alpha=False).save(path.with_suffix(".png"))
    factor = physical_factor(width_mm, page.rect.width)
    labels = [{"text": s["text"], "finished_pt": round(s["size"]*factor, 3),
               "bbox": list(s["bbox"])} for _, s in spans(page)]
    overflow = [s for _, s in spans(page)
                if not (page.rect + (-0.05, -0.05, 0.05, 0.05)).contains(fitz.Rect(s["bbox"]))]
    if overflow:
        raise RuntimeError(f"Text outside {relative}: {[s['text'] for s in overflow]}")
    return {"panel": relative, "tex_width_mm": width_mm,
            "size_pt": [page.rect.width, page.rect.height], "labels": labels,
            "embedded_fonts": True, "png_dpi": 600}


def image_digests(doc):
    return sorted({hashlib.sha256(doc.extract_image(x[0])["image"]).hexdigest()
                   for x in doc[0].get_images(full=True)})


def check_graphics(source, result, source_clip=None, result_clip=None):
    """Compare the text-free scientific regions, allowing rasterizer rounding."""
    clean = fitz.open(stream=result.tobytes(), filetype="pdf")
    remove_visible_text(clean)
    a = source[0].get_pixmap(matrix=fitz.Matrix(2, 2), clip=source_clip, alpha=False)
    b = clean[0].get_pixmap(matrix=fitz.Matrix(2, 2), clip=result_clip, alpha=False)
    if (a.width, a.height) != (b.width, b.height):
        raise RuntimeError("Scientific-region size changed")
    aa = np.frombuffer(a.samples, np.uint8).astype(np.int16)
    bb = np.frombuffer(b.samples, np.uint8).astype(np.int16)
    delta = abs(aa-bb)
    max_diff = int(delta.max())
    changed = float((delta > 2).mean())
    if changed > 0.00002:
        raise RuntimeError(f"Unexpected scientific graphics difference: {changed:.6f}")
    return {"max_channel_difference": max_diff,
            "channel_fraction_difference_gt_2": changed,
            "scientific_paths_preserved": True}


def arrow(page, start, end, color=GRAY, width=0.65):
    page.draw_line(start, end, color=color, width=width)
    dx, dy = end[0]-start[0], end[1]-start[1]
    norm = math.hypot(dx, dy)
    ux, uy = dx/norm, dy/norm
    tip = fitz.Point(*end)
    p1 = fitz.Point(end[0]-3.5*ux+1.65*uy, end[1]-3.5*uy-1.65*ux)
    p2 = fitz.Point(end[0]-3.5*ux-1.65*uy, end[1]-3.5*uy+1.65*ux)
    shape = page.new_shape()
    shape.draw_polyline([tip, p1, p2, tip])
    shape.finish(color=color, fill=color, width=0.25)
    shape.commit()


def box(page, rect, title, body, color=BLACK, title_size=8, body_size=7.5):
    r = fitz.Rect(rect)
    page.draw_rect(r, color=color, width=0.75)
    if FONT_BOLD.text_length(title,fontsize=title_size)>r.width-14:
        raise RuntimeError(f"Diagram heading does not fit: {title}")
    text(page, title, r.x0+7, r.y0+13, title_size, color=color, bold=True)
    y = r.y0+27
    for line in body:
        wrapped=[];current=""
        for word in line.split():
            candidate=(current+" "+word).strip()
            if current and FONT.text_length(candidate,fontsize=body_size)>r.width-14:
                wrapped.append(current);current=word
            else:current=candidate
        if current:wrapped.append(current)
        for item in wrapped:
            if y+2>r.y1:raise RuntimeError(f"Diagram body too tall: {title}")
            text(page,item,r.x0+7,y,body_size)
            y+=10.2


def build02():
    doc, page = newpage(145*72/25.4, 292)
    box(page, (5, 5, 129, 48), "Scene and task target",
        ["Ordinary and boundary-case", "analyses"])
    box(page, (5, 59, 63, 102), "Manual", ["From scratch"], BLUE)
    box(page, (71, 59, 129, 102), "Semi", ["Edit a proposal"], ORANGE)
    box(page, (5, 110, 129, 167), "Submitted observations",
        ["Extent and turns", "Paired endpoints", "Reports, edits, person-time"])
    box(page, (150, 25, 274, 80), "Geometric quality",
        ["Floor, boundary, direction, height", "Components and overall Q"], BLUE)
    box(page, (150, 124, 274, 179), "Structural consensus",
        ["Identity, support, position", "Connected layout", "Output status"], GREEN)
    box(page, (5, 191, 274, 238), "Controlled offline comparisons",
        ["Within images: fix target; vary team size or members.",
         "Across views: retain room relations and comparison support."])
    box(page, (288, 5, 406, 51), "RQ1 Individuals", ["Across task conditions"])
    box(page, (288, 66, 406, 112), "RQ2 Group size", ["Add people within a pool"])
    box(page, (288, 127, 406, 173), "RQ3 Team composition", ["Vary profiles and members"])
    box(page, (288, 188, 406, 234), "RQ4 Cross-view", ["Repetition and transfer"])
    arrow(page, (34,48), (34,59)); arrow(page, (100,48), (100,59))
    arrow(page, (34,102), (34,110)); arrow(page, (100,102), (100,110))
    arrow(page, (129,130), (150,63), BLUE)
    arrow(page, (129,151), (150,151), GREEN)
    # Scoreable consensus outputs enter the quality measurement; Q is not a
    # prerequisite for forming consensus. Individual observations enter Q too.
    arrow(page, (157,124), (157,80), BLUE)
    text(page, "Scorable layouts", 166, 104, 7, color=BLUE)
    text(page, "Reviewed target reference", 212, 12, 7, color=GRAY, align="center")
    arrow(page, (212,15), (212,25))
    arrow(page, (67,167), (67,191)); arrow(page, (212,179), (212,191))
    page.draw_line((281,28), (281,211), color=GRAY, width=0.65)
    arrow(page, (274,52), (281,52)); arrow(page, (274,152), (281,152))
    arrow(page, (274,216), (281,211))
    for y in (28,89,150,211): arrow(page, (281,y), (288,y))
    arrow(page, (139.5,238), (139.5,251))
    page.draw_rect((5,253,406,289), color=None, fill=(0.95,0.96,0.97))
    text(page, "Evidence for annotation organisation and review", 13, 266, 8.3, bold=True)
    text(page, "Clarify target rules; inspect disputed structures; use history and feedback", 13, 278, 7.5)
    text(page, "to guide re-annotation.", 13, 287, 7.5)
    record = export(doc, "fig02/a.pdf", 145)
    record["scope"] = "Code-drawn diagram; original method/data dependencies retained"
    return record


def build09():
    records = []
    mm = 150*.323
    # Equal finished heights align the existing native TeX subcaptions.
    finished_height = 43*72/25.4
    for panel in ("a", "b", "c"):
        rel = f"fig09/{panel}.pdf"
        src = clean_original(rel)
        raw = original(rel)
        width = src[0].rect.width
        factor = physical_factor(mm, width)
        doc, page = newpage(width, finished_height/factor)
        dy = 4 if panel in ("a", "b") else 0
        paste(page, src, x=0, y=dy)
        if panel == "a":
            for _, s in spans(raw[0]):
                value = s["text"]
                if value == "Relative Q":
                    text(page, value, 11.2, 53+dy, 8/factor, rotate=90, align="center")
                elif value == "Turns: difficult − easy":
                    text(page, value, 97.18, 131+dy, 8/factor, align="center")
                elif s["origin"][1] > 110:
                    text(page, value, (s["bbox"][0]+s["bbox"][2])/2,
                         s["origin"][1]+dy, 7.5/factor, align="center")
                else:
                    text(page, value, 42.7, s["origin"][1]+dy,
                         7.5/factor, align="right")
        elif panel == "b":
            for direction, s in spans(raw[0]):
                value = s["text"]
                if direction == (1.0, 0.0) and value in ("0.0", "0.5", "1.0"):
                    if s["origin"][0] > 35:
                        text(page, value, (s["bbox"][0]+s["bbox"][2])/2,
                             s["origin"][1]+dy, 7.5/factor, align="center")
                    else:
                        text(page, value, 41.14, s["origin"][1]+dy,
                             7.5/factor, align="right")
            text(page, "Mean relative rank:", 99.45, 134, 8/factor, align="center")
            text(page, "non-difficult images", 99.45, 146, 8/factor, align="center")
            text(page, "Mean relative rank:", 10.7, 55+dy, 8/factor, rotate=90, align="center")
            text(page, "difficult images", 22.6, 55+dy, 8/factor, rotate=90, align="center")
            text(page, "A2: 43 / 15 images", 72, 96.5, 7/factor)
        else:
            for i, value in enumerate(("C1: more simplifying", "C2: typical expression", "C3: more turn-retaining")):
                text(page, value, 8, 90.6+10.9*i, 8/factor)
            text(page, "Reference", 27, 127, 7.5/factor)
            text(page, "Short wall", 109, 127, 7.5/factor)
        before = src[0].rect
        after = fitz.Rect(0,dy,width,dy+before.height)
        check = check_graphics(src, doc, before, after)
        check["photograph_bytes_unchanged"] = image_digests(raw) == image_digests(doc)
        record = export(doc, rel, mm)
        record["verification"] = check
        records.append(record)
    return records


def build14():
    records = []
    for panel, mm in (("a",150*.3592),("b",150*.3424)):
        rel = f"fig14/{panel}.pdf"
        src = clean_original(rel)
        raw = original(rel)
        width, height = src[0].rect.width, src[0].rect.height
        factor = physical_factor(mm,width)
        doc,page = newpage(width,height)
        if panel=="a":
            paste(page,src,(0,0,width,120),0,0)
            paste(page,src,(0,120,110,height),0,120)
            paste(page,src,(110,120,width,height),102,120)
        else:
            paste(page,src)
        text(page,"A40: 16/16",4.08,97.7132,8/factor,color=BLUE)
        text(page,"A41: 9/16" if panel=="a" else "A41: 12/16",96,97.7132,8/factor,color=ORANGE)
        if panel=="a":
            text(page,"Door",81.5,159.1794,7/factor,color=(.03137,.29412,.54118))
            text(page,"Vanity",159,175.3624,7/factor,color=(.03137,.29412,.54118))
        else:
            text(page,"Door",98,142.1712,7/factor,color=(.03137,.29412,.54118))
            text(page,"Vanity",155.5,167.8032,7/factor,color=(.03137,.29412,.54118))
        if panel=="a":
            checks=[check_graphics(src,doc,fitz.Rect(0,0,width,120),fitz.Rect(0,0,width,120)),
                    check_graphics(src,doc,fitz.Rect(0,120,102,height),fitz.Rect(0,120,102,height)),
                    check_graphics(src,doc,fitz.Rect(110,120,width,height),fitz.Rect(102,120,width-8,height))]
            check={"scientific_regions":checks,"scientific_paths_preserved":True,
                   "detail_translation_pt":[-8,0]}
        else:
            check=check_graphics(src,doc)
        check["photograph_bytes_unchanged"] = image_digests(raw)==image_digests(doc)
        record=export(doc,rel,mm)
        record["verification"]=check
        record["label_note"]="Counts unchanged; repeated word 'turns' omitted because existing caption defines effective/reference turns."
        records.append(record)
    rel="fig14/c.pdf"
    raw=original(rel);src=clean_original(rel)
    width=src[0].rect.width;mm=150*.2684
    factor=physical_factor(mm,width)
    doc,page=newpage(width,258)
    scientific_clip=fitz.Rect(0,39,width,219)
    paste(page,src,scientific_clip,0,26)
    text(page,"15 view pairs in 5 buildings",width/2,12,8/factor,align="center")
    text(page,"Short edges in both references",width/2,25,7/factor,align="center")
    for _,s in spans(raw[0]):
        value=s["text"]
        if value.startswith("Building"):
            text(page,value,12.67,s["origin"][1]-13,7.5/factor,color=(.294,.333,.388))
        elif value in ("20","40","60","80","100"):
            text(page,value,(s["bbox"][0]+s["bbox"][2])/2,213,7.5/factor,align="center")
    text(page,"Same simplification state (%)",width/2,226,7.5/factor,align="center")
    page.draw_rect((15.68,235.5,20.68,240.5),color=(.604,.643,.675),fill=(.604,.643,.675),width=1)
    page.draw_circle((18.18,251),2.5,color=(.153,.2,.224),fill=(.153,.2,.224),width=1)
    text(page,"Different-person pairs",28.58,241,8/factor)
    text(page,"Same-person pairs",28.58,254,8/factor)
    check=check_graphics(src,doc,scientific_clip,fitz.Rect(0,26,width,206))
    record=export(doc,rel,mm)
    record["verification"]=check
    record["geometry_transform"]="Scientific plot translated (0,-13 pt), no rescaling; legend symbols redrawn outside data region."
    records.append(record)
    return records


def main():
    records=[build02()]+build09()+build14()
    payload={"scope":"Formal typography for Fig02, Fig09(a-c), Fig14(a-c); no TeX changes",
             "input_files":[{"path":str(p.relative_to(HERE)),"sha256":hashlib.sha256(p.read_bytes()).hexdigest()}
                            for p in sorted(INPUT.glob("fig*/*.pdf")) if p.parent.name in {"fig02","fig09","fig14"}],
             "panels":records}
    QA.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8")
    for record in records:
        sizes=sorted({x["finished_pt"] for x in record["labels"]})
        print(record["panel"],"finished font sizes:",sizes)


if __name__=="__main__":
    main()
