"""Explicit post-hoc audit of a weak worker-pair-history baseline.

The registered baseline keyed ordered output records and pooled difficulties.
Those choices can lose reciprocal history and confound easy/hard prevalence.
This audit changes only those two choices, retains shrinkage 5, and evaluates
all existing outer-building folds. It is a diagnostic follow-up, not a newly
untouched confirmation set or a reason to retune any personnel classes.
"""
from __future__ import annotations
import hashlib,json
from pathlib import Path
import numpy as np
import pandas as pd
from cluster_transfer import prior_predict
from analyze_fusion_clusters import bs
HERE=Path(__file__).resolve().parent

def main():
    out=HERE/'pair_history_diagnostic';out.mkdir(exist_ok=True)
    d=pd.read_csv(HERE/'pair_distances.csv.gz');d=d[d.layer.eq('ordinary_manual')].copy()
    d['canonical_pair']=['|'.join(sorted((a,b))) for a,b in zip(d.worker_id_a,d.worker_id_b)]
    d['target_9']=d.same_affinity_9.astype(int);d['target_12']=d.same_affinity_12.astype(int)
    predictions=[];coverage=[]
    for b in sorted(d.building_id.unique()):
        train=d[d.building_id.ne(b)];test=d[d.building_id.eq(b)]
        for cut in [9,12]:
            target='target_'+str(cut);base=prior_predict(train,test,target)
            for name,keys in [('ordered_unconditional',['worker_id_a','worker_id_b']),('unordered_unconditional',['canonical_pair']),('unordered_same_difficulty',['canonical_pair','difficulty'])]:
                counts=train.groupby(keys)[target].agg(['sum','count'])
                idx=pd.MultiIndex.from_frame(test[keys]) if len(keys)>1 else pd.Index(test[keys[0]])
                c=counts.reindex(idx);n=c['count'].fillna(0).to_numpy();s=c['sum'].fillna(0).to_numpy();pred=(s+5*base)/(n+5)
                z=test[['pool_id','image_id','image_code','building_id','difficulty','object_id_a','object_id_b','worker_id_a','worker_id_b','canonical_pair']].copy()
                z['threshold_deg']=cut;z['model']=name;z['target']=test[target].to_numpy();z['prediction']=pred;z['prior_prediction']=base;z['historical_images']=n
                z['brier']=(pred-z.target)**2;z['prior_brier']=(base-z.target)**2;predictions.append(z)
                coverage.append(dict(heldout_building=b,threshold_deg=cut,model=name,test_pairs=len(test),historical_pair_supported=int((n>0).sum()),mean_history_images=n.mean(),
                    test_images=test.pool_id.nunique(),test_buildings=1,no_target_building_history=True))
    p=pd.concat(predictions,ignore_index=True);p.to_csv(out/'heldout_predictions.csv.gz',index=False)
    key=['threshold_deg','model','pool_id','image_id','image_code','building_id','difficulty'];im=p.groupby(key)[['brier','prior_brier','historical_images']].mean().reset_index();im.to_csv(out/'image_scores.csv',index=False)
    rows=[]
    for (cut,model),g in im.groupby(['threshold_deg','model']):
        b=g.groupby('building_id')[['brier','prior_brier']].mean();delta=b.brier-b.prior_brier;stat=bs(delta)
        rows.append(dict(threshold_deg=cut,model=model,images=g.image_id.nunique(),buildings=len(b),brier=b.brier.mean(),prior_brier=b.prior_brier.mean(),
            delta_brier=stat['mean'],low=stat['low'],high=stat['high'],improved_buildings=int(delta.lt(0).sum())))
    pd.DataFrame(rows).to_csv(out/'summary.csv',index=False);pd.DataFrame(coverage).to_csv(out/'coverage.csv',index=False)
    r=dict(status='post_hoc_diagnostic_after_registered_history_baseline_performed_poorly',
        histories_keyed_by_unordered_people_and_frozen_difficulty=True,original_baseline_recomputed_as_control=True,
        targets_unchanged=True,shrinkage_retained=5,all_original_outer_building_folds=True,
        not_new_blind_data=True,no_personnel_label_or_cluster_tuning=True,
        input_sha256=hashlib.sha256((HERE/'pair_distances.csv.gz').read_bytes()).hexdigest())
    (out/'RECEIPT.json').write_text(json.dumps(r,indent=2)+'\n');print(pd.DataFrame(rows).to_string(index=False))

if __name__=='__main__':main()
