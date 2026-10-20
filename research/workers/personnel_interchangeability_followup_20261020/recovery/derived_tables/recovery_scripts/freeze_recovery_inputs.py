from pathlib import Path
import json,hashlib,gzip
R=Path(__file__).resolve().parent
P=R.parent/'publication_stage_recovered'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
sources=[]
for area in ['audit_corner','audit_learning']:
 for p in sorted((R/area).rglob('*')):
  if p.is_file() and (p.suffix=='.py' or p.name.endswith('labels.csv') or p.name=='METHOD_MANIFEST.json' or p.name=='LABEL_OVERRIDE.json' or p.name.endswith('requests.json.gz')):
   old=P/'research/workers/personnel_interchangeability_followup_20261020'/p.relative_to(R)
   if old.exists():assert sha(p)==sha(old),(p,'frozen copy changed')
   sources.append({'path':str(p.relative_to(R)),'bytes':p.stat().st_size,'sha256':sha(p),'original_staged_bytes_equal':old.exists()})
requests=[]
for mode,p in [('core',R/'unpacked/interchangeability_20261020/core_replay/CORE_REQUESTS.json.gz'),('fresh',R/'audit_learning/fresh_blocks/fresh_block_requests.json.gz'),('history',R/'audit_learning/history_blocks/history_block_requests.json.gz'),('h20',R/'unpacked/interchangeability_20261020/history_panel/history_requests.json.gz')]:
 j=json.load(gzip.open(p,'rt'));rows=j['requests'];keys={(x['pool_id'],tuple(sorted(x['worker_ids']))) for x in rows};requests.append({'mode':mode,'path':str(p.relative_to(R)),'sha256':sha(p),'request_rows':len(rows),'unique_frozen_teams':len(keys)})
cdf=R/'audit_statistics/block_tolerance_cdf.py';old=P/'research/statistics/personnel_interchangeability_audit_20261020/statistics/block_tolerance_cdf.py'
assert old.read_text().replace("R/'audit_corner/history_block_metrics/COMMON_ENDPOINT_PAIRS.csv.gz'","R/'recomputed/history_block_metrics/COMMON_ENDPOINT_PAIRS.csv.gz'")==cdf.read_text()
r={'science_scripts_and_saved_labels':sources,'requests':requests,'cdf_path_only_change':{'original_sha256':sha(old),'local_sha256':sha(cdf),'change':'Input path redirected to isolated recomputed table; mathematical operations unchanged.'},'no_model_refit':True,'no_reselection':True}
(R/'FROZEN_RECOVERY_INPUTS.json').write_text(json.dumps(r,indent=2));print(json.dumps(requests,indent=2));print('Frozen files',len(sources))
