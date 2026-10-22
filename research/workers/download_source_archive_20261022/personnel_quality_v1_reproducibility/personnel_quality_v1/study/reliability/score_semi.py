"""Recompute same-reference initial/final B8L2 + D10 without changing gates.

Only current frozen scorer is used. Initializer and final use the final record's
already assigned reference. Missing/failed geometries remain missing. Researcher
point repairs are recorded and excluded from gain attribution to the worker.
"""
import argparse,json,sys,hashlib
from pathlib import Path
from collections import Counter
import numpy as np,pandas as pd
from paths import ROOT,REPO,OUT,STUDY
from tools.thesis_main.analysis.scope_quality_scoring_20261016 import scoring_engine,score_task
from tools.thesis_main.analysis.quality_b8l2_d10_20261017 import dual_scores
METRICS=['B8L2','D10','IoU3D100','iou_2d','S_bottom_deg','dir','Hmean','Hcenter','height_mean_ratio','iou_3d_corner_mean']

def clean(x):
 if isinstance(x,dict):return {k:clean(v) for k,v in x.items()}
 if isinstance(x,(list,tuple)):return [clean(v) for v in x]
 if isinstance(x,np.generic):return clean(x.item())
 if isinstance(x,float) and not np.isfinite(x):return None
 return x

def main(ring_view='compatible'):
 payload_view=ring_view=='payload'
 evidence=pd.read_csv(OUT/'initialization_evidence_574.csv').set_index('object_id').to_dict('index')
 geoms={r['object_id']:r for r in json.loads((OUT/'initialization_geometry_canonical_574.json').read_text())}
 payload_scores={} if payload_view else pd.read_csv(OUT/'semi_payload_order_diagnostic.csv').set_index('object_id').to_dict('index')
 objects={o['object_id']:o for o in json.loads((OUT/'validated_annotations.json').read_text())}
 refs={r['target_id']:r for r in json.loads((REPO/'research/quality/quality_b8l2_d10_20261017/reference_catalog.json').read_text())}
 shared=pd.read_csv(REPO/'research/quality/quality_b8l2_d10_20261017/shared_records.csv').set_index('object_id').to_dict('index')
 ledger=pd.read_csv(OUT/'reliability_object_ledger.csv').set_index('object_id').to_dict('index')
 rows=[];measures=[];cache={};parity=[]
 with scoring_engine(REPO/'research/quality/quality_joint_closeout_review_20261015/pro_closeout_delta.zip',REPO/'research/statistics/b8l2_shared_v6_20261016/inputs/working_models.py') as (engine,models):
  for j,(oid,e) in enumerate(evidence.items(),1):
   o=objects[oid];s=shared[oid];l=ledger[oid];g=geoms[oid]
   if payload_view:g=dict(g,initial_canonical_points_1024x512=g['initial_payload_points_1024x512'],initial_ring_status='native_payload_array_diagnostic',initial_ring_changed_from_payload=False,initial_ring_source_object_ids=[])
   ref=refs.get(s['rescore_target_id'])
   row=dict(object_id=oid,**e)
   row.update(initial_ring_status=g['initial_ring_status'],initial_ring_changed_from_payload=g['initial_ring_changed_from_payload'],initial_ring_source_object_ids=g['initial_ring_source_object_ids'])
   for m in METRICS:row['initial_payload_'+m]=payload_scores.get(oid,{}).get('initial_'+m)
   row.update(data_release='v1',reference_id=s['rescore_target_id'],reference_version=s['rescore_reference_version'],
    current_quality_usable=s['quality_usable'],current_quality_use=s['quality_use'],current_final_full_score_state=s['full_score_state'],
    ordinary_task=l['ordinary_task'],ordinary_analysis_row_eligible=l['ordinary_analysis_row_eligible'],is_oos=l['oos'],is_doorway=l['doorway'],gt_error_excluded=l['gt_error_excluded_current'],
    original_holdout=l['current_original_holdout'],admission_role=l['admission_role'],independent_vote_eligible=l['independent_vote_eligible'],
    model_audit_covered=l['model_unchanged_audit_covered'],reviewer_personal_nonacceptance=l['reviewer_personal_nonacceptance'],strict_specific_personal_severe=l['strict_specific_personal_severe'])
   task=dict(object_id=oid,image_id=o['image_id'],worker_id=o['worker_id'],condition='semi',current_target_id=s['rescore_target_id'],reference_version=s['rescore_reference_version'],reference_points=ref.get('points_1024x512') if ref else None,reference_full_available=bool(ref and ref.get('full_reference_available')))
   scores={}
   for stage,pts in [('initial',g['initial_canonical_points_1024x512']),('final',g['current_final_points_1024x512'])]:
    key=(e['initialization_hash'],s['rescore_target_id']) if stage=='initial' else None
    if stage=='initial' and key in cache:res=dict(cache[key]);res['object_id']=oid;res['worker_id']=o['worker_id']
    else:
     try:
      res=score_task(dict(task,annotation_points=pts),engine,models)
      if res['score_status']=='complete':res.update(dual_scores(res,models))
     except Exception as ex:
      res=dict(task,score_status='unavailable',reasons=['uncaught_scorer_exception:'+type(ex).__name__+':'+str(ex)])
     if stage=='initial':cache[key]=res
    row[stage+'_score_status']=res['score_status'];row[stage+'_score_reasons']=res['reasons']
    for m in METRICS:row[stage+'_'+m]=res.get(m)
    scores[stage]=res
    measures.append(dict(stage=stage,**res))
   complete=all(x['score_status']=='complete' for x in scores.values())
   row['paired_score_available']=complete
   repairs=o.get('repair_evidence') or []
   if isinstance(repairs,dict):repairs=[repairs]
   applied=[r for r in repairs if str(r.get('status','')).startswith('applied')]
   row['researcher_point_repair_applied']=bool(applied)
   row['researcher_point_repair_description']=[r.get('operation') or r.get('description') for r in applied]
   row['worker_gain_attributable_under_current_view']=bool(complete and not applied)
   row['current_qualified_gain_available']=bool(complete and s['quality_usable'] and not applied)
   row['semi_profile_training_candidate']=bool(complete and s['quality_usable'] and l['ordinary_task'] and not l['current_original_holdout'] and not applied)
   row['semi_ordinary_profile_training_candidate']=bool(row['semi_profile_training_candidate'] and s['quality_use']=='ordinary_primary')
   row['semi_special_profile_training_candidate']=bool(row['semi_profile_training_candidate'] and s['quality_use']=='special_conditional_only')
   row['initialization_context_key']=json.dumps([o['image_id'],'semi',s['rescore_target_id'],e['initialization_hash']],separators=(',',':'))
   for m in ['B8L2','D10','IoU3D100']:
    row['gain_'+m]=row['final_'+m]-row['initial_'+m] if complete else None
    row['project_current_view_gain_'+m]=row['gain_'+m]
    row['worker_attributable_gain_'+m]=row['gain_'+m] if row['worker_gain_attributable_under_current_view'] else None
    row['initial_score_deficit_'+m]=100-row['initial_'+m] if scores['initial']['score_status']=='complete' else None
    row['residual_score_deficit_'+m]=100-row['final_'+m] if scores['final']['score_status']=='complete' else None
   if s['full_score_state']=='computed':
    assert scores['final']['score_status']=='complete',(oid,'previously computed final became unscorable',scores['final'])
    delta={m:abs(row['final_'+m]-s['diagnostic_'+m]) for m in ['B8L2','D10','IoU3D100']}
    assert max(delta.values())<1e-8,(oid,delta)
    parity.append(dict(object_id=oid,**{m+'_abs_error':v for m,v in delta.items()}))
   rows.append(row)
   if j%100==0:print(f'Scored {j}/{len(evidence)}; paired {sum(r["paired_score_available"] for r in rows)}; initializer/ref cache {len(cache)}',flush=True)
 f=pd.DataFrame(rows)
 for c in f:
  if f[c].map(lambda x:isinstance(x,(list,dict))).any():f[c]=f[c].map(lambda x:json.dumps(x,ensure_ascii=False) if isinstance(x,(list,dict)) else x)
 f.to_csv(OUT/('semi_payload_order_diagnostic.csv' if payload_view else 'semi_scores_b8l2_d10.csv'),index=False,encoding='utf-8-sig')
 pd.DataFrame(parity).to_csv(OUT/('semi_payload_final_score_parity.csv' if payload_view else 'semi_final_score_parity.csv'),index=False,encoding='utf-8-sig')
 (OUT/('semi_payload_measurement_records.json' if payload_view else 'semi_measurement_records.json')).write_text(json.dumps(clean(measures),ensure_ascii=False),encoding='utf8')
 summary=dict(data_release='v1',ring_measurement_view=ring_view,attempted_records=len(f),unique_initialization_reference_pairs=len(cache),final_recomputed=len(parity),
  final_score_status=f.final_score_status.value_counts().to_dict(),initial_score_status=f.initial_score_status.value_counts().to_dict(),paired_scores=int(f.paired_score_available.sum()),
  current_quality_usable=int(f.current_quality_usable.sum()),current_qualified_gain_available=int(f.current_qualified_gain_available.sum()),
  researcher_point_repair_records=int(f.researcher_point_repair_applied.sum()),semi_profile_training_candidates=int(f.semi_profile_training_candidate.sum()),
  semi_ordinary_profile_training_candidates=int(f.semi_ordinary_profile_training_candidate.sum()),semi_special_profile_training_candidates=int(f.semi_special_profile_training_candidate.sum()),
  final_failure_reason_combinations=f.loc[f.final_score_status.ne('complete'),'final_score_reasons'].value_counts().to_dict(),
  parity_max_abs_error={m:max((r[m+'_abs_error'] for r in parity),default=None) for m in ['B8L2','D10','IoU3D100']},
  unchanged_with_paired_scores=int((f.recovered_edit_status.eq('unchanged_coordinates')&f.paired_score_available).sum()),
  unchanged_max_abs_gain=float(f.loc[f.recovered_edit_status.eq('unchanged_coordinates')&f.paired_score_available,'gain_B8L2'].abs().max()),
  initial_failures=f.loc[~f.initial_score_status.eq('complete'),'image_code'].value_counts().to_dict(),
  initializer_ring_changes=int(f.initial_ring_changed_from_payload.sum()),
  initializer_existing_ring_verified=int(f.initial_ring_status.eq('existing_confirmed_ring_exact_point_identity').sum()),
  limits=['gain compares current canonical final view to deployed initialization using compatible ring semantics, same fixed reference','for exact unchanged coordinate sets, existing confirmed final rings transfer by point identity; no reference optimization','native initializer ring retained but unconfirmed when no exact-coordinate ring exists','payload-order diagnostics are retained separately: 11 unchanged outputs previously showed spurious gain from final-only ring corrections','researcher point repairs are retained as current final quality but excluded from gain credit','score deficit 100-Q is an index deficit, not an error probability or semantic error count','positive gain alone does not establish removal of a confirmed initialization defect'])
 if not payload_view:assert summary['unchanged_max_abs_gain']<1e-6,summary['unchanged_max_abs_gain']
 else:summary['limits']=['Native payload array versus current postprocessed final is an intentionally incompatible diagnostic. It cannot be credited to a worker; no UI rendering is proved.']
 (OUT/('semi_payload_order_receipt.json' if payload_view else 'semi_scoring_receipt.json')).write_text(json.dumps(clean(summary),ensure_ascii=False,indent=2),encoding='utf8')
 print(json.dumps(clean(summary),ensure_ascii=False,indent=2),flush=True)
if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--ring-view',choices=['payload','compatible'],default='compatible');args=parser.parse_args();main(args.ring_view)
