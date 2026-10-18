import sys,json,time,hashlib,os
from pathlib import Path
BASE=Path(__file__).resolve().parents[2];P=BASE/'extracted/work_v2_20261019/fusion';OUT=Path(__file__).resolve().parent
sys.path.insert(0,str(P)); import fusion_engine as fe
from pool_io import read,clean,digest
import pandas as pd,numpy as np
pools=fe.load_pools(); byp={p['pool_id']:p for p in pools};t=pd.read_csv(P/'team_results.csv',low_memory=False)
# Deterministically select one eligible ordinary pool in every building, one pair at k16.
selected=[]
for b,g in t[t.layer.eq('ordinary_manual')&t.request_family.eq('fixed_background')&t.k.eq(16)].groupby('building'):
 pid=sorted(g.pool_id.unique(),key=lambda x:digest(['independent-audit-20261018',x]))[0];q=g[g.pool_id.eq(pid)];bid=sorted(q.background_id.unique())[0];selected.extend(q[q.background_id.eq(bid)].sort_values('request_id').head(2).request_id)
for (layer,status),g in t.groupby(['layer','score_status'],dropna=False):
 selected.append(g.sort_values('request_id').iloc[0].request_id)
selected=list(dict.fromkeys(selected));(OUT/'REPLAY_SELECTION.json').write_text(json.dumps(dict(rule='One deterministic ordinary k16 same-background replacement pair per building, plus one per layer/status; chosen without result magnitude',requests=selected),indent=2))
tr=t.set_index('request_id'); rows=[];lastpid=None;start=time.monotonic()
with fe.cached_matching(),fe.scoring_engine(fe.ENGINE/'measurement_engine.zip',fe.ENGINE/'working_models.py') as (engine,models):
 for rid in selected:
  saved=tr.loc[rid];pid=saved.pool_id;p=byp[pid]
  if lastpid!=pid:cache={x['team_id']:x['automatic'] for x in read(P/'pools'/pid/'states.json.gz')['states']};lastpid=pid
  lookup={r['worker_id']:r for r in p['records']};workers=sorted(saved.member_workers.split('|'));records=[lookup[w] for w in workers];ts=time.monotonic()
  state=fe.compact(fe.fuse(records,gap=fe.WORKING_GAP)['automatic']);expected=cache[saved.team_id]
  score=fe.compute_score(state,p,engine,models);row=dict(request_id=rid,pool_id=pid,building=saved.building,layer=saved.layer,k=int(saved.k),state_exact_equal=state==expected,score_status=score.get('score_status'),elapsed_seconds=time.monotonic()-ts)
  for met in ['B8L2','D10']:
   a,b=score.get(met),saved[met];row[met+'_missing_equal']=(a is None)==pd.isna(b);row[met+'_abs_difference']=None if a is None or pd.isna(b) else abs(a-b)
  rows.append(row);print(json.dumps(row),flush=True)
  (OUT/'SAVED_TEAM_REPLAY.json').write_text(json.dumps(dict(completed=len(rows),planned=len(selected),seconds=time.monotonic()-start,rows=rows),indent=2))
