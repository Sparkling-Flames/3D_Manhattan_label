"""Read unchanged Pro scalar/official IoU implementations against frozen current geometry."""
import csv,importlib.util,sys,math
from pathlib import Path
from collections import Counter
from common import read,save,csvwrite,sha
ROOT=Path(__file__).resolve().parents[1]
PRO=ROOT/'frozen/Pro_selected_original'
def module(path,name):
 spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);sys.modules[name]=m;spec.loader.exec_module(m);return m
def main():
 rows=read(ROOT/'results/current_components.json');geo=read(ROOT/'inputs/current_geometry_compact.json')['geometries']
 original=list(csv.DictReader(open(PRO/'experiments/fixed_run/score_rows_3152.csv',encoding='utf-8-sig')));lookup={r['object_id']:r for r in original}
 config=read(PRO/'experiments/preregistered_candidates.json');variants=module(PRO/'experiments/run_quality.py','unchanged_Pro_run_quality')
 official=module(PRO/'official_audit/audit_official_controls.py','unchanged_Pro_official_audit');manifest=official.verify_official_sources()
 from shapely.geometry import Polygon
 fn,post,ast=official.load_official_iou_branch(Polygon)
 sys.path.insert(0,str(ROOT/'frozen/scope_engine/core'));sys.path.insert(0,str(ROOT/'frozen/scope_engine/traditional'))
 from traditional_metrics import frozen_to_hohonet_pixels
 current_alignment={r['record_id']:r for r in read(ROOT/'results/target_alignment_ledger.json')}
 components={'iou_2d':'iou_2d','boundary_rms_deg':'S_deg','Hstar':'Hstar','dir':'D_deg','flat':'F_deg','Q':'Q_v11'}
 diffs=Counter();checks=[];scores=[];ledger=[];population={}
 assert {r['object_id'] for r in rows}==set(lookup)
 for r in rows:
  p=lookup[r['object_id']];assert r['record_id']==p['record_id'];assert r['reference_object_id']==p['selected_gt_object_id']
  for c,k in components.items():
   a=r[c];b=float(p[k]) if p[k] else None;assert (a is None)==(b is None)
   if a is not None:diffs[c]=max(diffs[c],abs(a-b));assert abs(a-b)<1e-9
  flags={k:p[k]=='True' for k in ['conservative_fixed_gt_quality_candidate','conservative_fixed_gt_primary_candidate','target_aligned_quality_candidate','target_aligned_primary_candidate']}
  available=p['score_status']=='available'
  ledger.append({'record_id':r['record_id'],'object_id':r['object_id'],'image_code':r['image_code'],'worker_id':r['worker_id'],'available':available,**flags,'independent_vote_eligible':p['independent_vote_eligible']=='True','Pro_group_key':p['group_key'],'Pro_group_split':p['group_split'],'current_strict_target_subset':current_alignment[r['record_id']]['target_unconfounded_conservative'],'frozen_coordinates_changed':False})
  if not available:continue
  m={'iou':r['iou_2d'],'S_top_deg':r['S_top_deg'],'S_bottom_deg':r['S_bottom_deg'],'dir':r['dir'],'flat':r['flat'],'Hstar':r['Hstar']}
  v=variants.variant_scores(m,config)
  for name,q in v.items():
   expected=float(p[name]) if p.get(name) else None
   if expected is not None:diffs[name]=max(diffs[name],abs(q-expected));assert abs(q-expected)<1e-9
  a,g=geo[r['object_id']],geo[r['reference_object_id']];o=official.run_compatibility(fn,frozen_to_hohonet_pixels(a),frozen_to_hohonet_pixels(g))
  assert o['official_branch_status']=='returned_finite';delta=abs(o['official_iou3d_raw']-float(p['official_iou3d_same_geometry_vertex_mean']));diffs['official_iou3d_vs_Pro']=max(diffs['official_iou3d_vs_Pro'],delta);assert delta<1e-9
  checks.append({'record_id':r['record_id'],'reference_id':r['reference_object_id'],'official_iou2d':o['official_iou2d_raw'],'official_iou3d_corner_mean':o['official_iou3d_raw'],'delta_from_Pro_official_iou3d':delta,'official_branch_status':o['official_branch_status']})
  scores.append({'record_id':r['record_id'],'object_id':r['object_id'],'image_code':r['image_code'],'worker_id':r['worker_id'],**flags,**v})
 for flag in flags:population[flag]=sum(r['available'] and r[flag] for r in ledger)
 ours={r['object_id'] for r in rows if current_alignment[r['record_id']]['primary_without_confirmed_B_top_pending']}
 pro={r['object_id'] for r in ledger if r['available'] and r['target_aligned_quality_candidate']};assert ours==pro
 difference=[r for r in ledger if r['available'] and r['target_aligned_quality_candidate'] and not r['target_aligned_primary_candidate']]
 mild=[r for r in scores if r['target_aligned_quality_candidate'] and next(x for x in rows if x['record_id']==r['record_id'])['dir']<=5 and next(x for x in rows if x['record_id']==r['record_id'])['flat']<=2]
 severeids={r['record_id'] for r in rows if r['dir'] is not None and r['dir']>=10}
 severe=[r for r in scores if r['target_aligned_quality_candidate'] and r['record_id'] in severeids]
 summary={'all_objects':len(rows),'available':len(scores),'all_ids_and_references_equal':True,'six_component_null_patterns_equal':True,'maximum_absolute_differences':dict(diffs),'Pro_policy_population':population,'nested_1725_membership_exactly_matches_Pro':True,'quality_1725_minus_independent_primary_1724':difference,'target_1725_mild_count':len(mild),'stage13_mild_max_abs_change':max(abs(r['Q_stage13']-r['Q_v11']) for r in mild),'target_1725_Dge10_count':len(severe),'stage13_Dge10_mean_extra_deduction':sum(r['Q_v11']-r['Q_stage13'] for r in severe)/len(severe),'official_source_commit':manifest['commit'],'official_IoU_branch_3021_locally_executed':True,'official_full_CLI_depth_model_not_run':True,'original_frozen_scalar_code_reexecuted':True,'full_Pro_experiment_standalone_reproduced':False}
 rowmap={r['record_id']:r for r in rows};population_effects=[]
 for flag in ['conservative_fixed_gt_quality_candidate','target_aligned_quality_candidate']:
  selected=[r for r in scores if r[flag]];mild=[r for r in selected if rowmap[r['record_id']]['dir']<=5 and rowmap[r['record_id']]['flat']<=2];severe=[r for r in selected if rowmap[r['record_id']]['dir']>=10]
  population_effects.append({'population':flag,'n':len(selected),'mild':len(mild),'mild_stage13_max_delta':max(abs(r['Q_v11']-r['Q_stage13']) for r in mild),'Dge10':len(severe),'stage13_Dge10_mean_extra_deduction':sum(r['Q_v11']-r['Q_stage13'] for r in severe)/len(severe)})
 summary['stage13_population_specific_effects']=population_effects
 csvwrite(ROOT/'results/Pro_variants_replayed_current.csv',scores);csvwrite(ROOT/'results/Pro_policy_membership_current.csv',ledger);csvwrite(ROOT/'results/Pro_official_IoU_real3021_replay.csv',checks);save(ROOT/'results/Pro_source_replay_summary.json',summary);print(summary)
if __name__=='__main__':main()
