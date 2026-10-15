import numpy as np
import pandas as pd
import pytest

from tools.thesis_main.analysis.worker_wq_integration_20261015 import (
    geometry_equal, replacement_edges, fit_axis, classify, reference_cells, summarize_entrants,
)


def test_reference_geometry_not_id_controls_equivalence():
    a = {'bottom3d': [[0, -1, 0], [1, -1, 0], [1, -1, 1]],
         'top3d': [[0, 1, 0], [1, 1, 0], [1, 1, 1]]}
    rolled = {k: v[1:] + v[:1] for k, v in a.items()}
    assert geometry_equal(a, rolled)
    changed = {**a, 'top3d': [[0, 2, 0], [1, 1, 0], [1, 1, 1]]}
    assert not geometry_equal(a, changed)
    cells = reference_cells([('im', 'manual', 'id1', a), ('im', 'manual', 'id2', rolled),
                             ('im', 'manual', 'id1', changed), ('im', 'semi', 'id1', a)])
    assert cells[0] == cells[1] and len(set(cells)) == 3


def test_only_real_unique_single_replacements():
    sets = [('a', 'b', 'c'), ('a', 'b', 'd'), ('a', 'd', 'e')]
    edges = replacement_edges(sets)
    assert len(edges) == 2
    assert edges[0] == (0, 1, ('a', 'b'), 'c', 'd')
    with pytest.raises(ValueError, match='duplicate'):
        replacement_edges([('a', 'a', 'b')])
    with pytest.raises(ValueError, match='duplicate'):
        replacement_edges([sets[0], sets[0]])


def test_quality_profiles_exclude_entire_building_and_no_forced_labels():
    d = pd.DataFrame([dict(worker_id=w, building_id=str(b), context_key=f'{b}:{c}',
        WQ=20*b+3*c+v) for b in range(4) for c in range(3)
        for w, v in [('a', -2.), ('b', 0.), ('c', 2.)]])
    p = fit_axis(d, 'WQ', '3').set_index('worker_id')
    d.loc[d.building_id.eq('3'), 'WQ'] = 99999
    pd.testing.assert_frame_equal(p, fit_axis(d, 'WQ', '3').set_index('worker_id'))
    assert np.allclose(p.effect, [-2, 0, 2])
    assert classify(0, True) == 'unclassified'
    assert classify(2, False) == 'unclassified'


def test_fixed_base_association_preserves_missing_and_constant_outcomes():
    result=summarize_entrants([-2,-1,1,2],[0,0,2,2])
    assert result['class_gap']==2 and result['class_explained_fraction']==1
    assert summarize_entrants([-2,-1,1,2],[3,3,3,3])['class_explained_fraction'] is None
    assert summarize_entrants([-2,-1,1,2],[None,0,2,None])['evaluable_entrants']==2
