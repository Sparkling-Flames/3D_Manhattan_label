"""Independent table audit. No delivered code imports or native execution.
Read-only inputs; outputs confined to audit_statistics. Hierarchical reductions
and optional source-time linear recovery independently implemented here.
"""
from pathlib import Path
import pandas as pd,numpy as np,json,gzip,hashlib,math
from collections import Counter
B=Path('/workspace/shared/interchangeability_audit_20261020/unpacked/interchangeability_20261020')
O=Path(__file__).parent
used=[]
def csv(p):
 used.append(p); return pd.read_csv(B/p)
def js(p):
 used.append(p)
 with (gzip.open(B/p,'rt') if p.endswith('.gz') else open(B/p)) as f:return json.load(f)
def hierarchy(d,cols,image='image'):
 return d.groupby(['building',image],dropna=False)[cols].mean().groupby('building').mean()
def result(d,cols,image='image'):
 z=hierarchy(d,cols,image)
 return dict(events=len(d),images=d[image].nunique(),buildings=d.building.nunique(),means=z.mean().to_dict(),building_values=z.to_dict('index'))
req=js('core_replay/CORE_REQUESTS.json.gz'); finals=js('core_replay/EXPECTED_FINAL_FIELDS.json.gz'); pair=csv('core_replay/EXPECTED_PAIRED_EVENTS.csv.gz')
tm={t['team_key']:t for t in finals}; em={e['event_id']:e for e in req['events']}; rows=[]; errors=[]
for _,p in pair.iterrows():
 e=em[p.event_id]; arms={a:tm[e[a+'_team_key']] for a in 'ABC'}; A,C,R=[set(e[x]) for x in ['A_workers','C_workers','core_workers']]; BB=set(e['B_workers'])
 assert len(A)==len(BB)==len(C)==e['n']; assert A&BB==A&C==R;assert len(A-BB)==len(A-C)==e['m'];assert e['A_counts']==e['B_counts']
 for a,t in arms.items():
  assert set(t['member_workers'])==set(e[a+'_workers']);assert t['pool_id']==e['pool_id'];assert t['reference_id']==e['reference_id'];assert t['k']==e['n'];assert t['complete_evaluable']==p[a+'_complete']
 q=[arms[a]['B8L2'] for a in 'ABC'];delta=q[2]-q[1] if q[1] is not None and q[2] is not None else np.nan
 assert (pd.isna(delta) and pd.isna(p.net_B8L2_change)) or abs(delta-p.net_B8L2_change)<1e-10
 d=p.to_dict();d['net_B8L2_change']=delta;d['within_Q_drop_gt5']=(q[1]-q[0]<-5) if q[0] is not None and q[1] is not None else np.nan;rows.append(d)
f=pd.DataFrame(rows); cols=['net_B8L2_change','within_joint_stable_main','cross_joint_stable_main','within_geometry_shape_main','cross_geometry_shape_main','within_Q_drop_gt5','B_complete','C_complete']
res={'core':{k:result(g,cols) for k,g in f.groupby('group')},'checks':{'paired_events':len(f),'team_rows':len(finals),'exact_ABC_members_core_n_m_reference_and_delta_pass':True}}
# Time recovery: source times are sums. Solve independently from retained fully-known team totals.
known={};systems={};recover=[]
for pool,g in pd.DataFrame(finals).groupby('pool_id'):
 g=g[g.source_time_known_n.eq(g.k)&g.source_time_total_seconds.notna()];workers=sorted({w for ws in g.member_workers for w in ws})
 if not workers:continue
 ix={w:i for i,w in enumerate(workers)};M=np.zeros((len(g),len(workers)))
 for i,ws in enumerate(g.member_workers):
  for w in ws:M[i,ix[w]]=1
 y=g.source_time_total_seconds.to_numpy();x,_,rank,_=np.linalg.lstsq(M,y,rcond=None);resid=float(abs(M@x-y).max())
 assert resid<1e-6
 systems[pool]=(ix,x,np.linalg.pinv(M)@M)
 if rank==len(workers):known[pool]=dict(zip(workers,x))
 recover.append(dict(pool_id=pool,rows=len(g),workers=len(workers),rank=int(rank),max_residual=resid))
