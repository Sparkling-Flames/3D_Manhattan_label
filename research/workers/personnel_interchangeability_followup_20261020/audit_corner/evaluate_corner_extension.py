import argparse,json,gzip,pathlib,sys
import pandas as pd
from corner_distance import corner_compare

def read(p):
 with (gzip.open(p,'rt') if str(p).endswith('.gz') else open(p)) as f:return json.load(f)
def main():
 p=argparse.ArgumentParser();p.add_argument('--bundle',type=pathlib.Path,required=True);p.add_argument('--native',type=pathlib.Path);p.add_argument('--out',type=pathlib.Path,required=True);p.add_argument('--requests',type=pathlib.Path);p.add_argument('--source',default='core_native');args=p.parse_args();args.out.mkdir(parents=True,exist_ok=True)
 root=args.bundle/'interchangeability_20261020';sys.path.insert(0,str(root/'independent'));import pair_diagnostics as pro
 items=[]
 if args.native:
  events=read(args.requests or root/'core_replay/CORE_REQUESTS.json.gz')['events'];by={}
  included=[e for e in events if all(e.get(c+'_team_key') for c in 'ABC')]
  (args.out/'EVENT_DESIGN_COVERAGE.json').write_text(json.dumps(dict(total_design_rows=len(events),paired_ABC_events=len(included),excluded_nonpaired_design_rows=len(events)-len(included),exclusion_reason='Ratio/census single-team design rows have no A/B/C paired experiment, not geometry-based exclusions'),indent=2))
  events=included
  for e in events:by.setdefault(e['pool_id'],[]).append(e)
  for pool,es in by.items():
   path=args.native/'pools'/f'{pool}.json.gz'
   if not path.exists():raise FileNotFoundError(path)
   payload=read(path);teams={t['team_key']:t for t in payload['teams']}
   items.append((args.source,es,teams))
 else:
  for f in sorted((root/'cases').glob('S*.json')):
   c=read(f);es=[c['event']]+c.get('additional_events',[]);es=[e for e in es if e and all(e.get(x+'_team_key') for x in ['A','B','C'])]
   items.append((c['case_id'],es,{t['team_key']:t for t in c['teams']}))
 rows=[];details=[]
 for source,es,teams in items:
  cache={}
  for e in es:
   meta={k:e.get(k) for k in ['event_id','pool_id','building','image','method_id','domain','context_id','phase','k','m','direction','family','replay_group']};meta['source']=source
   for arm,letter in [('within','B'),('cross','C')]:
    if e['A_team_key'] not in teams or e[letter+'_team_key'] not in teams:raise KeyError('missing team for '+str(e['event_id']))
    a,b=teams[e['A_team_key']],teams[e[letter+'_team_key']]
    if a.get('image_id') != b.get('image_id'):raise ValueError('paired true image mismatch')
    if a.get('image') != b.get('image') or (e.get('image') and e['image']!=a.get('image')):raise ValueError('event image mismatch')
    meta['image_id']=a.get('image_id')
    v,pts=corner_compare(a,b);old=pro.pair_metrics(a,b,cache=cache)
    rows.append(dict(meta,arm=arm,**v,**old));details.extend(dict(meta,arm=arm,**pt) for pt in pts)
 df=pd.DataFrame(rows)
 if (df.groupby('pool_id').image_id.nunique()>1).any():raise ValueError('pool maps to multiple true images')
 df.to_csv(args.out/'CORNER_PAIRS.csv.gz',index=False);pd.DataFrame(details).to_csv(args.out/'CORNER_POINTS.csv.gz',index=False)
 keys=['source','replay_group','event_id'];meta=['source','event_id','pool_id','building','image','method_id','domain','context_id','phase','k','m','direction','family','replay_group','image_id']
 ev=df[meta].drop_duplicates();fields=[x for x in df.columns if x not in meta+['arm']]
 for arm in ['within','cross']:
  x=df[df.arm==arm][keys+fields].rename(columns={k:arm+'_'+k for k in fields});ev=ev.merge(x,on=keys,validate='one_to_one')
 ev['both_available']=(ev.within_status=='unique_cyclic_candidate')&(ev.cross_status=='unique_cyclic_candidate');ev.to_csv(args.out/'CORNER_EVENTS.csv.gz',index=False)
 strata=['source','method_id','domain','context_id','phase','k','m','direction','replay_group'];summary=[];buildings=[]
 metrics=['bev_mean_h','bev_max_h','top_mean_h','top_max_h','bev_max_pairscale','top_max_pairscale','bev_max_local_radius_fraction','top_max_local_radius_fraction']
 for key,g in ev.groupby(strata,dropna=False):
  for gate in [None,9,12]:
   v=g[g.both_available].copy()
   if gate:v=v[(v.within_angle_deg<=gate)&(v.cross_angle_deg<=gate)].copy()
   base=dict(zip(strata,key));base.update(gate='all_common' if gate is None else f'angle_le_{gate}',attempted_events=len(g),joint_events=len(v),joint_images=v.image.nunique(),joint_buildings=v.building.nunique())
   vals=[]
   for metric in metrics:
    for arm in ['within','cross']:vals.append(arm+'_'+metric)
    v['delta_'+metric]=v['cross_'+metric]-v['within_'+metric];vals.append('delta_'+metric)
    v['cross_larger_'+metric]=(v['delta_'+metric]>1e-9).astype(float);vals.append('cross_larger_'+metric)
   b=v.groupby(['building','pool_id'])[vals].mean().groupby('building').mean()
   for col in vals:base[col]=b[col].mean()
   summary.append(base)
   for building,row in b.iterrows():buildings.append(dict(zip(strata,key),gate=base['gate'],building=building,**row.to_dict()))
 pd.DataFrame(summary).to_csv(args.out/'CORNER_SUMMARY.csv',index=False);pd.DataFrame(buildings).to_csv(args.out/'CORNER_BUILDINGS.csv',index=False)
 df.groupby(strata+['arm','status'],dropna=False).size().rename('attempts').reset_index().to_csv(args.out/'CORNER_SUPPORT.csv',index=False)
 check=dict(events=len(ev),pairs=len(df),joint_events=int(ev.both_available.sum()),reversed_pairs=int(df.ring_reversed.fillna(False).sum()),point_rows=len(details),source='native final replay' if args.native else 'embedded case final rows')
 (args.out/'CORNER_CHECKS.json').write_text(json.dumps(check,indent=2));print(json.dumps(check))
if __name__=='__main__':main()
