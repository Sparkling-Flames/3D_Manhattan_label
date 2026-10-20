"""Check new metric against small retained prior-panel inputs, without refusion."""
import argparse,gzip,json
from pathlib import Path
import pandas as pd
from corner_distance import corner_compare
p=argparse.ArgumentParser();p.add_argument('--inputs',type=Path,default=Path(__file__).resolve().parent);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
teams=json.load(gzip.open(a.inputs/'prior_teams.json.gz'));events=pd.read_csv(a.inputs/'prior_events.csv.gz');old=pd.read_csv(a.inputs/'prior_pairs.csv.gz');rows=[]
for r in events.itertuples():
 for arm,letter in [('within','B'),('cross','C')]:
  v,_=corner_compare(teams[r.A_team_key],teams[getattr(r,letter+'_team_key')]);rows.append(dict(event_id=r.event_id,arm=arm,**v))
x=pd.DataFrame(rows).merge(old,on=['event_id','arm'],suffixes=('_new','_old'),validate='one_to_one')
metrics=['bev_mean_h','bev_max_h','top_mean_h','top_max_h','angle_deg']
out=dict(pairs=len(x),status_agreement=int((x.status_new==x.status_old).sum()),max_abs_difference={m:float((x[m+'_new']-x[m+'_old']).abs().max()) for m in metrics})
assert out['pairs']==out['status_agreement']==902
assert max(out['max_abs_difference'].values())<1e-10
a.out.write_text(json.dumps(out,indent=2));print(json.dumps(out))
