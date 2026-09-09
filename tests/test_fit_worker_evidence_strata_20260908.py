import numpy as np
import pandas as pd
import pytest
from tools.thesis_main.analysis import fit_worker_evidence_strata_20260908 as m


def sample(effects=(-2.,-1.,1.,2.)):
    return pd.DataFrame([dict(canonical_annotation_id=f'{b}:{t}:{w}',context_key=f'C1|{t}|image{b}|manual',
        building_id=str(b),worker_id=str(w),value=10*b+t+e)
        for b in range(5) for t in range(2) for w,e in enumerate(effects)])


def test_sufficient_fit_matches_existing_fixed_effects_and_weighted_buildings():
    d=sample();s=m.sufficient(d);weights=np.array([0,1,2,0,2])
    beta,status,rank=m.solve(s,weights)
    expanded=pd.concat([d[d.building_id==str(b)] for b,n in enumerate(weights) for _ in range(n)])
    old=m.fit_effects(expanded.assign(base_task_id=expanded.context_key),'value')
    assert status=='usable' and rank==3
    assert np.allclose(beta,old.reindex(s['workers']))


def test_image_only_has_no_worker_effect_and_true_worker_signal_generalizes():
    for effects,signal in [((0.,0.,0.,0.),False),((-2.,-1.,1.,2.),True)]:
        p,diag=m.fit_one(sample(effects),seed=12,replicates=500)
        assert len(diag)==500
        if signal:assert set(p.label)=={'high','low'}
        else:assert set(p.label)=={'uncertain'} and np.allclose(p.effect,0)
        train=sample(effects).query('building_id != "4"')
        test=sample(effects).query('building_id == "4"')
        profiles,_=m.fit_one(train,seed=13,replicates=500)
        pred=m.predict_peers(test,profiles)
        if signal:assert pred.layer_sqerr.sum()<pred.baseline_sqerr.sum()
        else:assert pred.layer_sqerr.sum()==0


def test_missing_roster_and_disconnected_contexts_fail_without_redraw():
    d=sample();d=d[~((d.worker_id=='3')&(d.building_id!='0'))]
    p,diag=m.fit_one(d,seed=9,replicates=500)
    assert len(diag)==500 and (diag.status=='missing_workers').any()
    assert p.loc[p.worker_id=='3','label'].iloc[0]=='insufficient'
    d=sample();d=d[((d.worker_id<'2')&(d.context_key.str.contains('|0|',regex=False)))|((d.worker_id>='2')&(d.context_key.str.contains('|1|',regex=False)))]
    _,status,_=m.solve(m.sufficient(d),np.ones(5))
    assert status=='disconnected_graph'


def test_identity_missingness_and_prediction_center_are_explicit():
    d=sample()
    with pytest.raises(ValueError,match='duplicate'):
        m.sufficient(pd.concat([d,d.iloc[:1]]))
    bad=d.copy();bad.loc[0,'value']=np.nan
    with pytest.raises(ValueError,match='finite'):
        m.sufficient(bad)
    p,_=m.fit_one(d,seed=11,replicates=500)
    test=d[d.worker_id!='0'].copy()
    out=m.predict_peers(test,p)
    assert np.allclose(out.groupby('context_key').target.mean(),0)
    assert np.allclose(out.groupby('context_key').continuous_prediction.mean(),0)
    changed=test.copy();changed['value']+=999
    assert np.allclose(m.predict_peers(changed,p).continuous_prediction,out.continuous_prediction)


def test_training_classification_isolated_and_reference_recentered():
    import csv
    import io
    from tools.thesis_main.analysis.summarize_worker_evidence_20260908 import paired_effects
    d=sample();changed=d.copy();changed.loc[changed.building_id=='4','value']*=1000
    key=('C1','manual','corner_pair_count','raw_point_count','not_applicable','available')
    fits=[]
    for data in [d,changed]:
        writer=csv.DictWriter(io.StringIO(),fieldnames=['fit_id','replicate','status','rank','missing_workers','building_counts_json'])
        fits.append(m.fit_parts(data[data.building_id!='4'],key,'4',writer))
    pd.testing.assert_frame_equal(*fits)
    assert all('"4"' not in s for s in fits[0].training_buildings)
    variant=('C1','manual','bi_delta','serialized_adjacency','native_uv','available')
    writer=csv.DictWriter(io.StringIO(),fieldnames=['fit_id','replicate','status','rank','missing_workers','building_counts_json'])
    other=m.fit_parts(d[d.building_id!='4'],variant,'4',writer)
    assert (fits[0].seed==other.seed).all()  # Matched sensitivity uses identical bootstrap weights.
    z=paired_effects(fits[0],fits[1][fits[1].worker_id!='0'].assign(effect=lambda q:q.effect+100))
    assert np.allclose(z.centered_a,z.centered_b)


def test_common_sample_and_provenance_sensitivity_do_not_substitute_versions():
    rows=[]
    for identity in ['a','b','c']:
        for reading in ['serialized_adjacency','historical_pairmap_unaveraged']:
            rows.append(dict(canonical_annotation_id=identity,stage='C1',raw_condition='manual',metric='log_floor_area',
                reading=reading,representation='raw_float_coordinates',value=np.nan if (identity,reading)==('b','serialized_adjacency') else 1.))
    flags=pd.DataFrame(dict(canonical_annotation_id=['a','b','c'],has_revision=[False,True,False],multiple_condition_observed=[False,False,True]))
    out=m.analysis_cohorts(pd.DataFrame(rows),flags)
    assert set(out[out.cohort=='common_geometry'].canonical_annotation_id)=={'a','c'}
    assert set(out[out.cohort=='no_revision_or_crosscondition'].canonical_annotation_id)=={'a'}
    assert len(out[out.cohort=='available'])==6
