"""Follow-up audit tests. They do not freeze a final convergence criterion."""
import json
import numpy as np,pandas as pd,pytest
from tools.thesis_main.analysis.image_portrait.history_difficulty_v1_core import OUT,B,read,GRADES
from tools.thesis_main.analysis.image_portrait.history_difficulty_v1_finalize import descriptive_effect


def test_none_controls_are_truly_unadjusted():
    n=np.arange(4,24);x=n+np.sin(n);y=2*x+3*np.log1p(n)
    d=pd.DataFrame({'x':x,'y':y,'n_valid':n,'building':['a']*10+['b']*10,'scene_category':['x']*20})
    a=descriptive_effect(d,'x','y','none');b=descriptive_effect(d,'x','y','n')
    assert a['slope']==pytest.approx(np.polyfit(x,y,1)[0])
    assert b['slope']==pytest.approx(2,abs=1e-8)
    assert abs(a['slope']-b['slope'])>.1


def test_person_training_keeps_conditions_separate():
    p=OUT/'E_conditioned/outside_building_person_scores.csv'
    if not p.exists():pytest.skip('conditioned stage not executed')
    d=pd.read_csv(p);assert (d.condition==d.source_condition).all()
    assert set(d.condition)=={'manual','semi'}


def test_future_workers_are_not_prefix_workers():
    p=OUT/'extra/singleton_real_future_support.csv.gz'
    if not p.exists():pytest.skip('singleton stage not executed')
    for ch in pd.read_csv(p,chunksize=10000,keep_default_na=False):
        for r in ch.itertuples():
            seen=set(r.prefix_worker_ids.split(';'));future=set(r.future_compatible_worker_ids.split(';'))-{''}
            assert not seen&future
            assert r.singleton_worker in seen
            assert r.n_future==r.n_total-r.k


def test_expert_empty_note_not_nonempty_comment():
    p=OUT/'expert/verified_nonempty_comments.csv'
    if not p.exists():pytest.skip('comment audit not executed')
    a=pd.read_csv(p,keep_default_na=False);j=read(OUT/'expert/COMMENT_COUNT_CORRECTION.json')
    assert j['actual_nonempty_image_comments']==a.actual_image_comment.str.len().gt(0).sum()
    assert j['actual_nonempty_image_comments']<106


def test_reconstructed_building_folds_match_fixed_membership():
    p=OUT/'inputs/historical_ids.json'
    if not p.exists():pytest.skip('inputs missing')
    ids=set(read(p));folds=[f for f in read(B/'evaluation/folds.jsonl.gz') if f['design']=='leave_building']
    for f in folds:
        test=set(f['test'])&ids;train=set(f['train'])&ids
        assert not {i.split('_')[0] for i in test}&{i.split('_')[0] for i in train}
        assert train|test==ids


def test_no_prediction_feature_uses_actual_target_n():
    p=OUT/'prediction/execution.json'
    if not p.exists():pytest.skip('prediction not executed')
    candidates=read(p)['completed']
    assert not any(x in candidates for x in ['n_valid','n_observed','singleton_mass','quality','expert_tag','difficulty'])


def test_repeated_modes_have_distinct_actual_people():
    p=OUT/'targets/mode_memberships_reused.csv.gz'
    if not p.exists():pytest.skip('memberships missing')
    a=pd.read_csv(p)
    assert not a.duplicated(['image_id','condition','cut','worker_id']).any()


def test_tier_expansion_counts_unique_images():
    p=OUT/'targets/primary_per_image.csv'
    if not p.exists():pytest.skip('targets missing')
    a=pd.read_csv(p);e=pd.read_csv(OUT/'expert/independent_tags106.csv');c=read(OUT/'targets/coverage.json')
    assigned=set(a.loc[a.grade.isin(GRADES),'image_id'])
    assert len(assigned-set(e.image_id))==c['new_primary_assigned_images']
    assert len(set(a.image_id)-set(e.image_id))==c['historical_outside_expert']
