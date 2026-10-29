"""Exact prefix marginals on completed full subset inventories, no new fusion.
Within each priority role all permutations are equiprobable. The n-prefix
therefore contains all earlier roles and a uniform subset of the frontier role.
Natural and priority policies have the same final pool; this is not a sampled
32-path experiment, and no cross-n trajectory covariance is inferred.
"""
from pathlib import Path
import argparse,gzip,json,hashlib,os
from math import comb
import numpy as np,pandas as pd
from aggregate_frozen_panels import METRICS,truth

def save(p,d):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);b=d.to_csv(index=False).encode('utf-8-sig')
 if p.suffix=='.gz':b=gzip.compress(b,mtime=0)
 t=p.with_name(p.name+'.writing')
 with t.open('wb') as f:f.write(b);f.flush();os.fsync(f.fileno())
 t.replace(p)
def distribution(d,fields,time_sources):
 out=[]
 for f in fields:
  sources=time_sources if f in ['recorded_time_total_seconds','log_recorded_time'] else ['not_time']
  for source in sources:
   v=pd.to_numeric(d[f],errors='coerce')
   if source!='not_time':v=v.where(d.time_source_kinds.eq(source))
   x=v.dropna().to_numpy(float);x=x[np.isfinite(x)]
   out.append(dict(metric=f,time_source=source,possible_teams=len(d),valid_teams=len(x),missing_teams=len(d)-len(x),
    mean=float(x.mean()) if len(x) else np.nan,sd=float(x.std()) if len(x) else np.nan,
    p05=float(np.quantile(x,.05)) if len(x) else np.nan,p10=float(np.quantile(x,.10)) if len(x) else np.nan,
    median=float(np.median(x)) if len(x) else np.nan,p90=float(np.quantile(x,.9)) if len(x) else np.nan,
    minimum=float(x.min()) if len(x) else np.nan,maximum=float(x.max()) if len(x) else np.nan,
    member_variation_estimable=len(x)>1))
 return out

