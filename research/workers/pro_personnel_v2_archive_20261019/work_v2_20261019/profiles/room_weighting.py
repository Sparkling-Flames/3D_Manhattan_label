#!/usr/bin/env python3
"""Reuse exact original declared room groups without inventing room identity.

Only group_kind=original and classification.physical_same=支持 are eligible.
Groups may overlap. This is a descriptive weighting sensitivity, not a set of
independent physical rooms. Bootstrap inference must retain building clusters.
"""
import argparse
import gzip
import hashlib
import json
from pathlib import Path

import pandas as pd

SOURCE = 'research/statistics/v2_integrated_analysis_20261019/tables.json.gz'


def original_supported_groups(repo):
    with gzip.open(Path(repo) / SOURCE, 'rt') as f:
        registry = json.load(f)['tables']['statistics__room_registry']
    return [r for r in registry
            if r.get('group_kind') == 'original'
            and r.get('classification', {}).get('physical_same') == '支持']


def membership_table(groups):
    rows = []
    for g in groups:
        for image_id in g['image_ids']:
            rows.append(dict(
                group_id=g['group_id'], image_id=image_id,
                group_kind=g['group_kind'], physical_same='支持',
                n_declared_views=g.get('n_declared_views'),
                n_inventory_views=g.get('n_inventory_views'),
                identity_basis=g.get('identity_basis'),
                classification_status=g.get('classification', {}).get('status'),
                classification_note=g.get('classification', {}).get('note')))
    result = pd.DataFrame(rows)
    if result.duplicated(['group_id', 'image_id']).any():
        raise ValueError('The authoritative registry contains repeated membership; inspect explicitly.')
    return result


def aggregate_declared_groups(per_image, groups_or_memberships, values,
                              strata=(), image_col='image_id',
                              building_col='building_id'):
    """Average images within each declared group, retaining coverage.

    per_image must already have ONE row per image and comparison stratum, and
    comparable models/strategies must first be matched on the exact eligible
    images/workers by the caller. This function does not silently rematch them.
    Returns (per_group, coverage). Average each per_group value across groups
    for group-equal sensitivity. Never bootstrap these groups as independent N.
    Missing images are omitted only from that group's observed mean and are
    explicitly counted; they are never synthesized as singleton rooms.
    """
    memberships = (groups_or_memberships.copy()
                   if isinstance(groups_or_memberships, pd.DataFrame)
                   else membership_table(groups_or_memberships))
    strata = list(strata)
    if per_image.duplicated([*strata, image_col]).any():
        raise ValueError('Aggregate repeated rows to one image per stratum before room weighting.')
    needed = [*strata, image_col, building_col, *values]
    m = memberships[['group_id', 'image_id', 'n_declared_views']].merge(
        per_image[needed], left_on='image_id', right_on=image_col, how='inner')
    rows = []
    grouper = [*strata, 'group_id']
    for keys, g in m.groupby(grouper, dropna=False):
        if not isinstance(keys, tuple):
            keys = (keys,)
        row = dict(zip(grouper, keys))
        row.update(observed_images=g.image_id.nunique(),
                   declared_images=int(g.n_declared_views.iloc[0]),
                   building_id=';'.join(sorted(g[building_col].dropna().astype(str).unique())))
        row['missing_declared_images'] = row['declared_images'] - row['observed_images']
        for value in values:
            row[value] = g[value].mean()
            row[value + '_observed_images'] = int(g[value].notna().sum())
        rows.append(row)
    coverage = dict(
        registered_groups=int(memberships.group_id.nunique()),
        declared_memberships=len(memberships),
        distinct_declared_images=int(memberships.image_id.nunique()),
        images_declared_in_multiple_groups=int(memberships.groupby('image_id').group_id.nunique().gt(1).sum()),
        input_images=int(per_image[image_col].nunique()),
        linked_input_images=int(per_image[image_col].isin(memberships.image_id).groupby(per_image[image_col]).max().sum()),
        unlinked_input_image_ids=sorted(set(per_image[image_col]) - set(memberships.image_id)),
        evaluable_groups=int(m.group_id.nunique()),
        overlapping_groups_are_not_independent_physical_rooms=True,
        no_transitive_closure_or_building_room_inference=True,
        inference_unit='building, never declared group')
    return pd.DataFrame(rows), coverage


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--repo', type=Path, default=Path('repo_main_20261019'))
    p.add_argument('--out', type=Path, default=Path('work_v2_20261019/profiles'))
    a = p.parse_args()
    groups = original_supported_groups(a.repo)
    memberships = membership_table(groups)
    a.out.mkdir(parents=True, exist_ok=True)
    memberships.to_csv(a.out / 'declared_room_groups.csv', index=False)
    metadata = dict(source=SOURCE, source_sha256=hashlib.sha256((a.repo/SOURCE).read_bytes()).hexdigest(),
                    source_commit='82c6164b0d4630de5316199c92aa405930973168',
                    filter="group_kind == 'original' and classification.physical_same == '支持'",
                    registered_groups=len(groups), memberships=len(memberships),
                    distinct_declared_images=int(memberships.image_id.nunique()),
                    images_declared_in_multiple_groups=int(memberships.groupby('image_id').group_id.nunique().gt(1).sum()),
                    overlapping_groups_are_not_independent_physical_rooms=True,
                    inference_unit='building, not group',
                    no_transitive_closure=True, no_invented_singletons=True)
    (a.out / 'DECLARED_ROOM_GROUPS.json').write_text(json.dumps(metadata, ensure_ascii=False, indent=2))
    print(json.dumps(metadata, ensure_ascii=False))


if __name__ == '__main__':
    main()
