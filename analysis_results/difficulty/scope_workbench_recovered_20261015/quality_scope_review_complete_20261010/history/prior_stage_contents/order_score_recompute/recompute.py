#!/usr/bin/env python3
"""Matched fixed-GT v1.1 diagnostics, preserving actual formal-input ring arrays.
Offline replay: python recompute.py --out results
The frozen engine and scalar formula are never modified. No sorting/repair/fit.
"""
from __future__ import annotations
import argparse,copy,csv,hashlib,json,platform,sys
from collections import Counter
from pathlib import Path
import numpy as np
from shapely.geometry import Polygon
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'frozen_engine/core'))
from quality_v11 import score_geometry

def read(p): return json.loads(Path(p).read_text(encoding='utf-8'))
def save(p,x): Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def csvwrite(p,rows):
    fields=list(dict.fromkeys(k for r in rows for k in r))
    with Path(p).open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
        for r in rows:w.writerow({k:json.dumps(v,ensure_ascii=False) if isinstance(v,(list,dict)) else v for k,v in r.items()})

def project(o):
    """Pointwise continuous 1024x512 projection in the existing ring order.
    Camera height is one; bottom_y=-1. No x sorting or ring repair.
    """
    p=np.asarray(o['points_1024x512'],dtype=np.float64)
    assert p.ndim==2 and p.shape[1]==2 and len(p)%2==0
    assert np.array_equal(p[::2,0],p[1::2,0])
    floor=p[1::2];top=p[::2]
    u=(floor[:,0]/1024-.5)*2*np.pi
    v=(floor[:,1]/512-.5)*np.pi
    r=1/np.tan(v)
    x=r*np.sin(u);z=-r*np.cos(u)
    y=-r*np.tan((top[:,1]/512-.5)*np.pi)
    return {'id':o['object_id'],'points':o['points_1024x512'],
      'sourcePointIndices':o['ordered_source_point_indices'],
      'sourcePairIndices':o['ordered_source_pair_indices'],
      'bottom3d':np.stack([x,-np.ones_like(x),z],axis=1).tolist(),
      'top3d':np.stack([x,y,z],axis=1).tolist()}

