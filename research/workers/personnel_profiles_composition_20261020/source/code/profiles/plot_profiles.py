"""Three standalone scientific figures from the personnel profile output tables."""
from pathlib import Path
import argparse,os
os.environ.setdefault('MPLCONFIGDIR','/tmp/personnel_profile_mpl')
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager


def main():
    pa=argparse.ArgumentParser();pa.add_argument('--out',type=Path,required=True);pa.add_argument('--font',type=Path,required=True)
    a=pa.parse_args();font_manager.fontManager.addfont(str(a.font));family=font_manager.FontProperties(fname=str(a.font)).get_name()
    plt.rcParams.update({'font.family':family,'font.size':10,'axes.titlesize':12,'axes.labelsize':10,
      'axes.spines.top':False,'axes.spines.right':False,'axes.unicode_minus':False,'savefig.facecolor':'white','figure.facecolor':'white'})
    p=pd.read_csv(a.out/'worker_profiles.csv');o=p[p.panel.eq('ordinary')]
    def annotate(ax,g,names,offsets=None):
        for name in names:
            r=g[g.worker_id.eq(name)]
            if r.empty:continue
            r=r.iloc[0];xy=(r['_x'],r['_y']);off=(5,4) if offsets is None else offsets.get(name,(5,4))
            ax.annotate(name,xy,xytext=off,textcoords='offset points',fontsize=9,color='#152536',
                arrowprops={'arrowstyle':'-','color':'#8a97a6','lw':.55} if abs(off[0])+abs(off[1])>14 else None)
    fig,axes=plt.subplots(2,2,figsize=(12,8),sharex=True,sharey=True)
    specs=[('manual','new','Manual · 新批'),('manual','v1','Manual · 旧批'),('semi','new','Semi · 新批'),('semi','v1','Semi · 旧批')]
    names={('manual','new'):['W109','W112','W102','W126','W122','W114','W121'],('manual','v1'):['W002','W027','W036','W037','W006'],
      ('semi','new'):['W109','W112','W122','W128','W117'],('semi','v1'):['W011','W006','W015','W036','W001']}
    offsets={'W109':(-38,-12),'W112':(8,4),'W102':(-42,1),'W126':(9,-8),'W122':(12,2),
      'W114':(-39,4),'W121':(-43,3),'W011':(-38,4),'W006':(-39,-12),'W015':(8,4),'W036':(9,1)}
    for ax,(cond,origin,label) in zip(axes.flat,specs):
        g=o[o.condition.eq(cond)&o.origin.eq(origin)&o.Q_supported&o.T_supported].copy()
        g['_x']=g.Q_peer;g['_y']=g.relative_time
        ax.scatter(g.Q_peer,g.relative_time,s=27+np.sqrt(g.n_quality)*7,c='#246b83' if cond=='manual' else '#785995',alpha=.8,edgecolor='white',linewidth=.7)
        ax.axvline(0,color='#bbc4cf',lw=.8);ax.axhline(1,color='#bbc4cf',lw=.8)
        ax.set_yscale('log');ax.set_ylim(.14,8);ax.set_xlim(-23,23);ax.set_yticks([.2,.5,1,2,5]);ax.set_yticklabels(['0.2','0.5','1','2','5'])
        ax.grid(alpha=.15);ax.set_title(f'{label}（{len(g)}人）',loc='left',fontweight='bold')
        annotate(ax,g,names[(cond,origin)],offsets)
    for ax in axes[-1]:ax.set_xlabel('同任务相对质量：B8L2 同行残差均值（分）')
    for ax in axes[:,0]:ax.set_ylabel('同来源任务调整耗时倍数（对数刻度）')
    fig.suptitle('质量与速度提供不同信息',fontsize=18,fontweight='bold',x=.075,ha='left',y=.995)
    fig.text(.075,.945,'Q、T 均须至少8张图、3栋建筑；每个条件和时间来源分别展示。点面积表示质量支持量。',fontsize=10,color='#526171')
    fig.text(.075,.015,'倍数 < 1 表示相对本来源同行更快。新批为报告任务活动耗时，旧批继承已审计源时间；图中倍数不能作跨来源绝对工时比较。',fontsize=9,color='#526171')
    fig.tight_layout(rect=[.03,.05,1,.93]);fig.savefig(a.out/'profile_quality_speed.png',dpi=190);plt.close(fig)

    fig,axes=plt.subplots(1,2,figsize=(12,5.6),sharey=True)
    for ax,origin,label in zip(axes,['new','v1'],['新批','旧批']):
        g=o[o.condition.eq('manual')&o.origin.eq(origin)&o.hard_supported].copy()
        g['_x']=g.hard_Q_peer;g['_y']=g.hard_minus_easy_peer
        ax.axvline(0,color='#aab6c1',lw=.8);ax.axhline(0,color='#aab6c1',lw=.8)
        ax.scatter(g._x,g._y,s=30+g.hard_n*3,c='#246b83',alpha=.8,edgecolors='white',linewidth=.7)
        ax.grid(alpha=.14);ax.set_xlabel('难图实际相对水平：B8L2 同行残差（分）')
        ax.set_title(f'Manual · {label}（{len(g)}人）',loc='left',fontweight='bold')
        annotate(ax,g,['W102','W109','W112','W122','W126','W128','W114'] if origin=='new' else ['W037','W018','W027','W034','W002'],
          {'W102':(-47,5),'W112':(6,6),'W126':(-40,-12),'W122':(8,1),'W109':(7,-7),'W128':(7,1),'W018':(7,2),'W027':(7,-13)})
    axes[0].set_ylabel('难图 − 简单图的同行残差（分）')
    fig.suptitle('困难适应性：水平和自身变化必须同时看',fontsize=18,fontweight='bold',x=.075,ha='left',y=.995)
    fig.text(.075,.915,'困难Q支持至少3图、2栋建筑；只使用难度与当前参考目标相容的正式质量作答。',fontsize=10,color='#526171')
    fig.text(.075,.02,'右上：难图高于同行且相对自身简单图更有利；左上：相对跌幅较小，但难图仍低于同行。Semi普通正式Q没有对应“困难”支持，留空。',fontsize=9,color='#526171')
    fig.tight_layout(rect=[.03,.06,1,.90]);fig.savefig(a.out/'profile_hard_adaptation.png',dpi=190);plt.close(fig)

    fig,axes=plt.subplots(1,2,figsize=(12,5.8))
    g=o[o.condition.eq('manual')&o.origin.eq('new')&o.Q_supported].copy();g['_x']=g.Q_mean;g['_y']=g.Q_q10
    axes[0].scatter(g._x,g._y,s=55,c='#246b83',alpha=.75,edgecolors='white',linewidth=.7)
    annotate(axes[0],g,['W109','W112','W122','W126','W130','W102'],{'W109':(-52,3),'W112':(-51,-7),'W122':(8,-9),'W126':(8,0),'W130':(8,2),'W102':(-50,13)})
    axes[0].set_xlabel('保留作答的 B8L2 均值');axes[0].set_ylabel('B8L2 第10百分位');axes[0].set_title('新批 Manual：相近均值仍有低尾差异',loc='left',fontweight='bold');axes[0].grid(alpha=.14)
    g=o[o.condition.eq('manual')&o.origin.eq('v1')&o.Q_supported].copy();g['_x']=g.Q_mean;g['_y']=100*g.cleaning_excluded_rate
    axes[1].scatter(g._x,g._y,s=55,c='#ad6359',alpha=.8,edgecolors='white',linewidth=.7)
    annotate(axes[1],g,['W037','W034','W032','W036','W012','W027'],{'W034':(6,6),'W032':(-47,0),'W012':(7,6),'W027':(7,4)})
    axes[1].set_xlabel('保留作答的 B8L2 均值');axes[1].set_ylabel('人工筛除／历史未接纳占库存比例（%）')
    axes[1].set_title('旧批 Manual：Q不包含已被筛除的作答',loc='left',fontweight='bold');axes[1].grid(alpha=.14);axes[1].set_ylim(-1.3,29)
    fig.suptitle('均分、低尾和筛除提供不同的风险信息',fontsize=18,fontweight='bold',x=.075,ha='left',y=.995)
    fig.text(.075,.908,'低尾图为个人原有任务集合；W122/W126进一步固定106张共同图后，均Q 86.08/86.42，Q10 50.11/61.00。',fontsize=10,color='#526171')
    fig.text(.075,.017,'筛除分母为普通Manual库存作答；具体归因另表，不能全称严重人员错误。W019/W026全无可用Q，故未画为零分；GT和池限制未计入筛除。',fontsize=9,color='#526171')
    fig.tight_layout(rect=[.03,.065,1,.89]);fig.savefig(a.out/'profile_low_tail_screening.png',dpi=190);plt.close(fig)


if __name__=='__main__':main()
