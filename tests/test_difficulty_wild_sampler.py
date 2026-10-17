import json
import numpy as np
import pytest

from tools.thesis_main.analysis import difficulty_wild_sampler as w
from tools.thesis_main.analysis import simulate_annotators as base


def polygon(n=8):
    return np.array([p for x in np.arange(n) * 1024 / n + 20 for p in ((x, 140), (x, 380))])


def severity():
    return dict(delta=[[[4, 6], [4, -6]], [[-3, 5], [-3, -5]]],
                cap=[[10, 12], [10, 12]], deletion_counts=[1, 2], missing_frequency=.5)


@pytest.mark.parametrize('difficulty,bounds', w.WILD_BUDGET.items())
def test_budget(difficulty, bounds):
    values = [w.wild_count(difficulty, s) for s in range(200)]
    assert min(values) == bounds[0] and max(values) == bounds[1]
    assert w.wild_count(difficulty, 1, 0) == 0
    assert w.wild_count(difficulty, 1, 1) <= 1
    assert values == [w.wild_count(difficulty, s) for s in range(200)]


def test_invalid_budget():
    with pytest.raises(ValueError): w.wild_count('unknown', 1)
    with pytest.raises(ValueError): w.wild_count('简单', 1, -1)


def test_counts_distinct_manual_inventory():
    rows = [dict(image_id='a', worker_id='1', condition='manual')] * 3
    rows += [dict(image_id='a', worker_id='2', condition='semi')]
    rows += [dict(image_id='a', worker_id='3', condition='manual', independent_vote_eligible=False)]
    assert w.manual_counts(rows) == {'a': 2}


def test_continuity_wraparound():
    wrapped = False
    for seed in range(30):
        points, keep = w.continuous_subset(polygon(), np.random.default_rng(seed), 5)
        assert all((b - a) % 8 == 1 for a, b in zip(keep, keep[1:]))
        assert np.array_equal(points, polygon().reshape(-1, 2, 2)[keep].reshape(-1, 2))
        assert base.geometry_status(points) == w.VALID
        wrapped |= any(b < a for a, b in zip(keep, keep[1:]))
    assert wrapped


@pytest.mark.parametrize('types', [[t] for t in w.ERROR_TYPES] + [list(w.ERROR_TYPES)])
def test_edits(types):
    for seed in range(20):
        out, info = w.wild_edit(polygon(), polygon(), np.random.default_rng(seed), severity(), types)
        replay, again = w.wild_edit(polygon(), polygon(), np.random.default_rng(seed), severity(), types)
        assert np.array_equal(out, replay) and info == again
        assert base.geometry_status(out) == w.VALID
        assert not np.array_equal(out, polygon())
        assert set(info['wild_error_types']) == set(types)
        if 'scope_restricted' in types:
            assert all((b-a) % 8 == 1 for a,b in zip(info['kept_pair_indices'], info['kept_pair_indices'][1:]))


def test_no_model_copy_on_no_evidence():
    s = severity(); s['delta'] = np.zeros((2,2,2)).tolist()
    with pytest.raises(ValueError, match='exhausted'):
        w.wild_edit(polygon(), polygon(), np.random.default_rng(2), s, ['partial_corner'])
    with pytest.raises(ValueError): w.calibrate([])
    with pytest.raises(ValueError): w.continuous_subset(polygon(3), np.random.default_rng(1))


def test_loader_rejects_duplicates_and_unknown(tmp_path):
    path = tmp_path / 'd.csv'
    header = 'image_id,difficulty_class,difficulty_version,gt_error_excluded,reference_full_available,difficulty_analysis_eligible\n'
    row = 'a,简单,test_v6,False,True,True\n'
    path.write_text(header + row, encoding='utf-8-sig')
    assert w.load_difficulty(path)['a']['gt_error_excluded'] is False
    path.write_text(header + row + row)
    with pytest.raises(ValueError): w.load_difficulty(path)
    path.write_text(header + row.replace('简单', 'unknown'))
    with pytest.raises(ValueError): w.load_difficulty(path)


def test_export_independent_workers(tmp_path):
    from tools.thesis_main.analysis.export_synthetic_label_studio import export_samples
    meta = dict(difficulty='简单', difficulty_version='v6', difficulty_source='fixture', wild=False,
                wild_error_types=[], wild_budget_k=0, need=35, real_manual_n=0,
                gt_error_excluded=False, pending_review=False, scope_reference_status='full')
    rows = [dict(meta, simulation_id=str(i), source_worker_profile_id='1', condition='manual',
                 synthetic=True, image_id='a', points=polygon().tolist(), worker_scope_response='in_scope',
                 lead_time_seconds=10., export_worker_id=f'S_MANUAL_{i:06d}') for i in range(35)]
    exported, summary = export_samples(rows, {'a': {'image_url': 'fixture.png'}}, tmp_path)
    assert len(exported) == 35 and summary['rejected'] == 0
    annotations = json.loads((tmp_path / 'label_studio_synthetic.json').read_text())[0]['annotations']
    assert len({a['completed_by'] for a in annotations}) == 35
    assert {a['source_worker_profile_id'] for a in annotations} == {'1'}
    rows[1]['export_worker_id'] = rows[0]['export_worker_id']
    with pytest.raises(ValueError, match='duplicate_synthetic_worker'):
        export_samples(rows, {'a': {'image_url': 'fixture.png'}}, tmp_path)
