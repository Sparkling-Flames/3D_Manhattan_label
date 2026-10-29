"""Scientific summary figure: class composition separates different outputs."""
from pathlib import Path
import numpy as np,pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

W=Path(__file__).resolve().parents[2];O=W/'composition/primary_mixture_results'
d=pd.read_csv(O/'ALL45_SHARED_KNOWN_METRIC_MATRIX.csv').set_index('method')
cols=['B8L2','D10','fusion_turn_n','geometry_area_h2','height_mean_h','failure',
      'recorded_time_total_seconds__user_processed_reported_not_raw_log_replayed']
names=['Q','D10','Turns','Floor area','Height','Failure','Recorded time\n(source-specific)']
groups=[('Structure',lambda x:x.startswith(('DSTRUCT','OPPSTRUCT'))),
 ('Boundary / geometry',lambda x:x.startswith(('DBOUNDARY','OPPGEOM'))),
 ('Joint / across-condition',lambda x:x.startswith(('DJOINT','OPPJOINT','MSDGEOM'))),
 ('Fusion response / admitted targets',lambda x:x.startswith(('RFUSE','TARGET_'))),
 ('V3 / quality baseline',lambda x:x.startswith(('V3_','Q_')))]
methods=[];ends=[]
for title,keep in groups:
 methods.extend([x for x in d.index if keep(x)]);ends.append((len(methods),title))
assert len(methods)==45 and len(set(methods))==45
v=d.loc[methods,cols].to_numpy(float)*100
fig,ax=plt.subplots(figsize=(10.4,15.3))
im=ax.imshow(v,cmap='Blues',vmin=0,vmax=max(50,float(np.nanmax(v))),aspect='auto')
ax.set_xticks(range(len(cols)),names,fontsize=10);ax.xaxis.tick_top();ax.tick_params(axis='x',length=0,pad=8)
ax.set_yticks(range(len(methods)),methods,fontsize=9);ax.tick_params(axis='y',length=0)
for i in range(len(methods)):
 for j in range(len(cols)):
  val=v[i,j];ax.text(j,i,'NA' if np.isnan(val) else f'{val:.1f}',ha='center',va='center',fontsize=8,
   color='white' if val>im.norm.vmax*.6 else '#163752')
for n,_ in ends[:-1]:ax.axhline(n-.5,color='#425b76',lw=1.1)
for s in ax.spines.values():s.set_visible(False)
cb=fig.colorbar(im,ax=ax,fraction=.025,pad=.025,shrink=.63)
cb.set_label('Between-composition share of total variance (%)',fontsize=10)
fig.suptitle('Manual v2.1: 45 frozen personnel classifications',y=.99,x=.58,fontsize=16,weight='bold')
fig.text(.57,.958,'Same finite member sets: 182 panels, 38 images, 22 buildings\n'
 'Complete class-count vectors; fixed background + 12 choose 6 members',ha='center',va='top',fontsize=10,color='#475569')
fig.text(.04,.012,'Variances are averaged panel → target → image → building before division.\n'
 'These shares describe mixtures; they are neither Q gains nor percentages of labor saved.',fontsize=10,color='#475569')
fig.subplots_adjust(left=.32,right=.93,top=.90,bottom=.055)
fig.savefig(O/'ALL45_COMPOSITION_VARIANCE.png',dpi=170)
fig.savefig(O/'ALL45_COMPOSITION_VARIANCE.svg')
plt.close(fig)
print({'methods':45,'metrics':len(cols),'output':str(O)})
