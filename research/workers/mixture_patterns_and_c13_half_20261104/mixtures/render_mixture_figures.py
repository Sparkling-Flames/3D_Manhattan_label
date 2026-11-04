#!/usr/bin/env python3
"""Publication-style plots from saved paired image results, without new scores."""
from pathlib import Path
import argparse
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import colors
from plot_style import configure_cjk_font

HERE=Path(__file__).resolve().parent
plt.rcParams.update({'savefig.dpi':220})
DIFF=['简单','中等','困难'];COL=['#409098','#dcab4e','#a25063']

def save(fig,name):
    fig.savefig(HERE/(name+'.png'),bbox_inches='tight')
    fig.savefig(HERE/(name+'.svg'),bbox_inches='tight');plt.close(fig)

def alliance():
    d=pd.read_csv(HERE/'DSTRUCT_ALLIANCE_STRATA.csv')
    choices=[('C1','C1|C3'),('C2','C2|C3'),('C1|C2','C1|C2|C3'),
             ('C3','C1|C3'),('C3','C2|C3'),('C2|C3','C1|C2|C3')]
    fig,(ax,bx)=plt.subplots(1,2,figsize=(13.3,6.7),layout='constrained',gridspec_kw={'width_ratios':[1.3,1]})
    ax.axvline(0,color='#5f6670',lw=1)
    labels=[]
    for i,(fr,to) in enumerate(choices):
        r=d[d.from_classes.eq(fr)&d.to_classes.eq(to)&d.metric.eq('B8L2')&d.axis.eq('ALL')].iloc[0]
        col='#087f8c' if r.image_mean>0 else '#b05739'
        ax.plot([r.leave_one_building_image_mean_min,r.leave_one_building_image_mean_max],[i,i],color=col,lw=3,zorder=2)
        ax.scatter([r.image_mean],[i],c=col,s=58,zorder=3,label='图等权均值' if i==0 else None)
        ax.scatter([r.image_median],[i],c='#303944',marker='D',s=25,zorder=4,label='图间中位数' if i==0 else None)
        ax.text(max(r.image_mean,r.image_median,r.leave_one_building_image_mean_max)+.55,i,
            f'{r.image_mean:+.2f}',va='center',fontsize=10,color=col)
        labels.append(f"{fr.replace('|','+')} → {to.replace('|','+')}\n{int(r.valid_images)} 图 / {int(r.buildings)} 楼 · 升 {int(r.positive_images)} / 降 {int(r.negative_images)}")
    ax.set_yticks(range(len(choices)),labels);ax.invert_yaxis();ax.set_xlim(-7.8,17.8)
    ax.set_xlabel('混合端减基线端的 Q 分差');ax.grid(axis='x',color='#e4e8ec',lw=.6)
    ax.set_title('A  同一混合终点，相对不同基线的变化',loc='left',fontweight='bold',pad=15)
    ax.legend(loc='lower right',frameon=False)
    cross=pd.read_csv(HERE/'DSTRUCT_DIFFICULTY_STRUCTURE_CROSS.csv')
    cross=cross[cross.from_classes.eq('C3')&cross.to_classes.eq('C2|C3')&cross.metric.eq('B8L2')]
    shapes=['no_short_turns_or_boundary_occlusion','short_turns_without_boundary_occlusion','boundary_self_occlusion']
    array=np.full((3,3),np.nan)
    for i,diff in enumerate(DIFF):
        for j,shape in enumerate(shapes):
            z=cross[cross.official_difficulty.eq(diff)&cross.structural_condition.eq(shape)]
            if not z.empty:array[i,j]=z.iloc[0].image_mean
    cmap=plt.get_cmap('RdBu').copy();cmap.set_bad('#eceff2')
    heat=bx.imshow(array,cmap=cmap,norm=colors.TwoSlopeNorm(vmin=-25,vcenter=0,vmax=5),aspect='auto')
    for i,diff in enumerate(DIFF):
        for j,shape in enumerate(shapes):
            z=cross[cross.official_difficulty.eq(diff)&cross.structural_condition.eq(shape)]
            if z.empty:label='无共同 Q';col='black'
            else:
                r=z.iloc[0];label=f'{r.image_mean:+.2f}\n{int(r.valid_images)} 图 · {int(r.buildings)} 楼';col='white' if r.image_mean< -15 else '#202832'
            bx.text(j,i,label,ha='center',va='center',fontsize=10,color=col)
    bx.set_yticks(range(3),DIFF);bx.set_xticks(range(3),['无短段、无遮挡','短段、无遮挡','边界自身遮挡'])
    bx.set_title('B  C3 → C2+C3 的难度与结构交叉',loc='left',fontweight='bold',pad=15)
    fig.colorbar(heat,ax=bx,shrink=.65,label='同图 Q 均差')
    fig.suptitle('当前 DSTRUCT K3：加入 C3 的补偿与加入其它类的条件性稀释',fontsize=15)
    fig.supxlabel('A 的线段为留一建筑后的图等权均值范围，不是置信区间。B 为既有难度与结构分层，不作为遮挡的独立因果效应。',fontsize=9)
    save(fig,'FIG01_COALITION_BASELINES_AND_STRUCTURE')

