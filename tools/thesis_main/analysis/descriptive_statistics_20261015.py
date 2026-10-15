"""现有数据的版本化描述统计；复用已审核输入和分数，不重评分、不改资格。"""
import argparse
import json
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OUT = ROOT / 'research/descriptive_statistics_20261015'
QPATH = 'research/difficulty_target_integration_20261015/quality_bindings_1145.csv'
APATH = 'research/quality_ab_feedback_handoff_20261015/prior_AB/results/SCORES_1145.csv'
IPATH = 'research/difficulty_special_coverage_20261015/image_coverage_259.csv'
PPATH = 'research/worker_four_axis_update_20261015/quality_panel_931.csv'
METRICS = ['WQ', 'A10', 'B8L2', 'IoU3D100', 'iou_2d', 'S_bottom_deg',
           'dir', 'Hmean', 'Hcenter', 'active_time_seconds']


def read(path):
    return pd.read_csv(ROOT / path, dtype=str, keep_default_na=False)


def attach_scores(binding, scores):
    joined = binding.merge(scores, on='record_id', how='outer',
                           suffixes=('', '_ab'), validate='one_to_one', indicator=True)
    assert joined['_merge'].eq('both').all(), 'score IDs differ'
    for field in ['object_id', 'image_id', 'worker_id', 'reference_id', 'condition', 'WQ']:
        assert joined[field].eq(joined[field + '_ab']).all(), field
    result = binding.copy()
    additions = scores.set_index('record_id').reindex(result.record_id)
    result['A10'] = pd.to_numeric(additions.Q_A10.to_numpy(), errors='raise')
    result['B8L2'] = pd.to_numeric(additions.Q_B8L2.to_numpy(), errors='raise')
    assert np.allclose(pd.to_numeric(result.WQ), pd.to_numeric(additions.Q_WQ))
    assert np.allclose(pd.to_numeric(result.IoU3D100), pd.to_numeric(additions.Q_IoU3D)) if 'IoU3D100' in result else True
    return result


def describe(frame, metric):
    values = pd.to_numeric(frame[metric], errors='raise').dropna()
    valid = frame.loc[values.index]
    def value(x):
        return float(x) if pd.notna(x) else None
    return dict(metric=metric, n_records=len(frame), n_valid=len(values),
                n_missing=len(frame)-len(values), n_workers=frame.worker_id.nunique(),
                n_images=frame.image_id.nunique(),
                n_valid_workers=valid.worker_id.nunique(), n_valid_images=valid.image_id.nunique(),
                n_references=frame.loc[frame.reference_id.notna() & frame.reference_id.ne(''), 'reference_id'].nunique() if 'reference_id' in frame else 0,
                n_valid_references=valid.loc[valid.reference_id.notna() & valid.reference_id.ne(''), 'reference_id'].nunique() if 'reference_id' in valid else 0,
                mean=value(values.mean()), median=value(values.median()), sd=value(values.std(ddof=1)),
                q25=value(values.quantile(.25)), q75=value(values.quantile(.75)),
                minimum=value(values.min()), maximum=value(values.max()),
                image_equal_mean=value(valid.assign(_v=values).groupby('image_id')._v.mean().mean()))


def summaries(panels, dimensions):
    output = []
    for panel_name, panel in panels.items():
        groups = panel.groupby(dimensions, dropna=False, sort=True) if dimensions else [((), panel)]
        for key, group in groups:
            key = key if isinstance(key, tuple) else (key,)
            labels = dict(zip(dimensions, key))
            output.extend(dict(panel=panel_name, **labels, **describe(group, metric)) for metric in METRICS)
    return pd.DataFrame(output)


def image_axis(row):
    # 来源未记录仍为unknown；难度层与loader层并列保留。
    return ('yes' if row.difficulty_scene in ['oos', 'oos_and_doorway'] else
            'no' if row.difficulty_oos_subtype == 'not_oos' else
            'pending' if row.difficulty_scene == 'oos_pending' else 'unknown')


