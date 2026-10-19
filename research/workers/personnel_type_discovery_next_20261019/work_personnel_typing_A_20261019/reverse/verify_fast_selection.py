#!/usr/bin/env python3
"""All-64 candidate equivalence to completed original Pandas selection folds."""
import sys,json,hashlib,time
from pathlib import Path
import numpy as np
import pandas as pd
H=Path(__file__).resolve().parent;W=H.parent
sys.path.insert(0,str(W/'forward'))
import selection_fast as fast
from discover_reverse_types import normalize_events,DIFFICULTY_MAP,candidates
from selection_common import attach_relation,one_se_choice
start=time.time();ev=normalize_events(W/'events/common_events.csv.gz');ev['difficulty']=ev.difficulty.replace(DIFFICULTY_MAP)
main=ev[ev.panel_id.eq('Pro_exact_fixed_background_v1')]
splits=json.loads((H/'FROZEN_BUILDING_SPLITS.json').read_text())['folds'];checks=[]
for fold in ['FULL','2t7WUuJeko7']:
    fp=H/'results/folds'/fold
    reference_scores=pd.read_csv(fp/'inner_building_scores.csv.gz');inner_classes=pd.read_csv(fp/'inner_classes.csv.gz')
    allclasses=pd.read_csv(fp/'classes.csv.gz');refcal=pd.read_csv(fp/'calibration.csv.gz')
    refselect=pd.read_csv(fp/'candidate_selection.csv');sp=splits[fold];scores=[];maxrate=maxpredict=maxbrier=0.
    for inner,held in sp['inner_validation_groups'].items():
        tr=main[main.building.isin([b for b in sp['train_buildings'] if b not in held])];va=main[main.building.isin(held)]
        itrain=fast.EncodedPanel(tr);ival=fast.EncodedPanel(va)
        old=reference_scores[reference_scores.inner_group.astype(str).eq(str(inner))]
        classes=inner_classes[inner_classes.fold_id.eq(f'{fold}__inner{inner}')]
        for c in candidates(True):
            g=classes[classes.method_id.eq(c['method_id'])]
            lab={(r.domain,r.worker_id):r.class_id for r in g.itertuples()} if c['conditional'] else g.set_index('worker_id').class_id.to_dict()
            domain='difficulty' if c['conditional'] else 'global'
            cal=itrain.fit(attach_relation(tr,lab,domain));pred=ival.predict(cal,attach_relation(va,lab,domain));bs=ival.brier(pred)
            ref=old[old.method_id.eq(c['method_id'])][['building','brier']]
            x=ref.merge(bs,on='building',suffixes=('_reference','_fast'),validate='one_to_one')
            assert len(x)==len(ref)==len(bs)
            maxbrier=max(maxbrier,float(abs(x.brier_reference-x.brier_fast).max()))
            bs['method_id']=c['method_id'];scores.append(bs)
    train=main[main.building.isin(sp['train_buildings'])];enc=fast.EncodedPanel(train)
    test=ev[ev.building.eq(fold)] if fold!='FULL' else None
    predref=pd.read_csv(fp/'predictions.csv.gz',usecols=['event_id','method_id','probability']) if fold!='FULL' else None
    testpanel=fast.EncodedPanel(test) if fold!='FULL' else None
    for c in candidates(True):
        g=allclasses[allclasses.method_id.eq(c['method_id'])]
        lab={(r.domain,r.worker_id):r.class_id for r in g.itertuples()} if c['conditional'] else g.set_index('worker_id').class_id.to_dict()
        domain='difficulty' if c['conditional'] else 'global'
        cal=enc.fit(attach_relation(train,lab,domain))
        rf=refcal[refcal.method_id.eq(c['method_id'])]
        for r in rf.itertuples():
            value=cal['cells'][(r.k,r.difficulty)] if r.relation=='unknown' else cal['rates'][(r.k,r.difficulty,r.relation)]
            maxrate=max(maxrate,abs(value-r.probability))
        if testpanel is not None:
            prob=testpanel.predict(cal,attach_relation(test,lab,domain))
            rf=predref[predref.method_id.eq(c['method_id'])].set_index('event_id').loc[test.event_id].probability.to_numpy()
            maxpredict=max(maxpredict,float(np.max(np.abs(prob-rf))))
    choice,selection=one_se_choice(pd.concat(scores),refselect[['method_id','complexity_order','tie_order']])
    refchoice=refselect[refselect.selected.eq(True)].iloc[0].method_id
    assert choice==refchoice and max(maxrate,maxpredict,maxbrier)<1e-12
    checks.append({'fold_id':fold,'candidate_count':64,'inner_groups':3,'max_calibration_rate_difference':maxrate,'max_outer_prediction_difference':maxpredict,
                   'max_inner_building_Brier_difference':maxbrier,'original_choice':refchoice,'accelerated_choice':choice,'choice_identical':True})
    print(f'fast parity {fold} {maxbrier:.3g} {maxrate:.3g}',flush=True)
r={'passed':True,'checks':checks,'seconds':time.time()-start,'tolerance':1e-12,
   'reference_selector_sha256':hashlib.sha256((H/'selection_common.py').read_bytes()).hexdigest(),
   'fast_sidecar_sha256':hashlib.sha256((W/'forward/selection_fast.py').read_bytes()).hexdigest(),
   'scientific_definition_change':False,'new_candidates':False}
(H/'FAST_SELECTION_PARITY.json').write_text(json.dumps(r,indent=2)+'\n')
