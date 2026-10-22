from pathlib import Path
import sys,json,time,importlib.util
from dataclasses import replace
from concurrent.futures import ProcessPoolExecutor
import numpy as np,pandas as pd
from controls import geom,transform,redundant
from envelope_quality import normalized_pair,measure_pair,NormalizedConfig,shell
ROOT=Path(__file__).resolve().parents[1]

def check(p):
 a=p['answer'];r=p['reference'];m=normalized_pair(a,r);fields=['score','score_l2','I','boundary_coverage','Hmean','Hcenter']
 rows=[]
 states=[('joint_yaw_37',dict(angle=37)),('joint_yaw_90',dict(angle=90)),('ring_start',dict(roll=1)),('ring_reverse',dict(reverse=True)),('joint_translate',dict(shift=(4.123,-2.71)))]
 for name,kw in states:
  q=normalized_pair(transform(a,**kw),transform(r,**kw));rows.append(dict(object_id=p['object_id'],state=name,status=q['status'],**{k:abs(q[k]-m[k]) for k in fields}))
 q=normalized_pair(redundant(a),redundant(r));rows.append(dict(object_id=p['object_id'],state='3D_redundant_subdivision',status=q['status'],**{k:abs(q[k]-m[k]) for k in fields}))
 return rows

def refine(p):
 q0=normalized_pair(p['answer'],p['reference']);q1=normalized_pair(p['answer'],p['reference'],NormalizedConfig(step_side=.00125));q2=normalized_pair(p['answer'],p['reference'],NormalizedConfig(step_side=.000625))
 return dict(object_id=p['object_id'],record_id=p['record_id'],score_original=q0['score'],score_l2_original=q0['score_l2'],score_half=q1['score'],score_quarter=q2['score'],score_l2_half=q1['score_l2'],score_l2_quarter=q2['score_l2'],error_half=abs(q1['score']-q0['score']),error_quarter=abs(q2['score']-q0['score']),error_l2_quarter=abs(q2['score_l2']-q0['score_l2']))

if __name__=='__main__':
 t=time.time();pairs=json.loads((ROOT/'inputs/fixed_pairs.json').read_text())
 with ProcessPoolExecutor(max_workers=4) as pool:rows=[r for batch in pool.map(check,pairs,chunksize=4) for r in batch]
 pd.DataFrame(rows).to_csv(ROOT/'results/invariance5346.csv',index=False)
 with ProcessPoolExecutor(max_workers=4) as pool:refinement=list(pool.map(refine,pairs,chunksize=4))
 pd.DataFrame(refinement).to_csv(ROOT/'results/quadrature_refinement891.csv',index=False)
 # Reproduce the received implementation, then test new measurements on exact controls.
 spec=importlib.util.spec_from_file_location('gqs_received',ROOT/'vendor/gqs_received.py');gqs=importlib.util.module_from_spec(spec);sys.modules[spec.name]=gqs;spec.loader.exec_module(gqs)
 erows=[]
 for fn in ['qa_matching_tie_regression.json','height_nearest_tie_old_new.json']:
  d=json.loads((ROOT/'inputs/external_controls'/fn).read_text());a=geom(d['answer_xz'],d.get('answer_height',d.get('wall_height',2)));r=geom(d['reference_xz'],d.get('reference_height',d.get('wall_height',2)))
  for yaw in [0,37,90,173,270]:
   aa=transform(a,angle=yaw);rr=transform(r,angle=yaw);old=gqs.score_pair(aa,rr);new=normalized_pair(aa,rr)
   erows.append(dict(control=fn,yaw=yaw,old_QA=old['QA'],old_QB=old['QB'],old_QC=old['QC'],new_score=new['score'],new_score_l2=new['score_l2'],new_Hcenter=new['Hcenter'],new_height_tie_lower=new['Hcenter_tie_lower'],new_tie_fraction_AG=new['height_tie_fraction_AG']))
 pd.DataFrame(erows).to_csv(ROOT/'results/received_defects_replayed.csv',index=False)
 # Self comparisons of every unique current fixed full reference.
 refs={p['reference_id']:p for p in pairs};selves=[]
 for rid,p in refs.items():
  q=normalized_pair(p['reference'],p['reference']);selves.append(dict(reference_id=rid,status=q['status'],score=q['score'],score_l2=q.get('score_l2')))
 pd.DataFrame(selves).to_csv(ROOT/'results/reference_self_checks.csv',index=False)
 df=pd.DataFrame(rows);rf=pd.DataFrame(refinement)
 summary=dict(invariance_pairs=len(pairs),states=len(rows),max_changes=df.groupby('state')[['score','score_l2','I','boundary_coverage','Hmean','Hcenter']].max().to_dict(orient='index'),refined_pairs=len(rf),quadrature_max=rf[['error_half','error_quarter','error_l2_quarter']].max().to_dict(),reference_count=len(selves),min_self_score=min(x['score'] for x in selves),seconds=time.time()-t)
 (ROOT/'results/numerical_audit.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary,indent=2))
