from pathlib import Path
import sys,json,time,os
from dataclasses import replace
import numpy as np
import pandas as pd

ROOT=Path('/workspace/scratch/81fa50cc64f5');STUDY=ROOT/'new_pro_return/panorama_quality_three_routes_20261016';OUT=Path(os.environ.get('GQS_INVARIANCE_OUT',str(ROOT/'new_pro_audit/invariance891')));OUT.mkdir(exist_ok=False,parents=True)
sys.path.insert(0,str(STUDY/'src'))
from geomscore import *
INPUT=Path(os.environ.get('GQS_891_INPUT',str(ROOT/'new_pro_audit/current891_extension')))
pairs=json.loads((INPUT/'fixed891_pairs.json').read_text())
base=json.loads((INPUT/'measurements891.json').read_text())

def transform(g,kind):
    b=np.array(g['bottom3d']);t=np.array(g['top3d'])
    if kind=='common_yaw90':R=np.array([[0.,-1.],[1.,0.]]);b[:,[0,2]]=b[:,[0,2]]@R;t[:,[0,2]]=t[:,[0,2]]@R
    elif kind=='common_yaw23':
        a=np.deg2rad(23.);R=np.array([[np.cos(a),-np.sin(a)],[np.sin(a),np.cos(a)]]);b[:,[0,2]]=b[:,[0,2]]@R;t[:,[0,2]]=t[:,[0,2]]@R
    elif kind=='reverse_answer':b=b[::-1];t=t[::-1]
    elif kind=='roll_answer':b=np.roll(b,2,axis=0);t=np.roll(t,2,axis=0)
    elif kind=='linear_insert_answer':
        k=int(np.argmax(np.linalg.norm(np.roll(b,-1,axis=0)-b,axis=1)));j=(k+1)%len(b)
        b=np.insert(b,k+1,(b[k]+b[j])/2,axis=0);t=np.insert(t,k+1,(t[k]+t[j])/2,axis=0)
    return {'bottom3d':b.tolist(),'top3d':t.tolist()}

rows=[];changed={};start=time.time()
for i,p in enumerate(pairs):
    old=base[p['object_id']]
    for kind in ['common_yaw90','common_yaw23','reverse_answer','roll_answer','linear_insert_answer']:
        a=transform(p['answer'],kind);r=transform(p['reference'],kind) if kind.startswith('common_') else p['reference']
        s=score_pair(a,r)
        row={k:p[k] for k in ['object_id','record_id','image_id','image_code','worker_id','condition']}
        row.update(kind=kind,**{'delta_'+k:s[k]-old[k] for k in ['QA','QB','QC','I']},
                   delta_angle_penalty=s['angle_detail']['angle_penalty']-old['angle_detail']['angle_penalty'],
                   delta_structural_loss=s['angle_detail']['structural_loss']-old['angle_detail']['structural_loss'],
                   delta_height_local=s['surface_height']['local_error']-old['surface_height']['local_error'],
                   delta_height_penalty=(s['surface_height']['local_penalty']+s['surface_height']['mean_penalty'])-(old['surface_height']['local_penalty']+old['surface_height']['mean_penalty']),
                   delta_turning_deg=s['turning']['distance_deg']-old['turning']['distance_deg'])
        rows.append(row)
        if abs(row['delta_QA'])>.1 or abs(row['delta_QB'])>.1 or abs(row['delta_QC'])>.2:changed[p['object_id']+':'+kind]={'pair':p,'base':old,'changed':s}
    if (i+1)%100==0:print('PROGRESS',i+1,time.time()-start,flush=True)
d=pd.DataFrame(rows);d.to_csv(OUT/'invariance891.csv',index=False)
(OUT/'changed_cases.json').write_text(json.dumps(changed,ensure_ascii=False,allow_nan=False),encoding='utf8')
summary={kind:{k:float(sub[k].abs().max()) for k in ['delta_QA','delta_QB','delta_QC','delta_I','delta_angle_penalty','delta_structural_loss','delta_height_local','delta_height_penalty','delta_turning_deg']} for kind,sub in d.groupby('kind')}
(OUT/'SUMMARY.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(json.dumps(summary,indent=2))
