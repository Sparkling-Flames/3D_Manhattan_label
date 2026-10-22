"""Record source hashes, tested versions, and complete missingness denominators."""
import hashlib,importlib.metadata,json,platform,subprocess
from pathlib import Path
import pandas as pd
from paths import REPO,OUT,STUDY

def digest(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
 return h.hexdigest()

def main():
 expected='c4dd8266c42a478c68b0dce8097c98e33e4b32b2'
 head=subprocess.check_output(['git','-C',str(REPO),'rev-parse','HEAD'],text=True).strip();assert head==expected
 paths={}
 def add(path,role):paths.setdefault(path.replace('\\','/'),set()).add(role)
 bundle='analysis_results/research_input_20261017/'
 manifest=json.loads((REPO/(bundle+'manifest.json')).read_text());add(bundle+'manifest.json','current loader entry')
 for key,path in manifest['entrypoints'].items():add(bundle+path,'current loader '+key)
 for path,role in [('research/quality/quality_joint_closeout_review_20261015/pro_closeout_delta.zip','frozen geometry engine'),('research/statistics/b8l2_shared_v6_20261016/inputs/working_models.py','frozen B8L2/D10 model definitions'),('research/quality/quality_b8l2_d10_20261017/reference_catalog.json','fixed reference geometries'),('research/quality/quality_b8l2_d10_20261017/shared_records.csv','current same-reference final scoring and eligibility'),('research/quality/quality_b8l2_d10_20261017/difficulty_records.json','current task scene and difficulty'),('research/workers/worker_b8l2_d10_20261017/personnel_ledger.csv','current Q/T inventory and original holdout'),('research/workers/worker_b8l2_d10_20261017/admission_snapshot.json','unchanged original personnel/context gates'),('research/workers/worker_four_axis_update_20261015/scope_records.csv','published 1013-scope binding/parity and later holds'),('analysis_results/uncertainty_cloud_inputs_20260906_v1/facts/proposal_response.csv.gz','574 proposal/raw-final bridge'),('analysis_results/annotation_research_prework_20260905_v2/evidence/initialization_trace.csv','574 exact initialization trace'),('analysis_results/prescreen_closeout_final_gold_v2_20260701/final_gold_records_v2_p1_closeout_corrected.jsonl','explicit historical task scope gold'),('analysis_results/prescreen_closeout_final_gold_v2_20260701/raw_inputs/prescreen_synthetic_expert_review.csv','six expert realized initialization defects and scope')]:add(path,role)
 ini=pd.read_csv(OUT/'initialization_evidence_574.csv')
 for p in ini.runtime_source.unique():add(p,'actual runtime initializer preview/raw worker final')
 for value in ini.import_paths:
  for p in json.loads(value):add(p,'formal deployed prediction payload')
 scope=pd.read_csv(OUT/'scope_object_ledger.csv')
 for p in scope.raw_source_path.unique():add(p,'exact task/annotation/worker scope choices')
 lfs={bundle+'data.json',bundle+'comments.json','research/quality/quality_joint_closeout_review_20261015/pro_closeout_delta.zip'}
 rows=[]
 for rel,roles in sorted(paths.items()):
  p=REPO/rel;row=dict(repository_path=rel,roles=' | '.join(sorted(roles)),bytes=p.stat().st_size,sha256=digest(p),repo_commit=head,lfs_pointer=False)
  if rel in lfs:
   gitblob=subprocess.check_output(['git','-C',str(REPO),'show','HEAD:'+rel])
   if gitblob.startswith(b'version https://git-lfs.github.com/spec/v1'):
    pointer=gitblob.decode('utf8');oid=next(x.split('sha256:')[1] for x in pointer.splitlines() if x.startswith('oid sha256:'));size=int(next(x.split()[1] for x in pointer.splitlines() if x.startswith('size ')))
    assert oid==row['sha256'] and size==row['bytes'];row.update(lfs_pointer=True,lfs_sha256=oid,lfs_bytes=size,lfs_restored_and_verified=True)
   else:
    assert hashlib.sha256(gitblob).hexdigest()==row['sha256'];row['ordinary_git_blob_verified']=True
  rows.append(row)
 pd.DataFrame(rows).to_csv(OUT/'source_provenance_manifest.csv',index=False,encoding='utf-8-sig')
 modules={}
 for name in ['numpy','pandas','scipy','shapely','scikit-learn','matplotlib','Pillow']:
  try:modules[name]=importlib.metadata.version(name)
  except importlib.metadata.PackageNotFoundError:modules[name]='not installed in this interpreter'
 code=Path(__file__).resolve().parent
 inputs=[dict(path='q/'+p.name,sha256=digest(p),bytes=p.stat().st_size) for p in [STUDY/'q/analyze_q.py',STUDY/'q/worker_profiles_enriched.csv',STUDY/'q/fold_profiles_recomputed.csv']]
 q=pd.read_csv(STUDY/'q/worker_profiles_enriched.csv');mainworkers=set(q.worker_id)
 ledger=pd.read_csv(OUT/'reliability_object_ledger.csv');cor=pd.read_csv(OUT/'correction_object_ledger.csv');s=pd.read_csv(OUT/'semi_scores_b8l2_d10.csv')
 coverage=[('all_submissions','raw_source_identity_bound',3222,int(scope.raw_binding_verified.sum()),'Raw task, annotation and worker identity; no screen viewing claim.'),
  ('all_submissions','recorded_scope_choice',3222,int(scope.raw_scope_recorded.sum()),'Five scope responses missing; no geometry-to-scope inference.'),
  ('all_submissions','original_protocol_scope_gold_after_holds',3222,int(scope.historical_eligible.sum()),'1429 known original task gold; all remaining current-policy correctness unpromoted.'),
  ('all_submissions','current_compatible_clear_in_scope',3222,int(scope.current_clear_in_scope_adjudicated.sum()),'Clear current scene and original explicit in-scope; OOS narrower historical diagnostic separate.'),
  ('all_submissions','strict_personal_severe_binary_judgable',3222,int(ledger.personal_binary_strict_eligible.sum()),'25 specific personal positives + 999 explicitly reviewed accepted negative candidates; selectively reviewed.'),
  ('all_submissions','broad_personal_nonacceptance_binary_judgable',3222,int(ledger.personal_binary_broad_eligible.sum()),'68 broad personal positives + 999 explicit accepted negative candidates; different outcome definition.'),
  ('semi_submissions','actual_deployed_coordinate_payload',574,int(ini.initialization_source_verified.sum()),'All import payloads and runtime preview coordinates agree.'),
  ('semi_submissions','historical_checkpoint_bound',574,0,'Checkpoint not recovered.'),
  ('semi_submissions','screen_render_and_user_view_event_verified',574,0,'No reconstruction/observation of exact UI wall rendering or user viewing.'),
  ('semi_submissions','initialization_ring_supported_by_existing_point_identity',574,int(s.initial_ring_status.eq('existing_confirmed_ring_exact_point_identity').sum()),'413 native rings retained unconfirmed; 0 conflicting existing rings.'),
  ('semi_submissions','same_reference_initial_score',574,int(s.initial_score_status.eq('complete').sum()),'19 reference-full-points unavailable; score is compatible-ring measurement diagnostic.'),
  ('semi_submissions','same_reference_final_score',574,int(s.final_score_status.eq('complete').sum()),'55 unavailable: 36 annotation paired points unavailable; 19 reference full points missing.'),
  ('semi_submissions','worker_delta_under_measurement_view',574,int(s.worker_gain_attributable_under_current_view.sum()),'519 paired minus five researcher point repairs; missing values are not zeros.'),
  ('semi_submissions','actual_initial_error_adjudicated_opportunity',574,int(cor.confirmed_initialization_error_opportunity.sum()),'156 across six expert tasks; remaining 418 not adjudicated as actual error or correct initializations.'),
  ('actual_initial_error_opportunities','error_specific_final_outcome_known',156,int(cor.known_error_unchanged.sum()),'25 persistent by unchanged coordinates; 131 edited outcomes unknown; no inferred repairs.'),
  ('main24_actual_initial_error_opportunities','error_specific_final_outcome_known',144,int(cor.loc[cor.worker_id.isin(mainworkers),'known_error_unchanged'].sum()),'20 persistent;124 edited unknown; opportunity denominator does not use quality_usable.')]
 c=pd.DataFrame([dict(population=p,measure=m,opportunity_denominator=n,observed_or_judgable=k,unknown_or_not_available=n-k,interpretation=t) for p,m,n,k,t in coverage]);c.to_csv(OUT/'coverage_and_unknown_states.csv',index=False,encoding='utf-8-sig')
 n_lfs=sum(bool(r['lfs_pointer']) for r in rows)
 comparison=json.loads((OUT/'reproduction_comparison_receipt.json').read_text()) if (OUT/'reproduction_comparison_receipt.json').exists() else dict(comparison='No separately saved comparison receipt in this output directory.',run_evidence=json.loads((OUT/'run_evidence.json').read_text()) if (OUT/'run_evidence.json').exists() else None)
 receipt=dict(data_release='v1',repository_url='https://github.com/Sparkling-Flames/3D_Manhattan_label',repo_commit=head,effective_input_revision=manifest['effective_input_revision'],source_files=len(rows),lfs_payloads_verified=n_lfs,python=platform.python_version(),tested_dependency_versions=modules,q_inputs=inputs,
  analysis_code=[dict(file=p.name,sha256=digest(p)) for p in sorted(code.glob('*.py'))],manual_coding_file=dict(file='review_reason_adjudications_v1.json',sha256=digest(code/'review_reason_adjudications_v1.json')),
  reproducibility=comparison,
  omitted_regenerable_caches=['validated_annotations.json','validated_images.json','semi_measurement_records.json','semi_payload_measurement_records.json'],
  source_policy='Pinned repository + LFS payloads; no geometry formulas, source verdicts, eligibility or vote counts modified.')
 (OUT/'reliability_provenance_receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf8');print(json.dumps(dict(repo_commit=head,source_files=len(rows),lfs_payloads_verified=n_lfs,tested_dependency_versions=modules),ensure_ascii=False,indent=2))

if __name__=='__main__':main()
