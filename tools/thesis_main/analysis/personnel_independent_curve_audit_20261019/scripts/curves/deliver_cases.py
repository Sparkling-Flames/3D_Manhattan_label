from pathlib import Path
import pandas as pd,numpy as np,json,gzip,math
P=Path(__file__).parent
D=json.load(open(P/'DESIGN.json'));E={e['experiment_id']:e for e in D['experiments']};C=pd.read_csv(P/'comparisons.csv.gz');CV=pd.read_csv(P/'curves.csv')
def clean(x):
 if isinstance(x,dict):return {str(k):clean(v) for k,v in x.items()}
 if isinstance(x,(tuple,list)):return [clean(v) for v in x]
 if isinstance(x,np.generic):return clean(x.item())
 if isinstance(x,float) and not math.isfinite(x):return None
 return x
cache={}
def pool(pid):
 if pid not in cache:
  with gzip.open(P/'pools'/pid/'request_results.json.gz','rt') as f:rs={r['request_id']:r for r in json.load(f)['results']}
  with gzip.open(P/'pools'/pid/'states.json.gz','rt') as f:ss={r['team_id']:r['automatic'] for r in json.load(f)['states']}
  cache[pid]=(rs,ss)
 return cache[pid]
caseout=[]
for method,g in CV.groupby('method'):
 for arm,ascending,title in [('same_or_near',False,'Largest whole-curve quality change among score-complete same/near swaps'),('cross_or_far',True,'Smallest whole-curve quality change among score-complete cross/far swaps')]:
  choices=g[g.arm.eq(arm)&g.all_q].sort_values(['max_abs_Q','experiment_id'],ascending=[ascending,True]);row=choices.iloc[0];e=E[row.experiment_id];rs,ss=pool(e['pool_id']);comparisons=C[C.experiment_id.eq(row.experiment_id)].to_dict('records');teams=[]
  for k,arms in e['requests'].items():
   for a,rid in arms.items():
    r=rs[rid];teams.append(dict(k=int(k),arm=a,request_id=rid,team_id=r['team_id'],Q=r['B8L2'],nodes=r['nodes'],complete=r['complete_evaluable'],members=r['member_workers'].split('|'),state=ss[r['team_id']]))
  caseout.append(dict(case_title=title,selection_denominator=len(choices),selected_arm=arm,experiment=e,curve_summary=row.to_dict(),comparisons=comparisons,teams=teams))
with gzip.open(P/'CURVE_CASES.json.gz','wt') as f:json.dump(clean(caseout),f,ensure_ascii=False)
# Every component is assessed independently; counts overlap, so do not sum.
C['fail_complete']=~C.both_complete
C['fail_Q_missing']=~C.quality_comparable
C['fail_Q_tolerance']=C.B8L2_change.abs().gt(2)&C.quality_comparable
C['fail_floor']=C.floor_jaccard_difference.isna()|C.floor_jaccard_difference.gt(.05)
C['fail_nodes']=C.node_count_difference.isna()|C.node_count_difference.ne(0)
C['fail_structure']=C.structure_bound_cyclic_deg.isna()|C.structure_bound_cyclic_deg.gt(3)
cols=[c for c in C if c.startswith('fail_')];breakdown=[]
for (m,a),g in C.groupby(['method','arm']):
 chain=g.groupby('experiment_id')[cols].max()
 for name in cols:
  breakdown.append(dict(method=m,arm=a,component=name,step_failures=int(g[name].sum()),steps=len(g),chain_failures=int(chain[name].sum()),chains=len(chain)))
pd.DataFrame(breakdown).to_csv(P/'FAILURE_COMPONENTS.csv',index=False)
# Post-design, outcome-independent mechanical feature definition; no fitting.
mechanism=[]
for r in C.to_dict('records'):
 rs,ss=pool(r['pool_id']);base=rs[r['request_a']];state=ss[base['team_id']];groups=state['identity_groups'] if state is not None else [];n=base['k'];margins=[abs(g['support']-n/2) for g in groups]
 mechanism.append(dict(experiment_id=r['experiment_id'],method=r['method'],arm=r['arm'],building=r['building'],pool_id=r['pool_id'],k=n,joint_stable=r['joint_stable_main'],abs_delta_Q=abs(r['B8L2_change']) if r['quality_comparable'] else None,base_vote_boundary_available=bool(groups),base_min_vote_distance=min(margins) if margins else None,base_groups_exact_half=sum(m==0 for m in margins),base_groups_within_one_vote=sum(m<=1 for m in margins),base_near_boundary=any(m<=1 for m in margins)))
M=pd.DataFrame(mechanism);M.to_csv(P/'VOTE_BOUNDARY_DIAGNOSTIC.csv',index=False)
agg=[]
for (method,arm,k,near),g in M[M.base_vote_boundary_available].groupby(['method','arm','k','base_near_boundary']):
 im=g.groupby(['building','pool_id'])[['joint_stable','abs_delta_Q']].mean();b=im.groupby('building').mean();agg.append(dict(method=method,arm=arm,k=k,base_within_one_vote=near,steps=len(g),buildings=len(b),stability=b.joint_stable.mean(),mean_abs_delta_Q=b.abs_delta_Q.mean()))
pd.DataFrame(agg).to_csv(P/'VOTE_BOUNDARY_SUMMARY.csv',index=False)
manifest=[]
for c in caseout:
 e=c['experiment'];manifest.append(dict(method=e['method'],case=c['case_title'],experiment_id=e['experiment_id'],pool_id=e['pool_id'],building=e['building'],difficulty=e['difficulty'],selected_arm=c['selected_arm'],a=e['a'],b=e['b'],c=e['c'],max_abs_Q=c['curve_summary']['max_abs_Q'],curve_stable=c['curve_summary']['curve_stable'],selection_denominator=c['selection_denominator']))
pd.DataFrame(manifest).to_csv(P/'CASE_MANIFEST.csv',index=False)
print(pd.DataFrame(manifest).to_string(index=False));print('case gzip bytes', (P/'CURVE_CASES.json.gz').stat().st_size)
