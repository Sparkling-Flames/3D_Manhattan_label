"""固定背景单人交换：绝对Q、相对Q与效率细类的6/8/12/16人观察。"""
import argparse
import json
import random
import zlib
from itertools import product
from pathlib import Path

import numpy as np
import pandas as pd

from .worker_fine_composition_20261018 import add_classes, composition

ROOT = Path(__file__).resolve().parents[3]
OLD = ROOT / 'research/workers/worker_v1_composition_20261017'
FINE = ROOT / 'research/workers/worker_fine_composition_20261018'
OUT = ROOT / 'research/workers/worker_exchangeability_20261018'
FUSION = ROOT / 'research/fusion/worker_exchangeability_fusion_20261018'
SCHEMES = ['AbsQ3', 'RelQ3', 'RelQT4']
SIZES = [6, 8, 12, 16]


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def save(name, value):
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def table(name, value):
    pd.DataFrame(value).to_csv(OUT / name, index=False, encoding='utf-8-sig')


def absolute_profiles(panel, folds):
    rows = []
    for fold in folds:
        train = panel if fold == 'full_descriptive' else panel[panel.building_id.ne(fold)]
        assert fold not in set(train.building_id)
        for worker, d in train.groupby('worker_id'):
            for metric in ['B8L2', 'D10']:
                valid = d[d[metric].notna()]
                rows.append(dict(fold=fold, worker_id=worker, metric=metric, absolute_Q=valid[metric].mean(),
                    absolute_n=len(valid), absolute_images=valid.image_id.nunique(),
                    absolute_buildings=valid.building_id.nunique(),
                    absolute_supported=valid.image_id.nunique() >= 6 and valid.building_id.nunique() >= 3,
                    absolute_training_buildings=json.dumps(sorted(valid.building_id.unique()))))
    return pd.DataFrame(rows)


def build_profiles():
    prior = pd.read_csv(OLD / 'fold_person_profiles.csv')
    classes, thresholds = add_classes(prior)
    source = ROOT / 'research/workers/worker_b8l2_d10_20261017/quality_panel.csv'
    panel = pd.read_csv(source)
    assert len(panel) == 1048 and panel.object_id.nunique() == 1048
    absolute = absolute_profiles(panel, sorted(prior.fold.unique()))
    classes = classes.merge(absolute, on=['fold', 'metric', 'worker_id'], how='left', validate='one_to_one')
    classes['AbsQ3'] = 'unclassified'
    classes['RelQ3'] = classes.Q3
    classes['RelQT4'] = classes.QT4
    cuts = []
    for (fold, metric), d in classes.groupby(['fold', 'metric']):
        supported = d.absolute_supported.eq(True) & d.absolute_Q.notna()
        low, high = np.quantile(d.loc[supported, 'absolute_Q'], [1/3, 2/3])
        cuts.append(dict(fold=fold, metric=metric, lower_cut=low, upper_cut=high,
            axis='absolute_mean_Q', workers=int(supported.sum())))
        for ix, r in d[supported].iterrows():
            classes.loc[ix, 'AbsQ3'] = 'low' if r.absolute_Q < low else 'high' if r.absolute_Q > high else 'middle'
    for axis in ['AbsQ3', 'RelQ3']:
        classes[axis + 'T6'] = ['unclassified' if q == 'unclassified' or t == 'unclassified' else q + '_' + t
            for q, t in zip(classes[axis], classes.T_group)]
    return classes, pd.DataFrame(cuts), thresholds


