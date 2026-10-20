#!/usr/bin/env python3
"""Select a compact publication table without selecting directions or signs."""
import pandas as pd
from assessment_summary_common import HERE,write_csv

def main():
    p=pd.read_csv(HERE/'nested_new2/primary_n13_aggregate.csv.gz')
    p['proposal_id']=p.outgoing_class.map({'C01':'R01','C02':'R02'})
    p['context_id']='fixed_n13_m'+p.m.astype(str);p['subset']='overall'
    p['n_min']=13;p['n_max']=13;p['m_min']=p.m;p['m_max']=p.m
    p['method_id']='R_directswap_geometry_partition_b2_K2__ordinary_new__mixed_history_v1';p['domain']='ordinary_new'
    d=pd.read_csv(HERE/'directions/direction_aggregate.csv.gz');f=pd.concat([p,d],ignore_index=True)
    cols=['proposal_id','method_id','domain','context_id','subset','outgoing_class','incoming_class',
        'n_min','n_max','m_min','m_max','events','pools','true_images','buildings','unique_teams','unique_AB_pairs','actual_people',
        'net_B8L2_change_finite_events','A_complete_events','B_complete_events','C_complete_events',
        'A_scored_events','B_scored_events','C_scored_events','within_joint_stable_main','cross_joint_stable_main','gap_joint_stable_main',
        'within_geometry_shape_main','cross_geometry_shape_main','gap_geometry_shape_main','gap_geometry_noQ_main',
        'net_B8L2_change','net_D10_change','within_abs_B8L2_change','cross_abs_B8L2_change','within_absQ_gt5','cross_absQ_gt5',
        'net_Q_worsen_gt5','net_diag_wall_coverage_05_delta','net_diag_corner_recall_05_delta','cross_minus_within_history_Q',
        'net_B8L2_change_positive_true_images','net_B8L2_change_negative_true_images',
        'net_B8L2_change_positive_buildings','net_B8L2_change_negative_buildings']
    write_csv(HERE/'FINAL_REVERSE_ASSESSMENT_SMALL.csv',f[cols])

if __name__=='__main__':main()
