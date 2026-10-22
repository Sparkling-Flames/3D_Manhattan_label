from pathlib import Path
from dataclasses import replace,asdict
import json,numpy as np,pandas as pd
from structure_quality import *
from run_audit import readj,xz,writej
ROOT=Path(__file__).resolve().parents[1]
g=readj(ROOT/'inputs/geometries30.json');df=pd.read_csv(ROOT/'results/review30_results.csv');cfgs={
'v01_tight':Config(),
'pos3_10_ang5_30':replace(Config(),position_free_deg=3,position_zero_deg=10),
'pos3_10_ang10_45':replace(Config(),position_free_deg=3,position_zero_deg=10,angle_free_deg=10,angle_zero_deg=45),
'pos5_15_ang10_45':replace(Config(),position_free_deg=5,position_zero_deg=15,angle_free_deg=10,angle_zero_deg=45),
'pos3_10_ang10_45_k15':replace(Config(),position_free_deg=3,position_zero_deg=10,angle_free_deg=10,angle_zero_deg=45,structure_scale=1.5),
'pos3_10_ang10_45_k1':replace(Config(),position_free_deg=3,position_zero_deg=10,angle_free_deg=10,angle_zero_deg=45,structure_scale=1),
'pos3_10_ang10_45_no_salience':replace(Config(),position_free_deg=3,position_zero_deg=10,angle_free_deg=10,angle_zero_deg=45,salience_free_h=0,salience_full_h=1e-8),
'pos3_10_ang10_45_salience_05_20':replace(Config(),position_free_deg=3,position_zero_deg=10,angle_free_deg=10,angle_zero_deg=45,salience_free_h=.05,salience_full_h=.20),
}
rows=[]
for name,cfg in cfgs.items():
 for _,r in df.iterrows():
  a,b=xz(g[r.object_id.strip()]),xz(g[r.reference_id]);s=structure(a,b,cfg)
  q=candidate_score(r.iou_2d,r.S_bottom_deg,r.Hmean,r.Hcenter,s['C'],cfg)
  rows.append({'config':name,'case_id':r.case_id,'phase':r.phase,'grade':r.grade,'B8L2':r.B8L2,'C':s['C'],'Q':q,'delta_B':q-r.B8L2})
d=pd.DataFrame(rows);d.to_csv(ROOT/'results/coarse_sensitivity_30.csv',index=False)
print(d.pivot(index='case_id',columns='config',values='Q').round(2).to_string())
# Unequal ordinal levels only encode order. No fabricated numerical grade intervals.
order={'poor':0,'average_poor':1,'average':2,'good_average':3,'good':4}
summary=[]
for name in cfgs:
 z=d[(d.config==name)&d.case_id.str.startswith('N')]
 den=bad=0
 for i in range(len(z)):
  for j in range(i):
   a,b=z.iloc[i],z.iloc[j]
   if order[a.grade]==order[b.grade]:continue
   den+=1;bad+=int((order[a.grade]-order[b.grade])*(a.Q-b.Q)<0)
 summary.append({'config':name,'ordinary_cases':len(z),'ordered_case_pairs':den,'discordant_pairs_descriptive':bad,'note':'post-exposure, exploratory; correlated pairs; not CV or independent evidence'})
pd.DataFrame(summary).to_csv(ROOT/'results/ordinal_sensitivity_descriptive.csv',index=False)
writej(ROOT/'results/explored_configs.json',{n:asdict(c) for n,c in cfgs.items()})