def exchange_design(profiles, pools, selected_images):
    index = profiles[profiles.metric.eq('B8L2')].set_index(['fold', 'worker_id'])
    requests, comparisons, support = [], [], []
    for image in selected_images:
        pool = pools[image]
        workers = sorted(pool['worker_ids'])
        assert pool['original_holdout_member_n'] == 0
        info = {w: index.loc[(pool['building_id'], w)].to_dict() for w in workers}
        for scheme in SCHEMES:
            labels = {w: info[w][scheme] for w in workers}
            names = sorted(set(labels.values()) - {'unclassified'})
            for label in names:
                own = [w for w in workers if labels[w] == label]
                others = [v for v in names if v != label]
                support.append(dict(image_code=image, building_id=pool['building_id'], scene_bucket=pool['scene_bucket'],
                    scheme=scheme, class_label=label, class_workers=len(own), worker_ids='|'.join(own),
                    same_class_exchange_supported=len(own) >= 2, pure_team_size_limit=len(own),
                    source_pool_n=len(workers), largest_background_supported_k=len(workers)-2))
                if len(own) < 2 or not others:
                    continue
                seed = 20261018 + zlib.crc32((image + scheme + label).encode())
                rng = random.Random(seed)
                member_pairs = [(a,b) for a in own for b in own if a != b]
                triplets = rng.sample(member_pairs, min(2, len(member_pairs)))
                cross_labels = rng.sample(others, len(others))
                for triplet_id, (anchor, same) in enumerate(triplets):
                    cross_label = cross_labels[triplet_id % len(cross_labels)]
                    cross = rng.choice([w for w in workers if labels[w] == cross_label])
                    remaining = [w for w in workers if w not in [anchor, same, cross]]
                    for background_id in range(2):
                        order = random.Random(seed + 1000 * triplet_id + 13 * background_id + 1).sample(remaining, len(remaining))
                        chain = f'{image}_{scheme}_{label}_t{triplet_id}_b{background_id}'
                        for k in SIZES:
                            if len(order) < k-1:
                                continue
                            background = order[:k-1]
                            block = chain + f'_k{k}'
                            by_variant = {}
                            for variant, entrant in [('anchor', anchor), ('same_class', same), ('cross_class', cross)]:
                                request_id = f'EXCH{len(requests)+1:06d}'
                                by_variant[variant] = request_id
                                members = background + [entrant]
                                requests.append(dict(request_id=request_id, image_code=image, image_id=pool['image_id'],
                                    building_id=pool['building_id'], condition='manual', scene_bucket=pool['scene_bucket'],
                                    selection_metric='B8L2', scheme=scheme, composition=composition([labels[w] for w in members]),
                                    k=k, worker_ids=members, original_holdout_member_n=0, exchange_block_id=block,
                                    chain_id=chain, background_worker_ids=background, entrant_worker_id=entrant,
                                    anchor_worker_id=anchor, same_class_worker_id=same, cross_class_worker_id=cross,
                                    anchor_class=label, entrant_class=labels[entrant], cross_class=cross_label,
                                    triplet_id=triplet_id, background_id=background_id, variant=variant,
                                    experiment='fixed_background_single_exchange', draw_id=triplet_id,
                                    order_id='', step_k=k))
                            for kind, entrant in [('same_class', same), ('cross_class', cross)]:
                                t_delta = info[entrant]['T_source_effect'] - info[anchor]['T_source_effect']
                                comparisons.append(dict(comparison_id=f'SWAP{len(comparisons)+1:06d}',
                                    request_a=by_variant['anchor'], request_b=by_variant[kind], swap_kind=kind,
                                    exchange_block_id=block, chain_id=chain, image_code=image,
                                    building_id=pool['building_id'], scene_bucket=pool['scene_bucket'], k=k,
                                    scheme=scheme, anchor_class=label, replacement_class=labels[entrant],
                                    entrant_a=anchor, entrant_b=entrant, background_id=background_id, triplet_id=triplet_id,
                                    absolute_Q_b_minus_a=info[entrant]['absolute_Q'] - info[anchor]['absolute_Q'],
                                    relative_Q_b_minus_a=info[entrant]['Q_effect'] - info[anchor]['Q_effect'],
                                    T_effect_b_minus_a=t_delta if pd.notna(t_delta) else None))
    return requests, comparisons, pd.DataFrame(support)


