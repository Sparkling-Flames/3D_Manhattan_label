"""80 polygon comparisons; strict geometry, no fitting, repair or new full Q."""
from pathlib import Path
import json, math, hashlib, csv, platform
from collections import Counter
import numpy as np, shapely
from shapely.geometry import Polygon, Point
from shapely.validation import explain_validity
ROOT=Path(__file__).resolve().parents[1]
def dump(p,x):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def project(points):
 a=np.asarray(points,dtype=float);assert a.ndim==2 and a.shape[1]==2 and len(a)%2==0 and np.isfinite(a).all()
 b=a[1::2];v=(b[:,1]/512-.5)*math.pi
 if np.any(v<=0) or np.any(v>=math.pi/2):raise ValueError('floor angles outside strict lower hemisphere')
 u=(b[:,0]/1024-.5)*math.pi*2;r=1/np.tan(v)
 return np.column_stack((r*np.sin(u),-r*np.cos(u)))
def strict_poly(x):
 a=np.asarray(x,dtype=float)
 if a.ndim!=2 or a.shape[1]!=2 or not np.isfinite(a).all() or len(a)<3:raise ValueError('nonfinite or insufficient vertices')
 p=Polygon(a)
 if not p.is_valid or p.is_empty or p.area<=0:raise ValueError(explain_validity(p))
 return p
def compare(p,t):
 inter=p.intersection(t).area;missing=t.difference(p).area;excess=p.difference(t).area;union=p.union(t).area
 assert union>0 and p.area>0 and t.area>0
 assert abs(t.area-inter-missing)<1e-9*max(1,t.area) and abs(p.area-inter-excess)<1e-9*max(1,p.area)
 i=inter/union;assert 0<=i<=1
 return dict(iou=i,annotation_area=p.area,reference_area=t.area,intersection_area=inter,union_area=union,missing_area=missing,excess_area=excess,symmetric_difference_area=missing+excess,missing_over_reference=missing/t.area,excess_over_reference=excess/t.area,excess_over_annotation=excess/p.area,symmetric_difference_over_reference=(missing+excess)/t.area,reference_covered=inter/t.area,annotation_inside_reference=inter/p.area)