def comparison_tables(quality):
    pairs, contexts = [], []
    for panel_name, panel in quality.items():
        for base, other in [('WQ', 'A10'), ('WQ', 'B8L2'), ('A10', 'B8L2'), ('WQ', 'IoU3D100')]:
            r = panel.copy()
            r['difference'] = r[other] - r[base]
            pairs.append(dict(panel=panel_name, comparison=other+'-'+base,
                n_higher=int(r.difference.gt(0).sum()), n_lower=int(r.difference.lt(0).sum()),
                spearman=r[[base, other]].corr(method='spearman').iloc[0, 1], **describe(r, 'difference')))
        for keys, cell in panel.groupby(['image_id', 'condition', 'reference_id'], dropna=False):
            for metric in ['WQ', 'A10', 'B8L2', 'active_time_seconds']:
                available = cell.dropna(subset=[metric])
                for _, r in available.iterrows():
                    n = len(available)
                    # Leave-one-out only compares with other workers in this exact reference cell.
                    peer = (available[metric].sum()-r[metric])/(n-1) if n > 1 else np.nan
                    contexts.append(dict(panel=panel_name, record_id=r.record_id, object_id=r.object_id,
                        worker_id=r.worker_id, image_id=keys[0], condition=keys[1], reference_id=keys[2],
                        metric=metric, value=r[metric], n_peer_workers=n-1, peer_mean=peer,
                        difference_from_peers=r[metric]-peer))
    detail = pd.DataFrame(contexts)
    residual = []
    for keys, cell in detail.groupby(['panel', 'worker_id', 'metric']):
        data = cell.rename(columns={'difference_from_peers': '_residual'})
        residual.append(dict(panel=keys[0], worker_id=keys[1], original_metric=keys[2],
                             **describe(data, '_residual')))
    return pd.DataFrame(pairs), detail, pd.DataFrame(residual)


