import json
import numpy as np
import pandas as pd
from tools.thesis_main.analysis.rebuild_v21_20261028 import OUT,ROOT


def test_current_exchange_partition_and_signed_contrasts():
    root=OUT/'current_exchange_results'
    checks=json.loads((root/'SUMMARY_CHECKS.json').read_text(encoding='utf8'))
    for stage in ['confirm','reverse_confirm']:
        original=pd.read_csv(root/stage/'original_reference/EVENTS_EXACT.csv.gz',usecols=['event_id'])
        added=pd.read_csv(root/stage/'added_reference/EVENTS_EXACT.csv.gz',usecols=['event_id'])
        d=pd.read_csv(root/stage/'EVENT_METRICS.csv.gz',low_memory=False)
        assert not set(original.event_id)&set(added.event_id)
        assert set(original.event_id)|set(added.event_id)==set(d.event_id)
        assert d.event_id.is_unique
        for metric in ['B8L2','D10','floor_turn5_n']:
            for contrast,a,b in [('CA','C','A'),('CB','C','B'),('BA','B','A')]:
                np.testing.assert_allclose(d[metric+'_'+contrast],d[a+'_'+metric]-d[b+'_'+metric],atol=1e-10,equal_nan=True)
        check=next(c for c in checks if c['stage']==stage and c['cohort']=='combined')
        assert check['complete'] and check['events']==len(d)


def test_d10_formation_uses_current_baseline_without_training_leakage():
    root=OUT/'d10_formation_sensitivity'
    for stage in ['FORMATION','RESPONSE','SUMMARY','STRUCTURE']:
        r=json.loads((root/(stage+'_COMPLETE.json')).read_text())
        assert r['complete'] and r['baseline']=='current_v21_B8L2'
    d=pd.read_csv(root/'TRAINING_EXCLUSION_LEDGER.csv')
    assert len(d)>100 and d.target_outer_in_training.eq(0).all() and d.target_inner_in_training.eq(0).all()
    old=ROOT/'research/workers/personnel_mixture_comparison_20261022/configurations'
    for name in ['PANELS_USED.csv','PANEL_TEAMS.csv.gz']:
        pd.testing.assert_frame_equal(pd.read_csv(old/name),pd.read_csv(root/'configuration_inputs'/name))
    current=pd.read_csv(OUT/'joint_history_classification/ALL_METHOD_LABELS_LOBO.csv.gz')
    baseline=pd.read_csv(root/'current_B8_source/JOINT_LABELS_LOBO.csv.gz')
    keys=['condition','heldout_building','worker_id']
    current=current[current.method.eq('V3_JOINT_QT')&current.heldout_building.ne('ALL')]
    joined=baseline.merge(current,on=keys,validate='one_to_one',suffixes=('_saved','_current'))
    assert len(joined)==len(baseline)==len(current)
    for field in ['coarse_label','fine_label','known']:
        assert joined[field+'_saved'].fillna('').eq(joined[field+'_current'].fillna('')).all()


def test_secondary_policy_small_pool_keeps_exact_six_orders():
    d=pd.read_csv(OUT/'current_policy_results/secondary/POLICY_IMAGE_K.csv.gz')
    small=d[d.pool_id.eq('X7HyMhZNoso-19__semi__4177d22d41')]
    assert len(small)>0 and small.base_paths.eq(6).all()
    assert d.loc[d.k.eq(2),'paired_Q_delta'].isna().all()
    assert d.loc[d.k.eq(2),'execution_status'].eq('not_executed_policy_k2').all()


def test_current_same_room_geometry_complete_with_current_reference_identity():
    root=OUT/'same_room_current_results/large'
    r=json.loads((root/'geometry/CHECKS.json').read_text(encoding='utf8'))
    assert r['complete'] and r['geometry_rows']==6*r['events']==377784
    assert sum(p['recovered_geometries'] for p in r['pools'])==0
    d=pd.read_csv(root/'geometry/EVENT_GEOMETRY_RESULTS.csv.gz',usecols=['event_id','view','comparison','pool_id','reference_id','reference_version'])
    assert not d.duplicated(['event_id','view','comparison']).any()
    pools={p['pool_id']:p['meta'] for p in json.loads((OUT/'pools/INPUT_SNAPSHOT.json').read_text(encoding='utf8'))['images']}
    for pid,g in d.groupby('pool_id'):
        assert g.reference_id.eq(pools[pid]['reference_id']).all()
        assert g.reference_version.eq(pools[pid]['reference_version']).all()


def test_current_policy_aggregate_support_and_missing_two_person_cells():
    for cohort,images,buildings in [('original_common32',153,21),('added_reference32',26,10)]:
        root=OUT/'current_policy_results'/cohort
        r=json.loads((root/'CHECKS.json').read_text(encoding='utf8'))
        assert (r['images'],r['buildings'],r['bootstrap'])==(images,buildings,2000)
        result=root/'analysis_policy26/results'
        d=pd.read_csv(result/'POLICY_IMAGE_K.csv.gz')
        assert d.pool_id.nunique()==images
        assert d.loc[d.k.eq(2),'paired_Q_delta'].isna().all()
        assert d.loc[d.k.eq(2),'execution_status'].eq('not_executed_policy_k2').all()
        summary=pd.read_csv(result/'POLICY_PRECISION_SUMMARY.csv')
        assert summary.bootstrap_replicates.eq(2000).all()
        assert summary.path_valid_replicates.add(summary.path_invalid_replicates).eq(2000).all()
