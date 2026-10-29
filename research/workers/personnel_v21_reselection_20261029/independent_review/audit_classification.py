"""Read ZIP inputs; check stored labels, history, stability and Q baseline design."""
import argparse
import io
import itertools
import json
import zipfile
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.cluster.hierarchy import linkage, cut_tree
from sklearn.decomposition import PCA
from sklearn.metrics import adjusted_rand_score


def read(archive, name):
    return pd.read_csv(io.BytesIO(archive.read(name)), compression='gzip' if name.endswith('.gz') else None, low_memory=False)


def partition(frame):
    groups = tuple(sorted(tuple(sorted(g.worker_id)) for _, g in frame[frame.known.eq(True)].groupby('class_id')))
    return groups, tuple(sorted(frame.loc[~frame.known.eq(True), 'worker_id']))


def describe(values):
    return {k: float(v) for k, v in pd.Series(values).describe().items()}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--downloads', type=Path, default=Path.home() / 'Downloads')
    parser.add_argument('--repo', type=Path, default=Path(r'D:\Work\HOHONET'))
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    paths = [list(args.downloads.glob(f'*v21*07{s}*20261029.zip')) for s in ['A', 'B']]
    assert all(len(p) == 1 for p in paths)
    za, zb = [zipfile.ZipFile(p[0]) for p in paths]
    labels = read(za, 'classification/MAIN45_LABELS_ALL_LOBO.csv.gz')
    personnel = read(za, 'stage07_adoption/PERSONNEL_LOBO_LABELS_AND_SUPPORT.csv.gz')
    history = read(za, 'classification/NEW_PERSONNEL_HISTORY_ALL.csv')
    config = json.loads(za.read('classification/CANDIDATE_CONFIG_BEFORE_TEAM_RESULTS.json'))
    registry = read(za, 'stage02/CURRENT_45_METHOD_FORMATION_REGISTRY.csv')
    assert len(labels) == 45 * 23 * 62
    assert not labels.duplicated(['method', 'heldout_building', 'worker_id']).any()
    signatures = defaultdict(list)
    for method, g in labels.groupby('method'):
        signatures[tuple((fold, partition(p)) for fold, p in g.groupby('heldout_building'))].append(method)
    reported_equivalence = read(za, 'stage07_adoption/METHODS_EXACT_PARTITION_EQUIVALENCE.csv')
    equivalence = []
    for (a, b), g in reported_equivalence.groupby(['method_a', 'method_b']):
        equal_folds = []
        for fold in labels.heldout_building.unique():
            aa = labels[labels.method.eq(a) & labels.heldout_building.eq(fold)]
            bb = labels[labels.method.eq(b) & labels.heldout_building.eq(fold)]
            actual = partition(aa) == partition(bb)
            reported = g[g.heldout_building.eq(fold)].same_partition_ignoring_ids.iloc[0]
            assert actual == reported
            if actual:
                equal_folds.append(fold)
        equivalence.append({'method_a': a, 'method_b': b, 'identical_folds': len(equal_folds), 'all_folds': 23})
    stability = {}
    for method in ['OPPJOINT_K3', 'OPPJOINT_K4']:
        d = labels[labels.method.eq(method) & labels.known.eq(True)]
        all_labels = d[d.heldout_building.eq('ALL')].set_index('worker_id').class_id
        folded, rows = [], []
        for fold, g in d[~d.heldout_building.eq('ALL')].groupby('heldout_building'):
            current = g.set_index('worker_id').class_id.reindex(all_labels.index)
            folded.append(current)
            rows.append({'fold': fold, 'ari_vs_all': adjusted_rand_score(all_labels, current), 'sizes': g.class_id.value_counts().to_dict()})
        stability[method] = {'ari_vs_all': describe([r['ari_vs_all'] for r in rows]), 'pairwise_lobo_ari': describe([adjusted_rand_score(a, b) for a, b in itertools.combinations(folded, 2)]), 'folds': rows}
    overlaps = []
    qa = labels[labels.method.eq('OPPJOINT_K4') & labels.heldout_building.eq('ALL') & labels.known.eq(True)].merge(history[['worker_id', 'm_all_B8L2']], on='worker_id', validate='one_to_one')
    groups = [('ALL', qa)] + list(personnel[personnel.method.eq('OPPJOINT_K4') & personnel.known.eq(True)].groupby('heldout_building'))
    for fold, g in groups:
        high_class = g.groupby('class_id').m_all_B8L2.mean().idxmax()
        joint = set(g.loc[g.class_id.eq(high_class), 'worker_id'])
        qtop = set(g.sort_values(['m_all_B8L2', 'worker_id'], ascending=[False, True]).head(len(joint)).worker_id)
        overlaps.append({'fold': fold, 'capacity': len(joint), 'overlap': len(joint & qtop), 'fraction': len(joint & qtop) / len(joint), 'joint_only': sorted(joint - qtop), 'q_only': sorted(qtop - joint)})
    child_count = 0
    for fold in labels.heldout_building.unique():
        d = labels[labels.heldout_building.eq(fold) & labels.known.eq(True)]
        a = d[d.method.eq('OPPJOINT_K3')][['worker_id', 'class_id']]
        b = d[d.method.eq('OPPJOINT_K4')][['worker_id', 'class_id']]
        m = a.merge(b, on='worker_id', suffixes=('_parent', '_child'), validate='one_to_one')
        assert len(m) == 56 and m.groupby('class_id_child').class_id_parent.nunique().eq(1).all()
        child_count += m.class_id_child.nunique()
    raw = read(za, 'targets/RECORD_TARGET_LINKS_AND_ALL_SUPPORT_WEIGHTS.csv.gz').rename(columns={'worker': 'worker_id'})
    counts = {'inventory': len(raw), 'ordinary_history': int(raw.layer.isin(['ordinary_manual', 'ordinary_semi']).sum()), 'manual_history': int(raw.layer.eq('ordinary_manual').sum())}
    release = args.repo / 'research/data/releases/v2.1'
    official = pd.read_csv(release / 'condition_classification/RAW_CONDITION_RESPONSE_RECORDS.csv.gz', low_memory=False)
    old_ids = set(official.loc[official.history_eligible.eq(True), 'object_id'])
    new_ids = set(raw.loc[raw.layer.isin(['ordinary_manual', 'ordinary_semi']), 'record_id'])
    history_scope = {'official_records': len(old_ids), 'new_records': len(new_ids), 'common_records': len(old_ids & new_ids), 'official_only': len(old_ids - new_ids), 'new_only': len(new_ids - old_ids), 'official_only_by_condition': official[official.object_id.isin(old_ids - new_ids)].groupby('condition').size().to_dict()}
    axes = pd.read_csv(release / 'scope_axis_classification/AXIS_METHOD_LABELS_ALL_LOBO.csv.gz', low_memory=False)
    fields = ['heldout_building', 'worker_id', 'class_id', 'axis_score']
    axis_match = axes[axes.method.eq('Q_MEDIAN2')][fields].merge(labels[labels.method.eq('Q_MEDIAN2')][fields], on=['heldout_building', 'worker_id'], validate='one_to_one')
    assert len(axis_match) == 23 * 62 and axis_match.class_id_x.eq(axis_match.class_id_y).all()
    assert (axis_match.axis_score_x - axis_match.axis_score_y).abs().max() == 0
    history_scope['Q_median_reused_official_label_rows'] = len(axis_match)
    raw['log_time'] = np.log(raw.source_time_seconds.where(raw.source_time_seconds.gt(0)))
    for metric in ['B8L2', 'log_time']:
        keys = ['image_id', 'reference_id', 'condition'] + (['origin', 'time_source_kind'] if metric == 'log_time' else [])
        raw[metric + '_peer'] = raw[metric] - raw.groupby(keys, dropna=False)[metric].transform('median')
    raw = raw[raw.layer.eq('ordinary_manual')].copy()
    errors = []
    for fold, g in personnel[personnel.method.eq('OPPJOINT_K4')].groupby('heldout_building'):
        d = raw[raw.building.ne(fold)]
        for metric in ['B8L2', 'log_time']:
            h = d.dropna(subset=[metric + '_peer']).groupby(['worker_id', 'building', 'image_id', 'reference_id'])[metric + '_peer'].mean().groupby(['worker_id', 'building', 'image_id']).mean().groupby(['worker_id', 'building']).mean().groupby('worker_id').mean()
            saved = g.set_index('worker_id')['m_all_' + metric].dropna()
            assert set(h.index) == set(saved.index)
            errors.append(float((h - saved).abs().max()))
    assert len(errors) == 44 and max(errors) < 1e-10
    aris = []
    for fold, g in personnel[personnel.method.eq('OPPJOINT_K4') & personnel.known.eq(True)].groupby('heldout_building'):
        parts = []
        for domain in config['families']['OPPJOINT']['domains']:
            a = g[config['domains'][domain]].to_numpy()
            med, scale = np.median(a, axis=0), np.quantile(a, .85, axis=0) - np.quantile(a, .15, axis=0)
            sd = np.std(a, axis=0)
            a = np.clip((a - med) / np.where(scale > 1e-9, scale, np.where(sd > 1e-9, sd, 1)), -3, 3)
            pc = PCA(n_components=min(2, a.shape[1], len(a) - 1), svd_solver='full').fit_transform(a)
            parts.append(pc / max(np.sqrt(np.mean(np.sum(pc ** 2, axis=1))), 1e-9) / 2)
        tree = linkage(np.column_stack(parts), method='ward', optimal_ordering=True)
        for k in [3, 4]:
            gold = personnel[personnel.method.eq(f'OPPJOINT_K{k}') & personnel.heldout_building.eq(fold) & personnel.known.eq(True)].set_index('worker_id').class_id.reindex(g.worker_id)
            aris.append(adjusted_rand_score(cut_tree(tree, n_clusters=k).ravel(), gold))
    assert len(aris) == 44 and min(aris) == 1
    focus = read(zb, 'experiment/focused_design/EVENTS_EXACT.csv.gz')
    focus = focus[focus.method.eq('OPPJOINT_K4') & focus.n.eq(12) & focus.m.eq(6)]
    baseline = read(zb, 'experiment/refinement_baseline_design/EVENTS_EXACT.csv.gz')
    baseline = baseline[baseline.method.eq('Q_MEDIAN2')]
    backgrounds = []
    canonical = lambda s: '|'.join(sorted(str(s).split('|')))
    for pool, g in focus.groupby('pool_id'):
        q = baseline[baseline.pool_id.eq(pool)]
        assert len(q)
        a, b = set(g.D.map(canonical)), set(q.D.map(canonical))
        backgrounds.append({'pool_id': pool, 'joint_D': len(a), 'q_D': len(b), 'common_D': len(a & b)})
    package_members = set()
    for path in args.downloads.glob('*v21*20261029.zip'):
        with zipfile.ZipFile(path) as archive:
            package_members.update(archive.namelist())
    needed = ['experiment/global_screen_design/EVENTS_EXACT.csv.gz', 'analysis/global_screen/EVENT_METRICS.csv.gz', 'stage05/ALL7356_CONDITIONS_KEY_RESULTS.csv']
    result = {
        'status': 'passed',
        'sources': [str(p[0]) for p in paths],
        'labels': {'rows': len(labels), 'methods': int(labels.method.nunique()), 'folds': int(labels.heldout_building.nunique()), 'workers': int(labels.worker_id.nunique()), 'sources': registry.groupby('source_stage').size().to_dict(), 'unique_full_fold_partitions': len(signatures), 'equivalent_all_folds_groups': [g for g in signatures.values() if len(g) > 1], 'checked_partial_equivalences': equivalence},
        'stability': stability,
        'q_top_capacity_overlap': {'folds': overlaps, 'lobo_fraction': describe([r['fraction'] for r in overlaps if r['fold'] != 'ALL'])},
        'K4_nested_in_K3': {'children': int(child_count), 'folds': 23, 'all_nested': True},
        'independent_history_reaggregation': {**counts, 'checks': len(errors), 'max_Q_and_log_time_difference': max(errors)},
        'independent_history_scope_difference': history_scope,
        'refit_from_saved_history': {'partitions': len(aris), 'minimum_ARI': min(aris)},
        'Q_median_baseline': {'ALL_class_sizes': labels[labels.method.eq('Q_MEDIAN2') & labels.heldout_building.eq('ALL')].groupby('class_id').size().to_dict(), 'joint_events': len(focus), 'q_events': len(baseline), 'common_pools': len(backgrounds), 'pools_with_exact_common_D': sum(r['common_D'] > 0 for r in backgrounds), 'by_pool': backgrounds},
        'broad_screen_files_present': {n: n in package_members for n in needed},
        'boundaries': ['No native fusion replay', 'No independent broad-screen event recomputation without missing 05A/05B', 'No raw-polygon recomputation of all structural/geometry histories', 'No new capacity-matched Q-only experiment; current comparison uses own members and no identical backgrounds'],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    print(json.dumps({'status': result['status'], 'output': str(args.output), 'unique_full_fold_partitions': len(signatures), 'max_history_difference': max(errors), 'minimum_refit_ARI': min(aris), 'pools_with_exact_common_D': result['Q_median_baseline']['pools_with_exact_common_D']}, ensure_ascii=False))


if __name__ == '__main__':
    main()
