#!/usr/bin/env python3
"""Publication-style figures from saved estimates; no model refitting."""
from pathlib import Path
import json,hashlib,os
import numpy as np
import pandas as pd
os.environ.setdefault('MPLCONFIGDIR',str(Path(__file__).resolve().parent/'mpl_cache'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties,fontManager

HERE=Path(__file__).resolve().parent;WORK=HERE.parent;OUT=HERE/'figures';OUT.mkdir(exist_ok=True)
FONT=HERE/'fonts/NotoSansCJKsc-Regular.otf'
fontManager.addfont(str(FONT));plt.rcParams.update({'font.family':FontProperties(fname=str(FONT)).get_name(),'axes.unicode_minus':False,'font.size':10,'axes.spines.top':False,'axes.spines.right':False,'svg.fonttype':'path','figure.dpi':145,'savefig.dpi':160})
sources=[]
def read(rel):
    p=WORK/rel;sources.append({'path':rel,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()});return pd.read_csv(p)
def save(fig,name):
    fig.savefig(OUT/(name+'.png'),bbox_inches='tight',facecolor='white');fig.savefig(OUT/(name+'.svg'),bbox_inches='tight',facecolor='white');plt.close(fig)
q=read('fusion/RANDOM_COMMON_8_12_16_24_SUMMARY.csv');v=read('fusion/SAME_K_VARIATION_COMMON_8_12_16_24.csv');s=read('clusters/fusion_analysis/replacement_summary.csv')
fig,ax=plt.subplots(2,2,figsize=(12,8.4));fig.suptitle('人数与标法簇：质量、换组波动和可互换性是不同结果',fontsize=17,y=1.01)
k=q.k.to_numpy();m=q.B8L2_building_equal.to_numpy();ax[0,0].errorbar(k,m,yerr=[m-q.B8L2_building_CI_low.to_numpy(),q.B8L2_building_CI_high.to_numpy()-m],fmt='o-',color='#006b89',capsize=4)
ax[0,0].set(title='随机团队条件可评分质量｜共同164图、22栋',xlabel='真实成员人数 k',ylabel='B8L2，建筑等权');ax[0,0].set_xticks(k)
for x,y in zip(k,m):ax[0,0].annotate(f'{y:.2f}',(x,y),xytext=(0,9),textcoords='offset points',ha='center')
m=v.abs_B8L2_change_building_equal.to_numpy();ax[0,1].errorbar(k,m,yerr=[m-v.abs_B8L2_change_building_CI_low.to_numpy(),v.abs_B8L2_change_building_CI_high.to_numpy()-m],fmt='s-',color='#bd6639',capsize=4)
ax[0,1].set(title='同 k 随机换组的端点质量差｜相同164图',xlabel='真实成员人数 k',ylabel='平均 |ΔB8L2|');ax[0,1].set_xticks(k)
for x,y in zip(k,m):ax[0,1].annotate(f'{y:.2f}',(x,y),xytext=(0,9),textcoords='offset points',ha='center')
ax[1,0].plot(k,v.joint_geometric_stable_building_equal*100,'o-',color='#006b89',label='主几何容差')
ax[1,0].plot(k,v.joint_with_shared_connections_building_equal*100,'s--',color='#bd6639',label='再要求共享观察连接一致')
ax[1,0].set(title='同 k 换组达到近似不变的比例｜失败留在分母',xlabel='真实成员人数 k',ylabel='建筑等权比例（%）',ylim=(0,100));ax[1,0].set_xticks(k);ax[1,0].legend(fontsize=9)
ss=s[(s.threshold_deg==9)&(s.contrast=='cross_minus_within_same_point_count')&(s.metric=='abs_B8L2_change')].sort_values('k')
m=ss.building_equal_difference.to_numpy();ax[1,1].errorbar(ss.k,m,yerr=[m-ss.low.to_numpy(),ss.high.to_numpy()-m],fmt='o-',capsize=4,color='#6c528b');ax[1,1].axhline(0,color='#a7b4b9',lw=1)
ax[1,1].set(title='固定背景、同点数：跨簇 − 簇内替换',xlabel='真实成员人数 k',ylabel='|ΔB8L2| 增量；9°实际簇');ax[1,1].set_xticks(k)
fig.text(.02,-.025,'区间按建筑重采样。前三图固定共同面板；第四图按 k 的可匹配图池计算，覆盖不相同。完整几何可评分不等于人工验收。',fontsize=9,color='#53646a');fig.tight_layout();save(fig,'team_size_and_swaps')

p=read('profiles/full_profiles.csv').set_index('worker_id');u=read('profiles/profile_stability_uncertainty.csv');ids=['W002','W017','W033','W006','W021','W027','W108','W114']
fig,axs=plt.subplots(2,4,figsize=(14,7.6),sharey=True);fig.suptitle('难图绝对质量、相对同伴优势、相对自身变化须分开读',fontsize=17,y=1.02)
for a,w in zip(axs.flat,ids):
    r=p.loc[w];vs=np.array([r['theta_'+d+'_B8L2']for d in ['easy','medium','hard']]);a.axhline(0,color='#9aaeb6',lw=1);a.axhline(3,color='#d2dce0',ls='--',lw=1);a.plot(range(3),vs,color='#087994',lw=2)
    for j,d in enumerate(['easy','medium','hard']):
        a.scatter(j,vs[j],s=45,facecolor='#087994'if r['difficulty_supported_'+d]else'white',edgecolor='#087994',zorder=3)
        a.annotate(f'{vs[j]:.1f}',(j,vs[j]),xytext=(0,8),textcoords='offset points',ha='center',fontsize=9)
    a.set_xticks(range(3),['简单','中等','困难']);a.set_ylim(-14,33);a.set_title(f"{w}｜绝对均值 {r.absolute_B8L2_mean:.1f} / P10 {r.absolute_B8L2_p10:.1f}",fontsize=10)
    a.text(.02,.02,' / '.join(f"{int(r['images_'+d])}图·{int(r['buildings_'+d])}楼"for d in ['easy','medium','hard']),transform=a.transAxes,fontsize=8,color='#5e7279')
for a in axs[:,0]:a.set_ylabel('部分汇聚后相对效应 θ（B8分）')
fig.text(.01,-.025,'全量描述曲线，不能代替目标建筑外训练；空心点未达每层6任务/3栋支持。W017是相对难图专长候选，W006的难图θ仍为负。',fontsize=9,color='#53646a');fig.tight_layout();save(fig,'personnel_difficulty')

f=read('fusion/FORWARD_POLICY_SUMMARY.csv');base=f[(f.selection_metric=='B8L2')&(f.candidate_pool=='Q_history_supported_all_origins')&(f.difficulty_stratum=='all')]
fig,ax=plt.subplots(1,2,figsize=(12.4,5.5));names=['Q_vs_eligible_random','QT_vs_eligible_random','QTD_vs_eligible_random'];colors=['#006b89','#bd6639','#70548f']
for name,c,l in zip(names,colors,['Q优先','Q＋T','Q＋T＋难度']):
    z=base[(base.contrast==name)&(base.metric=='B8_change')].sort_values('k');m=z.building_equal.to_numpy();off=names.index(name)*.22-.22
    ax[0].errorbar(z.k.to_numpy()+off,m,yerr=[m-z.building_CI_low.to_numpy(),z.building_CI_high.to_numpy()-m],fmt='o-',label=l,color=c,capsize=3)
ax[0].axhline(0,color='#9aafb6',lw=1);ax[0].set_xticks([8,12,16,24]);ax[0].set(title='楼外画像选人 vs 同候选池随机',xlabel='团队人数 k（各k覆盖不同）',ylabel='建筑等权 B8L2 差');ax[0].legend()
ct=['time_within_same_known_band_QT','time_within_same_known_band_QTD'];labels=['Q＋T 相对同质量带仅Q','Q＋T＋难度相对同质量带仅QD']
for i,(name,lab,col) in enumerate(zip(ct,labels,colors[1:])):
    z=base[(base.contrast==name)&(base.k==16)]
    yy=z[z.metric=='B8_change'].iloc[0];xx=z[z.metric=='source_cost_ratio_change'].iloc[0]
    ax[1].errorbar(xx.building_equal*100,yy.building_equal,xerr=[[100*(xx.building_equal-xx.building_CI_low)],[100*(xx.building_CI_high-xx.building_equal)]],yerr=[[yy.building_equal-yy.building_CI_low],[yy.building_CI_high-yy.building_equal]],fmt='o',capsize=4,color=col,label=lab)
ax[1].axhline(0,color='#9aafb6',lw=1);ax[1].set(title='16人：节省来源时间伴随质量代价',xlabel='来源全员成本变化（%）',ylabel='B8L2变化');ax[1].legend(fontsize=8,loc='upper left')
fig.text(.01,-.04,'图右：质量分别168/169图可比，成本分别114/112图完整已知；两个轴的缺失覆盖不同，不是同目标完工时长或个人因果效应。',fontsize=9,color='#53646a');fig.tight_layout();save(fig,'policy_tradeoffs')
(OUT/'FIGURE_SOURCES.json').write_text(json.dumps({'sources':sources,'font_sha256':hashlib.sha256(FONT.read_bytes()).hexdigest(),'figures':[p.name for p in OUT.glob('*.png')],'refit':False},ensure_ascii=False,indent=2))
print('saved 3 figures as PNG and SVG')
