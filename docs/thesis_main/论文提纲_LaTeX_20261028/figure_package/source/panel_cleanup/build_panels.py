"""Separate existing scientific artwork from figure/subfigure titles.

PDF text is actually removed with transparent redaction (images/paths untouched).
Each panel is a PDF Form XObject placed at its original scale, or a composition
of disjoint source regions. No white rectangles, rasterization of vector art,
numerical recalculation, image inpainting, or regeneration of photographs.
"""
from pathlib import Path
import json, re, hashlib
import fitz

HERE=Path(__file__).resolve().parent
PACKAGE=HERE.parents[1]
SRC=PACKAGE/'source/input_figures'
WORK=HERE/'_build'
OUT=PACKAGE/'panels'
WORK.mkdir(parents=True,exist_ok=True)

CONFIG={
1:dict(file='individual_fireplace.pdf', remove=[], layout='Left column: a over b; center c; right d. Common key underneath.', rows=[['a','c','d'],['b','c','d']], ratios=[.3702,.3366,.2932],
 panels={'a':([3,11,91,57],'Panorama'), 'b':([5,94,92,164],'Room context'), 'c':([93,18.5,173,164],'A29: four corners'), 'd':([174,18.5,243.7,164],'A59: eight corners')},
 extras={'legend':[44,164,204,178]}, caption_note='Existing caption remains applicable. Panels c and d each retain the complete BEV and corresponding 3D layout. Native captions identify A29/A59 and corner counts.'),
2:dict(file='study_design.pdf', remove=[],layout='One connected diagram, with no baked column titles.',rows=[['a']],ratios=[1],panels={'a':([7,22,505,298],'Study workflow')},extras={},caption_note='No subcaption is necessary. The existing main caption describes all three columns; use one native caption below the connected workflow.'),
3:dict(file='observed_corner_geometry.pdf',remove=[],layout='Two rows: panorama/detail, then BEV/3D. Common key underneath.',rows=[['a','b'],['c','d']],ratios=[.61,.39],panels={'a':([1,10,153,87],'Panorama'),'b':([160,29,239,68],'Floor corner'),'c':([24,106,104,192],'Full BEV'),'d':([130,108,242,193],'3D overlay')},extras={'legend':[48,195,198,210]},caption_note='Existing main caption remains applicable; native subcaptions name the four views.'),
5:dict(file='height_resampling_controls_trimmed.pdf',remove=['Balanced local height changes','Same geometry, more clicked pairs'],layout='Two columns, each retaining its 3D control and response curve. Shared key underneath.',rows=[['a','b']],ratios=[.5,.5],panels={'a':([0,15,240,319],'Balanced local height changes'),'b':([260,15,480.5,319],'Collinear resampling')},extras={'legend':[102,319,375,332]},caption_note='Existing main caption remains applicable. All numerical values and curves are unchanged.'),
7:dict(file='bathroom_turn_votes_rev11.pdf',remove=[],layout='One row: support, Team 1, Team 2. Source condition and reference key underneath.',rows=[['a','b','c']],ratios=[.24,.38,.38],panels={'a':([0,18,76,153],'Distinct-person support'),'b':([92,18,214,153],'Team 1 output'),'c':([247,18,369,153],'Team 2 output')},extras={'legend':[0,154,306,168]},caption_note='Existing main caption remains applicable. Removes hidden older panel titles as well as visible revised ones.'),
8:dict(file='upper_boundary_evidence.pdf',remove=[],layout='Three corresponding crops in one row. Shared key underneath.',rows=[['a','b','c']],ratios=[.333333,.333333,.333333],panels={'a':([26,35,166,195],'Upper observations'),'b':([195,35,335,195],'Consensus positions'),'c':([364,35,504,195],'Upper boundary')},extras={'legend':[88,195,439,211]},caption_note='Existing caption retains the left-to-right formation sequence. Inter-panel arrows are omitted from the independent assets; no observations, coordinates or geometry are removed.'),
9:dict(file='profiles_examples_rev11.pdf',remove=['C1 · A55','C2 · A44','C3 · A43'],layout='Three columns, two rows: structural response/ranks/panorama; C1/C2/C3 examples.',rows=[['a','b','c'],['d','e','f']],ratios=[.333333,.333333,.333333],panels={'a':([0,17,176,159],'Structural response'),'b':([182,17,350,159],'Quality ranks'),'c':([359,20,510.2,153],'Difficult panorama'),'d':([42,174.5,166,264.5],'C1: A55'),'e':([205,174.5,329,264.5],'C2: A44'),'f':([368,174.5,492,264.5],'C3: A43')},extras={},caption_note='Existing caption and panel numbering remain applicable. Native d-f captions carry the class/person identifiers; turn counts, Q, and recorded time remain in the artwork as quantitative annotations.'),
11:dict(file='composition_replacement_rev11.pdf',remove=['12-person teams: difficult image','14-person matched replacement'],layout='Left: a with composition plot and replacement design; right: b over c.',rows=[['a','b'],['a','c']],ratios=[.5,.5],panels={'a':([0,27,250,245],'Composition summary and replacement design'),'b':([260,26,510.2,119],'Excess absolute change'),'c':([260,154,510.2,246],'Signed difference')},extras={},caption_note='Keep original a/b/c numbering. The existing caption already gives the 12-person composition setting and separate 14-person replacement setting; explicitly say the membership diagram is below the composition plot, so its shared role for b-c is clear.'),
12:dict(file='profile_mixtures_rev11.pdf',remove=['Mixture minus pure'],layout='One plot with its native figure caption below.',rows=[['a']],ratios=[1],panels={'a':([0,18,243.77,145.5],'Mixture minus pure')},extras={},caption_note='No subcaption is necessary. Existing main caption is sufficient; both the visible title and hidden obsolete (b) title are actually removed.'),
14:dict(file='same_room_structure.pdf',remove=['Complete floor layouts','Local corners'],layout='One row: View 07, View 10, repetition summary. Shared geometry key under first two panels.',rows=[['a','b','c']],ratios=[.37,.36,.27],
 panels={'a':(None,'View 07: panorama, layout and corner detail'),'b':(None,'View 10: panorama, layout and corner detail'),'c':([366,25,510.2,309],'Personal repetition')},extras={'legend':[6,291,270,309]},caption_note='Existing main caption remains applicable. First two panels reassemble disjoint source regions to preserve both complete layouts and Door/Vanity labels without including the neighboring panorama.'),
16:dict(file='doorway_absolute_curves_trimmed.pdf',remove=['Whole-space reference: Q (17 images)','Whole-space reference: output rate'],layout='Two rows: common-reference screening; assigned-target pools. Separate keys for the two comparisons.',rows=[['a','b'],['c','d']],ratios=[.5,.5],panels={'a':([0,13,250,119],'Whole-space reference: Q (17 images)'),'b':([257,13,495,119],'Whole-space reference: output rate'),'c':([0,146,250,252],'Assigned targets: Q'),'d':([257,146,495,252],'Assigned targets: output rate')},extras={'legend_ab':[68,255,237,269],'legend_cd':[241,255,444,269]},caption_note='Existing caption remains applicable. Native subcaptions distinguish the seventeen-image comparison from the one-panorama assigned-target comparison.'),
}

