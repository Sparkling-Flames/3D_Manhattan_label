"""Actual quality/time frontier with all compared methods on identical teams."""
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import TwoSlopeNorm
from prepare_training import HERE,atomic_csv
from summarize_policy import macro_many

STRATEGIES=[
 ('Q','new_joint','history_Q','History Q'),
 ('T','new_joint','history_T','History time'),
 ('QT','new_joint','QT_interaction__balanced','Continuous QT, quadratic'),
 ('OLD','old_structure','class_fine_interaction__balanced','Old M/SP fine class, quadratic'),
 ('BEH','new_behavior','class_fine_interaction__balanced','New behavior fine class, quadratic'),
 ('JOINT','new_joint','class_fine_interaction__balanced','Joint class, quadratic'),
 ('EXACT','new_joint','exact_continuous_interaction__balanced','Exact joint inputs, continuous quadratic'),
 ('EX+CL','new_joint','exact_continuous_interaction_class_fine__balanced','Exact continuous + joint class')]

def main():
    points=[];supports=[]
    for condition in ['manual','semi']:
        data={family:pd.read_csv(HERE/'cross_panel_LOBO'/condition/family/'PANEL_POLICY_RESULTS.csv.gz',low_memory=False)
              for family in ['old_structure','new_behavior','new_joint']}
        anchor=data['new_joint'];anchor=anchor[anchor.policy.eq('ordinary_uniform')].copy()
        ok=set(anchor.loc[anchor.all_candidates_time_compatible,'panel_id'])
        for family,d in data.items():
            candidate=d[d.policy.eq('ordinary_uniform')][['panel_id','candidate_support_sha256']]
            z=anchor[['panel_id','candidate_support_sha256']].merge(candidate,on='panel_id',suffixes=('_a','_b'))
            ok &= set(z.loc[z.candidate_support_sha256_a.eq(z.candidate_support_sha256_b),'panel_id'])
        supports.append(anchor[anchor.panel_id.isin(ok)][['condition','panel_id','building','image','n','source_domain','common_candidates','candidate_support_sha256']])
        for code,family,policy,label in STRATEGIES:
            d=data[family];d=d[d.panel_id.isin(ok)&d.policy.eq(policy)]
            assert set(d.panel_id)==ok
            stats,_=macro_many(d,['delta_B8L2','time_percent_vs_uniform','failure_delta_pp'])
            row=dict(condition=condition,code=code,family=family,policy=policy,label=label)
            for metric,details in stats.items():
                row.update({metric+'_'+k:v for k,v in details.items()})
            points.append(row)
    d=pd.DataFrame(points);atomic_csv(d,HERE/'POLICY_FRONTIER_POINTS.csv')
    atomic_csv(pd.concat(supports,ignore_index=True),HERE/'POLICY_FRONTIER_SHARED_PANELS.csv')
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.spines.top':False,'axes.spines.right':False})
    fig,axes=plt.subplots(1,2,figsize=(12.6,6.2),sharex=True,sharey=True,layout='constrained')
    scale=max(1,float(d.failure_delta_pp_mean.abs().max()))
    norm=TwoSlopeNorm(vmin=-scale,vcenter=0,vmax=scale)
    for ax,condition in zip(axes,['manual','semi']):
        z=d[d.condition.eq(condition)]
        ax.axvline(0,color='#777777',linewidth=.7);ax.axhline(0,color='#777777',linewidth=.7)
        for i,r in enumerate(z.itertuples()):
            ax.errorbar(r.time_percent_vs_uniform_mean,r.delta_B8L2_mean,
                xerr=[[max(0,r.time_percent_vs_uniform_mean-r.time_percent_vs_uniform_low95)],[max(0,r.time_percent_vs_uniform_high95-r.time_percent_vs_uniform_mean)]],
                yerr=[[max(0,r.delta_B8L2_mean-r.delta_B8L2_low95)],[max(0,r.delta_B8L2_high95-r.delta_B8L2_mean)]],
                fmt='none',ecolor='#a7b0bb',alpha=.5,linewidth=.75,zorder=1)
            scatter=ax.scatter(r.time_percent_vs_uniform_mean,r.delta_B8L2_mean,c=[r.failure_delta_pp_mean],
                cmap='coolwarm',norm=norm,s=64,edgecolors='black',linewidths=.55,zorder=3)
            if condition=='manual':
                offset={'Q':(6,-8),'T':(6,-15),'QT':(-10,13),'OLD':(8,21),
                        'BEH':(11,-18),'JOINT':(-40,-16),'EXACT':(9,12),'EX+CL':(9,-15)}[r.code]
            else:offset=(5,8) if i%2==0 else (5,-12)
            ax.annotate(r.code,(r.time_percent_vs_uniform_mean,r.delta_B8L2_mean),xytext=offset,textcoords='offset points',fontsize=8,
                        arrowprops=dict(arrowstyle='-',color='#777777',lw=.55) if condition=='manual' else None)
        support=pd.concat(supports);support=support[support.condition.eq(condition)]
        ax.set_title(f'{condition.title()}: {support.panel_id.nunique()} panels / {support.image.nunique()} images / {support.building.nunique()} buildings')
        ax.set_xlabel('Actual total recorded time vs uniform teams (%)')
        ax.grid(alpha=.18)
    axes[0].set_ylabel('Success-conditional B8L2 change vs uniform teams (points)')
    fig.colorbar(scatter,ax=axes,shrink=.7,label='Complete failure change (percentage points)')
    handles=[plt.Line2D([],[],marker='o',linestyle='None',color='#555555',markersize=5) for _ in STRATEGIES]
    fig.legend(handles,[code+': '+label for code,_,_,label in STRATEGIES],
        loc='outside lower center',ncol=2,fontsize=8,frameon=False)
    fig.suptitle('Actual team choice on identical finite candidate sets',fontweight='bold',fontsize=14)
    fig.savefig(HERE/'FIGURE_POLICY_UTILITY_SHARED_SUPPORT.png',dpi=220)
    fig.savefig(HERE/'FIGURE_POLICY_UTILITY_SHARED_SUPPORT.svg')
    plt.close(fig)

if __name__=='__main__':main()
