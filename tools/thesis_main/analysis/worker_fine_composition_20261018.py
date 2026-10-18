"""真实v1：冻结楼外画像的粗细分类、固定构成换成员及顺序过程。"""
import argparse
import json
import math
import random
import zlib
from collections import Counter
from itertools import combinations, combinations_with_replacement, product
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
OLD = ROOT / 'research/workers/worker_v1_composition_20261017'
FUSION = ROOT / 'research/fusion/wall_consensus_v1_process_20261017'
OUT = ROOT / 'research/workers/worker_fine_composition_20261018'
SCHEMES = ['Q2', 'QT4', 'Q3']


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def save(name, value):
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2,
        allow_nan=False) + '\n', encoding='utf-8')


def table(name, rows):
    pd.DataFrame(rows).to_csv(OUT / name, index=False, encoding='utf-8-sig')


def add_classes(profiles):
    """阈值只读楼外已拟合效应；分位数并列不拆，未知不参与阈值。"""
    profiles = profiles.copy()
    profiles['Q2'] = profiles.Q_group
    profiles['QT4'] = profiles.QT_group
    profiles['Q3'] = 'unclassified'
    profiles['Q3_25_75'] = 'unclassified'
    thresholds = []
    for (fold, metric), d in profiles.groupby(['fold', 'metric']):
        assert all(fold not in json.loads(x) for x in d.Q_training_buildings)
        supported = d.Q_supported & d.Q_effect.notna()
        assert (d.loc[supported, 'Q_contexts'] >= 6).all()
        assert (d.loc[supported, 'Q_buildings'] >= 3).all()
        for scheme, quantiles in [('Q3', (1 / 3, 2 / 3)), ('Q3_25_75', (.25, .75))]:
            low, high = np.quantile(d.loc[supported, 'Q_effect'], quantiles)
            thresholds.append(dict(fold=fold, metric=metric, scheme=scheme,
                lower_cut=low, upper_cut=high, supported_workers=int(supported.sum()),
                training_profile='worker_v1_composition_20261017_frozen'))
            for ix, row in d[supported].iterrows():
                profiles.loc[ix, scheme] = ('low' if row.Q_effect < low else
                    'high' if row.Q_effect > high else 'middle')
    return profiles, pd.DataFrame(thresholds)


def composition(labels):
    return '|'.join(f'{label}:{n}' for label, n in sorted(Counter(labels).items()))


def parse_composition(value):
    return {name: int(n) for name, n in (part.split(':') for part in value.split('|'))}


def count_compositions(people, k):
    counts = Counter(v for v in people.values() if v != 'unclassified')
    result = {}
    for labels in combinations_with_replacement(sorted(counts), k):
        needed = Counter(labels)
        ways = math.prod(math.comb(counts[g], n) if n <= counts[g] else 0 for g, n in needed.items())
        if ways:
            result[composition(labels)] = ways
    return result


def draw_members(people, key, n, seed):
    required = parse_composition(key)
    options = [list(combinations(sorted(w for w, c in people.items() if c == label), count))
        for label, count in required.items()]
    # k=4有界枚举，先生成支持集合，再按预设种子无放回抽样。
    all_teams = sorted(tuple(sorted(w for group in groups for w in group)) for groups in product(*options))
    return random.Random(seed).sample(all_teams, min(n, len(all_teams)))


def shape(key):
    return '+'.join(map(str, sorted(parse_composition(key).values(), reverse=True)))


def choose_compositions(counts, scheme):
    if scheme == 'Q2':
        return sorted(counts)
    # 每种构成形态选择支持集合最多的一个；同数按标签排序，不看融合结果。
    selected = {}
    for key in sorted(counts, key=lambda c: (-counts[c], c)):
        selected.setdefault(shape(key), key)
    return sorted(set(selected.values()) | {key for key, n in counts.items() if shape(key) == '4' and n >= 2})


def load_design():
    prior = read(OLD / 'TEAM_REQUESTS.json')
    profiles, thresholds = add_classes(pd.read_csv(OLD / 'fold_person_profiles.csv'))
    pools = {}
    for team in prior['teams']:
        image = team['image_code']
        if image not in pools or team['k'] > pools[image]['k']:
            pools[image] = team
    return prior, profiles, thresholds, pools


