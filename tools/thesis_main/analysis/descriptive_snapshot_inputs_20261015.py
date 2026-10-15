"""已审核归一化批次与评分版本的描述统计接入；不评分、不授予资格。"""
import argparse
import itertools
import json
from pathlib import Path

import numpy as np
import pandas as pd

from .descriptive_statistics_20261015 import describe

IDENTITY = ['object_id', 'image_id', 'worker_id', 'condition']
ALGORITHM = ['algorithm_id', 'version', 'input_version', 'reference_version']
MEASUREMENT = ALGORITHM + ['object_id', 'reference_id']
OUTPUTS = ['snapshot_inputs', 'score_measurements', 'algorithm_coverage', 'algorithm_common_comparisons']
IMAGE_AXES = ['image_code', 'difficulty_version', 'difficulty_class', 'conditional_difficulty',
              'target_id', 'top_boundary_pending', 'special_layer', 'difficulty_scene',
              'difficulty_oos_subtype', 'live_oos_status', 'doorway_status',
              'markability_from_explicit_label', 'room_coarse_type', 'main_visual_space',
              'expected_annotation_extent', 'oos_axis', 'doorway_axis']


def require(frame, columns, label):
    missing = set(columns) - set(frame.columns)
    if missing:
        raise ValueError(f'{label}: missing fields {sorted(missing)}')


def read_csv(base, name):
    return pd.read_csv(base / name, dtype=str, keep_default_na=False)


