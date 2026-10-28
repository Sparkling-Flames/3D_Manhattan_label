import json
import pandas as pd
import numpy as np
from tools.thesis_main.analysis.extend_v21_admitted_spaces_20261029 import OUT, TARGET


def read(path):
    return json.loads(path.read_text(encoding='utf8'))


def test_extension_preserves_original_inventory_and_target_identity():
    old=read(OUT/'quality_inventory.json'); selected=read(TARGET/'ANALYSIS_RECORDS.json')
    pools=read(TARGET/'pools/INPUT_SNAPSHOT.json')['images']
    assert len(old)==10439 and sum(r['quality_usable'] for r in old)==8154
    assert len(selected)==231 and len(pools)==31
    lookup={r['object_id']:r for r in old}
    assert len({r['object_id'] for r in selected})==231
    for r in selected:
        before=lookup[r['object_id']]
        assert before['quality_exclusion_reasons']==['bound_other_admitted_space']
        assert r['B8L2']==before['diagnostic_B8L2'] and r['D10']==before['diagnostic_D10']
        assert r['reference_id']==before['reference_id']
    for p in pools:
        records=p['records'];assert len(records)>=3
        assert len({r['worker_id'] for r in records})==len(records)
        assert all(lookup[r['object_id']]['reference_id']==p['reference']['target_id'] for r in records)
        assert p['meta']['difficulty']=='未分级' and not p['meta']['difficulty_aligned']


def test_multiple_targets_do_not_duplicate_image_weight():
    from tools.thesis_main.analysis.summarize_v21_admitted_spaces_20261029 import image_weights
    d=pd.DataFrame(dict(pool_id=['a1','a2','b1'],image=['a','a','b'],building=['A','A','B']))
    for weighting in ['image_equal','building_equal']:
        w=image_weights(d,weighting)
        np.testing.assert_allclose(w,[.25,.25,.5])
        assert np.isclose(w@np.array([0.,100.,100.]),75)


def test_saved_extension_paths_rates_and_two_person_supplement():
    curves=pd.read_csv(TARGET/'natural_analysis/UPDATED_CURVES.csv.gz',low_memory=False)
    assert len(curves)==231 and curves.pool_id.nunique()==31
    nondeferred=curves[curves.k.ne(2)]
    assert nondeferred.nondeferred_attempts.eq(256).all()
    assert curves[curves.k.eq(2)].actual_consensus_failure_rate.isna().all()
    assert curves[curves.k.eq(2)].policy_deferred_paths.eq(256).all()
    for pid,g in curves.groupby('pool_id'):
        raw=pd.read_csv(TARGET/'natural_inputs'/(pid+'.csv.gz'),low_memory=False)
        assert raw.groupby('path_id').k.nunique().eq(g.pool_n.iloc[0]).all()
        assert raw.path_id.nunique()==256
        for r in g[g.k.ne(2)].itertuples():
            d=raw[raw.k.eq(r.k)]
            assert np.isclose(r.Q_mean,d.B8L2.mean(),equal_nan=True)
            expected=d.score_status.isin(['no_connection','below_four','fusion_exception']).mean()
            assert np.isclose(r.actual_consensus_failure_rate,expected)
    two=pd.read_csv(TARGET/'two_person_natural256/PAIRED_PATH_RESULTS.csv.gz')
    assert len(two)==31*256 and not two.duplicated(['pool_id','path_id']).any()
    assert not two.score_status.eq('two_person_deferred').any()
    assert two.Q2.notna().sum()==6599
    assert two.failure.sum()==1337
    summary=pd.read_csv(TARGET/'SUMMARY.csv')
    for r in summary[(summary.panel=='available_at_k') & (summary.metric=='Q_mean') & (summary.k==3)].itertuples():
        display=pd.read_csv(TARGET/'DISPLAY_CURVES.csv.gz',low_memory=False)
        d=display[(display.k==3)&(display.layer==r.layer)&(display.condition==r.condition)]
        if r.support!='combined':d=d[d.support==r.support]
        image=d.groupby(['building','image']).Q_mean.mean()
        expected=image.mean() if r.weighting=='image_equal' else image.groupby(level=0).mean().mean()
        assert np.isclose(r.estimate,expected)


def test_extended_quality_history_keeps_peer_target_and_frozen_behavior():
    old=pd.read_csv(OUT/'joint_history_classification/BEHAVIOR_RECORDS.csv.gz',low_memory=False).set_index('object_id')
    new=pd.read_csv(TARGET/'joint_history_classification/BEHAVIOR_RECORDS.csv.gz',low_memory=False).set_index('object_id')
    additions=read(TARGET/'ANALYSIS_RECORDS.json');ids=[r['object_id'] for r in additions]
    assert len(old)==len(new) and old.index.equals(new.index)
    invariant=read(TARGET/'joint_history_classification/CHECKS.json')['behavior_feature_columns_verified_equal']
    pd.testing.assert_frame_equal(old[invariant],new[invariant])
    assert not old.loc[ids,'quality_usable'].any() and new.loc[ids,'quality_usable'].all()
    for r in additions:assert np.isclose(new.at[r['object_id'],'B8L2'],r['B8L2'])
    keys=['condition','layer','image_id','reference_id']
    qok=new.quality_usable & (~new.layer.eq('ordinary') | new.quality_use.eq('ordinary_primary'))
    expected=new.B8L2-new.loc[qok].groupby(keys,dropna=False).B8L2.transform('mean')
    np.testing.assert_allclose(new.B8L2_peer_delta,expected.reindex(new.index),equal_nan=True,atol=1e-12)
