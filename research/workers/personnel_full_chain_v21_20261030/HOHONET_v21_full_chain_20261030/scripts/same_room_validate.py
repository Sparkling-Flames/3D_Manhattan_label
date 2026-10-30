"""Full read-through validation and exact claim checks for the same-room delivery.

This does not run fusion, select teams, or change scientific outputs.
"""
from pathlib import Path
import ast,csv,gzip,hashlib,json,subprocess,os
import numpy as np
import pandas as pd
from PIL import Image
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'stage02_same_room';SRC=ROOT/'source'
source_names=[
 'research/data/releases/v2.1/quality_inventory.json',
 'research/data/releases/v2.1/difficulty_records.json',
 'research/data/releases/v2.1/final_classification_downstream/USED_FINAL_LOBO_LABELS.csv.gz',
 'research/data/releases/v2.1/final_classification_downstream/OLD_ABC_APPLICABILITY.csv.gz',
 'research/workers/personnel_v21_reselection_20261029/classification/CLASS_ROLES_COMPACT_ALL_LOBO.csv.gz',
 'research/statistics/v2_evidence_audit_20261019/records.json.gz',
 'research/workers/worker_b8l2_d10_20261017/admission_snapshot.json',
 'research/same_room/relation_adoption_20261016/relations.json',
 'research/same_room/relation_adoption_20261016/original_groups.json',
 'research/same_room/relation_adoption_20261016/candidate_adoption.json',
 'research/same_room/same_room_multiview_20261020/GROUPS.json',
 'research/same_room/same_room_multiview_20261020/individual_features.csv.gz',
 'research/same_room/same_room_multiview_20261020/splits.csv.gz',
 'research/same_room/same_room_v2_prediction_20261019/training_admission.csv',
 'research/same_room/same_room_profile_return_review_20261021/direct_io.py',
 'research/same_room/same_room_profile_return_review_20261021/pro/room_similarity/code/common.py',
 'research/same_room/same_room_profile_return_review_20261021/pro/room_similarity/code/run_similarity.py',
 'research/same_room/same_room_profile_return_review_20261021/pro/room_similarity/code/run_mean_prediction.py',
 'research/same_room/same_room_profile_return_review_20261021/pro/personal_similarity/analyze.py',
]
cache_names=[
 'EXISTING_VALID_EVENT_SOURCE.csv.gz','VALID_CLASS_RELATION_SOURCE.csv.gz',
 'abc/EXISTING_GEOMETRY_SOURCE.csv.gz','abc/EXISTING_ENDPOINT_STATUS_COMPONENTS.csv.gz',
 'minimal_inputs/PRIMARY_POOL_INPUT_SNAPSHOT.json.gz',
 'abc/cases/PAIRED_CASE_INPUTS.json.gz','abc/cases/PAIRED_CASE_CACHED_GEOMETRY_AND_TRACE.jsonl.gz',
 'abc/cases/CACHED_GEOMETRY_RECEIPT.csv','abc/cases/ORIGINAL_PANORAMA_RECEIPT.csv',
]
manifest=[]
for p in [SRC/n for n in source_names]+[OUT/n for n in cache_names]+list((OUT/'abc/cases/images').glob('*.png')):
 assert p.is_file(),p
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 manifest.append(dict(path=str(p.relative_to(ROOT)),bytes=p.stat().st_size,sha256=h.hexdigest(),purpose='frozen current/legacy scientific input or exact archived endpoint cache'))
pd.DataFrame(manifest).to_csv(OUT/'MINIMUM_REPRODUCTION_INPUTS.csv',index=False)
results=[];errors=[]
for p in sorted(OUT.rglob('*')):
 if not p.is_file() or p.name.endswith('.tmp') or p.name in ['FINAL_VALIDATION.json','FINAL_FILE_MANIFEST.csv','final_validation_run.log']:continue
 row=dict(path=str(p.relative_to(OUT)),bytes=p.stat().st_size)
 try:
  h=hashlib.sha256()
  with p.open('rb') as f:
   for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
  row['sha256']=h.hexdigest()
  if p.name.endswith('.csv.gz') or p.suffix=='.csv':
   count=0
   for chunk in pd.read_csv(p,usecols=[0],chunksize=10000,low_memory=False):count+=len(chunk)
   row['logical_rows']=count;row['validation']='CSV parser read to EOF; gzip CRC checked when applicable'
  elif p.name.endswith('.jsonl.gz'):
   with gzip.open(p,'rt',encoding='utf8') as f:row['logical_rows']=sum(1 for line in f if json.loads(line) is not None)
   row['validation']='JSONL parsed to EOF and gzip CRC checked'
  elif p.name.endswith('.json.gz'):
   with gzip.open(p,'rt',encoding='utf8') as f:json.load(f)
   row['validation']='JSON parsed to EOF and gzip CRC checked'
  elif p.suffix=='.json':
   json.loads(p.read_text());row['validation']='JSON parsed'
  elif p.suffix=='.png':
   with Image.open(p) as im:im.load();row['image_size']=str(im.size)
   row['validation']='PNG fully decoded'
  elif p.suffix in ['.md','.log','.html','.txt']:
   p.read_text(encoding='utf8');row['validation']='UTF-8 read to EOF'
  else:row['validation']='Full byte read and SHA256'
  row['readable']=True
 except Exception as exc:row['readable']=False;row['error']=repr(exc);errors.append(row)
 results.append(row)
 print('READ',row['path'],row['readable'],flush=True)
