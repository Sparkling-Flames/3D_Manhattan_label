from pathlib import Path
import argparse,json,hashlib
import pandas as pd
import numpy as np
ap=argparse.ArgumentParser();ap.add_argument('source_root',type=Path);ap.add_argument('--output',type=Path);args=ap.parse_args();p=args.source_root/'assessment'
files=['CALIBRATION_TRAINING_RECEIPT.json','COMMON_EVENT_ANALYSIS_INPUT.csv.gz','LAST_SEAT_CHOICES.csv.gz']
result={'input_sha256':{x:hashlib.sha256((p/x).read_bytes()).hexdigest() for x in files},'seed':20261019,'bootstrap_replicates':2000,'scope':'Frozen-input diagnostics; not fusion replay or model refit'}
a=json.load(open(p/files[0]));cal={}
for m in ['reverse_selected','reverse_selected_swap','forward_selected','old_QT']:
 rows=[]
 for f in a:
  if f['method_id']!=m:continue
  rates={tuple(k):v for k,v,s in f['rates']}
  for k,d,r in rates:
   if r=='within' and (k,d,'between') in rates:rows.append({'heldout_building':f['heldout_building'],'k':k,'difficulty':d,'within_minus_between':rates[k,d,'within']-rates[k,d,'between']})
 cal[m]={'cells':len(rows),'negative_cells':sum(x['within_minus_between']<0 for x in rows),'rows':rows}
result['calibration_direction']=cal
cols=['event_id','panel_id','k','building','image_id','B8L2_a','B8L2_b','source_entrant_time_a','source_entrant_time_b','complete_a','complete_b']
e=pd.read_csv(p/files[1],usecols=cols);c=pd.read_csv(p/files[2],usecols=['event_id','choose_a_probability__QT','choose_a_probability__Q']);assert e.event_id.equals(c.event_id)
d=c.choose_a_probability__QT-c.choose_a_probability__Q
f=e[e.panel_id.eq('A_nested_even_v1')&e.k.eq(16)].copy();f['dq']=d*(e.B8L2_a-e.B8L2_b);f['dt']=d*(e.source_entrant_time_a-e.source_entrant_time_b)
f['dc']=d*(e.complete_a.astype(float)-e.complete_b.astype(float));f['changed']=d.ne(0)&d.notna()
def summary(z,col):
 g=z.dropna(subset=[col]);b=g.groupby(['building','image_id'])[col].mean().groupby('building').mean().to_numpy();rng=np.random.default_rng(20261019);boot=rng.choice(b,(2000,len(b)),replace=True).mean(axis=1)
 return {'events':len(g),'buildings':len(b),'building_mean':float(b.mean()),'building_ci':np.quantile(boot,[.025,.975]).tolist(),'event_p05':float(g[col].quantile(.05)),'event_min':float(g[col].min())}
z=f[f.changed]
result['QT_vs_Q_new_k16']={'events':len(f),'supported_decisions':int(d.loc[f.index].notna().sum()),'changed_choices':len(z),'changed_Q_known':int(z.dq.notna().sum()),'changed_Q_losses_gt2':int(z.dq.lt(-2).sum()),'changed_Q_gains_gt2':int(z.dq.gt(2).sum()),'changed_completeness_losses':int(z.dc.lt(0).sum()),'changed_completeness_gains':int(z.dc.gt(0).sum()),'all':{v:summary(f,v)for v in ['dq','dt','dc']},'joint_known':{v:summary(f.dropna(subset=['dq','dt']),v)for v in ['dq','dt']},'joint_known_changed':{v:summary(f.dropna(subset=['dq','dt']).loc[lambda x:x.changed],v)for v in ['dq','dt']},'largest_three_Q_losses':z.nsmallest(3,'dq')[['event_id','image_id','dq','dt']].to_dict('records')}
result['script_sha256']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
s=json.dumps(result,indent=2,ensure_ascii=False,allow_nan=False)+'\n'
if args.output:args.output.write_text(s)
else: print(s)
