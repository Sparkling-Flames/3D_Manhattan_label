#!/usr/bin/env python3
"""Coverage-informed, pre-fusion phenotype fine-class extension; no cutoff tuning."""
import argparse,time
from pathlib import Path
import numpy as np
import pandas as pd
from run_profiles import DIFFS,METRICS,labelq,predict_fold,summaries,js,digest

def labels(p):
    p=p.copy()
    for metric in METRICS:
        p['fine_dtype_'+metric]=np.where(p['QT_'+metric].eq('unknown'),'unknown',p['QT_'+metric]+'|'+p['difficulty_type_'+metric])
        p['hard_peer_tag_'+metric]=[labelq(t,3,s)for t,s in zip(p['theta_hard_'+metric],p.difficulty_supported_hard)]
        p['fine_dtype_merged_'+metric]=p['QT_'+metric]
        for parent,g in p[p['QT_'+metric].ne('unknown')].groupby('QT_'+metric):
            cnt=g['difficulty_type_'+metric].value_counts();accepted=set(cnt[(cnt>=3)&cnt.index.to_series().ne('unknown')].index)
            for idx,r in g.iterrows():
                c=r['difficulty_type_'+metric]
                if c=='unknown':x=parent+'|difficulty_unknown'
                elif len(accepted)>=2 and c in accepted:x=parent+'|'+c
                elif len(accepted)>=2:x=parent+'|sparse_child'
                else:x=parent+'|not_split'
                p.at[idx,'fine_dtype_merged_'+metric]=x
    return p

def main():
    a=argparse.ArgumentParser();a.add_argument('--out',type=Path,default=Path('work_v2_20261019/profiles'));out=a.parse_args().out;t0=time.time()
    full=labels(pd.read_csv(out/'full_profiles.csv'));fold=pd.concat([labels(g)for _,g in pd.read_csv(out/'fold_profiles.csv').groupby('heldout_building')],ignore_index=True)
    full.to_csv(out/'full_profiles.csv',index=False);fold.to_csv(out/'fold_profiles.csv',index=False)
    d=pd.read_csv(out/'records_flat.csv');main=d[d.quality_usable&d.condition.eq('manual')&d.quality_use.eq('ordinary_primary')]
    rows=[]
    for b,p in fold.groupby('heldout_building'):
        train=main[main.building_id.ne(b)];test=main[main.building_id.eq(b)];fits={}
        for metric in METRICS:
            fits[metric]={'models':{}}
            for scheme in ['fine_dtype','fine_dtype_merged']:
                mp={}
                # Unknown difficulty is retained in the coverage table, not
                # promoted into a pseudo-phenotype that could identify a lone
                # worker and create artificial class-prediction gains.
                known=~p[scheme+'_'+metric].str.contains('unknown',regex=False)
                for _,g in p[known].groupby(scheme+'_'+metric):
                    for diff in DIFFS:
                        mean=g['theta_'+diff+'_'+metric].mean()
                        for w in g.worker_id:mp[(w,diff)]=mean
                fits[metric]['models']['class_'+scheme]=mp
        rows.append(predict_fold(train,test,p,fits,'v2_full_5719'))
    add=pd.concat(rows,ignore_index=True);old=pd.read_csv(out/'validation_predictions.csv.gz');old=old[~old.model.isin(add.model.unique())];allp=pd.concat([old,add],ignore_index=True);allp.to_csv(out/'validation_predictions.csv.gz',index=False,compression='gzip');summaries(allp,out)
    memberships=[]
    for metric in METRICS:
        for scheme in ['fine_dtype','fine_dtype_merged','hard_peer_tag']:
            for lab,g in full.groupby(scheme+'_'+metric):
                r=main[main.worker_id.isin(g.worker_id)]
                memberships.append(dict(metric=metric,scheme=scheme,label=lab,workers=len(g),members=';'.join(g.worker_id),quality_n=len(r),images=r.image_id.nunique(),buildings=r.building_id.nunique(),q_supported_workers=int(g.Q_supported.sum()),t_supported_workers=int(g.T_source_supported.sum()),all_difficulty_supported_workers=int(g[[f'difficulty_supported_{d}'for d in DIFFS]].all(axis=1).sum()),status='unknown_or_sparse'if lab=='unknown'or len(g)<3 else'exploratory_candidate'))
    mc=pd.DataFrame(memberships);mc.to_csv(out/'fine_dtype_membership.csv',index=False)
    oldc=pd.read_csv(out/'class_membership.csv');pd.concat([oldc[~oldc.scheme.isin(mc.scheme.unique())],mc],ignore_index=True).to_csv(out/'class_membership.csv',index=False)
    ss=[]
    for metric in METRICS:
        for w,g in fold.groupby('worker_id'):
            f=full[full.worker_id.eq(w)].iloc[0];r=dict(worker_id=w,metric=metric,folds=len(g))
            for scheme in ['fine_dtype','fine_dtype_merged','hard_peer_tag']:
                r[scheme+'_full']=f[scheme+'_'+metric];r[scheme+'_same_fraction']=g[scheme+'_'+metric].eq(f[scheme+'_'+metric]).mean();r[scheme+'_unique_labels']=g[scheme+'_'+metric].nunique()
            ss.append(r)
    pd.DataFrame(ss).to_csv(out/'fine_dtype_stability.csv',index=False)
    js(out/'DTYPE_EXTENSION_RECEIPT.json',dict(completed=True,extension_registration_sha256=digest(out/'REGISTRATION_DTYPE_EXTENSION.json'),added_prediction_rows=len(add),full_workers=len(full),fold_rows=len(fold),elapsed_seconds=time.time()-t0,code_sha256=digest(Path(__file__)),classification_extension_not_new_blind_hypothesis=True))
    print('COMPLETE',len(add),time.time()-t0)
if __name__=='__main__':main()
