"""Explicit component ablations. Sb is frozen legacy input, not independently remeasured."""
from pathlib import Path
import pandas as pd,numpy as np
O=Path(__file__).resolve().parents[1]
def main():
 d=pd.read_csv(O/'results/current244_scores.csv');h=d.height_local_penalty+d.height_mean_penalty
 d['QA_no_angle']=100*d.I*np.exp(-h)*(1-.15*d.structural_loss)
 d['QA_no_structural_aux']=100*d.I*np.exp(-h-d.angle_penalty)
 d['QA_with_frozen_Sb_exponential']=d.QA*np.exp(-d.S_bottom_deg**2/32)
 d['QA_no_height']=100*d.I*np.exp(-d.angle_penalty)*(1-.15*d.structural_loss)
 cols=['object_id','case_id','grade','I','B8L2','QA','QA_no_angle','QA_no_structural_aux','QA_with_frozen_Sb_exponential','QA_no_height','angle_penalty','detail_loss','placement_loss','height_local_penalty','height_mean_penalty','S_bottom_deg']
 d[cols].to_csv(O/'results/component_ablation244.csv',index=False)
 print(d[d.case_id.isin(['N10','N17','N24','N06'])][cols[1:10]].to_string(index=False))
if __name__=='__main__':main()
