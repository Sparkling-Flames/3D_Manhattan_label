import copy

from tools.thesis_main.analysis import analyze_new_manual_20260921 as old
from tools.thesis_main.analysis import reviewed_manual_20260921 as reviewed


def test_reviewed_intake_preserves_raw_points_and_resolves_user_decisions():
    history = old.pipeline.rows_at(old.HIST / 'responses.jsonl.gz')
    registry = old.read(reviewed.REGISTRY)
    new, _ = old.intake(history, registry, reviewed.SOURCES)
    original = copy.deepcopy(new)
    rows, receipts, records, eligibility = reviewed.prepare(history, new, registry)
    by = {r['provenance']['annotation']: r for r in rows[len(history):]}
    assert new == original and rows[:len(history)] == history
    assert all(by[r['provenance']['annotation']]['raw_points_1024x512'] == r['raw_points_1024x512'] for r in original)
    for target, donor, point in [(6925, 7015, 10), (7273, 6987, 8)]:
        r = by[target]
        assert r['effective_point_count'] == r['raw_point_count'] + 1
        assert r['effective_points_1024x512'][-1] == by[donor]['raw_points_1024x512'][point - 1]
        assert r['imputed_point'] and r['active_time_seconds'] is None
        assert records[r['canonical_annotation_id']]['links'] is not None
    assert not by[7271]['calculation_included'] and by[7272]['calculation_included']
    parents = [r for r in receipts if r['parent_annotation']]
    assert len(parents) == 48 and all(r['strict_include'] for r in parents)
    assert not any('independence_pending' in f for r in receipts for f in r['flags'])
    assert all(records[by[a]['canonical_annotation_id']]['links'] is not None for a in [7182, 6877, 7433, 7285, 7086])
    assert records[by[7036]['canonical_annotation_id']]['links'] is None
    assert by[7036]['effective_points_1024x512'] == by[7036]['raw_points_1024x512']
    assert not by[7137]['calculation_included']
    assert 7111 not in by
    for aid in [7500, 7501, 7502]:
        assert by[aid]['calculation_included']
        assert by[aid]['provenance']['assignment'] == 'required'
        assert by[aid]['provenance']['submission_context'] == '用户确认W006补交原分配任务'
    assert by[7502]['provenance']['supersedes_annotation'] == 7111
    keys = [(r['image_id'], r['worker_id']) for r in rows[len(history):] if r['calculation_included']]
    assert len(keys) == len(set(keys))
    assert len(keys) == 636
    bound = [r['row'] for r in records.values() if r['links'] is not None]
    assert sum(r['canonical_annotation_id'].startswith('new_') for r in bound) == 635
    prediction = [r for r in bound if r['raw_condition'] in ['manual', 'oos'] and not r['imputed_point']]
    assert reviewed.counts(prediction) == dict(responses=2444, images=240, workers=25, buildings=22)
