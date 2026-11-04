"""Scientific six-direction figure, built only from the adopted AC table."""
from pathlib import Path
import argparse,os
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
import pandas as pd
import numpy as np

HERE=Path(__file__).resolve().parent
def font_path(given):
    candidates=[given,os.environ.get('HOHONET_CJK_FONT'),
                'C:/Windows/Fonts/msyh.ttc','C:/Windows/Fonts/simhei.ttf',
                '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc',
                '/System/Library/Fonts/PingFang.ttc']
    for p in candidates:
        if p and Path(p).is_file():return p
    return None
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--font');args=ap.parse_args()
    font=font_path(args.font)
    if font:
        font_manager.fontManager.addfont(font)
        plt.rcParams['font.family']=font_manager.FontProperties(fname=font).get_name()
    plt.rcParams.update({'axes.unicode_minus':False,'font.size':11,'svg.fonttype':'path','savefig.facecolor':'white'})
    df=pd.read_csv(HERE/'analysis/CORE_READABLE_RESULTS.csv')
    df=df[(df.analysis_cohort=='legacy_plus_capacity_gap')&(df.version=='automatic')&(df.support=='original_common')]
    dirs=['C1_to_C2','C2_to_C1','C1_to_C3','C3_to_C1','C2_to_C3','C3_to_C2']
    colors=['#b67717','#b67717','#4b66ae','#4b66ae','#147d75','#147d75']
    fig,axs=plt.subplots(1,2,figsize=(16,7.8),sharey=True)
    y=np.array([5.5,4.5,3.15,2.15,.8,-.2])
    for ax,n in zip(axs,[14,20]):
        q=df[df.n.eq(n)&df.m.eq(7)].set_index('direction').loc[dirs]
        ax.axvspan(-1,1,color='#eef1f3',zorder=0)
        ax.axvline(0,color='#8f9fa8',lw=.9,zorder=0)
        for i,(direction,row) in enumerate(q.iterrows()):
            mean=float(row.image_equal_mean);lo=float(row.cluster_bootstrap_low);hi=float(row.cluster_bootstrap_high)
            ax.plot([lo,hi],[y[i],y[i]],color=colors[i],lw=2.2,alpha=.9)
            ax.plot([lo,lo],[y[i]-.06,y[i]+.06],color=colors[i],lw=1.1)
            ax.plot([hi,hi],[y[i]-.06,y[i]+.06],color=colors[i],lw=1.1)
            ax.scatter(mean,y[i],s=64,marker='o',facecolor=colors[i] if i%2==0 else 'white',edgecolor=colors[i],linewidth=1.5,zorder=3)
            ax.text(9.25,y[i]+.12,f'{mean:+.2f}',ha='right',va='center',color=colors[i],fontweight='bold',fontsize=11)
            ax.text(9.25,y[i]-.18,f'{int(row.images)} 图 / {int(row.buildings)} 楼',ha='right',va='center',color='#52626e',fontsize=9)
        ax.set_xlim(-10,10);ax.set_ylim(-1,6.3);ax.set_xticks([-8,-4,0,4,8])
        ax.set_yticks(y,labels=[s.replace('_to_',' → ') for s in dirs]);ax.tick_params(axis='y',length=0,pad=12,labelleft=True)
        ax.set_xlabel('直接质量变化 ΔQ = Q(C) − Q(A)  / 分',labelpad=12)
        ax.set_title(f'n = {n}，m = 7  ·  替换 {7/n:.0%}',loc='left',fontweight='bold',fontsize=16,pad=18)
        ax.grid(axis='x',alpha=.17)
        for edge in ['top','right','left']:ax.spines[edge].set_visible(False)
        ax.spines['bottom'].set_color('#c8d1d8')
        ax.hlines([3.82,1.47],-9.5,9.5,color='#e3e8eb',lw=.8)
    fig.suptitle('当前 DSTRUCT 直接替换：六方向与实际支持',x=.065,y=.97,ha='left',fontsize=23,fontweight='bold',color='#1c3340')
    fig.text(.065,.91,'自动结果 · 普通 Manual 原目标 · 同图、同参考、同人数和共同背景 · 旧合法存量＋定向容量缺口补充',fontsize=11.5,color='#4f6572')
    fig.text(.065,.07,'线段：按建筑整簇重采样的 95% 区间。阴影：±1 分的描述性小变化范围。C1↔C3 的大预算支持仅 7 图。',fontsize=10,color='#455a66')
    fig.text(.065,.035,'空心点为同一物理对的反向镜像，方向翻号不增加独立证据；不同 n/m 与图片范围不能直接视为受控比例效应。',fontsize=10,color='#455a66')
    fig.subplots_adjust(left=.085,right=.97,bottom=.18,top=.83,wspace=.24)
    out=HERE/'figures';out.mkdir(exist_ok=True)
    for ext in ['png','svg']:fig.savefig(out/f'F01_CURRENT_DSTRUCT_AC_SIX_DIRECTIONS.{ext}',dpi=190)
    plt.close(fig)
    print(str(out/'F01_CURRENT_DSTRUCT_AC_SIX_DIRECTIONS.png'))

if __name__=='__main__':main()
