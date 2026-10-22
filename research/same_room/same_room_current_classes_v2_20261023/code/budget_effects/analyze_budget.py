"""Observed nested-background additions across registered same-room panels.

Replicate=0 only. Keep selected candidate identities fixed across low/mid/
mid+1/high clipped budgets, and add the actual deterministic core prefix.
No fusion, scoring, target-dependent selection, or interpolation of failures.
"""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from local_study_paths import WORK,CODE_ROOT,NATIVE,TAXONOMY,MECHANISMS,BUDGET,BUDGET_CASES,BUDGET_FINAL,FIGURES,ENGINE,REPO

from pathlib import Path
import os,sys,json,gzip,hashlib,math,argparse
os.environ.setdefault('OPENBLAS_NUM_THREADS','1')
import numpy as np,pandas as pd

P=BUDGET;W=WORK
from aggregation import hierarchy,write_csv

ROLES=['low_third','mid_half','mid_plus_one','high_two_thirds']
TRANSITIONS=[('low_third','mid_half'),('mid_half','mid_plus_one'),('mid_plus_one','high_two_thirds'),('low_third','high_two_thirds')]
METRICS=['B8L2','D10','nodes','fusion_turn_n','fusion_short_turn_edges','fusion_redundancy_n',
 'S_bottom_deg','dir','Hmean','iou_2d','ref_node_recall_5','ref_edge_recall_5',
 'recorded_time_total_seconds','complete_evaluable','score_status','geometry_status','time_source_kinds','minimum_support']
CONTINUOUS=['B8L2','D10','nodes','fusion_turn_n','fusion_short_turn_edges','fusion_redundancy_n',
 'S_bottom_deg','dir','Hmean','iou_2d','ref_node_recall_5','ref_edge_recall_5']

def clean(v):
 if isinstance(v,dict):return {str(k):clean(x) for k,x in v.items()}
 if isinstance(v,list):return [clean(x) for x in v]
 if isinstance(v,(np.integer,np.bool_)):return v.item()
 if isinstance(v,(np.floating,float)) and not math.isfinite(float(v)):return None
 return v

