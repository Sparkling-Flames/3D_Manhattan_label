"""Compare saved original and extension labels; never fit models or create teams."""
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import linear_sum_assignment
from sklearn.metrics import adjusted_rand_score

ROOT = Path(__file__).resolve().parents[3]
RELEASE = ROOT / 'research/data/releases/v2.1'
EXT = RELEASE / 'admitted_space_extension'
OUT = EXT / 'classification_impact'
KEY = ['condition', 'method', 'heldout_building', 'level', 'worker_id']
SUPPORT = ['n_records', 'n_images', 'n_buildings', 'n_quality_usable', 'q_images', 'q_buildings',
           't_images', 't_buildings', 'all_images', 'all_buildings', 'hard_images', 'hard_buildings',
           'easy_images', 'easy_buildings']


def align_labels(old, new):
    """Maximum agreement alignment on common known people, plus ambiguity indicator."""
    if len(old) == 0:
        return {}, False
    table = pd.crosstab(pd.Series(new, name='new'), pd.Series(old, name='old'))
    counts = table.to_numpy(dtype=int)
    rows, cols = linear_sum_assignment(-counts)
    best = int(counts[rows, cols].sum())
    mapping = {str(table.index[i]): str(table.columns[j]) for i, j in zip(rows, cols) if counts[i, j] > 0}
    ambiguous = False
    for i, j in zip(rows, cols):
        if counts[i, j] == 0:
            continue
        altered = counts.copy()
        altered[i, j] = -int(counts.sum()) - 1
        rr, cc = linear_sum_assignment(-altered)
        if altered[rr, cc].sum() == best:
            ambiguous = True
            break
    return mapping, ambiguous


def normalize(frame, source):
    required = {'worker_id', 'condition', 'method', 'heldout_building', 'known'}
    required |= {'coarse_label', 'fine_label'} if source == 'joint' else {'class_id'}
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f'{source} missing required fields: {sorted(missing)}')
    if frame[list(required - {'coarse_label', 'fine_label', 'class_id'})].isna().any().any():
        raise ValueError(f'{source} missing identity or known value')
    if not frame.known.isin([True, False]).all():
        raise ValueError(f'{source} known must be boolean')
    levels = [('coarse', 'coarse_label'), ('fine', 'fine_label')] if source == 'joint' else [('class', 'class_id')]
    result = []
    for level, label in levels:
        x = frame[[c for c in (['worker_id', 'condition', 'method', 'heldout_building', 'known', label] + SUPPORT) if c in frame]].copy()
        x = x.rename(columns={label: 'label'})
        x['level'] = level
        if x.loc[x.known, 'label'].isna().any():
            raise ValueError(f'{source}/{level} known label missing')
        x.loc[~x.known, 'label'] = pd.NA
        result.append(x)
    out = pd.concat(result, ignore_index=True)
    if out.duplicated(KEY).any():
        raise ValueError(f'{source} duplicate worker/method/condition/fold/level')
    return out


