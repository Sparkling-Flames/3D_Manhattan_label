"""Validate reconstructed missing tables against preserved overlapping evidence."""
from pathlib import Path
import json,hashlib,gzip,subprocess,sys
import pandas as pd,numpy as np
R=Path(__file__).resolve().parent;S=R.parent/'publication_stage_recovered';P=R/'venv/bin/python';O=R/'verification';O.mkdir(exist_ok=True)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
execres=json.loads((R/'EXECUTION_RESULT.json').read_text());assert all(v==0 for v in execres.values()),execres
native_integrity=json.loads((R/'NATIVE_REPLAY_INTEGRITY.json').read_text());assert native_integrity['all_restored_file_hashes_match'] and native_integrity['frozen_scripts_labels_and_requests_unchanged'] and native_integrity['total_frozen_endpoint_teams']==69164
frozen=json.loads((R/'FROZEN_RECOVERY_INPUTS.json').read_text())
for x in frozen['science_scripts_and_saved_labels']:assert sha(R/x['path'])==x['sha256'],x['path']
for x in frozen['requests']:assert sha(R/x['path'])==x['sha256'],x['path']
origbase=S/'research/workers/personnel_interchangeability_followup_20261020/audit_corner'
comparisons=[]
for folder in ['core','fresh_blocks','common_library','history_block_metrics','direct_block_assessment/B_direct_m2_composition_K2','direct_block_assessment/B_direct_m2_composition_K3']:
 dest=O/(folder.replace('/','_')+'.json');subprocess.run([str(P),str(R/'compare_recomputed.py'),'--new',str(R/'recomputed'/folder),'--old',str(origbase/folder),'--out',str(dest)],check=True,stdout=subprocess.DEVNULL)
 checks=json.loads(dest.read_text());assert all(x['semantic_pass'] for x in checks),(folder,checks);comparisons.append({'folder':folder,'tables_checked':len(checks),'rows_compared':sum(x['rows_old'] for x in checks),'all_semantic_checks_passed':True,'checks_file':str(dest.relative_to(R))})
 for name in ['CORNER_CHECKS.json','EVENT_DESIGN_COVERAGE.json']:
  a=origbase/folder/name;b=R/'recomputed'/folder/name
  if a.exists():assert json.loads(a.read_text())==json.loads(b.read_text()),(folder,name)
 old=origbase/folder/'COMMON_LIBRARY_RECEIPT.json';new=R/'recomputed'/folder/'COMMON_LIBRARY_RECEIPT.json'
 if old.exists():
  a=json.loads(old.read_text());b=json.loads(new.read_text())
  for key in ['request_sha256','frozen_anchors','endpoint_pairs','pools','images','buildings','mode','methods','failures','phase','labels_override_sha256']:
   if key in a:assert a[key]==b[key],(folder,key,a[key],b[key])
old=S/'research/statistics/personnel_interchangeability_audit_20261020/statistics/block_fit/tolerance';new=R/'audit_statistics/block_fit/tolerance';dest=O/'tolerance.json'
subprocess.run([str(P),str(R/'compare_recomputed.py'),'--new',str(new),'--old',str(old),'--out',str(dest)],check=True,stdout=subprocess.DEVNULL)
checks=json.loads(dest.read_text());assert all(x['semantic_pass'] for x in checks),checks
original_cdf_receipt=json.loads((old/'RECEIPT.json').read_text());new_cdf_receipt=json.loads((new/'RECEIPT.json').read_text())
# The preserved receipt was later augmented with original input hashes and
# validation. Compare original generation fields, then independently rerun
# the recorded validation instead of requiring absent metadata to be equal.
for key,value in new_cdf_receipt.items():assert original_cdf_receipt[key]==value,(key,value,original_cdf_receipt[key])
cdf_groups={};cdf_rows=0
for chunk in pd.read_csv(new/'EMPIRICAL_CDF.csv.gz',chunksize=100000):
 for key,g in chunk.groupby(['method','gate','metric','arm'],sort=False):
  x=g.tolerance.to_numpy();y=g.fraction_le.to_numpy();previous=cdf_groups.get(key)
  assert np.isfinite(x).all() and np.isfinite(y).all()
  assert np.all(np.diff(x)>=0) and np.all(np.diff(y)>=-1e-12)
  assert np.all((y>=-1e-12)&(y<=1+1e-10))
  if previous:assert x[0]>=previous['last_x'] and y[0]>=previous['last_y']-1e-12
  cdf_groups[key]={'last_x':float(x[-1]),'last_y':float(y[-1]),'rows':len(g)+(previous['rows'] if previous else 0)}
 cdf_rows+=len(chunk)
