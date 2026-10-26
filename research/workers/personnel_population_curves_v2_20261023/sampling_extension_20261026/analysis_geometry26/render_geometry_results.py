"""Publication-style geometry figures from completed fixed-support tables."""
from __future__ import annotations
import argparse,io,os
from pathlib import Path
import pandas as pd
os.environ.setdefault('MPLCONFIGDIR','/tmp/hohonet_geometry_matplotlib26')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
from safe_io import atomic_bytes

COLORS={'old48':'#66717e','new208':'#247ba0','pooled256':'#28784b'}
LABELS={'old48':'原 48 条','new208':'独立新增 208 条','pooled256':'主样本 256 条'}

def save(fig,out,name):
    for ext in ['png','pdf']:
        memory=io.BytesIO();fig.savefig(memory,format=ext,dpi=190,bbox_inches='tight');atomic_bytes(out/(name+'.'+ext),memory.getvalue())
    plt.close(fig)

def all_k(g):
    """Retain the visible k=2 gap instead of drawing a fictitious interpolation."""
    if not len(g):return g
    return g.set_index('k').reindex(range(1,int(g.k.max())+1)).rename_axis('k').reset_index()

def show_k1(ax,g,field,color):
    point=g[g.k.eq(1)]
    if len(point):ax.scatter(point.k,point[field],s=15,color=color,zorder=6,linewidths=.4,edgecolors='white')

