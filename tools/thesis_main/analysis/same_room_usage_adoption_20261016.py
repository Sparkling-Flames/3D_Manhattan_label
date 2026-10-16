"""接入统一门洞/OOS用途版，桥接同房图对；只消费楼外连续Q/T。"""
import json

import numpy as np
import pandas as pd

from .same_room_b8l2_20261016 import (
    ROOT, OUT as LEGACY, SHARED, QUALITY_METRICS, TIME_METRICS,
    pair_tables, aggregate_pairs, matched_controls, verify_original_scores,
)
from .same_room_similarity_20261003 import correlation
from .same_room_quality_curves_20261015 import save
from .scope_quality_scoring_20261016 import scoring_engine

SOURCE = ROOT / 'research/statistics/b8l2_usage_v6_20261016'
WORKERS = ROOT / 'research/workers/worker_b8l2_20261016'
OUT = LEGACY / 'usage_v3'
VERSION = 'same_room_usage_adopted_20261016_v3'


def profiles_for_buildings(frame, panel, axis, buildings):
    selected = frame[frame.panel.eq(panel) & frame.axis.eq(axis)]
    rows = []
    for building in buildings:
        fold = building if selected.fold.eq(building).any() else 'full_descriptive'
        current = selected[selected.fold.eq(fold)].copy()
        if current.empty or not current.worker_id.is_unique:
            raise ValueError('missing or duplicate worker profile fold')
        if current.training_buildings.map(lambda value: building in json.loads(value)).any():
            raise ValueError('target building leaked into profile training')
        current['building'] = building
        rows.append(current)
    return pd.concat(rows, ignore_index=True)


def doorway_relations(records, coverage, *, comparable_label='confirmed_comparable'):
    doors = set(records.loc[records.is_doorway, 'image_id'])
    scored_doors = set(records.loc[records.is_doorway & records.B8L2.notna(), 'image_id'])
    selected = coverage[coverage.image_a.isin(doors) | coverage.image_b.isin(doors)].copy()
    groups = {(i, c): g[g.B8L2.notna()] for (i, c), g in records.groupby(['image_id', 'condition'])}
    empty = records.iloc[:0]
    rows = []
    for row in selected.to_dict('records'):
        a, b = [groups.get((row[key], row['condition']), empty) for key in ['image_a', 'image_b']]
        common = sorted(set(a.worker_id) & set(b.worker_id))
        rows.append(dict(row, n_quality_a=len(a), n_quality_b=len(b), n_common_quality=len(common),
            scored_doorway_image_either=row['image_a'] in scored_doors or row['image_b'] in scored_doors,
            common_quality_workers='|'.join(common),
            reference_ids_a='|'.join(sorted(a.reference_id.dropna().unique())),
            reference_ids_b='|'.join(sorted(b.reference_id.dropna().unique())),
            quality_comparable=(row['confirmation'] == comparable_label and bool(common))))
    return pd.DataFrame(rows)


def qt_observations(people, profiles, out, *, quality_panel='current949', quality_metrics=('B8L2',)):
    frames = []; summaries = []; frozen = []
    for metric, panel, axis in [(metric, quality_panel, metric) for metric in quality_metrics]+[
        ('source_time_seconds', 'T_source', 'T_source'),
        ('target_matched_time_seconds', 'T_target', 'T_target')]:
        paired = people[people.metric.eq(metric)].copy()
        prior = profiles_for_buildings(profiles, panel, axis, sorted(paired.building.unique()))
        frozen.append(prior)
        joined = paired.merge(prior[['building', 'worker_id', 'effect', 'supported', 'fold',
            'contexts', 'buildings', 'training_buildings']], on=['building', 'worker_id'],
            how='left', validate='many_to_one')
        joined['profile_panel'] = panel
        frames.append(joined)
        for keys, group in joined.groupby(['image_a', 'image_b', 'condition', 'confirmation']):
            usable = group[group.supported.eq(True) & group.effect.notna()]
            a, b = usable.value_a.to_numpy(), usable.value_b.to_numpy()
            if metric.endswith('seconds'):
                a, b = np.log(a), np.log(b)
            summaries.append(dict(image_a=keys[0], image_b=keys[1], condition=keys[2], confirmation=keys[3],
                code_a=group.code_a.iloc[0], code_b=group.code_b.iloc[0], building=group.building.iloc[0],
                metric=metric, profile_panel=panel, n_original=len(group), n_supported=len(usable),
                workers='|'.join(sorted(usable.worker_id)), raw_view_spearman=correlation(a, b),
                profile_vs_a=correlation(usable.effect.to_numpy(), a),
                profile_vs_b=correlation(usable.effect.to_numpy(), b)))
    save(out, 'qt_fold_profiles.csv', pd.concat(frozen, ignore_index=True))
    save(out, 'qt_paired_people.csv', pd.concat(frames, ignore_index=True))
    result = pd.DataFrame(summaries)
    save(out, 'qt_pair_observations.csv', result)
    return result


