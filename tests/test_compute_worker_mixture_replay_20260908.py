import math
import numpy as np
import pytest
from tools.thesis_main.analysis.compute_worker_mixture_replay_20260908 import enumerate_combinations, evaluate_combination, summarize_methods, profile_group


def test_enumeration_uses_distinct_people_and_same_pool():
    rows = enumerate_combinations(['a','b'], ['c','d'], 2)
    assert len(rows) == 6
    assert sum(r[1]=='balanced_AB' for r in rows) == 4
    assert all(len(set(ids))==2 for ids,_ in rows)
    assert enumerate_combinations(['a'], [], 2)==[]
    with pytest.raises(ValueError): enumerate_combinations(['a'], ['a'], 2)


def test_profile_uses_training_outside_target_and_unknown_is_not_middle():
    p=dict(fold='target',training_buildings='["elsewhere"]',label='high',fit_status='usable')
    assert profile_group(p,'target')=='A'
    assert profile_group(p|{'label':'uncertain'},'target')=='unknown'
    assert profile_group(None,'target')=='unknown'
    with pytest.raises(ValueError):profile_group(p|{'training_buildings':'["target"]'},'target')
    with pytest.raises(ValueError):profile_group(p|{'fold':'full'},'target')


def test_real_response_validation_has_no_training_leakage():
    d=np.array([[0,20,0,20],[20,0,20,0],[0,20,0,20],[20,0,20,0]],float)
    r=evaluate_combination(d,[0,1],[2,3])
    assert r['distribution_tv']==0 and r['training_entropy']==pytest.approx(math.log(2))
    changed=d.copy();changed[2,:2]=changed[:2,2]=1
    q=evaluate_combination(changed,[0,1],[2,3])
    assert q['training_entropy']==r['training_entropy']
    assert q['validation_ambiguous_fraction']==.5 and math.isnan(q['distribution_tv'])
    with pytest.raises(ValueError):evaluate_combination(d,[0,1],[1,2])


def test_method_denominators_and_complete_pairing_do_not_zero_missing():
    rows=[dict(composition=c,pairwise_distance_mean=v,distribution_tv=t) for c,v,t in
          [('A_only',1.,.1),('balanced_AB',2.,float('nan')),('B_only',3.,.3)]]
    summary,paired=summarize_methods(rows,['pairwise_distance_mean','distribution_tv'])
    random=next(r for r in summary if r['method']=='random_AB_pool' and r['measure']=='distribution_tv')
    assert random['total_combinations']==3 and random['valid_combinations']==2
    assert random['mean']==pytest.approx(.2)
    tv=next(r for r in paired if r['measure']=='distribution_tv')
    assert not tv['paired_all_combinations_valid'] and not tv['paired_any_values']
    assert next(r for r in paired if r['measure']=='pairwise_distance_mean')['paired_all_combinations_valid']


def test_invalid_validation_and_nonunique_keep_schema_and_candidates():
    d=np.array([[0,1,10,1,1],[1,0,1,1,1],[10,1,0,1,1],[1,1,1,0,1],[1,1,1,1,0]],float)
    nonunique=evaluate_combination(d,[0,1,2],[3,4])
    assert nonunique['partition_status']=='non_unique'
    missing=evaluate_combination(d,[0,1],[2])
    unique=evaluate_combination(d,[0,1],[3,4])
    assert set(missing)==set(unique)==set(nonunique)
    assert missing['partition_status']=='validation_lt2' and math.isnan(missing['pairwise_distance_mean'])
    rows=[missing|dict(composition='A_only')]
    summary,_=summarize_methods(rows)
    assert summary[0]['total_combinations']==1 and summary[0]['valid_combinations']==0


def test_truncated_partition_is_retained_without_fabricated_tv(monkeypatch):
    import tools.thesis_main.analysis.compute_worker_mixture_replay_20260908 as module
    monkeypatch.setattr(module,'partition',lambda d,t:dict(status='truncated',candidate_partition_count=256,enumeration_truncated=True,clusters=[]))
    r=evaluate_combination(np.zeros((4,4)),[0,1],[2,3])
    assert r['truncated_indicator']==1 and r['pairwise_distance_mean']==0
    assert math.isnan(r['distribution_tv']) and r['validation_cluster_support_json']==''