def build_requests(profiles, pools):
    index = profiles.set_index(['fold', 'metric', 'worker_id'])
    pool_rows, support, labels = [], [], {}
    for image, pool in sorted(pools.items()):
        row = dict(image_code=image, image_id=pool['image_id'], building_id=pool['building_id'],
            scene_bucket=pool['scene_bucket'], source_pool_n=pool['k'],
            original_holdout_pool_n=pool['original_holdout_member_n'])
        for metric in ['B8L2', 'D10']:
            for scheme in SCHEMES + ['Q3_25_75']:
                people = {w: index.loc[(pool['building_id'], metric, w), scheme] for w in pool['worker_ids']}
                labels[(image, metric, scheme)] = people
                counts = count_compositions(people, 4)
                for key, n in counts.items():
                    support.append(dict(image_code=image, building_id=pool['building_id'],
                        scene_bucket=pool['scene_bucket'], selection_metric=metric, scheme=scheme, k=4,
                        composition=key, pattern=shape(key), possible_member_sets=n,
                        classified_pool_n=sum(v != 'unclassified' for v in people.values()),
                        unknown_pool_n=sum(v == 'unclassified' for v in people.values())))
                if metric == 'B8L2' and scheme in SCHEMES:
                    row[scheme + '_classes'] = len(set(people.values()) - {'unclassified'})
                    row[scheme + '_supported_compositions'] = len(counts)
        row['selection_support'] = sum(row[s + '_supported_compositions'] for s in SCHEMES)
        pool_rows.append(row)
    inventory = pd.DataFrame(pool_rows)
    selected = []
    buildings = set()
    for scene, n in [('doorway_only', 2), ('neither_flagged', 6)]:
        candidates = inventory[inventory.scene_bucket.eq(scene) & inventory.source_pool_n.ge(8)
            & inventory.original_holdout_pool_n.eq(0)]
        candidates = candidates.sort_values(['selection_support', 'source_pool_n', 'image_code'], ascending=[False, False, True])
        for row in candidates.to_dict('records'):
            if row['building_id'] in buildings:
                continue
            selected.append(row['image_code'])
            buildings.add(row['building_id'])
            if sum(pools[x]['scene_bucket'] == scene for x in selected) == n:
                break
    inventory['selected_targeted_panel'] = inventory.image_code.isin(selected)
    requests, extra_pure = [], []
    for image in selected:
        pool = pools[image]
        for scheme in SCHEMES:
            people = labels[(image, 'B8L2', scheme)]
            counts = count_compositions(people, 4)
            base_shapes = {}
            for key in sorted(counts, key=lambda c: (-counts[c], c)):
                base_shapes.setdefault(shape(key), key)
            for key in choose_compositions(counts, scheme):
                extras = scheme != 'Q2' and key not in base_shapes.values()
                seed = 20261018 + zlib.crc32((image + scheme + key).encode())
                for draw, members in enumerate(draw_members(people, key, 3, seed)):
                    (extra_pure if extras else requests).append(dict(request_id=f'FINE{len(requests)+1:05d}', image_code=image,
                        image_id=pool['image_id'], building_id=pool['building_id'], condition='manual',
                        scene_bucket=pool['scene_bucket'], scheme=scheme, selection_metric='B8L2',
                        composition=key, pattern=shape(key), k=4, worker_ids=list(members),
                        draw_id=draw, order_id='', step_k=4, experiment='fixed_k_composition_and_members',
                        possible_member_sets=counts[key], original_holdout_member_n=0))
        # 每图取首个QT三类以上构成的第一组，正序/反序/固定随机序。终点相同。
        eligible = [r for r in requests if r['image_code'] == image and r['scheme'] == 'QT4'
            and len(parse_composition(r['composition'])) >= 3 and r['draw_id'] == 0]
        if eligible:
            base = eligible[0]
            members = base['worker_ids']
            orders = [members, members[::-1], random.Random(20261018).sample(members, len(members))]
            for order_id, order in enumerate(orders):
                for k in range(1, 5):
                    requests.append(dict(base, request_id=f'FINE{len(requests)+1:05d}', worker_ids=order[:k],
                        k=k, step_k=k, order_id=f'{image}_O{order_id}',
                        composition=composition([labels[(image, 'B8L2', 'QT4')][w] for w in order[:k]]),
                        pattern=shape(composition([labels[(image, 'B8L2', 'QT4')][w] for w in order[:k]])),
                        experiment='same_endpoint_order', final_worker_ids=members))
    for row in extra_pure:
        row['request_id'] = f'FINE{len(requests)+1:05d}'
        requests.append(row)
    support = pd.DataFrame(support)
    support['selected_targeted_panel'] = support.image_code.isin(selected)
    return requests, inventory, support