def design():
    OUT.mkdir(parents=True, exist_ok=True)
    profiles, absolute_cuts, relative_cuts = build_profiles()
    prior = read(OLD / 'TEAM_REQUESTS.json')
    pools = {}
    for team in prior['teams']:
        image = team['image_code']
        if image not in pools or team['k'] > pools[image]['k']:
            pools[image] = team
    selected = read(FINE / 'summary.json')['selected_images']
    requests, comparisons, support = exchange_design(profiles, pools, selected)
    table('fold_profiles.csv', profiles)
    table('person_profiles.csv', profiles[profiles.fold.eq('full_descriptive')])
    table('absolute_class_thresholds.csv', absolute_cuts)
    table('relative_class_thresholds.csv', relative_cuts)
    table('class_support.csv', support)
    table('comparisons_design.csv', comparisons)
    table('requests_design.csv', [dict(r, worker_ids='|'.join(r['worker_ids']),
        background_worker_ids='|'.join(r['background_worker_ids'])) for r in requests])
    save('TEAM_REQUESTS.json', dict(schema='worker_exchangeability_20261018_v1', data_release='v1',
        design_revision='nested_background_single_person_exchange_v1', selected_images=selected,
        classification_inputs='frozen real Manual1048 training; target building excluded for absolute/relative Q and T',
        personal_quality_axes=['absolute_Q', 'relative_Q'], efficiency_axis='T_source_effect',
        excluded_from_personal_quality=['scope', 'Semi'], sizes=SIZES,
        design='2 entrant triplets per supported class, 2 backgrounds; same ABC and nested background across k',
        selection_reads_target_outcomes=False, random_seed=20261018,
        inference_unit='image/building; shared anchors/backgrounds/repeated k not independent',
        requests=requests, comparisons=comparisons))
    save('summary.json', dict(schema='worker_exchangeability_summary_v1', status='design_frozen',
        requested_rows=len(requests), unique_member_sets=len({(r['image_code'], tuple(sorted(r['worker_ids']))) for r in requests}),
        comparison_rows=len(comparisons), exchange_blocks=len({r['exchange_block_id'] for r in requests}),
        selected_images=selected, independent_buildings=len({r['building_id'] for r in requests}),
        sizes=SIZES, schemes=SCHEMES, data_release='v1', quality_axes=['absolute_Q','relative_Q']))
    print(json.dumps(read(OUT / 'summary.json'), ensure_ascii=False))


