#!/usr/bin/env python3
"""Scientific figure of complete per-image separation, without favorable-case filtering."""
import argparse
import io
import os
from pathlib import Path
import numpy as np
import pandas as pd
os.environ.setdefault('MPLCONFIGDIR','/tmp/hohonet_exchange_matplotlib')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


PANELS=[
    ('DSTRUCT_K3',10,7,'largest_to_highest_turn','Difficulty-aware structure, K=3'),
    ('V3_BEHAVIOR_coarse',12,8,'largest_to_highest_turn','Retained structural classes'),
    ('MSDGEOM_SCOPE_K4',10,7,'largest_to_highest_turn','Manual + Semi + scope, K=4'),
    ('Q_MEDIAN2',12,8,'all_directions','Historical quality baseline, K=2'),
]
CONFIRM_PANELS=[
    ('DSTRUCT_K3',18,7,'largest_to_highest_turn','Difficulty-aware structure, K=3'),
    ('RFUSE_GEOM_K2',12,4,'into_smallest_class','Team-response geometry, K=2'),
    ('RFUSE_GEOMQ_K3',20,6,'into_smallest_class','Team-response geometry + quality, K=3'),
    ('MSDGEOM_SCOPE_K4',20,6,'higher_Q|slower|more_turns','Manual + Semi + scope, K=4'),
]
COLORS={'简单':'#297E6E','中等':'#D58B22','困难':'#8C5DB0'}
NAMES={'简单':'Simple','中等':'Moderate','困难':'Difficult'}


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--summary',type=Path,required=True)
    ap.add_argument('--phase',default='screen');ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--reverse-summary',type=Path)
    ap.add_argument('--panel-set',choices=['screen','confirm'],default='screen')
    ap.add_argument('--prefix',default='SCREEN_Q_SEPARATION');a=ap.parse_args()
    a.output.mkdir(parents=True,exist_ok=True)
    cols=['phase','method','n','m','pool_id','image','building','difficulty',
          'B8L2_within','B8L2_cross','B8L2_gap']
    ordinary=pd.read_csv(a.summary/'POOL_METHOD_N_M_SUMMARY.csv.gz',usecols=cols)
    fair=pd.read_csv(a.summary/'FAIR_ROLE_POOL_SUMMARY.csv.gz',usecols=cols+['fair_role'])
    semantic=pd.read_csv(a.summary/'POOL_ROLE_SUMMARY.csv.gz',usecols=cols+['semantic_role'])
    reverse=pd.read_csv(a.reverse_summary/'REVERSE_BRANCH_POOL_SUMMARY.csv.gz',usecols=cols+['branch']) if a.reverse_summary else None
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.spines.top':False,
                         'axes.spines.right':False,'svg.fonttype':'none'})
    fig,axes=plt.subplots(2,2,figsize=(11,9.1),constrained_layout=True)
    plotted=[]
    panels=CONFIRM_PANELS if a.panel_set=='confirm' else PANELS
    for ax,(method,n,m,role,title) in zip(axes.ravel(),panels):
        if role=='into_smallest_class':
            assert reverse is not None,'The confirmation response-class panel requires --reverse-summary.'
            source=reverse[reverse.branch.eq(role)]
        elif '|' in role:source=semantic[semantic.semantic_role.eq(role)]
        else:source=ordinary if role=='all_directions' else fair[fair.fair_role.eq(role)]
        g=source[source.method.eq(method)&source.n.eq(n)&source.m.eq(m)&source.phase.eq(a.phase)].copy()
        g=g.dropna(subset=['B8L2_within','B8L2_cross','B8L2_gap'])
        g['plotted_role']=role;plotted.append(g)
        limit=max(10,float(g[['B8L2_within','B8L2_cross']].max().max())*1.10) if len(g) else 10
        ax.plot([0,limit],[0,limit],color='#888888',lw=1,ls='--',zorder=1)
        for difficulty in COLORS:
            d=g[g.difficulty.eq(difficulty)]
            ax.scatter(d.B8L2_within,d.B8L2_cross,s=38,c=COLORS[difficulty],
                       edgecolor='white',linewidth=.55,alpha=.88,label=NAMES[difficulty],zorder=3)
        if len(g):
            ax.scatter([g.B8L2_within.mean()],[g.B8L2_cross.mean()],marker='D',s=64,c='#222222',
                       edgecolor='white',linewidth=.8,zorder=5,label='Image-equal mean')
            b=g.groupby('building').B8L2_gap.mean()
            pos=g.B8L2_gap.gt(1e-9).sum();bp=b.gt(1e-9).sum()
            text=(f'Mean within / cross: {g.B8L2_within.mean():.2f} / {g.B8L2_cross.mean():.2f}\n'
                  f'Gap: {g.B8L2_gap.mean():+.2f} Q points\n'
                  f'Images above line: {pos}/{len(g)}\n'
                  f'Buildings above line: {bp}/{len(b)}')
            ax.text(.97,.04,text,transform=ax.transAxes,ha='right',va='bottom',fontsize=9,
                    bbox={'boxstyle':'round,pad=.35','facecolor':'white','alpha':.9,'edgecolor':'none'})
        ax.set(xlim=(-limit*.025,limit),ylim=(-limit*.025,limit),
               xlabel='Within-class replacement: |Q(B) - Q(A)|',
               ylabel='Cross-class replacement: mean absolute Q change')
        ax.set_aspect('equal',adjustable='box');ax.grid(alpha=.16,zorder=0)
        role_name={'all_directions':'all directions','into_smallest_class':'larger class → response-small class',
                   'higher_Q|slower|more_turns':'higher-Q / slower / more-turns role',
                   'largest_to_highest_turn':'largest class → most turns'}[role]
        ax.set_title(f'{title}\nn={n}, m={m}; '+role_name,fontsize=11)
    handles,labels=axes[0,0].get_legend_handles_labels()
    fig.legend(handles,labels,loc='outside lower center',ncol=4,frameon=False)
    phase_name={'screen':'Screening','selection_heldout_building':'Held-out-building internal check',
                'within_building_extension':'New-image internal check'}.get(a.phase,a.phase)
    fig.suptitle(phase_name+': same image, background, n and m\nEach point is one image; all usable image summaries retained',fontsize=13)
    for suffix in ['png','pdf','svg']:
        buffer=io.BytesIO()
        fig.savefig(buffer,format=suffix,dpi=210,bbox_inches='tight')
        payload=buffer.getvalue();target=a.output/(a.prefix+'.'+suffix)
        temporary=target.with_name(target.name+'.writing')
        with temporary.open('wb') as f:
            f.write(payload);f.flush();os.fsync(f.fileno())
        assert temporary.read_bytes()==payload
        temporary.replace(target)
    plt.close(fig)
    pd.concat(plotted,ignore_index=True).to_csv(a.output/(a.prefix+'_POINTS.csv'),index=False)
    caption='''# 图注

横轴为同类替换幅度，纵轴为跨类相对A/B的平均绝对Q幅度；对角线表示两者相同。每个点是一个图片，使用已经均衡具体XYZ块、背景和角色方向的逐图结果，未剔除反向结果。黑色菱形是图片等权均值；颜色对应主线简单/中等/困难。

ROLE_DESCRIPTION 图中是能够计算三队幅度的图片，全部登记事件、失败和质量损失另见同阶段风险表。图上点数不是事件数或独立成员数。

本图用于呈现全面候选比较之后选出的重点条件，不能解释为这些方法已在相同具体成员上全面胜过其它分类。原始逐图绘图数据保存在同名_POINTS.csv，实际绘图代码为analysis/plot_separation_scatter.py。
'''
    role_description=('第一格按楼外历史“最大人数类→困难转折最高类”对齐；第二、三格为楼外真实团队响应分型的非最小类→最小类；第四格是联合Manual/Semi/scope类中，目标相对源类历史Q更高、时间更慢、困难转折更多的方向，不能与该方法n10/m7最大类角色混同。全部使用selection_heldout_building阶段，即本轮相应选型未用建筑的内部v2检查，保留该材料已被多轮研究使用的事实。第三格是本轮条件比较后选出的20人换6人用途；其21图与K2共同三队可评分的20图分母差别另见GEOMQ_K3_VS_K2_N20_M6_COMMON_SUMMARY.csv。' if a.panel_set=='confirm' else '前三格按楼外历史的“最大人数类→困难转折最高类”对齐，第四格保留Q基线全部可行方向。')
    (a.output/(a.prefix+'_CAPTION.md')).write_text(caption.replace('ROLE_DESCRIPTION',role_description))
    print({'phase':a.phase,'figure':str(a.output/(a.prefix+'.png')),'points':sum(len(x) for x in plotted)})


if __name__=='__main__':main()
