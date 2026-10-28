#!/usr/bin/env python3
"""Publication-style charts from saved room-purpose image results only."""
import argparse
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager

MAJOR=['卧室','卫浴','通行与连接','起居与休闲','厨房与用餐','工作与学习']
COLORS=['#2b719c','#cb7541','#6a8d3b']

def main():
    p=argparse.ArgumentParser();p.add_argument('--study',type=Path,required=True);a=p.parse_args();root=a.study;r=root/'results/image';o=root/'figures';o.mkdir(exist_ok=True)
    fp=root/'assets/NotoSansCJKsc-Regular.otf'
    if fp.exists():font_manager.fontManager.addfont(str(fp));plt.rcParams['font.family']=font_manager.FontProperties(fname=str(fp)).get_name()
    plt.rcParams.update({'axes.unicode_minus':False,'axes.spines.top':False,'axes.spines.right':False,'font.size':11,'axes.titlesize':13,'figure.facecolor':'white','savefig.facecolor':'white'})
    d=pd.read_csv(root/'inputs/images.csv');d=d[(d.condition=='manual')&(d.layer=='ordinary')]
    standard=pd.read_csv(r/'DIFFICULTY_STANDARDIZED_PURPOSE.csv');standard=standard[standard.metric=='mean_Q'].set_index('purpose').loc[MAJOR]
    fig,axs=plt.subplots(1,3,figsize=(15,5.7),layout='constrained');x=np.arange(6)
    ax=axs[0];ax.plot(x,standard.raw_mean,'o-',lw=1.5,color=COLORS[0],label='原图片等权均Q');ax.plot(x,standard.standardized_mean,'s--',lw=1.5,color=COLORS[1],label='统一难度构成后的均Q')
    ax.set(xticks=x,xticklabels=MAJOR,ylabel='B8L2（分）',title='用途排序会随难度构成改变',ylim=(55,82));ax.tick_params(axis='x',rotation=45);ax.grid(axis='y',alpha=.2);ax.legend(frameon=False,fontsize=9)
    ax=axs[1];bottom=np.zeros(6)
    for difficulty,color in zip(['简单','中等','困难'],COLORS):
        vals=np.array([(d[d.room_type_model==p].difficulty==difficulty).mean() for p in MAJOR]);ax.bar(x,vals*100,bottom=bottom*100,color=color,label=difficulty);bottom+=vals
    for i,purpose in enumerate(MAJOR):
        s=d[d.room_type_model==purpose];ax.text(i,102,f'{len(s)}图/{s.building.nunique()}楼',ha='center',fontsize=8)
    ax.set(xticks=x,xticklabels=MAJOR,ylabel='用途内图片比例（%）',title='同一用途也包含不同难度',ylim=(0,110));ax.tick_params(axis='x',rotation=45);ax.legend(frameon=False,fontsize=9,ncol=3,loc='lower right')
    ax=axs[2]
    rng=np.random.default_rng(2026102703)
    for i,purpose in enumerate(MAJOR):
        s=d[d.room_type_model==purpose]
        for difficulty,color in zip(['简单','中等','困难'],COLORS):
            y=s[s.difficulty==difficulty].mean_Q.to_numpy();ax.scatter(np.full(len(y),i)+rng.uniform(-.16,.16,len(y)),y,s=20,alpha=.75,color=color)
        ax.plot([i-.25,i+.25],[s.mean_Q.mean()]*2,color='black',lw=1.5)
    ax.set(xticks=x,xticklabels=MAJOR,ylabel='逐图平均 B8L2（分）',title='用途内差异不能用一个均值代替',ylim=(15,100));ax.tick_params(axis='x',rotation=45);ax.grid(axis='y',alpha=.2)
    fig.suptitle('普通 Manual 六大用途（155图）：用途、难度构成与图片平均质量',fontsize=16)
    fig.savefig(o/'I01_PURPOSE_DIFFICULTY.png',dpi=180);plt.close(fig)
    f=r/'MATCHED_CONTRAST_SUMMARY.csv'
    if f.exists():
        s=pd.read_csv(f);s=s[s.purpose=='ALL'];fig,axs=plt.subplots(1,3,figsize=(14,5),layout='constrained')
        regs=['source_building','source_building_difficulty','source_building_difficulty_geometry'];labels=['同源建筑\n共同人员','＋源图难度相同','＋近似参考几何']
        for ax,(metric,title,unit) in zip(axs,[('Q_common_mean_absdiff','图片均Q的相似性','均Q绝对差（分）'),('Q_common_relative_absdiff','个人相对表现的相似性','逐人相对Q绝对差（分）'),('turn_delta_common_mean_absdiff','相对参考的结构表达','平均转折差的绝对差')]):
            q=s[s.metric==metric].set_index('regime').loc[regs];xx=np.arange(3)
            ax.plot(xx,q.same,'o-',color=COLORS[0],label='同用途');ax.plot(xx,q.different,'s--',color=COLORS[1],label='异用途')
            for i,row in enumerate(q.itertuples()):ax.annotate(f'Δ={row.difference_image_equal:+.2f}\n{row.n_images}图',xy=(i,max(row.same,row.different)),xytext=(0,9),textcoords='offset points',ha='center',fontsize=9)
            ax.set(xticks=xx,xticklabels=labels,title=title,ylabel=unit,ylim=(0,max(q.same.max(),q.different.max())*1.25));ax.grid(axis='y',alpha=.2)
        axs[0].legend(frameon=False);fig.suptitle('较宽三图对照：目标T固定，外楼同用途与异用途源图比较\n后两项约束源图S/C，未强制T与源图同难度',fontsize=14)
        fig.savefig(o/'I02_MATCHED_PURPOSE_SIMILARITY.png',dpi=180);plt.close(fig)
    f=r/'LOBO_PREDICTION_SUMMARY.csv'
    if f.exists():
        s=pd.read_csv(f);s=s[(s.metric=='Q')&(s.subset=='ALL')].set_index('method')
        methods=['training_mean','purpose_only','difficulty','difficulty_purpose','geometry_rich','geometry_purpose_rich','geometry_history','geometry_history_purpose'];labels=['训练图平均','仅用途','难度','难度＋用途','难度＋参考几何','几何＋用途','几何＋人员历史','几何＋人员历史＋用途']
        fig,axs=plt.subplots(1,2,figsize=(13,6.5),layout='constrained');ax=axs[0];v=s.loc[methods,'mae'];yy=np.arange(len(methods));ax.barh(yy,v,color=[COLORS[1] if 'purpose' in x else COLORS[0] for x in methods]);ax.set(yticks=yy,yticklabels=labels,xlabel='留一建筑：图片均Q预测 MAE（分，低为好）',title='177张普通 Manual 图片／22栋建筑');ax.invert_yaxis();ax.set_xlim(0,max(v)*1.2)
        for i,value in enumerate(v):ax.text(value+.15,i,f'{value:.2f}',va='center',fontsize=10)
        g=pd.read_csv(r/'LOBO_INCREMENT_SUMMARY.csv');g=g[(g.metric=='Q')&(g.method=='geometry_purpose_rich')&(g.baseline=='geometry_rich')&g.subset.isin(['REPEATED_RECORDED_PURPOSE']+MAJOR)].set_index('subset').reindex(['REPEATED_RECORDED_PURPOSE']+MAJOR)
        ax=axs[1];yy=np.arange(len(g));ax.barh(yy,g.gain_image_equal,color=[COLORS[0] if z>0 else COLORS[1] for z in g.gain_image_equal]);ax.set(yticks=yy,yticklabels=['有外楼同用途历史161图']+MAJOR,xlabel='加入用途后的 MAE 改善（分，正为好）',title='相同候选模型库：难度＋参考几何 → 再加用途');ax.invert_yaxis();ax.axvline(0,color='#555',lw=.8);ax.grid(axis='x',alpha=.15)
        for i,row in enumerate(g.itertuples()):ax.annotate(f'{row.gain_image_equal:+.2f}\n{int(row.improved_images)}/{int(row.images)}图改善',xy=(row.gain_image_equal,i),xytext=(5 if row.gain_image_equal>=0 else -5,0),textcoords='offset points',va='center',ha='left' if row.gain_image_equal>=0 else 'right',fontsize=9)
        ax.margins(x=.45);fig.suptitle('跨建筑留出检验：用途增加了多少目标图质量信息？',fontsize=15)
        fig.savefig(o/'I03_LOBO_IMAGE_PREDICTION.png',dpi=180);plt.close(fig)
    f=r/'MATCHED_ALL_THREE_SAME_DIFFICULTY_SUMMARY.csv'
    if f.exists():
        q=pd.read_csv(f);q=q[q.purpose=='ALL'].set_index('metric');fig,axs=plt.subplots(1,3,figsize=(13.5,5.5),layout='constrained')
        for ax,(metric,title,unit) in zip(axs,[('Q_common_mean_absdiff','图片公共均值更接近','共同人员均Q的绝对差（分）'),('Q_common_relative_absdiff','个人相对表现没有同时更接近','逐人相对Q的绝对差（分）'),('turn_delta_common_mean_absdiff','相对参考的结构表达也未同步','平均转折差的绝对差（个）')]):
            row=q.loc[metric];v=[row.same,row.different];ax.bar([0,1],v,color=COLORS[:2],width=.6)
            for i,value in enumerate(v):ax.text(i,value+max(v)*.025,f'{value:.3f}',ha='center',fontsize=12)
            ax.set(xticks=[0,1],xticklabels=['同用途','异用途'],ylabel=unit,title=title,ylim=(0,max(v)*1.32));ax.grid(axis='y',alpha=.15);ax.set_axisbelow(True)
            ax.text(.5,.94,f'同−异 = {row.effect_image_equal:+.3f}',ha='center',transform=ax.transAxes,fontsize=11)
            ax.text(.5,-.15,f'{int(row.negative_images)}图更近／{int(row.positive_images)}图更远／{int(row.near_zero_images)}图不变',ha='center',transform=ax.transAxes,fontsize=10)
        fig.suptitle('T/S/C 三图均同难度：150张目标图／21栋建筑\n固定目标、同一源楼、三图共同人员；异用途源图按参考几何接近程度选取',fontsize=14)
        fig.savefig(o/'I04_ALL_THREE_SAME_DIFFICULTY.png',dpi=180);plt.close(fig)
    print('wrote',sorted(x.name for x in o.glob('I0*.png')))

if __name__=='__main__':main()
