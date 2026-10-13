from copy import deepcopy

from tools.thesis_main.analysis.quality_manual_expansion_20261013 import evaluate_geometry, engine


def test_self_geometry_preserved_and_complete():
    g = dict(bottom3d=[[-1,-1,-1],[1,-1,-1],[1,-1,1],[-1,-1,1]],
             top3d=[[-1,1,-1],[1,1,-1],[1,1,1],[-1,1,1]])
    before = deepcopy(g)
    out = evaluate_geometry(g,g,engine())
    assert out['status']=='complete'
    assert all(abs(s['score']-100)<1e-8 for s in out['candidate_components'].values())
    assert abs(out['metrics']['iou_3d_corner_mean']-1)<1e-8
    assert g==before


def test_missing_top_is_not_repaired_or_scored_as_complete():
    g = dict(bottom3d=[[-1,-1,-1],[1,-1,-1],[1,-1,1],[-1,-1,1]], top3d=[])
    out = evaluate_geometry(g,g,engine())
    assert out['status']=='unavailable'
    assert out['candidate_components'] is None and out['reason_codes']