def build_tables():
    from .descriptive_inventory_20261015 import load_inventory
    from .descriptive_same_room_20261015 import build_same_room_tables
    from ..data_prep.consolidate_research_input import load_current_bundle
    bundle = load_current_bundle()
    with zipfile.ZipFile(ROOT/'research/quality_joint_closeout_review_20261015/pro_closeout_delta.zip') as archive:
        assert bundle['data'] == json.loads(archive.read('source/historical_current_formal_loader_data.json')), 'scoring geometry snapshot drift'
        import io
        ledger = pd.read_csv(io.BytesIO(archive.read('results/ALL_3152_LEDGER.csv')), dtype=str, keep_default_na=False)
    inventory = pd.DataFrame(load_inventory(bundle))
    inventory = inventory.rename(columns={'record_id': 'inventory_record_id'})
    assert len(inventory) == inventory.object_id.nunique() == 3152
    assert set(ledger.object_id) == set(inventory.object_id)
    ledger_fields = ['score_status', 'reference_id', 'reference_binding', 'role', 'source_cohort',
                     'personnel_barriers', 'context_barriers', 'numeric_barriers',
                     'iou_2d', 'S_bottom_deg', 'dir', 'floor_WQ', 'IoU3D100', 'WQ']
    inventory = inventory.merge(ledger[['object_id']+ledger_fields].rename(
        columns={c:'ledger_'+c for c in ledger_fields}), on='object_id', validate='one_to_one')
    for field in ['iou_2d', 'S_bottom_deg', 'dir', 'floor_WQ', 'IoU3D100', 'WQ']:
        inventory['ledger_'+field] = pd.to_numeric(inventory['ledger_'+field].replace('', np.nan), errors='raise')
    quality = attach_scores(read(QPATH), read(APATH))
    assert len(quality) == quality.object_id.nunique() == 1145
    for metric in METRICS[:-1]:
        quality[metric] = pd.to_numeric(quality[metric], errors='raise')
    original = read(PPATH)
    assert len(original) == original.record_id.nunique() == 931
    assert set(original.record_id) <= set(quality.record_id)
    quality['in_worker_931'] = quality.record_id.isin(original.record_id)
    quality['in_target_836'] = quality.use_panel.eq('ordinary_same_target_conditional')
    assert quality.in_target_836.sum() == 836
    assert quality.loc[quality.in_target_836, 'in_worker_931'].all()
    # 验证库存身份后才能通过对象ID接入评分；评分R号不是库存record_id。
    ids = inventory.set_index('object_id').reindex(quality.object_id)
    assert not ids.image_id.isna().any(), 'unbound quality objects'
    for field in ['image_id', 'worker_id', 'condition']:
        assert quality[field].to_list() == ids[field].to_list(), field
    qfields = [c for c in quality if c not in inventory or c == 'object_id']
    all_records = inventory.merge(quality[qfields], on='object_id', how='left', validate='one_to_one')
    images = read(IPATH)
    assert len(images) == images.image_id.nunique() == 259
    research_images = {r['image_id']: r for r in bundle['research']['images']}
    images['room_coarse_type'] = images.image_id.map(lambda i: research_images[i]['room_spatial_classification']['coarse_type'] or 'unknown')
    images['main_visual_space'] = images.image_id.map(lambda i: research_images[i]['main_visual_space'])
    images['expected_annotation_extent'] = images.image_id.map(lambda i: research_images[i]['expected_annotation_extent'])
    images['oos_axis'] = images.apply(image_axis, axis=1)
    images['doorway_axis'] = images.doorway_status.map(
        {'difficult': 'yes', 'annotatable': 'yes', 'none': 'no', 'not_recorded': 'unknown'})
    assert images.doorway_axis.notna().all()
    for column in ['difficulty_class', 'difficulty_version']:
        if column in all_records:
            existing = all_records[['image_id', column]].dropna()
            expected = images.set_index('image_id')[column]
            assert existing[column].eq(existing.image_id.map(expected)).all(), column
            all_records[column] = all_records[column].fillna(all_records.image_id.map(expected))
    axis_columns = [c for c in images if c not in all_records or c == 'image_id']
    all_records = all_records.merge(images[axis_columns], on='image_id', validate='many_to_one', how='left')
    assert all_records.special_layer.notna().all()
    all_records['reference_id'] = all_records.reference_id.fillna('')
    all_records['use_panel'] = all_records.use_panel.fillna('not_scored')
    for c in ['in_worker_931', 'in_target_836']:
        all_records[c] = all_records[c].eq(True)
    for c in METRICS:
        all_records[c] = pd.to_numeric(all_records[c], errors='raise')
    panels = dict(inventory_3152=all_records,
                  scored_1145=all_records[all_records.WQ.notna()],
                  worker_931=all_records[all_records.in_worker_931],
                  target_836=all_records[all_records.in_target_836])
    qpanels = {k: v for k, v in panels.items() if k != 'inventory_3152'}
    tables = {'records': all_records, 'overview': summaries(panels, []), 'images': images}
    partial = []
    for keys, cell in all_records.groupby(['ledger_score_status', 'condition'], dropna=False):
        bound = cell.copy()
        bound['reference_id'] = bound.ledger_reference_id
        for field in ['iou_2d', 'S_bottom_deg', 'dir', 'floor_WQ', 'IoU3D100', 'WQ']:
            partial.append(dict(ledger_score_status=keys[0], condition=keys[1],
                                **describe(bound, 'ledger_'+field)))
    tables['ledger_metric_coverage'] = pd.DataFrame(partial)
    for name, dims in [('by_image', ['image_code']), ('by_worker', ['worker_id']),
                       ('by_building', ['building_id']), ('by_difficulty', ['difficulty_class']),
                       ('by_condition', ['condition']), ('by_use', ['use_panel']),
                       ('by_ledger_status', ['ledger_score_status']),
                       ('by_room_type', ['room_coarse_type']),
                       ('by_time_status', ['time_status']),
                       ('worker_difficulty', ['worker_id', 'difficulty_class']),
                       ('worker_room_type', ['worker_id', 'room_coarse_type']),
                       ('worker_building', ['worker_id', 'building_id'])]:
        tables[name] = summaries(panels, dims)
    scenes = []
    for axis in ['oos_axis', 'doorway_axis', 'special_layer', 'markability_from_explicit_label',
                 'target_floor_relation', 'top_boundary_pending']:
        t = summaries(panels, [axis]).rename(columns={axis: 'axis_value'})
        t.insert(1, 'axis', axis)
        scenes.append(t)
    tables['by_scene'] = pd.concat(scenes, ignore_index=True)
    worker_scenes = []
    for axis in ['oos_axis', 'doorway_axis', 'special_layer']:
        t = summaries(panels, ['worker_id', axis]).rename(columns={axis: 'axis_value'})
        t.insert(1, 'axis', axis)
        worker_scenes.append(t)
    tables['worker_scene'] = pd.concat(worker_scenes, ignore_index=True)
    tables['by_scene_intersections'] = summaries(panels, ['difficulty_class', 'oos_axis', 'doorway_axis'])
    tables['scene_intersections'] = images.groupby(['difficulty_class', 'oos_axis', 'doorway_axis',
        'markability_from_explicit_label'], dropna=False).agg(n_images=('image_id', 'size'),
        n_scored_records=('joint_quality_count', lambda x: pd.to_numeric(x).sum())).reset_index()
    tables['score_comparison'], tables['peer_records'], tables['worker_peer_comparison'] = comparison_tables(qpanels)
    correlations = []
    for name, panel in qpanels.items():
        for keys, group in [(('all', 'all'), panel)] + list(panel.groupby(['difficulty_class', 'condition'])):
            for metric in ['WQ', 'A10', 'B8L2', 'IoU3D100']:
                cell = group[[metric, 'active_time_seconds']].dropna()
                correlations.append(dict(panel=name, difficulty_class=keys[0], condition=keys[1], metric=metric,
                    n_valid=len(cell), n_missing=len(group)-len(cell), n_images=group.image_id.nunique(),
                    spearman=cell.corr(method='spearman').iloc[0, 1] if len(cell)>1 else None))
    tables['time_quality'] = pd.DataFrame(correlations)
    # 同房主表采用836；931旧参考另表，不混合两种范围资格。
    for name in ['target_836', 'worker_931']:
        records = panels[name].assign(object_uid=lambda x: x.object_id, iou_3d=lambda x: x.IoU3D100/100)
        for key, rows in build_same_room_tables(records.replace({np.nan: None}).to_dict('records')).items():
            tables[key + ('_931' if name == 'worker_931' else '')] = pd.DataFrame(rows)
    time_pool = all_records[all_records.independent_vote_eligible & all_records.condition.eq('manual')]
    time_records = time_pool.assign(object_uid=lambda x: x.object_id, iou_3d=lambda x: x.IoU3D100/100)
    for key, rows in build_same_room_tables(time_records.replace({np.nan: None}).to_dict('records')).items():
        tables[key+'_manual_inventory'] = pd.DataFrame(rows)
    return tables


