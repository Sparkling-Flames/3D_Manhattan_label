"""Object-level review evidence and opportunity counts; all inputs remain data v1.

No score, vote, reference, or source verdict is changed. Absence of a personal
error adjudication is not a negative label. Model-unchanged audit is selective.
"""
from pathlib import Path
import json
import pandas as pd
from paths import ROOT,REPO,OUT,STUDY

def dump(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf8')
def cs(e):
 fields=[('review_evidence.current_decision_comment',e.get('current_decision_comment','')),('review_evidence.current_comment',e.get('current_comment',''))]
 fields += [(f"review_evidence.review_history[{j}].record.comment",x['record'].get('comment','')) for j,x in enumerate(e.get('review_history',[]))]
 out=[]
 for field,text in fields:
  if text:
   old=next((x for x in out if x['text']==text),None)
   if old:old['source_fields'].append(field)
   else:out.append(dict(text=text,source_fields=[field]))
 return out

def main():
 from tools.thesis_main.data_prep.consolidate_research_input import load_current_bundle
 bundle=load_current_bundle(REPO/'analysis_results/research_input_20261017/manifest.json')
 objects=[o for o in bundle['data']['objects'] if o['object_kind']=='annotation']
 coding={r['object_id']:r for r in json.loads((OUT/'exclusion_reason_coding.json').read_text())}
 quality=pd.read_csv(REPO/'research/quality/quality_b8l2_d10_20261017/shared_records.csv').set_index('object_id').to_dict('index')
 personnel=pd.read_csv(REPO/'research/workers/worker_b8l2_d10_20261017/personnel_ledger.csv').set_index('object_id').to_dict('index')
 audit={r['object_id']:r for r in bundle['data']['model_unchanged_audit']}
 assert len(audit)==105
 rows=[]
 for o in objects:
  oid=o['object_id'];e=o['review_evidence'];q=quality[oid];p=personnel[oid]
  c=coding.get(oid,{});h=e.get('historical_exclusion_reason','');v=e.get('verdict')
  accepted=v in {'usable','retained_scope_variation'}
  binary_broad=accepted or c.get('reviewer_personal_nonacceptance',False)
  binary_strict=accepted or c.get('strict_specific_personal_severe',False)
  row={k:o[k] for k in ['object_id','worker_id','image_id','image_code','building_id','condition','cleaning_disposition','trap_status','model_edit_status','independent_vote_eligible','preprocessing_status']}
  row.update(data_release='v1',source=o['source'],source_verdict=v,individually_reviewed_flag=(o.get('final_review') or {}).get('individually_reviewed'),
   any_current_invalid=v=='invalid',historical_exclusion_reason=h,
   historical_worker_exclusion=h=='existing_worker_exclusion',historical_empty_geometry=h in {'empty_point_response','empty_points'},
   historical_individual_exclusion=h=='user_confirmed_individual_exclusion',historical_nonindependence=h=='prior_exposure_not_new_independent_vote',
   historical_technical_or_pairing=h in {'coordinate_invalid','ambiguous_extra_or_missing_pair'},historical_superseded=h.startswith('superseded_'),
   reason_code=c.get('reason_code','not_current_invalid'),error_type=c.get('error_type'),
   strict_specific_personal_severe=bool(c.get('strict_specific_personal_severe',False)),reviewer_personal_nonacceptance=bool(c.get('reviewer_personal_nonacceptance',False)),
   personal_binary_broad_eligible=binary_broad,personal_binary_broad_outcome=(int(c.get('reviewer_personal_nonacceptance',False)) if binary_broad else None),
   personal_binary_strict_eligible=binary_strict,personal_binary_strict_outcome=(int(c.get('strict_specific_personal_severe',False)) if binary_strict else None),
   explicitly_accepted_negative_candidate=accepted,
   current_invalid_personal_reason_unknown_or_nonpersonal=v=='invalid' and not c.get('reviewer_personal_nonacceptance',False),
   annotation_comments=cs(e),image_comment=e.get('image_comment'),scope_policy=e.get('scope_policy'),
   gt_substantive_error_current=bool(e.get('gt_substantive_error')),gt_error_excluded_current=bool(q['gt_error_excluded']),
   gt_context_comment=e.get('image_comment') if 'gt' in (e.get('image_comment') or '').lower() else '',
   doorway=bool(q['is_doorway']),oos=bool(q['is_oos']),difficulty_class=q['difficulty_class'],scene=q['scene'],
   ordinary_analysis_row_eligible=bool(q['ordinary_difficulty_eligible']),
   ordinary_task=(q['difficulty_class'] in {'简单','中等','困难'} and not bool(q['is_oos']) and not bool(q['is_doorway']) and not bool(q['gt_error_excluded'])),
   quality_usable=bool(q['quality_usable']),quality_use=q['quality_use'],
   target_bound=bool(q['target_binding_unique']),reference_id=q['reference_id'],reference_version=q['reference_version'],
   current_original_holdout=bool(p['admission_original_holdout']),admission_role=p['admission_role'],in_Q_training=bool(p['in_Q_training']),
   model_unchanged_audit_covered=oid in audit,
   severe_and_unchanged_audit_overlap=bool(c.get('strict_specific_personal_severe',False)) and oid in audit,
   broader_personal_and_unchanged_audit_overlap=bool(c.get('reviewer_personal_nonacceptance',False)) and oid in audit)
  rows.append(row)
 frame=pd.DataFrame(rows)
 assert frame.loc[frame.explicitly_accepted_negative_candidate,'individually_reviewed_flag'].eq(True).all(), 'accepted negative must have explicit individual review'
 assert int(frame.explicitly_accepted_negative_candidate.sum())==999
 for col in ['source','annotation_comments']:frame[col]=frame[col].map(lambda x:json.dumps(x,ensure_ascii=False))
 frame.to_csv(OUT/'reliability_object_ledger.csv',index=False,encoding='utf-8-sig')
 stats=[]
 for w,g in frame.groupby('worker_id'):
  n=len(g);judged=g.personal_binary_broad_eligible;sj=g.personal_binary_strict_eligible
  stats.append(dict(worker_id=w,n_submissions=n,buildings=g.building_id.nunique(),n_manual=int(g.condition.eq('manual').sum()),n_semi=int(g.condition.eq('semi').sum()),n_oos_condition=int(g.condition.eq('oos').sum()),
   n_individual_review_flags=int(g.individually_reviewed_flag.fillna(False).sum()),n_explicit_accepted=int(g.explicitly_accepted_negative_candidate.sum()),n_invalid=int(g.any_current_invalid.sum()),
   n_strict_personal_severe=int(g.strict_specific_personal_severe.sum()),n_reviewer_personal_nonacceptance=int(g.reviewer_personal_nonacceptance.sum()),
   strict_known_submission_fraction=float(g.strict_specific_personal_severe.mean()),broad_known_submission_fraction=float(g.reviewer_personal_nonacceptance.mean()),
   n_broad_personally_judgable=int(judged.sum()),broad_error_fraction_in_judgable=float(g.loc[judged,'personal_binary_broad_outcome'].mean()) if judged.any() else None,
   n_strict_personally_judgable=int(sj.sum()),strict_error_fraction_in_judgable=float(g.loc[sj,'personal_binary_strict_outcome'].mean()) if sj.any() else None,
   n_invalid_reason_unknown_or_nonpersonal=int(g.current_invalid_personal_reason_unknown_or_nonpersonal.sum()),
   n_historical_worker_exclusion=int(g.historical_worker_exclusion.sum()),n_historical_empty_geometry=int(g.historical_empty_geometry.sum()),n_historical_individual_exclusion=int(g.historical_individual_exclusion.sum()),
   n_historical_technical_or_pairing=int(g.historical_technical_or_pairing.sum()),n_historical_nonindependence=int(g.historical_nonindependence.sum()),n_historical_superseded=int(g.historical_superseded.sum()),
   n_model_audit=int(g.model_unchanged_audit_covered.sum()),n_strict_severe_audit_overlap=int(g.severe_and_unchanged_audit_overlap.sum()),
   n_broad_severe_audit_overlap=int(g.broader_personal_and_unchanged_audit_overlap.sum()),
   evidence_class=('specific_personal_failures_documented' if g.strict_specific_personal_severe.any() else 'reviewer_unacceptable_personal_outputs_documented' if g.reviewer_personal_nonacceptance.any() else 'not_personally_adjudicated_in_current_review' if not judged.any() else 'no_confirmed_personal_failure_in_observed_judgements')))
 pd.DataFrame(stats).to_csv(OUT/'worker_reliability_summary.csv',index=False,encoding='utf-8-sig')
 receipt=dict(data_release='v1',loader_validation=bundle['validation'],annotations=len(frame),workers=frame.worker_id.nunique(),
  current_invalid=int(frame.any_current_invalid.sum()),strict_personal_severe=int(frame.strict_specific_personal_severe.sum()),broad_personal_nonacceptance=int(frame.reviewer_personal_nonacceptance.sum()),
  individually_reviewed_flags=int(frame.individually_reviewed_flag.fillna(False).sum()),explicit_accepted_negatives=int(frame.explicitly_accepted_negative_candidate.sum()),
  explicit_accepted_negatives_individually_reviewed=int(frame.loc[frame.explicitly_accepted_negative_candidate,'individually_reviewed_flag'].eq(True).sum()),
  strict_judgable=int(frame.personal_binary_strict_eligible.sum()),broad_judgable=int(frame.personal_binary_broad_eligible.sum()),
  targeted_audit=105,strict_severe_audit_overlap=int(frame.severe_and_unchanged_audit_overlap.sum()),broad_severe_audit_overlap=int(frame.broader_personal_and_unchanged_audit_overlap.sum()),
  reason_codes=frame.loc[frame.any_current_invalid,'reason_code'].value_counts().to_dict(),
  limitations=['targeted nonrandom review; rates are conditional on observed judgements','explicitly usable or retained_scope_variation are nonsevere negative candidates, not error-free gold labels','full-inventory count includes historical whole-worker exclusions, empty points, repeated exposure and superseded versions as distinct reasons; not restored to votes', 'strict vs broad rates have different determination sets; report numerator/denominator, not rank workers by the raw ratios'])
 dump(OUT/'reliability_receipt.json',receipt)
 print(json.dumps(receipt,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
