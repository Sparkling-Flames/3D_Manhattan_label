"""Building-cluster descriptive bootstrap; never implies external validation.
Uses 50000 resamples of observed building means, seed 20261020. No threshold
optimization, no geometry/native rerun. Also checks common-pair eligibility.
"""
import json
from pathlib import Path
import pandas as pd,numpy as np
B=Path('/workspace/shared/interchangeability_audit_20261020/unpacked/interchangeability_20261020');O=Path(__file__).parent
f=pd.read_csv(B/'core_replay/EXPECTED_PAIRED_EVENTS.csv.gz');out=[];rng=np.random.default_rng(20261020)
for key,g in f.groupby('group'):
 z=g.copy();z['stability_gap']=z.within_joint_stable_main.astype(int)-z.cross_joint_stable_main.astype(int);z['shape_gap']=z.within_geometry_shape_main.astype(int)-z.cross_geometry_shape_main.astype(int)
 for eligibility,zz in [('all_attempts',z),('ABC_complete',z[z.A_complete&z.B_complete&z.C_complete])]:
  met=['net_B8L2_change','within_joint_stable_main','stability_gap','within_geometry_shape_main','shape_gap'];b=zz.groupby(['building','image'])[met].mean().groupby('building').mean()
  for col in met:
   x=b[col].dropna().to_numpy();dist=x[rng.integers(0,len(x),(50000,len(x)))].mean(axis=1)
   out.append(dict(group=key,eligibility=eligibility,metric=col,events=len(zz),finite_events=int(zz[col].notna().sum()),images=zz.image.nunique(),buildings=len(x),estimate=x.mean(),bootstrap_2_5=np.quantile(dist,.025),bootstrap_97_5=np.quantile(dist,.975),building_min=x.min(),building_max=x.max()))
pd.DataFrame(out).to_csv(O/'BUILDING_BOOTSTRAP_DESCRIPTIVE.csv',index=False)
counts=[]
for key,g in f.groupby('group'):
 counts.append(dict(group=key,attempts=len(g),A_failed=int((~g.A_complete).sum()),B_failed=int((~g.B_complete).sum()),C_failed=int((~g.C_complete).sum()),ABC_complete=int((g.A_complete&g.B_complete&g.C_complete).sum()),BC_score_available=int(g.net_B8L2_change.notna().sum()),within_pass=int(g.within_joint_stable_main.sum()),cross_pass=int(g.cross_joint_stable_main.sum())))
pd.DataFrame(counts).to_csv(O/'RAW_FAILURE_DENOMINATORS.csv',index=False)
print(pd.DataFrame(out).query("group in ['F01_time','Rnew2_C02>C01_m5','mixed_highQ23_5fast_2slow'] and eligibility == 'all_attempts'").to_string(index=False))
