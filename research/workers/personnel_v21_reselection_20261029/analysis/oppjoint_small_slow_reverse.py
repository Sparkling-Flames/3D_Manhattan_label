"""Reverse AC time percentage on exactly the forward time-comparable support.
The reverse has no same-slow B when the pool has only one slow member.
"""
from pathlib import Path
import gzip,os,json
import pandas as pd,numpy as np
W=Path(__file__).resolve().parents[1];O=W/'analysis/fine_increment/oppjoint_small_slow'
def save(p,d):
 b=d.to_csv(index=False).encode('utf-8-sig')
 if p.suffix=='.gz':b=gzip.compress(b,mtime=0)
 t=p.with_name(p.name+'.writing')
 with t.open('wb') as f:f.write(b);f.flush();os.fsync(f.fileno())
 t.replace(p)
bg=pd.read_csv(O/'COMMON_BACKGROUND_TARGETS.csv.gz')
stat=pd.read_csv(O/'BACKGROUND_TARGET_METRICS.csv.gz')
end=pd.read_csv(O/'USED_ENDPOINT_SCALARS_AND_MEMBERS.csv.gz').set_index('team_key')
v=stat[stat.metric.eq('record_time_pct')&stat.valid_ABC.gt(0)];rows=[]
for r in bg[bg.background_target_id.isin(v.background_target_id)].itertuples():
 a=end.loc[r.source_team_keys.split('|')];c=end.loc[r.C_team_key]
 a=a[a.time_source_kinds.eq(c.time_source_kinds)&a.recorded_time_total_seconds.notna()];assert len(a)>=2
 rows.append(dict(background_target_id=r.background_target_id,panel_id=r.panel_id,pool_id=r.pool_id,
  image=r.image,building=r.building,n=r.n,Z=r.Z,
  reverse_direct_AC_time_pct=float(((a.recorded_time_total_seconds/c.recorded_time_total_seconds)-1).mean()*100),
  reverse_direct_AC_Q=float((a.B8L2-c.B8L2).mean())))
x=pd.DataFrame(rows);save(O/'REVERSE_DIRECT_AC_TIME_SAME_SUPPORT.csv.gz',x)
f=['reverse_direct_AC_time_pct','reverse_direct_AC_Q']
panel=x.groupby(['panel_id','pool_id','image','building'])[f].mean().reset_index()
pool=panel.groupby(['pool_id','image','building'])[f].mean().reset_index()
im=pool.groupby(['image','building'])[f].mean().reset_index();bu=im.groupby('building')[f].mean()
save(O/'REVERSE_DIRECT_AC_BY_IMAGE.csv',im)
result=dict(images=len(im),buildings=len(bu),image_equal_mean=im[f].mean().to_dict(),
 building_equal_mean=bu.mean().to_dict(),design='direct reverse AC; no claim of same-small-class B',
 time_source='user_processed_reported_not_raw_log_replayed')
(O/'REVERSE_DIRECT_AC_SUMMARY.json').write_text(json.dumps(result,ensure_ascii=False,indent=2));print(json.dumps(result,ensure_ascii=False))
