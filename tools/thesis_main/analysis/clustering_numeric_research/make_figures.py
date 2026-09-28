"""Quantitative figures, matplotlib default color cycle; no remote assets or fonts."""
from pathlib import Path
import json
import pandas as pd,numpy as np
import matplotlib.pyplot as plt
from common import ROOT

def main(results=None,figures=None,show=False):
    results=Path(results or ROOT/'results_recomputed');figures=Path(figures or ROOT/'figures_recomputed')
    if figures.resolve()==(ROOT/'figures').resolve():raise ValueError('Do not overwrite received figures')
    figures.mkdir(parents=True,exist_ok=True);saved=[]
    def finish(fig,name,caption):
        fig.tight_layout();fig.savefig(figures/name,dpi=170,bbox_inches='tight');saved.append(dict(file=name,caption=caption))
        if show:plt.show()
        plt.close(fig)
    exact=pd.read_csv(results/'high_support_exact_summary.csv');prefix=pd.read_csv(results/'high_support_prefix_summary.csv')
    for condition,number in [('manual',45),('semi',18),('oos',9)]:
        fig,ax=plt.subplots(figsize=(7.6,4.6));d=exact[(exact.condition==condition)&(exact.nominal_cut==9)&(exact.partition=='complete')]
        for metric,z in d.groupby('metric'):ax.plot(z.k,100*z.next_uncovered,label='Image distance (25.6 px)' if metric=='image' else 'Spherical distance (9 deg)')
        ax.set(xlabel='Number of observed distinct real annotators, k',ylabel='Next remaining response not covered (%)',title=f'{condition.capitalize()}: fixed panel of {number} high-support images',xlim=(1,18),ylim=(0,100));ax.legend();ax.grid(True,alpha=.25)
        finish(fig,f'01_coverage_{condition}.png',f'{condition}固定高人数面板的精确有限池成对未覆盖；分组规则不改变此量，N>=19，k<=18。')
    d=prefix[(prefix.condition=='manual')&(prefix.nominal_cut==9)]
    for field,ylabel,name in [('clusters_mean','Mean number of clusters','02_prefix_cluster_count.png'),('largest_share_mean','Mean largest-cluster share (%)','03_prefix_largest_share.png')]:
        fig,ax=plt.subplots(figsize=(7.6,4.6))
        for (metric,kind),z in d.groupby(['metric','partition']):ax.plot(z.k,z[field]*(100 if field=='largest_share_mean' else 1),label=f'{metric} / {kind}')
        ax.set(xlabel='Number of distinct real annotators, k',ylabel=ylabel,title='Manual: 45 images, 200 shared orders; prefix re-clustering',xlim=(1,18));ax.legend();ax.grid(True,alpha=.25)
        finish(fig,name,'相同人员、顺序和图像下，四方案的前缀重新分簇；不可用簇少、主簇大单独判断正确。')
    fig,ax=plt.subplots(figsize=(7.6,4.6));z=d[(d.metric=='image')&(d.partition=='complete')]
    ax.plot(z.k,z.clusters_mean,label='Re-cluster using only current prefix');ax.plot(z.k,z.fixed_clusters_mean,label='Assign full-pool hindsight labels to prefix')
    ax.set(xlabel='Observed distinct real annotators, k',ylabel='Mean number of clusters',title='Image / complete: available-prefix vs hindsight (45 images)');ax.legend();ax.grid(True,alpha=.25)
    finish(fig,'04_prefix_vs_hindsight.png','图上完整链接：同一前缀采用后见全池标签和重新分簇的差别，不把后见标签当在线信息。')
    p=pd.read_csv(results/'personnel/subtype_prefix_summary.csv.gz');a=pd.read_csv(results/'personnel/subtype_prefix_roster_aliases.csv')
    a=a[(a.condition=='manual')&(a.config=='QTSB_3')&(a.N>=5)];counts=a.groupby('key').subtype.nunique();valid=set(counts[counts==3].index);a=a[a.key.isin(valid)]
    m=p.merge(a,on='pool');m=m[(m.metric=='image')&(m.partition=='representative')&(m.k<=4)]
    fig,ax=plt.subplots(figsize=(7.6,4.6))
    for s,z in m.groupby('subtype'):
        zz=z.groupby('k').remaining_pair_uncovered_mean.mean();ax.plot(zz.index,100*zz.values,label=f'Fixed LOBO subtype {s}')
    ax.set(xlabel='Distinct people observed within fixed subtype, k',ylabel='Remaining response not covered (%)',title=f'Q/T/S/B fixed subtypes; {len(valid)} identical Manual images',xticks=[1,2,3,4],ylim=(0,100));ax.legend();ax.grid(True,alpha=.25)
    finish(fig,'05_fixed_personnel_subtypes.png','固定留建筑QTSB三组，同一图片交集且每组至少5人；人员名单不是按目标图稳定性选择。此图不支持任意外推到8人或20人。')
    model=pd.read_csv(results/'model_bridge/lobo_summary.csv');z=model[model.metric=='image'];fig,ax=plt.subplots(figsize=(7.6,4.6));labels=['Historical mean','Model corner counts','Corners + gaps + rotations'];ax.bar(labels,z.building_equal_MAE);ax.set(ylabel='Building-equal mean absolute error',title='Optional LOBO model bridge: finite-pool k=5 coverage target');ax.grid(axis='y',alpha=.25)
    finish(fig,'06_model_bridge.png','可选最小基线：45图14楼，目标是有限池k=5未覆盖，不是未来收敛人数；更多模型特征并未优于仅点数。')
    sy=pd.read_csv(results/'sensitivity3d/synthetic_projection_probes.csv');fig,ax=plt.subplots(figsize=(7.6,4.6))
    for delta in [-5,5]:
        z=sy[(sy.alpha_deg==30)&(sy.beta_deg>=5)&(sy.perturbation=='bottom_y')&(sy.delta_px==delta)];ax.plot(z.beta_deg,100*z.radius_relative_change,label=f'Bottom y shift {delta:+d} pixels')
    ax.axhline(0);ax.set(xlabel='Original bottom depression angle (degrees)',ylabel='Relative reconstructed radius change (%)',title='Auxiliary geometry: fixed horizontal floor and camera height');ax.legend();ax.grid(True,alpha=.25)
    finish(fig,'07_depth_sensitivity.png','条件性原始投影的bottom-y敏感性及正负非对称；不进入分簇权重。')
    (figures/'FIGURE_CAPTIONS.json').write_text(json.dumps(saved,ensure_ascii=False,indent=2),encoding='utf-8')
    return saved
if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--results',type=Path);p.add_argument('--figures',type=Path);a=p.parse_args()
    main(a.results,a.figures)