def render(root):
    font=root.parent/'assets/NotoSansCJKsc-Regular.otf'
    if font.exists():
        font_manager.fontManager.addfont(str(font));plt.rcParams['font.family']=font_manager.FontProperties(fname=str(font)).get_name()
    plt.rcParams['axes.unicode_minus']=False
    out=root/'figures';out.mkdir(exist_ok=True)
    d=pd.read_csv(root/'results_stage2/GEOMETRY_STRICT_COMMON_CURVE_SUMMARY.csv.gz')
    d=d[d.weighting.eq('image_equal')]
    door=d[d.layer.eq('doorway_manual')]
    door_candidates=door[['panel','candidate_images']].drop_duplicates()
    max_images=door_candidates.candidate_images.max()
    door_panel=sorted(door_candidates[door_candidates.candidate_images.eq(max_images)].panel.unique(),key=lambda s:int(s.rsplit('_',1)[1]))[-1]
    panels=[('ordinary_manual','fixed_N_ge_30','简单','简单'),('ordinary_manual','fixed_N_ge_30','中等','中等'),
            ('ordinary_manual','fixed_N_ge_30','困难','困难'),('doorway_manual',door_panel,'单列','门洞交界')]
    fig,axes=plt.subplots(2,4,figsize=(13.5,6.5),constrained_layout=True,sharex='col')
    for col,(layer,panel,difficulty,label) in enumerate(panels):
        x=d[d.layer.eq(layer)&d.panel.eq(panel)&d.difficulty.eq(difficulty)&d.metric.eq('V_floor')]
        for cohort,color in COLORS.items():
            g=all_k(x[x.cohort.eq(cohort)].sort_values('k'))
            axes[0,col].plot(g.k,g.estimate,color=color,label=LABELS[cohort],lw=1.6,ls='--' if cohort=='old48' else '-')
            show_k1(axes[0,col],g,'estimate',color)
            axes[1,col].plot(g.k,g.image_mcse_median,color=color,lw=1.6,ls='--' if cohort=='old48' else '-')
            show_k1(axes[1,col],g,'image_mcse_median',color)
            if cohort in ['old48','pooled256']:
                axes[1,col].plot(g.k,g.image_mcse_p90,color=color,lw=.8,ls=':')
                show_k1(axes[1,col],g,'image_mcse_p90',color)
        cand=int(x.candidate_images.iloc[0]);common=int(x.common_images.iloc[0]);buildings=int(x.common_buildings.iloc[0])
        axes[0,col].set_title(f'{label}\n全曲线共同 {common}/{cand} 图 / {buildings} 栋建筑',loc='left',fontsize=10,fontweight='bold')
        axes[1,col].set_xlabel('团队人数 k')
        for row in [0,1]:
            ax=axes[row,col];ax.set_ylim(bottom=0);ax.grid(alpha=.18);ax.spines[['top','right']].set_visible(False)
        axes[0,col].set_ylabel('平均地面几何波动 V')
        axes[1,col].set_ylabel('单图 V 的蒙特卡洛标准误')
    axes[0,0].legend(frameon=False,fontsize=8,loc='upper right')
    fig.suptitle('整条人数曲线的几何波动与单图抽样精度',fontsize=14)
    fig.supxlabel('上：完整有效地面的图等权 V；下：单图经验 MCSE 中位数，点线为第90百分位。孤立点显示1人；2人暂缓，未补零。',fontsize=9)
    save(fig,out,'F01_GEOMETRY_FULL_CURVE_AND_PRECISION')
    metrics=[('V_floor','地面：E[1−IoU]'),('V_centroid_h','质心距离 / 相机高度'),
        ('V_height_h','平均高度绝对差 / 相机高度'),('V_turn5','实际转折数绝对差'),('V_nodes','输出节点数绝对差')]
    fig,axes=plt.subplots(2,3,figsize=(11.6,6.8),constrained_layout=True)
    x=d[d.layer.eq('ordinary_manual')&d.panel.eq('fixed_N_ge_30')&d.difficulty.eq('全部')]
    for ax,(metric,title) in zip(axes.ravel(),metrics):
        for cohort,color in COLORS.items():
            g=all_k(x[x.metric.eq(metric)&x.cohort.eq(cohort)].sort_values('k'))
            ax.plot(g.k,g.estimate,color=color,lw=1.7,ls='--' if cohort=='old48' else '-',label=LABELS[cohort])
            show_k1(ax,g,'estimate',color)
            if cohort=='pooled256':ax.fill_between(g.k,g.estimate-1.96*g.path_mcse,g.estimate+1.96*g.path_mcse,color=color,alpha=.13)
        own=x[x.metric.eq(metric)&x.cohort.eq('pooled256')]
        common=int(own.common_images.iloc[0]);candidate=int(own.candidate_images.iloc[0])
        ax.set_title(title+f'\n全曲线共同 {common}/{candidate} 图',loc='left',fontsize=10);ax.set_ylim(bottom=0);ax.grid(alpha=.18);ax.spines[['top','right']].set_visible(False);ax.set_xlabel('团队人数 k')
    axes[1,2].axis('off');axes[0,0].legend(frameon=False,fontsize=8)
    axes[1,2].text(0,.94,'固定普通 Manual 候选范围\n157 张图 / 22 栋建筑\n\n各分量共同支持见子图标题\n完整有效地面条件分布\n呈现1至30人的实际结果\n1人以孤立点显示；2人暂缓\n\n色带：路径 Monte Carlo ±1.96 SE\n跨建筑差异在独立重抽表中报告',va='top',fontsize=10)
    fig.suptitle('不同几何分量的波动可以有不同变化',fontsize=14)
    save(fig,out,'F02_GEOMETRY_COMPONENT_CURVES')
    # The fixed N>=35 panel is actually N=35 throughout: retain all k rather
    # than switching to different images at 30/35. Full endpoint V=0 is the
    # finite team-space identity, not an extra independent result per path.
    x=d[d.layer.eq('ordinary_manual')&d.panel.eq('fixed_N_ge_35')&d.difficulty.eq('全部')]
    fig,axes=plt.subplots(1,3,figsize=(12.2,3.8),constrained_layout=True)
    for ax,(metric,title) in zip(axes,[metrics[0],metrics[2],metrics[4]]):
        for cohort,color in COLORS.items():
            g=all_k(x[x.metric.eq(metric)&x.cohort.eq(cohort)].sort_values('k'))
            ax.plot(g.k,g.estimate,color=color,lw=1.7,ls='--' if cohort=='old48' else '-',label=LABELS[cohort])
            show_k1(ax,g,'estimate',color)
        own=x[x.metric.eq(metric)&x.cohort.eq('pooled256')]
        common=int(own.common_images.iloc[0]);candidate=int(own.candidate_images.iloc[0]);buildings=int(own.common_buildings.iloc[0])
        ax.set_title(title+f'\n全曲线共同 {common}/{candidate} 图 / {buildings} 楼',loc='left',fontsize=10)
        ax.set_ylim(bottom=0);ax.grid(alpha=.18);ax.spines[['top','right']].set_visible(False);ax.set_xlabel('团队人数 k')
        ax.axvline(35,color='#666666',ls=':',lw=.7)
    axes[0].legend(frameon=False,fontsize=8)
    fig.suptitle('固定35人池：保留1至35人的完整几何过程',fontsize=13)
    fig.supxlabel('满员只有同一支团队，合法输出的换组波动为0；该端点重复路径不是新的独立团队。1人以孤立点显示；2人暂缓。',fontsize=9)
    save(fig,out,'F03_GEOMETRY_FIXED35_FULL_CURVE')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);a=p.parse_args();render(a.root.resolve())
