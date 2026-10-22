"""Eight separate figures. Default Matplotlib styling; no custom colour assignments."""
from pathlib import Path
import sys
import numpy as np,pandas as pd
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parent;sys.path.insert(0,str(ROOT/'src'))
from working_models import MODELS,A,score
from dataclasses import replace

def generate(results,figures):
 results=Path(results);figures=Path(figures);figures.mkdir(parents=True,exist_ok=True)
 def save(fig,name):fig.tight_layout();fig.savefig(figures/name,dpi=170);plt.close(fig)
 labels={'WQ':'Historical WQ','A10':'A: broader direction scale','B8L2':'B: floor-direction L2 pool'}
 d=np.linspace(0,20,201)
 fig,ax=plt.subplots(figsize=(9,5.2))
 for m,p in MODELS.items():ax.plot(d,score(1,0,d,0,0,p),label=labels[m])
 ax.set(xlabel='Intrinsic D / degrees',ylabel='Score / 100',ylim=(0,102),title='Isolated component response (not an independently realizable shape path)');ax.legend();ax.grid(alpha=.2);save(fig,'direction_response.png')
 c=pd.read_csv(results/'geometric_controls.csv');s=c[c.family.eq('shear')].copy()
 if len(s)==0:s=c[c['case'].str.startswith('shear_')].copy()
 s=s.sort_values('amplitude');x=np.degrees(np.arctan(s.amplitude))
 fig,ax=plt.subplots(figsize=(9,5.2))
 for m in list(MODELS)+['IoU3D']:ax.plot(x,s['Q_'+m],marker='o',label=labels.get(m,'Original 3D IoU'))
 ax.set(xlabel='Actual adjacent-wall angle deviation / degrees',ylabel='Score / 100',ylim=(0,102),title='Same explicit sheared-square geometry, same reference');ax.legend();ax.grid(alpha=.2);save(fig,'shear_response.png')
 F=np.linspace(0,2,201);I=1/(1+F)
 fig,ax=plt.subplots(figsize=(9,5.2))
 for m,p in MODELS.items():ax.plot(F,score(I,0,0,0,0,p)-score(I,0,5,0,0,p),label=labels[m])
 ax.set(xlabel='Floor fidelity loss F (algebraic fixed-component slice)',ylabel='Actual direction deletion gain / score points',title='Same D=5 degrees: marginal point cost depends on other errors');ax.legend();ax.grid(alpha=.2);save(fig,'conditional_direction_cost.png')
 r=pd.read_csv(results/'REPRESENTATIVE_CASES_AND_ATTRIBUTION.csv').set_index('case_label').loc[['N11','N18','N19','N24','J04']]
 fig,ax=plt.subplots(figsize=(9,5.2));x=np.arange(len(r));width=.25
 for j,m in enumerate(MODELS):ax.bar(x+(j-1)*width,r[m+'_delete_intrinsic_direction_gain'],width,label=labels[m])
 ax.set_xticks(x,r.index);ax.set(ylabel='Score increase after deleting D',title='Same fixed inputs: nonlinear ablation, not a fixed component weight');ax.legend();ax.grid(axis='y',alpha=.2);save(fig,'real_direction_ablation.png')
 allr=pd.read_csv(results/'SCORES_1145.csv');o=allr[allr.comparison_layer.eq('ordinary_manual_conditional')]
 fig,ax=plt.subplots(figsize=(7,6))
 ax.scatter(o.Q_WQ,o.Q_A10,s=13,alpha=.45,label='A10');ax.scatter(o.Q_WQ,o.Q_B8L2,s=13,alpha=.45,marker='x',label='B8L2');ax.plot([0,100],[0,100],linestyle='--',label='Unchanged')
 ax.set(xlabel='Historical WQ',ylabel='Working score',xlim=(0,102),ylim=(0,102),title='931 same-binding ordinary manual records');ax.legend();ax.grid(alpha=.2);save(fig,'ordinary_scatter.png')
 t=pd.read_csv(results/'DIFFICULTY_CLASS_SUMMARY.csv');cl=['简单','中等','困难'];fig,ax=plt.subplots(figsize=(9,5.2))
 for m in ['Q_WQ','Q_A10','Q_B8L2','Q_IoU3D']:
  z=t[t.metric.eq(m)].set_index('current_class').loc[cl];ax.plot(range(3),z.image_equal_mean,marker='o',label=m.replace('Q_',''))
 ax.set_xticks(range(3),['Easy (71 images)','Medium (10 images)','Hard (14 images)']);ax.set(ylabel='Image-equal mean score',ylim=(0,100),title='Fixed difficulty classes; same reference ID, no class re-fitting');ax.legend();ax.grid(alpha=.2);save(fig,'difficulty_means.png')
 z=allr[allr.comparison_layer.eq('severe_exception')].sort_values('Q_WQ');fig,ax=plt.subplots(figsize=(10,5.2))
 for m in list(MODELS)+['IoU3D']:ax.plot(z.record_id,z['Q_'+m],marker='o',label=labels.get(m,'Original 3D IoU'))
 ax.set(ylabel='Score / 100',ylim=(0,65),title='Nine existing severe exceptions (not an ordinary fitting cohort)');ax.tick_params(axis='x',rotation=30);ax.legend();ax.grid(alpha=.2);save(fig,'severe_records.png')
 z=c[c.family.eq('shear_translation_factorial')].copy();z['translation']=z['case'].str.rsplit('_t',n=1).str[-1].astype(float)
 fig,ax=plt.subplots(figsize=(9,5.2))
 for s in [0,.05,.1,.2,.4]:
  x=z[z.amplitude.eq(s)].sort_values('translation');a8=score(x.iou_2d.to_numpy(),x.S_bottom_deg.to_numpy(),x.dir.to_numpy(),x.Hmean.to_numpy(),x.Hcenter.to_numpy(),replace(A,direction_scale_deg=8))
  ax.plot(x.translation,x.Q_B8L2-a8,marker='o',label=f'Shear={s:g}')
 ax.set(xlabel='Added independent translation / camera height',ylabel='B score minus additive score with same D scale',title='Pooling also discounts independent co-occurring errors: an explicit cost');ax.legend();ax.grid(alpha=.2);save(fig,'factorial_pooling_cost.png')
 return 8
if __name__=='__main__':
 import argparse
 a=argparse.ArgumentParser();a.add_argument('--results',type=Path,default=ROOT/'results');a.add_argument('--figures',type=Path,default=ROOT/'figures');v=a.parse_args();print(generate(v.results,v.figures))