def composition():
    d=pd.read_csv(HERE/'FIXED_N_FOCUSED_IMAGE_EFFECTS.csv.gz')
    d=d[d.method.eq('TARGET_DSTRUCT_K3')&d.from_class.eq('C2')&d.to_class.eq('C3')&
        d.support.eq('all_teams_Q_valid_in_both_configurations')&d.n.isin([12,20])]
    c=pd.read_csv(HERE/'FIXED_N_THREE_OR_MORE_LEVEL_CHAIN_STRATA.csv')
    c=c[c.method.eq('TARGET_DSTRUCT_K3')&c.from_class.eq('C2')&c.to_class.eq('C3')&c.axis.eq('ALL')&
        c.support.eq('all_teams_Q_valid_in_every_configuration')&c.n.isin([12,20])]
    fig,(ax,bx)=plt.subplots(1,2,figsize=(12.8,5.8),layout='constrained',gridspec_kw={'width_ratios':[1.35,1]})
    rng=np.random.default_rng(61104)
    for i,n in enumerate([12,20]):
        g=d[d.n.eq(n)].sort_values('image')
        for diff,col in zip(DIFF,COL):
            z=g[g.official_difficulty.eq(diff)]
            ax.scatter(z.effect,np.full(len(z),i)+rng.uniform(-.16,.16,len(z)),s=25,alpha=.8,color=col,label=diff if i==0 else None)
        ax.scatter([g.effect.mean()],[i],marker='D',s=85,color='black',zorder=4)
        ax.text(g.effect.max()+.4,i,f'均值 {g.effect.mean():+.3f}\n{len(g)} 图 / {g.building.nunique()} 楼',va='center',fontsize=10)
    ax.set_yticks([0,1],['n=12','n=20']);ax.set_ylim(1.5,-.5);ax.axvline(0,color='#77808a',lw=.8)
    ax.set_xlabel('C2 少 1 人、C3 多 1 人的相邻配置均值 Q 差');ax.grid(axis='x',color='#e2e6eb',lw=.6)
    ax.set_xlim(d.effect.min()-1,d.effect.max()+8)
    ax.set_title('A  固定背景、候选池和人数的同图方向',loc='left',fontweight='bold',pad=15)
    ax.legend(loc='lower right',frameon=False,ncol=3)
    width=.58
    for i,n in enumerate([12,20]):
        g=c[c.n.eq(n)].set_index('metric');up=g.loc['nondecreasing','image_mean'];mixed=g.loc['both_directions','image_mean'];down=1-up-mixed
        bottom=0
        for value,col,label in [(up,'#087f8c','逐步不下降'),(mixed,'#dda842','双向起伏'),(down,'#a95463','逐步不增加')]:
            bx.bar(i,value*100,bottom=bottom*100,width=width,color=col,label=label if i==0 else None)
            if value>.07:bx.text(i,(bottom+value/2)*100,f'{value*100:.1f}%',ha='center',va='center',color='white' if col!='#dda842' else 'black',fontsize=11)
            bottom+=value
        r=g.loc['nondecreasing'];bx.text(i,-8,f'{int(r.valid_images)} 图 / {int(r.buildings)} 楼',ha='center',fontsize=9)
    bx.set_xticks([0,1],['n=12','n=20']);bx.set_ylim(-14,104);bx.set_ylabel('有限配比链比例（链→面板→图等权，%）')
    bx.set_title('B  至少 3 个连续配置层级的单调性',loc='left',fontweight='bold',pad=15)
    bx.legend(loc='upper left',bbox_to_anchor=(0,-.08),frameon=False,ncol=3,fontsize=9)
    fig.suptitle('固定人数仍有类别方向：多数 C2→C3 配比链的 Q 逐步不下降',fontsize=15)
    fig.supxlabel('all_formal 已有有限面板。各配置的全部团队都可评 Q；这是配置均值关系，不是同一队逐人进入的路径。',fontsize=9)
    save(fig,'FIG02_FIXED_N_COMPOSITION_AND_MONOTONICITY')

