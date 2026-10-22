"""Compact direct-role comparison with actual members and full count vectors."""
from __future__ import annotations
import argparse
from pathlib import Path
import numpy as np
import pandas as pd
from register_population_orders import save_csv


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--directory',required=True);a=ap.parse_args()
    root=Path(a.directory)
    support=pd.read_csv(root/'POLICY_PER_IMAGE_K.csv.gz',usecols=['pool_id','policy','pool_n','layer'])
    common=set(support.groupby('pool_id').policy.nunique().loc[lambda x:x.eq(4)].index)
    ids=['pool_id','image','building','condition','layer','difficulty','pool_n','policy','k']
    values=['actual_m','actual_replacement_fraction','target_seat_change','comparison_role_seat_change',
            'structure_coarse_net_seat_changes','structure_fine_net_seat_changes',
            'joint_coarse_net_seat_changes','joint_fine_net_seat_changes',
            'same_target_member_set','B8L2_delta','QT_Q_delta','QT_time_logratio',
            'score_failure_nonpolicy_focal','score_failure_nonpolicy_comparison']
    d=pd.read_csv(root/'POLICY_DIRECT_PAIRED_PREFIX_EVENTS.csv.gz',usecols=ids+values)
    d=d[d.pool_id.isin(common)&d.pool_n.ge(20)&d.layer.isin(['ordinary_manual','ordinary_semi'])]
    image_rows=[];summary_rows=[]
    phases=[('first_half_average_k3plus',d.k.ge(3)&d.k.le(np.floor(d.pool_n/2)))]
    phases += [('k'+str(k),d.k.eq(k)) for k in [3,6,10,20]]
    keys=['pool_id','image','building','condition','layer','policy']
    for phase,mask in phases:
        z=d[mask].copy()
        z['attempted']=1;z['scorable']=z.B8L2_delta.notna().astype(int)
        z['QT_pairs']=z.QT_Q_delta.notna().astype(int)
        z['Q_loss_gt5']=z.B8L2_delta.lt(-5).astype(int)
        z['Q_gain_gt5']=z.B8L2_delta.gt(5).astype(int)
        sums=['attempted','scorable','QT_pairs','Q_loss_gt5','Q_gain_gt5',
              'score_failure_nonpolicy_focal','score_failure_nonpolicy_comparison']
        means=[c for c in values if c not in sums]
        by=z.groupby(keys,dropna=False)
        # Mean paths within k, then give each observed k equal weight, matching
        # the main focal analysis even when some k have fewer valid Q/T pairs.
        per_k=z.groupby(keys+['k'],dropna=False)[means].mean()
        per_image=per_k.groupby(level=keys,dropna=False).mean()
        im=per_image.join(by[sums].sum().add_suffix('_events')).reset_index()
        im['phase']=phase;image_rows.append(im)
        for (condition,layer,policy),g in im.groupby(['condition','layer','policy']):
            row=dict(condition=condition,layer=layer,policy=policy,phase=phase,
                images=len(g),images_Q_defined=int(g.B8L2_delta.notna().sum()),
                images_Q_up=int(g.B8L2_delta.gt(0).sum()),images_Q_down=int(g.B8L2_delta.lt(0).sum()),
                images_same_target_member_set=int(g.same_target_member_set.eq(1).sum()),
                buildings=g.building.nunique())
            bg=g.groupby('building')[means].mean()
            row['buildings_Q_defined']=int(bg.B8L2_delta.notna().sum())
            row['buildings_Q_up']=int(bg.B8L2_delta.gt(0).sum())
            row['buildings_Q_down']=int(bg.B8L2_delta.lt(0).sum())
            for c in means:
                row[c+'_image_equal']=g[c].mean();row[c+'_building_equal']=bg[c].mean()
            for c in sums:row[c+'_events']=int(g[c+'_events'].sum())
            row['QT_recorded_time_pct_image_equal']=100*np.expm1(row['QT_time_logratio_image_equal'])
            row['QT_recorded_time_pct_building_equal']=100*np.expm1(row['QT_time_logratio_building_equal'])
            summary_rows.append(row)
    save_csv(pd.concat(image_rows,ignore_index=True),root/'POLICY_DIRECT_MAIN_PER_IMAGE.csv')
    save_csv(pd.DataFrame(summary_rows),root/'POLICY_DIRECT_MAIN_FIXED_N20.csv')
    print({'summary_rows':len(summary_rows),'image_rows':sum(map(len,image_rows))},flush=True)


if __name__=='__main__':main()
