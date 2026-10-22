"""Recompute all 14 received real-geometry editing controls against FULL fixed GT.
Edited answers are counterfactuals, not additional human submissions. No GT subchain
is used. Original scores in the received JSON are evidence, not inputs to scoring.
"""
from pathlib import Path
import json,sys
import pandas as pd
import numpy as np
from envelope_quality import normalized_pair,shell
import recompute_baseline as base
from b8_models import score,configs
ROOT=Path(__file__).resolve().parents[1]

def metrics(a,r):
 b=base.engine.measure(a,r);n=normalized_pair(a,r)
 if b['status']!='complete' or n['status']!='complete':
  return dict(status='not_evaluable',baseline=b,new=n)
 m=b['metrics']
 return dict(status='complete',I=m['iou_2d'],Sb=m['S_bottom_deg'],D=m['dir'],B8L2=float(score(m['iou_2d'],m['S_bottom_deg'],m['dir'],m['Hmean'],m['Hcenter'])),B8L2_D10=float(score(m['iou_2d'],m['S_bottom_deg'],m['dir'],m['Hmean'],m['Hcenter'],configs()[1])),EBC2_L2=n['score_l2'],coverage=n['boundary_coverage'],Hmean=n['Hmean'],Hcenter=n['Hcenter'],IoU3D100=100*m['iou_3d_corner_mean'])

if __name__=='__main__':
 base.initialize();controls=json.loads((ROOT/'inputs/external_controls/real_coarsening_controls.json').read_text());pairs=json.loads((ROOT/'inputs/fixed_pairs.json').read_text());ids={p['record_id']:p for p in pairs};rows=[]
 for c in controls:
  p=ids[c['record_id']]
  # Canonical index changes are harmless; verify represented polygons and heights.
  ref1,ref2=shell(c['reference']),shell(p['reference']);ans1,ans2=shell(c['original_answer']),shell(p['answer'])
  referr=ref1['poly'].symmetric_difference(ref2['poly']).area;anserr=ans1['poly'].symmetric_difference(ans2['poly']).area
  assert referr<1e-8 and anserr<1e-8
  assert abs(ref1['mu']-ref2['mu'])<1e-8 and abs(ans1['mu']-ans2['mu'])<1e-8
  assert normalized_pair(c['reference'],p['reference'])['Hcenter']<1e-8 and normalized_pair(c['original_answer'],p['answer'])['Hcenter']<1e-8
  old=metrics(c['original_answer'],c['reference']);new=metrics(c['edited_answer'],c['reference'])
  row=dict(record_id=c['record_id'],object_id=p['object_id'],reference_id=p['reference_id'],edit_eps_h=c['eps'],answer_vertices_before=len(c['original_answer']['bottom3d']),answer_vertices_after=len(c['edited_answer']['bottom3d']),reference_geometry_area_difference=referr,original_geometry_area_difference=anserr,hausdorff_to_original=shell(c['original_answer'])['poly'].boundary.hausdorff_distance(shell(c['edited_answer'])['poly'].boundary),status=old['status']+'|'+new['status'])
  for k in ['I','Sb','D','B8L2','B8L2_D10','EBC2_L2','coverage','Hmean','Hcenter','IoU3D100']:
   row[k+'_before']=old.get(k);row[k+'_after']=new.get(k);row[k+'_delta']=new.get(k,np.nan)-old.get(k,np.nan)
  rows.append(row)
 df=pd.DataFrame(rows);df.to_csv(ROOT/'results/coarsening_replay14.csv',index=False)
 (ROOT/'results/coarsening_replay_summary.json').write_text(json.dumps(dict(controls=len(rows),unique_original_answers=int(df.record_id.nunique()),status_counts=df.status.value_counts().to_dict(),EBC2_L2_delta_min=float(df.EBC2_L2_delta.min()),EBC2_L2_delta_max=float(df.EBC2_L2_delta.max()),warning='counterfactual edits, not new human answers or independent validation; deleting details is not intrinsically a quality error'),indent=2))
 print(df[['record_id','edit_eps_h','answer_vertices_before','answer_vertices_after','B8L2_delta','EBC2_L2_delta']].to_string(index=False))
