"""Create compact review tables and independently check saved ABC identities.

This script performs no fusion, classification, or score recalculation. Primary
Q directions share all three scored endpoints with the same-origin amplitude.
"""
from pathlib import Path
import argparse,json
import numpy as np
import pandas as pd

METRICS=['B8L2_same_origin_within','B8L2_same_origin_cross','B8L2_same_origin_gap',
         'joint_Q_BA','joint_Q_CA','joint_Q_CB','D10_CA','IoU3D100_CA','S_bottom_deg_CA',
         'fusion_turn_n_CA','fusion_short_turn_edges_CA','fusion_redundancy_n_CA',
         'geometry_area_h2_CA','height_mean_h_CA','boundary_loss_CA','direction_loss_CA',
         'height_loss_CA','omission_CA','extension_CA','geometry_pair_angle_same_origin_gap',
         'geometry_bev_distance_same_origin_gap','geometry_centroid_distance_same_origin_gap',
         'geometry_log_area_distance_same_origin_gap','record_time_CA_pct_source_matched',
         'record_time_CB_pct_source_matched','record_time_CA_pct_single_source',
         'A_failed','B_failed','C_failed','ABC_scored']
CORE_METHODS=['TARGET_DSTRUCT_K3','V21_DSTRUCT_RAW3_K3','OPPSTRUCT_K3','OPPJOINT_K3','OPPJOINT_K4']

def wanted(frame):
    return (frame.scope.eq('primary') & frame.method.isin(CORE_METHODS) &
            ((frame.stage_scope.eq('combined_union') & frame.m.eq(7) & frame.n.isin([14,20])) |
             (frame.stage_scope.eq('new_only') & frame.m.eq(8) & frame.n.isin([12,16]))))

