#!/usr/bin/env python3
"""Registered extra-background, direct-room and duplicate-request sensitivities.

No feature or type fitting. Four even k nodes are not a full integer curve.
"""
from pathlib import Path
import sys
import numpy as np
import pandas as pd
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent
sys.path.insert(0,str(HERE))
from evaluate_common import unit_summary,boolcol,savej,PRIMARY
sys.path.insert(0,str(ROOT/'recovered/work_v2_20261019/profiles'))
from room_weighting import aggregate_declared_groups

def room_sensitivity():
    p=HERE/'MATCHED_BACKGROUND_PER_IMAGE.csv.gz'
    data=pd.read_csv(p)
    memberships=pd.read_csv(ROOT/'recovered/work_v2_20261019/profiles/declared_room_groups.csv')
    summary=[];details=[];coverage=[]
    for key,g in data.groupby(['method_id','panel_id','k','stratum','metric']):
        label=dict(zip(['method_id','panel_id','k','stratum','metric'],key))
        groups,cov=aggregate_declared_groups(g,memberships,['within','between','contrast'],building_col='building')
        linked=g[g.image_id.isin(memberships.image_id)]
        r=dict(label,**{k:v for k,v in cov.items() if not isinstance(v,list)})
        for metric in ['within','between','contrast']:
            r[metric+'_declared_group_equal']=groups[metric].mean() if len(groups) else np.nan
            r[metric+'_linked_image_equal']=linked[metric].mean()
            r[metric+'_linked_building_equal']=linked.groupby('building')[metric].mean().mean()
        summary.append(r);coverage.append(dict(label,unlinked_image_ids=cov['unlinked_input_image_ids']))
        details.extend(dict(label,**x) for x in groups.to_dict('records'))
    pd.DataFrame(summary).to_csv(HERE/'DIRECT_ROOM_GROUP_SENSITIVITY.csv',index=False)
    pd.DataFrame(details).to_csv(HERE/'DIRECT_ROOM_GROUP_DETAILS.csv.gz',index=False)
    savej(HERE/'DIRECT_ROOM_COVERAGE.json',{'source':'frozen original room groups with physical_same=支持','inference_unit':'building','no_transitive_closure':True,'no_missing_singletons_invented':True,'rows':coverage})

