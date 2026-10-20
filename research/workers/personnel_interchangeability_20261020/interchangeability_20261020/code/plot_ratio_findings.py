"""Rebuild the ratio-search and finite-population figures from compact evidence."""
from __future__ import annotations
import argparse, ast, hashlib, json
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib import font_manager


def setup(font):
    font_manager.fontManager.addfont(str(font))
    plt.rcParams.update({'font.family':font_manager.FontProperties(fname=font).get_name(),
        'axes.unicode_minus':False,'font.size':10,'axes.spines.top':False,
        'axes.spines.right':False,'axes.labelcolor':'#35495e','text.color':'#22354a',
        'xtick.color':'#35495e','ytick.color':'#35495e','figure.facecolor':'white'})


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--study',type=Path,required=True)
    ap.add_argument('--out',type=Path,required=True);ap.add_argument('--font',type=Path,required=True)
    a=ap.parse_args();a.out.mkdir(parents=True,exist_ok=True);setup(a.font)
    root=a.study/'ratio_grid';r=root/'confirmation_results'
    winners=pd.read_csv(r/'discovery_winners_followed_without_reselection.csv').sort_values('rule_id')
    assessment=pd.read_csv(r/'frozen_ratio_summary.csv')
    assessment=assessment[(assessment.phase=='assessment')&(assessment.evaluation_band=='all_available')].sort_values('rule_id')
    fig,axs=plt.subplots(1,2,figsize=(11.2,5.6),gridspec_kw={'width_ratios':[1.1,1]})
    fig.subplots_adjust(left=.08,right=.975,top=.82,bottom=.235,wspace=.36)
    colors=['#197c9f','#5e91a4','#a47d3b','#875393','#bc5546']
    for i,row in enumerate(winners.itertuples()):
        axs[0].plot([0,1],[row.discovery,row.replication],'-o',color=colors[i],lw=2,label=row.rule_id)
        axs[0].annotate(f'{row.rule_id} {row.replication:+.2f}',(1,row.replication),xytext=(7,0),textcoords='offset points',va='center',fontsize=9)
    axs[0].set_xticks([0,1],['发现：每构成最多 4 队','同图：新抽最多 16 队'])
    axs[0].set_xlim(-.1,1.56);axs[0].set_ylim(-20,20);axs[0].axhline(0,color='#bac4ce',lw=.8)
    axs[0].set_ylabel('混类均值 − 最好纯类均值（B8L2 分）')
    axs[0].set_title('A  逐一追踪当初最好看的图片',loc='left',fontsize=12,pad=13)
    for i,row in enumerate(assessment.itertuples()):
        axs[1].barh(i,row.mixture_minus_best_pure_Q,color=colors[i],height=.64)
        axs[1].text(row.mixture_minus_best_pure_Q-.15,i,f'{row.mixture_minus_best_pure_Q:+.2f}',ha='right',va='center',fontsize=10)
        axs[1].text(.23,i,f'{row.images} 图 / 6 楼',va='center',fontsize=9)
    axs[1].set_yticks(range(5),assessment.rule_id);axs[1].invert_yaxis();axs[1].axvline(0,color='#a4b0bd',lw=.8)
    axs[1].set_xlim(-12.5,4);axs[1].set_xlabel('固定比例的评估质量差（B8L2 分）')
    axs[1].set_title('B  所有有容量的评估图片',loc='left',fontsize=12,pad=13)
    fig.text(.08,.957,'漂亮配比经过重抽与跨图片检查后，优势大多消失',fontsize=17,weight='bold')
    fig.text(.08,.902,'五个发现后冻结的比例全部保留；没有只挑复现成功者。',fontsize=11,color='#52687c')
    lines=[
      'P01/P02：反向新批两类 3:1（n4）/ 3:2（n5）；P03：高 Q 快慢 2:1（n3）。',
      'P04/P05：正向新批多变量三类 0:1:2（n3）/ 1:3:1（n5）。A 为不同规则各自的发现赢家图片。',
      'B 按图片内、建筑内平均后等权汇总；失败率另存，小表同时提供全部可用与各臂完整两种口径。',
      '“最好纯类”是已测纯类总体均值的描述性对照；这些曲线不代表采集前可知道哪个纯类最好。']
    for i,line in enumerate(lines):fig.text(.08,.158-.031*i,line,fontsize=9,color='#52687c')
    p=a.out/'04_ratio_replication.png';fig.savefig(p,dpi=190);plt.close(fig)

    s=pd.read_csv(root/'local_census/results/finite_population_summary.csv')
    t=pd.read_csv(root/'local_census/results/finite_team_evidence.csv.gz')
    order=[s.iloc[1],s.iloc[2],s.iloc[3],s.iloc[0]]
    names=['纯 C01（5:0:0）','纯 C02（0:5:0）','纯 C03（0:0:5）','混类（1:3:1）']
    cs=['#8b6fa9','#d29842','#3b92ae','#cb5546']
    fig,axs=plt.subplots(2,2,figsize=(11.2,8.2))
    fig.subplots_adjust(left=.09,right=.965,top=.86,bottom=.205,hspace=.5,wspace=.34)
    for row,name,color in zip(order,names,cs):
        x=np.sort(t.loc[t.composition_id==row.composition_id,'B8L2'].dropna().to_numpy())
        axs[0,0].plot(x,np.arange(1,len(x)+1)/len(x),color=color,lw=2,label=f'{name} / {len(x)} 队')
    axs[0,0].set_xlabel('B8L2');axs[0,0].set_ylabel('所有可行团队的累计比例')
    axs[0,0].set_title('A  团队穷举：混类分布没有整体领先',loc='left',fontsize=11)
    axs[0,0].legend(fontsize=8,loc='upper left',frameon=False)
    x=np.arange(4)
    axs[0,1].scatter(x,[q.B8L2_mean for q in order],color=cs,s=65,label='总体均值',zorder=4)
    axs[0,1].scatter(x,[q.Q_p10 for q in order],color=cs,s=40,marker='v',label='低 10% 分位',zorder=4)
    axs[0,1].scatter(x,[q.Q_min for q in order],color=cs,s=33,marker='x',label='最小值',zorder=4)
    for i,q in enumerate(order):
        axs[0,1].plot([i,i],[q.Q_min,q.B8L2_mean],color=cs[i],alpha=.4)
        axs[0,1].text(i,q.B8L2_mean+1.4,f'{q.B8L2_mean:.2f}',ha='center',fontsize=9)
    axs[0,1].set_xticks(x,['纯 C01','纯 C02','纯 C03','混类']);axs[0,1].set_ylim(40,91)
    axs[0,1].set_title('B  均值与低尾分别看',loc='left',fontsize=11)
    axs[0,1].legend(fontsize=8,ncol=3,loc='lower right',frameon=False)
    vals=[float(winners.loc[winners.rule_id=='P05','discovery'].iloc[0]),float(winners.loc[winners.rule_id=='P05','replication'].iloc[0]),float(s.iloc[0].B8L2_mean-max(q.B8L2_mean for q in order[:3]))]
    axs[1,0].plot(range(3),vals,'o-',color=cs[-1],lw=2)
    for i,y in enumerate(vals):axs[1,0].text(i,y+.5,f'{y:+.3f}',ha='center',fontsize=11)
    axs[1,0].axhline(0,color='#bdc6ce',lw=.8);axs[1,0].set_ylim(-1,14.5);axs[1,0].set_xlim(-.28,2.28)
    axs[1,0].set_xticks(range(3),['发现样本','同图新成员','有限总体全算'])
    axs[1,0].set_ylabel('混类 − 最好纯类（B8L2 分）')
    axs[1,0].set_title('C  最后一个正例继续追到底',loc='left',fontsize=11)
    axs[1,1].bar(x-.17,[q.within_joint_stable_main*100 for q in order],width=.32,color='#7998b1',label='旧主联合判据')
    axs[1,1].bar(x+.17,[q.within_geometry_shape_main*100 for q in order],width=.32,color='#386d8c',label='固定新形状判据')
    axs[1,1].set_xticks(x,['纯 C01','纯 C02','纯 C03','混类']);axs[1,1].set_ylim(0,30)
    axs[1,1].set_ylabel('同构成两队相近率（%）')
    axs[1,1].set_title('D  微弱均值优势没有带来可互换',loc='left',fontsize=11)
    axs[1,1].legend(frameon=False,fontsize=8,loc='upper left')
    fig.text(.09,.963,'局部有限总体：1:3:1 的优势从 11.90 分缩至 0.40 分',fontsize=16,weight='bold')
    fig.text(.09,.918,'jtcxE69GiFV-03｜n=5｜正向新批多变量三类，每类在该图均有 8 人｜24 人 / 1 图 / 1 楼',fontsize=10,color='#52687c')
    lines=[
      '本图全部 3,752 个团队完成原生融合：混类 3,584 队，三种纯类各 56 队；没有遗漏团队。',
      '两队比较并非全部穷举：混类 6,420,736 对中固定种子抽 2,000 对，纯类各 1,540 对全算。',
      'D 为这些已声明团队对的描述统计；不同纯/混构成的实际换人数分布不同，另表按实际换人数分层。',
      '各队均为 4 节点；该例主要是范围偏差的平衡，不是恢复缺失节点。来源：local_census/results。']
    for i,line in enumerate(lines):fig.text(.09,.144-.027*i,line,fontsize=9,color='#52687c')
    p=a.out/'05_ratio_finite_census.png';fig.savefig(p,dpi=190);plt.close(fig)
    (a.out/'RATIO_FIGURE_RECEIPT.json').write_text(json.dumps({
      'figures':[{'file':p.name,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted(a.out.glob('0[45]_*.png'))],
      'all_data_from_compact_tables':True,'mixture_team_pairs_exhaustive':False},ensure_ascii=False,indent=2)+'\n')


if __name__=='__main__':main()
