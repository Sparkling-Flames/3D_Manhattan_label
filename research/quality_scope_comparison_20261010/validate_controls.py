#!/usr/bin/env python3
"""Deterministic controls and a rerun comparison; this is not target-policy validation."""
import copy, json, sys
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parent))
from reproduce import ROOT, read, save, csvwrite, score, bev, geom, nearest_rule, exclusive_rule, sha

cfg=read(ROOT/'experiment_config.json');refs=read(ROOT/'results/fixed_references.json');controls=[];checks=[];raw={}
def check(name,condition,detail=None):
    checks.append({'check':name,'passed':bool(condition),'detail':detail})
    if not condition:raise AssertionError((name,detail))
for r in refs:
    code=r['image_code'];g,t=r['G'],r['T']; variants={'exact_G':copy.deepcopy(g),'exact_T':copy.deepcopy(t)}
    for name,scale,offset,dy in [('T_shrink_0p7',.7,0,0),('T_tiny_0p2',.2,0,0),('T_shift_x_0p2',1,.2,0),('T_top_plus_0p5',1,0,.5),('T_top_minus_0p3',1,0,-.3),('G_top_plus_0p5',1,0,.5)]:
        base=g if name.startswith('G_') else t; floor=np.asarray(base['bottom3d'])[:,[0,2]]*scale;floor[:,0]+=offset; y=np.asarray(base['top3d'])[:,1]+dy;variants[name]=geom(floor,y)
    for name,a in variants.items():
        b=bev(a,g,t);rg,rt=score(a,g,cfg),score(a,t,cfg)
        check(code+':'+name+':both_scores_available',rg['status']==rt['status']=='available')
        qg,qt=rg['quality_score'],rt['quality_score'];row={'image_code':code,'control':name,**b,'Q_G':qg,'Q_T':qt,'Q_max':max(qg,qt),'max_selected':'T' if qt>qg else 'G','nearest_BEV_margin0':nearest_rule(b,0),'nearest_BEV_margin0p1':nearest_rule(b,.1),'exclusive_0p1_0p75_cmin0p5':exclusive_rule(b,.1,.75,.5)};controls.append(row);raw[code+':'+name]={'annotation':a,'G':rg,'T':rt}
    v={x['control']:x for x in controls if x['image_code']==code}
    check(code+':exact_G_not_forced_small',v['exact_G']['max_selected']=='G' and v['exact_G']['nearest_BEV_margin0']=='G')
    check(code+':exact_T_allowed_under_set_definition',v['exact_T']['max_selected']=='T' and v['exact_T']['Q_max']>99.99)
    check(code+':tiny_answer_not_fully_rewarded',v['T_tiny_0p2']['Q_max']<v['exact_T']['Q_max']-1)
    check(code+':top_error_keeps_BEV_route_but_loses_Q',v['T_top_plus_0p5']['nearest_BEV_margin0']==v['exact_T']['nearest_BEV_margin0'] and v['T_top_plus_0p5']['Q_max']<v['exact_T']['Q_max']-1)
    check(code+':Q_independent_geometry_rules',all(nearest_rule({**v['exact_T'],'Q_G':-100000,'Q_T':100000},m)==nearest_rule(v['exact_T'],m) for m in [0,.05,.1,.2,.3]))
rows=read(ROOT/'results/comparison_18.json')
check('real18_max_vs_BEV_same_selection',all(r['max_selected_reference']==r['nearest_BEV_margin0'] for r in rows))
# Check the fresh full-reference scores against previously exported source Q for nine pictured examples.
wb=read(ROOT/'inputs/workbench_data.json');diffs=[]
for i in wb['images']:
    for e in i['examples']:
        rr=next(r for r in rows if r['record_id']==e['record_id']);diffs.append(abs(rr['Q_G']-float(e['Q'])))
check('nine_workbench_example_Q_reproduced',max(diffs)<1e-8,{'n':len(diffs),'max_abs_diff':max(diffs)})
check('no_rule_disagreement_with_max_is_observed_real_not_claimed_general',True)
records=read(ROOT/'inputs/current_geometry_three_images.json')['images'];signatures=[json.dumps({'top3d':a['top3d'],'bottom3d':a['bottom3d']},sort_keys=True) for im in records for a in im['annotations']];floors=[json.dumps(a['bottom3d']) for im in records for a in im['annotations']]
meta={'records':len(signatures),'unique_complete_geometries':len(set(signatures)),'unique_floor_geometries':len(set(floors)),'note':'These 18 selected records are not a blind or representative sample. Repeated geometries are retained, not counted as independent geometric tests.'}
save(ROOT/'results/controls_full_results.json',raw);csvwrite(ROOT/'results/controls_24.csv',controls);save(ROOT/'results/control_checks.json',{'passed':all(x['passed'] for x in checks),'check_count':len(checks),'checks':checks,'sample_duplicates':meta})
print(json.dumps({'checks':len(checks),'passed':True,'sample_duplicates':meta},ensure_ascii=False))
