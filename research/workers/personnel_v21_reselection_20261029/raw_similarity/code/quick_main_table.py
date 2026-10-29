from pathlib import Path
import pandas as pd,numpy as np
W=Path(__file__).resolve().parents[2];O=W/'raw_similarity';d=pd.read_csv(O/'RAW_CLASS_DISTANCE_BY_POOL.csv.gz',low_memory=False)
d=d[d.condition.eq('manual')&d.layer.eq('ordinary_manual')].copy();metrics=[c[:-7] for c in d if c.endswith('_within')]
rows=[]
for (method,support,subset),g in d.groupby(['method','support','subset']):
 cols=[m+'_'+c for m in metrics for c in ['within','cross','gap']]
 im=g.groupby(['image_id','building'])[cols].mean().reset_index();build=im.groupby('building')[cols].mean()
 for m in metrics:
  z=im.dropna(subset=[m+'_within',m+'_cross']);b=z.groupby('building')[[m+'_within',m+'_cross',m+'_gap']].mean()
  rows.append(dict(method=method,support=support,subset=subset,metric=m,images=len(z),buildings=len(b),pools=g.pool_id.nunique(),
   image_within=z[m+'_within'].mean(),image_cross=z[m+'_cross'].mean(),image_gap=z[m+'_gap'].mean(),
   image_ratio=z[m+'_cross'].mean()/z[m+'_within'].mean() if z[m+'_within'].mean()>1e-12 else np.nan,
   images_cross_larger=int(z[m+'_gap'].gt(1e-10).sum()),building_within=b[m+'_within'].mean(),building_cross=b[m+'_cross'].mean(),
   building_gap=b[m+'_gap'].mean(),buildings_cross_larger=int(b[m+'_gap'].gt(1e-10).sum())))
pd.DataFrame(rows).to_csv(O/'MANUAL_MAIN_TABLE_READY.csv',index=False,encoding='utf-8-sig')
print('rows',len(rows),flush=True)
z=pd.DataFrame(rows);s=z[(z.support=='common45_known')&(z.subset=='same_corner_count')&(z.metric=='geometry_pair_angle')]
print(s[['method','images','image_within','image_cross','image_gap','images_cross_larger']].round(4).to_string(index=False))