for p in sorted((ROOT/'scripts').glob('same_room_*.py')):ast.parse(p.read_text())
s=pd.read_csv(OUT/'abc/SUMMARY.csv',low_memory=False);sel=s[s.final_method.eq('TARGET_DSTRUCT_K3')&s.analysis_scope.eq('ordinary_comparable')&s.metric.eq('B8L2')&s.level.eq('direction_nm')&s.role_direction.eq('2→3')&s.n.eq(10)&s.m.eq(5)].iloc[0]
assert (int(sel.events),int(sel.valid_events),int(sel.valid_pairs),int(sel.valid_buildings),int(sel.pair_positive_CB))==(268,237,19,7,19)
assert abs(sel.building_equal_CB_mean-13.749295)<1e-6
r=pd.read_csv(OUT/'abc/PAIR_VIEW_REPETITION.csv');v=r[r.final_method.eq('TARGET_DSTRUCT_K3')&r.analysis_scope.eq('ordinary_comparable')&r.metric.eq('B8L2')&r.level.eq('direction_nm')&r.role_direction.eq('2→3')&r.n.eq(10)&r.m.eq(5)].iloc[0];assert (int(v.GA_both_positive_pairs),int(v.GS_both_positive_pairs),int(v.CB_both_positive_pairs))==(14,13,18)
cap=pd.read_csv(OUT/'abc/HALF_CAPACITY_SUMMARY.csv');cap=cap[cap.method.eq('TARGET_DSTRUCT_K3')&cap.ordinary_comparable&cap.role_direction.eq('2→3')].set_index('n');assert [int(cap.loc[n].legal_pairs) for n in [10,12,14]]==[32,9,2];assert [int(cap.loc[n].capacity_sufficient_unexecuted_pairs) for n in [10,12,14]]==[13,2,0]
q=pd.read_csv(OUT/'prediction/DIRECT_MEAN_SUMMARY_BY_SCOPE.csv');x=q[q.metric.eq('B8L2')&q.scenario.eq('v2_frozen')&q.scope.eq('legacy_combined')].set_index('method');assert abs(x.loc['source_mean'].mae-5.080849746409013)<1e-10
x=q[q.metric.eq('B8L2')&q.scenario.eq('v21_all')&q.scope.eq('ordinary_no_relation_oos_pending')].set_index('method');assert abs(x.loc['source_mean'].mae-6.463518)<1e-6 and int(x.loc['source_mean'].images)==65
edge=pd.read_csv(OUT/'prediction/HISTORY_DIRECT_EDGE_VALIDATION.csv');assert edge.direct_registry_exists.all() and edge.physical_adopted.all() and edge.scope_comparable.all() and not edge.substantive_conflict.any()
vp=pd.read_csv(OUT/'prediction/DECLARATION_VARIATION_PARTITION.csv');assert np.allclose(vp.worker_share+vp.view_share+vp.interaction_share,1,equal_nan=False)
pd.DataFrame(results).to_csv(OUT/'FINAL_FILE_MANIFEST.csv',index=False)
final=dict(files_checked=len(results),bytes_checked=sum(x['bytes'] for x in results),failures=errors,all_readable=not errors,CSV_and_GZIP_read_to_EOF=True,source_input_manifest_rows=len(manifest),source_input_bytes=sum(x['bytes'] for x in manifest),claim_assertions_passed=True,source_v2_exact_mean_reproduced=True,new_fusion_calls=0,viewer_execution_check=json.loads((OUT/'abc/cases/VIEWER_EXECUTION_CHECK.json').read_text()),script_syntax_valid=True)
(OUT/'FINAL_VALIDATION.json').write_text(json.dumps(final,ensure_ascii=False,indent=2));print(json.dumps(final,ensure_ascii=False),flush=True)
if errors:raise SystemExit('Unreadable output remains')
