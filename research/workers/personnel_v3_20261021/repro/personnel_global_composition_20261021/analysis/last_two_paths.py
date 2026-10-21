"""Enumerate every last-two-addition order from already complete set layers.

For each background of N-2 members, the two omitted people can be added in two
orders. All three prefix sets have already been fused. This is an exact suffix
population, not all N! complete addition orders and not a new online algorithm.
"""
from __future__ import annotations
import os
for k in ['OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS']:os.environ[k]='1'
from pathlib import Path
import hashlib,json,itertools,math
import numpy as np
import pandas as pd
from analyze_global import balanced,write

HERE=Path(__file__).resolve().parent
STUDY=HERE.parent


def main():
    p=STUDY/'composition/runtime/stage2/TEAMS_SCALARS.csv.gz'
    if not p.exists():p=STUDY/'composition/TEAMS_SCALARS.csv.gz'
    fields=['team_key','pool_id','image','building','condition','layer','difficulty','pool_n','k','member_workers',
      'B8L2','D10','nodes','complete_evaluable','score_status','minimum_support','source_time_total_seconds',
      'iou_2d','S_bottom_deg','dir','Hmean','Hcenter','ref_node_recall_5','ref_edge_recall_5']
    d=pd.read_csv(p,usecols=fields,low_memory=False)
    rows=[];pool_counts=[]
    for pid,g in d.groupby('pool_id',sort=False):
        N=int(g.pool_n.iloc[0]);full=g[g.k.eq(N)];assert len(full)==1
        e=full.iloc[0];people=set(e.member_workers.split('|'))
        one=g[g.k.eq(N-1)];two=g[g.k.eq(N-2)]
        assert len(one)==N and len(two)==math.comb(N,2),('incomplete layer',pid)
        one_lookup={next(iter(people-set(r.member_workers.split('|')))):r for r in one.itertuples()}
        for r in two.itertuples():
            u,v=sorted(people-set(r.member_workers.split('|')))
            # Add u first => v is the single person still omitted.
            a=one_lookup[v];b=one_lookup[u]
            z={k:getattr(r,k) for k in ['pool_id','image','building','condition','layer','difficulty','pool_n']}
            z.update(background_n=N-2,added_u=u,added_v=v,background_team=r.team_key,
                prefix_add_u=a.team_key,prefix_add_v=b.team_key,final_team=e.team_key,
                represented_ordered_paths=2,identical_final_set=True)
            states={'start':r,'add_u':a,'add_v':b,'final':e}
            for name,state in states.items():
                for field in ['B8L2','D10','nodes','complete_evaluable','score_status','minimum_support']:
                    z[name+'_'+field]=getattr(state,field)
            for metric in ['B8L2','D10','nodes','iou_2d','S_bottom_deg','dir','Hmean','Hcenter','ref_node_recall_5','ref_edge_recall_5']:
                start,midu,midv,finish=[getattr(states[k],metric) for k in ['start','add_u','add_v','final']]
                z[metric+'_middle_abs_gap']=abs(midu-midv) if np.isfinite(midu) and np.isfinite(midv) else np.nan
                z[metric+'_net_two_additions']=finish-start if np.isfinite(finish) and np.isfinite(start) else np.nan
                if metric in ['B8L2','D10']:
                    z[metric+'_prefix_worst_gap']=abs(min(start,midu,finish)-min(start,midv,finish)) if all(np.isfinite(t) for t in [start,midu,midv,finish]) else np.nan
                    risks=[];gains=[]
                    for name,mid in [('u_then_v',midu),('v_then_u',midv)]:
                        ok=all(np.isfinite(t) for t in [start,mid,finish]);z[name+'_'+metric+'_comparable']=ok
                        z[name+'_'+metric+'_first_addition']=mid-start if ok else np.nan
                        z[name+'_'+metric+'_second_addition']=finish-mid if ok else np.nan
                        risk=float(min(mid-start,finish-mid)<-5) if ok else np.nan
                        z[name+'_'+metric+'_any_step_loss_gt5']=risk
                        risks.append(risk);gains.append(float(max(mid-start,finish-mid)>5) if ok else np.nan)
                    z[metric+'_order_mean_any_step_loss_gt5']=float(np.mean([x for x in risks if np.isfinite(x)])) if any(np.isfinite(x) for x in risks) else np.nan
                    z[metric+'_order_mean_any_step_gain_gt5']=float(np.mean([x for x in gains if np.isfinite(x)])) if any(np.isfinite(x) for x in gains) else np.nan
                    z[metric+'_both_orders_comparable']=all(np.isfinite(t) for t in [start,midu,midv,finish])
            for name,mid in [('u_then_v',a),('v_then_u',b)]:
                z[name+'_any_prefix_failure']=not (r.complete_evaluable and mid.complete_evaluable and e.complete_evaluable)
            z['order_mean_any_prefix_failure']=(z['u_then_v_any_prefix_failure']+z['v_then_u_any_prefix_failure'])/2
            z['order_changes_any_prefix_failure']=z['u_then_v_any_prefix_failure']!=z['v_then_u_any_prefix_failure']
            z['middle_nodes_differ']=a.nodes!=b.nodes
            z['both_orders_quality_available']=bool(z['B8L2_both_orders_comparable'])
            z['ordered_paths_quality_available']=int(z['u_then_v_B8L2_comparable'])+int(z['v_then_u_B8L2_comparable'])
            rows.append(z)
        pool_counts.append(dict(pool_id=pid,condition=e.condition,layer=e.layer,image=e.image,building=e.building,
            pool_n=N,background_n=N-2,unordered_backgrounds=len(two),ordered_last_two_paths=2*len(two),
            expected_ordered_paths=N*(N-1),exhaustive_last_two=True,all_full_N_factorial_orders_enumerated=False))
    result=pd.DataFrame(rows);write(result,'LAST_TWO_SUFFIX_PAIRS.csv.gz');write(pd.DataFrame(pool_counts),'LAST_TWO_POOL_COVERAGE.csv')
    # Summary rows preserve the native layer and the declared large-team scope.
    measures=['B8L2_middle_abs_gap','D10_middle_abs_gap','B8L2_prefix_worst_gap','D10_prefix_worst_gap',
      'B8L2_order_mean_any_step_loss_gt5','D10_order_mean_any_step_loss_gt5',
      'B8L2_order_mean_any_step_gain_gt5','order_mean_any_prefix_failure','order_changes_any_prefix_failure',
      'middle_nodes_differ','B8L2_net_two_additions','D10_net_two_additions','both_orders_quality_available']
    summaries=[]
    for scope,g in [('all_native_pools',result),('background_n_ge_20',result[result.background_n>=20])]:
        s,_=balanced(g,measures,['condition','layer']);s['scope']=scope;summaries.append(s)
    write(pd.concat(summaries,ignore_index=True),'LAST_TWO_PATH_SUMMARY.csv')
    receipt=dict(source=str(p.relative_to(STUDY)),input_sha256=hashlib.sha256(p.read_bytes()).hexdigest(),
        unique_backgrounds=len(result),represented_ordered_paths=int(result.represented_ordered_paths.sum()),
        pools=len(pool_counts),all_prefix_sets_already_computed=True,new_fusion_endpoint_calls=0,
        ordered_paths_all_three_quality_available=int(result.ordered_paths_quality_available.sum()),
        identical_final_set_for_both_orders=True,all_N_factorial_orders_enumerated=False,
        interpretation='Exact two-step suffix orders, not full sequences. No order-dependent final geometry is possible in the frozen deterministic set fusion.')
    (HERE/'LAST_TWO_PATH_RECEIPT.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps(receipt,ensure_ascii=False),flush=True)


if __name__=='__main__':main()