assert cdf_rows==original_cdf_receipt['cdf_validation']['rows']==new_cdf_receipt['rows']
assert len(cdf_groups)==original_cdf_receipt['cdf_validation']['series']
assert all(abs(g['last_y']-1)<=1e-10 for g in cdf_groups.values())
for relative,digest in original_cdf_receipt['inputs_sha256'].items():
 if relative.startswith('audit_learning/'):assert sha(R/relative)==digest,relative
cdf_validation={'rows':cdf_rows,'series':len(cdf_groups),'monotone_bounded_terminal_one':True,'receipt_generation_fields_match':True,'saved_label_hashes_match':True}
(O/'cdf_integrity.json').write_text(json.dumps(cdf_validation,indent=2))
comparisons.append({'folder':'block_fit/tolerance','tables_checked':len(checks),'rows_compared':sum(x['rows_old'] for x in checks),'all_semantic_checks_passed':True,'checks_file':str(dest.relative_to(R))})
mixed=json.loads((R.parent/'mixed_pair_recovery/MIXED_PAIRED_RECOVERY_RECEIPT.json').read_text());assert mixed['frozen_inputs_unchanged'] and mixed['no_model_refit'] and all(x['passed'] for x in mixed['retained_summary_checks'])
targets=json.loads((R.parent/'UNAVAILABLE_FILES.json').read_text());files=[]
for t in targets:
 name=t['path']
 if t['dependency_category']=='stale_unindexed_figure':continue
 if '/audit_corner/' in name:p=R/'recomputed'/name.split('/audit_corner/',1)[1]
 elif '/statistics/block_fit/tolerance/' in name:p=new/'EMPIRICAL_CDF.csv.gz'
 elif '/corner_fit_mixed/' in name:p=R.parent/'mixed_pair_recovery/paired_random_building.csv.gz'
 else:raise ValueError(name)
 assert p.is_file(),p
 rows=sum(len(x) for x in pd.read_csv(p,chunksize=100000,low_memory=False))
 files.append({'publication_path':name,'local_path':str(p),'bytes':p.stat().st_size,'sha256':sha(p),'rows':rows,'original_expected_bytes':t['bytes'],'original_expected_sha256':t['sha256'],'original_byte_identity':sha(p)==t['sha256'],'identity_note':'Regenerated with frozen inputs and unchanged science; retained overlapping tables and aggregates verified. Original missing full table unavailable for full-cell comparison.'})
assert len(files)==10
out={'recovered_table_count':10,'no_model_refit':True,'no_reselection':True,'frozen_source_inputs_unchanged':True,'full_archive_restoration':json.loads((R/'restored/RESTORATION_RECEIPT.json').read_text()),'files':files,'retained_evidence_comparisons':comparisons,'cdf_validation':cdf_validation,'mixed_retained_evidence_comparisons':mixed['retained_summary_checks'],'native_replay_integrity':native_integrity,'frozen_manifest_sha256':sha(R/'FROZEN_RECOVERY_INPUTS.json'),'not_reconstructed':['stale unindexed corner_continuous_004.png','19 unidentified packaging-only paths'],'publication_stage_modified':False}
(R/'DERIVED_TABLE_RECOVERY_RECEIPT.json').write_text(json.dumps(out,indent=2));print(json.dumps({'recovered_table_count':10,'bytes':sum(x['bytes'] for x in files),'rows':sum(x['rows'] for x in files),'receipt':str(R/'DERIVED_TABLE_RECOVERY_RECEIPT.json')},indent=2))
