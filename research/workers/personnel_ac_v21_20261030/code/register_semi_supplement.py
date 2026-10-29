"""Small outcome-blind Semi supplement using its existing own frozen labels.

Complete class coalitions and whole-small-class equal replacement are registered.
This never applies Manual labels to Semi and never reads image Q/time/geometry.
"""
from __future__ import annotations
import hashlib, itertools, json, math, shutil, sys, gzip
from collections import Counter
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT.parent
sys.path.insert(0, str(ROOT / 'stage01_design_review/code'))
from register_ac_population import Registry, sample_xz, background_paths, digest, save


def csv(rows, path):
    data = pd.DataFrame(rows).to_csv(index=False).encode('utf-8-sig')
    data = gzip.compress(data, compresslevel=5, mtime=0) if str(path).endswith('.gz') else data
    tmp = path.with_name(path.name + '.partial')
    tmp.write_bytes(data)
    tmp.replace(path)


def main():
    out = ROOT / 'stage01b_semi'
    out.mkdir(exist_ok=False)
    label_path = WORK / 'repo/research/workers/personnel_v21_reselection_20261029/classification/SEMI_BASE_LABELS_ALL_LOBO.csv.gz'
    labels = pd.read_csv(label_path, low_memory=False)
    shutil.copy2(label_path, out / label_path.name)
    pools = {}
    for scope, rel in [('primary', 'pools'), ('other_admitted', 'admitted_space_extension/pools')]:
        path = WORK / 'repo/research/data/releases/v2.1' / rel / 'INPUT_SNAPSHOT.json'
        for p in json.loads(path.read_text())['images']:
            if p['meta']['condition'] != 'semi' or p['meta']['layer'] != 'ordinary_semi':
                continue
            pools[p['pool_id']] = {'pool_id': p['pool_id'], 'scope': scope,
                'meta': {k: p['meta'][k] for k in ['image', 'building', 'condition', 'layer', 'reference_id', 'reference_version']},
                'workers': sorted(r['worker_id'] for r in p['records']),
                'members': [{'worker_id': r['worker_id'], 'object_id': r['object_id']} for r in p['records']]}
    save({'pools': list(pools.values()), 'target_scores_read': False}, out / 'SCORE_BLIND_SEMI_POOL_INPUTS.json')
    reg = Registry(pools, None, {})
    capacity = []
    for pid, pool in sorted(pools.items()):
        N = len(pool['workers'])
        for method, d in labels[labels.heldout_building == pool['meta']['building']].groupby('method'):
            lookup = dict(zip(d.loc[d.known.astype(bool), 'worker_id'], d.loc[d.known.astype(bool), 'class_id']))
            groups = {}
            for w in pool['workers']:
                if w in lookup:
                    groups.setdefault(lookup[w], []).append(w)
            U = sorted(set(pool['workers']) - set(w for ws in groups.values() for w in ws))
            classes = sorted(groups)
            capacity.append({'pool_id': pid, 'method': method, 'scope': pool['scope'], 'N': N,
                             'class_members_json': json.dumps(groups, sort_keys=True), 'unknown_workers': '|'.join(U)})
            # Complete class unions, with unknown members either absent or fixed.
            for unknown in ([[], U] if U else [[]]):
                alliances = []
                for k in range(1, len(classes) + 1):
                    for cs in itertools.combinations(classes, k):
                        ws = sorted(unknown + [w for c in cs for w in groups[c]])
                        if len(ws) >= 3:
                            alliances.append((cs, ws))
                for (ca, A), (cc, C) in itertools.combinations(alliances, 2):
                    reg.event(pool, method, groups, A, C, 'S_complete_class_coalition',
                              input_A_classes='|'.join(ca), input_C_classes='|'.join(cc),
                              unknown_background='|'.join(unknown))
            for s, t in itertools.combinations(classes, 2):
                S, T = groups[s], groups[t]
                m = min(len(S), len(T))
                blocks, total = sample_xz(S, T, m, ['semi', pid, method, s, t], 4, 16)
                ns = sorted({m, 2*m, N-m})
                for n in ns:
                    if n < max(3, m) or n > N-m:
                        continue
                    for rep, (x, z, batch, attempt) in enumerate(blocks):
                        remaining = sorted(set(pool['workers']) - set(x) - set(z))
                        paths = background_paths(remaining, lookup, s, t, ['semi', pid, x, z])
                        seen = set()
                        for profile in ['neutral_members_0', 'neutral_members_1']:
                            D = sorted(paths[profile][:n-m])
                            if tuple(D) in seen:
                                continue
                            seen.add(tuple(D))
                            reg.event(pool, method, groups, D+x, D+z, 'S_equal_whole_class',
                                      n=n, m=m, member_rep=rep, sample_batch=batch,
                                      background_profile=profile, block_id=digest([pid, x, z])[:24],
                                      at_pool_frontier=n == N-m, zero_background=n == m,
                                      possible_XZ_blocks=str(total))
    csv(capacity, out / 'SEMI_POOL_CLASS_CAPACITY.csv.gz')
    reg.finish(out)
    receipt = {'source_commit': 'ec0973ad46fcfa64d3cdbedfeeef1fee180c4cff',
               'label_git_blob_at_current_and_previous_commit': '8475184f89a0e74dc4dbd18a65c3728f3b2b9955',
               'label_sha256': hashlib.sha256(label_path.read_bytes()).hexdigest(),
               'methods': sorted(labels.method.unique().tolist()), 'pools_available': len(pools),
               'registered_pools': len(reg.event_pools), 'events': len(reg.events),
               'teams': len(reg.teams), 'design_links': reg.link_n,
               'family_links': dict(reg.counts), 'manual_labels_applied_to_semi': False,
               'target_Q_time_geometry_used_for_selection': False, 'new_fusions': 0,
               'role_direction': 'lexical existing class IDs, not a quality ranking',
               'seed': 202610291901, 'block_draws': 4, 'enumeration_limit': 16,
               'interpretation': 'Secondary existing Semi population; own frozen V3 labels; separate from ordinary Manual.'}
    save(receipt, out / 'DESIGN_REGISTRATION_RECEIPT.json')
    validated = {}
    for path in sorted(out.glob('*.gz')):
        content = gzip.decompress(path.read_bytes())
        validated[path.name] = {'bytes_read': len(content), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
    save({'passed': True, 'files': validated}, out / 'READABILITY_RECEIPT.json')
    print(json.dumps(receipt, ensure_ascii=False))


if __name__ == '__main__':
    main()
