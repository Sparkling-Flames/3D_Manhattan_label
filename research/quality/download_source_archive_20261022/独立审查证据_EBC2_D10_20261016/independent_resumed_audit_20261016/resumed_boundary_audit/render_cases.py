from pathlib import Path
import json,sys
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
D=Path(__file__).resolve().parent;c=json.load(open(D/'audit_cases.json'))
fig,ax=plt.subplots(1,3,figsize=(14,4.5),gridspec_kw={'width_ratios':[1,1,1.3]})
for k,(name,title) in enumerate([('serration_baseline','Baseline: Q = 66.0193'),('serration_n400_step1over1','Added teeth: Q = 72.3419')]):
 a=np.array(c[name]['answer']['bottom3d'])[:,[0,2]];r=np.array(c[name]['reference']['bottom3d'])[:,[0,2]]
 ax[k].fill(r[:,0],r[:,1],color='#b5d7ee',alpha=.5,label='Fixed reference')
 ax[k].fill(a[:,0],a[:,1],color='#d6d6d6',alpha=.7,label='Answer')
 ax[k].plot(*np.vstack([r,r[0]]).T,color='#22658e',ls='--',lw=2)
 ax[k].plot(*np.vstack([a,a[0]]).T,color='#b23b26',lw=.8)
 ax[k].set_aspect('equal');ax[k].set_xlim(-2.3,2.3);ax[k].set_ylim(-2.3,2.3);ax[k].set_title(title);ax[k].set_xlabel('x / h_cam');ax[k].set_ylabel('z / h_cam')
 ax[k].legend(loc='upper left',fontsize=8)
a=np.array(c['serration_n400_step1over1']['answer']['bottom3d'])[:,[0,2]]
ax[2].plot(*a.T,color='#b23b26',lw=1);ax[2].axhline(-2,color='#22658e',ls='--',lw=2)
ax[2].set_xlim(-.05,.05);ax[2].set_ylim(-2.006,-1.95);ax[2].set_title('Zoom: added error near correct wall')
ax[2].set_xlabel('x / h_cam');ax[2].set_ylabel('z / h_cam')
fig.suptitle('Perimeter dilution: the original large omission is unchanged; IoU gets worse',fontsize=13)
fig.tight_layout();fig.savefig(D/'serration_counterexample.png',dpi=180)
