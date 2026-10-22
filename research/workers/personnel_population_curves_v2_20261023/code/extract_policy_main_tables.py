"""Compact fixed-N>=20 policy table with exact attempted-prefix denominators."""
from __future__ import annotations
import argparse
from pathlib import Path
import numpy as np
import pandas as pd
from register_population_orders import save_csv


PHASES=['k3','k6','k10','k20','first_half_average_k3plus']


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--directory',required=True);a=ap.parse_args();root=Path(a.directory)
    s=pd.read_csv(root/'POLICY_FOCAL_SUMMARY.csv',low_memory=False)
    p=pd.read_csv(root/'POLICY_PER_IMAGE_K.csv.gz',low_memory=False)
    s=s[s.cohort.isin(['all_four_common_Nge20','all_four_common_Nge20_time_complete'])&
        s.terminal_scope.eq('all_supported')&s.stratum.eq('all')&
        s.layer.isin(['ordinary_manual','ordinary_semi'])&s.landmark.isin(PHASES)].copy()
    common=set(p.groupby('pool_id').policy.nunique().loc[lambda x:x.eq(4)].index)
    p=p[p.pool_id.isin(common)&p.pool_n.ge(20)&p.layer.isin(['ordinary_manual','ordinary_semi'])]
    rows=[]
    for row in s.to_dict('records'):
        g=p[(p.condition==row['condition'])&(p.layer==row['layer'])&(p.policy==row['policy'])]
        if row['cohort'].endswith('_time_complete'):g=g[g.pool_source_time_complete]
        phase=row['landmark']
        g=g[g.k.ge(3)&g.k.le(np.floor(g.pool_n/2))] if phase.startswith('first_half') else g[g.k.eq(int(phase[1:]))]
        assert g.image.nunique()==row['images']
        row['exact_attempted_prefix_pairs']=int(g.paired_paths.sum())
        row['exact_scorable_prefix_pairs']=int(g.paired_Q.sum())
        row['exact_source_time_prefix_pairs']=int(g.source_time_pairs.sum())
        row['exact_QT_prefix_pairs']=int(g.QT_pairs.sum())
        row['exact_Qloss_gt5_pairs']=int(np.rint(g.Q_loss_gt5_fraction.fillna(0)*g.paired_Q).sum())
        row['exact_Qgain_gt5_pairs']=int(np.rint(g.Q_gain_gt5_fraction.fillna(0)*g.paired_Q).sum())
        row['images_with_any_Qloss_gt5_prefix']=int(g.groupby('pool_id').Q_loss_gt5_fraction.max().gt(0).sum())
        for side in ['natural','priority']:
            for endpoint_flag in ['score_failure_nonpolicy','incomplete_nonpolicy']:
                f=endpoint_flag+'_'+side+'_rate'
                row[side+'_'+endpoint_flag+'_events']=int(np.rint(g[f]*g.paired_paths).sum())
                row[side+'_'+endpoint_flag+'_image_equal_rate']=g.groupby('pool_id')[f].mean().mean()
                row[side+'_'+endpoint_flag+'_affected_images']=int(g.groupby('pool_id')[f].max().gt(0).sum())
            row[side+'_scorable_Q_image_equal']=g.groupby('pool_id')['Q_'+side+'_mean'].mean().mean()
        row['priority_single_member_set_image_k']=int(g.priority_fixed_membership.sum())
        row['priority_exact_target_block_image_k']=int((g.priority_exact_target_block&g.priority_fixed_membership).sum())
        row['full_pool_image_k']=int(g.at_full_pool.sum())
        row['total_image_k']=len(g)
        row['SD_ddof']=0
        rows.append(row)
    result=pd.DataFrame(rows).sort_values(['condition','cohort','landmark','policy'])
    save_csv(result,root/'POLICY_MAIN_FIXED_N20.csv')
    print({'main_rows':len(result),'policy_comparators':'same paired natural base/k','all_effects':'same final actual pool'},flush=True)


if __name__=='__main__':main()
