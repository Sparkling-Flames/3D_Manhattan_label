import json

import pandas as pd
import pytest

from tools.thesis_main.analysis.review_building_convergence_evidence_20260908 import (
    census, summarize_curves, matched_curve_distances,
)


def test_census_retains_excluded_workers_and_does_not_count_revisions_as_people():
    a = pd.DataFrame([
        dict(canonical_annotation_id=f'{c}-{w}', context_key=c, image_id=c,
             building_id='B', stage='P1', block_index=0, raw_condition='manual',
             worker_id=w, current20_member=w != 3,
             historical_primary_eligibility_status='excluded' if w == 3 else 'eligible')
        for c in ['I1', 'I2'] for w in [1, 2, 3]
    ])
    lineage = pd.DataFrame({'canonical_annotation_id': list(a.canonical_annotation_id) + ['I1-1']})
    states = a[['canonical_annotation_id']].assign(status='computable_point_pattern')
    states.loc[0, 'status'] = 'empty_point_response'
    buildings, contexts = census(a, lineage, states)
    row = buildings.iloc[0]
    assert (row.canonical_responses, row.workers, row.raw_versions, row.nonindependent_revisions) == (6, 3, 7, 1)
    assert row.computable_responses == 5
    assert json.loads(row.historical_eligibility_counts_json)['excluded'] == 2
    assert list(contexts.raw_workers) == [3, 3]
    with pytest.raises(ValueError, match='duplicate'):
        census(pd.concat([a, a.iloc[:1]]), lineage, states)


def values():
    rows = []
    # Different numbers of valid permutations must not change image weighting.
    for building, image, value, reps in [('A', 'a1', 0., [0, 1]), ('A', 'a2', .2, [0]),
                                         ('B', 'b1', .8, [0, 1]), ('B', 'b2', 1., [0, 1])]:
        for replicate in reps:
            for k in [3, 5]:
                rows.append(dict(building_id=building, image_id=image, context_key=image,
                                 stage='P1', block_index=0, raw_condition='manual', initialization_kind='not_applicable',
                                 scheme='two_thirds', config='ospa30_t6', max_k=5,
                                 path='full_history_fixed', measure='distribution_tv',
                                 split_id=f'{replicate}|{building}|two_thirds', replicate=replicate, k=k, value=value))
    return pd.DataFrame(rows)


def test_building_summary_weights_images_equally_not_permutation_rows():
    contexts, buildings = summarize_curves(values())
    assert contexts[(contexts.context_key == 'a1') & (contexts.k == 3)].iloc[0].valid_splits == 2
    assert buildings[(buildings.building_id == 'A') & (buildings.k == 3)].iloc[0]['mean'] == pytest.approx(.1)


def test_curve_comparison_matches_shared_permutations_and_preserves_unsupported_pairs():
    f = values()
    f.loc[(f.context_key == 'a1') & (f.replicate == 1), 'value'] = .9
    pairs, summary = matched_curve_distances(f)
    pair = pairs[(pairs.left_context == 'a1') & (pairs.right_context == 'a2')].iloc[0]
    assert pair.shared_replicates == 1 and pair.curve_distance == pytest.approx(.2)
    assert summary.iloc[0].within_building_distance == pytest.approx(.2)
    assert summary.iloc[0].between_building_distance > summary.iloc[0].within_building_distance
    f.loc[f.context_key == 'a2', 'replicate'] = 9
    pairs, summary = matched_curve_distances(f)
    pair = pairs[(pairs.left_context == 'a1') & (pairs.right_context == 'a2')].iloc[0]
    assert pair.status == 'no_shared_replicates' and pd.isna(pair.curve_distance)
    assert summary.iloc[0].comparable_buildings == 0
    assert pd.isna(summary.iloc[0].between_building_distance)


def three_buildings(spec):
    template = values().iloc[0].to_dict()
    return pd.DataFrame([template | dict(building_id=b, context_key=f'{b}{i}', image_id=f'{b}{i}',
                            replicate=r, split_id=f'{r}|{b}|two_thirds', k=k, value=v)
                         for b, reps, vals in spec for i, v in enumerate(vals) for r in reps for k in [3, 5]])


def test_isolated_building_is_excluded_from_both_sides_of_comparison():
    f = three_buildings([('A', [0], [0., 0.]), ('B', [0], [0., 0.]), ('C', [1], [0., 1.])])
    _, result = matched_curve_distances(f)
    row = result.iloc[0]
    assert row.comparable_buildings == 2
    assert row.within_building_distance == row.between_building_distance == 0
    assert row.descriptive_within_distance == pytest.approx(1/3)


def test_incomplete_building_pair_graph_has_matched_endpoint_weights():
    f = three_buildings([('A', [0, 1], [0., 1.]), ('B', [0], [0., 0.]), ('C', [1], [0., 0.])])
    _, result = matched_curve_distances(f)
    row = result.iloc[0]
    assert row.within_building_distance == pytest.approx(1/3)
    assert row.between_building_distance == pytest.approx(.5)
    assert row.pair_matched_within_distance == pytest.approx(.5)
    assert row.between_minus_within == pytest.approx(0.)
