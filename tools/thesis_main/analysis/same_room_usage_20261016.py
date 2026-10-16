"""同房用途补充：保留旧v6，数值与参考质量用途分开。"""
import json

import numpy as np
import pandas as pd

from .same_room_b8l2_20261016 import QUALITY_METRICS, TIME_METRICS, ROOT, SHARED, OUT as LEGACY, pair_tables
from .same_room_quality_curves_20261015 import save

OUT = LEGACY / 'usage_v2'


def quality_projection(records):
    """用途许可由统一统计表提供；OOS交集优先，时间不随质量屏蔽。"""
    if (records.is_oos & records.reference_quality_allowed).any():
        raise ValueError('OOS cannot enter reference quality analysis')
    result = records.copy()
    for metric in QUALITY_METRICS:
        result['numeric_' + metric] = result[metric]
        result.loc[~result.reference_quality_allowed, metric] = float('nan')
    return result


def legacy_impact():
    OUT.mkdir(exist_ok=True)
    version = json.loads((SHARED / 'CROSS_MODULE_INPUTS.json').read_text(encoding='utf-8'))['version']
    if version != 'b8l2_shared_v6_20261016_v1':
        raise ValueError('legacy audit requires the original frozen shared v6')
    metadata = pd.read_csv(SHARED / 'analysis_records.csv')
    records = pd.read_csv(LEGACY / 'frozen_analysis_records.csv')
    records = records.merge(metadata[['object_id', 'scene', 'doorway_status', 'oos_subtype', 'quality_use']],
                            on='object_id', validate='one_to_one')
    # This is explicitly the OLD coverage projection, not new doorway computation.
    records['is_oos'] = (records.scene.str.contains('oos', regex=False) |
        records.oos_subtype.isin(['nonorthogonal_annotatable', 'subtype_not_resolved', 'suspected_user_review']))
    records['is_doorway'] = (records.scene.str.contains('doorway', regex=False) |
        records.doorway_status.isin(['annotatable', 'difficult', 'suspected_user_review']))
    records['reference_quality_allowed'] = records.current_quality_eligible & ~records.is_oos
    projected = quality_projection(records)
    save(OUT, 'legacy_record_usage.csv', projected)
    relations = {(row['image_a'], row['image_b']): row for row in
                 json.loads((LEGACY / 'direct_relations.json').read_text(encoding='utf-8'))}
    images = {r.image_id: dict(image_code=r.image_code, building_id=r.building_id)
              for r in metadata.itertuples()}
    # Relation-only images can be outside the qualified source table.
    old_coverage = pd.read_csv(LEGACY / 'relation_coverage.csv')
    for r in old_coverage.itertuples():
        images[r.image_a] = dict(image_code=r.code_a, building_id=r.building)
        images[r.image_b] = dict(image_code=r.code_b, building_id=r.building)
    pairs, _, _ = pair_tables(projected, relations, images, QUALITY_METRICS + TIME_METRICS)
    old_pairs = pd.read_csv(LEGACY / 'current_pairs.csv')
    keys = ['image_a', 'image_b', 'condition', 'metric']
    fields = ['n_paired', 'absolute_mean_gap', 'mean_absolute_person_delta']
    bridge = old_pairs[keys + fields].merge(pairs[keys + fields], on=keys,
        how='outer', suffixes=('_old', '_usage'), validate='one_to_one', indicator=True)
    if not bridge._merge.eq('both').all():
        raise ValueError('legacy relation coverage changed during purpose projection')
    for field in fields:
        bridge[field + '_unchanged'] = (bridge[field + '_old'].eq(bridge[field + '_usage']) |
            (bridge[field + '_old'].isna() & bridge[field + '_usage'].isna()))
        # CSV float round-trips may differ in the final decimal digit.
        if field != 'n_paired':
            bridge[field + '_unchanged'] = np.isclose(bridge[field + '_old'], bridge[field + '_usage'],
                                                       equal_nan=True, atol=1e-10, rtol=0)
    save(OUT, 'legacy_pair_bridge.csv', bridge)
    people = pd.read_csv(LEGACY / 'current_people.csv')
    for side in ['a', 'b']:
        flags = projected[['object_id', 'is_oos', 'is_doorway', 'reference_quality_allowed']]
        flags = flags.rename(columns={c: c + '_' + side for c in flags})
        people = people.merge(flags, on='object_id_' + side, validate='many_to_one')
    people['reference_quality_metric'] = people.metric.isin(QUALITY_METRICS)
    people['both_quality_allowed'] = people.reference_quality_allowed_a & people.reference_quality_allowed_b
    people['oos_either'] = people.is_oos_a | people.is_oos_b
    people['doorway_either'] = people.is_doorway_a | people.is_doorway_b
    save(OUT, 'legacy_pair_person_usage.csv', people)
    impact = people.groupby(['confirmation', 'condition', 'metric'], as_index=False).agg(
        paired_person_occurrences=('worker_id', 'size'),
        oos_occurrences=('oos_either', 'sum'), doorway_occurrences=('doorway_either', 'sum'),
        quality_allowed_occurrences=('both_quality_allowed', 'sum'))
    save(OUT, 'legacy_pair_impact.csv', impact)
    controls = pd.read_csv(LEGACY / 'matched_single_source_controls.csv')
    image_flags = projected.groupby('image_id')[['is_oos', 'is_doorway']].any()
    audit = []
    for row in controls.itertuples():
        ids = [row.source, row.target] + (row.control_image_ids.split('|') if pd.notna(row.control_image_ids) else [])
        audit.append(dict(source=row.source, target=row.target, condition=row.condition,
                          metric=row.metric, images_checked=len(ids),
                          any_oos=any(image_flags.loc[i, 'is_oos'] for i in ids),
                          any_doorway=any(image_flags.loc[i, 'is_doorway'] for i in ids)))
    audit = pd.DataFrame(audit)
    save(OUT, 'legacy_control_impact.csv', audit)
    quality = people[people.reference_quality_metric]
    summary = dict(version='same_room_compute_use_separated_20261016_v2',
        stage='legacy_impact_complete_waiting_shared_usage_version',
        legacy_input=version,
        legacy_module=str(LEGACY.relative_to(ROOT)),
        old_numeric_records=int(projected.numeric_B8L2.notna().sum()),
        old_coverage_quality_after_oos_mask=int(projected.B8L2.notna().sum()),
        old_numeric_oos_records=int((projected.is_oos & projected.numeric_B8L2.notna()).sum()),
        old_numeric_doorway_records=int((projected.is_doorway & projected.numeric_B8L2.notna()).sum()),
        quality_pair_person_occurrences=len(quality),
        quality_pair_person_occurrences_blocked=int((~quality.both_quality_allowed).sum()),
        all_old_pair_counts_and_differences_unchanged=bool(bridge[[f + '_unchanged' for f in fields]].all().all()),
        control_rows_checked=len(audit), control_rows_with_oos=int(audit.any_oos.sum()),
        control_rows_with_doorway=int(audit.any_doorway.sum()),
        source_time_retained=bool(projected.source_time_seconds.equals(records.source_time_seconds)),
        target_time_retained=bool(projected.target_matched_time_seconds.equals(records.target_matched_time_seconds)),
        new_doorway_scores='not computed by this module; awaiting common version',
        full_inventory_worker_exclusions='owned by common statistics; not inferred from same-room subset',
        new_fusion_curves=False, historical_outputs_rewritten=False)
    save(OUT, 'SUMMARY.json', summary)
    save(OUT, 'FIELD_CONTRACT.json', dict(version=summary['version'],
        table_columns={p.name: list(pd.read_csv(p, nrows=0).columns) for p in OUT.glob('*.csv')},
        scope='legacy v6 coverage audit only until a new common purpose version is adopted',
        quality_projection='all reference-quality columns masked when not allowed; numeric_* retains diagnostic values',
        oos='scene flag independent of answer condition or refusal choice; OOS takes priority over doorway',
        time='source and target-matched seconds unchanged; quality exclusion does not exclude time',
        unknown='old not_queued is not mathematical impossibility; no new computability denominator inferred',
        personnel='module-specific paired coverage is not full-inventory worker exclusion or ability'))
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    legacy_impact()