def background():
    d=pd.read_csv(HERE/'FIXED_BLOCK_BACKGROUND_IMAGE_EFFECTS.csv.gz')
    choices=[('RFUSE_GEOM_K2','1->2',4,31,'RFUSE K2  1→2\nm=4，n=20→31'),
        ('OPPJOINT_K3','1->3',7,28,'JOINT K3  1→3\nm=7，n=20→28'),
        ('OPPJOINT_K4','1->2',7,28,'JOINT K4  1→2\nm=7，n=20→28')]
    fig,axs=plt.subplots(2,3,figsize=(12.5,8.0),layout='constrained')
    for ci,(method,direction,m,n2,title) in enumerate(choices):
        z=d[d.method.eq(method)&d.role_direction.eq(direction)&d.n_from.eq(20)&d.n_to.eq(n2)&d.m_from.eq(m)&d.m_to.eq(m)]
        assert np.allclose(z['B8L2_CA__to']-z['B8L2_CA__from'],z['B8L2_CA__step_difference'])
        for ri,(a,b,delta,label) in enumerate([
            ('B8L2_CA__from','B8L2_CA__to','B8L2_CA__step_difference','有符号换人效应'),
            ('absolute_effect_from','absolute_effect_to','absolute_effect_change','绝对换人幅度')]):
            ax=axs[ri,ci];x=z[a];y=z[b]
            lo=min(x.min(),y.min(),0);hi=max(x.max(),y.max(),0);pad=(hi-lo)*.08
            lo-=pad;hi+=pad
            ax.plot([lo,hi],[lo,hi],color='#87919c',ls='--',lw=.9)
            ax.scatter(x,y,s=20,alpha=.7,color=['#087f8c','#6b72a6','#b26448'][ci])
            ax.scatter([x.mean()],[y.mean()],marker='D',s=72,color='black',zorder=4)
            ax.set(xlim=(lo,hi),ylim=(lo,hi),aspect='equal',xlabel='背景增加前（Q 分）',ylabel='背景增加后（Q 分）')
            ax.grid(color='#e3e7ec',lw=.5)
            ax.text(.04,.96,f"{label}\n均值 {x.mean():.2f} → {y.mean():.2f}\n阶差 {z[delta].mean():+.3f}\n{len(z)} 图 / {z.building.nunique()} 楼",transform=ax.transAxes,va='top',fontsize=9,
                bbox=dict(facecolor='white',alpha=.8,edgecolor='none',pad=2))
            if ri==0:ax.set_title(title,loc='left',fontsize=11,fontweight='bold')
    fig.suptitle('固定换人块、扩充共同背景：有符号效应与绝对幅度可以给出不同答案',fontsize=14)
    fig.supxlabel('每点为同一图片的四端共同 Q 路径均值；黑菱形为图等权均值。角色方向保持既有 AC 训练历史 Q 秩身份。',fontsize=9)
    save(fig,'FIG03_BACKGROUND_SIGNED_AND_ABSOLUTE')

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--font');parser.add_argument('--without-background',action='store_true')
    args=parser.parse_args();configure_cjk_font(args.font)
    alliance();composition()
    if not args.without_background:background()
    print('Scientific figures exported.',flush=True)
