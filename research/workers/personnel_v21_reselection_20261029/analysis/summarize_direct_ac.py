"""Direct AC output: its own comparison, never manufacture a same-class B."""
from pathlib import Path
import argparse
import pandas as pd
import numpy as np
from measure_registered_events import save,jsave
from summarize_registered_screen import add_roles

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--metrics',nargs='+',required=True);ap.add_argument('--roles',required=True);ap.add_argument('--out',required=True);a=ap.parse_args();out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
 d=pd.concat([pd.read_csv(p,low_memory=False) for p in a.metrics],ignore_index=True).drop_duplicates('event_id')
 d=add_roles(d,pd.read_csv(a.roles,low_memory=False))
 keys=['method','condition','scope','role_direction','n','m']
 metrics=[c for c in d if c.endswith('_CA') and not c.startswith(('A_','C_','time_source_')) and pd.api.types.is_numeric_dtype(d[c])]
 metrics += [c for c in ['A_failed','C_failed','AC_scored','record_time_CA_pct_source_matched'] if c in d]
 for extra in [[],['official_difficulty'],['geometric_challenge']]:
  kk=keys+extra;p=d.groupby(kk+['pool_id','image','building'],dropna=False)[metrics].mean().reset_index();im=p.groupby(kk+['image','building'],dropna=False)[metrics].mean().reset_index();b=im.groupby(kk+['building'],dropna=False)[metrics].mean().reset_index();g=im.groupby(kk,dropna=False);bg=b.groupby(kk,dropna=False)
  s=g[metrics].mean().add_suffix('_mean_image').join(g[metrics].count().add_suffix('_valid_images'))
  for table,tier in [(im,'image'),(b,'building')]:
   x=table.copy();fields=['B8L2_CA','D10_CA','record_time_CA_pct_source_matched'];x[fields]=x[fields].gt(0).where(x[fields].notna()).astype(float);s=s.join(x.groupby(kk,dropna=False)[fields].sum(min_count=1).add_suffix('_positive_'+tier+'s'))
  s=s.join(bg[metrics].mean().add_suffix('_mean_building')).join(bg[metrics].count().add_suffix('_valid_buildings'))
  s=s.join(d.groupby(kk,dropna=False).agg(events=('event_id','size'),pools=('pool_id','nunique'),images=('image','nunique'),buildings=('building','nunique'),A_failed_events=('A_failed','sum'),C_failed_events=('C_failed','sum'),AC_scored_events=('AC_scored','sum'),Q_loss10_events=('Q_loss10_CA','sum'),Q_loss10_valid_events=('Q_loss10_CA','count'))).reset_index()
  suffix='_'.join(extra).upper() if extra else 'ALL'
  save(out/(suffix+'_RESULTS.csv.gz'),s);save(out/(suffix+'_BY_IMAGE.csv.gz'),im)
 save(out/'EXACT_EVENTS_WITH_ROLES.csv.gz',d)
 jsave(out/'COMPLETE.json',dict(events=len(d),methods=d.method.nunique(),pools=d.pool_id.nunique(),images=d.image.nunique(),buildings=d.building.nunique(),comparison='C-A only; no within-vs-cross amplitude claim without B',new_fusions=0))
 print('complete',len(d),flush=True)
if __name__=='__main__':main()