time=[]
for _,p in f[f.group.eq('F01_time')].iterrows():
 e=em[p.event_id];w=known.get(e['pool_id'],{});bs=e['within_incoming'];cs=e['cross_incoming'];r=p.to_dict()
 vals=[]
 for block in [bs,cs]:
  system=systems.get(e['pool_id'])
  if system is None or not all(v in system[0] for v in block):vals.append(np.nan);continue
  ix,x,P=system;z=np.zeros(len(ix))
  for v in block:z[ix[v]]=1
  vals.append(float(z@x) if np.max(abs(z-z@P))<1e-8 else np.nan)
 r['log_ratio']=math.log(vals[1]/vals[0]) if all(np.isfinite(vals)) and min(vals)>0 else np.nan;time.append(r)
t=pd.DataFrame(time);tr=result(t,['log_ratio']);tr['available_events']=int(t.log_ratio.notna().sum());tr['ratio']=math.exp(tr['means']['log_ratio']);res['F01_independent_source_time']=tr
t[['event_id','pool_id','building','image','log_ratio']].to_csv(O/'source_time_recovered_events.csv',index=False)
pd.DataFrame(recover).to_csv(O/'source_time_linear_recovery.csv',index=False)
# Frozen mixture assessment, from image-level evidence.
r=csv('ratio_grid/confirmation_results/all_frozen_ratio_image_results.csv.gz');r=r[r.phase.eq('assessment')];res['five_ratios']={k:result(g,['mixture_minus_best_pure_Q','mixture_complete_fraction','pure_min_complete_fraction']) for k,g in r.groupby('rule_id')}
# Census exact finite means, all 3752 rows.
c=csv('ratio_grid/local_census/results/finite_team_evidence.csv.gz');res['census']=c.groupby('composition_id').agg(teams=('team_key','size'),unique_teams=('team_key','nunique'),mean_Q=('B8L2','mean'),min_Q=('B8L2','min'),complete=('complete_evaluable','sum')).to_dict('index')
# Same crew condition links.
c=csv('condition_transfer/assessment_effects/linked_condition_effects.csv.gz');c=c[(c.n>=3)&(c.m>=2)];res['condition']={str(k):result(g,['manual_net_B8L2_change','semi_net_B8L2_change','interaction_net_B8L2_change']) for k,g in c.groupby(['method_id','direction'])}
# W132 parent-averaged paired-support result.
w=csv('reverse/assessment_interpretation/w132_probe/matched_parent_effects.csv.gz');wm=['original_matched_net_B8L2_change','replacement_matched_net_B8L2_change','original_matched_gap_geometry_shape_main','replacement_matched_gap_geometry_shape_main'];res['W132']={str(k):result(g,wm,'image_id') for k,g in w.groupby(['outgoing_class','incoming_class'])}
# Matched support curve metadata and actual unique images per n, not outcome-based filtering.
c=csv('reverse/assessment_interpretation/nested_new2/curves_aggregate.csv.gz');res['curve_support']=c[['cohort','outgoing_class','m','n','true_images','buildings']].to_dict('records')
res['inputs']=[dict(path=p,sha256=hashlib.sha256((B/p).read_bytes()).hexdigest()) for p in used]
(O/'RECOMPUTED_RESULTS.json').write_text(json.dumps(res,indent=2,default=lambda x:x.item() if isinstance(x,np.generic) else str(x)))
print(json.dumps({'core':{k:{'events':v['events'],'images':v['images'],'buildings':v['buildings'],**v['means']} for k,v in res['core'].items()},'time':tr,'ratios':{k:v['means'] for k,v in res['five_ratios'].items()},'census':res['census'],'W132':{k:v['means'] for k,v in res['W132'].items()}},indent=2))
