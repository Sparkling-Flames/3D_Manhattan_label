"""Descriptive empirical tolerance curves; all observations, no selected cutoff."""
from pathlib import Path
import json,hashlib
import numpy as np,pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
R=Path(__file__).resolve().parent.parent;O=R/'audit_statistics/tolerance';O.mkdir(exist_ok=True)
rows=[];coverage=[];quant=[];inputs={}
metrics=['bev_max_h','top_max_h','bev_max_local_radius_fraction','top_max_local_radius_fraction']
for panel in ['core','fresh_blocks']:
 p=R/'audit_corner'/panel/'CORNER_EVENTS.csv.gz';inputs[panel]=hashlib.sha256(p.read_bytes()).hexdigest();e=pd.read_csv(p)
 if panel=='core':groups=[('core_'+str(k),g) for k,g in e.groupby('replay_group') if k in ['Rnew2_C02>C01_m5','Rnew2_C01>C02_m5','old_G_anchor','old_R_anchor','F01_time']]
 else:groups=[('fresh_'+str(mid).split('__')[0]+'_'+str(di)+'_m'+str(m),g) for (mid,di,m),g in e[e.k.eq(13)].groupby(['method_id','direction','m'])]
 for name,g in groups:
  both=g.within_status.eq('unique_cyclic_candidate')&g.cross_status.eq('unique_cyclic_candidate')
  for arm in ['within','cross']:
   coverage.append(dict(panel=panel,role=name,arm=arm,attempts=len(g),images=g.image.nunique(),buildings=g.building.nunique(),complete=int(g[arm+'_complete'].sum()),same_count=int(g[arm+'_same_count'].sum()),available=int(g[arm+'_status'].eq('unique_cyclic_candidate').sum()),paired_common=int(both.sum()),status_counts=json.dumps(g[arm+'_status'].value_counts().to_dict())))
  fig,ax=plt.subplots(2,2,figsize=(10,7))
  for gate in ['all_common','angle_le_9','angle_le_12']:
   z=g[both].copy()
   if gate!='all_common':z=z[(z.within_angle_deg<=int(gate.split('_')[-1]))&(z.cross_angle_deg<=int(gate.split('_')[-1]))]
   if z.empty:continue
   # Each building equally weighted, images equally within building, events equally within image.
   n=z.groupby(['building','image']).event_id.transform('size');ni=z.groupby('building').image.transform('nunique');w=1/(z.building.nunique()*ni*n);assert abs(w.sum()-1)<1e-12
   for j,metric in enumerate(metrics):
    xx=np.unique(np.r_[0,z['within_'+metric],z['cross_'+metric]])
    for arm in ['within','cross']:
     v=z[arm+'_'+metric].to_numpy();order=np.argsort(v);vs=v[order];cw=np.cumsum(w.to_numpy()[order]);ix=np.searchsorted(vs,xx,side='right');y=np.where(ix>0,cw[np.maximum(ix-1,0)],0)
     for x,yy in zip(xx,y):rows.append(dict(panel=panel,role=name,gate=gate,metric=metric,arm=arm,tolerance=x,fraction_le=yy,paired_events=len(z),images=z.image.nunique(),buildings=z.building.nunique()))
     quant.append(dict(panel=panel,role=name,gate=gate,metric=metric,arm=arm,weighted_median=vs[np.searchsorted(cw,.5)],weighted_p90=vs[min(np.searchsorted(cw,.9),len(vs)-1)],weighted_p95=vs[min(np.searchsorted(cw,.95),len(vs)-1)],max=vs[-1]))
     if gate=='all_common':ax.flat[j].step(xx,y,where='post',label=arm);ax.flat[j].set(title=metric,xlim=(0,xx[-1]*1.02 if xx[-1]>0 else 1),ylim=(0,1.02),ylabel='Building-weighted fraction ≤ tolerance');ax.flat[j].legend()
  fig.suptitle(name+'\nPaired common subset; full observed axis, no fitted threshold',fontsize=10);fig.tight_layout();fig.savefig(O/(name.replace('>','to')+'.png'),dpi=140);plt.close(fig)
pd.DataFrame(rows).to_csv(O/'EMPIRICAL_TOLERANCE_CDF.csv.gz',index=False);pd.DataFrame(coverage).to_csv(O/'ALL_ATTEMPT_COVERAGE.csv',index=False);pd.DataFrame(quant).to_csv(O/'WEIGHTED_DISTANCE_QUANTILES.csv',index=False)
(O/'RECEIPT.json').write_text(json.dumps(dict(inputs=inputs,cdf_rows=len(rows),coverage_rows=len(coverage),rule='Empirical thresholds at every pooled observed within/cross value. Equal building, then image, then event. Paired common subset with 9/12 degree sensitivity. Full observed axis, no threshold optimized. Fresh panel uses n13 only, whole-path evidence separate. Coverage retains every attempted event.'),indent=2))
print(len(rows),len(coverage))
