import os
os.environ.setdefault('MPLCONFIGDIR','/tmp/corner_matplotlib');os.environ.setdefault('XDG_CACHE_HOME','/tmp/corner_cache')
from pathlib import Path
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
P=Path(__file__).resolve().parent/'discovery_evaluation'
f=pd.read_csv(P/'DISCOVERY_BUILDINGS.csv')
for metric in ['bev_mean_h','bev_max_h','top_mean_h','top_max_h']:
 fig,axes=plt.subplots(2,3,figsize=(13,8))
 for ax,(mid,g) in zip(axes.flat,f.groupby('method_id')):
  for r in g.itertuples():ax.plot([0,1],[getattr(r,'within_'+metric),getattr(r,'between_'+metric)],marker='o',alpha=.6,lw=1)
  ax.plot([0,1],[g['within_'+metric].mean(),g['between_'+metric].mean()],marker='D',lw=3,color='black')
  ax.set_title(mid.replace('C_corner_','').replace('__new__legacy',''));ax.set_xticks([0,1],['Within','Between']);ax.set_ylim(bottom=0);ax.grid(alpha=.2);ax.set_ylabel(metric+' / camera h')
 fig.suptitle('Frozen history-only candidates: discovery exact-background m=1 replacements\nLines: six buildings; black: equal-building mean; no fitted nearness threshold')
 fig.tight_layout(rect=[0,0,1,.91]);fig.savefig(P/(metric+'_discovery.png'),dpi=150);plt.close(fig)
