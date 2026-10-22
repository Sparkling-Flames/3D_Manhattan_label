"""Separate verified initialization defects from edits and quantitative gains."""
import json
from pathlib import Path
import pandas as pd
from paths import ROOT,REPO,OUT,STUDY

def save(name,frame):
 for c in frame:
  if frame[c].map(lambda x:isinstance(x,(dict,list))).any():frame[c]=frame[c].map(lambda x:json.dumps(x,ensure_ascii=False) if isinstance(x,(dict,list)) else x)
 frame.to_csv(OUT/name,index=False,encoding='utf-8-sig')

def main():
 s=pd.read_csv(OUT/'semi_scores_b8l2_d10.csv')
 objects={o['object_id']:o for o in json.loads((OUT/'validated_annotations.json').read_text())}
 xp='analysis_results/prescreen_closeout_final_gold_v2_20260701/raw_inputs/prescreen_synthetic_expert_review.csv'
 expert=pd.read_csv(REPO/xp).fillna('').set_index('base_image_key').to_dict('index')
 rows=[]
 for v in s.to_dict('records'):
  o=objects[v['object_id']];e=o['review_evidence'];x=expert.get(o['image_id'])
  verified=bool(x and x['trap_effective'] and int(v['runtime_task']) in {int(x['runtime_task_id']),int(x['mirror_task_id'])} and v['initialization_source_verified'])
  if x:assert verified
  unchanged=v['recovered_edit_status']=='unchanged_coordinates'
  comments=[]
  for z in [e.get('current_decision_comment',''),e.get('current_comment',''),*[a['record'].get('comment','') for a in e.get('review_history',[])]]:
   if z and z not in comments:comments.append(z)
  joined=' | '.join(comments)
  explicitly_failed_edit=('没改对' in joined)
  model_comment=any(w in joined for w in ['预标注','模型初始化','被模型','模型误'])
  r={k:v[k] for k in ['object_id','worker_id','image_id','image_code','building_id','condition','cleaning_disposition','trap_status','runtime_initialization_kind','runtime_task','runtime_annotation','recovered_edit_status','initialization_hash','initialization_source_verified','current_quality_usable','current_quality_use','original_holdout','model_audit_covered','reviewer_personal_nonacceptance','strict_specific_personal_severe','initial_ring_status','initial_ring_changed_from_payload','paired_score_available','researcher_point_repair_applied']}
  r.update(data_release='v1',confirmed_initialization_error_opportunity=verified,
   initialization_error_evidence_level='expert_realized_defect_plus_exact_deployed_payload' if verified else 'no_adopted_error_specific_initialization_gold',
   initialization_error_source=xp if verified else '',initialization_error_type=x['expert_realized_model_issue_primary'] if verified else '',
   initialization_error_secondary=x['expert_realized_model_issue_secondary'] if verified else '',
   planned_error_type=x['planned_synthetic_family'] if verified else '',planned_realized_mismatch=bool(x['planned_realized_mismatch']) if verified else None,
   initialization_error_expert_note=x['operator_validity_note'] if verified else '',
   known_error_unchanged=bool(verified and unchanged),
   error_specific_residual_state='known_persistent_by_coordinate_identity' if verified and unchanged else 'unknown_after_edit' if verified else 'initial_defect_not_adjudicated',
   changed_error_specific_residual_known=False,changed_error_specific_residual_unknown=bool(verified and not unchanged),
   changed_error_specific_correction_confirmed=False,
   annotation_model_comment_observed=model_comment,reviewer_residual_after_edit_statement=bool(explicitly_failed_edit and not unchanged),
   reviewer_statement_is_error_specific_gold=False,
   reviewer_statement_limit='Error mechanism/reference not fully specified; original record remains usable and statement does not certify all outputs for this initializer.' if explicitly_failed_edit else 'Scope alternatives and revision context retained; a model-related comment alone is not adopted as a complete error-specific outcome.' if model_comment else '',
   source_verdict=e.get('verdict'),gt_version_note=e.get('gt_version_note'),image_comment=e.get('image_comment'),scope_policy=e.get('scope_policy'),annotation_comments=comments,
   semantic_miss_and_strict_exclusion_overlap=bool(verified and unchanged and v['strict_specific_personal_severe']),
   semantic_miss_and_broad_exclusion_overlap=bool(verified and unchanged and v['reviewer_personal_nonacceptance']),
   scoring_interpretation='compatible-ring same-reference measurement diagnostic; not verified screen-rendered geometry')
  for m in ['B8L2','D10','IoU3D100']:
   for p in ['initial_','final_','project_current_view_gain_','worker_attributable_gain_','residual_score_deficit_']:r[p+m]=v[p+m]
  rows.append(r)
 f=pd.DataFrame(rows);assert f.confirmed_initialization_error_opportunity.sum()==156
 save('correction_object_ledger.csv',f)
 workers=sorted(set(o['worker_id'] for o in objects.values()));wr=[]
 for w in workers:
  g=f[f.worker_id.eq(w)];known=g[g.confirmed_initialization_error_opportunity]
  r=dict(worker_id=w,n_semi=len(g),n_initialization_payload_verified=int(g.initialization_source_verified.sum()),n_initialization_error_opportunities=len(known),
   n_error_opportunity_images=known.image_id.nunique(),n_error_opportunity_buildings=known.building_id.nunique(),
   n_known_error_unchanged=int(known.known_error_unchanged.sum()),n_edited_error_specific_outcome_unknown=int(known.changed_error_specific_residual_unknown.sum()),
   n_edited_error_specific_correction_confirmed=0,n_edited_error_specific_residual_confirmed=0,
   n_current_quality_error_opportunities=int(known.current_quality_usable.sum()),n_current_quality_known_error_unchanged=int((known.current_quality_usable&known.known_error_unchanged).sum()),
   n_error_opportunities_in_model_audit=int(known.model_audit_covered.sum()),n_all_model_audit=int(g.model_audit_covered.sum()),
   n_model_audit_known_error_unchanged=int((known.model_audit_covered&known.known_error_unchanged).sum()),
   n_semi_initial_error_unknown=int((~g.confirmed_initialization_error_opportunity).sum()),
   n_review_comment_failed_after_edit=int(g.reviewer_residual_after_edit_statement.sum()),
   n_unchanged_without_adopted_initial_error_gold=int((~g.confirmed_initialization_error_opportunity&g.recovered_edit_status.eq('unchanged_coordinates')).sum()),
   n_semantic_miss_strict_severe_overlap=int(g.semantic_miss_and_strict_exclusion_overlap.sum()),n_semantic_miss_broad_severe_overlap=int(g.semantic_miss_and_broad_exclusion_overlap.sum()))
  wr.append(r)
 save('worker_correction_summary.csv',pd.DataFrame(wr))
 audit=f[f.model_audit_covered&f.trap_status.eq('confirmed_trap')&f.recovered_edit_status.eq('unchanged_coordinates')]
 receipt=dict(data_release='v1',semi_inventory=len(f),confirmed_initial_error_opportunities=int(f.confirmed_initialization_error_opportunity.sum()),
  expert_tasks=len(expert),expert_planned_actual_type_mismatches=sum(bool(x['planned_realized_mismatch']) for x in expert.values()),
  confirmed_initial_error_workers=f.loc[f.confirmed_initialization_error_opportunity,'worker_id'].nunique(),
  confirmed_initial_error_buildings=f.loc[f.confirmed_initialization_error_opportunity,'building_id'].nunique(),
  known_error_unchanged=int(f.known_error_unchanged.sum()),changed_error_specific_outcome_unknown=int(f.changed_error_specific_residual_unknown.sum()),
  current_quality_error_opportunities=int((f.confirmed_initialization_error_opportunity&f.current_quality_usable).sum()),
  current_quality_known_error_unchanged=int((f.known_error_unchanged&f.current_quality_usable).sum()),
  original_audit_confirmed_trap_unchanged=len(audit),original_audit_trap_unchanged_with_actual_error_gold=int(audit.confirmed_initialization_error_opportunity.sum()),original_audit_trap_unchanged_without_actual_error_gold=int((~audit.confirmed_initialization_error_opportunity).sum()),
  semantic_miss_strict_exclusion_overlap=int(f.semantic_miss_and_strict_exclusion_overlap.sum()),semantic_miss_broad_exclusion_overlap=int(f.semantic_miss_and_broad_exclusion_overlap.sum()),
  reviewer_edited_residual_statements=int(f.reviewer_residual_after_edit_statement.sum()),
  limits=['Known unedited coordinate defects remain in raw coordinates; this is an observed missed-correction event, not a permanent worker type.','Edited erroneous initializations have unknown error-specific correction outcomes unless separately verified; no inferred successes from edit/gain.','Quantitative final/gain/residual indices are compatible-ring measurement diagnostics and do not prove a semantic defect was fixed.','Current trap_status and planned trap labels are not substitutes for expert realized-error evidence.','Only six error-specific tasks exist; removing any one building leaves fewer than six task contexts, so the existing 6-context worker support rule cannot yield a semantic-miss LOBO classifier.'])
 (OUT/'correction_ledger_receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf8');print(json.dumps(receipt,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