def build_snapshot(manifest, base):
    batches, image_batches = [], []
    batch_ids = set()
    for batch in manifest['batches']:
        batch_id, input_version = batch['batch_id'], batch['input_version']
        reference_version = batch['reference_version']
        if not batch_id or not input_version or not reference_version or batch_id in batch_ids:
            raise ValueError('empty or duplicate batch_id / input_version')
        batch_ids.add(batch_id)
        records = read_csv(base, batch['records_csv'])
        images = read_csv(base, batch['images_csv'])
        require(records, IDENTITY + ['reference_id', 'use_panel', 'active_time_seconds',
                                    'time_status', 'time_source', 'time_source_file', 'time_rule_version'], 'records')
        require(images, ['image_id'], 'images')
        images = images[['image_id'] + [c for c in IMAGE_AXES if c in images]]
        if images.image_id.eq('').any() or images.image_id.duplicated().any():
            raise ValueError('empty or duplicate image_id')
        if records[IDENTITY + ['use_panel', 'time_status']].eq('').any().any():
            raise ValueError('empty record identity / use_panel / time_status')
        if not records.image_id.isin(images.image_id).all():
            raise ValueError('unbound image_id')
        for column, value in [('input_version', input_version), ('reference_version', reference_version)]:
            if column in records and not records[column].eq(value).all():
                raise ValueError(f'batch {column} mismatch')
        # 图片轴逐值核对；记录级资格空值不能与图片级审计声明混为一谈。
        overlap = [c for c in images if c in records and c != 'image_id']
        indexed = images.set_index('image_id')
        for column in set(overlap) & set(IMAGE_AXES):
            if not records[column].eq(records.image_id.map(indexed[column])).all():
                raise ValueError(f'image axis conflict: {column}')
        records = records.merge(images.drop(columns=overlap), on='image_id', validate='many_to_one')
        time = pd.to_numeric(records.active_time_seconds.replace('', np.nan), errors='raise')
        usable = records.time_status.eq('usable')
        missing_provenance = records[['time_source', 'time_source_file', 'time_rule_version']].eq('').any(axis=1)
        lead_time = records.time_source.str.contains('lead_time', case=False, regex=False)
        if ((time.notna() & (~np.isfinite(time) | time.lt(0))) |
                (usable & (time.isna() | time.le(0) | missing_provenance | lead_time)) |
                (~usable & time.notna())).any():
            raise ValueError('active_time_seconds / time_status / time_source mismatch')
        records['active_time_seconds'] = time
        records['batch_id'] = batch_id
        records['input_version'] = input_version
        records['reference_version'] = reference_version
        records['records_source_csv'] = batch['records_csv']
        records['images_source_csv'] = batch['images_csv']
        batches.append(records)
        image_batches.append(images)
    inputs = pd.concat(batches, ignore_index=True)
    if inputs.object_id.duplicated().any():
        raise ValueError('duplicate object_id across batches; use separate snapshots for revisions')
    all_images = pd.concat(image_batches, ignore_index=True).fillna('')
    for column in all_images.columns.difference(['image_id']):
        if all_images.groupby('image_id')[column].nunique().gt(1).any():
            raise ValueError(f'image axis conflict between batches: {column}')

    measurements = []
    for algorithm in manifest['algorithms']:
        metadata = {key: algorithm[key] for key in ALGORITHM}
        if not all(isinstance(value, str) and value for value in metadata.values()):
            raise ValueError('empty algorithm identity/version')
        if algorithm['direction'] not in ('higher_is_better', 'lower_is_better'):
            raise ValueError('unknown algorithm direction')
        low, high = float(algorithm['minimum']), float(algorithm['maximum'])
        if not np.isfinite([low, high]).all() or low >= high:
            raise ValueError('invalid algorithm range')
        population = inputs[inputs.input_version.eq(algorithm['input_version']) &
                            inputs.reference_version.eq(algorithm['reference_version'])]
        if population.empty:
            raise ValueError('algorithm input_version / reference_version absent from audited batches')
        source = read_csv(base, algorithm['source_csv'])
        value_column = algorithm['value_column']
        require(source, IDENTITY + ['reference_id', value_column], 'scores')
        if source.object_id.duplicated().any():
            raise ValueError('duplicate measurement object_id')
        if not source.object_id.isin(population.object_id).all():
            raise ValueError('score identity / input_version outside declared population')
        for column in ['input_version', 'reference_version']:
            if column in source and not source[column].eq(algorithm[column]).all():
                raise ValueError(f'score {column} mismatch')
        expected = population.set_index('object_id').reindex(source.object_id)
        for column in IDENTITY[1:]:
            if not source[column].reset_index(drop=True).eq(expected[column].reset_index(drop=True)).all():
                raise ValueError(f'score identity mismatch: {column}')
        if not source.reference_id.to_list() == expected.reference_id.to_list():
            raise ValueError('score reference_id mismatch; independent reference review required')
        values = pd.to_numeric(source[value_column].replace('', np.nan), errors='raise')
        if (values.notna() & (~np.isfinite(values) | ~values.between(low, high))).any():
            raise ValueError('score range / nonfinite value')
        if (values.notna() & source.reference_id.eq('')).any():
            raise ValueError('score has unbound reference')
        detail = population[IDENTITY + ['reference_id', 'use_panel', 'batch_id', 'input_version']].copy()
        detail['source_row_present'] = detail.object_id.isin(source.object_id)
        detail['value'] = detail.object_id.map(pd.Series(values.to_numpy(), index=source.object_id))
        for key, value in metadata.items():
            detail[key] = value
        detail['source_csv'] = algorithm['source_csv']
        detail['value_column'] = value_column
        detail['direction'] = algorithm['direction']
        detail['minimum'], detail['maximum'] = low, high
        detail['measurement_status'] = np.where(detail.value.notna(), 'valid',
                                               np.where(detail.source_row_present, 'empty_value', 'absent_row'))
        measurements.append(detail)
    scores = pd.concat(measurements, ignore_index=True)
    if scores.duplicated(MEASUREMENT).any():
        raise ValueError('duplicate measurement algorithm/version/object/input/reference')
    coverage = []
    for key, group in scores.groupby(ALGORITHM, sort=True):
        layers = [('all_inputs', 'all', group)]
        layers += [('use_panel', panel, cell) for panel, cell in group.groupby('use_panel')]
        layers += [('reference_binding', 'bound', group[group.reference_id.ne('')])]
        for layer, label, cell in layers:
            coverage.append(dict(zip(ALGORITHM, key), coverage_layer=layer, layer_value=label,
                                 n_source_rows=int(cell.source_row_present.sum()),
                                 n_target_limited=int(cell.use_panel.ne('ordinary_same_target_conditional').sum()),
                                 n_unbound_reference=int(cell.reference_id.eq('').sum()),
                                 **describe(cell, 'value')))
    comparisons = []
    # 参考版本与输入版本必须同时相同；每个用途层只比较两算法共同非缺失的同对象集合。
    for context, group in scores.groupby(['input_version', 'reference_version', 'use_panel']):
        methods = list(group.groupby(['algorithm_id', 'version']))
        for (left_key, left), (right_key, right) in itertools.combinations(methods, 2):
            common = left.merge(right, on=IDENTITY + ['reference_id', 'input_version',
                                                     'reference_version', 'use_panel'],
                                suffixes=('_left', '_right'), validate='one_to_one')
            valid = common.value_left.notna() & common.value_right.notna()
            paired = common[valid].copy()
            paired['difference'] = paired.value_right - paired.value_left
            comparisons.append(dict(input_version=context[0], reference_version=context[1], use_panel=context[2],
                                    left_algorithm=left_key[0], left_version=left_key[1],
                                    right_algorithm=right_key[0], right_version=right_key[1],
                                    n_same_identity=len(common), n_left_valid=int(common.value_left.notna().sum()),
                                    n_right_valid=int(common.value_right.notna().sum()),
                                    n_incomplete_pairs=int((~valid).sum()),
                                    difference_definition='right_minus_left', **describe(paired, 'difference')))
    return dict(snapshot_inputs=inputs, score_measurements=scores,
                algorithm_coverage=pd.DataFrame(coverage),
                algorithm_common_comparisons=pd.DataFrame(comparisons))


def run(manifest_path, out):
    manifest_path, out = Path(manifest_path), Path(out)
    if out.exists() and any(out.iterdir()):
        raise FileExistsError(f'refusing to overwrite existing snapshot: {out}')
    manifest = json.loads(manifest_path.read_text(encoding='utf-8-sig'))
    tables = build_snapshot(manifest, manifest_path.parent)
    out.mkdir(parents=True, exist_ok=True)
    for name in OUTPUTS:
        tables[name].to_csv(out / (name + '.csv'), index=False, encoding='utf-8-sig')
    (out / 'INPUT_MANIFEST.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    locations = dict(manifest_origin=str(manifest_path.resolve()),
        batches=[dict(batch_id=b['batch_id'], records_csv=str((manifest_path.parent/b['records_csv']).resolve()),
                      images_csv=str((manifest_path.parent/b['images_csv']).resolve())) for b in manifest['batches']],
        algorithms=[dict(algorithm_id=a['algorithm_id'], version=a['version'],
                         source_csv=str((manifest_path.parent/a['source_csv']).resolve())) for a in manifest['algorithms']])
    (out / 'SOURCE_LOCATIONS.json').write_text(json.dumps(locations, ensure_ascii=False, indent=2), encoding='utf-8')
    return tables


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    result = run(args.manifest, args.out)
    print(json.dumps({name: len(table) for name, table in result.items()}, ensure_ascii=False))
