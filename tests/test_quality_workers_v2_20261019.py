from tools.thesis_main.analysis.quality_workers_v2_20261019 import resolve_binding, quality_gate


def test_sole_identity_does_not_release_quality_hold():
    b, audit = resolve_binding(dict(chosen_target_id='', allowed_target_ids=['a'], current_target_id='a'), 'old')
    assert b['chosen_target_id']=='a' and audit=='sole_reference_identity_only'
    assert quality_gate(['legacy:original_holdout'], True)==['legacy:original_holdout']


def test_multiple_and_failed_measurement_stay_missing():
    b, audit = resolve_binding(dict(chosen_target_id='', allowed_target_ids=['a','b']), 'v2:new:1')
    assert not b['chosen_target_id'] and audit=='needs_geometry_or_target_review'
    assert quality_gate([], False)==['score_unavailable']


def test_exploratory_categories_require_support():
    from tools.thesis_main.analysis.personnel_v2_20261019 import qclass,tclass
    assert qclass(.9,5,3)=='证据不足'
    assert qclass(2/3,6,3)=='高'
    assert tclass(59,6)=='快' and tclass(60,6)=='中' and tclass(180,6)=='慢'


def test_reported_scope_and_semi_opportunities():
    from tools.thesis_main.analysis.personnel_v2_20261019 import scope_response,error_opportunity
    assert scope_response('out_of_scope')=='out' and scope_response(['in_scope'])=='in'
    assert scope_response(None) is None
    assert error_opportunity(dict(initialization_kind='original_hohonet_ep300',error_specific_outcome='unknown_after_edit'))
    assert not error_opportunity(dict(error_specific_outcome='not_an_error_opportunity'))


def test_published_v2_keeps_old_scores_and_holds():
    from tools.thesis_main.analysis.quality_workers_v2_20261019 import OUT,INPUT,BASE,read
    from tools.thesis_main.data_prep.consolidate_research_input import load_current_bundle
    from tools.thesis_main.analysis.current_annotation_context_20261017 import load_scored_context
    old=load_scored_context(load_current_bundle(BASE))
    current=load_scored_context(load_current_bundle(INPUT/'manifest.json'))
    rows={r['object_id']:r for r in current['quality_records']}
    assert len(rows)==10439 and sum(r['quality_usable'] for r in rows.values())==7302
    for r in old['quality_records']:
        if r['quality_usable']:
            assert rows[r['object_id']]['quality_usable']
            for m in ('B8L2','D10'):assert abs(rows[r['object_id']][m]-r[m])<1e-9
    assert all(not r['quality_usable'] for r in rows.values() if r['image_quality_gate'].startswith('hold_'))
    audit=read(OUT/'binding_audit.json')
    assert len(audit)==34 and sum(r['resolution']=='needs_geometry_or_target_review' for r in audit)==7
    adopted=[r['adopted_review'] for r in audit if r.get('adopted_review')]
    assert len(adopted)==7
    assert sum(r['method']=='manual_bev_color' for r in adopted)==5
    for r in adopted:
        q=rows[r['object_id']]
        assert q['rescore_target_id']==r['chosen_target_id']
        if r['display_number'] in (1,2,3,6):assert q['B8L2'] is None
        if r['method']=='user_authorized_existing_floor_fallback':
            metrics=r['candidate_floor_metrics']
            assert r['chosen_target_id']==min(metrics,key=lambda k:(-metrics[k]['I'],metrics[k]['boundary_mean_over_sqrt_ref_area'],k))
    import pandas as pd
    from tools.thesis_main.analysis.personnel_v2_20261019 import OUT as WORKERS
    reliability=pd.read_csv(WORKERS/'reliability.csv')
    assert reliability.semi_error_opportunities.sum()==284
    assert reliability.semi_known_error_unchanged.sum()==45
    assert reliability.scope_judged_n.sum()==89
    assert (reliability.scope_correct_n<=reliability.scope_judged_n).all()


def test_scope_does_not_use_image_oos_as_person_gold():
    from tools.thesis_main.analysis.personnel_v2_20261019 import audited_scope_counts
    rows=[dict(cleaning_disposition='retained',image_oos_status='confirmed',
               scope_evidence=dict(response='out_of_scope',judgement_opportunity=False,correct=None)),
          dict(cleaning_disposition='retained',scope_evidence=dict(response='in_scope',
               judgement_opportunity=True,compatible_gold='in_scope',correct=True))]
    result=audited_scope_counts(rows)
    assert result['scope_judged_n']==1 and result['scope_correct_n']==1
    assert result['scope_response_n']==2 and result['scope_out_n']==1
