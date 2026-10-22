from pathlib import Path
import json, shutil, hashlib, subprocess, sys, platform
import numpy as np, pandas as pd, shapely, scipy
P=Path(__file__).resolve().parents[1];R=P.parent/'repo'
def dump(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf8')
f=R/'research/quality_ab_feedback_handoff_20261015/quality_ab_human_review_20261015_v1.json';shutil.copy2(f,P/'inputs/raw_feedback30.json')
d=json.loads(f.read_text());tab=pd.read_csv(P/'inputs/FEEDBACK_30_JOINED.csv').fillna('');rows=[]
for _,r in tab.iterrows():
 q=d['decisions'][r.case_id];b=q['bindings'][0];errs=[]
 for c,v in [('grade',q['grade']),('comment',q['comment']),('object_id',b['object_id']),('image_id',b['image_id']),('reference_id',b['reference_object_id'])]:
  if str(r[c]).strip()!=str(v).strip():errs.append(c)
 first=q['grade_at_first_score_reveal'];revealed=q['score_revealed_at'] is not None
 rows.append(dict(case_id=r.case_id,object_id=b['object_id'],phase=q['phase'],grade=q['grade'],comment=q['comment'],revealed=revealed,grade_before_first_reveal=bool(first),changed_since_first_reveal=bool(first and first!=q['grade']),raw_join_mismatches=','.join(errs)))
a=pd.DataFrame(rows);assert not a.raw_join_mismatches.any();a.to_csv(P/'results/raw_feedback_audit.csv',index=False)
dump(P/'results/raw_feedback_summary.json',dict(n=len(a),revealed=int(a.revealed.sum()),with_grade_at_first_reveal=int(a.grade_before_first_reveal.sum()),no_grade_at_first_reveal=a.loc[~a.grade_before_first_reveal,'case_id'].tolist(),changed_since_first_reveal=a.loc[a.changed_since_first_reveal,'case_id'].tolist(),all_grade_comment_identity_reference_matches=True,note='current AB30 receipt only; case IDs are local to this batch, not globally unique'))
current=R/'research/descriptive_statistics_rescored_20261016/quality_records.csv';hist=R/'research/quality_ab_feedback_handoff_20261015/prior_AB/results/SCORES_1145.csv'
for src,dest in [(current,'current891_frozen_components.csv'),(hist,'historical1145_frozen_components.csv')]:
 t=pd.read_csv(src);cols=[x for x in ['object_id','record_id','image_id','image_code','worker_id','condition','reference_id','current_target_id','use_panel','pool_source_workers','WQ','A10','Q_A10','B8L2','Q_B8L2','IoU3D100','iou_2d','S_bottom_deg','dir','Hmean','Hcenter'] if x in t];t[cols].to_csv(P/'inputs'/dest,index=False)
refs=json.loads((R/'research/scope_quality_rescore_20261016/reference_catalog.json').read_text());ids=set(pd.read_csv(current).reference_id);refs=[r for r in refs if r['target_id'] in ids]
dump(P/'inputs/current77_references.json',refs)
shutil.copy2(P/'results/current_matched_geometry_results.csv',P/'inputs/current227_frozen_audit.csv')
# Actual fresh loader import probe: failure is recorded, never labelled executed successfully.
cmd=[sys.executable,'-c','from tools.thesis_main.data_prep.consolidate_research_input import load_current_bundle; print(load_current_bundle())']
r=subprocess.run(cmd,cwd=R,capture_output=True,text=True,timeout=20)
(P/'results/live_loader_probe.txt').write_text('COMMAND: '+repr(cmd)+'\nRETURN_CODE: '+str(r.returncode)+'\nSTDOUT:\n'+r.stdout+'\nSTDERR:\n'+r.stderr,encoding='utf8')
archive=P.parent.parent/'quality_structure_handoff_20261016.zip'
prov=dict(archive_name=archive.name,archive_bytes=archive.stat().st_size,archive_sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),local_handoff_and_remote_main='f16394da8ddaaded0ad5c6c26156e6194fb6b92f',handoff_base='e3dcf9d11daf9390d6acc09974101f7b6b88a3dd',algorithm='RCS-0.2-20261016',execution_date_project_timezone='2026-10-16 Australia/Sydney',live_loader_return_code=r.returncode,original_images_viewed=0,lfs_real_content_recovered=False,lfs_expected_sha256='d4201b59acbfe0d2844ea073ca4888b4e5f3e894a0915b9c91ec14447c5a932e',lfs_expected_bytes=59490666,access_attempts=['GitHub API branch, directory, release and LFS pointer read succeeded','GitHub connector contract excludes binary downloads','container network/DNS and web media/release binary fetch failed','Library materialize for five prior ZIP resources returned no authorized raw-byte access'],source_snapshot_manifest='results/audit_summary.json',geometry_input_policy='unchanged snapshot answers; reference prebound by current registry; no best-score matching; no missing geometry synthesis',python=sys.version,numpy=np.__version__,pandas=pd.__version__,shapely=shapely.__version__,scipy=scipy.__version__)
dump(P/'PROVENANCE.json',prov)
(P/'requirements.txt').write_text('numpy=='+np.__version__+'\npandas=='+pd.__version__+'\nshapely=='+shapely.__version__+'\nscipy=='+scipy.__version__+'\npytest\n',encoding='utf8')
print(json.dumps(prov,ensure_ascii=False,indent=2));print((P/'results/raw_feedback_summary.json').read_text());print(r.stderr)
