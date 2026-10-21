"""Publication-style figures from frozen study tables; no new experiments."""
from __future__ import annotations
import os
os.environ['MPLCONFIGDIR']='/tmp/hohonet_report_matplotlib'
os.environ['OPENBLAS_NUM_THREADS']='1'
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager

HERE=Path(__file__).resolve().parent
STUDY=HERE.parent
OUT=HERE/'figures';OUT.mkdir(exist_ok=True)
font_manager.fontManager.addfont(str(HERE/'assets/HOHONET_Report_Regular.ttf'))
FONT=font_manager.FontProperties(fname=str(HERE/'assets/HOHONET_Report_Regular.ttf')).get_name()
plt.rcParams.update({'font.family':FONT,'axes.unicode_minus':False,'font.size':11,'axes.labelcolor':'#263950','text.color':'#263950','axes.edgecolor':'#cbd6df','grid.color':'#dce5ec','axes.spines.top':False,'axes.spines.right':False,'savefig.facecolor':'white'})
TEAL='#1784a4';PURPLE='#8957b1';INK='#263950'


def efficiency():
    d=pd.read_csv(STUDY/'analysis/NEW_CLASS_EXPRESSION_PANELS.csv.gz')
    z=d[(d.method_id=='MV_QTD_manual_new')&(d.layer=='ordinary')&(d.source=='new')&(d.level=='fine_class')&(d.class_a=='QL.1')&(d.class_b=='QL.2')]
    assert len(z)>0
    cols=['log_time_peer_delta_difference','turn_n_difference','B8L2_difference']
    q=z.groupby(['building_id','image_code'])[cols].mean().groupby('building_id').mean().sort_values(cols[0])
    q['image_n']=z.groupby('building_id').image_code.nunique();q['relative_time_ratio']=np.exp(q[cols[0]])
    q.to_csv(OUT/'manual_efficiency_building_points.csv',encoding='utf-8-sig')
    fig,axes=plt.subplots(1,2,figsize=(12.2,8.2),sharey=True,gridspec_kw={'width_ratios':[1,1.1]})
    y=np.arange(len(q));labels=[f'{b[:5]}  ({int(r.image_n)}图)' for b,r in q.iterrows()]
    axes[0].barh(y,q.relative_time_ratio,color=TEAL,alpha=.85,height=.64)
    axes[0].axvline(1,color=INK,linestyle='--',linewidth=1);axes[0].set_xlabel('较慢类 / 较快类：相对活动时间倍数')
    axes[0].set_yticks(y,labels);axes[0].set_xlim(0,max(q.relative_time_ratio)*1.12)
    axes[1].barh(y,q.turn_n_difference,color=[PURPLE if v>0 else '#879ba9' for v in q.turn_n_difference],height=.64)
    axes[1].axvline(0,color=INK,linestyle='--',linewidth=1);axes[1].set_xlabel('较慢类 − 较快类：同图转折数差')
    for ax in axes:ax.grid(axis='x',alpha=.55);ax.set_axisbelow(True)
    axes[0].set_title('22 / 22 建筑：较慢类均更慢',loc='left',fontsize=13,pad=14)
    axes[1].set_title('仅 8 / 22 建筑：较慢类转折更多',loc='left',fontsize=13,pad=14)
    fig.suptitle('新批 Manual 细类：可重复的时间差，较弱的结构分离',fontsize=18,x=.06,ha='left',y=.98)
    fig.text(.06,.025,'楼外标签；同图同来源比较，参考面板 → 图片 → 建筑。每个点为一栋建筑；括号为图数。\n细类成员已冻结，类别名只解释实际证据。时间倍数来自 log 时间差，不是团队工期。',fontsize=10,color='#58687a')
    fig.subplots_adjust(left=.17,right=.97,top=.9,bottom=.13,wspace=.18)
    fig.savefig(OUT/'manual_efficiency_vs_structure.png',dpi=170);plt.close(fig)