def main():
 p=argparse.ArgumentParser();p.add_argument('--design',type=Path,required=True);p.add_argument('--endpoints',type=Path,required=True)
 p.add_argument('--labels',type=Path,required=True);p.add_argument('--roles',type=Path,required=True);p.add_argument('--condition',choices=['manual','semi'],required=True)
 p.add_argument('--methods',required=True);p.add_argument('--target-conditions',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
 p.add_argument('--policies',default='more_turn_first,higher_Q_first,fast_first');a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
 methods=a.methods.split(',');policies=a.policies.split(',');plan=pd.read_csv(a.design/'POOL_CAPACITY_PLAN.csv');plan=plan[plan.condition.eq(a.condition)&truth(plan.all_n_ge3_member_sets_enumerated)].copy()
 req=pd.read_csv(a.design/'TEAM_REQUESTS.csv.gz');end=pd.read_csv(a.endpoints,low_memory=False);end=end.merge(req[['team_key','member_workers']],on='team_key',how='left',validate='one_to_one',suffixes=('','_request'))
 if 'member_workers_request' in end:end['member_workers']=end.member_workers.fillna(end.member_workers_request)
 end['failure']=(~truth(end.complete_evaluable)).astype(float)
 if 'recorded_time_total_seconds' in end:
  t=pd.to_numeric(end.recorded_time_total_seconds,errors='coerce');end['log_recorded_time']=np.log(t.where(t>0))
 time_sources=sorted(end.loc[end.recorded_time_total_seconds.notna(),'time_source_kinds'].dropna().unique())
 fields=[f for f in METRICS if f in end];l=pd.read_csv(a.labels,low_memory=False);l=l[l.method.isin(methods)&l.heldout_building.ne('ALL')];l=l[truth(l.known)]
 assert set(methods)<=set(l.method)
 labels={(m,b):dict(zip(g.worker_id,g.class_id)) for (m,b),g in l.groupby(['method','heldout_building'])}
 roles=pd.read_csv(a.roles,low_memory=False);targets=pd.read_csv(a.target_conditions).set_index('pool_id')
 if a.condition=='manual':axis={'more_turn_first':('m_challenge_turn_n',False),'higher_Q_first':('m_all_B8L2',False),'fast_first':('m_all_log_time',True)}
 else:axis={'more_turn_first':('complex_turn_history',False),'higher_Q_first':('q_history',False),'fast_first':('t_history',True)}
 rows=[];links=[];orders=[]
 for pool in plan.itertuples():
  ws=pool.panel_workers.split('|');N=int(pool.pool_n);assert len(ws)==N
  e=end[end.pool_id.eq(pool.pool_id)].copy(); e['member_set']=e.member_workers.map(lambda x:frozenset(x.split('|')))
  assert len(e)==sum(comb(N,n) for n in range(3,N+1))
  meta=dict(pool_id=pool.pool_id,image=pool.image,building=pool.building,condition=a.condition,pool_n=N,reference_id=pool.reference_id,
   official_difficulty=targets.at[pool.pool_id,'official_difficulty'],geometric_challenge=targets.at[pool.pool_id,'geometric_challenge'],scope=targets.at[pool.pool_id,'scope'])
  for n in range(3,N+1):
   d=e[e.k.eq(n)];assert len(d)==comb(N,n)
   for r in distribution(d,fields,time_sources):rows.append(dict(meta,method='__natural__',policy='natural',n=n,**r))
   links += [dict(pool_id=pool.pool_id,method='__natural__',policy='natural',n=n,team_key=k,probability=1/len(d)) for k in d.team_key]
  for method in methods:
   lm=labels.get((method,pool.building),{});rr=roles[roles.method.eq(method)&roles.heldout_building.eq(pool.building)].set_index('class_id')
   for policy in policies:
    feature,ascending=axis[policy];assert feature in rr,feature
    values={w:rr.at[lm[w],feature] if w in lm and lm[w] in rr.index else np.nan for w in ws}
    levels=sorted({float(v) for v in values.values() if pd.notna(v)},reverse=not ascending)
    groups=[sorted(w for w,v in values.items() if pd.notna(v) and float(v)==x) for x in levels]
    unknown=sorted(w for w,v in values.items() if pd.isna(v))
    if unknown:groups.append(unknown)
    for i,g in enumerate(groups):orders.append(dict(meta,method=method,policy=policy,priority_level=i,workers='|'.join(g),priority_feature=feature,
      unknown_history_group=(g==unknown and bool(unknown)),class_labels='|'.join(sorted({str(lm.get(w,'unknown')) for w in g}))))
    for n in range(3,N+1):
     before=set();frontier=[];take=0
     for g in groups:
      if len(before)+len(g)>=n:frontier=g;take=n-len(before);break
      before.update(g)
     allowed=before|set(frontier);d=e[e.k.eq(n)];d=d[d.member_set.map(lambda s:before<=s and s<=allowed)]
     expected=comb(len(frontier),take);assert len(d)==expected,(pool.pool_id,method,policy,n,len(d),expected)
     for r in distribution(d,fields,time_sources):rows.append(dict(meta,method=method,policy=policy,n=n,**r))
     links += [dict(pool_id=pool.pool_id,method=method,policy=policy,n=n,team_key=k,probability=1/len(d)) for k in d.team_key]
 stats=pd.DataFrame(rows);save(a.out/'POLICY_PREFIX_DISTRIBUTIONS.csv.gz',stats);save(a.out/'POLICY_PREFIX_ENDPOINT_LINKS.csv.gz',pd.DataFrame(links));save(a.out/'HISTORICAL_ROLE_PRIORITY_GROUPS.csv.gz',pd.DataFrame(orders))
 natural=stats[stats.policy.eq('natural')];changed=stats[stats.policy.ne('natural')];keys=['pool_id','n','metric','time_source'];base=natural[keys+['mean','sd','p05','p10','median','valid_teams','possible_teams']]
 paired=changed.merge(base,on=keys,suffixes=('','_natural'),validate='many_to_one')
 for f in ['mean','sd','p05','p10','median']:paired[f+'_minus_natural']=paired[f]-paired[f+'_natural']
 full=paired[paired.n.eq(paired.pool_n)];assert full.mean_minus_natural.dropna().abs().max()<1e-10
 save(a.out/'PAIRED_SAME_POOL_PREFIX_DIFFERENCES.csv.gz',paired)
 early=paired[paired.n.lt(paired.pool_n)]
 group=['method','policy','condition','pool_id','image','building','metric','time_source'];pool=early.groupby(group,dropna=False)[['mean_minus_natural','sd_minus_natural','p10_minus_natural']].mean().reset_index();save(a.out/'PRE_FULL_POOL_AVERAGE_DIFFERENCES.csv',pool)
 image=pool.groupby(['method','policy','condition','image','building','metric','time_source'],dropna=False)[['mean_minus_natural','sd_minus_natural','p10_minus_natural']].mean().reset_index()
 building=image.groupby(['method','policy','condition','building','metric','time_source'],dropna=False)[['mean_minus_natural','sd_minus_natural','p10_minus_natural']].mean().reset_index();summary=[]
 for (m,policy,c,metric,source),g in image.groupby(['method','policy','condition','metric','time_source'],dropna=False):
  b=building[building.method.eq(m)&building.policy.eq(policy)&building.condition.eq(c)&building.metric.eq(metric)&building.time_source.eq(source)]
  summary.append(dict(method=m,policy=policy,condition=c,metric=metric,time_source=source,images=g.mean_minus_natural.notna().sum(),buildings=b.mean_minus_natural.notna().sum(),
    mean_image=g.mean_minus_natural.mean(),mean_building=b.mean_minus_natural.mean(),positive_images=int(g.mean_minus_natural.gt(0).sum()),positive_buildings=int(b.mean_minus_natural.gt(0).sum()),
    mean_sd_difference=g.sd_minus_natural.mean(),mean_low_tail_difference=g.p10_minus_natural.mean()))
 save(a.out/'POLICY_SUMMARY.csv',pd.DataFrame(summary))
 receipt=dict(condition=a.condition,methods=methods,policies=policies,pools=len(plan),early_curve_pools=int(plan.pool_n.gt(3).sum()),n_min=3,n_max=int(plan.pool_n.max()),
  used_unique_endpoints=int(end[end.pool_id.isin(plan.pool_id)].team_key.nunique()),new_fusions=0,full_endpoint_equality=True,
  natural_definition='exact uniform n-subset marginal of all without-replacement permutations',priority_definition='all earlier groups + uniform subset of frontier group; unlabelled histories retained as explicitly unknown last group',
  not_the_old_32_path_experiment=True,does_not_estimate_cross_n_path_covariance=True,
  time_sources_separate=time_sources,sd_definition='exact finite policy distribution SD; deterministic singleton=0; member_variation_estimable separately false',
  labels_sha256=hashlib.sha256(a.labels.read_bytes()).hexdigest(),roles_sha256=hashlib.sha256(a.roles.read_bytes()).hexdigest())
 (a.out/'COMPLETE.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2));print(json.dumps(receipt,ensure_ascii=False),flush=True)
if __name__=='__main__':main()
