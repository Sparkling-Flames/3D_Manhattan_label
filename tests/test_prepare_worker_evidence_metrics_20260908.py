import numpy as np
import pandas as pd
import pytest

from tools.thesis_main.analysis.prepare_worker_evidence_metrics_20260908 import pair_count, attach_identity, validate_index, reference_dispute_status, summarize_auxiliary, response_history_flags, META


def test_raw_count_and_complete_identity():
    p = np.array([[.3, .7], [.3, .9], [.6, .5], [.6, .8]])
    before = p.copy()
    assert pair_count(p) == (2., 'computable')
    assert np.array_equal(p, before)
    assert pair_count(p[:3])[1] == 'odd_point_count'
    assert np.isnan(pair_count([])[0])
    assert reference_dispute_status('available') == 'unknown_not_adjudicated'
    assert reference_dispute_status('researcher_confirmed_bad_gt') == 'source_researcher_confirmed_bad_gt'
    a = pd.DataFrame([{k: 'x' for k in META}, {k: 'x' for k in META}])
    a['canonical_annotation_id'] = ['a','b']
    a['context_key'] = ['C2|1|image|manual', 'C2|2|image|manual']
    validate_index(a)  # Same worker/image across blocks remains distinct.
    joined = attach_identity(pd.DataFrame({'canonical_annotation_id':['b']}), a)
    assert joined.context_key.iloc[0] == 'C2|2|image|manual'
    with pytest.raises(AssertionError):
        validate_index(pd.concat([a, a.iloc[:1]]))
    with pytest.raises(AssertionError):
        attach_identity(pd.DataFrame({'canonical_annotation_id':['b'],'context_key':['C2|1|image|manual']}), a)


def test_auxiliary_missing_time_is_not_zero():
    f = pd.DataFrame(dict(worker_id=[1,1,2], stage=['C1']*3, raw_condition=['manual']*3,
                          canonical_annotation_id=['a','b','c'], context_key=['x','y','z'],
                          building_id=['b1','b2','b1'], seconds=[10.,np.nan,np.nan]))
    s = summarize_auxiliary(f, [], 'seconds', 'active_time','seconds').set_index('worker_id')
    assert s.loc[1,'mean'] == 10 and s.loc[1,'observed_values'] == 1
    assert s.loc[1,'missing_values'] == 1
    assert np.isnan(s.loc[2,'mean']) and s.loc[2,'observed_values'] == 0


def test_revision_flags_do_not_inflate_canonical_or_infer_exposure():
    a = pd.DataFrame([{k:'x' for k in META} for _ in range(2)])
    a['canonical_annotation_id'] = ['a','b']
    a['context_key'] = ['C1|0|image|manual','C1|0|image|semi']
    a['raw_condition'] = ['manual','semi']
    a['assistance_exposure'] = ['none','observed_model']
    lineage = pd.DataFrame({'raw_annotation_version_id':['a1','a2','b1'], 'canonical_annotation_id':['a','a','b']})
    f = response_history_flags(a, lineage)
    assert len(f) == 2 and f.raw_version_count.tolist() == [2,1]
    assert f.has_revision.tolist() == [True,False]
    assert f.multiple_condition_observed.all() and (f.worker_image_condition_count == 2).all()
    assert f.assistance_exposure.tolist() == ['none','observed_model']
