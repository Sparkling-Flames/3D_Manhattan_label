"""Offline point-overlay review sheets and deterministic replay verification."""
import argparse
import html
import json
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

from . import simulate_annotators as base
from .difficulty_wild_inputs import load_inputs


def verify_replay(first, second):
    first,second=Path(first),Path(second)
    required=['simulations.jsonl','label_studio_synthetic.json','difficulty_wild_audit.csv',
              'summary.json','VALIDATION.json','source_integrity.json','source_manifest.json',
              'target_manifest.csv','real_manual_count_audit.csv','difficulty_unassigned.json',
              'supplemental_model_index.json','private_worker_ledger.csv','export_validation.json',
              'real_lower_quality_reference.csv']
    required+=sorted(p.name for p in first.glob('fold_*.json'))
    comparisons={name:base.digest(first/name)==base.digest(second/name) for name in required}
    if not all(comparisons.values()):
        base.dump(first/'reproducibility_failure.json',comparisons)
        raise ValueError('replay_bytes_differ:'+','.join(k for k,v in comparisons.items() if not v))
    for directory in (first,second):
        value=json.loads((directory/'VALIDATION.json').read_text())
        value['reproducibility']='passed_independent_full_replay_byte_identical'
        base.dump(directory/'VALIDATION.json',value)
    report=dict(passed=True,seed=json.loads((first/'summary.json').read_text())['seed'],
        compared_files=len(required),same_bytes=comparisons,
        sha256={name:base.digest(first/name) for name in required})
    for directory in (first,second):base.dump(directory/'REPRODUCIBILITY.json',report)
    return report


def render(directory):
    directory=Path(directory); sources=load_inputs()
    rows=base.read_jsonl(directory/'simulations.jsonl'); groups={}
    for row in rows:groups.setdefault(row['image_id'],[]).append(row)
    selected=set()
    for difficulty in sorted({r['difficulty'] for r in rows}):
        selected.add(next(r['image_id'] for r in rows if r['difficulty']==difficulty and r['wild']))
    selected.update(r['image_id'] for r in rows if r['scope_issue_flag'])
    selected.update(r['image_id'] for r in rows if r['gt_error_excluded'] or r['pending_review'])
    cases=[(iid,None) for iid in sorted(selected)]
    for kind in ('partial_corner','missing_corner','scope_restricted'):
        cases.append((next(r['image_id'] for r in rows if r['wild_error_types']==[kind]),kind))
    review=directory/'review';review.mkdir(exist_ok=True)
    font=ImageFont.load_default(size=17)
    pages=[]; ledger=[]
    def panel(photo,points,color):
        image=photo.copy();draw=ImageDraw.Draw(image)
        for i in range(0,len(points),2):
            a,b=points[i:i+2]
            draw.line([tuple(a),tuple(b)],fill=color,width=2)
            for x,y in (a,b):draw.ellipse((x-4,y-4,x+4,y+4),outline='black',fill=color,width=1)
        return image.resize((512,256))
    for index,(iid,requested_kind) in enumerate(cases):
        if index%4==0: sheet=Image.new('RGB',(1536,4*320),'#101820')
        group=groups[iid]
        def pick(wild):
            candidates=[r for r in group if r['wild']==wild]
            if not candidates:return None
            candidates.sort(key=lambda r:(r['evaluation']['B8L2'] if r['evaluation']['B8L2'] is not None else -1,r['simulation_id']))
            return candidates[len(candidates)//2]
        normal,wild=pick(False),pick(True); anchor=wild or normal
        if requested_kind:
            wild=next(r for r in group if r['wild_error_types']==[requested_kind]);anchor=wild
        photo=Image.open(next((base.ROOT/'data/mp3d_layout').glob('*/img/'+iid+'.png'))).convert('RGB').resize((1024,512))
        model=sources['models'][iid][anchor['model_family']]['points']
        y=(index%4)*320;draw=ImageDraw.Draw(sheet)
        title=sources['difficulty'][iid]['image']+' | '+anchor['scope_reference_status']
        draw.text((8,y+5),title,font=font,fill='white')
        for col,(label,pts,color) in enumerate([
            ('model '+anchor['model_family'],model,'cyan'),
            ('normal '+normal['model_family']+' '+str(round(normal['evaluation']['B8L2'],1) if normal['evaluation']['B8L2'] is not None else 'unscored') if normal else 'normal: none (model shown)',normal['points'] if normal else model,'#7cff8c'),
            ('wild '+','.join(wild['wild_error_types']) if wild else 'wild: none',wild['points'] if wild else model,'#ffbd44')]):
            draw.text((col*512+8,y+28),label,font=font,fill=color)
            sheet.paste(panel(photo,pts,color),(col*512,y+60))
        ledger.append(dict(image_id=iid,image=sources['difficulty'][iid]['image'],
            normal_id=normal['simulation_id'] if normal else None,wild_id=wild['simulation_id'] if wild else None,
            scope_reference_status=anchor['scope_reference_status'],
            selection='explicit_'+requested_kind if requested_kind else 'per_image_median_available_B8L2_for_visual_review_only'))
        if index%4==3 or index==len(cases)-1:
            name=f'review_{len(pages)+1:02d}.png';sheet.save(review/name);pages.append(name)
    base.dump(review/'selection.json',ledger)
    (directory/'review.html').write_text('<!doctype html><meta charset="utf-8"><title>Manual 35 review</title>'
        '<style>body{background:#101820;color:white;font:16px sans-serif;margin:24px}img{width:100%;max-width:1536px}</style>'
        '<h1>Manual 35: synthetic point overlays</h1><p>Cyan: model; green: normal from higher templates; amber: wild. '
        'Scope and bad-GT cases are included. Point overlays do not certify target semantics or measured quality.</p>'
        +''.join(f'<h2>Sheet {i+1}</h2><img src="review/{html.escape(name)}">' for i,name in enumerate(pages)),encoding='utf-8')
    return ledger


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--run',type=Path,required=True)
    p.add_argument('--replay',type=Path);a=p.parse_args()
    if a.replay:verify_replay(a.run,a.replay)
    render(a.run)


if __name__=='__main__':main()
