#!/usr/bin/env python3
"""Target-specific structure conditions for HOHONET v2.1.

Never modifies target assignment, grade, reference, eligibility or scoring.
Frozen geometry features are extracted verbatim from repository methods.
All output identifiers retain image, condition and exact target binding.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
from shapely.geometry import Polygon

from frozen_geometry_traits import floor_features, reference_traits, visibility_from_floor

COMMIT = 'a476461d7ede8db95da43de4139e612c05e618bc'
RELEASE = Path('research/data/releases/v2.1')
FILES = {
    'main': RELEASE / 'pools/INPUT_SNAPSHOT.json',
    'other': RELEASE / 'admitted_space_extension/pools/INPUT_SNAPSHOT.json',
    'evidence': RELEASE / 'admitted_space_extension/difficulty_evidence/POOL_EVIDENCE.csv',
    'review': RELEASE / 'admitted_space_extension/difficulty_evidence/MINIMAL_TARGET_REVIEW.csv',
}
GRADES = {'简单', '中等', '困难'}


def hierarchical_history_weights(df: pd.DataFrame) -> pd.DataFrame:
    """Recompute after each LOBO/support filter; never reuse ALL denominators.

    Within a worker/condition, equal buildings; within building equal images;
    within image equal annotated targets; within target equal records.
    Thus annotating another legal space does not give an image extra influence.
    This function intentionally leaves condition separate.
    """
    z = df.copy()
    worker = ['worker', 'condition']
    image = worker + ['building', 'image_id']
    target = image + ['reference_id']
    z['records_in_worker_target'] = z.groupby(target)['record_id'].transform('size')
    z['targets_in_worker_image'] = z.groupby(image)['reference_id'].transform('nunique')
    z['images_in_worker_building'] = z.groupby(worker + ['building'])['image_id'].transform('nunique')
    z['buildings_in_worker_history'] = z.groupby(worker)['building'].transform('nunique')
    z['weight_record_within_target'] = 1 / z['records_in_worker_target']
    z['weight_target_within_image'] = 1 / z['targets_in_worker_image']
    z['weight_image_within_building'] = 1 / z['images_in_worker_building']
    z['weight_building_within_history'] = 1 / z['buildings_in_worker_history']
    z['history_weight_on_this_support'] = (
        z['weight_record_within_target'] * z['weight_target_within_image']
        * z['weight_image_within_building'] * z['weight_building_within_history']
    )
    return z


def target_traits(ref: dict) -> dict:
    p = np.asarray(ref['floor_xz_h'], dtype=float)
    result = reference_traits(p)
    if result['ref_geometry_status'] in {'unavailable', 'zero_length_edge'}:
        return {**result, 'geometric_challenge': None, 'structural_condition': 'unknown_geometry'}
    geom = floor_features(p)
    visibility = visibility_from_floor(p)
    edges = np.roll(p, -1, axis=0) - p
    lengths = np.linalg.norm(edges, axis=1)
    turn = np.degrees(np.arccos(np.clip(
        (edges * np.roll(edges, 1, axis=0)).sum(axis=1)
        / (lengths * np.roll(lengths, 1)), -1, 1)))
    short = (lengths / lengths.sum() < .04) & (turn >= 15) & (np.roll(turn, -1) >= 15)
    az = np.degrees(np.arctan2(p[:, 0], p[:, 1]))
    span = np.abs((np.roll(az, -1) - az + 180) % 360 - 180)
    poly = Polygon(p)
    result.update({
        'ref_floor_area_h2': float(poly.area),
        'ref_perimeter_h': float(poly.length),
        'ref_compactness_4pi_area_over_perimeter2': float(4 * np.pi * poly.area / poly.length ** 2),
        'ref_min_edge_perimeter_fraction': float(lengths.min() / lengths.sum()),
        'ref_short_total_horizontal_deg': float(span[short].sum()),
        'ref_redundant_or_near_straight5': int(len(p) - (turn > 5).sum()),
        'ref_hidden_vertices_1based': json.dumps(geom['hidden_vertices_1based']),
        'ref_grazing_vertices_1based': json.dumps(visibility.get('grazing_vertices_1based')),
        'ref_short_edges_1based': json.dumps((np.flatnonzero(short) + 1).tolist()),
        'ref_nonredundant_turns5_1based': json.dumps((np.flatnonzero(turn > 5) + 1).tolist()),
        'ref_ring_class': geom['ring_class'],
    })
    points = np.asarray(ref.get('points_1024x512', []), dtype=float)
    if len(points) == 2 * len(p):
        height = 1 + np.linalg.norm(p, axis=1) * np.tan((.5 - points[0::2, 1] / 512) * np.pi)
        result['ref_height_h_median'] = float(np.median(height))
        result['ref_height_h_vertex_range'] = float(np.ptp(height))
    if geom['H'] is None:
        result.update(geometric_challenge=None, structural_condition='unknown_boundary_visibility')
    else:
        result['geometric_challenge'] = bool(result['ref_turn5'] > 6 or geom['H'] > 0 or short.any())
        result['structural_condition'] = (
            'boundary_self_occlusion' if geom['H'] > 0 else
            'short_turns_without_boundary_occlusion' if short.any() else
            'no_short_turns_or_boundary_occlusion'
        )
        result['ref_hidden_fraction'] = float(geom['H'] / len(p))
    return result


def truth(v) -> bool:
    return str(v).strip().lower() in {'true', '1'}


def evidence_status(e: dict | None, official_grade: str | None) -> tuple[str, str | None, str | None]:
    if official_grade:
        return 'official_target_aligned', None, None
    if not e:
        return 'ungraded_no_target_evidence_in_extension_table', None, None
    if truth(e.get('external_exact_target')) and e.get('external_grade') in GRADES:
        return 'historical_external_exact_target_not_final', e['external_grade'], 'external_review_20261010'
    if e.get('assistant_grade') in GRADES and e.get('status') != '确实缺对应难度':
        return 'historical_assistant_exact_target_not_final', e['assistant_grade'], 'codex_visual_review'
    return 'no_exact_target_grade', None, None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--repo', type=Path, required=True)
    ap.add_argument('--fallback-source', type=Path)
    ap.add_argument('--out', type=Path, required=True)
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    resolved = {}
    for key, path in FILES.items():
        q = args.repo / path
        if not q.exists() and args.fallback_source:
            q = args.fallback_source / path
        if not q.exists():
            raise FileNotFoundError(path)
        resolved[key] = q
    ev = pd.read_csv(resolved['evidence'], keep_default_na=False)
    review = pd.read_csv(resolved['review'], keep_default_na=False)
    evidence = ev.set_index('pool_id').to_dict('index')
    pools = []
    for key in ('main', 'other'):
        data = json.loads(resolved[key].read_text())
        for pool in data['images']:
            pools.append((key, pool))
    assert sum(k == 'main' for k, _ in pools) == 263
    assert sum(k == 'other' for k, _ in pools) == 31
    rows, records, target_cache = [], [], {}
    for scope, pool in pools:
        m, ref = pool['meta'], pool['reference']
        assert m['reference_id'] == ref['target_id']
        key = (ref['target_id'], ref['reference_version'])
        ref_hash = hashlib.sha256(json.dumps(ref, sort_keys=True).encode()).hexdigest()
        if key not in target_cache:
            target_cache[key] = (ref_hash, target_traits(ref))
        else:
            assert target_cache[key][0] == ref_hash, key
        official = m['difficulty'] if m['difficulty_aligned'] and m['difficulty'] in GRADES else None
        e = evidence.get(m['pool_id'])
        status, prior_grade, prior_source = evidence_status(e, official)
        r = dict(m)
        r.update({
            'scope': 'primary' if scope == 'main' else 'other_admitted',
            'official_difficulty': official,
            'difficulty_evidence_status': status,
            'historical_target_grade_for_sensitivity_only': prior_grade,
            'historical_target_grade_source': prior_source,
            'official_difficulty_inherited_from_other_space': False,
            'reference_sha256': ref_hash,
            **target_cache[key][1],
        })
        rows.append(r)
        for a in pool['records']:
            records.append({
                'record_id': a['object_id'], 'worker': a['worker'],
                'image': m['image'], 'image_id': m['image_id'],
                'building': m['building'], 'condition': m['condition'],
                'pool_id': m['pool_id'], 'reference_id': m['reference_id'],
                'reference_version': m['reference_version'],
                'scope': r['scope'], 'layer': m['layer'], 'scene': m['scene'],
                'official_difficulty': official,
                'geometric_challenge': r['geometric_challenge'],
                'structural_condition': r['structural_condition'],
                'source_time_seconds': a['source_time_seconds'],
                'target_time_seconds': a['target_time_seconds'],
                'time_source_kind': a['time_source_kind'], 'origin': a['origin'],
                'B8L2': a['B8L2'], 'D10': a['D10'],
            })
    table = pd.DataFrame(rows)
    assert table.pool_id.is_unique
    table['legal_targets_in_image_condition'] = table.groupby(['image_id', 'condition'])['reference_id'].transform('nunique')
    table['evaluation_target_weight_within_image'] = 1 / table['legal_targets_in_image_condition']
    table.to_csv(args.out / 'POOL_TARGET_CONDITIONS.csv', index=False)
    desc = ['image', 'image_id', 'building', 'reference_id', 'reference_version', 'scope',
            'official_difficulty', 'difficulty_evidence_status',
            'historical_target_grade_for_sensitivity_only', 'historical_target_grade_source',
            'reference_sha256', 'geometric_challenge', 'structural_condition']
    desc += [c for c in table if c.startswith('ref_')]
    targets = table[desc].drop_duplicates(['image_id', 'reference_id', 'reference_version'])
    targets.to_csv(args.out / 'TARGET_STRUCTURAL_FEATURES.csv', index=False)
    other = table[table.scope == 'other_admitted'].copy().merge(ev, on='pool_id', how='left', suffixes=('', '_historical'))
    primary = table[table.scope == 'primary'].drop_duplicates(['image_id', 'condition'])
    reference_fields = ['official_difficulty', 'reference_id', 'ref_turn5', 'ref_H', 'ref_short_edges', 'geometric_challenge', 'ref_floor_area_h2', 'ref_height_h_median']
    primary = primary[['image_id', 'condition'] + reference_fields].rename(columns={c: 'primary_space_' + c for c in reference_fields})
    other = other.merge(primary, on=['image_id', 'condition'], how='left', validate='many_to_one')
    for c in ['ref_turn5', 'ref_H', 'ref_short_edges', 'ref_floor_area_h2', 'ref_height_h_median']:
        other['other_minus_primary_' + c] = other[c] - other['primary_space_' + c]
    other.to_csv(args.out / 'OTHER_TARGETS_EVIDENCE_AND_CONDITIONS.csv', index=False)
    weights = hierarchical_history_weights(pd.DataFrame(records))
    assert len(weights) == 8385
    assert weights.record_id.is_unique
    weight_sums = weights.groupby(['worker', 'condition']).history_weight_on_this_support.sum()
    assert np.allclose(weight_sums, 1)
    weights.to_csv(args.out / 'RECORD_TARGET_LINKS_AND_ALL_SUPPORT_WEIGHTS.csv.gz', index=False)
    missing = other[other.difficulty_evidence_status == 'no_exact_target_grade'].drop_duplicates('reference_id')
    missing[['image', 'reference_id', 'pool_n', 'ref_turn5', 'ref_H', 'ref_short_edges',
             'geometric_challenge', 'reason']].to_csv(args.out / 'OPTIONAL_EXACT_TARGET_GRADE_QUESTIONS.csv', index=False)
    summary = table.groupby(['scope', 'condition', 'layer', 'structural_condition'], dropna=False).agg(
        pools=('pool_id', 'size'), images=('image_id', 'nunique'), buildings=('building', 'nunique'),
        records=('pool_n', 'sum'), mean_turn5=('ref_turn5', 'mean'), mean_H=('ref_H', 'mean'),
        mean_short_edges=('ref_short_edges', 'mean')).reset_index()
    summary.to_csv(args.out / 'TARGET_CONDITION_SUPPORT.csv', index=False)
    # One exact recomputation check on already available main-target traits.
    comparison = args.repo / RELEASE / 'condition_classification/RAW_CONDITION_RESPONSE_RECORDS.csv.gz'
    check = {'existing_trait_comparison_available': comparison.exists()}
    if comparison.exists():
        raw = pd.read_csv(comparison)
        old = raw.drop_duplicates('pool_id').set_index('pool_id')
        new = table.set_index('pool_id')
        common = old.index.intersection(new.index)
        check['existing_trait_common_pools'] = len(common)
        for c in ['ref_turn5', 'ref_H', 'ref_short_edges', 'ref_min_horizontal_deg']:
            if c in old:
                delta = (pd.to_numeric(old.loc[common, c], errors='coerce') - pd.to_numeric(new.loc[common, c], errors='coerce')).abs()
                check[c + '_max_abs_difference'] = None if delta.isna().all() else float(delta.max())
                assert delta.dropna().max() <= 1e-9, c
    facts = {
        'commit': COMMIT, 'data_release': 'v2.1',
        'pools': len(table), 'records': len(weights), 'unique_targets': len(targets),
        'images': int(table.image_id.nunique()), 'buildings': int(table.building.nunique()),
        'main_records': int(table.loc[table.scope == 'primary', 'pool_n'].sum()),
        'other_records': int(table.loc[table.scope == 'other_admitted', 'pool_n'].sum()),
        'all_pool_geometry_status': table.ref_geometry_status.value_counts().to_dict(),
        'other_target_grade_status': other.drop_duplicates('reference_id').difficulty_evidence_status.value_counts().to_dict(),
        'other_geometry_challenge_pools': int(other.geometric_challenge.eq(True).sum()),
        'other_plain_pools': int(other.geometric_challenge.eq(False).sum()),
        'other_challenge_differs_from_primary_pools': int((other.geometric_challenge != other.primary_space_geometric_challenge).sum()),
        'optional_missing_exact_grade_targets': len(missing),
        'worker_image_condition_with_multiple_annotated_targets': int(weights.groupby(['worker', 'image_id', 'condition']).reference_id.nunique().gt(1).sum()),
        'number_of_multi_target_image_condition_pairs': int(table.groupby(['image_id', 'condition']).reference_id.nunique().gt(1).sum()),
        'weights_sum_to_one_per_worker_condition': bool(np.allclose(weight_sums, 1)),
        'source_time_known_records': int(weights.source_time_seconds.notna().sum()),
        'target_time_known_records': int(weights.target_time_seconds.notna().sum()),
        'checks': check,
        'no_change_to': ['GT', 'official_difficulty', 'space_assignment', 'eligibility', 'quality_contract', 'fusion_contract'],
    }
    (args.out / 'CHECKS_AND_SUPPORT.json').write_text(json.dumps(facts, ensure_ascii=False, indent=2) + '\n')
    manifest = [{'repository_path': str(FILES[k]), 'sha256': hashlib.sha256(p.read_bytes()).hexdigest(),
                 'bytes': p.stat().st_size, 'commit': COMMIT} for k, p in resolved.items()]
    (args.out / 'INPUT_MANIFEST.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(facts, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