def nested_sensitivity(e,w):
    f=e[e.panel_id.eq('A_nested_even_v1')].copy()
    for c in [x for x in w if x.startswith('rel__')]:f[c]=w.loc[f.index,c].to_numpy()
    methods=[m for m in ['Q3','old_QT','old_QTD_archive','forward_selected','reverse_selected','reverse_selected_global','reverse_selected_difficulty'] if 'rel__'+m in f]
    rows=[];summ=[];changes=[]
    for chain,g in f.groupby('nested_chain_id'):
        g=g.sort_values('k');first=g.iloc[0]
        row=dict(nested_chain_id=chain,building=first.building,image_id=first.image_id,worker_a=first.worker_a,worker_b=first.worker_b,n_observed_k=len(g),k_nodes='|'.join(map(str,g.k)),complete_four_nodes=tuple(g.k)==(8,12,16,24))
        for metric in ['stable_main','stable_strict','stable_loose','stable_D10','either_failure','abs_delta_Q','floor_change','node_changed']:
            vals=g[metric].to_numpy()
            for k,v in zip(g.k,vals):row[metric+'_k'+str(k)]=v
        row['all_four_stable']=bool(row['complete_four_nodes'] and g.stable_main.all())
        row['any_observed_failure']=bool(g.either_failure.any())
        row['stable_then_unstable_observed']=bool(np.any(g.stable_main.to_numpy()[:-1] & ~g.stable_main.to_numpy()[1:]))
        for m in methods:
            v=g['rel__'+m].unique();assert len(v)==1,'same pair/building/difficulty unexpectedly changes label across k'
            row['relation__'+m]=v[0]
        rows.append(row)
        for j in range(len(g)-1):
            a,b=g.iloc[j],g.iloc[j+1]
            z=dict(nested_chain_id=chain,building=first.building,image_id=first.image_id,k_from=int(a.k),k_to=int(b.k),stable_gain=float(b.stable_main)-float(a.stable_main),abs_Q_change_difference=b.abs_delta_Q-a.abs_delta_Q,floor_change_difference=b.floor_change-a.floor_change,failure_gain=float(b.either_failure)-float(a.either_failure))
            for m in methods:z['relation__'+m]=row['relation__'+m]
            changes.append(z)
    chains=pd.DataFrame(rows);trans=pd.DataFrame(changes)
    for m in methods:
        for relation,g in chains[chains.complete_four_nodes].groupby('relation__'+m):
            for metric in ['all_four_stable','any_observed_failure','stable_then_unstable_observed']:
                summ.append(dict(method_id=m,relation=relation,metric=metric,kind='complete_four_node_chains',**unit_summary(g,metric)))
        for (ka,kb,relation),g in trans.groupby(['k_from','k_to','relation__'+m]):
            for metric in ['stable_gain','abs_Q_change_difference','floor_change_difference','failure_gain']:
                summ.append(dict(method_id=m,relation=relation,metric=metric,k_from=ka,k_to=kb,kind='observed_adjacent_nodes_only',**unit_summary(g,metric)))
    chains.to_csv(HERE/'NESTED_FOUR_NODE_CHAINS.csv.gz',index=False)
    trans.to_csv(HERE/'NESTED_OBSERVED_TRANSITIONS.csv.gz',index=False)
    pd.DataFrame(summ).to_csv(HERE/'NESTED_FOUR_NODE_SUMMARY.csv',index=False)
    savej(HERE/'NESTED_INTERPRETATION.json',{'chains':len(chains),'four_node_chains':int(chains.complete_four_nodes.sum()),'full_four_node_images':chains[chains.complete_four_nodes].image_id.nunique(),'not_full_integer_curve':True,'probabilities_multiplied_across_k':False,'evaluation_only_panel':True,'one_swap_per_background_at_each_k':'No within-vs-between contrast on exactly the same nested background; method Brier comparisons use the identical event IDs.'})

def duplicate_sensitivity(e,w):
    keys=['panel_id','pool_id','k','team_id_a','team_id_b']
    duplicate=e.duplicated(keys,keep='first')
    rows=[]
    methods=[m for m in ['baseline_k_difficulty','Q3','old_QT','old_QTD_archive','forward_selected','reverse_selected'] if 'p__'+m in w]
    for m in methods:
        f=e[['panel_id','k','building','image_id','stable_main']].copy();f['brier']=(w['p__'+m].to_numpy()-f.stable_main.astype(float))**2
        for label,mask in [('all_registered_requests',np.ones(len(e),bool)),('unique_actual_endpoint_pairs',~duplicate.to_numpy())]:
            for (panel,k),g in f.loc[mask].groupby(['panel_id','k']):
                for metric in ['stable_main','brier']:rows.append(dict(method_id=m,duplicate_policy=label,panel_id=panel,k=k,metric=metric,**unit_summary(g,metric)))
    pd.DataFrame(rows).to_csv(HERE/'DUPLICATE_REQUEST_SENSITIVITY.csv',index=False)
    savej(HERE/'DUPLICATE_REQUEST_RECEIPT.json',{'identity':keys,'duplicate_requests':int(duplicate.sum()),'new_human_samples_created_by_duplicates':False,'by_panel':e.loc[duplicate].panel_id.value_counts().to_dict()})

def main():
    e=pd.read_csv(HERE/'COMMON_EVENT_ANALYSIS_INPUT.csv.gz',low_memory=False)
    w=pd.read_csv(HERE/'EVENT_PREDICTIONS_WIDE.csv.gz',low_memory=False)
    for c in ['stable_main','stable_strict','stable_loose','stable_D10','either_failure','node_changed']:e[c]=boolcol(e[c])
    nested_sensitivity(e,w);print('nested done',flush=True)
    duplicate_sensitivity(e,w);print('duplicates done',flush=True)
    room_sensitivity();print('direct rooms done',flush=True)
if __name__=='__main__':main()
