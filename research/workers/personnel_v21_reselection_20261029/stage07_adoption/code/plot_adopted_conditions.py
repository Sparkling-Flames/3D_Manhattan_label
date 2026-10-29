"""Static research figures from saved image-equal effects, not illustrative data."""
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties

W=Path(__file__).resolve().parents[2]
O=W/'stage07_adoption'
F=FontProperties(fname=W/'cases/source/NotoSansCJKsc-Regular.otf')
d=pd.read_csv(O/'ALL32_EXTENDED_CONDITIONS_COMPLETE.csv')
picks=[('OPPJOINT_K4',12,6),('OPPJOINT_K4',20,5),('OPPJOINT_K4',26,3),('TARGET_DSTRUCT_K3',14,7),('TARGET_DSTRUCT_K3',18,7),('TARGET_DSTRUCT_K3',20,6),('RFUSE_GEOM_K2',12,4),('MSDGEOM_SCOPE_K4',14,7),('OPPGEOM_K3',14,7)]
x=pd.concat([d[(d.method==m)&(d.n==n)&(d.m==k)] for m,n,k in picks],ignore_index=True)
labels=[f'{m.replace("TARGET_DSTRUCT", "目标结构").replace("MSDGEOM_SCOPE", "跨条件+scope")}  {n}/{k}' for m,n,k in picks]
fig,ax=plt.subplots(figsize=(13,7.5));y=np.arange(len(x))
ax.barh(y-.17,x.B8L2_within_mean_image,height=.31,color='#84939e',label='同类换人 |B−A|')
ax.barh(y+.17,x.B8L2_cross_mean_image,height=.31,color='#197f91',label='跨类平均幅度 (|C−A|+|C−B|)/2')
ax.set_yticks(y,labels,fontproperties=F,fontsize=10)
for i,r in x.iterrows():
    ax.text(r.B8L2_within_mean_image+.09,i-.17,f'{r.B8L2_within_mean_image:.2f}',fontsize=9,va='center')
    ax.text(r.B8L2_cross_mean_image+.09,i+.17,f'{r.B8L2_cross_mean_image:.2f}',fontsize=9,va='center')
    ax.text(11.4,i,f'{int(r.B8L2_gap_positive_images)}/{int(r.B8L2_gap_valid_images)}',ha='center',va='center',fontsize=10)
    ax.text(13.3,i,f'{r.B8L2_CB_mean_image:+.2f}',ha='center',va='center',fontsize=10)
    ax.text(15.3,i,f'{r.record_time_CB_pct_source_matched_mean_image:+.1f}%',ha='center',va='center',fontsize=10)
for pos,title in [(11.4,'跨类更大图'),(13.3,'净Q：C−B'),(15.3,'记录时间 C−B')]:ax.text(pos,-.8,title,fontproperties=F,ha='center',fontsize=10)
ax.set_xlim(0,16.4);ax.set_xticks([0,2,4,6,8,10]);ax.set_ylim(len(x)-.5,-1.15)
ax.set_xlabel('Q绝对变化幅度（分）；每图先汇总实际成员与背景，再图片等权',fontproperties=F,fontsize=10)
ax.axvline(10.9,color='#dddddd',lw=.8);ax.grid(axis='x',alpha=.13);ax.set_axisbelow(True)
ax.spines[['top','right']].set_visible(False)
ax.legend(prop=F,loc='lower right',bbox_to_anchor=(1,-.21),ncol=2,frameon=False,fontsize=9)
fig.suptitle('v2.1：主联合家族与有独立用途的分类条件',fontproperties=F,fontsize=17,y=.98)
fig.text(.02,.025,'n/m表示团队人数/实际替换人数。各行采用其全部可行扩展支持，不是共同图片的算法排名。\n时间为来源匹配的库存记录总秒数百分比；正数表示增加。OPPJOINT四细层主方向跨越三粗层父类。',fontproperties=F,fontsize=9)
fig.subplots_adjust(left=.29,right=.98,top=.9,bottom=.18)
fig.savefig(O/'MAIN_CONDITION_COMPARISON.png',dpi=200,bbox_inches='tight')
fig.savefig(O/'MAIN_CONDITION_COMPARISON.pdf',bbox_inches='tight');plt.close(fig)

