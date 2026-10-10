"""Reconcile frozen scope screens with current inputs. No GT edits or Q recomputation."""
import argparse
import csv
import hashlib
import json
import html
from collections import Counter
from pathlib import Path
import numpy as np
from shapely.geometry import Polygon
from tools.thesis_main.data_prep.materialize_current_research_input import load_current_input

ROOT = Path(__file__).resolve().parents[3]
FIRST = ['e9zR4mvMWw7-17', 'e9zR4mvMWw7-09', 'b8cTxDM8gDG-18']
QUESTIONS = {
 FIRST[0]: '侧方楼梯/通道分支是否允许不纳入？若允许，请指出主体在哪里封口。',
 FIRST[1]: '餐厨相连区域是否允许只标相机附近主体？若允许，请指出跨开口的停止边。',
 FIRST[2]: '四份较小底面与两份较大底面是否对应可接受的两个目标？请先判范围，再判各自几何错误。',
}
GLASS = {'pRbA3pwrgk9-02','uNb9QFRL6hY-67','rPc6DW4iMge-06','jtcxE69GiFV-18'}
HELD = {'q9vSo1VnCiC-29','uNb9QFRL6hY-32'}
EXCESS = {'wc2JMjhGNzB-26','yqstnuAEVhm-31'}
NEGATIVE = {'uNb9QFRL6hY-54','uNb9QFRL6hY-79'}

def read_csv(path):
    with path.open(encoding='utf-8-sig',newline='') as f: return list(csv.DictReader(f))

def write_csv(path, rows):
    with path.open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)

def is_true(x): return x is True or x=='True'

def polygon(points):
    p=np.array(points,float)[1::2];u=(p[:,0]/1024-.5)*2*np.pi;v=(p[:,1]/512-.5)*np.pi
    if len(p)<3 or not np.isfinite(p).all() or (v<=0).any() or (v>=np.pi/2).any():
        raise ValueError('invalid floor projection')
    r=1/np.tan(v);p=Polygon(np.c_[r*np.sin(u),-r*np.cos(u)])
    if not p.is_valid or p.area<=0:raise ValueError('invalid polygon')
    return p

def route(code):
    if code in FIRST:return 'first_round_3'
    if code in GLASS:return 'fixed_gt_glass_or_mixed_control'
    if code in HELD:return 'existing_hold_no_reactivation'
    if code in EXCESS:return 'excess_or_mixed_not_simple_crop'
    if code in NEGATIVE:return 'same_space_depth_control'
    return 'reserve_geometry_or_target_uncertain'