def describe_existing(prior, profiles):
    """广图机会性支持单列，不把优先顺序留下的集合称为均衡抽样。"""
    teams = {t['request_id']: t for t in prior['teams']}
    results = pd.read_csv(FUSION / 'TEAM_RESULTS.csv')
    index = profiles.set_index(['fold', 'metric', 'worker_id'])
    rows = []
    for r in results.to_dict('records'):
        source = teams[r['request_id']]
        for metric in ['B8L2', 'D10']:
            for scheme in SCHEMES + ['Q3_25_75']:
                labels = [index.loc[(source['building_id'], metric, w), scheme] for w in source['worker_ids']]
                rows.append(dict(request_id=r['request_id'], image_code=source['image_code'],
                    building_id=source['building_id'], scene_bucket=source['scene_bucket'],
                    selection_metric=metric, scheme=scheme, composition=composition(labels),
                    pattern=shape(composition(labels)), unknown_members=labels.count('unclassified'),
                    worker_ids='|'.join(sorted(source['worker_ids'])), k=source['k'],
                    status=r['status'], complete_evaluable=r['complete_evaluable'],
                    main_comparison_allowed=r['main_comparison_allowed'],
                    B8L2=r['B8L2'], D10=r['D10'], nodes=r['nodes'],
                    R_union_normalized=r['R_union_normalized'], omission=r['omission'], extension=r['extension'],
                    cohort='existing_opportunistic_20261017'))
    return pd.DataFrame(rows)


def summarize_cells(data):
    keys = ['cohort', 'selection_metric', 'scheme', 'image_code', 'building_id', 'scene_bucket', 'k', 'composition']
    groups = []
    for key, d in data.groupby(keys, dropna=False):
        d = d.drop_duplicates('worker_ids')
        eligible = d.main_comparison_allowed.eq(True) & d.complete_evaluable.eq(True)
        out = dict(zip(keys, key), member_sets=len(d), quality_member_sets=int((eligible & d.B8L2.notna()).sum()),
            unknown_members=int(d.unknown_members.max()), pattern=shape(key[-1]))
        for metric in ['B8L2', 'D10', 'nodes', 'R_union_normalized', 'omission', 'extension']:
            values = d.loc[eligible, metric] if metric in ['B8L2', 'D10', 'omission', 'extension'] else d[metric]
            out.update({metric + '_n': int(values.notna().sum()), metric + '_mean': values.mean(),
                metric + '_sd': values.std(), metric + '_range': values.max() - values.min()})
        groups.append(out)
    return pd.DataFrame(groups)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--phase', choices=['design', 'analyze'], default='design')
    parser.add_argument('--results', type=Path)
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    prior, profiles, thresholds, pools = load_design()
    if args.phase == 'design':
        requests, inventory, support = build_requests(profiles, pools)
        table('fold_classes.csv', profiles)
        table('class_thresholds.csv', thresholds)
        table('pool_support.csv', inventory)
        table('composition_support.csv', support)
        save('TEAM_REQUESTS.json', dict(schema='worker_fine_composition_20261018_v1', data_release='v1',
            profile_source='research/workers/worker_v1_composition_20261017/fold_person_profiles.csv',
            profile_freeze='20261017_1048_manual_training_before_coordinate_restoration',
            selection_reads_target_outcomes=False, seed=20261018,
            design_revision='r3_all_supported_pure_classes_before_outcomes',
            selection_rule='two doorway then six ordinary non-original-holdout pools; one image/building; descending feasible compositions and pool N; lexical ties',
            composition_rule='Q2 all feasible; QT4/Q3 max-support per partition shape plus every pure class with >=2 sets; three seeded distinct sets',
            input_geometry='fusion consumer must use adopted restored input and report revision; no simulated data',
            requests=requests))
        table('request_membership.csv', [dict(r, worker_ids='|'.join(r['worker_ids']),
            final_worker_ids='|'.join(r.get('final_worker_ids', []))) for r in requests])
        existing = describe_existing(prior, profiles)
        table('existing_team_classes.csv', existing)
        cells = summarize_cells(existing)
        table('existing_composition_cells.csv', cells)
        full = profiles[profiles.fold.eq('full_descriptive')]
        table('person_classes.csv', full)
        summary = dict(schema='worker_fine_composition_summary_v1', status='design_and_existing_completed',
            data_release='v1', existing_images=len(pools), existing_team_requests=len(prior['teams']),
            requested_rows=len(requests), requested_unique_sets=len({(r['image_code'], tuple(sorted(r['worker_ids']))) for r in requests}),
            selected_images=inventory.loc[inventory.selected_targeted_panel, 'image_code'].tolist(),
            selected_buildings=int(inventory.loc[inventory.selected_targeted_panel, 'building_id'].nunique()),
            profile_source_freeze='20261017 ordinary Manual 1048; not refit after coordinate restoration',
            unknown_classes_preserved=True, overlapping_teams_are_not_independent_samples=True)
        save('summary.json', summary)
        print(json.dumps(summary, ensure_ascii=False))
    else:
        analyze(args.results, profiles)


