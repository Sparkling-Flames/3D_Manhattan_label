"""Versioned use/compute split over saved fusion states; never re-fuse or edit old scores."""
import gzip
import json

import pandas as pd

from .wall_consensus_b8l2_20261016 import OUT as SOURCE, ROOT, COMPONENTS, finite
from .wall_consensus_quality_20261015 import measured, save
from .scope_quality_scoring_20261016 import scoring_engine

OUT = SOURCE / 'usage_v2'
VERSION = 'fusion_compute_use_separated_20261016_v2'


def eligibility(row, scene):
    oos = 'oos' in scene
    full = finite(row, COMPONENTS) and pd.notna(row.get('IoU3D100'))
    status = row['score_status']
    if int(row['k']) == 2:
        availability = 'not_run_two_person_order_deferred'
    elif full:
        availability = 'complete_numeric'
    elif bool(row['below_four']):
        availability = 'insufficient_nodes'
    elif not bool(row['connection_available']):
        availability = 'no_connection'
    elif not bool(row['full_reference_available']):
        availability = 'floor_only_reference' if pd.notna(row.get('iou_2d')) else 'missing_reference'
    elif pd.notna(row.get('iou_2d')):
        availability = 'floor_only_invalid_full_geometry'
    elif 'held' in status:
        availability = 'not_run_policy_hold'
    else:
        availability = 'invalid_geometry'
    return dict(computability=availability, is_oos=oos,
                quality_use=('excluded_oos_reference_uncertain' if oos else
                             'doorway_conditional' if 'doorway' in scene else row['use']),
                reference_quality_scene_allowed=(not oos and full and bool(row['source_pool_allowed'])),
                # Existing target/holdout/member limits still apply to ordinary comparisons.
                primary_comparison_eligible=(not oos and bool(row['primary_comparison_eligible'])),
                geometry_stability_available=bool(row['floor_evaluable']))


def main():
    OUT.mkdir(exist_ok=True)
    snapshot = json.loads((SOURCE/'input_snapshot.json').read_text(encoding='utf-8'))
    frame = pd.read_csv(SOURCE/'trajectory_scores.csv')
    rows = []
    with scoring_engine() as (engine, models):
        for im in snapshot['images']:
            code = im['image']; scene = im['difficulty']['scene']; cache = {}
            states = json.load(gzip.open(ROOT/im['state_source'], 'rt', encoding='utf-8'))['states']
            states = {'|'.join(sorted(e['workers'])): e['automatic'] for e in states}
            ref = im['reference']
            for _, original in frame[frame.image.eq(code)].iterrows():
                row = original.to_dict()
                oos = 'oos' in scene
                origin = 'saved_components'
                if oos and row['k'] != 2 and not finite(row, COMPONENTS):
                    key = row['subset']
                    if key not in cache:
                        cache[key] = measured(engine, states[key], dict(floor=ref['floor_xz_h'],
                            points=ref['points_1024x512'] if ref['full_reference_available'] else None))
                    row.update(cache[key]); origin = 'measured_saved_geometry_diagnostic_only'
                row.update(eligibility(row, scene))
                row.update(usage_version=VERSION, numeric_origin=origin,
                           B8L2_numeric=None, WQ_numeric=None, IoU3D100_numeric=row.get('IoU3D100'))
                if finite(row, COMPONENTS):
                    vals = [float(row[k]) for k in COMPONENTS]
                    row.update(B8L2_numeric=float(models.score(*vals, params=models.B)),
                               WQ_numeric=float(models.score(*vals, params=models.WQ)))
                # These are explicit diagnostic columns; old B8L2/WQ remain untouched in SOURCE.
                if oos:
                    row['B8L2'] = None; row['WQ'] = None; row['IoU3D100'] = None
                rows.append(row)
    result = pd.DataFrame(rows)
    result.to_csv(OUT/'trajectory_usage.csv', index=False, encoding='utf-8-sig')
    unique = result.drop_duplicates(['image','subset'])
    unique.to_csv(OUT/'subset_usage.csv', index=False, encoding='utf-8-sig')
    coverage = []
    for unit, data in [('path_state', result), ('unique_subset', unique)]:
        for (image, scene, state, use), g in data.groupby(['image','scene','computability','quality_use']):
            coverage.append(dict(unit=unit,image=image,scene=scene,computability=state,quality_use=use,
                count=len(g),B8L2_numeric=int(g.B8L2_numeric.notna().sum()),
                scene_allowed=int(g.reference_quality_scene_allowed.sum()),
                geometry_stability_available=int(g.geometry_stability_available.sum())))
    pd.DataFrame(coverage).to_csv(OUT/'coverage.csv',index=False,encoding='utf-8-sig')
    members = []
    for im in snapshot['images']:
        oos = 'oos' in im['difficulty']['scene']
        for member in im['members']:
            blocked = []
            if oos: blocked.append('oos_reference_quality_excluded')
            if not im['source_pool']['pool_analysis_eligible']: blocked.append('source_pool_held')
            if member['quality_gate']['status'] != 'candidate_pending_geometry': blocked.append('existing_quality_gate')
            if member['worker_quality_gate'] != 'candidate_pending_geometry': blocked.append('existing_worker_quality_gate')
            if member['legacy_personnel_barriers']: blocked.append('legacy_personnel_barrier')
            if member['original_holdout']: blocked.append('original_holdout')
            if member['binding'] and member['binding']['chosen_target_id'] != im['reference']['target_id']: blocked.append('target_binding_pending')
            members.append(dict(image=im['image'],worker_id=member['worker_id'],record_id=member['record_id'],
                oos_quality_excluded=oos,known_quality_restricted=bool(blocked),
                reasons='|'.join(blocked),pool_vote_eligible=member['pool_vote_eligible']))
    members = pd.DataFrame(members)
    members.to_csv(OUT/'member_usage.csv',index=False,encoding='utf-8-sig')
    members.groupby('worker_id').agg(module_records=('record_id','count'),
        oos_quality_excluded=('oos_quality_excluded','sum'),
        known_quality_restricted=('known_quality_restricted','sum'),
        pool_vote_eligible=('pool_vote_eligible','sum')).to_csv(OUT/'worker_coverage.csv',encoding='utf-8-sig')
    save(OUT/'FIELD_CONTRACT.json',dict(version=VERSION,source=str(SOURCE.relative_to(ROOT)),
        units=['path_state','unique_subset','source_record'],
        numeric_columns='B8L2_numeric/WQ_numeric/IoU3D100_numeric include OOS diagnostic calculations, never quality comparison',
        quality_use='OOS always excluded; doorway conditional; original binding/holdout/worker gates still apply',
        reference_quality_scene_allowed='numerically complete and scene/source pool permitted; NOT sufficient for primary comparison',
        member_scope='18 frozen pools only; known source restrictions, not global worker exclusion counts or individual scoring success',
        failure_scope='prepared paired inputs only; no raw unpaired-input prevalence estimate',
        not_run='k2 ordering deferred or explicit policy hold, never counted as mathematical impossibility',
        stability='floor_evaluable is geometric availability, not correctness or endorsement',
        fusion_rerun=False,old_files_rewritten=False))
    print(pd.DataFrame(coverage).query("unit == 'path_state' and scene != 'clear'").to_string(index=False))


if __name__ == '__main__':
    main()
