import numpy as np
import pandas as pd
import pytest
import json

from tools.thesis_main.analysis.v1_integrated_analysis_20261017 import (
    summarize, peer_context, compose_team, paired_conditions,
    reliability_summary, attach_stability,
)


def records():
    return pd.DataFrame(dict(object_id=['a','b','c'],image_id=['i','i','j'],worker_id=['w','x','w'],
        building_id=['b']*3,condition=['manual']*3,rescore_target_id=['r','r','s'],
        reference_version=['v']*3,B8L2=[80.,60.,40.],D10=[81.,62.,43.],
        quality_usable=[True]*3,pool_vote_eligible=[True]*3,pool_analysis_eligible=[True]*3,
        source_active_time_seconds=[10.,None,30.],active_time_seconds=[10.,None,30.],
        target_matched_time_seconds=[None]*3))


def test_weighting_missingness_and_low_tail_do_not_fill_missing_time():
    r=summarize(records())
    assert r['B8L2_mean']==60 and r['B8L2_image_equal_mean']==55
    assert r['B8L2_q10']==44 and r['n_quality']==3 and r['n_quality_images']==2
    assert r['source_time_n']==2 and r['target_time_n']==0 and r['source_time_missing']==1
    bad=records();bad.loc[1,'D10']=np.nan
    with pytest.raises(AssertionError):summarize(bad)
    with pytest.raises(AssertionError):summarize(pd.concat([records(),records().iloc[:1]]))


def test_peer_baseline_excludes_self_and_keeps_singleton_unknown():
    out=peer_context(records(),'B8L2')
    assert out.peer_mean.tolist()[:2]==[60,80]
    assert pd.isna(out.peer_mean.iloc[2]) and pd.isna(out.peer_residual.iloc[2])
    assert out.peer_n.tolist()==[1,1,0]


def test_composition_requires_matching_building_outside_profiles_and_keeps_unsupported():
    fits=pd.DataFrame(dict(worker_id=['w','x','w'],fold=['target','target','other'],axis=['B8L2']*3,
        panel=['current']*3,effect=[5.,-2.,99.],supported=[True,False,True],label=['above_pool','below_pool','above_pool']))
    assert compose_team(['w','x','missing'],'target','B8L2',fits)==(1,0,2)


def test_manual_semi_match_requires_worker_image_and_exact_target():
    a=records().iloc[:1].copy();b=a.copy();b['object_id']='semi';b['condition']='semi';b['B8L2']=90
    pair=paired_conditions(pd.concat([a,b]))
    assert len(pair)==1 and pair.iloc[0].B8L2_final_semi_minus_manual==10
    b['rescore_target_id']='other'
    assert paired_conditions(pd.concat([a,b])).empty


def test_reliability_uses_explicit_error_opportunities_and_does_not_fill_unknown_correct():
    d=records();d['confirmed_person_error_exclusion']=[True,False,False]
    d['severe_assessed_under_explicit_rule']=[True,True,False]
    d['known_wrong_initialization_opportunity']=[True,False,True]
    d['explicit_error_remains']=[True,False,False];d['explicit_correction_success']=False
    d['targeted_audit_member']=[True,True,False]
    out=reliability_summary(d)
    w=out[out.worker_id.eq('w')].iloc[0]
    assert w.n_total==2 and w.n_known_error_opportunity==2 and w.n_explicit_unfixed==1
    assert w.n_repair_status_unknown==1 and w.known_unfixed_lower_bound_share==.5
    assert w.n_known_person_error==1 and w.n_severe_assessed==1


def test_same_k_join_preserves_attempts_and_both_endpoint_eligibility():
    s=pd.DataFrame(dict(pool_id=['p','p'],path_id=['a','b'],k=[3,3],R_union_normalized=[.2,.4],
        B8L2=[80.,None],D10=[81.,None],main_comparison_allowed=[True,False],
        complete_evaluable=[True,False],subset=['x','y']))
    pairs=pd.DataFrame(dict(pool_id=['p'],k=[3],path_a=['a'],path_b=['b'],floor_jaccard_difference=[.3]))
    out=attach_stability(s,pairs)
    assert len(out)==1 and not out.iloc[0].both_main_quality and out.iloc[0].R_pair_mean==pytest.approx(.3)
    with pytest.raises(pd.errors.MergeError):attach_stability(pd.concat([s,s.iloc[:1]]),pairs)


def test_reselection_separates_fixed_member_scale_from_changed_members_and_keeps_missing(tmp_path,monkeypatch):
    from tools.thesis_main.analysis import v1_integrated_analysis_20261017 as module
    monkeypatch.setattr(module,'ROOT',tmp_path)
    monkeypatch.setattr(module,'OUT',tmp_path/'analysis_output')
    p=tmp_path/'research/workers/worker_v1_composition_20261017';p.mkdir(parents=True)
    pd.DataFrame(dict(image_code=['ok','failed'],B8L2_selected_team=['a','c'],D10_reselected_team=['b','d'])).to_csv(p/'metric_selection_contrasts.csv',index=False)
    (p/'TEAM_REQUESTS.json').write_text(json.dumps(dict(paths=[])),encoding='utf-8')
    f=tmp_path/'research/fusion/wall_consensus_v1_process_20261017';f.mkdir(parents=True)
    (f/'worker_request_status.json').write_text(json.dumps(dict(rejected_paths=[dict(image='failed')])),encoding='utf-8')
    states=pd.DataFrame(dict(request_id=['a','b'],pool_id=['p','p'],subset=['w1','w2'],reference_id=['r','r'],
        reference_version=['v','v'],B8L2=[80.,79.],D10=[82.,81.],main_comparison_allowed=[True,True]))
    out=module.request_contrasts(states)['metric_reselection_contrasts']
    assert len(out)==2 and out.iloc[0].fixed_member_D10_minus_B8L2==2
    assert out.iloc[0].reselection_at_fixed_B8L2==-1 and out.iloc[0].reselection_at_fixed_D10==-1
    assert not out.iloc[1].both_published and pd.isna(out.iloc[1].reselection_at_fixed_D10)
    assert out.iloc[1].publication_status=='whole_pool_input_failed'
