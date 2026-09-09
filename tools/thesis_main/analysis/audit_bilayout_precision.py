"""审查保存的 Bi 浮点/整数坐标及历史人员覆盖；不改变源数据或建立工人类别。

python -m tools.thesis_main.analysis.audit_bilayout_precision --out RESULTS
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import io
import json
from pathlib import Path

import numpy as np
import pandas as pd
from shapely.geometry import Point, Polygon


def pixel_uv(points):
    """仅用于 Bi 导出器的像素中心约定，不用于真人连续百分比坐标。"""
    return (np.asarray(points, dtype=float) + 0.5) / [1024, 512]


def floor_gap(first, second):
    """同相机高度的浮点地面 1-IoU；保留输入邻接，不读取/判断天花板。"""
    polygons = []
    for values in (first, second):
        p = np.asarray(values, dtype=float)
        if p.ndim != 2 or p.shape[1] != 2 or len(p) < 3:
            raise ValueError('insufficient_floor_points')
        if not np.isfinite(p).all() or np.any(p < 0) or np.any(p > 1):
            raise ValueError('invalid_uv')
        latitude = np.pi * (p[:, 1] - 0.5)
        if np.any(np.sin(latitude) <= 1e-5):
            raise ValueError('not_below_horizon_or_near_horizon')
        radius = 1 / np.tan(latitude)
        azimuth = 2 * np.pi * p[:, 0]
        polygon = Polygon(np.c_[radius * np.sin(azimuth), radius * np.cos(azimuth)])
        if not polygon.is_valid or polygon.area < 1e-10:
            raise ValueError('invalid_floor_polygon')
        if not polygon.contains(Point(0, 0)):
            raise ValueError('camera_outside')
        polygons.append(polygon)
    p, q = polygons
    return float(1 - p.intersection(q).area / p.union(q).area)


def main(out):
    from tools.thesis_main.analysis.prepare_uncertainty_visual_review import helpers

    out.mkdir(parents=True, exist_ok=True)
    audit, _ = helpers()
    annotations, _, _, _, _, models, *_ = audit.load()
    assert annotations.canonical_annotation_id.is_unique
    assert not annotations.duplicated(['context_key', 'worker_id']).any()
    historical = set(annotations.image_id)
    by_image = defaultdict(dict)
    for m in models:
        if m['model_family'] == 'Bi-Layout':
            assert m['head'] not in by_image[m['image_id']]
            by_image[m['image_id']][m['head']] = m
    rows = []
    for image_id, heads in sorted(by_image.items()):
        assert set(heads) == {'enclosed', 'extended'}
        uv = [np.loadtxt(io.StringIO(heads[h]['floor_uv_text']), ndmin=2)
              for h in ('enclosed', 'extended')]
        points = [np.asarray(heads[h]['points_1024x512'], dtype=float)
                  for h in ('enclosed', 'extended')]
        for native, serialized in zip(uv, points):
            expected = np.round(native * [1024, 512] - 0.5)
            expected[:, 0] %= 1024
            expected[:, 1] = np.clip(expected[:, 1], 0, 511)
            assert np.array_equal(expected, serialized[1::2]), image_id
        equal = np.array_equal(*points)
        row = dict(image_id=image_id, historical=image_id in historical,
                   integer_sequence_equal=equal, native_uv_sequence_equal=np.array_equal(*uv),
                   native_uv_cycle_equal=uv[0].shape == uv[1].shape and any(
                       np.array_equal(uv[0], np.roll(z, k, axis=0))
                       for z in (uv[1], uv[1][::-1]) for k in range(len(z))))
        for name, values in [('legacy_integer', points),
                             ('pixel_center_integer', [p + 0.5 for p in points]),
                             ('native_uv', uv)]:
            try:
                d = (floor_gap(*values) if name == 'native_uv' else
                     audit.dp(*[audit.footprint(p) for p in values]))
                row[name + '_floor'] = d
                row[name + '_status'] = 'computable'
            except ValueError as e:
                row[name + '_floor'] = np.nan
                row[name + '_status'] = str(e)
        if row['pixel_center_integer_status'] == 'computable':
            independent = floor_gap(*[pixel_uv(p[1::2]) for p in points])
            assert np.isclose(independent, row['pixel_center_integer_floor'], atol=1e-12, rtol=0)
        if equal:
            delta = uv[0] - uv[1]
            delta[:, 0] = (delta[:, 0] + 0.5) % 1 - 0.5
            row['max_native_coordinate_difference_pixels_when_integer_equal'] = float(
                np.abs(delta * [1024, 512]).max())
        rows.append(row)
    data = pd.DataFrame(rows)
    data.to_csv(out / 'model_precision.csv', index=False)
    summaries = []
    for cohort, group in [('all_workset', data), ('historical', data[data.historical]),
                          ('candidate', data[~data.historical])]:
        for representation in ('legacy_integer', 'pixel_center_integer', 'native_uv'):
            distances = group[representation + '_floor'].dropna()
            summaries.append(dict(cohort=cohort, representation=representation, images=len(group),
                                  computable=len(distances), zero_within_1e12=int((distances.abs() <= 1e-12).sum()),
                                  le_0p01=int((distances <= 0.01).sum()), le_0p05=int((distances <= 0.05).sum()),
                                  median=distances.median(), p90=distances.quantile(0.9)))
    pd.DataFrame(summaries).to_csv(out / 'precision_summary.csv', index=False)

    merged = annotations.merge(data, on='image_id', how='left', validate='many_to_one')
    assert merged.integer_sequence_equal.notna().all()
    coverage = []
    for worker, group in merged.groupby('worker_id'):
        manual = group[group.raw_condition == 'manual']
        separated = manual[manual.legacy_integer_floor > 0.05]
        assert group.current20_member.nunique() == 1
        coverage.append(dict(worker_id=worker, current20_member=audit.yes(group.current20_member.iloc[0]),
                             canonical_rows=len(group), manual_rows=len(manual),
                             manual_images=manual.image_id.nunique(), manual_buildings=manual.building_id.nunique(),
                             semi_rows=int((group.raw_condition == 'semi').sum()),
                             oos_rows=int((group.raw_condition == 'oos').sum()),
                             manual_integer_equal_images=manual[manual.integer_sequence_equal].image_id.nunique(),
                             manual_legacy_gap_over_0p05_images=separated.image_id.nunique(),
                             manual_legacy_gap_over_0p05_buildings=separated.building_id.nunique()))
    workers = pd.DataFrame(coverage).sort_values('worker_id', key=lambda s: s.astype(int))
    assert workers.canonical_rows.sum() == len(annotations)
    workers.to_csv(out / 'worker_coverage.csv', index=False)
    equal_rows = data[data.integer_sequence_equal]
    qa = dict(canonical_rows=len(annotations), historical_images=len(historical), workers=len(workers),
              conditions=annotations.raw_condition.value_counts().to_dict(),
              bi_images=len(data), verified_native_floor_to_integer_exports=2 * len(data),
              integer_sequence_equal=len(equal_rows), native_uv_sequence_equal=int(data.native_uv_sequence_equal.sum()),
              native_uv_cycle_equal=int(data.native_uv_cycle_equal.sum()),
              integer_equal_native_floor_gap_quantiles=equal_rows.native_uv_floor.quantile([0, .5, .9, 1]).to_dict(),
              integer_equal_max_native_coordinate_difference_pixels=float(equal_rows[
                  'max_native_coordinate_difference_pixels_when_integer_equal'].max()),
              meaning='descriptive_precision_and_coverage_audit_not_semantic_thresholds_or_worker_classes',
              original_data_modified=False, neural_inference_runs=0)
    (out / 'PRECISION_QA.json').write_text(json.dumps(qa, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(qa, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    main(parser.parse_args().out)
