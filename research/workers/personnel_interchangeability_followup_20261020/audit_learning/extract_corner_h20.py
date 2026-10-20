"""Extract original metrics and supplementary corners from frozen H20 endpoints."""
import os
for k in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS']:os.environ[k]='1'
import sys,json,gzip,itertools,hashlib,time,argparse
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor
import pandas as pd
ROOT=Path(__file__).resolve().parents[1];BASE=Path(__file__).resolve().parent;P=ROOT/'unpacked';S=P/'interchangeability_20261020'
sys.path[:0]=[str(ROOT/'audit_corner'),str(P/'analysis/composition'),str(S/'reverse')]
from corner_distance import corner_compare
from summarize_grid import pair_metrics,signature
from learn_swap_types import READ_COLUMNS
OUT=BASE/'corner_h20';OUT.mkdir(exist_ok=True)
def read(p):return json.load(gzip.open(p,'rt'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def process(task):
 pid,anchors=task;np=ROOT/'audit_replay/history_native/pools'/(pid+'.json.gz');dest=OUT/(pid+'.csv.gz');receipt=OUT/(pid+'.receipt.json')
 if dest.exists() and receipt.exists():
  r=json.loads(receipt.read_text())
  try:
   if r['rows']==len(pd.read_csv(dest)) and r['corner_code_sha256']==sha(ROOT/'audit_corner/corner_distance.py'):return {'pool_id':pid,'cached':True,'rows':r['rows']}
  except Exception:pass
 native=read(np);assert native['context']['science_commit']=='82c6164b0d4630de5316199c92aa405930973168'
 teams={r['team_key']:r for r in native['teams']};sigs={k:signature(v) for k,v in teams.items()};features=pd.read_csv(S/'forward/features_train.csv.gz');origin=features.set_index('worker_id').person_origin.to_dict();rows=[];seen=set();t=time.perf_counter()
 for anc in anchors:
  core=set(anc['core_workers']);assert len(core)==anc['k']-1
  for wa,wb in itertools.combinations(sorted(anc['entrant_workers']),2):
   ka,kb=anc['entrant_teams'][wa],anc['entrant_teams'][wb];a,b=teams[ka],teams[kb];assert set(a['member_workers'])==core|{wa};assert set(b['member_workers'])==core|{wb}
   for k in ['pool_id','image_id','reference_id','reference_version']:assert a[k]==b[k]
   physical=tuple(sorted([ka,kb]));
   if physical in seen:continue
   seen.add(physical);m=pair_metrics(a,b,sigs[ka],sigs[kb]);assert m['turnover']==1
   row={c:None for c in READ_COLUMNS};row.update({k:v for k,v in m.items() if k in row})
   row.update(event_id='H20pair_'+hashlib.sha256(json.dumps([anc['anchor_id'],wa,wb]).encode()).hexdigest()[:24],panel_id='H20_metadata_allentrant_v1',pool_id=pid,image=a['image'],image_id=a['image_id'],building=a['building'],difficulty=a['difficulty'],condition=a['condition'],layer=a['layer'],reference_id=a['reference_id'],reference_version=a['reference_version'],k=anc['k'],background_id=anc['anchor_id'],background_members='|'.join(sorted(core)),worker_a=wa,worker_b=wb,request_a=ka,request_b=kb,team_id_a=ka,team_id_b=kb,member_workers_a='|'.join(sorted(a['member_workers'])),member_workers_b='|'.join(sorted(b['member_workers'])),entrant_origin_a=origin[wa],entrant_origin_b=origin[wb],B8L2_a=a.get('B8L2'),B8L2_b=b.get('B8L2'),D10_a=a.get('D10'),D10_b=b.get('D10'),nodes_a=a.get('nodes'),nodes_b=b.get('nodes'))
   corner,_=corner_compare(a,b);row.update(corner);rows.append(row)
 f=pd.DataFrame(rows);tmp=dest.with_suffix('.tmp.gz');f.to_csv(tmp,index=False,compression={'method':'gzip','mtime':0});assert len(pd.read_csv(tmp))==len(rows);tmp.replace(dest)
 rec={'pool_id':pid,'rows':len(rows),'elapsed_seconds':time.perf_counter()-t,'native_sha256':sha(np),'corner_code_sha256':sha(ROOT/'audit_corner/corner_distance.py'),'original_comparator_sha256':sha(P/'analysis/composition/summarize_grid.py')};receipt.write_text(json.dumps(rec,indent=2));return rec
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--jobs',type=int,default=4);ap.add_argument('--available',action='store_true');args=ap.parse_args();design=read(S/'history_panel/history_anchors.json.gz');groups={}
 for a in design['anchors']:groups.setdefault(a['pool_id'],[]).append(a)
 tasks=[(p,a) for p,a in sorted(groups.items()) if not args.available or (ROOT/'audit_replay/history_native/pools'/(p+'.json.gz')).exists()]
 with ProcessPoolExecutor(max_workers=args.jobs) as pool:
  for r in pool.map(process,tasks):print(json.dumps(r),flush=True)
 if len(tasks)==len(groups):
  f=pd.concat([pd.read_csv(OUT/(p+'.csv.gz')) for p in sorted(groups)],ignore_index=True);assert len(f)==359916 and f.event_id.is_unique
  f[READ_COLUMNS].to_csv(BASE/'native_history_events_rebuilt.csv.gz',index=False,compression={'method':'gzip','mtime':0})
  (BASE/'H20_EXTRACTION_RECEIPT.json').write_text(json.dumps({'pools':len(groups),'rows':len(f),'unique_events':True,'all_original_metrics_retained':True,'schema_new_corner_not_overwriting_original':True},indent=2))
 print(json.dumps({'available_pools':len(tasks),'expected_pools':len(groups)}),flush=True)
