"""Select reproducibility deliverables explicitly; preserve extensionless licenses."""
from pathlib import Path
import hashlib,json,zipfile
ROOT=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def pack(path,pairs):
 pairs=sorted(pairs,key=lambda x:x[1]);manifest={name:{'bytes':p.stat().st_size,'sha256':sha(p)} for p,name in pairs}
 with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
  for p,name in pairs:z.write(p,name)
  z.writestr('FILE_MANIFEST_SHA256.json',json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
 with zipfile.ZipFile(path) as z:
  assert z.testzip() is None
  for name,v in manifest.items():assert hashlib.sha256(z.read(name)).hexdigest()==v['sha256']
 return {'file':str(path),'bytes':path.stat().st_size,'sha256':sha(path),'n_files_including_manifest':len(pairs)+1,'manifest_and_CRC_verified':True}
def main():
 files=[]
 for directory in ['code','frozen','inputs','logs','reports','results','history']:
  for p in (ROOT/directory).rglob('*'):
   if not p.is_file() or '__pycache__' in p.parts or p.suffix=='.pyc':continue
   if p.name in ['current_geometry.json','current_full_results.json','user_sample_exact_v0.zip','answer_mapping_exact_v0.zip','delivery_revision2_local.json','package_revision2.log','delivery_revision2_with_blocker.json','full_results_3152.jsonl','projected_objects_3441.json']:continue
   if p.parent.name=='Pro_full_current_pipeline_replay' and p.name=='score_rows_3152.csv':continue # byte-identical original already frozen
   files.append((p,str(p.relative_to(ROOT))))
 for name in ['README.md','RUN_COMMANDS.txt','requirements.txt']:files.append((ROOT/name,name))
 for name in ['answer_mapping_private.json','selection_audit.json','render_manifest.json','user_response_blank.csv']:files.append((ROOT/'blind_sample'/name,'blind_sample/'+name))
 # Preserve licenses by directory membership, including files with no suffix.
 assert any(p.name=='LICENSE' for p,n in files)
 user=[(p,p.name) for p in (ROOT/'blind_sample/user').iterdir() if p.is_file()]
 answer=[(ROOT/'blind_sample'/n,n) for n in ['answer_mapping_private.json','selection_audit.json','render_manifest.json']]
 answer.extend((ROOT/'results'/n,n) for n in ['room_holdout_manifest.csv','regularity_sample_pair_candidates.json','regularity_sample_selection_audit.json','target_alignment_summary.json','revision_validation.json'])
 answer.append((ROOT/'reports/BLIND_SELECTION_CONTRACT.md','BLIND_SELECTION_CONTRACT.md'))
 small=[(p,n) for p,n in files if n.startswith(('code/','reports/','frozen/scope_engine/')) or (n.startswith('frozen/Pro_selected_original/') and (p.suffix=='.py' or p.name in ['preregistered_candidates.json','source_manifest.json','LICENCE'])) or p.name in ['README.md','RUN_COMMANDS.txt','requirements.txt','stage1_summary.json','stage2_summary.json','stage3_summary.json','AB_mapping.json','AB_mapping.csv','target_distance_matrix.csv','AB_margins_all_events.csv','routing_sensitivity_summary.csv','space_match_tests.json','target_alignment_summary.json','target_alignment_ledger.csv','revision_validation.json','net42_current_diagnostic_sources.csv','net42_source_summary.json','parent_Pro_record_closure_evidence.json','current_components.csv','Pro_source_replay_summary.json','Pro_full_pipeline_comparison_summary.json','Pro_stage_enumeration_summary.json','Pro_selected_manifest_verification.json','quality_threshold_necessary_envelopes.csv','quality_joint_condition_evidence.json']]
 out=[pack(Path('/workspace/quality_blind_sample_user_20261010.zip'),user),pack(Path('/workspace/quality_blind_sample_answer_mapping_20261010.zip'),answer),pack(Path('/workspace/quality_cloud_compute_review_20261010.zip'),files),pack(Path('/workspace/quality_stage1_2_review_20261010.zip'),small)]
 (ROOT/'results/delivery_revision2_local.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n');print(json.dumps(out,indent=2))
if __name__=='__main__':main()
