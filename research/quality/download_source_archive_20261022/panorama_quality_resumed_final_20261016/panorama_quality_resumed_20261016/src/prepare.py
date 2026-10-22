"""Freeze a fixed approved cohort, applying the actual manifest loader and v6 checks.
No candidate is selected by score. v4 rows are retained only if object/reference/
target/eligibility still agree with the current snapshot. Changed rows go to gaps.
"""
from pathlib import Path
import sys,json,hashlib,shutil,importlib.util
import numpy as np
import pandas as pd
OUT=Path(__file__).resolve().parents[1]
REPO=Path(sys.argv[1]).resolve()
sys.path.insert(0,str(REPO))
from tools.thesis_main.data_prep.consolidate_research_input import load_current_bundle
bundle=load_current_bundle();objects={o['object_id']:o for o in bundle['data']['objects']}
ptrpath=REPO/'analysis_results/image_difficulty_full_review_20261010/CURRENT.json'
ptr=json.loads(ptrpath.read_text(encoding='utf-8-sig'))
diffpath=(ptrpath.parent/ptr['details']).resolve();detail=json.loads(diffpath.read_text(encoding='utf-8-sig'))
diffs={d['image_id']:d for d in detail['records']}
rows=pd.read_csv(REPO/'research/statistics/descriptive_statistics_rescored_20261016/quality_records.csv')
refs=pd.read_csv(REPO/'research/statistics/descriptive_statistics_rescored_20261016/space_reference_catalog.csv').set_index('target_id').to_dict('index')
engine_path=REPO/'analysis_results/quality/quality_joint_closeout_review_20261015/local_replay'
spec=importlib.util.spec_from_file_location('frozen_measure',engine_path/'src/quality.py');engine=importlib.util.module_from_spec(spec);spec.loader.exec_module(engine)
def sha(x):return hashlib.sha256(json.dumps(x,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def cleanval(v):
 if isinstance(v,(bool,np.bool_)):return bool(v)
 if isinstance(v,np.generic):return v.item()
 if isinstance(v,float) and not np.isfinite(v):return None
 return v
pairs=[];meta=[];gaps=[];refpts_delta=[]
for _,rr in rows.iterrows():
 row={k:cleanval(v) for k,v in rr.items()};o=objects[row['object_id']];d=diffs[row['image_id']];ref=refs[row['reference_id']]
 reasons=[]
 for k in ['image_id','worker_id','condition']:
  assert row[k]==o[k],(row['object_id'],k)
 assert row['current_quality_eligible'] and row['pool_analysis_eligible'] and row['pool_source_workers']>=3
 assert row['worker_id'] not in ['W019','W026']
 if row['current_target_id']!=d['target_version']:reasons.append('target_changed_requires_new_binding_and_reference')
 if d.get('gt_error_excluded'):reasons.append('current_gt_error')
 if not d.get('difficulty_analysis_eligible'):reasons.append('current_image_gate:'+d.get('difficulty_analysis_exclusion',''))
 if not ref['full_reference_available']:reasons.append('full_reference_missing')
 if ref['image_id']!=row['image_id']:reasons.append('reference_image_mismatch')
 if reasons:
  gaps.append(dict(object_id=o['object_id'],image_id=o['image_id'],reasons=reasons));continue
 rp=json.loads(ref['points_1024x512']);ap=o['points_1024x512']
 if row['reference_id'] in objects:
  native=objects[row['reference_id']]['points_1024x512']
  assert np.array_equal(native,rp),'reference live points changed '+row['reference_id']
 a=engine.geometry(ap);g=engine.geometry(rp)
 cut=[] if pd.isna(ref.get('introduced_scope_edges')) else json.loads(ref['introduced_scope_edges'])
 if cut:assert len(cut)<len(g['bottom3d'])
 pair=dict(object_id=o['object_id'],record_id=row['record_id'],image_id=o['image_id'],image_code=o['image_code'],worker_id=o['worker_id'],condition=o['condition'],building_id=o['building_id'],reference_id=row['reference_id'],current_target_id=d['target_version'],reference_version=ref['reference_version'],answer=a,reference=g,answer_points=ap,reference_points=rp,answer_sha256=sha(a),reference_sha256=sha(g),answer_points_sha256=sha(ap),reference_points_sha256=sha(rp),introduced_scope_edges=cut,vertex_sources=None if pd.isna(ref.get('vertex_sources')) else json.loads(ref['vertex_sources']),physical_wall_asserted=cleanval(ref.get('physical_wall_asserted')),source_pool_workers=row['pool_source_workers'],input_revision=bundle['manifest'].get('effective_input_revision'),difficulty_version=detail['version'],difficulty=d['current_class'],conditional_difficulty=d['conditional_difficulty'],doorway_status=d.get('doorway_status','not_recorded'),oos_subtype=d.get('oos_subtype','not_recorded'),reference_complete=True,original_quality_eligible=True)
 pairs.append(pair)
 meta.append(dict(**row,difficulty_v6=d['current_class'],conditional_difficulty_v6=d['conditional_difficulty'],doorway_status_v6=d.get('doorway_status','not_recorded'),oos_subtype_v6=d.get('oos_subtype','not_recorded'),difficulty_version_v6=detail['version'],difficulty_basis_v6=d.get('classification_basis'),new_reference_sha256=sha(g),new_answer_sha256=sha(a),introduced_scope_edge_count=len(cut)))
(OUT/'inputs/fixed_pairs.json').write_text(json.dumps(pairs,ensure_ascii=False,allow_nan=False,separators=(',',':')))
pd.DataFrame(meta).to_csv(OUT/'inputs/cohort_metadata.csv',index=False,encoding='utf-8-sig')
(OUT/'inputs/current_difficulty.json').write_text(json.dumps(detail,ensure_ascii=False,indent=2))
feedback=REPO/'research/quality/quality_three_routes_feedback_20261016'
for name in ['README.md','CASE_REVIEW.md','SOURCE_INDEX.json','reviewed_snapshot.json','quality_three_routes_review_20261016_v1.json']:
 dest=OUT/'inputs/review24'/name;dest.parent.mkdir(exist_ok=True);shutil.copy2(feedback/name,dest)
for src in (feedback/'received/external_audit').glob('*.json'):
 dest=OUT/'inputs/external_controls'/src.name;dest.parent.mkdir(exist_ok=True);shutil.copy2(src,dest)
# Save standalone engine files that were really consumed; no dependency stubs.
vendor=OUT/'vendor/frozen';vendor.mkdir(parents=True,exist_ok=True)
for dr in ['engine','configs','src']:
 for f in (engine_path/dr).glob('*'):
  if f.suffix in ['.py','.json'] and (dr!='src' or f.name=='quality.py'):
   target=vendor/dr/f.name;target.parent.mkdir(exist_ok=True);shutil.copy2(f,target)
models=REPO/'research/quality/quality_ab_feedback_handoff_20261015/prior_AB/src/working_models.py'
shutil.copy2(models,OUT/'vendor/working_models.py')
# Preserve full reference metadata, including cuts, not just sampled points.
shutil.copy2(REPO/'research/statistics/descriptive_statistics_rescored_20261016/space_reference_catalog.csv',OUT/'inputs/reference_catalog.csv')
shutil.copy2(diffpath.parent/'new_scope_references.json',OUT/'inputs/v6_new_scope_references.json')
shutil.copy2(REPO/'analysis_results/research_input_20260929/manifest.json',OUT/'inputs/source_manifest.json')
source_paths=[ptrpath,diffpath,models]
source_paths += [REPO/'analysis_results/research_input_20260929'/f for f in ['manifest.json','preprocessed_source.json','quality_update_20261010.json','floor_scope_update_20261015.json']]
summary=dict(current_repo='6fb0f7a88078bbf57a17d955e044fac2ec8943c7',loader=bundle['validation'],cohort_original_rows=len(rows),current_compatible_rows=len(pairs),images=len({p['image_id'] for p in pairs}),workers=len({p['worker_id'] for p in pairs}),conditions=pd.Series([p['condition'] for p in pairs]).value_counts().to_dict(),removed_rows=gaps,new_targets_not_admitted=['user_space_20261016:S9hNv5qa7GM-09','user_space_20261016:zsNo4HB9uLZ-13'],cohort_definition='approved v4 scored cohort revalidated against actual loader and v6 target/eligibility; not all 3152 annotations',source_files={str(p.relative_to(REPO)):dict(bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in source_paths},uploaded_current259_identical=(Path('/mnt/data/current_259.csv').read_bytes()==(diffpath.parent/'current_259.csv').read_bytes()))
(OUT/'results/input_audit.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2));print(json.dumps(summary,ensure_ascii=False,indent=2))