def analyze():
    request = pd.read_csv(OUT / 'requests_design.csv', keep_default_na=False)
    design_pairs = pd.read_csv(OUT / 'comparisons_design.csv')
    teams = pd.read_csv(FUSION / 'team_results.csv', low_memory=False)
    teams = teams[teams.request_family.eq('exchangeability')]
    pairs = pd.read_csv(FUSION / 'exchange_pairs.csv')
    assert teams.request_id.is_unique and set(teams.request_id) == set(request.request_id)
    assert pairs.comparison_id.is_unique and set(pairs.comparison_id) == set(design_pairs.comparison_id)
    assert (pairs.shared_workers == pairs.k-1).all()
    pairs['B8_delta'] = pairs.B8L2_difference
    pairs['D10_delta'] = pairs.D10_difference
    pairs['abs_B8_delta'] = pairs.B8_delta.abs()
    pairs['abs_D10_delta'] = pairs.D10_delta.abs()
    pairs['node_count_unchanged'] = pairs.node_count_difference.eq(0)
    pairs['node_count_changed'] = pairs.node_count_difference.ne(0)
    pairs['absolute_Q_direction'] = np.select([pairs.absolute_Q_b_minus_a > 0, pairs.absolute_Q_b_minus_a < 0], ['higher','lower'], default='equal')
    pairs['relative_Q_direction'] = np.select([pairs.relative_Q_b_minus_a > 0, pairs.relative_Q_b_minus_a < 0], ['higher','lower'], default='equal')
    attach_annotation_evidence(pairs)
    table('exchange_analysis.csv', pairs)
    table('team_analysis.csv', teams)
    blocks = matched_blocks(pairs)
    table('matched_block_analysis.csv', blocks)
    keys = ['image_code', 'building_id', 'scene_bucket', 'scheme', 'k']
    image_class = aggregate_blocks(blocks, keys + ['anchor_class'])
    image = aggregate_blocks(blocks, keys)
    table('by_image_k_class.csv', image_class)
    table('by_image_k.csv', image)
    table('summary_by_k.csv', summarize_images(image, ['scheme', 'k']))
    table('summary_by_k_class.csv', summarize_images(image_class, ['scheme', 'k', 'anchor_class']))
    fixed = blocks.groupby('chain_id').agg(sizes=('k', 'nunique'),
        V_valid_all_sizes=('paired_V_available', 'all'), Q_valid_all_sizes=('paired_Q_available', 'all'))
    fixed['V_complete_chain'] = fixed.sizes.eq(len(SIZES)) & fixed.V_valid_all_sizes
    fixed['Q_complete_chain'] = fixed.sizes.eq(len(SIZES)) & fixed.Q_valid_all_sizes
    table('fixed_chain_coverage.csv', fixed.reset_index())
    chain_curves = []
    for endpoint in ['V', 'Q']:
        eligible = fixed[fixed[endpoint + '_complete_chain']].index
        curve = aggregate_blocks(blocks[blocks.chain_id.isin(eligible)], keys)
        curve['fixed_endpoint'] = endpoint
        chain_curves.append(curve)
    curves = pd.concat(chain_curves, ignore_index=True)
    table('fixed_chain_curves_by_image.csv', curves)
    table('fixed_chain_curve_summary.csv', summarize_images(curves, ['scheme', 'k', 'fixed_endpoint']))
    larger = blocks[blocks.k.eq(16)].merge(blocks[blocks.k.eq(6)], on='chain_id', suffixes=('_16', '_6'), validate='one_to_one')
    size_changes = []
    for r in larger.itertuples():
        size_changes.append(dict(chain_id=r.chain_id, image_code=r.image_code_16, building_id=r.building_id_16,
            scene_bucket=r.scene_bucket_16, scheme=r.scheme_16, anchor_class=r.anchor_class_16,
            both_endpoint_V=r.paired_V_available_16 and r.paired_V_available_6,
            both_endpoint_Q=r.paired_Q_available_16 and r.paired_Q_available_6,
            same_V_16_minus_6=r.same_V_16-r.same_V_6, cross_V_16_minus_6=r.cross_V_16-r.cross_V_6,
            same_abs_Q_16_minus_6=r.same_abs_B8_delta_16-r.same_abs_B8_delta_6,
            cross_abs_Q_16_minus_6=r.cross_abs_B8_delta_16-r.cross_abs_B8_delta_6))
    table('fixed_chain_size_changes.csv', size_changes)
    targeted_directions(pairs)
    background_transfer(pairs, request)
    annotation_relation_summary(pairs)
    review_cases(pairs)
    failure_rows = []
    for key, d in teams.groupby(['image_code', 'building_id', 'scene_bucket', 'scheme', 'k', 'variant']):
        failure_rows.append(dict(zip(['image_code', 'building_id', 'scene_bucket', 'scheme', 'k', 'variant'], key),
            attempts=len(d), complete=int(d.complete_evaluable.sum()), main_quality=int(d.B8L2.notna().sum()),
            failed_or_incomplete=int((~d.complete_evaluable).sum()), status_counts=json.dumps(d.score_status.value_counts().to_dict())))
    table('completion_by_image_k.csv', failure_rows)
    summary = read(OUT / 'summary.json')
    summary.update(status='true_exchange_results_completed', returned_rows=len(teams), returned_comparisons=len(pairs),
        complete_team_rows=int(teams.complete_evaluable.sum()), main_quality_team_rows=int(teams.B8L2.notna().sum()),
        valid_floor_pairs=int(pairs.floor_jaccard_difference.notna().sum()),
        valid_quality_pairs=int(pairs.B8_delta.notna().sum()),
        paired_V_blocks=int(blocks.paired_V_available.sum()), paired_Q_blocks=int(blocks.paired_Q_available.sum()),
        all_sizes_V_chains=int(fixed.V_complete_chain.sum()), all_sizes_Q_chains=int(fixed.Q_complete_chain.sum()),
        annotation_distance_available=int(pairs.annotation_floor_jaccard_distance.notna().sum()))
    save('summary.json', summary)
    owned_tables = ['fold_profiles.csv', 'person_profiles.csv', 'absolute_class_thresholds.csv',
        'relative_class_thresholds.csv', 'class_support.csv', 'comparisons_design.csv', 'requests_design.csv',
        'exchange_analysis.csv', 'team_analysis.csv', 'matched_block_analysis.csv', 'by_image_k_class.csv',
        'by_image_k.csv', 'summary_by_k.csv', 'summary_by_k_class.csv', 'fixed_chain_coverage.csv',
        'fixed_chain_curves_by_image.csv', 'fixed_chain_curve_summary.csv', 'fixed_chain_size_changes.csv',
        'high_fast_directions.csv', 'high_fast_by_image_k.csv', 'high_fast_summary.csv', 'completion_by_image_k.csv',
        'background_transfer.csv', 'background_transfer_summary.csv', 'cross_image_exchange_support.csv',
        'annotation_relation_by_image_k.csv', 'annotation_distance_association.csv']
    save('FIELD_CONTRACT.json', dict(schema='worker_exchangeability_20261018_v1',
        tables={name: dict(rows=len(pd.read_csv(OUT/name)), columns=list(pd.read_csv(OUT/name, nrows=0))) for name in owned_tables},
        units=dict(B8_delta='replacement B minus anchor A, 0–100 points; unavailable stays missing',
            floor_jaccard_difference='actual fused floor 1-IoU after replacing exactly one person',
            annotation_floor_jaccard_distance='two original submissions floor 1-IoU; not fused result or personnel type',
            cross_minus_same='matched anchor/background; positive means same-class exchange changed less',
            exact_equality='use fusion exact fields only; node count unchanged does not imply same geometry'),
        independence='image/building; anchor/background/k/overlapping teams are repeated observations',
        quality_axes=['absolute_Q', 'relative_Q'], efficiency_axis='T_source_effect', scope_semi_not_quality_axes=True))
    save('CHECKS.json', dict(all_requests_returned=True, all_comparisons_returned=True,
        exactly_one_person_replaced=True, nested_backgrounds_checked_by_tests=True,
        fixed_anchor_matched_comparison=True, no_target_outcome_in_selection=True,
        missing_results_not_zero_filled=True, original_holdout_members=0, real_data_only=True))
    save('INPUTS.json', dict(data_release='v1', classification_sources=[
        'research/workers/worker_v1_composition_20261017/fold_person_profiles.csv',
        'research/workers/worker_b8l2_d10_20261017/quality_panel.csv'],
        prepared_geometry_source='research/fusion/worker_exchangeability_fusion_20261018/input_snapshot.json',
        result_sources=['research/fusion/worker_exchangeability_fusion_20261018/team_results.csv',
            'research/fusion/worker_exchangeability_fusion_20261018/exchange_pairs.csv'],
        annotation_evidence=['annotation_pair_distances.csv','annotation_clusters.csv','CLUSTER_NOTES.md'],
        source_training_rows=1048, target_building_excluded=True,
        N1_applied=False, scope_semi_used_as_quality=False, simulated_data_used=False))
    print(json.dumps(summary, ensure_ascii=False))


