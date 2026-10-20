"""Static research figures from the saved image/building-level small tables."""
from pathlib import Path
import argparse
import os

os.environ.setdefault('MPLCONFIGDIR','/tmp/hohonet_quality_plot_config')

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from analyze_high_low import delta_summary,bmean
import high_low_study as hs


def plot(out):
    out=Path(out);figdir=out/'figures';figdir.mkdir(exist_ok=True)
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.spines.top':False,
                         'axes.spines.right':False,'savefig.facecolor':'white'})
    data=pd.read_csv(out/'composition_effects.csv')
    layers=[('ordinary_manual','Manual | ordinary'),('ordinary_semi','Semi | ordinary'),('doorway_manual','Manual | doorway')]
    common=pd.read_csv(out/'source_common_image_comparison.csv')
    fig,axes=plt.subplots(2,3,figsize=(14,8.6),sharey=True)
    for j,(layer,title) in enumerate(layers):
        g=data[(data.layer==layer)&(data.phase=='all')&(data.n==7)&(data.baseline=='pure_H')]
        for i,(source,color,label) in enumerate([('all_supported','#156a9d','All eligible origins'),('new_only','#c77a10','New cohort only')]):
            ax=axes[i,j]
            s=g[g.source_policy==source].sort_values('H')
            if s.empty:continue
            ax.plot(s.H,s['mean'],marker='o',color=color,label=label,lw=2)
            ax.fill_between(s.H,s.cluster_CI_low,s.cluster_CI_high,color=color,alpha=.12)
            n=int(s.images.max());b=int(s.buildings.max())
            ax.text(.02,.04,f'{n} attempted images / {b} buildings',transform=ax.transAxes,fontsize=8)
            if source=='new_only':
                c=common[(common.layer==layer)&(common.phase=='all')&(common.baseline=='pure_H')].sort_values('H')
                ax.plot(c.H,c.all_d_B8L2,'--',color='#156a9d',lw=1.7,label='All origins on these same images')
            ax.axhspan(-2,0,color='#50a273',alpha=.10)
            ax.axhline(0,color='#333333',lw=.9)
            ax.axhline(-2,color='#638367',lw=.7,ls=':')
            ax.set_xticks(range(8));ax.set_xlabel('H workers in a 7-person team')
            ax.set_title(title+' | '+label);ax.grid(axis='y',alpha=.16)
    for i in range(2):axes[i,0].set_ylabel('B8L2 difference from 7H\n(image then building equal mean)')
    axes[1,2].legend(loc='upper left',fontsize=7)
    fig.suptitle('How much high-Q staffing can be replaced? Historical Q excludes the target building.',fontsize=13)
    fig.text(.065,.01,'H: historical same-task peer residual >= 0; L: < 0. Bands: building bootstrap 95% interval. Paired scored outcomes only; failures remain in separate tables.\nThe lower panels control the image set when comparing source policies. Green band: exploratory 2-point tolerance, not validated visual equivalence.',fontsize=8)
    fig.tight_layout(rect=[0,.08,1,.93]);fig.savefig(figdir/'quality_mix_n7.png',dpi=180);fig.savefig(figdir/'quality_mix_n7.svg');plt.close(fig)

    growth=pd.read_csv(out/'growth_events.csv.gz')
    fig,axes=plt.subplots(2,3,figsize=(14,8),sharex=True,sharey=True)
    plotrows=[]
    for j,(layer,title) in enumerate(layers):
        for i,core in enumerate([3,5]):
            ax=axes[i,j]
            g=growth[(growth.layer==layer)&(growth.core_n==core)&(growth.added_n<=6)]
            counts=g.groupby(['pool_id','replicate','incoming_group']).added_n.nunique().unstack('incoming_group')
            commonkeys=counts[(counts.H==7)&(counts.L==7)].reset_index()[['pool_id','replicate']]
            g=g.merge(commonkeys,on=['pool_id','replicate'],validate='many_to_one')
            for incoming,color,label in [('L','#be6524','Append L'),('H','#156a9d','Append H')]:
                rows=[]
                for add,t in g[g.incoming_group==incoming].groupby('added_n'):
                    r=dict(layer=layer,core_n=core,incoming_group=incoming,added_n=add,images=t.image_id.nunique(),buildings=t.building.nunique(),**delta_summary(t))
                    rows.append(r);plotrows.append(r)
                s=pd.DataFrame(rows).sort_values('added_n')
                if s.empty:continue
                ax.plot(s.added_n,s['mean'],marker='o',color=color,label=label,lw=2)
                ax.fill_between(s.added_n,s.cluster_CI_low,s.cluster_CI_high,color=color,alpha=.10)
            for add in [2,4,6]:ax.axvspan(add-.13,add+.13,color='#7a7390',alpha=.11)
            ax.axhline(0,color='#333333',lw=.8);ax.grid(axis='y',alpha=.15)
            ax.set_title(f'{title} | fixed {core}H core')
            ax.set_xticks(range(0,7))
            ax.text(.02,.04,f'{g.image_id.nunique()} fixed images / {g.building.nunique()} buildings',transform=ax.transAxes,fontsize=8)
            if i==1:ax.set_xlabel('Number of appended workers')
            if j==0:ax.set_ylabel('B8L2 change from the exact core')
    axes[0,-1].legend(fontsize=9)
    fig.suptitle('Adding people to a fixed high-Q core: extra support and dilution',fontsize=14)
    fig.text(.055,.013,'Same exact core and fixed member prefixes; these plotted image sets support both streams through six additions. Full tables retain paths through ten.\nPurple stripes mark even-to-odd team-size transitions: the MV50 vote threshold rises by one. Bands: building bootstrap 95% interval; scored pairs only.',fontsize=8)
    fig.tight_layout(rect=[0,.06,1,.94]);fig.savefig(figdir/'fixed_high_core_growth.png',dpi=175);fig.savefig(figdir/'fixed_high_core_growth.svg');plt.close(fig)
    hs.write_csv(out/'growth_common_plot_data.csv',pd.DataFrame(plotrows))

    cells=pd.read_csv(out/'composition_summary.csv')
    fig,axes=plt.subplots(1,3,figsize=(14,4.6),sharey=True)
    for ax,(layer,title) in zip(axes,layers):
        g=cells[(cells.layer==layer)&(cells.phase=='all')&(cells.source_policy=='all_supported')&(cells.n==7)].sort_values('H')
        ax.plot(g.H,100*(1-g.score_rate),marker='o',color='#a53f37',label='Missing formal score')
        ax.plot(g.H,100*g.low_Q50_rate,marker='s',color='#156a9d',label='B8L2 < 50 | scored')
        ax.set_xticks(range(8));ax.set_xlabel('H workers in a 7-person team');ax.set_title(title)
        ax.grid(axis='y',alpha=.16)
    axes[0].set_ylabel('Image then building equal rate (%)');axes[-1].legend(fontsize=8)
    fig.suptitle('Low-score risk and fusion/measurement unavailability remain separate',fontsize=13)
    fig.text(.065,.01,'The B8L2 < 50 threshold describes the observed score tail; it is not independently labelled serious-error gold.\nMissing outcomes are never assigned zero or removed from availability rates.',fontsize=8)
    fig.tight_layout(rect=[0,.08,1,.94]);fig.savefig(figdir/'quality_tail_and_availability.png',dpi=180);fig.savefig(figdir/'quality_tail_and_availability.svg');plt.close(fig)


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,required=True);args=ap.parse_args();plot(args.out)
