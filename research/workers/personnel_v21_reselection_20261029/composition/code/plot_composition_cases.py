"""All configurations of four explanatory finite-panel cases; no cell selection."""
from pathlib import Path
import os
os.environ.setdefault('MPLCONFIGDIR','/tmp/hohonet_v21_mpl')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import pandas as pd,numpy as np
W=Path(__file__).resolve().parents[2];o=W/'composition/stage03A_other_targets'
c=pd.read_csv(o/'REPRESENTATIVE_ALL_CONFIGURATIONS.csv');d=pd.read_csv(o/'REPRESENTATIVE_CONFIGURATION_DISTRIBUTIONS.csv.gz');meta=pd.read_csv(o/'REPRESENTATIVE_CASES.csv')
titles={'structure_composition':'rPc-06 | other target | n=5 | DSTRUCT K3',
 'within_composition_risk':'wc2-26 | other target | n=6 | DSTRUCT K3',
 'same_coarse_different_members':'e9z-17 | other target | n=3 | DSTRUCT K3',
 'fine_partition_small_absolute_effect':'uNb-68 | Semi other target | n=3 | own fine roles'}
fig,axs=plt.subplots(2,2,figsize=(13,8),layout='constrained')
for ax,r in zip(axs.flat,meta.itertuples()):
 x=c[c.case_id.eq(r.case_id)].copy();q=d[d.case_id.eq(r.case_id)&d.metric.eq('B8L2')][['class_counts','mean','p05','p95','minimum','maximum','valid_teams','sd']]
 x=x.merge(q,on='class_counts');x=x.sort_values('class_counts').reset_index(drop=True)
 at=np.arange(len(x));ax.vlines(at,x.minimum,x.maximum,color='#94a3b8',lw=1.3,label='Full scored member range')
 ax.vlines(at,x.p05,x.p95,color='#2563eb',lw=5,alpha=.6,label='5th–95th member percentiles')
 ax.scatter(at,x['mean'],color='#0f172a',s=35,zorder=3,label='Configuration mean')
 labels=['/'.join(p.split(':')[1] for p in s.split('|')) for s in x.class_counts]
 ax.set_xticks(at,labels,rotation=30 if len(x)>3 else 0,ha='right' if len(x)>3 else 'center')
 for i,z in x.iterrows():
  text=f'{z.scorable_teams}/{z.teams}'
  if z.failed_teams:text+=f'\n{z.failed_teams} fail'
  ax.annotate(text,(i,z.maximum),xytext=(0,9),textcoords='offset points',ha='center',fontsize=7.5,color='#9a3412' if z.failed_teams else '#475569')
 if r.case_id=='fine_partition_small_absolute_effect':ax.set_ylim(98.9,100.25)
 else:ax.set_ylim(0,108)
 ax.set_xlim(-.6,len(x)-.4);ax.set_title(titles[r.case_id],fontsize=10.5,loc='left',weight='bold')
 ax.set_ylabel('Q (B8L2)');ax.set_xlabel(' / '.join(v.split(':')[0] for v in x.class_counts.iloc[0].split('|'))+' seats');ax.grid(axis='y',alpha=.2)
 if r.case_id=='same_coarse_different_members':ax.text(.97,.06,'Same class composition,\ndifferent actual members',transform=ax.transAxes,ha='right',fontsize=10,color='#0f172a')
 if r.case_id=='fine_partition_small_absolute_effect':ax.text(.97,.06,'Zoomed Q axis: entire range < 0.74',transform=ax.transAxes,ha='right',fontsize=9,color='#0f172a')
handles,labels=axs[0,0].get_legend_handles_labels();fig.legend(handles,labels,loc='outside lower center',ncol=3,frameon=False,fontsize=9)
fig.suptitle('Finite complete panels: composition differences and member variation',fontsize=15,weight='bold')
fig.savefig(o/'COMPLETE_CONFIGURATION_CASES.png',dpi=180);fig.savefig(o/'COMPLETE_CONFIGURATION_CASES.svg');plt.close(fig)