def write_tables(tables, out):
    out.mkdir(parents=True, exist_ok=True)
    schema = {}
    for name, table in tables.items():
        table = table.copy()
        for c in table:
            if table[c].map(lambda x: isinstance(x, (list, dict, tuple))).any():
                table[c] = table[c].map(lambda x: json.dumps(x, ensure_ascii=False) if isinstance(x, (list, dict, tuple)) else x)
        table.to_csv(out / (name + '.csv'), index=False, encoding='utf-8-sig')
        schema[name] = dict(rows=len(table), columns=list(table.columns))
    payload = {name: json.loads(t.to_json(orient='records', force_ascii=False)) for name, t in tables.items()}
    (out/'tables.json').write_text(json.dumps(payload, ensure_ascii=False, allow_nan=False), encoding='utf-8')
    contract = dict(version='descriptive_statistics_20261015_v1', protocol='consensus_research_20260923_v1',
        sources=[QPATH, APATH, IPATH, PPATH, 'analysis_results/research_input_20260929/manifest.json',
                 'research/quality_joint_closeout_review_20261015/pro_closeout_delta.zip',
                 'analysis_results/uncertainty_cloud_inputs_20260906_v1/facts/active_time_context.csv.gz',
                 'analysis_results/uncertainty_cloud_inputs_20260906_v1/facts/annotation_spine.csv.gz'],
        panels={'inventory':3152, 'scores':1145, 'workers':931, 'same_target':836},
        metrics=METRICS, time_unit='seconds; valid active time only; lead_time fallback excluded',
        score_versions={'WQ':'WQ-LS08-20261014','A10':'WQ-A10-20261015','B8L2':'WQ-B8L2-20261015'},
        iou_units={'IoU3D100':'0-100; mean-height prism','same_room_iou_3d':'0-1; same score divided by 100'},
        room_type='recorded spatial coarse type, not a confirmed physical room ID',
        partial_metrics='ledger_* preserves original 3152 ledger metrics/reference including floor-only; never merged into the 1145 full score panel',
        same_room_manual_inventory='independent_vote_eligible manual only; supports time outside scored panels; no new quality eligibility',
        missing='CSV blank / JSON null; never zero imputation', sd='sample ddof=1; singleton missing',
        quantiles='pandas linear interpolation', weighting='row mean; image_equal_mean also reported',
        comparison='same input and bound reference; no parameter fitting or reference selection',
        tables=schema)
    (out/'FIELD_CONTRACT.json').write_text(json.dumps(contract, ensure_ascii=False, indent=2), encoding='utf-8')
    records = tables['records']
    checks = dict(snapshot_geometry_equals_scoring_source=True, score_join='one_to_one; source identity and bound reference checked',
        inventory_records=len(records), inventory_images=records.image_id.nunique(),
        inventory_workers=records.worker_id.nunique(), inventory_buildings=records.building_id.nunique(),
        quality_rows=int(records.WQ.notna().sum()), worker_rows=int(records.in_worker_931.sum()),
        target_rows=int(records.in_target_836.sum()), difficulty_missing=int(records.difficulty_class.isna().sum()),
        valid_active_time=int(records.active_time_seconds.notna().sum()), time_status=records.time_status.value_counts().to_dict(),
        same_person_image_extra=int(records.duplicated(['worker_id','image_id']).sum()),
        same_person_image_condition_extra=int(records.duplicated(['worker_id','image_id','condition']).sum()),
        room_relations=tables['same_room_relations'].relation.value_counts().to_dict(),
        source_mutation=False, rescoring=False, parameter_tuning=False, new_fusion=False)
    assert checks['difficulty_missing'] == 0
    assert records.loc[records.time_status.ne('usable'), 'active_time_seconds'].isna().all()
    assert records.loc[records.time_status.eq('usable'), 'active_time_seconds'].gt(0).all()
    for key, table in tables.items():
        if key.startswith('same_room_relations'):
            assert table[['building_a','building_b','image_code_a','image_code_b']].notna().all().all()
    (out/'CHECKS.json').write_text(json.dumps(checks, ensure_ascii=False, indent=2), encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    tables = build_tables()
    write_tables(tables, args.out)
    from .descriptive_statistics_report_20261015 import write_report
    write_report(tables, args.out)
    print(json.dumps({name: len(table) for name, table in tables.items()}, ensure_ascii=False))


if __name__ == '__main__':
    main()
