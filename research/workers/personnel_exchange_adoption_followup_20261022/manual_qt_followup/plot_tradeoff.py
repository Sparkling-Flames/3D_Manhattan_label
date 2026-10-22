#!/usr/bin/env python3
from pathlib import Path
import io,os
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

HERE=Path(__file__).resolve().parent
D=pd.read_csv(HERE/'FINITE_POLICIES_COMMON_SUMMARY.csv')
fig,axs=plt.subplots(1,3,figsize=(13.5,4.4))
style={'finite_uniform':('Uniform target blocks','#3b424b','o'),
       'finite_Q':('Highest historical Q','#b77928','s'),
       'finite_QT10':('Historical QT10 (= QT20)','#2564a8','D')}
for ax,m in zip(axs,[3,4,5]):
    panel=D[D.m.eq(m)].set_index('policy')
    r=panel.loc['finite_uniform']
    for policy,(label,color,marker) in style.items():
        p=panel.loc[policy];x=p.delta_logT_geomean_pct;y=p.delta_B8L2
        if policy!='finite_uniform':
            ax.annotate('',xy=(x,y),xytext=(r.delta_logT_geomean_pct,r.delta_B8L2),
                        arrowprops={'arrowstyle':'->','color':color,'lw':1.1,'alpha':0.6})
        ax.scatter(x,y,s=74,c=color,marker=marker,label=label,zorder=3)
        ax.annotate(f'{y:+.2f} Q / {x:+.2f}%',(x,y),xytext=(4,9 if policy!='finite_Q' else -16),
                    textcoords='offset points',fontsize=8.2,color=color)
    ax.set_title(f'n = 20, m = {m}\n{int(r.image_Q_known)} images / {int(r.building_Q_known)} buildings',fontsize=11)
    ax.set_xlabel('Recorded team time change (%)')
    ax.set_ylabel('B8L2 change vs the same original A')
    ax.grid(alpha=.2);ax.spines[['top','right']].set_visible(False)
    ax.margins(x=.4,y=.4)
handles,labels=axs[0].get_legend_handles_labels()
fig.legend(handles,labels,loc='lower center',ncol=3,frameon=False,bbox_to_anchor=(.5,-.005))
fig.suptitle('Within-class selection on the identical frozen candidate reservoir',fontsize=14)
fig.tight_layout(rect=[0,.06,1,.93])
buf=io.BytesIO();fig.savefig(buf,format='png',dpi=180,bbox_inches='tight');plt.close(fig)
tmp=HERE/'FINITE_QT_TRADEOFF.png.tmp'
with tmp.open('wb') as f:f.write(buf.getvalue());f.flush();os.fsync(f.fileno())
tmp.replace(HERE/'FINITE_QT_TRADEOFF.png')
