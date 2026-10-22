from pathlib import Path
import json
import pandas as pd
from controls import one
import recompute_baseline as base
ROOT=Path(__file__).resolve().parents[1]
if __name__=='__main__':
 base.initialize();pairs=json.loads((ROOT/'inputs/doorway_conditional_pairs.json').read_text());rows=[]
 for p in pairs:
  row=one(dict(name=p['object_id'],family='unadmitted_doorway_conditional_stress',provenance=p['role'],answer=p['answer'],reference=p['reference']))
  row.update({k:p[k] for k in ['object_id','image_id','image_code','worker_id','condition','reference_id','ring_confirmed']});row['admitted_to_mainline']=False;row['used_to_select_parameters']=False;rows.append(row)
 pd.DataFrame(rows).to_csv(ROOT/'results/doorway_conditional_stress.csv',index=False)
 summary=pd.DataFrame(rows).groupby('image_code').agg(rows=('object_id','size'),B8L2=('B8L2_original','mean'),B8L2_D10=('B8L2_s32_d10','mean'),B8L2_s50_d10=('B8L2_s50_d10','mean'),EBC2_L2=('EBC2_score_l2','mean'),IoU3D=('IoU3D100','mean'))
 summary.to_csv(ROOT/'results/doorway_conditional_summary.csv');print(summary.to_string())
