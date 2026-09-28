import gzip
import json
import numpy as np

from tools.thesis_main.analysis.run_structural_consensus_20260926 import (
    split_workers, reference_agreement, budgeted_candidates, save,
)


def test_holdout_is_reproducible_worker_disjoint_and_not_future_fitted():
    rows = [dict(worker=f'W{i:02}') for i in range(12)]
    splits = split_workers(rows)
    assert splits == split_workers(list(reversed(rows)))
    assert len(splits) == 4
    for split in splits:
        assert len(split['train']) == 9 and len(split['test']) == 3
        assert not set(split['train']) & set(split['test'])
        assert set(split['train'] + split['test']) == {r['worker'] for r in rows}
    assert split_workers(rows[:2]) == []


def test_reference_is_evaluation_only_and_invalid_ring_stays_unavailable(tmp_path):
    square = np.array([[-2, -2], [2, -2], [2, 2], [-2, 2]])
    assert reference_agreement(square, square)['iou'] == 1
    assert reference_agreement(square, square * 2)['iou'] == .25
    bad = reference_agreement(square[[0, 2, 1, 3]], square)
    assert bad['status'] == 'unavailable' and bad['iou'] is None
    target=tmp_path/'case.json.gz'
    save(target,bad)
    with gzip.open(target,'rt',encoding='utf8') as stream:
        assert json.load(stream)==bad


def test_candidate_cap_uses_training_support_and_deduplicates_ring_equivalence():
    square=np.array([[-2,-2],[2,-2],[2,2],[-2,2]])
    train=[dict(worker='w',floor=square.tolist())]
    candidates=[dict(floor=(square*2).tolist()),dict(floor=square.tolist()),
                dict(floor=np.roll(square[::-1],1,axis=0).tolist())]
    selected=budgeted_candidates(candidates,train,limit=2)
    assert len(selected)==2
    assert np.array_equal(selected[0]['floor'],square)
