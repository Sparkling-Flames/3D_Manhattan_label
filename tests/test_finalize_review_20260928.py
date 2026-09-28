from tools.thesis_main.analysis.finalize_review_20260928 import choose_decision, repair_authorized, scene_dimensions, recover_scene, coverage_decision
import csv
import json
from pathlib import Path


def test_historical_scene_recovery_respects_explicit_second_review():
    iid='2t7WUuJeko7_53937db036374126830e0f1203b04ead'
    event=dict(event_id='user:new_95_3649_7457_W030',comment='这图是门洞交界处,不好标')
    assert recover_scene(iid, {}, [event])[0]=='doorway_difficult'
    assert recover_scene(iid, {'category':'oos'}, [event])==('oos', [])
    assert recover_scene('unrecorded', {}, [])==('unconfirmed', [])


def test_coverage_does_not_create_review_requests():
    root=Path(__file__).resolve().parents[1]/'analysis_results/review_final_20260928'
    csv.field_size_limit(32*1024*1024)
    with (root/'逐图审核覆盖.csv').open(encoding='utf-8-sig',newline='') as f:
        rows=list(csv.DictReader(f))
    assert len(rows)==259
    assert sum(r['coverage_group']=='individual_review_only' for r in rows)==38
    assert sum(r['coverage_group']=='not_in_current_review_files' for r in rows)==0
    assert all(r['needs_reclassification']=='false' for r in rows)
    recovered=[r for r in rows if r['image_code']=='2t7WUuJeko7-07'][0]
    assert recovered['original_scene_category']=='unconfirmed'
    assert recovered['resolved_scene_category']=='doorway_difficult'


def test_coverage_scene_is_not_individual_verdict():
    record=dict(status='resolved',oos='in_scope',doorway='none',tags=[],comment='范围不同',view_context={})
    decision, traits, evidence=coverage_decision('wc2JMjhGNzB_e6693f97b36545f7a76e03c3fe32ba8c',record)
    assert traits['tags']==['scope'] and record['tags']==[]
    assert decision['category']=='ordinary' and 'verdict' not in decision
    assert evidence['user_clarification']
    pending={**record,'oos':'pending','doorway':''}
    assert coverage_decision('other',pending)[0]['category']=='unconfirmed'


def test_coverage_merge_and_worker_denominators():
    root=Path(__file__).resolve().parents[1]/'analysis_results/review_final_20260928'
    with (root/'全量复核.csv').open(encoding='utf-8-sig',newline='') as f: rows=list(csv.DictReader(f))
    wc=[r for r in rows if r['image_code']=='wc2JMjhGNzB-61']
    assert wc and all(json.loads(r['image_traits'])['tags']==['scope'] for r in wc)
    assert all(r['scope_difference_image']=='true' and r['gt_substantive_error']=='false' for r in wc)
    held=[r for r in rows if r['image_code']=='pRbA3pwrgk9-16']
    assert held and all(r['worker_quality_gate']=='hold_all_analysis' and r['cleaning_disposition']!='excluded_by_review' and r['scene_oos_status']=='pending' for r in held)
    with (root/'标注者排除统计.csv').open(encoding='utf-8-sig',newline='') as f: workers=list(csv.DictReader(f))
    assert sum(int(r['total_responses']) for r in workers)==3152
    assert sum(int(r['explicitly_excluded']) for r in workers)==85
    assert sum(int(r['historical_not_accepted']) for r in workers)==133
    for r in workers:
        assert int(r['explicitly_excluded'])==sum(int(r[k]) for k in ['normal_excluded','oos_difficult_doorway_excluded','other_or_unclassified_excluded'])
        assert int(r['explicitly_excluded'])==sum(int(r[k]) for k in ['excluded_manual','excluded_semi','excluded_condition_oos'])
        assert int(r['total_responses'])==sum(int(r[k]) for k in ['normal_total','oos_difficult_doorway_total','other_or_unclassified_total'])
    assert next(r for r in workers if r['worker_id']=='W037')['explicitly_excluded']=='29'
    with (root/'同房图片复核对照.csv').open(encoding='utf-8-sig',newline='') as f: rooms=list(csv.DictReader(f))
    unknown=[r for r in rooms if not r['room_id']]
    assert len({r['comparison_group'] for r in unknown})==len(unknown)
    original=json.loads((root/'evidence/coverage.json').read_text(encoding='utf-8'))
    assert original['decisions']['wc2JMjhGNzB_e6693f97b36545f7a76e03c3fe32ba8c']['tags']==[]


