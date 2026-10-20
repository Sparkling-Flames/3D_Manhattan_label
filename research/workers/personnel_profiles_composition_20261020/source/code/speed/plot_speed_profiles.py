"""Plot frozen speed-study summaries and describe held-building-out difficulty history.

No fusion, scoring, participant selection, or frozen LOBO features are modified.
Run: OPENBLAS_NUM_THREADS=1 python plot_speed_profiles.py --speed DIR --profiles DIR --font FONT
"""
from pathlib import Path
import argparse, gzip, json
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties, fontManager

ap=argparse.ArgumentParser()
ap.add_argument('--speed',type=Path,default=Path(__file__).parent)
ap.add_argument('--profiles',type=Path,default=Path(__file__).parent.parent/'profiles')
ap.add_argument('--font',type=Path,default=Path(__file__).parent.parent/'mechanisms/NotoSansSC-Regular-full.ttf')
a=ap.parse_args(); out=a.speed
fontManager.addfont(str(a.font)); fn=FontProperties(fname=str(a.font)).get_name()
plt.rcParams.update({'font.family':fn,'axes.unicode_minus':False,'font.size':10,'axes.spines.top':False,'axes.spines.right':False,'figure.facecolor':'white','savefig.facecolor':'white'})
d=pd.read_csv(out/'main_summary.csv')
s=d[(d.layer.isin(['ordinary_manual','ordinary_semi']))&(d.contrast=='versus_slow')].copy()
colors={'allQ':'#146C94','above_peer_Q':'#CF6B35'}
fig,axes=plt.subplots(2,2,figsize=(12.3,8.1),sharex='col',gridspec_kw={'height_ratios':[1.2,1]})
for col,condition in enumerate(['manual','semi']):
    sub=s[(s.origin=='new')&(s.condition==condition)&(s.n==5)]
    for domain,g in sub.groupby('domain',sort=False):
        g=g.sort_values('n_fast'); color=colors[domain]
        x=np.r_[0,g.n_fast]; q=np.r_[0,g.quality_difference]; t=np.r_[1,g.source_time_ratio]
        label=('全部历史Q' if domain=='allQ' else '历史相对Q≥0')+f'（{int(g.images.iloc[0])}图/{int(g.buildings.iloc[0])}楼）'
        axes[0,col].plot(x,q,'o-',color=color,label=label,lw=2)
        lo=g.quality_difference_ci_low.to_numpy(); hi=g.quality_difference_ci_high.to_numpy()
        axes[0,col].fill_between(g.n_fast,lo,hi,color=color,alpha=.13)
        axes[1,col].plot(x,t,'o-',color=color,lw=2)
        for n in [4,5]:
            r=g[g.n_fast==n].iloc[0]
            dy=10 if domain=='allQ' else -19
            axes[0,col].annotate(f'{r.quality_difference:+.2f}',(n,r.quality_difference),xytext=(0,dy),textcoords='offset points',ha='center',color=color,fontweight='bold')
            axes[1,col].annotate(f'{r.source_time_ratio:.3f}',(n,r.source_time_ratio),xytext=(-3,9 if domain=='allQ' else -17),textcoords='offset points',ha='center',color=color)
    axes[0,col].set_title(('Manual' if condition=='manual' else 'Semi')+'｜新批、普通图、5人',loc='left',fontweight='bold')
    axes[0,col].axhline(0,color='#777777',lw=.8);axes[0,col].axhline(-2,color='#777777',ls=':',lw=.8)
    axes[0,col].set_ylabel('B8L2 变化（分，相对5名慢者）')
    axes[0,col].legend(fontsize=9,loc='lower left',frameon=False)
    axes[1,col].set_ylabel('总劳动时间比（相对5名慢者）')
    axes[1,col].set_ylim(.23,1.08);axes[1,col].set_xticks(range(6),['0快5慢','1快4慢','2快3慢','3快2慢','4快1慢','5快0慢'],rotation=18)
    for ax in axes[:,col]: ax.grid(axis='y',alpha=.17)
