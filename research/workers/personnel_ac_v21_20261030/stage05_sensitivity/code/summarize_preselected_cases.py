"""Compact complete-case tables, including existing equal-size pure-class anchors."""
from pathlib import Path
import argparse,csv,gzip,json,sys
import numpy as np
import pandas as pd
from analyze_population_sensitivity import save,validate_final_tables,PRESELECTED_IMAGES,finite_array

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--cases',required=True);ap.add_argument('--metrics',required=True)
    ap.add_argument('--links',required=True);ap.add_argument('--out',required=True);a=ap.parse_args()
    src=Path(a.cases);out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
    teams=pd.read_csv(src/'PRESELECTED_8_17_10_TEAMS.csv.gz')
    pairs=pd.read_csv(src/'PRESELECTED_8_17_10_CONTRASTS.csv.gz')
    decomp=pd.read_csv(src/'PRESELECTED_ALLIANCE_WHOLE_DECOMPOSITION.csv.gz')
    assert len(teams)==28 and len(pairs)==84 and len(decomp)==48
    q=teams.pivot(index='image',columns='alliance_classes',values='B8L2').reset_index();save(q,out/'SEVEN_TEAM_Q_BY_IMAGE.csv.gz')
    rows=[]
    for key,g in decomp.groupby(['image','parent_contrast_id','n_small','n_large','role_direction'],sort=False):
        r=dict(zip(['image','parent_contrast_id','n_small','n_large','role_direction'],key))
        r.update(middle_teams=g.middle_team.nunique(),total_unique_pairs=g.total_event_id.nunique(),D_workers=g.parent_D_workers.iloc[0],small_team=g.small_team.iloc[0],large_team=g.large_team.iloc[0])
        for metric in ['B8L2_CA','D10_CA','fusion_turn_n_CA','geometry_bev_distance_AC','record_time_CA_seconds_single_source']:
            for leg in ['total','equal','addition']:
                x=finite_array(g[metric+'__'+leg]);r[metric+'__'+leg+'_mean']=float(x.mean()) if len(x) else np.nan
                r[metric+'__'+leg+'_min']=float(x.min()) if len(x) else np.nan
                r[metric+'__'+leg+'_max']=float(x.max()) if len(x) else np.nan
                r[metric+'__'+leg+'_valid']=int(len(x)>0) if leg=='total' else len(x)
        rows.append(r)
    save(pd.DataFrame(rows),out/'TWELVE_PARENT_DECOMPOSITION_SUMMARY.csv.gz')
    pids=set(teams.pool_id);eids=set()
    with gzip.open(a.links,'rt',encoding='utf-8-sig',newline='') as f:
        for r in csv.DictReader(f):
            if r['pool_id'] in pids and r['method']=='OPPJOINT_K3' and r['design_family']=='B_equal_whole_class' and r['background_profile']=='neutral_members_0':eids.add(r['event_id'])
    wanted=['event_id','pool_id','image','building','method','scope','n','m','D_n','source_class','target_class',
        'A_team_key','C_team_key','B8L2_CA','D10_CA','fusion_turn_n_CA','geometry_bev_distance_AC',
        'record_time_CA_seconds_source_matched','record_time_CA_pct_source_matched',
        'fusion_failure_observed_risk_change_CA','Q_missing_risk_change_CA']
    frames=[]
    for pid in sorted(pids):
        d=pd.read_csv(Path(a.metrics)/'metric_shards'/(pid+'.csv.gz'),usecols=lambda c:c in wanted)
        d=d[d.event_id.isin(eids)&d.D_n.eq(0)]
        frames.append(d)
    equal=pd.concat(frames,ignore_index=True).drop_duplicates('event_id')
    save(equal,out/'PURE_WHOLE_EQUAL_ANCHOR_EVENTS.csv.gz')
    rows=[]
    metrics=[c for c in wanted if c.endswith(('_CA','_AC')) or c.startswith('record_time_CA')]
    for key,g in equal.groupby(['image','pool_id','building','source_class','target_class','n','m'],sort=False):
        r=dict(zip(['image','pool_id','building','source_class','target_class','n','m'],key));r['exact_pairs']=g.event_id.nunique()
        r['A_member_variants']=g.A_team_key.nunique();r['C_member_variants']=g.C_team_key.nunique();r['event_ids']='|'.join(g.event_id)
        for metric in metrics:
            x=finite_array(g[metric]);r[metric+'__valid']=len(x);r[metric+'__mean']=float(x.mean()) if len(x) else np.nan
            r[metric+'__min']=float(x.min()) if len(x) else np.nan;r[metric+'__max']=float(x.max()) if len(x) else np.nan
            r[metric+'__median']=float(np.median(x)) if len(x) else np.nan
            r[metric+'__positive_pairs']=int(np.sum(x>1e-9));r[metric+'__negative_pairs']=int(np.sum(x< -1e-9))
        tv=g.record_time_CA_seconds_source_matched.notna();r['Q_mean_on_time_valid_pairs']=float(g.loc[tv,'B8L2_CA'].mean()) if tv.any() else np.nan
        rows.append(r)
    result=pd.DataFrame(rows);assert len(result)==12
    save(result,out/'PURE_WHOLE_EQUAL_ANCHOR_SUMMARY.csv.gz')
    validation=validate_final_tables(out);(out/'READABILITY_RECEIPT.json').write_text(json.dumps(validation,ensure_ascii=False,indent=2)+'\n')
    print(result[['image','source_class','target_class','n','exact_pairs','B8L2_CA__mean','B8L2_CA__min','B8L2_CA__max',
                  'record_time_CA_seconds_source_matched__valid','record_time_CA_seconds_source_matched__mean','record_time_CA_pct_source_matched__mean']].to_string(index=False))

if __name__=='__main__':main()