def attach_annotation_evidence(pairs):
    evidence = pd.read_csv(OUT / 'annotation_pair_distances.csv')
    evidence['pair_key'] = ['|'.join(sorted([a,b])) for a,b in zip(evidence.worker_id_a, evidence.worker_id_b)]
    assert not evidence.duplicated(['image_code','pair_key']).any()
    lookup = evidence.set_index(['image_code','pair_key'])
    pairs['annotation_floor_jaccard_distance'] = [lookup.loc[(r.image_code, '|'.join(sorted([r.entrant_a,r.entrant_b]))), 'distance_floor_1_minus_iou']
        for r in pairs.itertuples()]
    pairs['annotation_same_pair_count'] = [lookup.loc[(r.image_code, '|'.join(sorted([r.entrant_a,r.entrant_b]))), 'same_pair_count']
        for r in pairs.itertuples()]
    clusters = pd.read_csv(OUT / 'annotation_clusters.csv')
    for method, threshold in [('range_similarity_complete', .20), ('annotation_structure_bound_cyclic_complete', 9.0)]:
        selected = clusters[clusters.method.eq(method) & np.isclose(clusters.threshold, threshold)]
        chosen = selected.set_index(['image_code','worker_id'])
        values = []
        for r in pairs.itertuples():
            a = chosen.loc[(r.image_code,r.entrant_a), 'cluster_id']
            b = chosen.loc[(r.image_code,r.entrant_b), 'cluster_id']
            values.append(a == b if pd.notna(a) and pd.notna(b) else None)
        field = 'annotation_same_range_cluster_020' if method == 'range_similarity_complete' else 'annotation_same_structure_cluster_9deg'
        pairs[field] = values


def matched_blocks(pairs):
    rows = []
    for key, d in pairs.groupby('exchange_block_id'):
        assert len(d) == 2 and set(d.swap_kind) == {'same_class','cross_class'}
        same = d[d.swap_kind.eq('same_class')].iloc[0]
        cross = d[d.swap_kind.eq('cross_class')].iloc[0]
        assert same.request_a == cross.request_a
        row = {c: same[c] for c in ['chain_id','image_code','building_id','scene_bucket','scheme','k','anchor_class']}
        row.update(exchange_block_id=key, anchor_request_id=same.request_a,
            same_request_id=same.request_b, cross_request_id=cross.request_b,
            same_comparison_id=same.comparison_id, cross_comparison_id=cross.comparison_id,
            paired_V_available=pd.notna(same.floor_jaccard_difference) and pd.notna(cross.floor_jaccard_difference),
            paired_Q_available=pd.notna(same.B8_delta) and pd.notna(cross.B8_delta),
            same_V=same.floor_jaccard_difference, cross_V=cross.floor_jaccard_difference,
            same_abs_B8_delta=same.abs_B8_delta, cross_abs_B8_delta=cross.abs_B8_delta,
            same_abs_D10_delta=same.abs_D10_delta, cross_abs_D10_delta=cross.abs_D10_delta,
            same_node_count_changed=bool(same.node_count_changed), cross_node_count_changed=bool(cross.node_count_changed),
            same_annotation_floor_distance=same.annotation_floor_jaccard_distance, cross_annotation_floor_distance=cross.annotation_floor_jaccard_distance)
        row['cross_minus_same_V'] = row['cross_V'] - row['same_V']
        row['cross_minus_same_abs_B8_delta'] = row['cross_abs_B8_delta'] - row['same_abs_B8_delta']
        for field in ['full_geometry_equal', 'floor_geometry_equal', 'node_content_equal']:
            if field in d:
                row['same_' + field] = same[field]
                row['cross_' + field] = cross[field]
        rows.append(row)
    return pd.DataFrame(rows)