axes[0,1].text(.03,.97,'该域历史相对Q≥0配对人数不足，\n没有5人实验',transform=axes[0,1].transAxes,va='top',fontsize=9,color='#666666')
fig.suptitle('快慢混合的主要价值是省工；质量收益取决于人员域与图片条件',fontsize=15,fontweight='bold',x=.07,ha='left')
fig.text(.07,.035,'每对人员历史Q差≤3分、历史速度差≥1.5倍；选人排除目标建筑。阴影为按建筑重采样95%区间。\n先在同图内汇总，再按建筑等权；时间为来源一致的活动/报告耗时之和。图中0快5慢为比较基准。',fontsize=9,color='#555555')
fig.subplots_adjust(left=.085,right=.98,top=.9,bottom=.15,wspace=.22,hspace=.12)
fig.savefig(out/'speed_n5_quality_labor.png',dpi=190);plt.close(fig)

z=s[(s.domain=='allQ')&(s.n_fast==s.n-1)]
fig,axes=plt.subplots(2,2,figsize=(12.3,8.3),sharex='col',gridspec_kw={'height_ratios':[1.25,1]})
for col,condition in enumerate(['manual','semi']):
    for origin,g in z[z.condition==condition].groupby('origin',sort=False):
        g=g.sort_values('n'); color='#146C94' if origin=='new' else '#8C5C99';style='-' if origin=='new' else '--'
        label='新批：统一报告时间语义' if origin=='new' else '旧批：原审计活动时间语义'
        axes[0,col].plot(g.n,g.quality_difference,style,color=color,lw=1.7,label=label)
        axes[1,col].plot(g.n,g.source_time_ratio,style,color=color,lw=1.7)
        for _,r in g.iterrows():
            marker='o' if int(r.n)%2 else 's'
            axes[0,col].scatter(r.n,r.quality_difference,marker=marker,c=color,s=40,zorder=3)
            axes[1,col].scatter(r.n,r.source_time_ratio,marker=marker,c=color,s=40,zorder=3)
            if np.isfinite(r.quality_difference_ci_low):
                axes[0,col].vlines(r.n+(-.04 if origin=='new' else .04),r.quality_difference_ci_low,r.quality_difference_ci_high,color=color,alpha=.32,lw=1)
            axes[1,col].annotate(f'{int(r.images)}/{int(r.buildings)}',(r.n,r.source_time_ratio),xytext=(0,10 if origin=='new' else -16),textcoords='offset points',ha='center',fontsize=8,color=color)
    axes[0,col].set_title(('Manual' if condition=='manual' else 'Semi')+'｜全部历史Q、普通图',loc='left',fontweight='bold')
    axes[0,col].axhline(0,color='#777777',lw=.8);axes[0,col].axhline(-2,color='#777777',ls=':',lw=.8)
    axes[0,col].set_ylabel('B8L2 变化（分，相对同人数纯慢）');axes[0,col].legend(fontsize=8.5,frameon=False,loc='lower left')
    axes[1,col].set_ylabel('总劳动时间比');axes[1,col].set_xlabel('团队人数 n；每队保留1名慢者，其余为快者')
    axes[1,col].set_xticks(range(3,10));axes[1,col].set_ylim(.25,.72)
    for ax in axes[:,col]:ax.grid(axis='y',alpha=.17)
fig.suptitle('一名慢者方案：Manual省工覆盖较宽；Semi大队伍出现质量损失',fontsize=15,fontweight='bold',x=.07,ha='left')
fig.text(.07,.035,'圆点=奇数人数；方点=偶数人数。时间点旁数字为图片数/建筑数；无点表示该来源没有该人数实验。\n竖线为建筑重采样95%区间。不同 n 可用图片集合不同，曲线不能独立证明人数或奇偶的因果效应。旧批时间只汇总有真实时间的成对团队。',fontsize=9,color='#555555')
fig.subplots_adjust(left=.085,right=.98,top=.9,bottom=.14,wspace=.22,hspace=.1)
fig.savefig(out/'speed_sizes_sources.png',dpi=190);plt.close(fig)

