#!/usr/bin/env python3
"""Three fixed-reference comparisons. No formal input edits, label fitting or Q-based scope assignment.
Run: PYTHONPATH=/tmp/quality_integration_deps python reproduce.py
Portable requirements: Python 3, numpy, scipy, shapely; matplotlib only for optional figures.
"""
from __future__ import annotations
import argparse, copy, csv, hashlib, json, platform, sys, time
from collections import Counter
from pathlib import Path
import numpy as np
from shapely.geometry import Polygon, Point

ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'frozen_engine/core'))
from quality_v11 import score_geometry
from strict_geometry import validate_record
from audit_geometry import area_metrics, height_stats


def read(p): return json.loads(Path(p).read_text())
def save(p,d): Path(p).write_text(json.dumps(d,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def plain(v):
    if isinstance(v,dict): return {k:plain(x) for k,x in v.items()}
    if isinstance(v,(list,tuple)): return [plain(x) for x in v]
    if isinstance(v,np.generic):return v.item()
    return v

def csvwrite(path, rows):
    if not rows: return
    fields=list(dict.fromkeys(k for r in rows for k in r))
    with Path(path).open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
        for r in rows:w.writerow({k:json.dumps(v,ensure_ascii=False) if isinstance(v,(list,dict)) else v for k,v in r.items()})

def poly(r): return Polygon(np.asarray(r['bottom3d'])[:,[0,2]])
def geom(floor,ys):return {'bottom3d':[[float(x),-1.,float(z)] for x,z in floor], 'top3d':[[float(x),float(y),float(z)] for (x,z),y in zip(floor,ys)]}

def bev(a,g,t):
    A,G,T=map(poly,(a,g,t)); gi=A.intersection(G).area;ti=A.intersection(T).area
    ext=G.difference(T); extra=T.difference(G)
    return {'annotation_area_h2':A.area,'G_area_h2':G.area,'T_area_h2':T.area,'T_over_G_area':T.area/G.area,
            'G_intersection_h2':gi,'T_intersection_h2':ti,
            'coverage_G':gi/G.area,'coverage_T':ti/T.area,
            'outside_G_fraction_of_annotation':A.difference(G).area/A.area,
            'outside_T_fraction_of_annotation':A.difference(T).area/A.area,
            'outside_G_area_h2':A.difference(G).area,'outside_T_area_h2':A.difference(T).area,
            'iou_G':gi/A.union(G).area,'iou_T':ti/A.union(T).area,
            'G_minus_T_area_h2':ext.area,'T_minus_G_area_h2':extra.area,
            'coverage_G_minus_T':A.intersection(ext).area/ext.area if ext.area>1e-12 else None,
            'coverage_T_minus_G':A.intersection(extra).area/extra.area if extra.area>1e-12 else None,
            'annotation_outside_G_union_T_fraction':A.difference(G.union(T)).area/A.area}

def nearest_rule(b,margin):
    delta=b['iou_T']-b['iou_G']
    return ('T' if delta>margin else 'G' if delta < -margin else 'uncertain')

def exclusive_rule(b, low, high, cmin):
    e=b['coverage_G_minus_T']
    if e is None:return 'uncertain'
    if b['coverage_T']>=cmin and e<=low:return 'T'
    if b['coverage_G']>=cmin and e>=high:return 'G'
    return 'uncertain'

def score(a,g,config):
    return score_geometry(a,g,**config['score_samples'])

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,default=ROOT/'results'); args=ap.parse_args();out=args.out;out.mkdir(parents=True,exist_ok=True)
    config=read(ROOT/'experiment_config.json');data=read(ROOT/'inputs/current_geometry_three_images.json');wb=read(ROOT/'inputs/workbench_data.json');manual=read(ROOT/'inputs/manual_scope_review_received_20261010.json');confirmation=read(ROOT/'inputs/manual_scope_confirmation_20261010.json');proposal=read(ROOT/'inputs/e9z17_crop_proposal_frozen_before_scores.json')
    checks=[]
    def ck(name,ok,detail=None):
        checks.append({'check':name,'passed':bool(ok),'detail':plain(detail)})
        if not ok:raise AssertionError((name,detail))
    ck('manual_export_hash_matches_confirmation',sha(ROOT/'inputs/manual_scope_review_received_20261010.json')==confirmation['source_sha256'])
    ck('exactly_three_workbench_images',len(wb['images'])==3)
    original_hash=sha(ROOT/'inputs/current_geometry_three_images.json')
    selected_ids=[];reference_records=[];reference_meta=[];ref_by_image={};all_rows=[];component_rows=[];full_results={};sensitivity=[]
    for wi in wb['images']:
        code=wi['image_code']; im=next(i for i in data['images'] if i['code']==code);mr=next(i for i in manual['records'] if i['image_code']==code); cr=next(i for i in confirmation['records'] if i['image_code']==code)
        candidates=[g for g in im['groundtruths'] if g['points']==wi['reference_points_1024x512']]
        ck(code+':unique_GT_selected_by_exact_workbench_points',len(candidates)==1);g=candidates[0]
        ck(code+':GT_ID_unchanged',g['id']==im['defaultReferenceId'])
        ck(code+':manual_parent_matches_workbench',mr['reference_object_id']==wi['reference_object_id'] and mr['original_GT_points_1024x512']==g['points'])
        ck(code+':floor_polygon_explicitly_confirmed',cr['floor_region_confirmed'] and cr['decision']=='allow' and cr['polygon']==mr['polygon'])
        floor=mr['polygon'];gy=np.asarray(g['top3d'])[:,1]
        if code=='e9zR4mvMWw7-17':
            inds=proposal['kept_gt_vertex_indices_zero_based']; old=proposal['reference']
            ck(code+':legacy_top_exact_GT_endpoints',old=={k:[g[k][j] for j in inds] for k in ('top3d','bottom3d')})
            oldfloor=np.asarray(old['bottom3d'])[:,[0,2]];err=float(np.max(np.abs(oldfloor-np.asarray(floor))))
            ck(code+':legacy_floor_roundoff_only',err<2e-15,err)
            ty=np.asarray(old['top3d'])[:,1];t=geom(floor,ty);rule='reuse retained original GT top heights; confirmed floor XZ exact, max legacy floor drift '+str(err)
        else:
            t=geom(floor,np.full(len(floor),np.median(gy)));rule='constant median of original GT vertex top_y; independent of annotations, their heights and all Q'
        vg,vt=validate_record(g,role='reference'),validate_record(t,role='reference')
        ck(code+':G_and_T_strict_valid',vg['available'] and vt['available'])
        G,T=poly(g),poly(t)
        meta={'image_code':code,'G_id':g['id'],'G_version':g['version'],'reference_object_id':wi['reference_object_id'],'T_id':code+':confirmed_floor_conditional_top_v1','floor_confirmation':'confirmed','top_boundary_approval':'not established','set_scoring_protocol_approval':'exploratory_not_default','top_rule':rule,'original_GT_top_y_min':float(gy.min()),'original_GT_top_y_max':float(gy.max()),'original_GT_top_y_median':float(np.median(gy)),'original_GT_top_y_range_h':float(np.ptp(gy)), 'original_GT_perimeter_height_relative_rms':height_stats(g)['height_internal_relative_rms'],'G_area_h2':G.area,'T_area_h2':T.area,'T_over_G_area':T.area/G.area,'T_outside_G_h2':T.difference(G).area,'T_outside_G_fraction':T.difference(G).area/T.area,'G_outside_T_h2':G.difference(T).area,'camera_inside_G':G.contains(Point(0,0)),'camera_inside_T':T.contains(Point(0,0)),'camera_distance_to_T_boundary_h':T.boundary.distance(Point(0,0)), 'G_validity':vg,'T_validity':vt}
        reference_meta.append(meta);reference_records.append({'image_code':code,'G':g,'T':t,'metadata':meta});ref_by_image[code]=(g,t)
        ts=score(t,t,config);ck(code+':T_self_score_near_100',abs(ts['quality_score']-100)<0.002,ts['quality_score'])
        # Q need not be exactly 100 for geometrically self-identical non-orthogonal/non-flat G.
        ck(code+':workbench_ids_equal_current_records',set(a['record_id'] for a in wi['annotations'])==set(a['id'] for a in im['annotations']))
        for wa in wi['annotations']:
            a=next(a for a in im['annotations'] if a['id']==wa['record_id']);rid=a['id'];selected_ids.append(rid)
            ck(rid+':workbench_points_equal_current',wa['points']==a['points'])
            ar=a['source_record']; b=bev(a,g,t); rg,rt=score(a,g,config),score(a,t,config)
            ck(rid+':both_Q_available',rg['status']==rt['status']=='available',{'G':rg['reason_codes'],'T':rt['reason_codes']})
            for key,res in [('G',rg),('T',rt)]:
                ck(rid+':'+key+':BEV_independent_shapely_agrees',abs(res['metrics']['iou_2d']-b['iou_'+key])<1e-10)
                deduction=sum(res['metrics'][n] for n in ('range_deduction_points','boundary_deduction_points','height_deduction_points','intrinsic_deduction_points'))
                ck(rid+':'+key+':deductions_conserve_100_minus_Q',abs(deduction+res['quality_score']-100)<1e-10)
                component_rows.append({'image_code':code,'record_id':rid,'reference_kind':key,'status':res['status'],**res['metrics']})
            qg,qt=rg['quality_score'],rt['quality_score'];maxref='T' if qt>qg else 'G' if qg>qt else 'tie'
            row={'image_code':code,'record_id':rid,'worker_id_workbench':wa['worker_id'],'worker_id_source':ar['worker'],'condition':ar['condition'],'workbench_gate':wa['gate'],'cleaning_disposition':ar['cleaning_disposition'],'independent_vote_eligible':ar['independent_vote_eligible'],'main_quality_gate':ar['main_quality_gate']['status'],'main_consensus_gate':ar['main_consensus_gate']['status'],'population':'exact_workbench_18_not_new_eligibility_decision','G_id':g['id'],'G_version':g['version'],'T_id':meta['T_id'],'top_status':'conditional_geometry_not_confirmed_top','Q_G':qg,'Q_T_conditional':qt,'Q_set_max_conditional':max(qg,qt),'Q_T_minus_G':qt-qg,'max_selected_reference':maxref,**b}
            row['nearest_BEV_margin0']=nearest_rule(b,0);row['nearest_BEV_margin0p1']=nearest_rule(b,.1);row['exclusive_low0p1_high0p75_cmin0p5']=exclusive_rule(b,.1,.75,.5)
            row['Q_nearest_BEV_margin0']=qt if row['nearest_BEV_margin0']=='T' else qg if row['nearest_BEV_margin0']=='G' else None
            row['max_minus_nearest_BEV_Q']=max(qg,qt)-row['Q_nearest_BEV_margin0'] if row['Q_nearest_BEV_margin0'] is not None else None
            for tag,r in [('G',rg),('T',rt)]:
                for k in ('S_top_deg','S_bottom_deg','Hstar','Hmean','Hlocal','dir','flat','iou_3d_corner_mean','iou_3d_perimeter_mean','range_deduction_points','boundary_deduction_points','height_deduction_points','intrinsic_deduction_points'):
                    row[k+'_'+tag]=r['metrics'].get(k)
            variants={}
            # Vary only the conditional reference ceiling within the original GT endpoint envelope.
            for name,ht in [('GT_min_flat',float(gy.min())),('GT_max_flat',float(gy.max()))]:
                rr=score(a,geom(floor,[ht]*len(floor)),config);variants[name]=rr
                sensitivity.append({'image_code':code,'record_id':rid,'variant':name,'top_y':ht,'Q_T':rr['quality_score'],'delta_from_primary':rr['quality_score']-qt,'S_top_deg':rr['metrics'].get('S_top_deg'),'Hstar':rr['metrics'].get('Hstar')})
            row['Q_T_GT_top_envelope_min']=min([qt]+[r['quality_score'] for r in variants.values()]);row['Q_T_GT_top_envelope_max']=max([qt]+[r['quality_score'] for r in variants.values()]);all_rows.append(row)
            full_results[rid]={'image_code':code,'G':rg,'T_conditional':rt,'GT_top_envelope_variants':variants}
        print(code, 'done',flush=True)
    ck('exactly_18_unique_workbench_records',len(selected_ids)==len(set(selected_ids))==18)
    ck('source_subset_unchanged',sha(ROOT/'inputs/current_geometry_three_images.json')==original_hash)
    save(out/'fixed_references.json',reference_records);save(out/'reference_metadata.json',reference_meta);save(out/'full_score_results.json',full_results);save(out/'comparison_18.json',all_rows);csvwrite(out/'comparison_18.csv',all_rows);csvwrite(out/'complete_components_long.csv',component_rows);csvwrite(out/'ceiling_sensitivity.csv',sensitivity)
    # All rules below consume BEV-only inputs; Q is used after routing solely to compare outcomes.
    rules=[]
    for margin in config['geometric_rules']['nearest_bev']['margins']:
        rules.append(('nearest_BEV',{'margin':margin},lambda b,m=margin:nearest_rule(b,m)))
    er=config['geometric_rules']['exclusive_region']
    for low in er['small_max_exclusive_G_coverage']:
        for high in er['large_min_exclusive_G_coverage']:
            for c in er['min_chosen_reference_coverage']:
                rules.append(('exclusive_region',{'low':low,'high':high,'cmin':c},lambda b,l=low,h=high,c=c:exclusive_rule(b,l,h,c)))
    route_rows=[];route_summary=[]
    for name,params,fn in rules:
        routes=[]
        for r in all_rows:
            tag=fn(r);q=r['Q_G'] if tag=='G' else r['Q_T_conditional'] if tag=='T' else None
            rec={'rule':name,'parameters':params,'image_code':r['image_code'],'record_id':r['record_id'],'route':tag,'max_selected_reference':r['max_selected_reference'],'Q_routed':q,'Q_max':r['Q_set_max_conditional'],'max_minus_routed_Q':r['Q_set_max_conditional']-q if q is not None else None}
            route_rows.append(rec);routes.append(rec)
        dif=[r['max_minus_routed_Q'] for r in routes if r['max_minus_routed_Q'] is not None]; cnt=Counter(r['route'] for r in routes)
        route_summary.append({'rule':name,'parameters':params,'n':len(routes),'G':cnt['G'],'T':cnt['T'],'uncertain':cnt['uncertain'],'assigned_disagree_with_max':sum(r['route']!='uncertain' and r['route']!=r['max_selected_reference'] for r in routes),'max_Q_loss_of_assigned':max(dif) if dif else None,'mean_Q_loss_of_assigned':float(np.mean(dif)) if dif else None})
    csvwrite(out/'scope_routing_sensitivity_576rows.csv',route_rows);csvwrite(out/'scope_routing_summary_32rules.csv',route_summary);save(out/'scope_routing_summary.json',route_summary)
    summary=[]
    for code in [i['image_code'] for i in wb['images']]:
        rows=[r for r in all_rows if r['image_code']==code];m=next(r for r in reference_meta if r['image_code']==code)
        s={'image_code':code,'n':len(rows),'T_over_G_area':m['T_over_G_area'],'T_outside_G_fraction':m['T_outside_G_fraction'],'max_reference_counts':dict(Counter(r['max_selected_reference'] for r in rows)),'nearest_BEV_counts':dict(Counter(r['nearest_BEV_margin0'] for r in rows)),'max_vs_nearest_disagreements':sum(r['nearest_BEV_margin0']!=r['max_selected_reference'] for r in rows)}
        for k in ('Q_G','Q_T_conditional','Q_set_max_conditional','Q_T_minus_G','coverage_G','coverage_T','outside_G_fraction_of_annotation','outside_T_fraction_of_annotation','coverage_G_minus_T','S_top_deg_T','S_bottom_deg_T','Hstar_T'):
            vals=[r[k] for r in rows];s[k+'_min']=min(vals);s[k+'_median']=float(np.median(vals));s[k+'_max']=max(vals)
        s['largest_abs_Q_ceiling_variation']=max(abs(r['delta_from_primary']) for r in sensitivity if r['image_code']==code);summary.append(s)
    save(out/'summary.json',summary);csvwrite(out/'summary.csv',summary)
    ck('32_exploratory_rules',len(route_summary)==32);ck('576_routing_results',len(route_rows)==576)
    save(out/'checks.json',{'passed':all(c['passed'] for c in checks),'check_count':len(checks),'checks':checks,'runtime':{'python':platform.python_version(),'numpy':np.__version__},'config_sha256':sha(ROOT/'experiment_config.json'),'limitations':['No top-boundary approval is inferred from floor approval.','No historical worker intention is inferred or required for set matching.','Full accepted-set Q is conditional on GT-derived ceiling and future protocol decision.','No formal GT, default score or eligibility is modified.','Threshold grids are exploratory, not validated classification rules.','Fixed G and confirmed T may be non-nested.']})
    print(json.dumps(summary,ensure_ascii=False,indent=2));print('CHECKS',len(checks),'PASS')

if __name__=='__main__':main()
