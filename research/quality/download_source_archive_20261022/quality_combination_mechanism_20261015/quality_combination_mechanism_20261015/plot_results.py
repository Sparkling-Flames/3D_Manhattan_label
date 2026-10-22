"""Independent plots, matplotlib defaults; no image generation or photo inference."""
from pathlib import Path
import numpy as np,pandas as pd
import matplotlib.pyplot as plt

def generate(root):
    root=Path(root);r=root/'results';figs=root/'figures';figs.mkdir(parents=True,exist_ok=True)
    made=[]
    def save(fig,name):
        fig.tight_layout();fig.savefig(figs/name,dpi=170);plt.close(fig);made.append(name)
    shapes=pd.read_csv(r/'EQUAL_SCALE_POOL_SHAPES.csv')
    fig,ax=plt.subplots(figsize=(9,5.6))
    for name in ['S8','B8L2','C8_anchor_matched','P1.5','P3','MAX8']:
        z=shapes[shapes.model==name];ax.plot(z.minor_over_major,z.geometric_loss_over_major,label=name)
    ax.set(xlabel='Smaller burden / larger burden',ylabel='Joint burden / larger burden',title='Same single-channel scales: pooling encodes joint-error utility',xlim=(0,1),ylim=(.97,2.02))
    ax.legend();ax.grid(alpha=.2);save(fig,'pooling_semantics.png')
    fig,ax=plt.subplots(figsize=(9,5.6))
    for name in ['S8','B8L2','C8_anchor_matched']:
        z=shapes[(shapes.model==name)&(shapes.minor_over_major<=.25)]
        ax.plot(z.minor_over_major,z.minor_increment,label=name)
    ax.set(xlabel='Smaller burden / larger burden',ylabel='Additional burden / larger burden',title='L2 increasingly discounts a minor error; C retains a linear marginal cost')
    ax.legend();ax.grid(alpha=.2);save(fig,'minor_error_marginal.png')
    fb=pd.read_csv(r/'FEEDBACK_30_ALL_RECORDS_AND_RAW_COMMENTS.csv').set_index('case_id')
    names=['N02','N10','N17','N21','N22','N23'];z=fb.loc[names];xx=np.arange(len(names))
    fig,ax=plt.subplots(figsize=(9,5.6))
    ax.bar(xx,z.Q_gain_scale_shapley,label='Direction scale contribution (Shapley)')
    ax.bar(xx,z.Q_gain_pool_shapley,bottom=z.Q_gain_scale_shapley,label='Pooling contribution (Shapley)')
    ax.set_xticks(xx,names);ax.set(ylabel='B8L2 minus original WQ / score points',title='Two-factor attribution: changed scales are not a pooling effect')
    ax.legend();ax.grid(axis='y',alpha=.2);save(fig,'scale_pool_attribution.png')
    ctrl=pd.read_csv(r/'PHYSICAL_CONTROLS.csv');z=ctrl[ctrl.family=='shear'].copy()
    fig,ax=plt.subplots(figsize=(9,5.6))
    for name in ['WQ','S8','B8L2','C8_anchor_matched','IoU3D100']:ax.plot(np.degrees(np.arctan(z.amplitude)),z[name],marker='o',label=name)
    ax.set(xlabel='Actual wall-angle error under shear / degrees',ylabel='Score / 100',title='One physical deformation: component scaling and pooling separated',ylim=(0,102))
    ax.legend();ax.grid(alpha=.2);save(fig,'physical_shear.png')
    z=ctrl[ctrl.family=='shear_translation_factorial'].copy();z['translation']=z['case'].str.split('_t').str[-1].astype(float);z['shear']=z['case'].str.split('_s').str[-1].str.split('_t').str[0].astype(float)
    fig,ax=plt.subplots(figsize=(9,5.6))
    for sh in [.025,.05,.1,.2,.4]:
        a=z[z.shear==sh].sort_values('translation');ax.plot(a.translation,a.B8L2-a.S8,marker='o',label=f'Shear {sh:g}')
    ax.set(xlabel='Additional independently imposed translation / camera height',ylabel='B8L2 minus additive S8 / score points',title='Pooling also discounts independently coexisting geometric defects')
    ax.legend();ax.grid(alpha=.2);save(fig,'independent_error_discount.png')
    a=pd.read_csv(r/'SCORES_1145.csv');z=a[a.comparison_layer=='ordinary_manual_conditional']
    fig,ax=plt.subplots(figsize=(9,5.6))
    ax.scatter(z.B8L2,z.B8L2-z.C8_anchor_matched,s=14,alpha=.45)
    ax.axhline(1.9790813505956357,linestyle='--',label='Analytic global upper bound: 1.979 points')
    ax.set(xlabel='B8L2',ylabel='B8L2 minus C8',title='931 fixed-reference ordinary records: equal-anchor shape sensitivity',ylim=(-.05,2.12))
    ax.legend();ax.grid(alpha=.2);save(fig,'equal_anchor_real_comparison.png')
    fig,ax=plt.subplots(figsize=(8,6))
    ax.scatter(z.abs_S8_derivative_Q_per_Ddeg,z.abs_B_derivative_Q_per_Ddeg,s=14,alpha=.45)
    m=max(z.abs_S8_derivative_Q_per_Ddeg.max(),z.abs_B_derivative_Q_per_Ddeg.max());ax.plot([0,m],[0,m],linestyle='--',label='Equal local slope')
    ax.set(xlabel='S8: absolute local score slope / degree D',ylabel='B8L2: absolute local score slope / degree D',title='243/931 records: B has a steeper LOCAL slope despite lower total D cost')
    ax.legend();ax.grid(alpha=.2);save(fig,'local_slope_vs_total_cost.png')
    geo=__import__('json').load(open(r/'REVIEW_GEOMETRY_30.json'))
    for name in ['N10','N17','N22','N24']:
        q=next(x for x in geo if x['case_id']==name);fig,ax=plt.subplots(figsize=(8,6))
        for label,key in [('Answer','a'),('Fixed reference','g')]:
            x=np.asarray(q[key]);x=np.r_[x,x[:1]];ax.plot(x[:,0],x[:,1],marker='o',label=f'{label}: {len(x)-1} vertices')
        ax.plot([0],[0],marker='x',markersize=8,label='Camera')
        ax.set(aspect='equal',xlabel='X / camera height',ylabel='Z / camera height',title=f'Current receipt {name} | {q["record_id"]}\nDeclared geometry only; no new RGB adjudication')
        ax.legend();ax.grid(alpha=.2);save(fig,f'{name}_geometry.png')
    return made

if __name__=='__main__':generate(Path(__file__).resolve().parent)
