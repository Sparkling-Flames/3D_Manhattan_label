"""独立检查新增合法空间的设计、实际端点、曲线和分类比较；不融合或拟合。"""
from collections import Counter
import gzip
import json
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.optimize import linear_sum_assignment
from sklearn.metrics import adjusted_rand_score

ROOT = Path(__file__).resolve().parents[3]
RELEASE = ROOT / 'research/data/releases/v2.1'
EXT = RELEASE / 'admitted_space_extension'


def read(path):
    return json.loads(path.read_text(encoding='utf8'))


def same_number(a, b):
    if a is None:
        return pd.isna(b)
    return bool(np.isclose(a, b, rtol=0, atol=1e-10, equal_nan=True))


def main():
    inventory = {r['object_id']: r for r in read(RELEASE/'quality_inventory.json')}
    bindings = {r['object_id']: r for r in read(RELEASE/'reference_bindings.json')}
    additions = read(EXT/'ANALYSIS_RECORDS.json')
    old_ids = {k for k, r in inventory.items() if r['quality_usable']}
    new_ids = {r['object_id'] for r in additions}
    assert len(inventory) == 10439 and len(old_ids) == 8154
    assert len(new_ids) == 231 and not old_ids & new_ids
    for r in additions:
        old = inventory[r['object_id']]; binding = bindings[r['object_id']]
        assert old['quality_exclusion_reasons'] == ['bound_other_admitted_space']
        assert r['reference_id'] == old['reference_id'] == binding['chosen_target_id']
        assert r['reference_id'] in binding['allowed_target_ids']
        assert binding['pool_vote_eligible'] and binding['independent_vote_eligible']
        assert r['B8L2'] == old['diagnostic_B8L2'] and r['D10'] == old['diagnostic_D10']
    pools = read(EXT/'pools/INPUT_SNAPSHOT.json')['images']
    curves = pd.read_csv(EXT/'natural_analysis/UPDATED_CURVES.csv.gz')
    endpoint_status = Counter(); prefix_status = Counter(); sizes = []
    unique_teams = prefixes = 0
    for pool in pools:
        pid = pool['pool_id']; records = {r['worker_id']: r for r in pool['records']}
        assert len(records) == len(pool['records']) >= 3
        assert all(inventory[r['object_id']]['reference_id'] == pool['reference']['target_id'] for r in records.values())
        directory = EXT/'new_space_natural256'/pid
        plan = read(directory/'DESIGN.json'); rng = np.random.default_rng(plan['seed'])
        roster = sorted(records); expected = set()
        assert len(plan['paths']) == 256
        for i, path in enumerate(plan['paths']):
            assert path['path_index'] == i and path['workers'] == rng.permutation(roster).tolist()
            for k in range(1, len(roster)+1):
                expected.add(tuple(sorted(path['workers'][:k])))
        assert expected == {tuple(w) for w in plan['teams']}
        native = {}; by_members = {}
        for part in directory.glob('part_*.jsonl.gz'):
            with gzip.open(part, 'rt', encoding='utf8') as f:
                for line in f:
                    row = json.loads(line); members = tuple(row['member_workers'])
                    assert row['team_key'] not in native and members not in by_members
                    assert members in expected and row['k'] == len(members)
                    assert row['reference_id'] == pool['reference']['target_id']
                    assert row['member_object_ids'] == [records[w]['object_id'] for w in members]
                    native[row['team_key']] = row; by_members[members] = row
                    endpoint_status[row['score_status']] += 1
        assert set(by_members) == expected
        raw = pd.read_csv(EXT/'natural_inputs'/(pid+'.csv.gz'), low_memory=False)
        assert len(raw) == len(roster)*256 and not raw.duplicated(['path_index', 'k']).any()
        for row in raw.itertuples():
            members = tuple(sorted(plan['paths'][row.path_index]['workers'][:row.k]))
            saved = by_members[members]
            assert row.team_key == saved['team_key']
            assert row.member_workers.split('|') == list(members)
            assert row.score_status == saved['score_status']
            assert same_number(saved.get('B8L2'), row.B8L2) and same_number(saved.get('D10'), row.D10)
            prefix_status[row.score_status] += 1
        for row in curves[curves.pool_id.eq(pid)].itertuples():
            q = raw[raw.k.eq(row.k)]
            assert same_number(q.B8L2.mean(), row.Q_mean)
            if row.k != 2:
                assert np.isclose(q.score_status.isin(['no_connection', 'below_four', 'fusion_exception']).mean(), row.actual_consensus_failure_rate)
                assert row.nondeferred_attempts == 256
            else:
                assert row.policy_deferred_paths == 256 and pd.isna(row.actual_consensus_failure_rate)
        full = by_members[tuple(roster)]
        assert full.get('B8L2') is not None
        unique_teams += len(native); prefixes += len(raw); sizes.append(len(roster))
    assert unique_teams == 19976 and prefixes == 59136
    two = pd.read_csv(EXT/'two_person_natural256/PAIRED_PATH_RESULTS.csv.gz')
    assert len(two) == 7936 and two.Q2.notna().sum() == 6599 and two.failure.sum() == 1337
    for pool in pools:
        pid = pool['pool_id']; plan = read(EXT/'new_space_natural256'/pid/'DESIGN.json')
        with gzip.open(EXT/'two_person_natural256/pools'/(pid+'.json.gz'), 'rt', encoding='utf8') as f:
            actual = {tuple(r['member_workers']): r for r in json.load(f)['teams']}
        rows = two[two.pool_id.eq(pid)]
        assert len(rows) == 256
        for r in rows.itertuples():
            index = int(r.path_id.rsplit('_', 1)[1])
            native = actual[tuple(sorted(plan['paths'][index]['workers'][:2]))]
            assert native['reference_id'] == pool['reference']['target_id']
            assert r.team_key == native['team_key'] and r.score_status == native['score_status']
            assert same_number(native.get('B8L2'), r.Q2)

    summary = pd.read_csv(EXT/'classification_impact/FOLD_COMPARISON.csv')
    assert len(summary) == 276
    cache = {}
    for family, rel in [('joint', 'joint_history_classification/ALL_METHOD_LABELS_LOBO.csv.gz'),
                        ('fusion', 'fusion_role_classification/LABELS_ALL_LOBO.csv.gz')]:
        cache[family] = [pd.read_csv(root/rel, low_memory=False) for root in [RELEASE, EXT]]
    for r in summary.itertuples():
        family = 'fusion' if r.method.startswith('RFUSE') else 'joint'
        col = 'class_id' if family == 'fusion' else r.level+'_label'
        pair = []
        for data in cache[family]:
            x = data[data.method.eq(r.method) & data.condition.eq(r.condition) & data.heldout_building.eq(r.heldout_building)]
            assert x.worker_id.is_unique
            pair.append(x[x.known.eq(True)].set_index('worker_id')[col])
        old, new = pair; ids = old.index.intersection(new.index)
        assert len(ids) == r.common_known
        assert len(new.index.difference(old.index)) == r.gained_known
        assert len(old.index.difference(new.index)) == r.lost_known
        a, b = old.loc[ids], new.loc[ids]
        counts = pd.crosstab(a, b); i, j = linear_sum_assignment(-counts.to_numpy())
        assert len(ids)-int(counts.to_numpy()[i, j].sum()) == r.changed_after_alignment
        assert np.isclose(adjusted_rand_score(a, b), r.ari)

    grades = {r['image_id']: r for r in read(RELEASE/'difficulty_records.json')['records']}
    evidence = []
    for pool in pools:
        meta = pool['meta']; r = grades[meta['image_id']]; old = r.get('external_review') or {}
        evidence.append(dict(pool_id=pool['pool_id'], image=meta['image'], condition=meta['condition'],
            target_id=pool['reference']['target_id'], current_target_grade=r['current_class'],
            historical_review_target=old.get('gt_object_id'), historical_review_grade=old.get('grade'),
            historical_review_scope=old.get('scope'), exact_target_match=old.get('gt_object_id') == pool['reference']['target_id'],
            adoption='historical_evidence_only_not_automatically_adopted'))
    pd.DataFrame(evidence).to_csv(RELEASE/'EXTENDED_TARGET_DIFFICULTY_EVIDENCE_20261029.csv', index=False, encoding='utf-8-sig')
    result = dict(raw_annotations=len(inventory), original_quality=len(old_ids), extension_quality=len(new_ids),
        combined_quality=len(old_ids|new_ids), extension_pools=len(pools), order_replays=len(pools)*256,
        unique_natural_endpoint_records=unique_teams, natural_prefix_occurrences=prefixes,
        endpoint_status=dict(endpoint_status), prefix_status=dict(prefix_status),
        pool_capacity_min=min(sizes), pool_capacity_max=max(sizes), full_pool_Q_available=len(pools),
        actual_k2_paths=len(two), actual_k2_scoreable=int(two.Q2.notna().sum()), actual_k2_failed=int(two.failure.sum()),
        classification_comparison_cells=len(summary), exact_target_historical_grade_matches=sum(e['exact_target_match'] for e in evidence),
        new_scoring=0, new_fusion=0, new_classification=0, browser_checked=False)
    (RELEASE/'FULL_DELIVERY_INDEPENDENT_CHECKS_20261029.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf8')
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
