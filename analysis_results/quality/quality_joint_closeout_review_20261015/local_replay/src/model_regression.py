"""Frozen candidate regression, including negative controls; no tuning."""
from quality import *
import pandas as pd
from copy import deepcopy

def mkfloor(xz,h=2.6):
 b=np.column_stack((np.array(xz)[:,0],-np.ones(len(xz)),np.array(xz)[:,1]));t=b.copy();t[:,1]=h-1
 return {'bottom3d':b.tolist(),'top3d':t.tolist()}

def main():
 R=ROOT/'results';theta=np.deg2rad(80);v=np.array([1.,0]);w=np.array([np.cos(theta),np.sin(theta)])
 pg=mkfloor(np.array([-(v+w)/2,(v-w)/2,(v+w)/2,(-v+w)/2]))
 sq=mkfloor([[-2,-2],[2,-2],[2,2],[-2,2]])
 branch=mkfloor([[-2,-2],[2,-2],[2,.8],[6,.8],[6,1.],[2,1.],[2,2],[-2,2]])
 negative=[dict(case_id='nonorthogonal_80deg_self',annotation_geometry=pg,reference_geometry=pg,**measure(pg,pg),role='synthetic_applicability_counterexample_not_oos_fit'),dict(case_id='orthogonal_branch_omission',annotation_geometry=sq,reference_geometry=branch,**measure(sq,branch),role='synthetic_structure_blindspot_no_human_severity_label')]
 old=pd.read_csv(ROOT/'source/prior_working_score_810.csv');cur=pd.read_csv(R/'ALL_3152_LEDGER.csv');check=old.merge(cur,on='record_id',suffixes=('_old','_now'))
 # Prior export names are kept; only compare actual non-null numeric rows.
 cols=list(old.columns);qcol='working_Q' if 'working_Q' in cols else 'final_Q' if 'final_Q' in cols else 'WQ' if 'WQ' in cols else None
 parity=[]
 if qcol:
  for _,r in check.iterrows():
   a=r[qcol+'_old'] if qcol+'_old' in check else r[qcol];b=r.WQ_now if 'WQ_now' in check else r.WQ
   if pd.notna(a) and pd.notna(b):parity.append(abs(float(a)-float(b)))
 out=dict(negative_controls=negative,prior_rows_compared=len(check),prior_numeric_column=qcol,prior_numeric_rows_compared=len(parity),maximum_previous_WQ_difference=max(parity) if parity else None,ordinary_and_doorway_parameters_changed=False,additional_parameter_search=False)
 dump(R/'FROZEN_MODEL_REGRESSION.json',out);print(json.dumps(out,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
