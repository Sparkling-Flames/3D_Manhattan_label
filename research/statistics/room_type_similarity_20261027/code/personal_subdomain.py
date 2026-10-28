#!/usr/bin/env python3
"""Reaggregate identical OOF predictions on recorded multi-building purposes."""
import os
for k in ['OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS']:os.environ.setdefault(k,'1')
import argparse,json,hashlib
from pathlib import Path
import pandas as pd
from personal import summarize,save

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--primary',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args();a.out.mkdir(parents=True,exist_ok=True)
 ps=[]
 for oc in ['Q','D10','annotation_turn5']:
  d=pd.read_csv(a.primary/f'OOF_{oc}.csv.gz',dtype={'object_id':str})
  im=d[['image_key','building','room_type_model','room_type_status']].drop_duplicates()
  k=im[im.room_type_status=='recorded_purpose'].groupby('room_type_model').building.nunique()
  types=k[k>=2].index.tolist()
  ps.append(d[d.room_type_model.isin(types)])
 P=pd.concat(ps);I,D=summarize(P,a.out)
 support=P[['object_id','image_key','image','building','worker_id','room_type_model','room_type_status']].drop_duplicates()
 save(support,a.out/'TARGET_SUPPORT.csv.gz')
 r={'reaggregation_only':True,'same_fitted_predictions':str(a.primary),'no_model_refit':True,'rule':'Recorded purpose and >=2 actual buildings across original target inventory; missing/explicit unknown/open multifunction/single-building special preserved in all177 main tables',
  'purposes':types,'records':len(support),'images':support.image_key.nunique(),'buildings':support.building.nunique(),'people':support.worker_id.nunique(),'fitted_source_main_inventory':177}
 (a.out/'COMPLETE.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps(r,ensure_ascii=False));print(pd.read_csv(a.out/'METHOD_SUMMARY.csv').to_string(index=False))
if __name__=='__main__':main()