def lines(page):
    for b in page.get_text('dict')['blocks']:
        for line in b.get('lines',[]):
            yield ''.join(s['text'] for s in line['spans']), fitz.Rect(line['bbox'])

def remove_text(page, exact):
    removed=[]
    for text,rect in lines(page):
        norm=text.strip()
        if re.match(r'^\([a-f]\)',norm) or any(norm==s or norm.strip()==s.strip() for s in exact):
            removed.append({'text':text,'bbox':list(rect)})
            page.add_redact_annot(rect,fill=False,cross_out=False)
    if removed:page.apply_redactions(images=0,graphics=0,text=0)
    return removed

def remove_title_background(page, figure):
    """Delete only the two identified obsolete title backdrops.

    The old white rectangle's stroke overlaps the photograph by about one pt.
    Images and text are explicitly excluded from this graphics-only removal.
    No new rectangle is painted and the photograph is not cropped further.
    """
    targets={1:(4.1345,2.8379,55.7321,11.7578),
             3:(2.8748,1.5234,56.6893,10.8264)}
    if figure not in targets:return []
    target=fitz.Rect(targets[figure])
    before=page.get_drawings()
    matched=[(i,d) for i,d in enumerate(before)
             if d.get('fill')==(1.0,1.0,1.0)
             and all(abs(a-b)<.002 for a,b in zip(d['rect'],target))]
    if len(matched)!=1:raise RuntimeError(f'Expected one old title background in Figure {figure}: {matched}')
    i,path=matched[0]
    r=fitz.Rect(path['rect']);pad=path['width']/2+.08
    r.x0-=pad;r.y0-=pad;r.x1+=pad;r.y1+=pad
    page.add_redact_annot(r,fill=False,cross_out=False)
    page.apply_redactions(images=0,graphics=1,text=1)
    after=page.get_drawings()
    if len(after)!=len(before)-1:raise RuntimeError(f'Unexpected graphic removal in Figure {figure}')
    return [{'source_path_index':i,'rect':list(path['rect']),
             'stroke_width':path['width'],'operation':'Deleted original white title backdrop; photograph and all scientific paths retained'}]

