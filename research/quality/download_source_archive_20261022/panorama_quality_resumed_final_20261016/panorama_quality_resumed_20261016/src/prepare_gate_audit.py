from pathlib import Path
import sys,json
import numpy as np,pandas as pd
ROOT=Path(__file__).resolve().parents[1];REPO=Path(sys.argv[1]);sys.path.insert(0,str(REPO))
from tools.thesis_main.data_prep.consolidate_research_input import load_current_bundle
import recompute_baseline as base
from score_manifest import geometry_hash
bundle=load_current_bundle();objs={o['object_id']:o for o in bundle['data']['objects']};base.initialize()
a=pd.read_csv(REPO/'research/statistics/descriptive_statistics_rescored_20261016/record_audit.csv');details=json.loads((ROOT/'inputs/current_difficulty.json').read_text());di={d['image_id']:d for d in details['records']};ref=pd.read_csv(ROOT/'inputs/reference_catalog.csv').set_index('target_id')
rows=[];diagnostic=[]
for _,r in a.iterrows():
 o=objs[r.object_id];d=di[r.image_id];gate=o['main_quality_gate'];oid=r.object_id
 z=dict(object_id=oid,image_id=r.image_id,image_code=r.image_code,condition=r.condition,worker_id=r.worker_id,source_pool_workers=int(r.pool_source_workers),independent_vote_eligible=bool(o['independent_vote_eligible']),raw_geometry_status=o['preprocessing_status'],ring_confirmed=o['ring_confirmed'],legacy_main_quality_status=gate['status'],legacy_main_quality_reasons='|'.join(gate['reasons']),current_target_id=d['target_version'],v6_difficulty=d['current_class'],v6_doorway_status=d['doorway_status'],gt_error_excluded=d['gt_error_excluded'],prior_full_score_eligible=bool(r.current_quality_eligible),target_changed_from_archived_score_audit=(r.current_target_id!=d['target_version']))
 rows.append(z)
 if d['doorway_status']!='annotatable':continue
 # Conditional mechanism calculations, NOT promotion into the approved cohort.
 # Existing raw exclusions, wrong identity, missing geometry/reference are still refused.
 if not o['independent_vote_eligible'] or o['worker_id'] in ['W019','W026'] or r.pool_source_workers<3 or o['preprocessing_status']!='ready':continue
 rid=d['target_version']
 if rid not in ref.index or not ref.loc[rid,'full_reference_available']:continue
 rp=json.loads(ref.loc[rid,'points_1024x512']);ap=o['points_1024x512']
 if ap is None:continue
 ag=base.engine.geometry(ap);rg=base.engine.geometry(rp)
 diagnostic.append(dict(object_id=oid,record_id=None if pd.isna(r.record_id) else r.record_id,image_id=r.image_id,image_code=r.image_code,worker_id=r.worker_id,condition=r.condition,reference_id=rid,current_target_id=rid,reference_complete=True,original_quality_eligible=False,source_pool_workers=int(r.pool_source_workers),answer=ag,reference=rg,answer_sha256=geometry_hash(ag),reference_sha256=geometry_hash(rg),ring_confirmed=o['ring_confirmed'],preserved_hold=gate,role='conditional doorway geometry stress calculation only; no admission and no parameter selection'))
pd.DataFrame(rows).to_csv(ROOT/'inputs/eligibility_ledger3152.csv',index=False);(ROOT/'inputs/doorway_conditional_pairs.json').write_text(json.dumps(diagnostic,ensure_ascii=False,allow_nan=False))
df=pd.DataFrame(rows);summary=dict(loader_annotations=len(rows),approved_cohort_unchanged=int(df.prior_full_score_eligible.sum()),doorway_annotatable_raw=int((df.v6_doorway_status=='annotatable').sum()),doorway_annotatable_prior_eligible=int(((df.v6_doorway_status=='annotatable')&df.prior_full_score_eligible).sum()),conditional_geometry_pairs=len(diagnostic),conditional_images=len({p['image_id'] for p in diagnostic}),conditional_ring_confirmed=sum(p['ring_confirmed'] for p in diagnostic),new_target_rows_changed=int(df.target_changed_from_archived_score_audit.sum()),source_pool_below3_rows=int((df.source_pool_workers<3).sum()),formal_doorway_calibration_completed=False)
(ROOT/'results/eligibility_summary.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary,indent=2))