def test_latest_review_and_repair_intent():
    old = {'verdict': 'invalid', 'comment': '旧意见'}
    second = {'verdict': 'usable', 'comment': '二审保留'}
    latest = {'verdict': 'usable', 'comment': '去掉一对会更好', 'status': 'resolved'}
    assert choose_decision(latest, second, old) == (latest, 'latest')
    assert choose_decision(None, second, old) == (second, 'second')
    assert not repair_authorized(latest)
    assert repair_authorized({'verdict': 'repair_needed', 'comment': '补点'})
    assert latest['comment'] == '去掉一对会更好'


def test_generated_full_review():
    root = Path(__file__).resolve().parents[1] / 'analysis_results/review_final_20260928'
    csv.field_size_limit(32 * 1024 * 1024)
    with (root / '全量复核.csv').open(encoding='utf-8-sig', newline='') as f:
        records = list(csv.DictReader(f))
    rows = {r['canonical_annotation_id']: r for r in records}
    assert len(rows) == len(records) == 3152
    assert all(r['raw_verified'] == 'true' for r in records)
    assert sum(r['accepted_before_review'] == 'false' for r in records) == 133
    assert rows['f8c20f06811c7321e708']['effective_point_count'] == '14'
    assert rows['new_95_3663_7443_W028']['effective_point_count'] == '14'
    assert rows['1623fbedf957f0be9421']['effective_point_count'] == '12'
    assert 'p14' not in json.loads(rows['2559d23544f7b937']['effective_point_labels'])
    assert rows['new_94_3628_7046_W037']['needs_user_review'] == 'false'
    assert rows['new_94_3628_7046_W037']['raw_review_status'] == 'pending'
    assert sum(r['repair_status'] == 'applied' for r in records) == 9
    assert all(r['worker_quality_gate'] != 'candidate_pending_geometry' for r in records
               if r['scene_category'] in {'oos','oos_stable_nonorthogonal','doorway_difficult'})
    assert all(r['worker_quality_gate'] == 'hold_all_analysis' for r in records if r['image_code'] == 'jtcxE69GiFV-11')
    assert not any(r['latest_decision_source'] == 'historical_user' and r['verdict'] == 'invalid' for r in records)


def test_overlapping_scene_dimensions_and_continuation():
    assert scene_dimensions('doorway_difficult', True)['oos_status'] == 'confirmed'
    assert scene_dimensions('doorway_difficult', True)['doorway_status'] == 'difficult'
    assert scene_dimensions('ordinary', False)['oos_status'] == 'not_recorded'
    root = Path(__file__).resolve().parents[1] / 'analysis_results/review_final_20260928'
    csv.field_size_limit(32 * 1024 * 1024)
    with (root / '全量复核.csv').open(encoding='utf-8-sig', newline='') as f:
        rows = list(csv.DictReader(f))
    assert all(r['scene_oos_status']=='confirmed' and r['scene_doorway_status']=='difficult'
               for r in rows if r['image_code'] in {'pRbA3pwrgk9-01','pRbA3pwrgk9-11'})
    targets={'4a1158da9bd83ef9','6aed1eb1185c1318','6d192755ca096a2c','032cd152706166629e82'}
    assert all(r['verdict']=='invalid' and r['pending_history_verification']=='false'
               for r in rows if r['canonical_annotation_id'] in targets)
    assert all(r['consensus_group'] in {'hold_main_analysis','excluded'} for r in rows if r['image_code']=='uNb9QFRL6hY-32')
    assert all(r['scope_policy']=='inner_space_only' for r in rows if r['image_code']=='uNb9QFRL6hY-51')
    assert all(r['needs_user_review']=='false' for r in rows if r['image_code']=='S9hNv5qa7GM-04')
