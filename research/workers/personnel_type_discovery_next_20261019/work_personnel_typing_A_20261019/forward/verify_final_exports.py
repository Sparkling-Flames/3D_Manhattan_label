#!/usr/bin/env python3
"""Independent, read-only final CSV/CRC/key/calibrator reconciliation."""
from pathlib import Path
import hashlib,json,time
import numpy as np
import pandas as pd

P=Path(__file__).resolve().parent
def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(2**20),b''):h.update(b)
    return h.hexdigest()

def main():
    started=time.time();counts={};checks=[]
    expected={'candidate_classes_by_fold.csv.gz':49680,'candidate_classes_by_fold_D10.csv.gz':49680,
              'candidate_labels_by_training_set.csv.gz':149040,'candidate_labels_by_training_set_D10.csv.gz':149040,
              'worker_features_by_training_set.csv.gz':4140,'worker_features_by_training_set_D10.csv.gz':4140,
              'fold_features.csv.gz':1380,'fold_features_D10.csv.gz':1380,
              'historical_feature_pair_relations.csv.gz':705240,'historical_feature_pair_relations_D10.csv.gz':705240}
    for n,total in expected.items():
        actual=sum(len(c)for c in pd.read_csv(P/n,chunksize=25000))
        assert actual==total,(n,actual,total)
        counts[n]={'rows':actual,'sha256':sha(P/n),'complete_crc_readback':True}
    sets=json.loads((P/'TRAINING_SETS.json').read_text());aliases=pd.DataFrame(sets['aliases'])
    cands=pd.read_csv(P/'candidate_labels_by_training_set.csv.gz')
    chosen=pd.read_csv(P/'selected_classes_by_fold.csv.gz')
    assert not chosen.duplicated(['fold_id','method_id','difficulty','worker_id']).any()
    joined=chosen.merge(cands[['train_key','method_id','difficulty','worker_id','class_id']].rename(columns={'method_id':'candidate_method','class_id':'candidate_class_id'}),on=['train_key','candidate_method','difficulty','worker_id'],how='left',validate='many_to_one')
    assert joined.class_id.eq(joined.candidate_class_id).all()
    methods=sorted(chosen.method_id.unique());assert len(methods)==14
    counts['selected_classes_by_fold.csv.gz']={'rows':len(chosen),'sha256':sha(P/'selected_classes_by_fold.csv.gz'),'candidate_lookup_exact':True}
    for fold,g in aliases.groupby('fold_id'):
        base=g[g.inner_group.isna()].iloc[0];bs=set(sets['sets'][base.train_key]);f=pd.read_csv(P/'inner_brier'/f'{fold}.csv')
        assert len(f)==len(bs)*28 and not f.duplicated(['method_id','building']).any(),fold
        assert f.groupby('method_id').building.apply(set).apply(lambda x:x==bs).all(),fold
        checks.append({'fold_id':fold,'rows':len(f),'training_buildings':len(bs),'full_candidate_building_grid':True})
    evcols=['event_id','building','panel_id']
    events=pd.concat(pd.read_csv(P.parent/'events/common_events.csv.gz',usecols=evcols,chunksize=25000),ignore_index=True)
    assert events.event_id.is_unique and len(events)==286666
    ei={x:i for i,x in enumerate(events.event_id)};mi={x:i for i,x in enumerate(methods)}
    seen=np.zeros((len(methods),len(events)),dtype=np.bool_)
    cals=json.loads((P/'FROZEN_CALIBRATORS.json').read_text());maxdiff=0.;total=0
    for ch in pd.read_csv(P/'event_predictions.csv.gz',chunksize=25000):
        assert ch.probability.between(0,1).all()
        ex=ch.event_id.map(ei);mx=ch.method_id.map(mi)
        assert ex.notna().all()and mx.notna().all()
        a=mx.to_numpy(dtype=int);b=ex.to_numpy(dtype=int)
        assert not np.any(seen[a,b]) and len(set(zip(a,b)))==len(ch)
        seen[a,b]=True
        assert np.all(ch.building.to_numpy()==events.building.to_numpy()[b])
        assert np.all(ch.panel_id.to_numpy()==events.panel_id.to_numpy()[b])
        assert ch.fold_id.eq(ch.building).all()
        for (fold,method),g in ch.groupby(['fold_id','method_id']):
            c=cals[fold][method];rates={(int(k),d,r):v for k,d,r,v in c['rates']};cells={(int(k),d):v for k,d,v in c['cells']};ks={int(k):v for k,v in c['k'].items()}
            p=np.array([rates.get((int(k),d,r),cells.get((int(k),d),ks.get(int(k),c['global'])))for k,d,r in zip(g.k,g.difficulty,g.predicted_relation)])
            maxdiff=max(maxdiff,float(np.max(np.abs(p-g.probability.to_numpy()))))
            assert np.all(g.candidate_method.eq(c['candidate_method']))
        total+=len(ch)
    assert total==4013324 and seen.all() and maxdiff<1e-12
    counts['event_predictions.csv.gz']={'rows':total,'sha256':sha(P/'event_predictions.csv.gz'),'complete_crc_readback':True,'unique_event_method_grid':True,'calibrator_probability_max_abs_diff':maxdiff}
    for n in ['selected_methods.csv','candidate_selection_process.csv','frozen_training_calibration.csv','inner_validation_building_scores.csv.gz']:
        f=pd.read_csv(P/n);counts[n]={'rows':len(f),'sha256':sha(P/n),'complete_readback':True}
    receipt={'status':'COMPLETE','output_writer_status':'both original and fast runs have exited; no active selector writes',
             'published_predictions_origin':'successful original shared-selection implementation; fast run failed CRC on its unique temporary .writing path before publish',
             'failed_fast_publish':False,'temporary_gzip_failure_cause':'not established; preserved without claiming a scientific discrepancy',
             'original_full_prediction_receipt':json.loads((P/'SELECTION_PREDICTION_RECEIPT.json').read_text()),
             'calibrations_reconciled_to_published_predictions':True,'counts_and_hashes':counts,'inner_cache_checks':checks,'seconds':time.time()-started}
    (P/'FINAL_EXPORT_COMPLETE.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'status':'COMPLETE','prediction_rows':total,'max_probability_difference':maxdiff,'seconds':time.time()-started}))
if __name__=='__main__':main()