def aggregate_blocks(blocks, keys):
    rows = []
    for key, d in blocks.groupby(keys):
        v = d[d.paired_V_available]
        q = d[d.paired_Q_available]
        row = dict(zip(keys,key), blocks=len(d), V_blocks=len(v), Q_blocks=len(q),
            same_V=v.same_V.mean(), cross_V=v.cross_V.mean(), cross_minus_same_V=v.cross_minus_same_V.mean(),
            same_abs_B8_delta=q.same_abs_B8_delta.mean(), cross_abs_B8_delta=q.cross_abs_B8_delta.mean(),
            cross_minus_same_abs_B8_delta=q.cross_minus_same_abs_B8_delta.mean(),
            same_abs_D10_delta=q.same_abs_D10_delta.mean(), cross_abs_D10_delta=q.cross_abs_D10_delta.mean(),
            same_class_smaller_V_blocks=int(v.cross_minus_same_V.gt(0).sum()),
            same_class_larger_V_blocks=int(v.cross_minus_same_V.lt(0).sum()),
            same_node_changed_rate=d.same_node_count_changed.mean(), cross_node_changed_rate=d.cross_node_count_changed.mean())
        for measure in ['full_geometry_equal', 'floor_geometry_equal', 'node_content_equal']:
            fields = ['same_' + measure, 'cross_' + measure]
            if fields[0] not in d:
                continue
            matched = d[d[fields[0]].notna() & d[fields[1]].notna()]
            for field in fields:
                row[field + '_n'] = len(matched)
                row[field + '_rate'] = matched[field].mean()
        rows.append(row)
    return pd.DataFrame(rows)


def summarize_images(frame, by):
    rows = []
    for key, d in pd.concat([frame.assign(layer='all'), frame.assign(layer=frame.scene_bucket)]).groupby(by + ['layer']):
        v, q = d[d.V_blocks.gt(0)], d[d.Q_blocks.gt(0)]
        row = dict(zip(by + ['layer'],key), attempted_images=d.image_code.nunique(),
            valid_V_images=v.image_code.nunique(), valid_Q_images=q.image_code.nunique(),
            independent_buildings=d.building_id.nunique(), blocks=int(d.blocks.sum()),
            V_blocks=int(d.V_blocks.sum()), Q_blocks=int(d.Q_blocks.sum()),
            same_V=v.same_V.mean(), cross_V=v.cross_V.mean(), cross_minus_same_V=v.cross_minus_same_V.mean(),
            same_abs_B8_delta=q.same_abs_B8_delta.mean(), cross_abs_B8_delta=q.cross_abs_B8_delta.mean(),
            cross_minus_same_abs_B8_delta=q.cross_minus_same_abs_B8_delta.mean(),
            same_abs_D10_delta=q.same_abs_D10_delta.mean(), cross_abs_D10_delta=q.cross_abs_D10_delta.mean(),
            same_class_smaller_V_images=int(v.cross_minus_same_V.gt(0).sum()),
            same_class_larger_V_images=int(v.cross_minus_same_V.lt(0).sum()))
        for field in [c for c in frame if c.endswith('_geometry_equal_rate') or c.endswith('_node_content_equal_rate')]:
            row[field] = d[field].mean()
        rows.append(row)
    return pd.DataFrame(rows)