def main(args):
    out=Path(args.out)
    s=pd.read_csv(out/'ALL_STAGES_DIRECTION_N_M_SUMMARY.csv.gz')
    ss=s[wanted(s)].copy()
    keys=['stage_scope','method','scope','n','m','axis','rank_direction','events','pools','images','buildings',
          'jointly_scored_events','A_failed_events','B_failed_events','C_failed_events']
    stats=['mean_image','median_image','p10_image','p90_image','valid_images','positive_images',
           'negative_images','near_zero_images','mean_building','valid_buildings','positive_buildings']
    qcols=keys+[metric+'_'+stat for metric in METRICS[:6] for stat in stats]
    ss[qcols].to_csv(out/'MAIN_CONDITIONS_JOINT_Q.csv',index=False)
    long=[]
    for row in ss.to_dict('records'):
        for metric in METRICS:
            long.append({**{k:row[k] for k in keys},'metric':metric,**{k:row[metric+'_'+k] for k in stats}})
    pd.DataFrame(long).to_csv(out/'MAIN_CONDITIONS_METRIC_LONG.csv',index=False)
    pat=pd.read_csv(out/'ALL_STAGES_DIRECTION_PATTERNS.csv')
    pat[wanted(pat)].to_csv(out/'MAIN_CONDITIONS_DIRECTION_PATTERNS.csv',index=False)

    pools=pd.read_csv(out/'ALL_STAGES_POOL_RESULTS.csv.gz')
    common_rows=[]
    for stage,n,m in [('combined_union',14,7),('combined_union',20,7),('new_only',12,8),('new_only',16,8)]:
        z=pools[pools.stage_scope.eq(stage)&pools.n.eq(n)&pools.m.eq(m)&pools.rank_direction.eq('2/3->3/3')&pools.scope.eq('primary')]
        a=z[z.method.eq('TARGET_DSTRUCT_K3')];b=z[z.method.eq('V21_DSTRUCT_RAW3_K3')]
        j=a.merge(b,on=['pool_id','image','building'],suffixes=('_T','_R'),validate='one_to_one')
        for metric in METRICS:
            x=j.dropna(subset=[metric+'_T',metric+'_R'])
            im=x.groupby(['image','building'])[[metric+'_T',metric+'_R']].mean()
            bu=im.groupby(level='building').mean()
            common_rows.append(dict(stage=stage,n=n,m=m,role='hard_turn_rank_asc:2/3->3/3',metric=metric,
                common_registered_pools=len(j),paired_pools=len(x),images=len(im),buildings=len(bu),
                T=im[metric+'_T'].mean(),R=im[metric+'_R'].mean(),Tpos=int(im[metric+'_T'].gt(1e-9).sum()),
                Rpos=int(im[metric+'_R'].gt(1e-9).sum()),Rgreater=int((im[metric+'_R']>im[metric+'_T']+1e-9).sum()),
                Tbuilding=bu[metric+'_T'].mean(),Rbuilding=bu[metric+'_R'].mean(),
                Tbuildingpos=int(bu[metric+'_T'].gt(1e-9).sum()),Rbuildingpos=int(bu[metric+'_R'].gt(1e-9).sum())))
    pd.DataFrame(common_rows).to_csv(out/'MAIN_HARD23_COMMON_POOL_READING.csv',index=False)

    d=pd.read_csv(out/'COMBINED_UNION_EVENTS_WITH_ROLES.csv.gz',low_memory=False)
    overlap=[]
    for n,m in [(12,8),(16,8)]:
        z=d[d.source_stage.eq('this_turn_supplement')&d.n.eq(n)&d.m.eq(m)&d.scope.eq('primary')&d.rank_direction.eq('2/3->3/3')]
        a=z[z.method.eq('TARGET_DSTRUCT_K3')];b=z[z.method.eq('V21_DSTRUCT_RAW3_K3')]
        for pid in sorted(set(a.pool_id)&set(b.pool_id)):
            aa=a[a.pool_id.eq(pid)];bb=b[b.pool_id.eq(pid)];cols=['A_team_key','B_team_key','C_team_key']
            identA=set(map(tuple,aa[cols].to_numpy()));identB=set(map(tuple,bb[cols].to_numpy()))
            overlap.append(dict(n=n,m=m,pool_id=pid,image=aa.image.iloc[0],TARGET_events=len(identA),RAW3_events=len(identB),
                common_ABC_identities=len(identA&identB),common_original_A=len(set(aa.A_team_key)&set(bb.A_team_key)),all_ABC_same=identA==identB))
    pd.DataFrame(overlap).to_csv(out/'NEW_M8_COMMON_POOL_EXACT_TEAM_OVERLAP.csv',index=False)

    c=pd.read_csv(args.capacity_events,low_memory=False)
    cols=['method','pool_id','n','m','A_team_key','B_team_key','C_team_key']
    x=d[d.method.isin(c.method.unique())&d.scope.eq('primary')]
    y=c[c.layer.eq('ordinary_manual')]
    j=x.merge(y[cols+['A_Q','B_Q','C_Q']],on=cols,validate='one_to_one')
    checks={}
    for our,a,b in [('B8L2_BA','B_Q','A_Q'),('B8L2_CA','C_Q','A_Q'),('B8L2_CB','C_Q','B_Q')]:
        good=np.isclose(j[our],j[a]-j[b],equal_nan=True,atol=1e-8,rtol=1e-8)
        checks[our]={'matched':bool(good.all()),'max_error':float((j[our]-(j[a]-j[b])).abs().max())}
        assert good.all()
    q3=j[['A_Q','B_Q','C_Q']].notna().all(axis=1)
    gap=((j.C_Q-j.A_Q).abs()-(j.B_Q-j.A_Q).abs()).where(q3)
    assert np.isclose(j.B8L2_same_origin_gap,gap,equal_nan=True,atol=1e-8,rtol=1e-8).all()
    for n,m in [(14,7),(20,7),(12,8),(16,8)]:
        aa=x[x.n.eq(n)&x.m.eq(m)];bb=y[y.n.eq(n)&y.m.eq(m)]
        assert set(map(tuple,aa[cols].to_numpy()))==set(map(tuple,bb[cols].to_numpy())),(n,m)
    receipt=dict(independently_rejoined_competitive_events=len(j),metrics=checks,same_origin_gap_matches=True,
        all_four_main_grids_exact_identity_sets_match_capacity_agent=True,common_m8_identity_rows=len(overlap),
        primary_Q_directions='joint_Q_BA/CA/CB use the same three-scored-arm events as Q amplitude; pair-only B8L2_CA/CB remain separately available',
        old_missing_pair_geometry='Fixed-A scalar-only additions have unavailable angular and BEV pair geometry; no zero imputation. Centroid and log-area reconstructed from saved footprint summaries.',
        weighting='backgrounds within exact XYZ block, blocks within target pool, targets within image, then equal image or building')
    (out/'INDEPENDENT_Q_IDENTITY_CROSSCHECK.json').write_text(json.dumps(receipt,indent=2))
    print(json.dumps(receipt),flush=True)

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--out',required=True);ap.add_argument('--capacity-events',required=True);main(ap.parse_args())
