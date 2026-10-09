import numpy as np
import pytest

from tools.thesis_main.analysis.difficulty_dino_20261009 import summarize_patches, fold_features, nested_predictions


def test_constant_patches_zero_dispersion_and_invalid_not_silently_repaired():
    arrays = {face: np.ones((3, 2, 2), np.float32) for face in ('front','right','back','left','up','down')}
    vector, dispersion = summarize_patches(arrays)
    assert np.linalg.norm(vector) == pytest.approx(1)
    assert dispersion == pytest.approx(0, abs=1e-6)
    with pytest.raises(ValueError, match='nonfinite'):
        summarize_patches(dict(arrays, front=np.full((3,2,2), np.nan)))
    with pytest.raises(ValueError, match='zero'):
        summarize_patches(dict(arrays, front=np.zeros((3,2,2))))


def test_neighbours_exclude_heldout_and_query_buildings():
    buildings = np.array(['a','a','b','c','d','e','heldout'])
    distances = np.ones((7,7))
    distances[:, 0:2] = 0
    distances[:, -1] = 0
    base = np.zeros((7,4))
    train = buildings != 'heldout'
    first = fold_features(base, distances, buildings, train, neighbours=3)
    assert first[0,3] == 1
    changed = distances.copy()
    changed[:, -1] = 100
    assert np.array_equal(first, fold_features(base, changed, buildings, train, neighbours=3))
    inner_train = train & (buildings != 'a')
    assert fold_features(base, distances, buildings, inner_train, neighbours=3)[2,3] == 1
    with pytest.raises(ValueError, match='insufficient'):
        fold_features(base, distances, buildings, buildings=='a', neighbours=3)


def test_outer_labels_never_change_own_predictions_or_weights():
    buildings = np.repeat(list('abcde'),5)
    rows = [dict(image=str(i),image_id=str(i),building=b,
                 subjective_label=('简单','中等','困难')[i%3]) for i,b in enumerate(buildings)]
    base = np.column_stack((np.arange(25),np.zeros((25,3))))
    distances = np.abs(np.arange(25)[:,None]-np.arange(25)[None,:])/25
    first = nested_predictions(rows,base,distances,(0,3))
    changed = [dict(r,subjective_label='困难') if r['building']=='a' else r for r in rows]
    second = nested_predictions(changed,base,distances,(0,3))
    a = [(p['weights'],p['calibrated_score']) for p in first if p['building']=='a']
    b = [(p['weights'],p['calibrated_score']) for p in second if p['building']=='a']
    assert a == b
