#!/usr/bin/env python3
"""Produce links, hierarchy and old/new label comparison, without refitting."""
import argparse
from pathlib import Path
import pandas as pd
from sklearn.metrics import adjusted_rand_score,normalized_mutual_info_score
from build_condition_response_classes import save_csv

def main(a):
 p=Path(a.output);d=pd.read_csv(p/'CANDIDATE_LABELS_COMPLETE_ALL_LOBO.csv.gz');old=pd.read_csv(a.old)
 old=old[old.condition.eq('manual')&old.known];out=[]
 for (method,b),g in d[d.known&d.heldout_building.ne('ALL')].groupby(['method','heldout_building']):
  for om,og in old[old.heldout_building.eq(b)].groupby('method'):
   z=g[['worker_id','class_id']].merge(og[['worker_id','coarse_label','fine_label']],on='worker_id',validate='one_to_one')
   for tier in ['coarse_label','fine_label']:
    out.append(dict(method=method,heldout_building=b,old_method=om,old_tier=tier,workers=len(z),ari=adjusted_rand_score(z.class_id,z[tier]),nmi=normalized_mutual_info_score(z.class_id,z[tier])))
 s=pd.DataFrame(out);save_csv(s,p/'NEW_OLD_LABEL_CROSSWALK_LOBO.csv')
 save_csv(s.groupby(['method','old_method','old_tier']).agg(folds=('heldout_building','nunique'),ari_mean=('ari','mean'),ari_min=('ari','min'),nmi_mean=('nmi','mean')).reset_index(),p/'NEW_OLD_LABEL_CROSSWALK_SUMMARY.csv')
 out=[]
 for (fam,b),g in d[d.known&d.family.isin(['DSTRUCT','DBOUNDARY','DJOINT','MSDGEOM','MSDGEOM_SCOPE'])].groupby(['family','heldout_building']):
  base=g[g.k.eq(2)].set_index('worker_id').class_id
  for (method,cl),gg in g[g.k.gt(2)].groupby(['method','class_id']):
   par=base.reindex(gg.worker_id).dropna().unique();assert len(par)==1
   out.append(dict(family=fam,heldout_building=b,method=method,class_id=cl,parent_k2_class=par[0],members='|'.join(gg.worker_id),people=len(gg)))
 save_csv(pd.DataFrame(out),p/'WARD_HIERARCHY_PARENT_LINKS.csv')
 cs=pd.concat([pd.read_csv(p/z) for z in ['NEW_CLASS_DEFINITIONS_ALL_LOBO.csv.gz','AXIS_CLASS_DEFINITIONS_ALL_LOBO.csv.gz','SCOPE_INCREMENT_CLASS_DEFINITIONS_ALL_LOBO.csv.gz']],ignore_index=True)
 save_csv(cs,p/'CANDIDATE_CLASS_DEFINITIONS_COMPLETE_ALL_LOBO.csv.gz');save_csv(cs[cs.heldout_building.eq('ALL')],p/'CANDIDATE_CLASS_DEFINITIONS_COMPLETE_ALL.csv')

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('--old',required=True);main(p.parse_args())
