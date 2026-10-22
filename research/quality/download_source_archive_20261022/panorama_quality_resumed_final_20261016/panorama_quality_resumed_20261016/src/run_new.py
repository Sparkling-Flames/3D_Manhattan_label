from pathlib import Path
import json,time
from concurrent.futures import ProcessPoolExecutor
from dataclasses import replace,asdict
import pandas as pd
from envelope_quality import Config,configurations,measure_pair,combine
ROOT=Path(__file__).resolve().parents[1]

def work(p):
 row={k:p[k] for k in ['object_id','record_id','image_id','reference_id','current_target_id','answer_sha256','reference_sha256']}
 r=measure_pair(p['answer'],p['reference']);row.update(r)
 for c in configurations()[1:]:
  s=measure_pair(p['answer'],p['reference'],c);row[c.version]=s['score']
 if r['status']=='complete':
  row['EBC1_half_boundary']=combine(r['I'],r['boundary_coverage'],r['Hmean'],r['Hcenter'],replace(Config(),boundary_weight=.5))
  row['EBC1_double_boundary']=combine(r['I'],r['boundary_coverage'],r['Hmean'],r['Hcenter'],replace(Config(),boundary_weight=2.))
 return row
if __name__=='__main__':
 t=time.time();pairs=json.loads((ROOT/'inputs/fixed_pairs.json').read_text());rows=[]
 (ROOT/'inputs/EBC_PARAMETER_DESIGN.json').write_text(json.dumps([asdict(c) for c in configurations()],indent=2))
 with (ROOT/'results/new_scores.jsonl').open('w') as log,ProcessPoolExecutor(max_workers=4) as pool:
  for i,r in enumerate(pool.map(work,pairs,chunksize=4)):
   rows.append(r);log.write(json.dumps(r,ensure_ascii=False,allow_nan=False)+'\n');log.flush()
   if (i+1)%100==0:print('new_model',i+1,round(time.time()-t,1),flush=True)
 pd.DataFrame(rows).to_csv(ROOT/'results/new_scores891.csv',index=False)
 summary=dict(input_rows=len(pairs),complete=sum(r['status']=='complete' for r in rows),failures=[r for r in rows if r['status']!='complete'],camera_outside_scored=[{'object_id':r['object_id'],'record_id':r['record_id'],'score':r['score']} for r in rows if r['status']=='complete' and not r['answer_camera_inside']],seconds=time.time()-t)
 (ROOT/'results/new_summary.json').write_text(json.dumps(summary,indent=2,ensure_ascii=False));print(json.dumps(summary,indent=2))
