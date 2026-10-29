#!/usr/bin/env python3
"""Reuse the exact finite composition panels with current v2.1 references.

Only reads saved endpoints. Changed-reference fields are replaced from existing
composition_rescore records; missing current diagnostics are not filled by old GT.
No class fitting, fusion or scoring is performed.
"""
from __future__ import annotations
import argparse
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

SOURCE = Path('research/workers/personnel_mixture_comparison_20261022/configurations')
RELEASE = Path('research/data/releases/v2.1')
REFERENCE_FIELDS = [
    'B8L2', 'D10', 'iou_2d', 'IoU3D100', 'S_bottom_deg', 'Hmean', 'Hcenter',
    'omission', 'extension', 'height_mean_ratio', 'ref_node_recall_5',
    'ref_node_recall_9', 'ref_edge_recall_5', 'ref_edge_recall_9',
    'diag_corner_recall_05', 'diag_wall_coverage_03', 'diag_wall_coverage_05',
]


def save_csv(path, frame):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.writing')
    compression = {'method':'gzip', 'mtime':0} if path.name.endswith('.gz') else None
    frame.to_csv(tmp, index=False, compression=compression)
    tmp.replace(path)


def as_bool(s):
    if s.dtype == bool:
        return s
    return s.fillna(False).astype(str).str.lower().isin(['true', '1', '1.0'])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--repo', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--conditions', default='manual')
    ap.add_argument('--target-conditions', type=Path, required=True)
    args = ap.parse_args(); args.out.mkdir(parents=True, exist_ok=True)
    conditions = set(args.conditions.split(','))
    origin = args.repo / SOURCE
    panels = pd.read_csv(origin/'PANELS_USED.csv')
    panels = panels[panels.condition.isin(conditions)].copy()
    links = pd.read_csv(origin/'PANEL_TEAMS.csv.gz')
    links = links[links.panel_id.isin(panels.panel_id)].copy()
    members = pd.read_csv(origin/'TEAM_MEMBERS.csv.gz')
    wanted = set(links.team_key)
    members = members[members.team_key.isin(wanted)].copy()
    assert members.team_key.is_unique
    endpoints = pd.concat([pd.read_csv(origin/f'ENDPOINT_OUTCOMES_{c}.csv.gz', low_memory=False)
                           for c in sorted(conditions)], ignore_index=True)
    endpoints = endpoints[endpoints.team_key.isin(wanted)].set_index('team_key')
    assert endpoints.index.is_unique and set(endpoints.index) == wanted
    pools = {p['pool_id']:p for p in json.loads((args.repo/RELEASE/'pools/INPUT_SNAPSHOT.json').read_text())['images']}
    deps = {r['pool_id']:r for r in json.loads((args.repo/RELEASE/'pools/DEPENDENCIES.json').read_text())}
    bad = []
    for r in members.itertuples():
        pool = pools.get(r.pool_id)
        if pool is None:
            bad.append(dict(team_key=r.team_key, pool_id=r.pool_id, reason='pool_not_in_current_primary_snapshot'))
            continue
        own = {a['worker_id']:a['object_id'] for a in pool['records']}
        workers = r.member_workers.split('|')
        if not set(workers) <= set(own):
            bad.append(dict(team_key=r.team_key, pool_id=r.pool_id, reason='member_not_in_current_target_pool'))
    badkeys = {r['team_key'] for r in bad}
    save_csv(args.out/'EXCLUDED_LEGACY_TEAMS.csv', pd.DataFrame(bad, columns=['team_key','pool_id','reason']))
    if badkeys:
        links = links[~links.team_key.isin(badkeys)]
        members = members[~members.team_key.isin(badkeys)]
        endpoints = endpoints.drop(index=list(badkeys))
        panels = panels[panels.panel_id.isin(links.panel_id)].copy()
    changed = {p for p,r in deps.items() if r['action']=='reuse_geometry_rescore'}
    changed_wanted = set(endpoints[endpoints.pool_id.isin(changed)].index)
    updated = set(); sources = []; patch_fields = Counter()
    endpoints['endpoint_provenance'] = 'unchanged_saved_finite_panel_endpoint'
    endpoints['quality_data_release'] = 'v2.1'
    endpoints['reference_diagnostic_current'] = True
    # Keep geometry/time scalars, replace every reference-dependent scalar.
    endpoints.loc[list(changed_wanted), [c for c in REFERENCE_FIELDS if c in endpoints]] = np.nan
    for path in sorted((args.repo/RELEASE/'composition_rescore').rglob('*.jsonl.gz')):
        if path.name != 'REUSED_ENDPOINTS.jsonl.gz' and path.parent.name not in set(endpoints.pool_id):
            continue
        hits = 0
        with gzip.open(path, 'rt', encoding='utf-8') as stream:
            for line in stream:
                r = json.loads(line); key = r.get('team_key')
                if key not in changed_wanted:
                    continue
                assert key not in updated, key
                assert int(r['k']) == int(endpoints.at[key, 'k'])
                flat = {**r, **(r.get('result') or {})}
                for field, value in flat.items():
                    if field in endpoints.columns and (value is None or isinstance(value, (str, bool, int, float))):
                        if field not in {'team_key','endpoint_provenance','quality_data_release'}:
                            endpoints.at[key, field] = value
                            patch_fields[field] += 1
                # These diagnostics must never silently retain old-target values.
                diagnostics = [f for f in REFERENCE_FIELDS if f.startswith(('ref_', 'diag_')) and f in endpoints]
                endpoints.at[key, 'reference_diagnostic_current'] = all(f in flat for f in diagnostics)
                endpoints.at[key, 'endpoint_provenance'] = 'existing_v21_reference_rescore'
                updated.add(key); hits += 1
        if hits:
            sources.append(dict(repository_path=str(path.relative_to(args.repo)), reused_endpoints=hits,
                                bytes=path.stat().st_size, sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
    pending = sorted(changed_wanted-updated)
    if pending:
        save_csv(args.out/'MISSING_CURRENT_RESCORED_ENDPOINTS.csv', pd.DataFrame({'team_key':pending}))
        raise RuntimeError(f'{len(pending)} changed-reference endpoints unavailable; exact keys saved, no old scores substituted')
    for field in ['complete_evaluable', 'recorded_time_eligible']:
        if field in endpoints:
            endpoints[field] = as_bool(endpoints[field])
    endpoints['failure'] = (~endpoints.complete_evaluable).astype(float)
    endpoints['not_complete_evaluable'] = endpoints['failure']
    time = pd.to_numeric(endpoints.recorded_time_total_seconds, errors='coerce')
    good_time = endpoints.recorded_time_eligible & time.gt(0)
    if 'time_source_kinds' in endpoints:
        good_time &= endpoints.time_source_kinds.fillna('').ne('') & ~endpoints.time_source_kinds.fillna('').str.contains('|', regex=False)
    endpoints['recorded_time_total_seconds'] = time.where(good_time)
    endpoints['log_recorded_time'] = np.log(time.where(good_time))
    target = pd.read_csv(args.target_conditions).set_index('pool_id')
    for c in ['image_id','reference_id','reference_version','official_difficulty','geometric_challenge',
              'structural_condition','ref_turn5','ref_H','ref_short_edges','scope']:
        if c in target:
            panels[c] = panels.pool_id.map(target[c])
    panels['difficulty'] = panels['official_difficulty'].fillna('未分级')
    panels['panel_provenance'] = 'reused_original_complete_12_choose_6_panel'
    panel_counts = links.groupby('panel_id').size()
    panels['observed_team_links'] = panels.panel_id.map(panel_counts)
    panels['current_pool_legal_member_census_complete'] = panels.observed_team_links.eq(924)
    save_csv(args.out/'PANELS_USED.csv', panels)
    save_csv(args.out/'PANEL_TEAMS.csv.gz', links)
    save_csv(args.out/'TEAM_MEMBERS.csv.gz', members)
    save_csv(args.out/'ENDPOINT_SCALARS.csv.gz', endpoints.reset_index())
    save_csv(args.out/'RESCORE_SOURCE_MANIFEST.csv', pd.DataFrame(sources))
    save_csv(args.out/'PATCHED_FIELD_COVERAGE.csv', pd.DataFrame(sorted(patch_fields.items()), columns=['field','current_endpoint_patches']))
    save_csv(args.out/'METRIC_AVAILABILITY.csv', pd.DataFrame([
        dict(field=c, nonmissing=int(endpoints[c].notna().sum()), total=len(endpoints))
        for c in endpoints.columns if c not in {'image','building','condition','pool_id'}]))
    receipt = dict(conditions=sorted(conditions), panels=len(panels), images=panels.image.nunique(),
                   buildings=panels.building.nunique(), team_links=len(links), unique_endpoints=len(endpoints),
                   current_reference_rescored=len(updated), unchanged_endpoint_reuse=len(endpoints)-len(updated),
                   missing_current_rescores=len(pending), excluded_legacy_teams=len(bad),
                   new_fusions=0, new_scores=0,
                   changed_reference_diagnostics_unavailable=int((~endpoints.reference_diagnostic_current).sum()))
    (args.out/'INPUT_PREPARATION.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps(receipt, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