def compose(src, parts, width=None, height=None):
    """parts = (clip, output origin), all at original scale."""
    width=width or max(x+clip[2]-clip[0] for clip,(x,y) in parts)
    height=height or max(y+clip[3]-clip[1] for clip,(x,y) in parts)
    dst=fitz.open();p=dst.new_page(width=width,height=height)
    for box,(x,y) in parts:
        r=fitz.Rect(box)
        p.show_pdf_page(fitz.Rect(x,y,x+r.width,y+r.height),src,0,clip=r)
    return dst

def export(doc,path):
    doc.save(path,garbage=4,deflate=True)
    p=doc[0]
    path.with_suffix('.svg').write_text(p.get_svg_image(text_as_path=True))
    p.get_pixmap(dpi=600,alpha=False).save(path.with_suffix('.png'))
    return {'pdf':str(path.relative_to(OUT.parent)),'svg':str(path.with_suffix('.svg').relative_to(OUT.parent)),'png':str(path.with_suffix('.png').relative_to(OUT.parent)),'width_pt':p.rect.width,'height_pt':p.rect.height,'png_dpi':600}

manifest={'source_revision':'3ddad0be3788c1fb558965625d33ba49b1f77838','scope':'11 existing main-text figures; titles separated from unchanged scientific artwork','operations':'Actual PDF text removal with no fill; vector-preserving cropping/placement; no numerical recomputation; original photographs preserved at source resolution within PDF. 600 dpi PNG is a compatibility export, not additional photographic information.','figures':[]}
for n,cfg in CONFIG.items():
    dest=OUT/f'fig{n:02}';dest.mkdir(parents=True,exist_ok=True)
    source=SRC/cfg['file'];d=fitz.open(source)
    removed=remove_text(d[0],cfg['remove'])
    removed_background=remove_title_background(d[0],n)
    cleaned=WORK/f'fig{n:02}_title_free.pdf';d.save(cleaned,garbage=4,deflate=True)
    # Reopen for canonical import of the cleaned page.
    d.close();d=fitz.open(cleaned)
    fig={'figure':n,'source_file':cfg['file'],'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'layout':cfg['layout'],'recommended_rows':cfg['rows'],'column_width_ratios':cfg['ratios'],'caption_note':cfg['caption_note'],'scale_note':('Keep panels c and d at equal physical height to preserve the shared BEV scale.' if n==1 else 'Keep panels b and c at equal physical width/height; their canvas sizes are equal.' if n==7 else 'Keep panels d/e/f at equal physical width; their canvas sizes are equal.' if n==9 else 'Use the same source-to-paper scale for shared-scale panels.'),'removed_title_text':removed,'removed_obsolete_title_background':removed_background,'panels':[],'extras':[]}
    for label,(box,title) in cfg['panels'].items():
        if n==14 and label=='a':
            result=compose(d,[([0,25,173,129],(0,0)),([0,147,193,285],(0,120))],width=193,height=258)
        elif n==14 and label=='b':
            # The left-view Vanity label extends into this source region. Its
            # text is not part of view 10, so remove it only in this panel copy.
            db=fitz.open(cleaned)
            for txt,rect in lines(db[0]):
                if txt.strip()=='Vanity' and rect.x0<200:
                    db[0].add_redact_annot(rect,fill=False,cross_out=False)
            db[0].apply_redactions(images=0,graphics=0,text=0)
            result=compose(db,[([174,25,349,129],(0,0)),([176,147,360,285],(0,120))],width=184,height=258)
        else:result=compose(d,[(box,(0,0))])
        item=export(result,dest/f'{label}.pdf');item.update({'id':label,'native_subcaption':title,'source_crop':box})
        fig['panels'].append(item)
        result.close()
    for label,box in cfg['extras'].items():
        result=compose(d,[(box,(0,0))]);item=export(result,dest/f'{label}.pdf');item.update({'id':label,'role':'Shared legend/conditions; not a panel title','source_crop':box});fig['extras'].append(item);result.close()
    fig['verification']={'all_source_figures_visually_reviewed':True,'actual_title_text_removed':True,'vectors_preserved':True,'result_visual_review':'pending'}
    manifest['figures'].append(fig)
    print('exported',n,len(fig['panels']),len(fig['extras']))
(WORK/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
(OUT.parent/'panel_cleanup_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
print('manifest',WORK/'manifest.json')
