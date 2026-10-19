#!/usr/bin/env python3
"""Adversarial withheld-building/new-background outcome isolation checks."""
from pathlib import Path
import copy,json,hashlib,sys
import numpy as np
import pandas as pd
from discover_reverse_types import (read_geometry_inputs,normalize_events,RelationStore,candidates,cluster_labels,DIFFICULTY_MAP)
from selection_common import attach_relation,fit_calibrator,predict_calibrator
H=Path(__file__).resolve().parent;W=H.parent
rec,pairs=read_geometry_inputs(W/'recovered/work_v2_20261019/clusters/assignments.csv',W/'recovered/work_v2_20261019/clusters/records_geometry.csv')
ev=normalize_events(W/'events/common_events.csv.gz');ev['difficulty']=ev.difficulty.replace(DIFFICULTY_MAP)
sp=json.loads((H/'FROZEN_BUILDING_SPLITS.json').read_text())['folds'];outer='B6ByNegPMKs'
plans=[('outer',sp[outer]['train_buildings']),('outer_plus_inner0',[b for b in sp[outer]['train_buildings'] if b not in sp[outer]['inner_validation_groups']['0']])]
results=[]
for name,train_buildings in plans:
    main=ev[ev.panel_id.eq('Pro_exact_fixed_background_v1')].copy()
    base=RelationStore(rec,pairs,main).fit(train_buildings)
    poisoned_geo=pairs.copy();test_geo=~poisoned_geo.building.isin(train_buildings)
    for c in ['same9','same12','same_point_count']:poisoned_geo.loc[test_geo,c]=1-poisoned_geo.loc[test_geo,c]
    poisoned_geo.loc[test_geo,'abs_point_count_difference']+=1000000
    poisoned_rec=rec.copy();poisoned_rec.loc[~poisoned_rec.building.isin(train_buildings),'B8L2']=1e9
    poisoned_ev=ev.copy();mask=(~poisoned_ev.building.isin(train_buildings))|poisoned_ev.panel_id.eq('A_nested_even_v1')
    poisoned_ev.loc[mask,'stable_main']=np.logical_not(poisoned_ev.loc[mask,'stable_main'].to_numpy(dtype=bool))
    poisoned_main=poisoned_ev[poisoned_ev.panel_id.eq('Pro_exact_fixed_background_v1')]
    alternative=RelationStore(poisoned_rec,poisoned_geo,poisoned_main).fit(train_buildings)
    max_matrix=max(float(np.max(np.abs(base['matrices'][dom][src]-alternative['matrices'][dom][src]))) for dom in base['matrices'] for src in base['matrices'][dom])
    mismatches=0;max_pred=0
    train=main[main.building.isin(train_buildings)];test=ev[~ev.building.isin(train_buildings)]
    for c in candidates(True):
        a,_=cluster_labels(base,c['source'],c['algorithm'],c['k'],c['conditional'])
        b,_=cluster_labels(alternative,c['source'],c['algorithm'],c['k'],c['conditional'])
        mismatches+=a!=b
        if c['method_id'] not in {'reverse_geometry9_average_K4_global','reverse_geometry9_swap_equal_complete_K10_difficulty'}:continue
        domain='difficulty' if c['conditional'] else 'global'
        ca=fit_calibrator(train,attach_relation(train,a,domain))
        cb=fit_calibrator(poisoned_main[poisoned_main.building.isin(train_buildings)],attach_relation(train,b,domain))
        pa=predict_calibrator(ca,test,attach_relation(test,a,domain));pb=predict_calibrator(cb,test,attach_relation(test,b,domain))
        max_pred=max(max_pred,float(np.max(np.abs(pa-pb))) if len(pa) else 0)
    print(json.dumps({'scope':name,'max_matrix':max_matrix,'partition_mismatches':mismatches,'max_prediction':max_pred}),flush=True)
    assert max_matrix==0 and mismatches==0 and max_pred==0
    results.append({'scope':name,'train_buildings':train_buildings,'geometric_test_rows_poisoned':int(test_geo.sum()),
                    'event_outcomes_poisoned':int(mask.sum()),'max_pair_matrix_difference':max_matrix,
                    'candidate_partitions_compared':64,'calibrated_prediction_methods_compared':2,'partition_mismatches':mismatches,'max_prediction_difference':max_pred})
(H/'TRAINING_ISOLATION_RECEIPT.json').write_text(json.dumps({'passed':True,'checks':results,
    'test_quality_poison_value':1e9,'event_poison':'flip all excluded-building and evaluation-only new-background stable outcomes',
    'geometric_poison':'flip excluded-building local co-cluster/point-count flags; offset point-count discrepancy',
    'native_fusion_calls':0,'does_not_claim':'independent external validation or reconstructed collection pipeline'},indent=2)+'\n')
print('training isolation passed',len(results))