def roles_for(p):
 n=int(p.known_common_n);k=int(p.k_selected)
 clip=lambda x:max(3,k,min(n-k,x))
 return dict(zip(ROLES,[clip(math.ceil(n/3)),clip(n//2),clip(n//2+1),clip(math.ceil(2*n/3))]))

def design():
 p=pd.read_csv(W/'design/PANELS.csv');p=p[p.ordinary_comparable.astype(bool)&p.replicate.eq(0)].copy()
 l=pd.read_csv(W/'design/PANEL_TEAM_LINKS.csv.gz');l=l[l.panel_id.isin(p.panel_id)]
 key=['pair_key','method','selected_family','class_lo','class_hi','candidates','k_selected']
 rows=[]
 for values,g in p.groupby(key,dropna=False,sort=False):
  first=g.iloc[0];by=g.set_index('n');expected=roles_for(first)
  assert not by.index.duplicated().any()
  series='SRB_'+hashlib.sha256(json.dumps([str(v) for v in values],ensure_ascii=False).encode()).hexdigest()[:20]
  for role,n in expected.items():
   r=by.loc[n].to_dict();r['n']=n;r.update(series_id=series,budget=role,role_aliases='|'.join(k for k,v in expected.items() if v==n))
   rows.append(r)
 roles=pd.DataFrame(rows)
 return p,l,roles

def load_endpoints(roles,links):
 needed=set(links.team_key_a)|set(links.team_key_b); rows=[]
 scalar=NATIVE/'ENDPOINT_SCALARS.csv.gz'
 if scalar.exists():
  header=pd.read_csv(scalar,nrows=0).columns
  cols=[c for c in ['team_key','image','pool_id','reference_id','member_workers','recorded_time_eligible']+METRICS if c in header]
  d=pd.read_csv(scalar,usecols=cols,low_memory=False);d=d[d.team_key.isin(needed)].copy()
  return d,dict(source=str(scalar.relative_to(W)),pool_files=None,available=len(d),needed=len(needed))
 pools=sorted(set(roles.pool_id_a)|set(roles.pool_id_b))
 for pid in pools:
  f=NATIVE/'pools'/(pid+'.json.gz')
  if not f.exists():continue
  obj=json.load(gzip.open(f,'rt'))
  for r in obj['teams']:
   if r['team_key'] in needed:rows.append({k:r.get(k) for k in ['team_key','image','pool_id','reference_id','recorded_time_eligible']+METRICS})
 d=pd.DataFrame(rows)
 return d,dict(source='native/pools/*.json.gz',pool_files=len(pools),available=len(d),needed=len(needed))

def stat(g,metric):
 v=pd.to_numeric(g[metric],errors='coerce');f=v[np.isfinite(v)]
 return (float(f.mean()) if len(f) else np.nan,len(f))

def endpoint_panels(roles,links,end):
 e=end.set_index('team_key');summaries=[];support=[];saved_keys=set(e.index)
 bypanel={pid:g for pid,g in links.groupby('panel_id')}
 for r in roles.to_dict('records'):
  l=bypanel[r['panel_id']];good=set(l.team_key_a)|set(l.team_key_b)
  present=good<=saved_keys
  support.append(dict(series_id=r['series_id'],panel_id=r['panel_id'],budget=r['budget'],n=r['n'],
      pair_key=r['pair_key'],n_requested_teams=len(good),n_saved_teams=len(good&saved_keys),panel_available=present))
  if not present:continue
  s={k:r[k] for k in ['series_id','panel_id','pair_key','building','groups','budget','n','class_lo','class_hi','difficulty_a','difficulty_b']}
  z=pd.concat([e.loc[l.team_key_a],e.loc[l.team_key_b]],ignore_index=True)
  q=pd.to_numeric(z.B8L2,errors='coerce');valid=q.notna()
  s.update(n_finite_teams=len(l),n_view_endpoints=len(z),quality_known_n=int(valid.sum()),
    quality_available_rate=float(valid.mean()),failure_rate=float((~z.complete_evaluable.fillna(False).astype(bool)).mean()),
    quality_unavailable_rate=float((~valid).mean()),Q_lt80=float(q[valid].lt(80).mean()) if valid.any() else np.nan,
    Q_lt70=float(q[valid].lt(70).mean()) if valid.any() else np.nan,
    recorded_time_known_rate=float(z.recorded_time_total_seconds.notna().mean()))
  for m in CONTINUOUS:s[m+'_mean'],s[m+'_known_n']=stat(z,m)
  s['recorded_time_seconds_mean'],s['recorded_time_known_n']=stat(z,'recorded_time_total_seconds')
  summaries.append(s)
 return pd.DataFrame(summaries),pd.DataFrame(support)

def add_links(roles,links,end):
 byrole={(r.series_id,r.budget):r for r in roles.itertuples(index=False)}
 bypanel={pid:g.set_index('selected_mask') for pid,g in links.groupby('panel_id')}
 e=end.set_index('team_key').to_dict('index');rows=[];notready=[]
 for series in roles.series_id.unique():
  for fr,to in TRANSITIONS:
   x,y=byrole[(series,fr)],byrole[(series,to)];xx,yx=bypanel[x.panel_id],bypanel[y.panel_id]
   assert x.candidates==y.candidates and set(xx.index)==set(yx.index)
   core0=set(str(x.core).split('|')) if isinstance(x.core,str) else set()
   core1=set(str(y.core).split('|')) if isinstance(y.core,str) else set()
   assert core0<=core1,(series,fr,to)
   for mask,l0 in xx.iterrows():
    l1=yx.loc[mask];assert l0.selected==l1.selected
    keys=[l0.team_key_a,l1.team_key_a,l0.team_key_b,l1.team_key_b]
    base=dict(series_id=series,pair_key=x.pair_key,building=x.building,groups=x.groups,
      panel_before=x.panel_id,panel_after=y.panel_id,transition=fr+'__'+to,budget_before=fr,budget_after=to,
      selected_mask=mask,selected_members=l0.selected,n_before=x.n,n_after=y.n,added_n=y.n-x.n,
      added_members='|'.join(sorted(core1-core0)),core_before=x.core,core_after=y.core,
      team_before_a=keys[0],team_after_a=keys[1],team_before_b=keys[2],team_after_b=keys[3],
      members_before=l0.member_set_key,members_after=l1.member_set_key,
      class_vector_before=l0.structure_vector,class_vector_after=l1.structure_vector,
      image_a=x.image_a,image_b=x.image_b,pool_id_a=x.pool_id_a,pool_id_b=x.pool_id_b,
      reference_id_a=x.reference_id_a,reference_id_b=x.reference_id_b,
      difficulty_a=x.difficulty_a,difficulty_b=x.difficulty_b,
      class_lo=x.class_lo,class_hi=x.class_hi,known_common_n=x.known_common_n,
      parity_step='even_to_odd' if y.n-x.n==1 and x.n%2==0 else 'odd_to_even' if y.n-x.n==1 else 'multiple_added' if y.n>x.n else 'clipped_same_n')
    if not all(k in e for k in keys):notready.append(base|dict(saved_endpoints=sum(k in e for k in keys)));continue
    for side,k0,k1 in [('a',keys[0],keys[1]),('b',keys[2],keys[3])]:
     a,b=e[k0],e[k1]
     for m in METRICS:
      base[f'{m}_before_{side}']=a.get(m);base[f'{m}_after_{side}']=b.get(m)
     for m in CONTINUOUS:
      a0,b0=a.get(m),b.get(m)
      base[f'delta_{m}_{side}']=float(b0)-float(a0) if pd.notna(a0) and pd.notna(b0) else None
     oldtime,newtime=a.get('recorded_time_total_seconds'),b.get('recorded_time_total_seconds')
     tm=pd.notna(oldtime) and pd.notna(newtime) and oldtime>0 and a.get('time_source_kinds')==b.get('time_source_kinds')
     base[f'labor_ratio_{side}']=newtime/oldtime if tm else None
     base[f'failure_before_{side}']=not bool(a.get('complete_evaluable'))
     base[f'failure_after_{side}']=not bool(b.get('complete_evaluable'))
     base[f'minimum_support_delta_{side}']=b['minimum_support']-a['minimum_support']
    qa,qb=base['delta_B8L2_a'],base['delta_B8L2_b']
    if qa is None or qb is None:state='quality_unavailable'
    else:
     sa=0 if abs(qa)<=1 else (1 if qa>0 else -1);sb=0 if abs(qb)<=1 else (1 if qb>0 else -1)
     state='both_small' if sa==sb==0 else 'both_up' if sa==sb==1 else 'both_down' if sa==sb==-1 else 'opposite' if sa*sb==-1 else 'one_changes'
    base['crossview_Q_state_t1']=state
    ta,tb=base['delta_fusion_turn_n_a'],base['delta_fusion_turn_n_b']
    base['crossview_turn_state']='unavailable' if ta is None or tb is None else 'both_zero' if ta==tb==0 else 'same_nonzero_sign' if ta*tb>0 else 'opposite' if ta*tb<0 else 'one_changes'
    rows.append(base)
 return pd.DataFrame(rows),pd.DataFrame(notready)

def transition_panels(add):
 rows=[]
 for keys,g in add.groupby(['series_id','transition'],sort=False):
  first=g.iloc[0];base={k:first[k] for k in ['series_id','pair_key','building','groups','transition','n_before','n_after','added_n','parity_step','class_lo','class_hi','difficulty_a','difficulty_b']}
  base['n_team_additions']=len(g)
  qa=np.r_[g.delta_B8L2_a.to_numpy(),g.delta_B8L2_b.to_numpy()].astype(float);valid=np.isfinite(qa)
  base.update(Q_delta_mean=float(qa[valid].mean()) if valid.any() else np.nan,
    Q_known_rate=float(valid.mean()),Q_loss_gt5=float((qa[valid]<-5).mean()) if valid.any() else np.nan,
    Q_gain_gt5=float((qa[valid]>5).mean()) if valid.any() else np.nan,
    Q_change_small_t1=float((np.abs(qa[valid])<=1).mean()) if valid.any() else np.nan,
    Q_change_negative=float((qa[valid]<0).mean()) if valid.any() else np.nan)
  for m in ['D10','nodes','fusion_turn_n','fusion_short_turn_edges','fusion_redundancy_n','S_bottom_deg','dir','Hmean','iou_2d','ref_node_recall_5','ref_edge_recall_5']:
   v=np.r_[g['delta_'+m+'_a'],g['delta_'+m+'_b']].astype(float);v=v[np.isfinite(v)]
   base[m+'_delta_mean']=v.mean() if len(v) else np.nan
   if m in ['nodes','fusion_turn_n']:
    for name,cond in [('increase',v>0),('decrease',v<0),('unchanged',v==0)]:base[m+'_'+name]=cond.mean() if len(v) else np.nan
  for phase in ['before','after']:
   q=np.r_[pd.to_numeric(g['B8L2_'+phase+'_a'],errors='coerce'),pd.to_numeric(g['B8L2_'+phase+'_b'],errors='coerce')];good=np.isfinite(q)
   for threshold in [70,80]:base[f'Q_lt{threshold}_{phase}']=float((q[good]<threshold).mean()) if good.any() else np.nan
   f=np.r_[g['failure_'+phase+'_a'].astype(float),g['failure_'+phase+'_b'].astype(float)]
   base['failure_'+phase]=f.mean()
  q0=np.r_[pd.to_numeric(g.B8L2_before_a,errors='coerce'),pd.to_numeric(g.B8L2_before_b,errors='coerce')]
  q1=np.r_[pd.to_numeric(g.B8L2_after_a,errors='coerce'),pd.to_numeric(g.B8L2_after_b,errors='coerce')]
  joint=np.isfinite(q0)&np.isfinite(q1)
  for threshold in [70,80]:
   base[f'Q_lt{threshold}_joint_before']=float((q0[joint]<threshold).mean()) if joint.any() else np.nan
   base[f'Q_lt{threshold}_joint_after']=float((q1[joint]<threshold).mean()) if joint.any() else np.nan
  f0=np.r_[g.failure_before_a.astype(float),g.failure_before_b.astype(float)];f1=np.r_[g.failure_after_a.astype(float),g.failure_after_b.astype(float)]
  base['new_failure_rate']=((f0==0)&(f1==1)).mean();base['recovered_from_failure_rate']=((f0==1)&(f1==0)).mean()
  for name in ['both_small','both_up','both_down','opposite','one_changes','quality_unavailable']:
   base['crossview_Q_'+name]=g.crossview_Q_state_t1.eq(name).mean()
  for name in ['both_zero','same_nonzero_sign','opposite','one_changes','unavailable']:
   base['crossview_turn_'+name]=g.crossview_turn_state.eq(name).mean()
  times=np.r_[pd.to_numeric(g.labor_ratio_a,errors='coerce'),pd.to_numeric(g.labor_ratio_b,errors='coerce')];good=np.isfinite(times)
  base['labor_ratio_mean']=times[good].mean() if good.any() else np.nan;base['labor_ratio_known_rate']=good.mean()
  rows.append(base)
 return pd.DataFrame(rows)

def save_hierarchy(out,prefix,df,keys,metrics):
 pair,group,building,summary=hierarchy(df,keys,metrics)
 for suffix,d in [('PAIR',pair),('GROUP',group),('BUILDING',building),('SUMMARY',summary)]:write_csv(out/(prefix+'_'+suffix+'.csv'),d)
 return summary

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--require-complete',action='store_true');ap.add_argument('--out',type=Path,default=P/'partial');a=ap.parse_args();a.out.mkdir(parents=True,exist_ok=True)
 panels,links,roles=design();print('design loaded',len(panels),len(links),flush=True)
 end,load_receipt=load_endpoints(roles,links);print('endpoints loaded',load_receipt,flush=True)
 assert not end.team_key.duplicated().any()
 complete=load_receipt['available']==load_receipt['needed']
 if a.require_complete and not complete:raise RuntimeError('Required endpoints still computing: '+str(load_receipt))
 ep,availability=endpoint_panels(roles,links,end);print('budget panels',len(ep),flush=True)
 adds,pending=add_links(roles,links,end);print('addition links',len(adds),'pending',len(pending),flush=True)
 # Main addition summaries exclude role aliases that add no actual person.
 valid_adds=adds[adds.added_n>0].copy();tp=transition_panels(valid_adds)
 write_csv(a.out/'BUDGET_PANEL_ROLES.csv',roles.drop(columns=['lo_members_in_common','hi_members_in_common']))
 write_csv(a.out/'ENDPOINT_AVAILABILITY.csv',availability)
 write_csv(a.out/'BUDGET_PANEL_RESULTS.csv',ep)
 write_csv(a.out/'ADDITION_LINKS.csv.gz',adds)
 write_csv(a.out/'ADDITION_PANEL_RESULTS.csv',tp)
 if len(pending):write_csv(a.out/'PENDING_ADDITIONS.csv.gz',pending)
 em=[c for c in ep if c.endswith('_mean') or c in ['n','quality_available_rate','failure_rate','quality_unavailable_rate','Q_lt80','Q_lt70','recorded_time_known_rate']]
 sm=save_hierarchy(a.out,'BUDGET',ep,['budget'],em)
 exclude={'series_id','pair_key','building','groups','transition','parity_step','class_lo','class_hi','difficulty_a','difficulty_b'}
 tm=[c for c in tp if c not in exclude]
 ts=save_hierarchy(a.out,'ADDITION',tp,['transition'],tm)
 sp=tp[tp.added_n.eq(1)&tp.transition.eq('mid_half__mid_plus_one')].copy()
 if len(sp):save_hierarchy(a.out,'SINGLE_ADDITION_PARITY',sp,['parity_step'],[c for c in tm if c not in ['n_team_additions']])
 receipt=dict(repository_commit='72a44e80c344975962e1071bd54d894dd86bb4b4',design_version='SRCC23_paired_finite_panels_v1',
   room_relation_version='same_room_user_working_classification_20261016_v2',scope='ordinary_comparable; replicate0; same candidates and selected_mask; actual nested core',
   data_complete=complete,load=load_receipt,design_panels=len(panels),series=roles.series_id.nunique(),
   requested_direct_pairs=panels.pair_key.nunique(),available_direct_pairs=ep.pair_key.nunique(),
   available_images=len(set(roles[roles.panel_id.isin(ep.panel_id)].image_a)|set(roles[roles.panel_id.isin(ep.panel_id)].image_b)),
   exact_additions=len(adds),distinct_nonzero_additions=len(valid_adds),clipped_same_n=len(adds)-len(valid_adds),pending_additions=len(pending),
   new_fusion_count=0,new_score_count=0,weighting='uniform masks within class-pair series; direct pair; adopted declared group; building equally',
   Q_tail_denominator='finite Q at respective budget; quality unavailable and incomplete separately reported',
   Q_delta_denominator='finite before+after in the same view; failed values not filled',
   time='ratio only when both recorded totals known and one identical time_source_kind; activity labor, not delivery time',
   case_selection='registered hash design without target scores; additions change actual background composition together with n')
 (a.out/'BUDGET_RECEIPT.json').write_text(json.dumps(clean(receipt),ensure_ascii=False,indent=2))
 print(json.dumps(clean(receipt),ensure_ascii=False));print(sm.round(4).to_string(index=False));print(ts[['transition','Q_delta_mean','Q_loss_gt5','Q_gain_gt5','fusion_turn_n_increase','fusion_turn_n_decrease','labor_ratio_mean','direct_pairs','buildings']].round(4).to_string(index=False))

if __name__=='__main__':main()