def large_replacements():
    path=STUDY/'analysis/ABC_LARGE_SUMMARY.csv'
    if not path.exists():return
    d=pd.read_csv(path);d=d[(d.event_mode=='cross_composition')&d.layer.isin(['ordinary_manual','ordinary_semi'])]
    labels={'M_structure':'M 结构','A2_relation':'A2 原答关系','Rnew2':'Rnew2 反向','MV_QTD_manual_new':'新批 QTD','MV_QTD_manual':'混来源 QTD','SP_scale':'SP 尺度','MV_QTScopeSemi_semi_new':'Semi 行为','MV_TDScopeSemi_manual_new':'无Q四域'}
    tiers={'coarse':'粗','fine':'细','single':'单层'}
    groups=[]
    for cond in ['manual','semi']:
        g=d[(d.condition==cond)&d.method_id.ne('MV_TDScopeSemi_manual_new')].copy()
        g['order']=g.method_id.map({k:i for i,k in enumerate(labels)})*3+g.tier.map({'coarse':0,'fine':1,'single':2})
        groups.append(g.sort_values('order'))
    fig,axes=plt.subplots(2,2,figsize=(13,9.8),gridspec_kw={'height_ratios':[max(4,len(groups[0])),max(3,len(groups[1]))]})
    for ridx,(cond,g) in enumerate(zip(['Manual','Semi'],groups)):
        y=np.arange(len(g));tags=[labels[r.method_id]+' · '+tiers[r.tier]+f'  ({r.buildings}楼)' for r in g.itertuples()]
        ax=axes[ridx,0]
        same=g.common_quality_within_abs_mean.to_numpy();cross=g.common_quality_cross_abs_mean.to_numpy()
        for yy,a,b in zip(y,same,cross):ax.plot([a,b],[yy,yy],color='#bccbd6',linewidth=2)
        ax.scatter(same,y,color=TEAL,s=36,label='同构成换人');ax.scatter(cross,y,color=PURPLE,s=36,label='改构成换类')
        ax.set_yticks(y,tags);ax.invert_yaxis();ax.set_xlabel('平均 |ΔB8L2|（共同可评分三臂）');ax.grid(axis='x',alpha=.5)
        ax.set_title(cond+' · 质量波动',loc='left',fontsize=14,pad=10)
        ax=axes[ridx,1];v=g.stable_advantage_mean.to_numpy()*100
        lo=g.stable_advantage_lo.to_numpy()*100;hi=g.stable_advantage_hi.to_numpy()*100
        ax.errorbar(v,y,xerr=np.vstack([np.maximum(0,v-lo),np.maximum(0,hi-v)]),fmt='o',color=INK,ecolor='#8aa2b4',capsize=3)
        ax.axvline(0,color='#889bad',linestyle='--',linewidth=1);ax.set_yticks(y,[]);ax.invert_yaxis()
        ax.set_xlabel('同构成 − 改构成：主联合稳定率（百分点）')
        ax.set_title('质量与形状同时接近',loc='left',fontsize=14,pad=10);ax.grid(axis='x',alpha=.5)
    handles,legend_labels=axes[0,0].get_legend_handles_labels()
    fig.legend(handles,legend_labels,frameon=False,loc='lower center',bbox_to_anchor=(.55,.072),ncol=2,fontsize=10)
    fig.suptitle('大团队块替换：固定人数、实际换人数与共同背景',fontsize=18,x=.04,ha='left',y=.985)
    fig.text(.04,.022,'n ≥ 20、m ≥ 4；各方法使用其合法容量，不能把不同人群的横行直接解释为方法排名。\n参考池 → 图片 → 建筑等权；右图为建筑重采样区间。新 Semi 行为类缺少此规模的可用块，另列 n15 结果。',fontsize=10,color='#58687a')
    fig.subplots_adjust(left=.22,right=.98,top=.91,bottom=.13,hspace=.42,wspace=.2)
    fig.savefig(OUT/'large_replacement_quality_and_shape.png',dpi=170);plt.close(fig)


def m_response():
    path=STUDY/'analysis/ABC_ALL_COMPONENT_EVENTS.csv.gz'
    if not path.exists():return
    d=pd.read_csv(path,low_memory=False)
    g=d[(d.method_id=='M_structure')&(d.tier=='coarse')&(d.layer=='ordinary_manual')&(d.n==20)&(d.event_mode=='cross_composition')&d.m_AB.isin([4,8,12])]
    supports=[set(g[g.m_AB.eq(m)].pool_id) for m in [4,8,12]];common=set.intersection(*supports);g=g[g.pool_id.isin(common)]
    vals=[]
    for m,z in g.groupby('m_AB'):
        for variable in ['common_quality_within_abs','common_quality_cross_abs','within_joint_stable_main','cross_joint_stable_main']:
            q=z.groupby(['building','image','pool_id'])[variable].mean().groupby(['building','image']).mean().groupby('building').mean()
            vals.append(dict(m=m,metric=variable,mean=q.mean(),pools=len(common),images=z.image.nunique(),buildings=z.building.nunique(),events=len(z)))
    v=pd.DataFrame(vals);v.to_csv(OUT/'m_response_shared_pools.csv',index=False,encoding='utf-8-sig')
    fig,axes=plt.subplots(1,2,figsize=(11.8,4.8))
    for ax,fields,scale,ylabel in [(axes[0],['common_quality_within_abs','common_quality_cross_abs'],1,'平均 |ΔB8L2|'),(axes[1],['within_joint_stable_main','cross_joint_stable_main'],100,'主联合稳定率 (%)')]:
        for field,color,name in zip(fields,[TEAL,PURPLE],['同构成换人','改构成换类']):
            z=v[v.metric.eq(field)];ax.plot(z.m,z['mean']*scale,'o-',color=color,label=name,linewidth=2)
        ax.set_xticks([4,8,12]);ax.set_xlabel('实际替换人数 m');ax.set_ylabel(ylabel);ax.grid(alpha=.5);ax.legend(frameon=False)
    fig.suptitle('M 结构粗类：n=20，在同一组图片上比较 m=4、8、12',fontsize=17,x=.06,ha='left',y=.98)
    fig.text(.06,.025,f'共同支持 {g.image.nunique()} 图 / {g.building.nunique()} 楼。每个 ABC 事件内背景、n、m 严格相同；不同 m 使用注册背景抽样。',fontsize=10,color='#58687a')
    fig.subplots_adjust(left=.08,right=.98,top=.84,bottom=.19,wspace=.3)
    fig.savefig(OUT/'replacement_m_response.png',dpi=170);plt.close(fig)


if __name__=='__main__':
    efficiency();large_replacements();m_response();print('Figures generated from available final tables',flush=True)
