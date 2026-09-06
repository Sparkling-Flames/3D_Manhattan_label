"""Data plots; default Matplotlib colors, one chart per figure."""
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parents[3]
OUT=ROOT/'analysis_results/preflight_20260906_v2'
def run():
 out=OUT/'figures';out.mkdir(exist_ok=True)
 def finish(fig,name):
  fig.tight_layout();fig.savefig(out/name,dpi=170);plt.close(fig)
 d=pd.read_csv(OUT/'precision_curves_k_and_fraction.csv');q=d[d.k<=20].groupby('k')[['finite_sd','empirical_iid_sd']].mean()
 fig,ax=plt.subplots(figsize=(8,4.5));ax.plot(q.index,q.finite_sd,marker='o',label='Without replacement: observed roster');ax.plot(q.index,q.empirical_iid_sd,marker='s',label='Empirical with-replacement diagnostic');ax.set(xlabel='Number of selected responses k',ylabel='Mean SD of pairwise-disagreement estimate',title='70 fixed high-support contexts; not layout-quality error');ax.legend();ax.grid(alpha=.25);finish(fig,'precision_by_k.png')
 f=pd.read_csv(OUT/'precision_fraction_grid.csv').groupby('requested_fraction')[['finite_sd','empirical_iid_sd']].mean()
 fig,ax=plt.subplots(figsize=(8,4.5));ax.plot(f.index,f.finite_sd,marker='o',label='Finite observed roster');ax.plot(f.index,f.empirical_iid_sd,marker='s',label='Empirical with-replacement diagnostic');ax.set(xlabel='Requested roster fraction f, using k = ceil(f N)',ylabel='Mean SD of pairwise-disagreement estimate',title='Finite-roster endpoint versus non-exhausting resampling');ax.legend();ax.grid(alpha=.25);finish(fig,'precision_by_fraction.png')
 b=pd.read_csv(OUT/'early_prediction_baselines.csv');names=['stage_condition_mean','direct_early_D','calibrated_early','early_plus_corners','early_plus_corners_models']
 fig,ax=plt.subplots(figsize=(9,4.8))
 for k in [3,5]:
  q=b[b.k==k].set_index('model').loc[names];ax.plot(range(5),q.RMSE,marker='o',label=f'First {k} historical responses')
 ax.set_xticks(range(5),['Train-stage\nmean','Direct early\ndisagreement','Calibrated\nearly signal','Early +\ncorner counts','Early + corners\n+ model gaps']);ax.set(ylabel='Held-out-building RMSE',title='Same 70 contexts / 14 buildings; 240 simulated prefixes per context');ax.legend();ax.grid(alpha=.25);finish(fig,'prediction_baselines.png')
 p=pd.read_csv(OUT/'fixed_panel_vs_independent.csv');fig,ax=plt.subplots(figsize=(8,4.8))
 for (stage,condition),q in p[p.k<20].groupby(['stage','condition']):
  ax.plot(q.k,q.exact_variance_ratio,marker='o',label=stage+' '+condition)
 ax.axhline(1,linestyle='--');ax.set(xlabel='Selected current-roster workers k',ylabel='Exact variance: fixed panel / independent panels',title='Conditional on actual common-support historical responses');ax.legend();ax.grid(alpha=.25);finish(fig,'fixed_panel_variance.png')
 sim=pd.read_csv(OUT/'synthetic_EM_summary.csv');fig,ax=plt.subplots(figsize=(8,4.5))
 for f,q in sim.groupby('shared_flip_fraction'):ax.plot(q.workers,q.mean_EM_truth_error,marker='o',label=f'Assumed shared flip fraction {f:.0%}')
 ax.set(xlabel='Simulated workers',ylabel='Mean error against simulated physical truth',title='Synthetic demonstration only: not calibrated human behavior');ax.legend();ax.grid(alpha=.25);finish(fig,'synthetic_error_vs_workers.png')
 tr=pd.read_csv(OUT/'synthetic_EM_objective_trace.csv');fig,ax=plt.subplots(figsize=(8,4.5))
 for f,q in tr.groupby('shared_flip_fraction'):ax.plot(q.iteration,q.log_likelihood,marker='o',label=f'Shared flip fraction {f:.0%}')
 ax.set(xlabel='EM iteration, one example with 20 simulated workers',ylabel='Observed-data log likelihood',title='Optimizer convergence is not correctness convergence');ax.legend();ax.grid(alpha=.25);finish(fig,'synthetic_EM_objective.png')
 print('Created',len(list(out.glob('*.png'))),'data plots')
if __name__=='__main__':run()
