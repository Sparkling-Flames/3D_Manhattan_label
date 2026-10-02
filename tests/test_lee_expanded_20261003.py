import pytest

from tools.thesis_main.analysis.lee_expanded_20261003 import select_groups, summarize


def test_selection_keeps_failed_full_pool_and_unknown_difficulty():
    base = dict(condition='manual', consensus_gate='main_candidate',
                reference_quality_compatible=True, curve_ready=True,
                original_bev_ok=True, candidate_n=24)
    groups = [dict(base, image='unknown', difficulty='未记录'),
              dict(base, image='failed', curve_ready=False, candidate_bev_failed_n=1),
              dict(base, image='semi', condition='semi'),
              dict(base, image='single', candidate_n=1)]
    ledger = {r['image']: r for r in select_groups(groups)}
    assert ledger['unknown']['expansion_status'] == 'selected'
    assert ledger['failed']['expansion_status'] == 'whole_pool_unavailable'
    assert ledger['failed']['candidate_n'] == 24
    assert ledger['semi']['expansion_status'] == 'outside_manual_quality_panel'
    assert ledger['single']['expansion_status'] == 'single_person_only'


def test_fixed_cohorts_do_not_shrink_with_k_or_treat_unknown_as_easy():
    meta = {'short': dict(n=2, difficulty='简单', building='a'),
            'long': dict(n=4, difficulty='未记录', building='b')}
    rows = []
    for image, m in meta.items():
        for method in ('mv50', 'mv_strict'):
            for k in range(1, m['n']+1):
                rows.append(dict(image=image, n=m['n'], k=k, method=method,
                    version='original', iou_mean=(.8 if image=='short' else .2)+.01*(k-1),
                    mc_error_bound=0 if k==1 else .02,
                    expected_intersection_h2=1, expected_omission_h2=1, expected_extension_h2=.5))
    enriched, grouped = summarize(rows, meta, thresholds=(2, 4))
    fixed = [r for r in grouped if r['panel_max_k']==2 and r['cohort']=='全部' and r['method']=='mv50']
    assert [r['image_n'] for r in fixed] == [2, 2]
    assert fixed[1]['iou_mean'] == pytest.approx(.51)
    assert fixed[1]['gain_from_one'] == pytest.approx(.01)
    assert fixed[1]['mc_error_bound'] == pytest.approx(.02)
    assert all(r['images']=='short' for r in grouped if r['cohort']=='非困难（已标）')
    assert all(r['images']=='long' for r in grouped if r['panel_max_k']==4)
    assert len(enriched)==len(rows)
    with pytest.raises(ValueError, match='incomplete_image_curve'):
        summarize(rows[:-1], meta, thresholds=(2,4))
    with pytest.raises(ValueError, match='duplicate_curve_point'):
        summarize(rows+[rows[0]], meta, thresholds=(2,4))
