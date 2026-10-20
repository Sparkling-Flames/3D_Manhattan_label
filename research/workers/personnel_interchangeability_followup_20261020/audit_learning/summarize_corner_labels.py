import json
from pathlib import Path
import pandas as pd,numpy as np
from sklearn.metrics import adjusted_rand_score
BASE=Path(__file__).resolve().parent

def run(tier):
 p=BASE/('corner_fit_'+tier);full=pd.read_csv(p/'worker_labels.csv');fold=pd.read_csv(p/'fold_labels.csv');rows=[]
 for (mid,fi),g in fold.groupby(['method_id','fold']):
  f=full[(full.method_id==mid)&full.known].set_index('worker_id');g=g.set_index('worker_id');common=sorted(set(f.index)&set(g.index));a=f.loc[common,'class_id'].to_numpy();b=g.loc[common,'class_id'].to_numpy();ix=np.triu_indices(len(common),1)
  rows.append({'method_id':mid,'fold':fi,'common_people':len(common),'lost_people':len(set(f.index)-set(g.index)),'ARI_vs_full':adjusted_rand_score(a,b),'pair_flip_fraction':np.mean((a[:,None]==a[None,:])[ix]!=(b[:,None]==b[None,:])[ix])})
 r=pd.DataFrame(rows);r.to_csv(p/'inner_fit_label_sensitivity.csv',index=False);summary=r.groupby('method_id').agg(ARI_mean=('ARI_vs_full','mean'),ARI_min=('ARI_vs_full','min'),pair_flip_mean=('pair_flip_fraction','mean'),lost_people_max=('lost_people','max'));summary.to_csv(p/'inner_fit_label_sensitivity_summary.csv');print(summary.to_string())
if __name__=='__main__':
 import argparse
 a=argparse.ArgumentParser();a.add_argument('--tier',default='legacy');run(a.parse_args().tier)
