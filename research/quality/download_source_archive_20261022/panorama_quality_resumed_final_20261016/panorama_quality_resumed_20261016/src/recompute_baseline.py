from pathlib import Path
import sys,json,time,traceback,importlib.util
from concurrent.futures import ProcessPoolExecutor
import numpy as np,pandas as pd
from b8_models import configs,score
ROOT=Path(__file__).resolve().parents[1]
engine=None

def initialize():
 global engine
 p=ROOT/'vendor/frozen/src/quality.py';s=importlib.util.spec_from_file_location('frozen_quality_checked',p);engine=importlib.util.module_from_spec(s);s.loader.exec_module(engine)
def compute(p):
 try:
  m=engine.measure(p['answer'],p['reference'])
  return dict(object_id=p['object_id'],record_id=p['record_id'],**m)
 except Exception as e:return dict(object_id=p['object_id'],record_id=p['record_id'],status='exception',reasons=[repr(e)],traceback=traceback.format_exc())
if __name__=='__main__':
 start=time.time();pairs=json.loads((ROOT/'inputs/fixed_pairs.json').read_text());meta=pd.read_csv(ROOT/'inputs/cohort_metadata.csv').set_index('object_id')
 results=[]
 with (ROOT/'results/baseline_recomputed.jsonl').open('w') as log,ProcessPoolExecutor(max_workers=4,initializer=initialize) as pool:
  for i,r in enumerate(pool.map(compute,pairs,chunksize=4)):
   log.write(json.dumps(r,ensure_ascii=False,allow_nan=False)+'\n');log.flush();results.append(r)
   if (i+1)%100==0:print('baseline',i+1,'seconds',round(time.time()-start,1),flush=True)
 rows=[];diff=[]
 for r in results:
  if r['status']!='complete':continue
  m=r['metrics'];row=dict(object_id=r['object_id'],record_id=r['record_id'],**m)
  for c in configs():row[c.name]=float(score(m['iou_2d'],m['S_bottom_deg'],m['dir'],m['Hmean'],m['Hcenter'],c))
  row['IoU3D100']=100*m['iou_3d_corner_mean'];rows.append(row)
  old=meta.loc[r['object_id']]
  diff.append(dict(object_id=r['object_id'],**{k:row[k]-old[k] for k in ['iou_2d','S_bottom_deg','dir','Hmean','Hcenter','IoU3D100']},B8L2=row['B8L2_original']-old['B8L2']))
 pd.DataFrame(rows).to_csv(ROOT/'results/baseline_and_all_B_parameters.csv',index=False)
 pd.DataFrame(diff).to_csv(ROOT/'results/baseline_parity_differences.csv',index=False)
 summary=dict(input_rows=len(pairs),complete=len(rows),failures=[r for r in results if r['status']!='complete'],seconds=time.time()-start,max_abs_difference=pd.DataFrame(diff).drop(columns='object_id').abs().max().to_dict())
 (ROOT/'results/baseline_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2));print(json.dumps(summary,ensure_ascii=False,indent=2))
