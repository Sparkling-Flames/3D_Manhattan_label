"""Small reading tables from the complete scale/background summaries."""
from pathlib import Path
import pandas as pd

OUT=Path(__file__).resolve().parent/'scale_background_summary'
def main():
 p=pd.read_csv(OUT/'CAPACITY_POLICY_CORE_SUMMARY.csv');p=p[p.scope=='primary']
 qcols=['method','n','actual_m_pairs','pools','images','buildings','Q_delta_C_mean_image','Q_delta_B_mean_image','Q_delta_net_CB_mean_image','Q_delta_C_mean_building','Q_delta_B_mean_building','Q_delta_net_CB_mean_building','Q_delta_C_valid_images','Q_delta_C_positive_images','Q_delta_net_CB_positive_images','Q_delta_C_valid_buildings','Q_delta_C_positive_buildings','Q_delta_net_CB_positive_buildings','Q_delta_amplitude_gap_mean_image','Q_delta_amplitude_gap_mean_building','Q_delta_amplitude_gap_valid_images','Q_delta_amplitude_gap_valid_buildings']
 p[qcols].to_csv(OUT/'MAIN_POLICY_Q.csv',index=False)
 base=['method','n','pools','actual_m_pairs'];met=['D10_delta_C','IoU3D_delta_C','floor_WQ_delta_C','turn_delta_C','short_edge_delta_C','redundancy_delta_C','area_delta_C','height_delta_C','direction_loss_delta_C','height_loss_delta_C','time_delta_C_seconds','time_delta_B_seconds','time_delta_net_CB_seconds','time_delta_C_pct','time_delta_B_pct','C_small_failure','C_large_failure','C_new_failure','C_recovered','C_loss10','C_failure_or_loss10','B_small_failure','B_large_failure','B_new_failure']
 cols=base+[c for m in met for c in [m+'_mean_image',m+'_mean_building',m+'_valid_images',m+'_valid_path_pairs'] if c in p]
 p[cols].to_csv(OUT/'MAIN_POLICY_STRUCTURE_TIME_RISK.csv',index=False)
 f=pd.read_csv(OUT/'FIXED_M_PAIR_CORE_SUMMARY.csv')
 selected=(f.scope=='primary')&f.method.isin(['OPPJOINT_K4','TARGET_DSTRUCT_K3'])&(((f.n.isin([12,20]))&(f.m_small==2)&(f.m_large==6))|((f.n==26)&(f.m_small==1)&(f.m_large==4)))
 z=f[selected].copy();long=pd.read_csv(OUT/'FIXED_M_PAIR_ALL_METRIC_SUMMARY.csv.gz')
 v=long[long.measure=='B8L2_net_increment_matched_CB'][['method','condition','scope','role_direction','n','m_small','m_large','median_image','p10_image','p90_image','negative_images']]
 z=z.merge(v,on=['method','condition','scope','role_direction','n','m_small','m_large']);z.to_csv(OUT/'READING_EXAMPLES_FIXED_M.csv',index=False)
 print('saved',len(p),'capacity-policy rows and',len(z),'explicit fixed-m reading examples')
if __name__=='__main__':main()