# Difficulty comparison from saved per-image results and the frozen official grade.
im=pd.read_csv(W/'analysis/focused_summary/DIRECTION_IMAGE_RESULTS.csv.gz')
t=pd.read_csv(W/'targets/POOL_TARGET_CONDITIONS.csv')
grade_col='official_difficulty'
grades=t[['image',grade_col]].dropna().drop_duplicates()
assert not grades.image.duplicated().any()
im=im.merge(grades,on='image',how='left',validate='many_to_one')
rows=[]
for m,n,k in [('OPPJOINT_K4',12,6),('OPPJOINT_K4',20,5),('TARGET_DSTRUCT_K3',14,7)]:
    for g in ['简单','中等','困难']:
        q=im[(im.method==m)&(im.n==n)&(im.m==k)&im[grade_col].eq(g)]
        rows.append(dict(label=f'{m.replace("TARGET_DSTRUCT_K3","目标结构 K3").replace("OPPJOINT_K4","联合 K4")} {n}/{k} · {g}',grade=g,
                         q=q.B8L2_CB.mean(),turn=q.fusion_turn_n_CB.mean(),time=q.record_time_CB_pct_source_matched.mean(),N=q.B8L2_CB.count(),wins=(q.B8L2_CB>0).sum(),timeN=q.record_time_CB_pct_source_matched.count()))
r=pd.DataFrame(rows);r.to_csv(O/'FIGURE_DIFFICULTY_DATA.csv',index=False)
fig,axs=plt.subplots(1,3,figsize=(13,6),sharey=True,gridspec_kw={'width_ratios':[1.4,1,1],'wspace':.13})
colors=r.grade.map({'简单':'#268d9e','中等':'#e3a340','困难':'#b44c54'})
for ax,c,title in zip(axs,['q','turn','time'],['净Q：C−B（分）','转折变化：C−B（个）','记录时间：C−B（%）']):
    ax.barh(np.arange(len(r)),r[c],color=colors,height=.65)
    ax.axvline(0,color='#777777',lw=.7);ax.grid(axis='x',alpha=.14);ax.set_axisbelow(True)
    ax.spines[['top','right']].set_visible(False);ax.set_title(title,fontproperties=F,fontsize=11)
    lo,hi=ax.get_xlim();pad=(hi-lo)*.02
    for i,row in r.iterrows():
        val=row[c];text=f'{val:+.2f}'
        if c=='q':text+=f'  ({int(row.wins)}/{int(row.N)})'
        if c=='time':text+=f'  ({int(row.timeN)}图)'
        ax.text(max(val,0)+pad,i,text,va='center',ha='left',fontsize=8,fontproperties=F)
    ax.set_xlim(min(lo,-2 if c=='q' else lo),hi+(hi-lo)*(.45 if c=='q' else .5))
axs[0].set_yticks(np.arange(len(r)),r.label,fontproperties=F,fontsize=9);axs[0].invert_yaxis()
fig.suptitle('同一分类方向在简单、中等与困难图上的作用不同',fontproperties=F,fontsize=16,y=.99)
fig.text(.02,.025,'仅采用已有正式难度，不把其它目标的计算结构条件冒充人工难度。括号为净Q提高图/可评图，时间列单独注明分母。\n简单图也可改善：转折数不变时，变化主要在位置、上下界或尺度。困难图的结构收益更大，但并非每个规模、每张图都同向。',fontproperties=F,fontsize=9)
fig.subplots_adjust(left=.24,right=.98,top=.88,bottom=.18)
fig.savefig(O/'DIFFICULTY_ROLE_EFFECTS.png',dpi=200,bbox_inches='tight')
fig.savefig(O/'DIFFICULTY_ROLE_EFFECTS.pdf',bbox_inches='tight');plt.close(fig)
print('Two figures and exact figure data saved.')