# New descriptive join: actual frozen n=5 panels to prior difficulty performance.
h=pd.read_csv(a.profiles/'lobo_difficulty_features.csv')
h=h[h.panel=='ordinary'].set_index(['target_building','worker_id','condition','origin'])
panels=json.load(gzip.open(out/'panels.json.gz','rt'))
rows=[]
for p in panels:
    if p['layer']!='ordinary_manual' or p['origin']!='new' or p['n']!=5: continue
    for i,pair in enumerate(p['pairs']):
        r={k:p[k] for k in ['panel_id','image_id','building','domain','difficulty','replicate','member_stage']}
        r.update(pair_index=i,fast=pair['fast'],slow=pair['slow'],overall_Q_gap=pair['fast_Q_peer']-pair['slow_Q_peer'])
        for arm in ['fast','slow']:
            v=h.loc[(p['building'],pair[arm],'manual','new')]
            for field in ['hard_n','hard_buildings','hard_Q_mean','hard_Q_peer','hard_minus_easy_peer']:
                r[arm+'_'+field]=v[field]
        for field in ['hard_Q_mean','hard_Q_peer','hard_minus_easy_peer']:r[field+'_gap']=r['fast_'+field]-r['slow_'+field]
        rows.append(r)
hist=pd.DataFrame(rows)
hist.to_csv(out/'speed_n5_historical_difficulty_pairs.csv',index=False)
hist_rows=[]
metrics=['overall_Q_gap','hard_Q_mean_gap','hard_Q_peer_gap','hard_minus_easy_peer_gap','fast_hard_n','slow_hard_n','fast_hard_buildings','slow_hard_buildings']
for domain,g in hist.groupby('domain'):
    for subset in ['全部目标图','困难目标图']:
        u=g if subset=='全部目标图' else g[g.difficulty=='困难']
        v=u.groupby(['building','image_id','panel_id'])[metrics].mean().groupby(['building','image_id']).mean().groupby('building').mean()
        hist_rows.append(dict(domain=domain,target_subset=subset,images=u.image_id.nunique(),buildings=u.building.nunique(),panels=u.panel_id.nunique(),pair_draws=len(u),**v.mean().to_dict()))
pd.DataFrame(hist_rows).to_csv(out/'speed_n5_historical_difficulty_summary.csv',index=False)
# Compare the two worker domains on the same available target images.
paired=pd.read_csv(out/'paired_comparisons.csv.gz',usecols=['layer','origin','domain','n','n_fast','contrast','building','image_id','quality_difference','base_Q','candidate_Q','log_source_time_ratio','corner_recall_difference'])
paired=paired[(paired.layer=='ordinary_manual')&(paired.origin=='new')&(paired.n==5)&paired.n_fast.isin([4,5])&(paired.contrast=='versus_slow')]
common=set(paired[paired.domain=='above_peer_Q'].image_id)
common_rows=[]
for (domain,nfast),g in paired[paired.image_id.isin(common)].groupby(['domain','n_fast']):
    v=g.groupby(['building','image_id'])[['quality_difference','base_Q','candidate_Q','log_source_time_ratio','corner_recall_difference']].mean().groupby('building').mean().mean()
    r=dict(domain=domain,n_fast=nfast,images=g.image_id.nunique(),buildings=g.building.nunique(),**v.to_dict())
    r['source_time_ratio']=np.exp(r['log_source_time_ratio']);common_rows.append(r)
pd.DataFrame(common_rows).to_csv(out/'speed_n5_common_target_domains.csv',index=False)
print(pd.DataFrame(hist_rows).to_string(index=False))
print('Saved 2 figures and held-building-out difficulty joins; no fusion rerun.')
