import sys,json,time
from pathlib import Path
from dataclasses import asdict
import pandas as pd,numpy as np
from geomscore import Config,score_pair
O=Path(__file__).resolve().parents[1]
def flat(s):
 d={k:v for k,v in s.items() if not isinstance(v,dict)}
 d.update({'height_'+k:v for k,v in s['surface_height'].items()})
 d.update({k:v for k,v in s['angle_detail'].items() if k!='event_scales'})
 d['turning_deg']=s['turning']['distance_deg']
 d['event_counts']=';'.join(f"{x['nA']}/{x['nR']}" for x in s['angle_detail']['event_scales'])
 return d

def main():
 pairs=json.load(open(O/'inputs/current_pairs.json'));md=pd.read_csv(O/'inputs/current_metadata.csv').set_index('object_id');rows=[];details={};start=time.time()
 for i,p in enumerate(pairs):
  try:s=score_pair(p['answer'],p['reference']);d=flat(s);d['status']='ok';details[p['object_id']]=s
  except Exception as e:d=dict(status=type(e).__name__+':'+str(e))
  m=md.loc[p['object_id']].fillna('').to_dict();rows.append(dict(object_id=p['object_id'],**m,**d))
  if (i+1)%50==0:print(i+1,time.time()-start,flush=True)
 pd.DataFrame(rows).to_csv(O/'results/current244_scores.csv',index=False)
 (O/'results/current244_measurements.json').write_text(json.dumps(details,ensure_ascii=False,indent=2,allow_nan=False))
 (O/'config.json').write_text(json.dumps(asdict(Config()),indent=2))
 selves=json.load(open(O/'inputs/reference_self.json'));rr=[]
 for p in selves:
  try:s=score_pair(p['reference'],p['reference']);rr.append(dict(reference_id=p['reference_id'],**flat(s),status='ok'))
  except Exception as e:rr.append(dict(reference_id=p['reference_id'],status=str(e)))
 pd.DataFrame(rr).to_csv(O/'results/reference_self77.csv',index=False)
 d=pd.DataFrame(rows);print(d.status.value_counts());print(d[d.case_id!=''][['case_id','grade','B8L2','QA','QB','QC','angle_RMS_deg','detail_loss','turning_deg','height_local_error','height_mean_log_error']].sort_values('case_id').to_string(index=False));print('elapsed',time.time()-start)
if __name__=='__main__':main()