def analyze(results_path, profiles):
    results_path = results_path or ROOT / 'research/fusion/worker_composition_fusion_20261018/team_results.csv'
    requested = pd.read_csv(OUT / 'request_membership.csv', keep_default_na=False)
    result = pd.read_csv(results_path)
    result = result[result.request_family.eq('fine_composition')].copy()
    assert set(result.request_id) == set(requested.request_id)
    assert not result.request_id.duplicated().any()
    # 请求表确定分类与选择，融合表只提供实际产物；不由输出重选人员。
    measures = [c for c in result if c not in requested or c == 'request_id']
    joined = requested.merge(result[measures], on='request_id', validate='one_to_one')
    index = profiles.set_index(['fold', 'metric', 'worker_id'])
    joined['unknown_members'] = [sum(index.loc[(r.building_id, r.selection_metric, w), r.scheme] == 'unclassified'
        for w in r.worker_ids.split('|')) for r in joined.itertuples()]
    joined['cohort'] = 'targeted_8_images_20261018'
    for r in joined.itertuples():
        assert len(r.worker_ids.split('|')) == r.k
        assert r.original_holdout_member_n == 0
    table('team_analysis.csv', joined)
    fixed = joined[joined.experiment.eq('fixed_k_composition_and_members')]
    cells = summarize_cells(fixed)
    pairs_path = results_path.parent / 'same_composition_pairs.csv'
    pairs = pd.read_csv(pairs_path)
    pairs = pairs[pairs.request_a.isin(fixed.request_id) & pairs.request_b.isin(fixed.request_id)].copy()
    metadata = fixed[['request_id', 'image_code', 'building_id', 'scene_bucket', 'scheme', 'selection_metric', 'k', 'composition']]
    pairs = pairs.merge(metadata.rename(columns={'request_id': 'request_a'}), on='request_a', suffixes=('_fusion', ''), validate='many_to_one')
    table('member_replacement_pairs.csv', pairs)
    vkeys = ['image_code', 'scheme', 'selection_metric', 'k', 'composition']
    vrows = []
    for key, d in pairs.groupby(vkeys):
        values = d.loc[d.both_complete_floor.eq(True), 'floor_jaccard_difference']
        vrows.append(dict(zip(vkeys, key), compared_member_pairs=len(d),
            V_valid_pairs=int(values.notna().sum()), V_floor_jaccard_mean=values.mean(),
            V_floor_jaccard_max=values.max(), changed_coidentity_pairs_mean=d.changed_coidentity_pairs.mean(),
            node_count_difference_mean=d.node_count_difference.abs().mean()))
    cells = cells.merge(pd.DataFrame(vrows), on=vkeys, how='left', validate='one_to_one')
    table('composition_cells.csv', cells)
    between = pd.read_csv(results_path.parent / 'between_composition_pairs.csv')
    between = between[between.request_a.isin(fixed.request_id) & between.request_b.isin(fixed.request_id)].copy()
    between = between.merge(metadata.drop(columns='composition').rename(columns={'request_id': 'request_a'}),
        on='request_a', suffixes=('_fusion', ''), validate='many_to_one')
    table('between_composition_pairs.csv', between)
    structure = []
    for relation, values in [('same_composition', pairs), ('different_composition', between)]:
        for key, d in values.groupby(['image_code', 'building_id', 'scene_bucket', 'scheme']):
            valid = d[d.both_complete_floor.eq(True)]
            correspondence = d[d.common_pair_comparisons.gt(0)]
            structure.append(dict(zip(['image_code', 'building_id', 'scene_bucket', 'scheme'], key),
                relation=relation, attempted_pairs=len(d), valid_floor_pairs=len(valid),
                V_floor_jaccard_mean=valid.floor_jaccard_difference.mean(),
                V_floor_jaccard_median=valid.floor_jaccard_difference.median(),
                node_count_changed_pairs=int((d.node_count_difference.notna() & d.node_count_difference.ne(0)).sum()),
                correspondence_comparable_pairs=len(correspondence),
                correspondence_changed_pairs=int(correspondence.changed_coidentity_pairs.gt(0).sum())))
    table('structure_variation_by_image.csv', structure)

    contrasts = []
    for (image, scheme), d in cells.groupby(['image_code', 'scheme']):
        for a, b in combinations(d.sort_values('composition').to_dict('records'), 2):
            if a['quality_member_sets'] < 2 or b['quality_member_sets'] < 2:
                continue
            contrasts.append(dict(image_code=image, building_id=a['building_id'], scene_bucket=a['scene_bucket'],
                scheme=scheme, k=4, composition_a=a['composition'], composition_b=b['composition'],
                member_sets_a=a['member_sets'], member_sets_b=b['member_sets'],
                B8L2_b_minus_a=b['B8L2_mean'] - a['B8L2_mean'],
                D10_b_minus_a=b['D10_mean'] - a['D10_mean'],
                nodes_b_minus_a=b['nodes_mean'] - a['nodes_mean'],
                V_b_minus_a=b['V_floor_jaccard_mean'] - a['V_floor_jaccard_mean']))
    table('between_composition_by_image.csv', contrasts)
    pure = []
    candidates = {'Q2': [('lower:4', 'higher:4')],
        'Q3': [('low:4', 'high:4'), ('low:4', 'middle:4'), ('middle:4', 'high:4')],
        'QT4': [('lower_faster:4', 'higher_faster:4'), ('lower_slower:4', 'higher_slower:4'),
            ('higher_slower:4', 'higher_faster:4'), ('lower_slower:4', 'lower_faster:4')]}
    for (image, scheme), d in cells.groupby(['image_code', 'scheme']):
        by_comp = d.set_index('composition')
        for a, b in candidates[scheme]:
            if a not in by_comp.index or b not in by_comp.index:
                continue
            x, y = by_comp.loc[a], by_comp.loc[b]
            pure.append(dict(image_code=image, building_id=x.building_id, scene_bucket=x.scene_bucket,
                scheme=scheme, contrast=b + '_minus_' + a,
                both_quality_at_least_two=x.quality_member_sets >= 2 and y.quality_member_sets >= 2,
                quality_sets_a=int(x.quality_member_sets), quality_sets_b=int(y.quality_member_sets),
                B8L2_difference=y.B8L2_mean - x.B8L2_mean,
                D10_difference=y.D10_mean - x.D10_mean,
                V_difference=y.V_floor_jaccard_mean - x.V_floor_jaccard_mean))
    pure = pd.DataFrame(pure)
    table('pure_class_contrasts_by_image.csv', pure)
    summaries = []
    for (scheme, contrast, layer), d in pd.concat([pure.assign(layer='all'), pure.assign(layer=pure.scene_bucket)]).groupby(['scheme', 'contrast', 'layer']):
        valid = d[d.both_quality_at_least_two]
        summaries.append(dict(scheme=scheme, contrast=contrast, layer=layer, attempted_images=len(d),
            comparable_images=len(valid), independent_buildings=valid.building_id.nunique(),
            B8L2_mean=valid.B8L2_difference.mean(), B8L2_min=valid.B8L2_difference.min(),
            B8L2_max=valid.B8L2_difference.max(), positive_images=int(valid.B8L2_difference.gt(0).sum()),
            negative_images=int(valid.B8L2_difference.lt(0).sum()), D10_mean=valid.D10_difference.mean(),
            V_mean=valid.V_difference.mean()))
    table('pure_class_contrast_summary.csv', summaries)

    transitions = pd.read_csv(results_path.parent / 'transitions.csv')
    transitions = transitions[transitions.request_a.isin(joined.request_id) & transitions.request_b.isin(joined.request_id)]
    table('order_transitions.csv', transitions)
    table('order_trajectories.csv', joined[joined.experiment.eq('same_endpoint_order')])
    endpoint = joined[joined.experiment.eq('same_endpoint_order') & joined.k.eq(4)]
    order_checks = endpoint.groupby('image_code').agg(orders=('request_id', 'size'),
        final_member_sets=('worker_ids', lambda s: len({tuple(sorted(v.split('|'))) for v in s})),
        B8L2_spread=('B8L2', lambda s: s.max() - s.min()))
    assert order_checks.final_member_sets.eq(1).all()
    table('order_endpoint_checks.csv', order_checks.reset_index())

    sensitivity = []
    for r in fixed.itertuples():
        workers = r.worker_ids.split('|')
        for metric in ['B8L2', 'D10']:
            for scheme in SCHEMES + ['Q3_25_75']:
                labels = [index.loc[(r.building_id, metric, w), scheme] for w in workers]
                sensitivity.append(dict(request_id=r.request_id, image_code=r.image_code, design_scheme=r.scheme,
                    design_composition=r.composition, design_selection_metric=r.selection_metric,
                    profile_metric=metric, reinterpretation_scheme=scheme,
                    composition=composition(labels), worker_ids=r.worker_ids, B8L2=r.B8L2, D10=r.D10,
                    interpretation='same_members_relabelled_no_reselection'))
    table('fixed_member_classification_sensitivity.csv', sensitivity)

    cases = []
    valid_pairs = pairs[pairs.both_quality.eq(True) & pairs.both_main.eq(True)]
    # 可视复审实例按预定选图后的差异挑选；不反向改变设计或把它当盲测。
    for scheme, d in valid_pairs.groupby('scheme'):
        if len(d):
            r = d.sort_values('floor_jaccard_difference', ascending=False).iloc[0]
            cases.append(dict(case_kind='same_composition_largest_observed_geometry_difference', scheme=scheme,
                image_code=r.image_code, composition=r.composition, request_a=r.request_a, request_b=r.request_b,
                floor_jaccard_difference=float(r.floor_jaccard_difference)))
    for sign in ['positive', 'negative']:
        d = pure[pure.both_quality_at_least_two & (pure.B8L2_difference.gt(0) if sign == 'positive' else pure.B8L2_difference.lt(0))]
        if len(d):
            r = d.iloc[d.B8L2_difference.abs().argmax()]
            b, a = r.contrast.split('_minus_')
            left = fixed[fixed.image_code.eq(r.image_code) & fixed.scheme.eq(r.scheme) & fixed.composition.eq(a)].iloc[0]
            right = fixed[fixed.image_code.eq(r.image_code) & fixed.scheme.eq(r.scheme) & fixed.composition.eq(b)].iloc[0]
            cases.append(dict(case_kind='pure_class_' + sign + '_mean_contrast', scheme=r.scheme,
                image_code=r.image_code, composition=r.contrast, request_a=left.request_id, request_b=right.request_id,
                B8L2_cell_mean_difference=float(r.B8L2_difference),
                display_note='展示预设draw0；数值为各组三队均值差，非所展示两队差'))
    doorway = between[between.scene_bucket.eq('doorway_only') & between.both_quality.eq(True) & between.both_main.eq(True)]
    if len(doorway):
        r = doorway.iloc[doorway.node_count_difference.abs().argmax()]
        cases.append(dict(case_kind='different_composition_doorway_node_change', scheme=r.scheme,
            image_code=r.image_code, composition=r.composition_a + ' vs ' + r.composition_b,
            request_a=r.request_a, request_b=r.request_b,
            node_count_difference=int(r.node_count_difference), floor_jaccard_difference=float(r.floor_jaccard_difference)))
    save('review_cases.json', dict(selection='posthoc_examples_only_not_design_selection', cases=cases))
    summary = read(OUT / 'summary.json')
    summary.update(status='targeted_true_fusion_completed', requested_rows=len(requested),
        requested_unique_sets=len({(r.image_code, tuple(sorted(r.worker_ids.split('|')))) for r in requested.itertuples()}),
        selected_images=sorted(joined.image_code.unique()), selected_buildings=joined.building_id.nunique(),
        target_team_attempts=len(fixed), complete_team_rows=int(fixed.complete_evaluable.eq(True).sum()),
        quality_team_rows=int((fixed.main_comparison_allowed.eq(True) & fixed.B8L2.notna()).sum()),
        supported_composition_cells=len(cells), replacement_pairs=len(pairs),
        between_composition_pairs=len(between),
        review_cases=len(cases), order_paths=int(joined.loc[joined.experiment.eq('same_endpoint_order'), 'order_id'].nunique()),
        selection_reads_target_outcomes=False, input_geometry_results=str(results_path.relative_to(ROOT)),
        mixed_compositions_are_shape_representatives_not_exhaustive=True)
    save('summary.json', summary)
    csvs = {}
    for path in sorted(OUT.glob('*.csv')):
        frame = pd.read_csv(path, low_memory=False)
        csvs[path.name] = dict(rows=len(frame), columns=list(frame.columns))
    save('FIELD_CONTRACT.json', dict(schema='worker_fine_composition_20261018_v1', tables=csvs,
        units=dict(Q='0–100 conditional score; failed/diagnostic not filled with zero',
            R_union_normalized='原作答两两范围分歧，非融合成员波动',
            V_floor_jaccard='同图同构成不同真人集合的融合底面1-IoU；仅实际可计算对',
            composition='label:count sorted lexically; unknown remains explicit',
            pattern='counts sorted descending; not a class label',
            independent_unit='image/building; overlapping subsets are repeated observations'),
        classification='frozen 20261017 LOBO Q/T; Q3 cuts on supported worker effects; no target outcome fitting',
        scope_semi='not inserted into fine classes because compatible opportunity support is insufficient',
        holdout='targeted panel excludes pools with any original holdout; wide existing panel keeps its status'))
    save('CHECKS.json', dict(request_rows=len(requested), result_rows=len(result), exact_request_id_set=True,
        target_building_excluded_from_profile_training=True, no_simulated_inputs=True,
        target_original_holdout_members=int(joined.original_holdout_member_n.sum()),
        same_final_member_set_in_each_order_panel=True, scores_missing_not_zero_filled=True,
        classification_retrained_after_coordinate_restoration=False))
    save('INPUTS.json', dict(data_release='v1', actual_sources=[str(p.relative_to(ROOT)).replace('\\', '/') for p in [
        OLD / 'fold_person_profiles.csv', OLD / 'TEAM_REQUESTS.json', FUSION / 'TEAM_RESULTS.csv',
        results_path, pairs_path, results_path.parent / 'between_composition_pairs.csv',
        results_path.parent / 'transitions.csv']],
        quality_profile_training_rows=1048, profile_fit_revision='worker_b8l2_d10_20261017',
        geometry_revision_source='research/fusion/worker_composition_fusion_20261018/input_snapshot.json',
        historical_wide_results_preserved=True, simulated_received_data_consumed=False))
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == '__main__':
    main()
