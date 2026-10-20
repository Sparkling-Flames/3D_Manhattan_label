import os
os.environ.setdefault('MPLCONFIGDIR','/tmp/corner_matplotlib');os.environ.setdefault('XDG_CACHE_HOME','/tmp/corner_cache')
from pathlib import Path
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
P=Path(__file__).resolve().parent/'common_library';f=pd.read_csv(P/'COMMON_LIBRARY_SUMMARY.csv');f=f[f.subset.eq('all_count_vectors')]
fig,axs=plt.subplots(2,3,figsize=(13,8))
for i,m in enumerate([2,5]):
 for j,(metric,field,title) in enumerate([('bev_mean_h','within','Within-composition BEV mean / h'),('bev_mean_h','gap','Between minus within BEV mean / h'),('different_count','within','Verified changed-count rate, all anchors')]):
  ax=axs[i,j];g=f[(f.m==m)&f.metric.eq(metric)].sort_values('n')
  for method,label,color in [('candidate','New mean-K3','#087f8c'),('baseline','Existing Rnew2','#d97706')]:ax.plot(g.n,g[method+'_'+field],marker='o',label=label,color=color)
  for r in g.itertuples():ax.annotate(f'{r.common_anchors} anchors', (r.n,getattr(r,'candidate_'+field)),xytext=(0,8),textcoords='offset points',ha='center',fontsize=7)
  if field=='gap':ax.axhline(0,color='gray',lw=.7)
  else:ax.set_ylim(bottom=0)
  ax.set_xticks([5,9,13,17]);ax.set_xlabel('Total team n');ax.set_title(f'm={m}: {title}',fontsize=10);ax.grid(alpha=.2)
axs[0,0].legend(fontsize=9)
fig.suptitle('Shared endpoints: exploratory block-composition comparison\nDistance uses per-metric four-cell common anchors; risks use all-observed common anchors',fontsize=12)
fig.text(.02,.01,'m=5 has only 5–6 distance-common anchors (4–5 images): no broad ranking. Same vector is not necessarily a pure-class block.',fontsize=9)
fig.tight_layout(rect=[0,.035,1,.91]);fig.savefig(P/'shared_library_comparison.png',dpi=160);plt.close(fig)