def targeted_directions(pairs):
    target = 'higher_faster'
    d = pairs[pairs.scheme.eq('RelQT4') & pairs.swap_kind.eq('cross_class') &
        (pairs.anchor_class.eq(target) | pairs.replacement_class.eq(target))].copy()
    d['opponent_class'] = np.where(d.anchor_class.eq(target), d.replacement_class, d.anchor_class)
    d['high_fast_minus_other_Q'] = np.where(d.replacement_class.eq(target), d.B8_delta, -d.B8_delta)
    d['high_fast_minus_other_D10'] = np.where(d.replacement_class.eq(target), d.D10_delta, -d.D10_delta)
    table('high_fast_directions.csv', d)
    rows = []
    for key, g in d.groupby(['image_code','building_id','scene_bucket','k','opponent_class']):
        rows.append(dict(zip(['image_code','building_id','scene_bucket','k','opponent_class'],key),
            attempts=len(g), V_pairs=int(g.floor_jaccard_difference.notna().sum()),
            Q_pairs=int(g.high_fast_minus_other_Q.notna().sum()),
            V=g.floor_jaccard_difference.mean(), high_fast_minus_other_Q=g.high_fast_minus_other_Q.mean(),
            high_fast_minus_other_D10=g.high_fast_minus_other_D10.mean()))
    by_image = pd.DataFrame(rows)
    table('high_fast_by_image_k.csv', by_image)
    summaries = []
    for key,g in pd.concat([by_image.assign(layer='all'),by_image.assign(layer=by_image.scene_bucket)]).groupby(['k','opponent_class','layer']):
        q = g[g.Q_pairs.gt(0)]
        summaries.append(dict(zip(['k','opponent_class','layer'],key), images=g.image_code.nunique(),
            quality_images=q.image_code.nunique(), high_fast_minus_other_Q=q.high_fast_minus_other_Q.mean(),
            high_fast_minus_other_D10=q.high_fast_minus_other_D10.mean(), V=g.V.mean(),
            positive_images=int(q.high_fast_minus_other_Q.gt(0).sum()), negative_images=int(q.high_fast_minus_other_Q.lt(0).sum())))
    table('high_fast_summary.csv', summaries)


def background_transfer(pairs, requests):
    keys = ['image_code','building_id','scene_bucket','scheme','k','anchor_class','triplet_id','swap_kind','entrant_a','entrant_b']
    a = pairs[pairs.background_id.eq(0)]
    b = pairs[pairs.background_id.eq(1)]
    transfer = a.merge(b, on=keys, suffixes=('_discovery','_check'), validate='one_to_one')
    membership = requests.set_index('request_id').background_worker_ids.map(lambda s: set(s.split('|'))).to_dict()
    transfer['shared_background_members'] = [len(membership[x] & membership[y])
        for x,y in zip(transfer.request_a_discovery,transfer.request_a_check)]
    transfer['same_background_set'] = transfer.shared_background_members.eq(transfer.k-1)
    transfer['discover_exact_full'] = transfer.full_geometry_equal_discovery.eq(True)
    transfer['discover_small_floor_001'] = transfer.floor_jaccard_difference_discovery.le(.01)
    table('background_transfer.csv', transfer)
    summaries = []
    for rule in ['discover_exact_full','discover_small_floor_001']:
        candidates = transfer[transfer[rule] & ~transfer.same_background_set]
        all_layers = pd.concat([candidates.assign(layer='all'), candidates.assign(layer=candidates.scene_bucket)])
        for key, d in all_layers.groupby(['scheme','k','layer']):
            v = d.floor_jaccard_difference_check.dropna()
            equality = d.full_geometry_equal_check.dropna()
            summaries.append(dict(zip(['scheme','k','layer'],key), discovery_rule=rule,
                discovered_pairs=len(d), images=d.image_code.nunique(),
                check_floor_available=len(v), check_full_equality_available=len(equality),
                retained_small_floor_001=int(v.le(.01).sum()), retained_exact_full=int(equality.eq(True).sum()),
                check_V_mean=v.mean(), check_V_median=v.median(), check_V_q90=v.quantile(.9), check_V_max=v.max(),
                mean_shared_background_members=d.shared_background_members.mean()))
    table('background_transfer_summary.csv', summaries)
    source = pairs.copy()
    source['worker_pair'] = ['|'.join(sorted([a,b])) for a,b in zip(source.entrant_a,source.entrant_b)]
    image = source.groupby(['worker_pair','k','image_code','building_id']).agg(
        attempts=('comparison_id','size'), valid_V=('floor_jaccard_difference','count'),
        V_image_mean=('floor_jaccard_difference','mean'),
        exact_full_rate=('full_geometry_equal','mean')).reset_index()
    rows = []
    for (worker_pair,k),d in image.groupby(['worker_pair','k']):
        rows.append(dict(worker_pair=worker_pair,k=k,images=d.image_code.nunique(),buildings=d.building_id.nunique(),
            images_with_V=int(d.valid_V.gt(0).sum()), V_image_mean=d.V_image_mean.mean(),
            V_image_min=d.V_image_mean.min(),V_image_max=d.V_image_mean.max(),
            exact_full_rate_min=d.exact_full_rate.min(),exact_full_rate_max=d.exact_full_rate.max()))
    table('cross_image_exchange_support.csv', rows)


