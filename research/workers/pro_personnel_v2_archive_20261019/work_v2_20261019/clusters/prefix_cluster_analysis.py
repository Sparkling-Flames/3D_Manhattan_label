"""Actual ordered prefixes and local-cluster arrival composition."""
from __future__ import annotations
import collections,hashlib,json
from pathlib import Path
import numpy as np
import pandas as pd
from analyze_fusion_clusters import attach_flags,bs
HERE=Path(__file__).resolve().parent;FUSION=HERE.parent/'fusion'

def main():
    out=HERE/'prefix_analysis';out.mkdir(exist_ok=True)
    labels=pd.read_csv(HERE/'assignments.csv');labels=labels[labels.method.eq('affinity') & labels.layer.eq('ordinary_manual')]
    lm={(r.pool_id,int(r.threshold_deg),r.worker_id):r.local_cluster_id for r in labels.itertuples()}
    source=FUSION/'prefix_transitions.csv.gz';raw=pd.read_csv(source,low_memory=False);raw=raw[raw.layer.eq('ordinary_manual')].copy();d=[]
    for cut in [9,12]:
        x=raw[raw.path_family.eq('uniform_prefix') | (raw.path_family.eq('cluster_oracle_prefix') & raw.threshold.eq(cut))].copy()
        x=attach_flags(x);x['threshold_deg']=cut;shares=[];new=[];ncl=[]
        for p,w,bg in zip(x.pool_id,x.added_worker,x.member_workers_a):
            members=bg.split('|');ct=collections.Counter(lm[p,cut,q] for q in members);c=lm[p,cut,w]
            shares.append(ct[c]/len(members));new.append(ct[c]==0);ncl.append(len(ct))
        x['added_cluster_prior_share']=shares;x['new_cluster_arrival']=new;x['prior_local_cluster_count']=ncl
        x['quality_drop_gt2']=np.where(x.B8L2_change.notna(),x.B8L2_change.lt(-2).astype(float),np.nan)
        x['quality_gain_gt2']=np.where(x.B8L2_change.notna(),x.B8L2_change.gt(2).astype(float),np.nan)
        x['quality_within2']=np.where(x.B8L2_change.notna(),x.B8L2_change.abs().le(2).astype(float),np.nan)
        x['shared_identity_vote_loss_any']=x.unchanged_identity_vote_losses.gt(0)
        d.append(x)
    d=pd.concat(d,ignore_index=True);d.to_csv(out/'actual_prefix_steps_with_clusters.csv.gz',index=False)
    metrics=['B8L2_change','abs_B8L2_change','floor_jaccard_difference','node_changed','quality_drop_gt2','quality_gain_gt2','quality_within2',
             'joint_geometric_stable','joint_with_shared_connections_and_retention','complete_to_incomplete','incomplete_to_complete','threshold_increased','shared_identity_vote_loss_any']
    rows=[]
    for key,g in d.groupby(['threshold_deg','path_family','path_strategy','k_from','k_to']):
        for metric in metrics:
            value=pd.to_numeric(g[metric],errors='coerce');a=g[['pool_id','building_id']].copy();a['value']=value
            b=a.groupby(['building_id','pool_id']).value.mean().groupby('building_id').mean();z=bs(b)
            rows.append(dict(zip(['threshold_deg','path_family','path_strategy','k_from','k_to'],key),metric=metric,attempts=len(g),observed=int(value.notna().sum()),
                images=g.pool_id.nunique(),buildings=z['n'],building_equal_mean=z['mean'],low=z['low'],high=z['high']))
    pd.DataFrame(rows).to_csv(out/'step_summary.csv',index=False)
    # Arrival association on random paths only, at the same image and k. The
    # different paths have different backgrounds: never call this a fixed-background causal contrast.
    random=d[d.path_family.eq('uniform_prefix') & d.k_from.ge(4)].copy();associations=[]
    for cut,g in random.groupby('threshold_deg'):
        for metric in ['abs_B8L2_change','floor_jaccard_difference','joint_geometric_stable']:
            v=g.groupby(['pool_id','image_id','building_id','difficulty','k_from','new_cluster_arrival'])[metric].mean().unstack('new_cluster_arrival')
            if True not in v or False not in v:continue
            h=(v[True]-v[False]).dropna().rename('difference').reset_index();h['metric']=metric;h['threshold_deg']=cut;associations.append(h)
    if associations:
        a=pd.concat(associations,ignore_index=True);a.to_csv(out/'new_cluster_arrival_image_k_association.csv',index=False)
    # Native frozen fusion is recomputed for each actual prefix. Compare the
    # two ordered strategies at equal k; the endpoint geometry is set-defined.
    teamsource=FUSION/'team_results.csv'
    cols=['pool_id','image_id','image','building','difficulty','k','request_id','request_family','strategy','threshold','path_id','team_id','member_workers',
        'B8L2','D10','iou_2d','omission','extension','nodes','Hmean','complete_evaluable','source_time_total_seconds','source_time_missing_n','target_time_total_seconds','target_time_missing_n']
    teams=pd.read_csv(teamsource,usecols=cols,low_memory=False);t=teams[teams.request_family.eq('cluster_oracle_prefix')].copy();t.to_csv(out/'oracle_prefix_endpoints.csv.gz',index=False)
    results=[];imrows=[]
    for metric in ['B8L2','D10','iou_2d','omission','extension','nodes','Hmean','complete_evaluable','source_time_total_seconds','target_time_total_seconds']:
        t[metric]=pd.to_numeric(t[metric],errors='coerce').astype(float)
        w=t.pivot(index=['threshold','k','pool_id','image_id','building','difficulty'],columns='strategy',values=metric)
        if 'cluster_balanced' not in w or 'largest_cluster_first' not in w:continue
        x=(w.cluster_balanced-w.largest_cluster_first).rename('balanced_minus_largest').reset_index();x['metric']=metric;imrows.append(x)
        for (cut,k),g in x.groupby(['threshold','k']):
            z=bs(g.groupby('building').balanced_minus_largest.mean())
            results.append(dict(threshold_deg=cut,k=k,metric=metric,attempted_images=len(g),measurable_images=int(g.balanced_minus_largest.notna().sum()),
                buildings=z['n'],difference=z['mean'],low=z['low'],high=z['high']))
    pd.concat(imrows,ignore_index=True).to_csv(out/'balanced_minus_largest_image_k.csv',index=False);pd.DataFrame(results).to_csv(out/'balanced_minus_largest_summary.csv',index=False)
    receipt=dict(ordinary_images=raw.pool_id.nunique(),buildings=raw.building.nunique(),actual_transition_attempts=len(raw),
        unique_actual_team_transitions=len(raw[['pool_id','team_id_a','team_id_b']].drop_duplicates()),
        cluster_oracle_transitions=int(raw.path_family.eq('cluster_oracle_prefix').sum()),uniform_transitions=int(raw.path_family.eq('uniform_prefix').sum()),
        threshold_labeled_rows=len(d),oracle_full_paths=t.path_id.nunique(),oracle_endpoints=len(t),
        prefixes_are_actual_member_sequences=True,every_prefix_recomputed=True,set_order_invariance_not_history_dependence=True,
        low_k_shown_but_main_from_k4=True,source_missing_not_imputed=True,target_missing_not_replaced_with_source=True,
        comparisons_not_causal=True,input_sha256=hashlib.sha256(source.read_bytes()).hexdigest())
    (out/'RECEIPT.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt,indent=2))

if __name__=='__main__':main()