def main():
 valid=json.loads((ROOT/'results/receipt_validation.json').read_text());assert valid['C_D_confirmations_replayed_and_match_current_drafts']
 raw=(ROOT/'inputs/library/空间范围人工审核_2026-10-11.json').read_bytes();assert hashlib.sha256(raw).hexdigest()==valid['raw_receipt_sha256'];x=json.loads(raw)
 seed=json.loads((ROOT/'inputs/previous/editor_seed_data.json').read_text());c=seed['images'][0];old=json.loads((ROOT/'inputs/frozen_components_20.json').read_text());oldmap={r['record_id']:r for r in old}
 rr={r['region_id']:r for r in x['records'][0]['space_regions']['regions']}
 coords={'A':project(c['reference_points_1024x512']).tolist(),'B':c['baseline_spaces']['B']['polygon'],'C':rr['space_c']['confirmed_version']['polygon'],'D':rr['space_d']['confirmed_version']['polygon']}
 targets={k:strict_poly(v) for k,v in coords.items()};ledger=[]
 for k,t in targets.items():
  ledger.append(dict(space_label=k,region_id={'A':'primary','B':'space_b','C':'space_c','D':'space_d'}[k],polygon_xz_h=coords[k],area_h2=t.area,geometry_valid=True,camera_strictly_inside=t.contains(Point(0,0)),acceptance_source='inherited_previously_acknowledged' if k in 'AB' else 'new_explicit_workbench_confirmation',confirmed_at=(c['baseline_spaces']['B']['original_confirmation']['confirmed_at'] if k=='B' else rr['space_'+k.lower()]['confirmed_version']['confirmed_at'] if k in 'CD' else None),top_status='original_GT_top_retained_no_new_validation' if k=='A' else 'top_pending',new_full_Q_allowed=False))
 dump(ROOT/'results/reference_ledger.json',dict(image_code=c['image_code'],coordinate_frame=x['coordinate_frame'],area_unit='camera_height_normalized_h_squared; not square metres',no_alignment_or_repair=True,receipt_library_id='libfile_477d2fe4a0ec8191937721f30ba67c8a',receipt_sha256=valid['raw_receipt_sha256'],spaces=ledger,manual_target_directives=[dict(case_id='T30',record_id='R02962',object_id='new_93_3608_7113_W006',target_space_label='D',routing_source='user_specified',source_field='independent_T30_rereview.matching_region_ids',automatic_routing=False),*x['user_target_directives']],all_people_C_D='user_expectation_to_be_checked; not preset',formal_GT_or_eligibility_changed=False))
 rows=[];long=[];results=[]
 for a in c['annotations']:
  frozen=oldmap[a['record_id']];pointsha=hashlib.sha256(json.dumps(a['points'],separators=(',',':')).encode()).hexdigest();assert pointsha==a['current_points_sha256']==frozen['current_points_sha256'];assert a['object_id']==frozen['object_id']
  base=dict(record_id=a['record_id'],object_id=a['object_id'],worker_id=a['worker_id'],condition=a['condition'],current_points_sha256=pointsha,frozen_Q=frozen.get('Q'),frozen_Q_status=frozen.get('current_Q_status'),frozen_D_degrees=frozen.get('dir'),frozen_F_degrees=frozen.get('flat'),frozen_primary_included=frozen.get('primary_included'),frozen_primary_exclusion_reasons=';'.join(frozen.get('primary_exclusion_reasons',[])),manual_target='D' if a['record_id']=='R02962' else '',manual_source='user_specified' if a['record_id']=='R02962' else '',new_full_Q=None,new_full_3d_IoU=None,full_recompute_status='not_computed_C_D_top_pending',intention_from_automatic_choice=False)
  try:
   xy=project(a['points']);p=strict_poly(xy);base['cached_footprint_status']='missing' if a['footprint'] is None else 'present_matches_current';base['automatic_summary_denominator_eligible']=bool(a['in_current_manual_pool'] and frozen['independent_vote_eligible']);base['frozen_main_quality_gate']=frozen['main_quality_gate']['status'];base['frozen_main_consensus_gate']=frozen['main_consensus_gate']['status'];
   if a['footprint'] is not None:assert p.symmetric_difference(strict_poly(a['footprint'])).area<1e-9
  except (ValueError,AssertionError) as e:
   base.update(geometry_status='invalid',geometry_reason=str(e));rows.append(base);results.append(base);continue
  metrics={k:compare(p,t) for k,t in targets.items()};assert abs(metrics['A']['iou']-frozen['iou_2d'])<1e-9; base['A_IoU_matches_frozen_current_computation']=True;rank=sorted(metrics,key=lambda k:(-metrics[k]['iou'],k));oldrank=sorted('AB',key=lambda k:(-metrics[k]['iou'],k));best=rank[0];delta=metrics[best]['iou']-metrics[oldrank[0]]['iou'];margin=metrics[best]['iou']-metrics[rank[1]]['iou']
  base.update(geometry_status='valid',geometry_reason='',annotation_area_h2=p.area,camera_strictly_inside=p.contains(Point(0,0)),automatic_best_floor_IoU=best,automatic_second_best=rank[1],best_second_gap=margin,exact_numerical_tie_candidates=';'.join(k for k in rank if metrics[best]['iou']-metrics[k]['iou']<=1e-12),margin_at_most_1pp=margin<=.01,margin_at_most_2pp=margin<=.02,margin_at_most_5pp=margin<=.05,absolute_mismatch_one_minus_best_IoU=1-metrics[best]['iou'],old_AB_best=oldrank[0],old_AB_best_IoU=metrics[oldrank[0]]['iou'],new_ABCD_best_IoU=metrics[best]['iou'],best_IoU_gain_over_AB=delta,manual_matches_automatic=(best=='D') if a['record_id']=='R02962' else None,effective_human_target='D' if a['record_id']=='R02962' else '',unmatched_or_ambiguous_human_status='not_automatically_decided',D_F_reference_independent_unchanged=True)
  for k,m in metrics.items():
   for name,value in m.items():base[k+'_'+name]=value
   long.append(dict(record_id=a['record_id'],worker_id=a['worker_id'],space_label=k,area_unit='h^2',**m))
  rows.append(base);results.append(dict(**base,comparisons=metrics,ordered_candidates=rank))
 current_validrows=[r for r in rows if r['geometry_status']=='valid'];validrows=[r for r in current_validrows if r['automatic_summary_denominator_eligible']];counts=dict(Counter(r['automatic_best_floor_IoU'] for r in validrows));t30=next(r for r in results if r['record_id']=='R02962');low=sorted([r for r in validrows if r['frozen_Q'] is not None and r['frozen_Q']<50],key=lambda r:-r['best_IoU_gain_over_AB'])
 summary=dict(main_checked=valid['main_checked'],record_count=len(rows),distinct_worker_ids=len({r['worker_id'] for r in rows}),valid_current_points_geometries=len(current_validrows),invalid_current_points_geometries=len(rows)-len(current_validrows),manual_pool_denominator_records=len(validrows),formal_quality_primary_included_records=sum(r['frozen_primary_included'] for r in current_validrows),all_current_points_counts=dict(Counter(r['automatic_best_floor_IoU'] for r in current_validrows)),legacy_cached_footprint_counts=dict(Counter(r['automatic_best_floor_IoU'] for r in current_validrows if r['cached_footprint_status']!='missing')),formal_quality_primary_counts=dict(Counter(r['automatic_best_floor_IoU'] for r in current_validrows if r['frozen_primary_included'])),quality_holds_preserved=[r['record_id'] for r in current_validrows if r['frozen_main_quality_gate'].startswith('hold')],excluded_diagnostic_records=[{k:r[k] for k in ['record_id','cached_footprint_status','frozen_main_quality_gate','frozen_primary_included','automatic_best_floor_IoU','new_ABCD_best_IoU']} for r in current_validrows if not r['automatic_summary_denominator_eligible']],automatic_max_floor_IoU_counts={k:counts.get(k,0) for k in 'ABCD'},CD_automatic_records=sum(counts.get(k,0) for k in 'CD'),non_CD_exceptions=[{k:r[k] for k in ['record_id','worker_id','automatic_best_floor_IoU','old_AB_best','new_ABCD_best_IoU','best_second_gap','frozen_Q','frozen_D_degrees','frozen_F_degrees']} for r in validrows if r['automatic_best_floor_IoU'] in 'AB'],small_margin_descriptive_counts={str(v):sum(r['best_second_gap']<=v for r in validrows) for v in [.01,.02,.05]},margin_flags_are_not_acceptance_or_routing_thresholds=True,target_areas_h2={k:v.area for k,v in targets.items()},T30=t30,largest_reference_scope_gains=[{k:r[k] for k in ['record_id','worker_id','frozen_Q','old_AB_best','old_AB_best_IoU','automatic_best_floor_IoU','new_ABCD_best_IoU','best_IoU_gain_over_AB','frozen_D_degrees','frozen_F_degrees']} for r in sorted(validrows,key=lambda r:-r['best_IoU_gain_over_AB'])[:8]],old_Q_under_50_reference_gain_candidates=[{k:r[k] for k in ['record_id','worker_id','frozen_Q','old_AB_best_IoU','new_ABCD_best_IoU','best_IoU_gain_over_AB','frozen_D_degrees','frozen_F_degrees']} for r in low],frozen_D_F_unchanged=True,new_Q_or_full_3d_IoU_computed=False,formal_GT_eligibility_exclusions_or_holds_changed=False,interpretation='Higher floor IoU alone does not establish intent, acceptance, severe/mild status or improved complete Q.',runtime=dict(python=platform.python_version(),numpy=np.__version__,shapely=shapely.__version__))
 dump(ROOT/'results/floor_recompute_20.json',dict(coordinate_frame=x['coordinate_frame'],area_unit='h^2',rows=results));dump(ROOT/'results/summary.json',summary)
 for name,data in [('floor_recompute_20.csv',rows),('floor_metrics_80_long.csv',long)]:
  fields=list(dict.fromkeys(k for r in data for k in r));p=ROOT/'results'/name
  with p.open('w',newline='',encoding='utf-8-sig') as f:w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(data)
 print(json.dumps({k:summary[k] for k in ['record_count','distinct_worker_ids','valid_current_points_geometries','automatic_max_floor_IoU_counts','small_margin_descriptive_counts','non_CD_exceptions','largest_reference_scope_gains']},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
