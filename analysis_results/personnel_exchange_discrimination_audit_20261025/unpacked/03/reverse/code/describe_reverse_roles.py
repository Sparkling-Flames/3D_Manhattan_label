#!/usr/bin/env python3
"""Capacity, validation components and prior-label links for learned roles."""
from pathlib import Path
import argparse,gzip,json
import numpy as np
import pandas as pd
from sklearn.metrics import adjusted_rand_score
from prepare_natural_training import save_csv,save_json,sha

def main(a):
 p=Path(a.output);labels=pd.read_csv(p/'REVERSE_LABELS_ALL_LOBO.csv.gz');old=pd.read_csv(a.previous)
 checks=pd.read_csv(p/'INNER_BUILDING_RESPONSE_ERRORS.csv.gz');selected=pd.read_csv(p/'NESTED_LAMBDA_SELECTION.csv');selected=selected[selected.selected]
 z=checks.merge(selected[['family','heldout_building','alpha']],on=['heldout_building','alpha'],validate='many_to_many')
 valid=z.groupby(['family','heldout_building','stratum','output']).agg(model_mse=('normalized_mse','mean'),zero_mse=('zero_response_normalized_mse','mean'),inner_buildings=('inner_building','nunique')).reset_index();valid['relative_mse_to_zero']=valid.model_mse/valid.zero_mse
 save_csv(valid,p/'INNER_RESPONSE_COMPONENT_SUMMARY.csv')
 cross=[]
 for (method,b),g in labels[labels.known].groupby(['method','heldout_building']):
  for om,h in old[old.known&old.heldout_building.eq(b)].groupby('method'):
   q=g[['worker_id','class_id']].merge(h[['worker_id','class_id']],on='worker_id',suffixes=('_new','_old'),validate='one_to_one')
   cross.append(dict(method=method,heldout_building=b,previous_method=om,common_workers=len(q),ari=adjusted_rand_score(q.class_id_new,q.class_id_old)))
 save_csv(pd.DataFrame(cross),p/'REVERSE_PREVIOUS_LABEL_OVERLAP.csv')
 save_csv(pd.DataFrame(cross).query("heldout_building != 'ALL'").groupby(['method','previous_method']).agg(folds=('heldout_building','nunique'),ari_mean=('ari','mean'),ari_min=('ari','min')).reset_index(),p/'REVERSE_PREVIOUS_LABEL_OVERLAP_SUMMARY.csv')
 snap=json.load(gzip.open(a.snapshot,'rt'));pools=[x for x in snap['images'] if x['meta']['layer']=='ordinary_manual']
 caps=[];members=[]
 for (method,b),g in labels[labels.known&labels.heldout_building.ne('ALL')].groupby(['method','heldout_building']):
  mapping=g.set_index('worker_id').class_id.to_dict()
  for pool in pools:
   meta=pool['meta']
   if meta['building']!=b:continue
   people=[r['worker_id'] for r in pool['records'] if r['worker_id'] in mapping];counts=pd.Series([mapping[w] for w in people]).value_counts().to_dict();N=len(people)
   for cl,nc in counts.items():members.append(dict(method=method,pool_id=pool['pool_id'],image=meta['image'],building=b,difficulty=meta['difficulty'],class_id=cl,class_n=nc,pool_known_n=N,members='|'.join(w for w in people if mapping[w]==cl)))
   for src,ns in counts.items():
    for dst,nt in counts.items():
     if src==dst:continue
     for n in [8,10,12,14,16,18,20,22,24,26,28,30]:
      mmax=max(0,min(ns//2,nt,(N-n)//2,n))
      if mmax<2:continue
      caps.append(dict(method=method,pool_id=pool['pool_id'],image=meta['image'],building=b,difficulty=meta['difficulty'],n=n,source_class=src,target_class=dst,source_n=ns,target_n=nt,pool_known_n=N,max_strict_m=mmax))
 cap=pd.DataFrame(caps);save_csv(cap,p/'REVERSE_STRICT_CAPACITY_BY_IMAGE_N.csv.gz');save_csv(pd.DataFrame(members),p/'REVERSE_CURRENT_POOL_MEMBERS.csv.gz')
 totals=[]
 for (method,n),g in cap.groupby(['method','n']):
  for m in [3,4,5,6,7,8,9,10,12]:
   t=g[g.max_strict_m.ge(m)]
   if len(t):totals.append(dict(method=method,n=n,m=m,images=t.pool_id.nunique(),buildings=t.building.nunique(),directions=len(t),evaluation_scope='ordinary_manual'))
 save_csv(pd.DataFrame(totals),p/'REVERSE_STRICT_CAPACITY_SUMMARY.csv')
 # K3 is a refinement of the same K2 Ward tree for every fold.
 hierarchy=[]
 for (family,b),g in labels[labels.known].groupby(['family','heldout_building']):
  co=g[g.k.eq(2)].set_index('worker_id').class_id
  for cl,h in g[g.k.eq(3)].groupby('class_id'):
   parents=co.reindex(h.worker_id).unique();assert len(parents)==1
   hierarchy.append(dict(family=family,heldout_building=b,fine_class=cl,parent_k2_class=parents[0],members='|'.join(h.worker_id),people=len(h)))
 save_csv(pd.DataFrame(hierarchy),p/'REVERSE_HIERARCHY.csv')
 manifest=[]
 for path in sorted(p.rglob('*')):
  if not path.is_file() or path.name=='FILE_MANIFEST.csv' or path.name.endswith('_LOG.txt') or '__pycache__' in str(path):continue
  manifest.append(dict(path=str(path),bytes=path.stat().st_size,sha256=sha(path)))
 save_csv(pd.DataFrame(manifest),p/'FILE_MANIFEST.csv')
 print(pd.DataFrame(totals).query('n in [10,14,20] and m in [4,6,7,9]').to_string(index=False))

if __name__=='__main__':
 q=argparse.ArgumentParser();q.add_argument('--output',required=True);q.add_argument('--previous',required=True);q.add_argument('--snapshot',required=True);main(q.parse_args())
