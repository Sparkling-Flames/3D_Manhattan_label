import numpy as np
import pandas as pd
import pytest
from tools.thesis_main.analysis import wall_consensus_v1_process_20261017 as process
from tools.thesis_main.analysis.wall_consensus_v1_process_20261017 import cached_matching, selected_state, original_disagreement
from tools.thesis_main.analysis.consensus_delivery_20261008 import fuse


def records():
    pts=[[80,120],[80,380],[300,120],[300,380],[570,120],[570,380],[810,120],[810,380]]
    return [dict(id='R'+str(i),worker='P'+str(i),points=pts,source_pair_indices=list(range(4)),ring_confirmed=False) for i in range(3)]


def test_csv_false_and_blank_are_not_holdout_flags():
    assert not process.explicit_true('False')
    assert not process.explicit_true('')
    assert process.explicit_true('True') and process.explicit_true(True)
    assert process.explicit_true(np.bool_(True))


def test_cached_matching_preserves_subset_only_fusion_and_k2():
    rs=records(); expected=fuse(rs)['automatic']
    with cached_matching():
        a=selected_state(rs,{})
        b=selected_state(list(reversed(rs)),{})
        two=selected_state(rs[:2],{})
    assert a==b and a['node_consensus']==expected['node_consensus'] and a['candidate']==expected['candidate']
    assert two['candidate']['points'] is None
    assert len(a['assignments'])==3


def test_original_disagreement_excludes_self_pairs_and_keeps_pair_denominator():
    d=np.array([[0,2,np.nan],[2,0,4],[np.nan,4,0.]])
    r=original_disagreement([0,1,2],d,10)
    assert r['R_valid_pairs']==2 and r['R_possible_pairs']==3
    assert r['R_symdiff_h2']==3 and r['R_union_normalized']==.3
    assert original_disagreement([0],d,10)['R_symdiff_h2'] is None


@pytest.mark.parametrize('layer,mixed,quality', [('ordinary',False,True),('ordinary',True,False),('oos_diagnostic',False,False)])
def test_real_replay_masks_oos_mixed_targets_and_missing_time(tmp_path,monkeypatch,layer,mixed,quality):
    rs=records()
    for i,r in enumerate(rs):
        r.update(worker_id='W'+str(i),object_id='O'+str(i),chosen_target_id='other' if mixed and i==0 else 'reference',
                 quality_usable=True,original_holdout=False,source_time_seconds=None)
    ref=dict(target_id='reference',reference_version='test',points_1024x512=rs[0]['points'],
             floor_xz_h=process.reconstruct(rs[0])['floor'].tolist(),full_reference_available=True)
    monkeypatch.setattr(process,'OUT',tmp_path)
    monkeypatch.setattr(process,'legacy_states',lambda im:({},{}))
    process.run_image(dict(pool_id='sample__manual',image='sample',condition='manual',
        layer=layer,difficulty='test',scene='oos' if layer=='oos_diagnostic' else 'clear',records=rs,reference=ref))
    frame=pd.read_csv(tmp_path/'pools/sample__manual/observations.csv')
    end=frame[frame.k==3]
    assert end.B8L2.notna().all()==quality
    assert end.diagnostic_B8L2.notna().all()
    assert frame.source_active_seconds.isna().all()
    assert frame[frame.k==2].diagnostic_B8L2.isna().all()


def test_request_expansion_keeps_complete_cached_measurement_payload(tmp_path,monkeypatch):
    rs=records()
    for i,r in enumerate(rs):
        r.update(worker_id='W'+str(i),object_id='O'+str(i),chosen_target_id='reference',
                 quality_usable=True,original_holdout=False,source_time_seconds=None)
    ref=dict(target_id='reference',reference_version='test',points_1024x512=rs[0]['points'],
             floor_xz_h=process.reconstruct(rs[0])['floor'].tolist(),full_reference_available=True)
    im=dict(pool_id='sample__manual',image='sample',condition='manual',layer='ordinary',
            difficulty='test',scene='clear',records=rs,reference=ref)
    monkeypatch.setattr(process,'OUT',tmp_path)
    monkeypatch.setattr(process,'legacy_states',lambda im:({},{}))
    measure=process.measured;measurement_fields=set()
    def future_measure(*args):
        raw=dict(measure(*args),future_measurement_field=42.)
        measurement_fields.update(raw)
        return raw
    monkeypatch.setattr(process,'measured',future_measure)
    process.run_image(im)
    file=tmp_path/'pools/sample__manual/observations.csv'
    before=pd.read_csv(file).set_index(['path_id','k'])
    im['requested_orders']=[dict(path_id='extra',kind='test',workers=['W2','W1','W0'],request_id='extra')]
    process.run_image(im)
    after=pd.read_csv(file).set_index(['path_id','k'])
    for field in measurement_fields:
        assert field in after,field
        pd.testing.assert_series_equal(before[field],after.loc[before.index,field],check_dtype=False)
    im['reference']=dict(ref,reference_version='changed')
    with pytest.raises(ValueError,match='measurement_cache_context_changed'):
        process.run_image(im)


def test_main_panel_excludes_holdout_and_v_strict_pairs_are_separate():
    from tools.thesis_main.analysis.wall_consensus_v1_summary_20261017 import random_panels
    rows=[]
    for pool,main in [('a',True),('holdout',False)]:
        for path in ['p0','p1','p2']:
            for k in [8,16]:
                rows.append(dict(pool_id=pool,image=pool,condition='manual',layer='ordinary',difficulty='simple',
                    path_kind='random',path_id=path,k=k,B8L2=10.+(k==16),D10=11.+(k==16),
                    main_comparison_allowed=main,complete_evaluable=True))
    stability=pd.DataFrame([dict(pool_id=pool,k=k,path_a=a,path_b=b,floor_jaccard_difference=v)
        for pool in ['a','holdout'] for k,a,b,v in [(8,'p0','p1',.2),(8,'p0','p2',.4),(16,'p0','p1',.1),(16,'p1','p2',.7)]])
    descriptive,main=random_panels(pd.DataFrame(rows),stability)
    descriptive=descriptive[descriptive.k_from==8];main=main[main.k_from==8]
    assert len(descriptive)==2 and main.pool_id.tolist()==['a']
    row=main.iloc[0]
    assert not row.V_pair_sets_equal and row.V_strict_pairs==1
    assert row.V_to>row.V_from and row.V_strict_to<row.V_strict_from