def annotation_relation_summary(pairs):
    rows, associations = [], []
    for key,d in pairs.groupby(['image_code','building_id','scene_bucket','k']):
        valid=d.dropna(subset=['annotation_floor_jaccard_distance','floor_jaccard_difference'])
        # 重复背景是机制观察；相关系数只描述该图，不能按重放对数作推断。
        corr = valid[['annotation_floor_jaccard_distance','floor_jaccard_difference']].corr(method='spearman').iloc[0,1]
        associations.append(dict(zip(['image_code','building_id','scene_bucket','k'],key),
            available_pairs=len(valid), original_fused_floor_spearman=corr))
        for field, method in [('annotation_same_range_cluster_020','range_similarity_complete_0.20'),
            ('annotation_same_structure_cluster_9deg','annotation_structure_bound_cyclic_complete_9deg')]:
            for same, subset in d[d[field].notna()].groupby(field):
                rows.append(dict(zip(['image_code','building_id','scene_bucket','k'],key),
                    cluster_method=method,same_cluster=bool(same),attempts=len(subset),
                    V_available=int(subset.floor_jaccard_difference.notna().sum()),
                    V_mean=subset.floor_jaccard_difference.mean(),abs_Q_mean=subset.abs_B8_delta.mean(),
                    original_distance_mean=subset.annotation_floor_jaccard_distance.mean(),
                    exact_full_rate=subset.full_geometry_equal.mean()))
    table('annotation_relation_by_image_k.csv',rows)
    table('annotation_distance_association.csv',associations)


def review_cases(pairs):
    rows = []
    valid = pairs[pairs.both_main & pairs.both_quality & pairs.floor_jaccard_difference.notna()]
    candidates = valid[(valid.anchor_class=='higher_faster') & valid.swap_kind.eq('same_class') & valid.k.eq(16)]
    if len(candidates):
        for kind, index in [('high_fast_same_class_largest_change', candidates.floor_jaccard_difference.idxmax()),
            ('high_fast_same_class_typical_change', (candidates.floor_jaccard_difference-candidates.floor_jaccard_difference.median()).abs().idxmin())]:
            rows.append((kind,candidates.loc[index]))
    candidates = valid[valid.k.eq(16) & valid.swap_kind.eq('same_class') & valid.node_count_unchanged]
    if len(candidates):
        rows.append(('same_node_count_large_geometry_change',candidates.loc[candidates.floor_jaccard_difference.idxmax()]))
    candidates = valid[valid.swap_kind.eq('cross_class') & valid.full_geometry_equal.eq(True)]
    if len(candidates):
        rows.append(('different_person_class_same_fused_geometry',candidates.iloc[0]))
    transfer = pd.read_csv(OUT/'background_transfer.csv')
    candidates = transfer[transfer.discover_small_floor_001 & transfer.floor_jaccard_difference_check.notna()]
    if len(candidates):
        r = candidates.loc[candidates.floor_jaccard_difference_check.idxmax()]
        rows.append(('small_change_does_not_transfer_background',pairs[pairs.comparison_id.eq(r.comparison_id_check)].iloc[0]))
    save('review_cases.json',dict(selection='posthoc explanatory examples; not used to design classes/teams',
        cases=[dict(case_kind=kind,comparison_id=r.comparison_id,image_code=r.image_code,k=int(r.k),
            scheme=r.scheme,swap_kind=r.swap_kind,request_a=r.request_a,request_b=r.request_b,
            entrant_a=r.entrant_a,entrant_b=r.entrant_b,anchor_class=r.anchor_class,replacement_class=r.replacement_class,
            floor_jaccard_difference=float(r.floor_jaccard_difference),
            B8_delta=float(r.B8_delta) if pd.notna(r.B8_delta) else None) for kind,r in rows]))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--phase', choices=['design', 'analyze'], default='design')
    args = parser.parse_args()
    (design if args.phase == 'design' else analyze)()


if __name__ == '__main__':
    main()