def area_diagnostics(a,g):
    A=Polygon(np.asarray(a['bottom3d'])[:,[0,2]]);G=Polygon(np.asarray(g['bottom3d'])[:,[0,2]])
    return {'symmetric_difference':A.symmetric_difference(G).area/G.area,
      'excess':A.difference(G).area/G.area,'missing':G.difference(A).area/G.area,
      'iou_2d_independent':A.intersection(G).area/A.union(G).area,
      'annotation_area_h2':A.area,'GT_area_h2':G.area}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,default=ROOT/'results');args=ap.parse_args();out=args.out;out.mkdir(parents=True,exist_ok=True)
    old,new=[read(ROOT/'inputs'/f'{s}_formal.json') for s in ('old','new')]
    receipt=read(ROOT/'inputs/confirmed_orders.json');checks=[]
    def ck(name,ok,details=None):
        checks.append({'name':name,'passed':bool(ok),'details':details})
        if not ok:raise AssertionError((name,details))
    ck('both_formal_loaders_validated',all(d['validation']['status']=='passed' and d['both_loaders_identical'] for d in (old,new)))
    ck('object_population_same',old['object_digests'].keys()==new['object_digests'].keys())
    changed=sorted(k for k in old['object_digests'] if old['object_digests'][k]!=new['object_digests'][k])
    ck('exactly_three_objects_changed',changed==sorted(receipt['records']),changed)
    ck('3438_other_objects_byte_equivalent_canonical_json',len(new['object_digests'])-len(changed)==3438)
    ck('raw_coordinates_pairing_GT_identity_gates_and_review_preserved',old['protected_object_digests']==new['protected_object_digests'])
    ck('quality_layer_revision_same',old['input_revision']==new['input_revision']=='quality_review_20261010_v1')
    ck('confirmation_count_1309_to_1312',old['validation']['confirmed_orders']==1309 and new['validation']['confirmed_orders']==1312)
    maps=[{o['object_id']:o for o in d['objects']} for d in (old,new)];om,nm=maps
    gt_id=new['image']['references']['gt_original'];ck('only_one_official_GT',len(new['image']['references'])==1)
    ck('GT_object_exactly_unchanged',om[gt_id]==nm[gt_id])
    reference=project(nm[gt_id]);full={};rows=[];flat=[];geoms={};metrics={}
    keys=['quality_score','iou_2d','iou_3d_corner_mean','iou_3d_perimeter_mean','S_top_deg','S_bottom_deg','Hstar','Hmean','Hlocal','dir','flat','range_deduction_points','boundary_deduction_points','height_deduction_points','intrinsic_deduction_points','mean_height_only_score_same_parameters','T','F','U','B','area_h2','C']
    for oid in sorted(om):
        if om[oid]['object_kind']!='annotation':continue
        alias=new['aliases'][oid];geoms[oid]={};full[oid]={};metrics[oid]={}
        for name,ob in [('old',om[oid]),('new',nm[oid])]:
            a=project(ob);geoms[oid][name]=a
            res=score_geometry(a,reference,spherical_samples=2048,height_samples=4096)
            area=area_diagnostics(a,reference);metrics[oid][name]=area
            full[oid][name]={'geometry':a,'result':res,'independent_shapely_area':area}
            ck(f'{alias}:{name}:quality_available',res['status']=='available',res['reason_codes'])
            ck(f'{alias}:{name}:independent_iou_matches',abs(res['metrics']['iou_2d']-area['iou_2d_independent'])<1e-12)
            ck(f'{alias}:{name}:deductions_sum_to_100',abs(sum(res['metrics'][k] for k in keys if k.endswith('_deduction_points'))+res['quality_score']-100)<1e-10)
            flat.append({'record_id':alias,'worker_id':ob['worker_id'],'object_id':oid,'snapshot':name,'changed_order':oid in changed,'score_status':res['status'],'official_use':'diagnostic_only','main_quality_gate':ob['main_quality_gate'],'main_consensus_gate':ob['main_consensus_gate'],'quality_score':res['quality_score'],**res['metrics'],**area})
        row={'image_code':new['image']['image_code'],'object_id':oid,'record_id':alias,'worker_id':nm[oid]['worker_id'],'changed_order':oid in changed,'fixed_GT_record_id':new['aliases'][gt_id],'fixed_GT_version':'original','old_order':om[oid]['ordered_source_pair_indices'],'new_order':nm[oid]['ordered_source_pair_indices'],'main_quality_gate':nm[oid]['main_quality_gate'],'main_consensus_gate':nm[oid]['main_consensus_gate'],'official_use':'diagnostic_only_hold_preserved'}
        for k in keys:
            a=full[oid]['old']['result'];b=full[oid]['new']['result'];ov=a['quality_score'] if k=='quality_score' else a['metrics'].get(k);nv=b['quality_score'] if k=='quality_score' else b['metrics'].get(k)
            row[k+'_old']=ov;row[k+'_new']=nv;row[k+'_delta']=nv-ov if ov is not None and nv is not None else None
        for k in ('symmetric_difference','excess','missing'):
            row[k+'_old']=metrics[oid]['old'][k];row[k+'_new']=metrics[oid]['new'][k];row[k+'_delta']=row[k+'_new']-row[k+'_old']
        rows.append(row)
        if oid in changed:
            order=receipt['records'][oid]['order'];bind=json.loads(receipt['records'][oid]['binding'])
            target=[bind['points'][j] for i in order for j in (2*i,2*i+1)]
            ck(f'{alias}:current_ring_exact_receipt_order',nm[oid]['points_1024x512']==target)
            ck(f'{alias}:current_confirmed_no_x_sort',nm[oid]['ring_confirmed'] and nm[oid]['order_status']=='human_confirmed' and nm[oid]['points_1024x512']!=sorted(nm[oid]['points_1024x512']))
            ck(f'{alias}:geometry_is_only_permuted',all(np.array_equal(np.asarray(geoms[oid]['old'][k])[order],geoms[oid]['new'][k]) for k in ('top3d','bottom3d')))
            ck(f'{alias}:actual_ring_changes_quality',abs(row['quality_score_delta'])>1e-5,row['quality_score_delta'])
        else:ck(f'{alias}:unaffected_full_scores_exact',full[oid]['old']==full[oid]['new'])
        print(alias,nm[oid]['worker_id'],row['quality_score_old'],row['quality_score_new'],flush=True)
    summary={'image_code':new['image']['image_code'],'records':6,'changed_records':3,'all_corpus_recomputed':False,'fixed_GT_record_id':new['aliases'][gt_id],'fixed_GT_object_id':gt_id,'fixed_GT_version':'original','official_score_count':0,'diagnostic_score_count':6,'all_main_quality_gates_preserved_as_hold':all(o['main_quality_gate']['status']=='hold_scene_or_reference' for o in nm.values() if o['object_kind']=='annotation'),'N_unchanged':len(reference['bottom3d']),'explanation':'Six image-local old/new diagnostics were evaluated; only three rings changed. Image aggregates below are descriptive diagnostics, not official worker scores or a new difficulty class.'}
    for s in ('old','new'):
        q=[r['quality_score_'+s] for r in rows];ds=[r['symmetric_difference_'+s] for r in rows]
        summary[s]={'quality_mean':float(np.mean(q)),'quality_median':float(np.median(q)),'quality_min':min(q),'quality_max':max(q),'scope_flag_counts':{str(t):sum(d>=t for d in ds) for t in (.2,.3,.4)},'scope_flag_fraction_lower_at_0p3':sum(d>=.3 for d in ds)/6,'scope_flag_fraction_upper_at_0p3':sum(d>=.3 for d in ds)/6,'scope_majority_geometry_signal':sum(d>=.3 for d in ds)>=3,'valid_geometries':6}
    save(out/'matched_scores_all_six.json',rows);csvwrite(out/'matched_scores_all_six.csv',rows);csvwrite(out/'changed_three_scores.csv',[r for r in rows if r['changed_order']]);csvwrite(out/'complete_components.csv',flat)
    save(out/'full_old_new_results.json',full);save(out/'fixed_GT.json',reference);save(out/'image_summary.json',summary)
    save(out/'checks.json',{'passed':True,'check_count':len(checks),'checks':checks,'old_source_commit':old['source_commit'],'new_source_commit':new['source_commit'],'inputs_sha256':{p.name:sha(p) for p in sorted((ROOT/'inputs').glob('*.json'))},'runtime':{'python':platform.python_version(),'numpy':np.__version__},'limitations':['All six current quality gates remain on hold; numerical scores are diagnostic only.','No corpus-wide quality, fusion, clustering, worker ranking, GT, eligibility, scope decision or difficulty stratification was changed.','Old scores are matched recomputations using the same v1.1 engine, not a claim that every historical score used v1.1.']})
    print(json.dumps(summary,ensure_ascii=False,indent=2));print('CHECKS',len(checks),'PASS')
if __name__=='__main__': main()
