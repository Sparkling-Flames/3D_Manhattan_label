"""Scientific overview of every frozen candidate on the registered main grid."""
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties

w=Path(__file__).resolve().parents[1]
font=FontProperties(fname=w/'cases/source/NotoSansCJKsc-Regular.otf')
d=pd.read_csv(w/'analysis/global_screen_summary/METHOD_GRID_RESULTS.csv')
d=d[(d.condition=='manual')&(d.scope=='primary')]
grid=[(6,2),(8,4),(10,3),(10,7),(12,4),(12,6),(12,8),(14,7),(16,4),(18,7),(20,5),(20,6),(24,4),(26,3)]
methods=sorted(d.method.unique())
fig,axs=plt.subplots(1,2,figsize=(15,15),sharey=True,gridspec_kw={'wspace':.12})
for ax,metric,title,lim in zip(axs,['B8L2_gap_mean_image','geometry_pair_angle_gap_mean_image'],['Q：跨类幅度 − 同类幅度（分）','融合角点联合角距：跨类 − 同类（度）'],[4,2]):
    a=np.full((len(methods),len(grid)),np.nan)
    for i,m in enumerate(methods):
        for j,(n,k) in enumerate(grid):
            r=d[(d.method==m)&(d.n==n)&(d.m==k)]
            if len(r):a[i,j]=r.iloc[0][metric]
    cmap=plt.get_cmap('RdBu_r').copy();cmap.set_bad('#e8e8e8')
    im=ax.imshow(a,cmap=cmap,vmin=-lim,vmax=lim,aspect='auto')
    ax.set_xticks(range(len(grid)),[f'{n}/{m}' for n,m in grid],rotation=60,ha='right',fontsize=9)
    ax.set_yticks(range(len(methods)),methods,fontsize=8.5)
    ax.set_xlabel('团队人数 n / 实际替换人数 m',fontproperties=font,fontsize=11)
    ax.set_title(title,fontproperties=font,fontsize=12,pad=15)
    ax.set_xticks(np.arange(-.5,len(grid),1),minor=True);ax.set_yticks(np.arange(-.5,len(methods),1),minor=True)
    ax.grid(which='minor',color='white',linewidth=.4);ax.tick_params(which='minor',bottom=False,left=False)
    fig.colorbar(im,ax=ax,fraction=.03,pad=.025,extend='both')
fig.suptitle('v2.1 全候选广筛：45种冻结分类 × 14个主要人数配置',fontproperties=font,fontsize=17,y=.975)
fig.text(.12,.025,'每格先汇总该法全部可行方向，再目标／图片等权；灰格为无可评支持。\n红色表示跨类变化更大，蓝色表示同类变化更大；不代表质量改善。每法实际支持及有符号结果另表保留。',fontproperties=font,fontsize=10)
fig.subplots_adjust(left=.23,right=.97,top=.93,bottom=.11)
out=w/'stage05';out.mkdir(exist_ok=True)
fig.savefig(out/'GLOBAL45_METHOD_NM_COMPARISON.png',dpi=180,bbox_inches='tight')
fig.savefig(out/'GLOBAL45_METHOD_NM_COMPARISON.pdf',bbox_inches='tight')
plt.close(fig)