def compare(old, new):
    joined = old.merge(new, on=KEY, how='outer', suffixes=('_old', '_extended'), validate='one_to_one', indicator=True)
    output, details = [], []
    group_keys = KEY[:-1]
    for ident, g in joined.groupby(group_keys, dropna=False, sort=True):
        before = g.known_old.eq(True)
        after = g.known_extended.eq(True)
        common = before & after
        pair = g.loc[common]
        mapping, ambiguous = align_labels(pair.label_old.tolist(), pair.label_extended.tolist())
        aligned = g.label_extended.map(mapping)
        raw_same = common & g.label_old.fillna('').eq(g.label_extended.fillna(''))
        aligned_same = common & g.label_old.fillna('').eq(aligned.fillna(''))
        counts = dict(zip(group_keys, ident))
        counts.update(roster_old=int(g.known_old.notna().sum()), roster_extended=int(g.known_extended.notna().sum()),
            known_old=int(before.sum()), known_extended=int(after.sum()), common_known=int(common.sum()),
            gained_known=int((~before & after).sum()), lost_known=int((before & ~after).sum()),
            same_raw_id=int(raw_same.sum()), changed_raw_id=int((common & ~raw_same).sum()),
            same_after_alignment=int(aligned_same.sum()), changed_after_alignment=int((common & ~aligned_same).sum()),
            ari=float(adjusted_rand_score(pair.label_old, pair.label_extended)) if len(pair) >= 2 else None,
            mapping_new_to_old=json.dumps(mapping, ensure_ascii=False, sort_keys=True), mapping_ambiguous=ambiguous)
        for field in SUPPORT:
            col_old, col_new = field + '_old', field + '_extended'
            if col_old in g and col_new in g:
                values_old = pd.to_numeric(g[col_old], errors='raise')
                values_new = pd.to_numeric(g[col_new], errors='raise')
                paired = values_old.notna() & values_new.notna()
                counts[field + '_paired_people'] = int(paired.sum())
                counts[field + '_old_sum_paired'] = float(values_old[paired].sum()) if paired.any() else None
                counts[field + '_extended_sum_paired'] = float(values_new[paired].sum()) if paired.any() else None
                counts[field + '_delta_sum_paired'] = float((values_new[paired] - values_old[paired]).sum()) if paired.any() else None
        g = g.copy()
        g['aligned_extended_label'] = aligned
        g['raw_id_changed'] = (common & ~raw_same).where(common)
        g['partition_changed_after_alignment'] = (common & ~aligned_same).where(common)
        g['mapping_ambiguous'] = ambiguous
        g['support_state'] = np.select([common, ~before & after, before & ~after],
            ['common_known', 'gained_known', 'lost_known'], default='unknown_both')
        output.append(counts)
        details.append(g)
    return pd.DataFrame(output), pd.concat(details, ignore_index=True)


def build():
    frames = []
    for source, name in [('joint_history_classification', 'ALL_METHOD_LABELS_LOBO.csv.gz'),
                         ('fusion_role_classification', 'LABELS_ALL_LOBO.csv.gz')]:
        old_path, new_path = RELEASE / source / name, EXT / source / name
        if not new_path.is_file():
            raise FileNotFoundError(f'Extension classification not yet available: {new_path}')
        old, new = (pd.read_csv(p, low_memory=False) for p in (old_path, new_path))
        kind = 'joint' if source.startswith('joint') else 'fusion'
        before, after = normalize(old, kind), normalize(new, kind)
        if set(map(tuple, before[KEY[:-1]].drop_duplicates().to_numpy())) != set(map(tuple, after[KEY[:-1]].drop_duplicates().to_numpy())):
            raise ValueError(f'{source}: method/condition/fold/level grid differs; inspect before comparison')
        frames.append((before, after))
    old = pd.concat([x[0] for x in frames], ignore_index=True)
    new = pd.concat([x[1] for x in frames], ignore_index=True)
    summary, people = compare(old, new)
    OUT.mkdir(parents=True, exist_ok=True)
    summary.to_csv(OUT / 'FOLD_COMPARISON.csv', index=False, encoding='utf-8-sig')
    people.to_csv(OUT / 'PERSON_FOLD_COMPARISON.csv.gz', index=False, encoding='utf-8-sig')
    people[people.heldout_building.eq('ALL')].to_csv(OUT / 'ALL_PERSON_COMPARISON.csv', index=False, encoding='utf-8-sig')
    checks = dict(old_rows=len(old), extended_rows=len(new), fold_groups=len(summary),
                  all_people_rows=int(people.heldout_building.eq('ALL').sum()),
                  aligned_on='common known people within method/condition/fold/level',
                  original_inputs_unchanged=True, classification_fit=False, fusion_run=False)
    (OUT / 'CHECKS.json').write_text(json.dumps(checks, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
    print(json.dumps(checks, ensure_ascii=False))


if __name__ == '__main__':
    build()
