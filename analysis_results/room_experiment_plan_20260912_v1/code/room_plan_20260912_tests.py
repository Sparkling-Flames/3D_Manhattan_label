from pathlib import Path
import json,os
import pandas as pd
OUT=Path(os.environ['ROOM_PLAN_RESULTS'])

def test_raw_identity():
    q=json.loads((OUT/'QA.json').read_text());assert q['raw_source_files']==18 and q['raw_identity_and_coordinate_checks']==2501 and q['registry_core_keys_reproduced']
    d=pd.read_csv(OUT/'raw_coordinate_and_identity_checks.csv');assert len(d)==2501 and d.canonical_annotation_id.is_unique and d.raw_identity_and_coordinates_match.all()

def test_complete_anchored_set():
    c=pd.read_csv(OUT/'low_ambiguity_69_support.csv');p=pd.read_csv(OUT/'priority_source_target_pairs.csv')
    assert len(c)==69 and (c.n_manual_ge19>=2).sum()==0
    assert set(c.loc[c.n_manual_ge19>=1,'candidate_id'])==set(p.group_code) and len(p)==9

def test_assisted_exposure_is_not_unseen():
    d=pd.read_csv(OUT/'image_inventory_648_with_exposure.csv');r=d[(d.building=='wc2JMjhGNzB')&(d.number==40)].iloc[0]
    assert r.n_people_manual_included==0 and r.n_current20_any_seen==20 and r.max_current20_without_reusing_seen_nonmanual==0

def test_support_gaps_not_hidden():
    d=pd.read_csv(OUT/'priority_source_target_pairs.csv').set_index('group_code')
    assert d.loc['G036','target_current20_clean_capacity']==17 and not d.loc['G036','current20_topup_possible_from_snapshot']
    assert d.loc['G057','source_manual_N']==19 and d.loc['G202','review_state']=='explicit_discussion'

def test_endpoint_and_tail():
    d=pd.read_csv(OUT/'number_vs_validation_horizon.csv');a=d[(d.total_distinct_workers==20)&(d.required_tail_workers==5)].iloc[0]
    assert a.max_candidate_k==15 and not a.can_check_k20_with_tail
    a=d[(d.total_distinct_workers==25)&(d.required_tail_workers==5)].iloc[0];assert a.max_candidate_k==20 and a.can_check_k20_with_tail

def test_budget():
    d=pd.read_csv(OUT/'cost_scenarios.csv');assert d.not_power_justified_sample_size.all()
    a=d[(d.plan=='C_main9_plus_boundary')&(d.assumed_minutes_per_action==5)].iloc[0]
    assert a.total_geometry_actions==380 and a.per_initial_worker_actions==19 and abs(a.annotation_hours-380*5/60)<1e-8
    assert d[d.plan=='C_plus_k20_tail4'].total_geometry_actions.eq(430).all()

def test_duration_subcohort():
    d=pd.read_csv(OUT/'historical_time_context.csv');assert (d.n_duration_records>0).all()
    assert d[(d.cohort=='current20')&(d.condition=='included_unassisted')].n_duration_records.iloc[0]==1390

def test_calibration_is_provisional():
    d=pd.read_csv(OUT/'calibration_review_candidates.csv');assert len(d)==6 and set(d.approval_status)=={'review_candidate_not_frozen_gold'}
    p=pd.read_csv(OUT/'priority_source_target_pairs.csv');assert not set(d.image_id)&set(p.target_image_id)

def test_small_pair_and_binomial():
    d=pd.read_csv(OUT/'existing_same_room_same_worker_count_comparison.csv');assert len(d)==6
    r=d[d.group_code=='G036'].iloc[0];assert r.n_common_workers==6 and r.common_worker_count_disagreement_a==0 and abs(r.common_worker_count_disagreement_b-1/3)<1e-10
    d=pd.read_csv(OUT/'rare_mode_binomial_sensitivity.csv');r=d[(d.N==20)&(d.assumed_independent_mode_probability==.1)].iloc[0]
    assert abs(r.probability_at_least_two-(1-.9**20-20*.1*.9**19))<1e-10