def main(out=OUT, relation_package=None):
    OUT = out
    VERSION = 'same_room_usage_adopted_20261016_v3' if relation_package is None else 'same_room_working_relations_20261016_v4'
    comparable_label = 'confirmed_comparable' if relation_package is None else 'user_classified_comparable'
    OUT.mkdir(exist_ok=True)
    cross = json.loads((SOURCE / 'CROSS_MODULE_INPUTS.json').read_text(encoding='utf-8'))
    assert cross['version'] == 'b8l2_scene_usage_v6_20261016_v2'
    assert cross['input_version'] == 'b8l2_shared_v6_20261016_v1'
    assert cross['score_version'] == 'WQ-B8L2-20261015'
    record = pd.read_csv(SOURCE / 'analysis_records.csv')
    old = pd.read_csv(LEGACY / 'frozen_analysis_records.csv')
    assert record.object_id.is_unique and set(record.object_id) == set(old.object_id)
    assert record.usage_version.eq(cross['version']).all()
    assert record.difficulty_version.eq(cross['difficulty_version']).all()
    assert not record.duplicated(['image_id', 'condition', 'worker_id']).any()
    before = old.set_index('object_id').loc[record.object_id]
    for field in ['image_id', 'worker_id', 'condition', 'current_target_id']:
        assert list(record[field]) == list(before[field]), field
    record['source_time_seconds'] = record.active_time_seconds
    for field in TIME_METRICS:
        assert np.allclose(record[field], before[field], equal_nan=True, atol=1e-10, rtol=0), field
    for field in ['time_status', 'time_source', 'time_source_file', 'time_rule_version', 'time_stage', 'time_binding']:
        assert list(record[field].fillna('')) == list(before[field].fillna('')), field
    assert not (record.is_oos & record.quality_usable).any()
    assert record.loc[~record.quality_usable, QUALITY_METRICS].isna().all().all()
    quality = record[record.quality_usable]
    assert quality[QUALITY_METRICS].notna().all().all()
    assert quality.reference_id.eq(quality.current_target_id).all()
    binding = pd.read_csv(SOURCE / 'shared_bindings.csv').set_index('object_id').loc[quality.object_id]
    assert binding[['analysis_binding_eligible', 'score_input_eligible', 'chosen_target_is_current', 'target_binding_unique']].all().all()
    assert not binding[['annotation_modified', 'annotation_cropped', 'quality_used_for_binding']].any().any()
    refs = pd.read_csv(SOURCE / 'space_reference_catalog.csv').set_index('target_id').loc[quality.reference_id]
    assert refs.full_reference_available.all() and refs.is_admitted_space_candidate.all()
    save(OUT, 'binding_reference_audit.csv', quality[['object_id', 'reference_id', 'reference_version',
        'condition', 'worker_id', 'quality_use', 'target_binding_unique', 'full_input_available', 'reference_full_available']])
    with scoring_engine(SHARED / 'inputs/measurement_engine.zip', SHARED / 'inputs/working_models.py') as (_, models):
        save(OUT, 'formula_audit.csv', verify_original_scores(quality, models))
    save(OUT, 'frozen_analysis_records.csv', record)
    relation_file = LEGACY / 'direct_relations.json' if relation_package is None else relation_package / 'relations.json'
    relations = {(r['image_a'], r['image_b']): r for r in json.loads(relation_file.read_text(encoding='utf-8'))}
    old_cov = pd.read_csv(LEGACY / 'relation_coverage.csv')
    images = {}
    for r in old_cov.itertuples():
        images[r.image_a] = dict(image_code=r.code_a, building_id=r.building)
        images[r.image_b] = dict(image_code=r.code_b, building_id=r.building)
    if relation_package is not None:
        registry = json.loads((ROOT / 'analysis_results/final_review_summary_20260929/同房分类_原始完整记录.json').read_text(encoding='utf-8'))
        for r in registry['images']:
            images[r['image_id']] = dict(image_code=f"{r['building']}-{r['number']:02d}", building_id=r['building'])
    pairs, people, coverage = pair_tables(record, relations, images, QUALITY_METRICS + TIME_METRICS)
    save(OUT, 'current_pairs.csv', pairs); save(OUT, 'current_people.csv', people)
    save(OUT, 'current_by_building.csv', aggregate_pairs(pairs))
    door = doorway_relations(record, coverage, comparable_label=comparable_label); save(OUT, 'doorway_relation_coverage.csv', door)
    save(OUT, 'doorway_records.csv', record[record.is_doorway])
    old_pairs = pd.read_csv(LEGACY / 'current_pairs.csv')
    keys = ['image_a', 'image_b', 'condition', 'metric']
    fields = ['n_paired', 'paired_workers', 'absolute_mean_gap', 'mean_absolute_person_delta']
    bridge = old_pairs[keys + fields].merge(pairs[keys + fields], on=keys, how='outer',
        suffixes=('_old', '_new'), indicator=True, validate='one_to_one')
    for field in fields:
        if field in ['n_paired', 'paired_workers']:
            bridge[field + '_unchanged'] = bridge[field + '_old'].fillna('').eq(bridge[field + '_new'].fillna(''))
        else:
            bridge[field + '_unchanged'] = np.isclose(bridge[field + '_old'], bridge[field + '_new'],
                equal_nan=True, atol=1e-8, rtol=0)
    save(OUT, 'old_new_pair_bridge.csv', bridge)
    old_quality = old[old.B8L2.notna()]
    membership = old_quality[['object_id', 'reference_id', 'B8L2']].merge(
        quality[['object_id', 'reference_id', 'B8L2', 'quality_use']], on='object_id', how='outer',
        suffixes=('_old', '_new'), indicator=True, validate='one_to_one')
    save(OUT, 'old_new_quality_membership.csv', membership)
    retained = membership[membership._merge.eq('both')]
    assert retained.reference_id_old.eq(retained.reference_id_new).all()
    controls = matched_controls(record, pairs, relations, comparable_label=comparable_label)
    save(OUT, 'matched_single_source_controls.csv', controls)
    worker_inputs = json.loads((WORKERS / 'INPUTS.json').read_text(encoding='utf-8'))
    train = pd.read_csv(WORKERS / 'current_quality_panel.csv')
    train_new = quality.set_index('object_id').loc[train.object_id]
    assert train_new.reference_id.to_list() == train.reference_id.to_list()
    assert np.allclose(train_new.B8L2, train.B8L2, atol=1e-8, rtol=0)
    assert not train_new.is_oos.any() and not train_new.is_doorway.any()
    qt = qt_observations(people, pd.read_csv(WORKERS / 'fold_profiles.csv'), OUT)
    positive = pairs[pairs.n_paired.gt(0)]
    summary = dict(version=VERSION, stage='shared_usage_adopted', usage_version=cross['version'],
        input_version=cross['input_version'], difficulty_version=cross['difficulty_version'],
        source_records=len(record), quality_records=len(quality), doorway_quality_records=int(quality.is_doorway.sum()),
        doorway_quality_images=int(quality.loc[quality.is_doorway, 'image_id'].nunique()),
        oos_quality_records=int(quality.is_oos.sum()),
        membership_changes=membership._merge.value_counts().to_dict(),
        retained_reference_ids_equal=True,
        retained_max_score_difference=float((retained.B8L2_old - retained.B8L2_new).abs().max()),
        doorway_candidate_edges=int(door[['image_a', 'image_b']].drop_duplicates().shape[0]),
        scored_doorway_candidate_edges=int(door.loc[door.scored_doorway_image_either, ['image_a', 'image_b']].drop_duplicates().shape[0]),
        doorway_direct_confirmed_edges=int(door.loc[door.confirmation.ne('not_explicitly_confirmed'), ['image_a', 'image_b']].drop_duplicates().shape[0]),
        doorway_legal_quality_pairs=int(door.quality_comparable.sum()),
        old_pair_members_and_values_unchanged=bool(bridge._merge.eq('both').all() and bridge[[f + '_unchanged' for f in fields]].all().all()),
        positive_pairs=positive.groupby(['metric', 'condition', 'confirmation']).size().reset_index(name='pairs').to_dict('records'),
        source_time_records=int(record.source_time_seconds.notna().sum()),
        target_matched_time_records=int(record.target_matched_time_seconds.notna().sum()),
        time_records_unchanged=True, controls=len(controls), worker_profile_rows=len(train),
        worker_input_version=worker_inputs['shared']['version'],
        worker_adoption='existing ordinary Q/T folds only; all training scores/references retained by new usage; no doorway profile invented',
        qt_pairs_ge4=qt[qt.n_supported.ge(4)].groupby(['metric', 'confirmation']).size().reset_index(name='pairs').to_dict('records'),
        new_fusion_experiments=False, global_files_modified=False)
    save(OUT, 'INPUTS.json', dict(shared=cross, personnel=worker_inputs,
        direct_relations=str(relation_file.relative_to(ROOT))))
    save(OUT, 'SUMMARY.json', summary)
    save(OUT, 'FIELD_CONTRACT.json', dict(version=VERSION,
        table_columns={p.name: list(pd.read_csv(p, nrows=0).columns) for p in OUT.glob('*.csv')},
        cohort='shared qualified source; all metrics already masked by unified quality_usable; diagnostic_* never quality',
        relation='direct explicit physical confirmation; comparable and other-scope separated; conditions never pooled',
        doorway='candidate coverage is not confirmation; separate side reference IDs and common workers retained',
        time='source and audited target-matched seconds kept independently; no new target time inferred',
        bridge='same keys/workers and differences; 1e-8 numeric tolerance for shared export/recomputation rounding',
        qt='held-out whole building continuous profiles; unseen building uses full training only after exclusion check; unsupported not imputed',
        inference='raw paired/view/prior associations only; no residual-correlation evidence, no fixed classes, no S/B',
        curves='no new geometry or fusion experiment'))
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