def representatives(group):
    # Deliberately geometry-only selection, never choose by Q or maximum GT score.
    s=sorted(group,key=lambda r:(float(r['annotation_area_over_gt']),r['record_id']))
    if not s:return []
    candidates=[('small_area',s[0]),('middle_area',s[(len(s)-1)//2]),('large_area',s[-1])]
    return [dict(role=role,**r) for role,r in candidates]

def render_svg(code, gt_points, examples):
    rings=[list(polygon(p).exterior.coords) for p in [gt_points]+[e['points_1024x512'] for e in examples]]
    coords=np.concatenate(rings);lo=coords.min(axis=0);hi=coords.max(axis=0)
    scale=min(260/max(hi[0]-lo[0],1e-9),220/max(hi[1]-lo[1],1e-9))
    result=['<svg xmlns="http://www.w3.org/2000/svg" width="960" height="340" viewBox="0 0 960 340">', '<rect width="960" height="340" fill="white"/>']
    for j,e in enumerate(examples):
        xoff=320*j+30;yoff=65
        def transform(r):return ' '.join(f'{xoff+(x-lo[0])*scale:.3f},{yoff+(hi[1]-y)*scale:.3f}' for x,y in r)
        result.append(f'<text x="{320*j+15}" y="24" font-family="sans-serif" font-size="15">{html.escape(e["record_id"]+" / "+e["role"])}</text>')
        result.append(f'<polygon points="{transform(rings[0])}" fill="#ef4444" fill-opacity="0.06" stroke="#be123c" stroke-width="2"/>')
        result.append(f'<polygon points="{transform(rings[j+1])}" fill="#2563eb" fill-opacity="0.1" stroke="#2563eb" stroke-width="2"/>')
        px=xoff-lo[0]*scale;py=yoff+hi[1]*scale
        result.append(f'<circle cx="{px:.3f}" cy="{py:.3f}" r="3" fill="black"/>')
        result.append(f'<text x="{320*j+15}" y="303" font-family="sans-serif" font-size="13">area/GT={float(e["annotation_area_over_gt"]):.3f}; old Q={float(e["Q"]):.2f}</text>')
    result.append('<text x="15" y="331" font-family="sans-serif" font-size="13">Red: fixed GT. Blue: annotation. Black: camera. Same scale in all three panels. No crop applied.</text></svg>')
    return ''.join(result)

def main(source_root, out):
    scan=source_root/'scope_scan'; out.mkdir(parents=True,exist_ok=True)
    review_root=ROOT/'analysis_results/image_difficulty_full_review_20261010'
    paths=[scan/'all_259_images_scope_scan.csv',scan/'all_3152_records_scope_metrics.csv',
           review_root/'review_data.json',review_root/'all_scope_evidence.json',
           ROOT/'analysis_results/research_input_20260929/quality_update_20261010.json']
    hashes={str(p.relative_to(ROOT) if p.is_relative_to(ROOT) else 'frozen_package/'+str(p.relative_to(source_root))):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    current=load_current_input();objs={o['object_id']:o for o in current['objects']}
    images={r['image_code']:r for r in read_csv(paths[0])};records=read_csv(paths[1])
    visuals={r['image']:r for r in json.loads(paths[2].read_text(encoding='utf-8'))}
    evidence={r['image']:r for r in json.loads(paths[3].read_text(encoding='utf-8'))}
    observations={r['record_id']:r for im in evidence.values() for r in im['observations']}
    assert len(images)==len(visuals)==len(evidence)==259 and len(records)==3152
    primary=[r for r in records if is_true(r['primary_manual_oos'])]
    assert len(primary)==2368
    for r in primary:
        o=objs[r['canonical_object_id']];old=observations[r['record_id']]
        assert o['image_code']==r['image_code'] and o['worker_id']==old['worker_id']
        assert o['points_1024x512']==old['points'], 'frozen coordinate drift: '+r['record_id']
        assert not o.get('quality_review_provenance')
    algorithm={k for k,v in images.items() if is_true(v['candidate_base'])}
    visual={k for k,v in visuals.items() if v['scope_category']=='extent_candidate'}
    union=algorithm|visual
    assert (len(algorithm),len(visual),len(algorithm&visual),len(union))==(16,13,5,24)
    rows=[]; detail=[]; check_errors=[];checked=0;max_error=0.0
    for code in sorted(union,key=lambda c:(FIRST.index(c) if c in FIRST else 100,c)):
        im=images[code];vis=visuals[code];ev=evidence[code]
        group=[r for r in primary if r['image_code']==code]
        # A source screening population is not identical to current formal quality eligibility.
        gates=Counter(objs[r['canonical_object_id']]['worker_quality_gate'] for r in group)
        assert len({r['worker'] for r in group})==len(group)
        gt=objs[ev['gt_object_id']]
        assert gt['points_1024x512']==ev['selected_gt_points']
        gp=polygon(gt['points_1024x512']) if group else None
        for r in group:
            p=polygon(objs[r['canonical_object_id']]['points_1024x512']);inter=p.intersection(gp).area
            values={'annotation_area_over_gt':p.area/gp.area,'gt_missing_fraction_exact':1-inter/gp.area,'annotation_outside_fraction_exact':1-inter/p.area}
            err=max(abs(values[k]-float(r[k])) for k in values)
            max_error=max(max_error,err)
            if err>1e-7:check_errors.append(dict(image=code,record=r['record_id'],max_error=err))
            checked+=1
        example=[]
        for r in representatives(group):
            o=objs[r['canonical_object_id']]
            example.append({k:r[k] for k in ['role','record_id','canonical_object_id','worker','condition','reference_id','reference_version','Q','annotation_area_over_gt','gt_missing_fraction_exact','annotation_outside_fraction_exact','scope_regular_base']}|{'formal_worker_id':o['worker_id'],'current_quality_gate':o['worker_quality_gate'],'points_1024x512':o['points_1024x512']})
        evidence_url='https://github.com/Sparkling-Flames/3D_Manhattan_label/blob/3db905eb7cfd63c6055039dae621bb173bf75ac7/analysis_results/image_difficulty_full_review_20261010/'+vis['card']
        row=dict(image_code=code,review_queue=route(code),old_algorithm_base=code in algorithm,visual_extent_candidate=code in visual,
            frozen_screen_workers=len(group),current_gate_counts=json.dumps(dict(gates),ensure_ascii=False,sort_keys=True),
            frozen_Q_median=im['median_Q'],frozen_scope_regular_workers=im['scope_regular_base_n'],
            frozen_shared_missing_fraction=im['shared_missing_ge2of3_gt_fraction_grid'],
            small_example=example[0]['record_id'] if example else '',large_example=example[-1]['record_id'] if example else '',
            prior_visual_note=vis['scope_note'],human_question=QUESTIONS.get(code,'暂不要求本轮裁剪；先保留证据及原资格。'),
            evidence_url=evidence_url,human_range_decision='',human_closure_location='',human_note='')
        rows.append(row)
        detail.append(dict(image_code=code,reference_object_id=ev['gt_object_id'],reference_points_1024x512=gt['points_1024x512'],screen_record_ids=[r['record_id'] for r in group],examples=example,evidence_url=evidence_url))
    assert not check_errors,check_errors
    for d in detail:
        if d['image_code'] in FIRST:
            (out/(d['image_code']+'.svg')).write_text(render_svg(d['image_code'],d['reference_points_1024x512'],d['examples']),encoding='utf-8')
    write_csv(out/'candidate_reconciliation_24.csv',rows)
    write_csv(out/'human_review_first3.csv',[r for r in rows if r['review_queue']=='first_round_3'])
    (out/'record_evidence.json').write_text(json.dumps(detail,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    summary=dict(source_commit='3db905eb7cfd63c6055039dae621bb173bf75ac7',formal_update=current['quality_update_revision'],
        source_hashes=hashes,algorithm_base=16,visual_extent=13,intersection=5,union=24,first_round=FIRST,
        routing_counts=dict(Counter(r['review_queue'] for r in rows)),frozen_primary_records=2368,
        frozen_primary_coordinate_matches=2368,reviewed14_in_frozen_primary=0,
        exact_geometry_records_rechecked=checked,geometry_max_tolerance=1e-7,geometry_max_absolute_error=max_error,geometry_failures=check_errors,
        Q_recomputed=False,GT_modified=False,eligibility_modified=False,human_decisions_applied=False,
        scope='24-candidate reconciliation, not a fresh full-corpus Q run; screening sample differs from formal quality gates')
    (out/'validation.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in summary.items() if k!='source_hashes'},ensure_ascii=False,indent=2))
    return rows

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source-root',type=Path,required=True);p.add_argument('--out',type=Path,default=ROOT/'analysis_results/quality_scope_human_review_20261010');a=p.parse_args();main(a.source_root,a.out)
