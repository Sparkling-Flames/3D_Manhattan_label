"""Reflow the formal height-control panels at their unchanged LaTeX sizes.

All geometry and scientific curves are copied from the supplied vector PDF.
Only text objects are removed and re-typeset. No index, geometry or curve is
computed, interpolated or resampled. Run this after the general panel splitter.
"""
from pathlib import Path
import hashlib
import json
import fitz
from matplotlib import font_manager

ROOT = Path(__file__).resolve().parent
PACKAGE = ROOT.parents[1]
SOURCE = PACKAGE / 'source/input_figures/height_resampling_controls_trimmed.pdf'
OUT = PACKAGE / 'panels/fig05'
OUT.mkdir(parents=True, exist_ok=True)
FONT = Path(font_manager.findfont('DejaVu Sans'))
FT = fitz.Font(fontfile=str(FONT))
BLUE = (0.0, 0.4470588267, 0.6980392337)
ORANGE = (0.8352941275, 0.3686274588, 0.0)
DARK = (.10, .12, .14)
MM = 72 / 25.4
HEIGHT = 242.0
source = fitz.open(SOURCE)
page = source[0]
original_text = page.get_text()
original_drawings = page.get_drawings()
assert all(s in original_text for s in ['Q = 70.09', '86.96', '70.09 throughout', '16 pairs'])
page.add_redact_annot(page.rect, fill=None, cross_out=False)
page.apply_redactions(images=0, graphics=0, text=0)
assert not page.get_text().strip()
assert [{k:v for k,v in d.items() if k!='seqno'} for d in page.get_drawings()] == [{k:v for k,v in d.items() if k!='seqno'} for d in original_drawings]
records = []

def new(w, h):
    d = fitz.open()
    p = d.new_page(width=w, height=h)
    p.insert_font(fontname='DV', fontfile=str(FONT))
    return d, p

def text(p, x, baseline, value, size=8.0, align='left', color=DARK, rotate=0):
    width = FT.text_length(value, fontsize=size)
    if rotate == 0:
        if align == 'center': x -= width / 2
        elif align == 'right': x -= width
    elif align == 'center':
        baseline += width / 2
    p.insert_text((x, baseline), value, fontname='DV', fontsize=size,
                  color=color, rotate=rotate)

def copy(p, clip, dest, *, isotropic=False):
    clip, dest = fitz.Rect(clip), fitz.Rect(dest)
    if isotropic:
        assert abs(dest.width / clip.width - dest.height / clip.height) < 1e-8
    p.show_pdf_page(dest, source, 0, clip=clip, keep_proportion=False)
    return lambda x, y: (dest.x0 + (x-clip.x0) * dest.width/clip.width,
                         dest.y0 + (y-clip.y0) * dest.height/clip.height)

def save(doc, name):
    # Review only new visible text; all source text was removed first.
    p = doc[0]
    boxes = []
    for b in p.get_text('dict')['blocks']:
        for line in b.get('lines', []):
            for span in line['spans']:
                r = fitz.Rect(span['bbox'])
                assert p.rect.contains(r), (name, span['text'], r)
                assert span['size'] >= 7.99
                boxes.append({'text': span['text'], 'font_pt': span['size'], 'bbox': list(r)})
    doc.subset_fonts()
    target = OUT / (name+'.pdf')
    doc.save(target, garbage=4, deflate=True)
    doc.close()
    with fitz.open(target) as doc:
        p = doc[0]
        p.get_pixmap(dpi=600, alpha=False).save(target.with_suffix('.png'))
        target.with_suffix('.svg').write_text(p.get_svg_image(text_as_path=True))
        panel_rect=p.rect
    records.append({'panel': name, 'file': str(target.relative_to(PACKAGE)),
                    'width_pt': panel_rect.width, 'height_pt': panel_rect.height,
                    'text': boxes})

configs = [
    ('a', 70.70*MM, [(14,33,92,115), (133,33,211,115)], [12.0,114.0],
     [(47.88,'Reference: 3 m'),(149.88,'Opposite shifts: ±20%')],
     (30,163,215,295), [(0,86),(10,87),(20,88),(30,89),(40,90)],
     'Opposite height shift (%)'),
    ('b', 64.96*MM, [(274,33,352,115), (393,33,471,115)], [5.0,105.0],
     [(40.88,'4 pairs'),(140.88,'16 pairs')],
     (296,163,480,295), [(4,108),(5,109),(8,110),(16,111)],
     'Top/bottom point pairs'),
]
for name,w,geometry,origins,labels,chart,xticks,xlabel in configs:
    d,p = new(w,HEIGHT)
    for clip,x in zip(geometry,origins):
        # All four 3D controls share one physical scale and keep their aspect.
        copy(p,clip,(x,3,x+78*.92,3+82*.92),isotropic=True)
    for x,label in labels: text(p,x,91,label,align='center')
    dest = fitz.Rect(28,102,w-3,214)
    pt = copy(p,chart,dest)
    for value,index in xticks:
        x,_ = pt(original_drawings[index]['rect'].x0,0)
        text(p,x,225,str(value),align='center')
    for value,index in [(0,91),(25,93),(50,95),(75,97),(100,99)]:
        _,y = pt(0,original_drawings[index]['rect'].y0)
        text(p,28.8,y+2.8,str(value),align='right')
    text(p,8.5,(102+214)/2,'Index value',rotate=90,align='center')
    text(p,(dest.x0+dest.x1)/2,238,xlabel,align='center')
    if name=='a':
        x,y=pt(136.341949,193.7)
        text(p,x,y,'Q = 70.09',color=BLUE)
    else:
        x,y=pt(434.02835,179.3)
        text(p,x,y,'86.96',color=ORANGE)
        x,y=pt(361.312408,217.8)
        text(p,x,y,'70.09 throughout',color=BLUE)
    save(d,name)

# Keep both full metric names. Two compact rows fit the unchanged 84 mm
# legend width with 8 pt type; reduced panel whitespace offsets this height.
d,p = new(84*MM,23)
for value,color,y,dash in [('Geometric quality Q',BLUE,8.5,None),
                          ('Corner-mean prism IoU × 100',ORANGE,20.3,'[4.44 1.92] 0')]:
    tw=FT.text_length(value,fontsize=8)
    x=(p.rect.width-(20+6+tw))/2
    p.draw_line((x,y-2.7),(x+20,y-2.7),color=color,width=1.2,dashes=dash)
    text(p,x+26,y,value,color=DARK)
save(d,'legend')

(ROOT/'verification.json').write_text(json.dumps({
    'source':str(SOURCE.relative_to(PACKAGE)),
    'source_sha256':hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
    'source_vector_paths_before_text_removal':len(original_drawings),
    'source_vector_paths_after_text_removal':len(page.get_drawings()),
    'source_vector_paths_exactly_unchanged':[{k:v for k,v in d.items() if k!='seqno'} for d in page.get_drawings()]==[{k:v for k,v in d.items() if k!='seqno'} for d in original_drawings],
    'scientific_data_recomputed':False,
    'geometry_scale_common_isotropic':.92,
    'source_curve_paths_copied_without_reconstruction':True,
    'final_widths_mm':{'a':70.70,'b':64.96,'legend':84},
    'panel_height_mm':HEIGHT/MM,
    'minimum_regular_text_pt':8,
    'subcaptions_in_latex':True,
    'panels':records,
},ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'panels':3,'minimum_text_pt':8,'vector_paths_preserved':len(original_drawings),'data_recomputed':False}))
