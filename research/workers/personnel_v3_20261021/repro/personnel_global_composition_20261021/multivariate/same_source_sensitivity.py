#!/usr/bin/env python3
"""Prespecified same-source rerun after observing source association, before fusion."""
import time
import pandas as pd
from build_multivariate import HERE,METHODS,classify,js,sha,summarize

def main():
    f=pd.read_csv(HERE/'continuous_features_lobo.csv.gz')
    method=dict(METHODS[0],method_id='MV_QTD_manual_new',new_only=True,scope='ordinary_manual_new',
                description='同新批普通 Manual 内 Q 父层、T/D 等权细分；原混来源 QTD 的来源敏感性。')
    labels=[];fits=[]
    for b,g in f[f.condition.eq('manual')].groupby('heldout_building',sort=False):
        ll,meta=classify(g.reset_index(drop=True),method);labels.append(ll);meta['heldout_building']=b;fits.append(meta)
    labels=pd.concat(labels,ignore_index=True)
    labels.to_csv(HERE/'same_source_candidate_labels.csv',index=False)
    stability,classes,_=summarize(labels,f,pd.DataFrame(),pd.DataFrame(columns=['condition','domain_subset']))
    stability.to_csv(HERE/'same_source_lobo_stability.csv',index=False)
    classes.to_csv(HERE/'same_source_class_members.csv',index=False)
    js(HERE/'SAME_SOURCE_FREEZE.json',{'frozen_at_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),
       'reason':'Original QTD fine classes show source association; same-source formation checks whether fine distinctions survive within new35.',
       'selection_basis':'Origin composition and training labels only; no fusion outcomes inspected.',
       'label_sha256':sha(HERE/'same_source_candidate_labels.csv'),'original_frozen_labels_unchanged':True,'method':method,'fits':fits})
    print(labels[labels.heldout_building.eq('ALL')&labels.known].groupby(['coarse_class','fine_class']).size().to_string())
    print(stability.groupby('level').ARI_full_vs_lobo.agg(['mean','median','min']).to_string())

if __name__=='__main__':main()
