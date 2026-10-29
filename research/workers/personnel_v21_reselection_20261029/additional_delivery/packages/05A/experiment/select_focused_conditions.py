"""Translate selected historical semantic directions to exact fold classes.

Input conditions are chosen after the completed global comparison. This script
reads no target outcomes and never adjusts labels. It exposes all pool-level
capacity exclusions, including pools outside the original screen frame.
"""
from __future__ import annotations
import argparse,collections,itertools,json,hashlib
from pathlib import Path
from capacity_space import read_json,read_labels,capacities,exact_counts,write_csv
from register_adaptive import write_json


def number(x):return int(float(x))
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--pools',nargs='+',required=True);ap.add_argument('--labels',required=True)
 ap.add_argument('--roles',required=True);ap.add_argument('--conditions',required=True);ap.add_argument('--screen-frame',required=True);ap.add_argument('--output',required=True);ap.add_argument('--design',choices=['ABC','AC'],default='ABC');ap.add_argument('--selection-phase');ap.add_argument('--restrict-pool-list',help='CSV with pool_id; retain outside-pool exclusions, register only these actual pools')
 a=ap.parse_args();out=Path(a.output);out.mkdir(parents=True,exist_ok=True)
 pools=[p for fn in a.pools for p in read_json(fn)['images']];labels=read_labels(a.labels);roles=read_labels(a.roles);conditions=read_labels(a.conditions)
 frame=[r for r in read_labels(a.screen_frame) if str(r.get('selected','true')).lower() in ('true','1','1.0')];screenp={r['pool_id'] for r in frame};screenb={r['building'] for r in frame}
 L=collections.defaultdict(list);R=collections.defaultdict(list)
 for r in labels:L[r['method'],r['heldout_building']].append(r)
 for r in roles:R[r['method'],r['heldout_building']].append(r)
 allowed={r['pool_id'] for r in read_labels(a.restrict_pool_list)} if a.restrict_pool_list else None
 allrows=[];cells=[]
 for cfg in conditions:
  condition=cfg.get('condition') or 'manual';layer=cfg.get('layer') or ('ordinary_'+condition)
  method=cfg['method'];axis=cfg['role_axis'];n_spec=cfg['n'];m_spec=cfg['m'];m_fixed=None if m_spec=='capacity' else number(m_spec);sr,tr=number(cfg['source_rank']),number(cfg['target_rank'])
  assert not (n_spec=='capacity' and m_spec=='capacity'),'Choose a fixed n or a fixed m, not two unconstrained capacities.'
  for p in pools:
   meta=p['meta'];pid=p['pool_id'];b=meta['building'];n=len(p['records'])-((m_fixed or 0) if a.design=='AC' else 2*(m_fixed or 0)) if n_spec=='capacity' else number(n_spec)
   if meta['condition']!=condition:continue
   scope='other' if meta.get('analysis_scope')=='other_admitted_target' else 'primary'
   identity=dict(condition_id=cfg['condition_id'],pool_id=pid,image=meta['image'],building=b,condition=condition,layer=meta['layer'],scope=scope,
       method=method,n=n,m=m_fixed,requested_n_spec=n_spec,requested_m_spec=m_spec,comparison_design=a.design,role_axis=axis,source_rank=sr,target_rank=tr,pool_n=len(p['records']),
       in_global_screen_pool=pid in screenp,in_global_screen_building=b in screenb)
   if allowed is not None and pid not in allowed:
    allrows.append(dict(identity,feasible=False,reason='outside_declared_common_pool_support'));continue
   if meta['layer']!=layer or (cfg.get('scope') not in ('','all',None) and cfg['scope']!=scope):
    allrows.append(dict(identity,feasible=False,reason='condition_layer_or_scope_not_selected'));continue
   rs=R[method,b]
   if cfg.get('k'):
    rs=[r for r in rs if number(r['k'])==number(cfg['k'])]
   source=[r for r in rs if r.get(axis) not in ('','nan',None) and number(r[axis])==sr]
   target=[r for r in rs if r.get(axis) not in ('','nan',None) and number(r[axis])==tr]
   if not source or not target:
    allrows.append(dict(identity,feasible=False,reason='fold_role_or_k_not_available'));continue
   groups=capacities(p,L[method,b])
   for s,t in itertools.product(source,target):
    sc,tc=s['class_id'],t['class_id']
    if sc==tc:continue
    S,T=len(groups.get(sc,[])),len(groups.get(tc,[]));N=len(p['records']);why=[]
    m=m_fixed if m_fixed is not None else max(0,min(S if a.design=='AC' else S//2,T,(N-n) if a.design=='AC' else (N-n)//2,n))
    if m<1:why.append('no_positive_feasible_replacement_capacity')
    if n<3:why.append('n_below_3')
    if m>n:why.append('m_exceeds_n')
    if S<(m if a.design=='AC' else 2*m):why.append('source_capacity_below_m' if a.design=='AC' else 'source_capacity_below_2m')
    if T<m:why.append('target_capacity_below_m')
    if N<n+(m if a.design=='AC' else 2*m):why.append('pool_capacity_below_n_plus_m' if a.design=='AC' else 'pool_capacity_below_n_plus_2m')
    counts=exact_counts(N,S,T,n,m) if m>=1 else dict(strict_ABC=False,direct_AC=False,xyz_unordered_AB_count='0',strict_ABC_member_background_count='0',direct_AC_member_background_count='0')
    r=dict(identity,m=m,source_class=sc,target_class=tc,source_capacity=S,target_capacity=T,
       source_role_semantic=s['semantic_training_role'],target_role_semantic=t['semantic_training_role'],
       feasible=not why,reason=';'.join(why) or 'feasible',selection_phase=a.selection_phase or ('post_global_screen_direct_AC_extension' if a.design=='AC' else 'post_global_screen_member_background_extension'),
       **counts)
    allrows.append(r)
    if not why:cells.append(r)
 write_csv(out/'POOL_CONDITION_ENTRY_AND_EXIT.csv.gz',allrows);write_csv(out/'FOCUSED_CELLS.csv.gz',cells)
 by=collections.Counter(r['condition_id'] for r in cells)
 write_json(out/'CONDITIONS_FROZEN.json',dict(conditions=conditions,labels_sha256=hashlib.sha256(Path(a.labels).read_bytes()).hexdigest(),
    roles_sha256=hashlib.sha256(Path(a.roles).read_bytes()).hexdigest(),conditions_sha256=hashlib.sha256(Path(a.conditions).read_bytes()).hexdigest(),
    pools_checked=len(pools),design=a.design,feasible_cells=len(cells),cells_by_condition=dict(by),labels_modified=False,target_outcomes_read=False,
    selection_phase=a.selection_phase,restricted_pool_list=a.restrict_pool_list,restricted_pool_count=len(allowed) if allowed is not None else None,
    selection_status='Conditions chosen after broad internal screen; outside-screen images/buildings flagged for extension, not called new external data'))
 print(json.dumps(dict(feasible_cells=len(cells),by_condition=dict(by))),flush=True)
if __name__=='__main__':main()
