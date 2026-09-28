"""Diagnostic figures using Matplotlib defaults; no outcome-based method selection."""
from pathlib import Path
import json
import pandas as pd,numpy as np
import matplotlib.pyplot as plt

def make_figures(root):
    root=Path(root);out=root/'figures';out.mkdir(exist_ok=True);r=root/'results'
    def finish(fig,name):
        fig.tight_layout();fig.savefig(out/name,dpi=180,bbox_inches='tight');plt.close(fig)
    d=pd.read_csv(r/'uNb47_local_coverage_curve.csv')
    fig,ax=plt.subplots(figsize=(7.4,4.5))
    joint=d[d.local_pair=='joint'].sort_values('k');local=d[d.local_pair!='joint'].groupby('k').U.agg(['mean','max'])
    ax.plot(joint.k,joint.U,marker='o',label='Whole-layout maximum')
    ax.plot(local.index,local['mean'],marker='s',label='Mean across 7 local corner pairs')
    ax.plot(local.index,local['max'],marker='^',label='Most uncovered local corner pair')
    ax.set(xlabel='Distinct observed people, k',ylabel='Next response not covered, U(k)',ylim=(-.02,1.02),title='uNb-47: local coverage is not joint coverage\n12 real responses with 14 endpoints; 12 of 22 responses overall')
    ax.legend(fontsize=8);finish(fig,'01_local_vs_joint.png')
    a=pd.read_csv(r/'replay_onsets.csv');a=a[(a.N>=8)&(a.epsilon==.1)&(a.profile=='uncapped')]
    fig,ax=plt.subplots(figsize=(7.4,4.5))
    for method,label in [('complete','Complete linkage'),('representative','Real-response radius')]:
        counts=a[a.method==method].groupby('tail').status.apply(lambda x:(x=='identified').sum())
        ax.plot(counts.index,counts,marker='o',label=label)
    ax.set(xlabel='Required remaining tail',ylabel='Images with identified observed onset',title='Stability counts depend on the measurement contract\nSame 110 images, N >= 8; 200 actual-worker replays',xticks=[2,3,5],ylim=(0,65))
    ax.legend();finish(fig,'02_tail_sensitivity.png')
    a=pd.read_csv(r/'team_composition_variance.csv.gz');a=a[(a.N==24)&(a.total_variance>1e-14)]
    fig,ax=plt.subplots(figsize=(7.4,4.5))
    for config,label in [('Q_2','Historical Q2 types'),('QTSB_3','Historical QTSB3 types')]:
        d=a[a.config==config].groupby('n').composition_fraction.mean()
        ax.plot(d.index,1-d,marker='o',label=label)
    ax.set(xlabel='Distinct real people in a team',ylabel='Variance remaining within identical type composition',title='Swapping actual members matters\nFixed 24-response image panel; finite-team disagreement variance',ylim=(0,1),xticks=[4,8,12,16,20])
    ax.legend();finish(fig,'03_members_within_composition.png')
    d=pd.read_csv(r/'ray_derivative_probes.csv.gz')
    fig,ax=plt.subplots(figsize=(7.4,4.5))
    for col,label in [('top_y_sensitivity','Top y'),('bottom_y_sensitivity','Bottom y'),('top_x_sensitivity','Top x')]:
        vals=np.sort(d[col].dropna().to_numpy());ax.plot(vals,np.arange(1,len(vals)+1)/len(vals),label=label)
    ax.set(xscale='log',xlabel='Maximum endpoint displacement / camera height / pixel',ylabel='Empirical cumulative fraction',title='Sensitivity under the actual raw ray / paired-range proxy\nNumerical probes, not additional annotations')
    ax.legend();finish(fig,'04_3d_sensitivity.png')
    a=json.loads((r/'model_N_roster_controls_summary.json').read_text())
    a=[z for z in a if z['outcome']=='U8'];ordered=['N_only','N_plus_roster','N_plus_model_counts','N_plus_model_counts_gaps','N_plus_model_and_roster'];labels=['N only','N + historical Q2 roster','N + model corner counts','N + counts + model gaps','N + model features + roster']
    vals=[next(z['MAE'] for z in a if z['config']==k) for k in ordered]
    fig,ax=plt.subplots(figsize=(7.4,4.5));ax.barh(labels[::-1],vals[::-1]);ax.set(xlabel='Building-equal mean absolute error',title='Predicting finite-pool U(8), not future convergence\nLeave-one-building-out; identical target panel; fixed Ridge alpha=10')
    for y,v in enumerate(vals[::-1]):ax.text(v+.002,y,f'{v:.3f}',va='center',fontsize=9)
    ax.set_xlim(0,max(vals)*1.17);finish(fig,'05_model_controls.png')
    return list(out.glob('*.png'))

if __name__=='__main__':
    print('\n'.join(map(str,make_figures(Path(__file__).resolve().parents[1]))))
