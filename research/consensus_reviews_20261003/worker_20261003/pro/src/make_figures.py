"""Scientific figures for the independent audit. Default Matplotlib colours only."""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

ROOT=Path(__file__).resolve().parents[1]

def main():
    out=ROOT/'figures';out.mkdir(exist_ok=True);paths=[]
    s=json.loads((ROOT/'results/profile_analysis_summary.json').read_text())
    splits=pd.read_csv(ROOT/'results/disjoint_building_splits.csv')
    fig=plt.figure(figsize=(9.6,5.4));ax=fig.add_subplot(111)
    bins=np.arange(7.5,21.6,2)/24*100
    for policy,label in [('original','Original references'),('revised_where_available','Revised where available')]:
        d=splits[splits.policy==policy]
        ax.hist(100*d.same_half_fraction,bins=bins,alpha=.6,label=label)
    ax.set(xlabel='Workers assigned to the same half in both disjoint calibration blocks (%)',
           ylabel='Number of building partitions',title='Disjoint 4-building vs 4-building calibration\nMedian agreement: 14/24 workers under each reference policy')
    ax.legend();fig.text(.5,.015,'35 partitions reuse the same 8 buildings. These are not 35 independent validation samples.',ha='center',fontsize=9)
    fig.tight_layout(rect=(0,.045,1,1));p=out/'01_disjoint_group_reliability.png';fig.savefig(p,dpi=175);plt.close(fig);paths.append(p)
    fig=plt.figure(figsize=(9.6,5.4));ax=fig.add_subplot(111);x=np.arange(3);width=.36
    for offset,(policy,label) in zip([-.5,.5],[('original','Original references'),('revised_where_available','Revised where available')]):
        y=np.array([s[policy]['influence_'+key]['skill'] for key in ['none','P017','P017-P002']])*100
        bars=ax.bar(x+offset*width,y,width,label=label)
        ax.bar_label(bars,fmt='%.2f',padding=4)
    ax.axhline(0,linewidth=.8)
    ax.set(xticks=x,xticklabels=['All 24 workers','Without P017','Without P017 and P002'],ylabel='Reduction in held-out relative-score squared error (%)',
       title='Cross-building predictive value is unevenly distributed\nOmissions are influence diagnostics, NOT eligibility decisions',ylim=(-15,20))
    ax.legend();fig.tight_layout();p=out/'02_worker_influence.png';fig.savefig(p,dpi=175);plt.close(fig);paths.append(p)
    d=pd.read_csv(ROOT/'results/metric_image_diagnostics.csv');images=d[d.policy=='original'].image.tolist()
    fig=plt.figure(figsize=(10.8,5.8));ax=fig.add_subplot(111)
    for policy,label in [('original','Original references'),('revised_where_available','Revised where available')]:
        vals=d[d.policy==policy].set_index('image').loc[images].within_image_loss_centroid_rho
        ax.plot(np.arange(len(images)),vals,marker='o',label=label)
    ax.axhline(0,linewidth=.8);ax.set(xticks=np.arange(len(images)),xticklabels=[i[:3]+'-'+i.rsplit('-',1)[-1] for i in images],
       xlabel='Image (abbreviated IDs)',ylabel='Within-image Spearman: 1 - IoU vs normalized centroid distance',ylim=(-.8,1.04),
       title='The apparent relationship between metrics depends on the reference\ne9z-19: -0.565 with the original vs +0.933 with the revision')
    ax.legend(loc='lower right');fig.tight_layout();p=out/'03_reference_metric_relation.png';fig.savefig(p,dpi=175);plt.close(fig);paths.append(p)
    d=pd.read_csv(ROOT/'results/one_image_k4_exact.csv');v=d[d.method=='mv50'].sort_values('higher_n')
    fig=plt.figure(figsize=(9.6,5.5));ax=fig.add_subplot(111)
    ax.plot(v.higher_n,v.expected_symdiff_gt,marker='o',label='Expected reference symmetric difference R')
    ax.plot(v.higher_n,v.consensus_field_bias_gt,marker='o',label='Consensus-field reference bias B')
    ax.plot(v.higher_n,v.expected_symdiff_gt-v.consensus_field_bias_gt,marker='o',label='Composition variance V = pair difference / 2')
    ax.set(xlabel='Number from the externally calibrated upper half (total k = 4)',ylabel='Area divided by fixed reference area',xticks=range(5),
       title='Reference error falls while composition variability grows\nExact area identity R = B + V; one real image, MV50')
    ax.legend();fig.text(.5,.015,'7y3sRwLe3Va-04; 10,626 subsets. This is NOT an IoU decomposition or a difficulty label.',ha='center',fontsize=9)
    fig.tight_layout(rect=(0,.05,1,1));p=out/'04_reference_variability_decomposition.png';fig.savefig(p,dpi=175);plt.close(fig);paths.append(p)
    return paths

if __name__=='__main__':
    for path in main():print(path)
