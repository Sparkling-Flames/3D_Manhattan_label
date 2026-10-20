"""Held-out common-anchor original Rnew2 comparison, using refitted inner labels."""
import json,time
from pathlib import Path
import pandas as pd,numpy as np
from learn_corner_types import BASE,ROOT,P,prepare,Anchors,make_inner_folds,write

def run(tier):
 out=BASE/('corner_fit_'+tier);files=sorted((BASE/'corner_history').glob('*.csv.gz'))
 if tier=='mixed':files+=sorted((BASE/'corner_h20').glob('*.csv.gz'))
 d=prepare(pd.concat([pd.read_csv(p) for p in files],ignore_index=True));folds=make_inner_folds(json.load(open(P/'analysis/composition/SPLIT.json'))['history_buildings']);a=pd.read_csv(out/'fold_labels.csv');b=pd.read_csv(BASE/'original_Rnew2_inner_fold_labels.csv');rows=[]
 for (mid,fi),g in a.groupby(['method_id','fold']):
  x=g.set_index('worker_id');y=b[b.fold.eq(fi)].set_index('worker_id');ws=sorted(set(x.index)&set(y.index));fast=Anchors(d[d.building.isin(folds[fi])],ws)
  for r in fast.paired(x.loc[ws,'class_id'].to_numpy(int),y.loc[ws,'class_id'].to_numpy(int)):rows.append({'method_id':mid,'fold':fi,'baseline':'original_Rnew2_refitted_mixed_history_K2',**r})
 f=pd.DataFrame(rows);f.to_csv(out/'original_Rnew2_paired_buildings.csv',index=False);f.groupby(['method_id','baseline']).mean(numeric_only=True).to_csv(out/'original_Rnew2_paired_summary.csv');write(out/'RNEW2_CONTROL_RECEIPT.json',{'no_fitting_or_selection':True,'baseline_labels_source':'original_Rnew2_inner_fold_labels.csv','baseline_fit':'original mixed-history old geometry risk reconstructed separately per eightbuildingfold','evaluation_panel':tier,'legacy_limit':'Rnew2 baseline uses richer mixed training evidence even when evaluation limited to legacy history events','same_personnel_and_anchor_intersection':True,'rows':len(f)})
if __name__=='__main__':
 import argparse
 p=argparse.ArgumentParser();p.add_argument('--tier',default='legacy');run(p.parse_args().tier)
