"""Prepare descriptive human/Bi comparisons; never replace original point order.

python -m tools.thesis_main.analysis.prepare_human_bi_comparisons_20260908 --out PATH
"""
from __future__ import annotations

import argparse
import io
import json
from pathlib import Path
import warnings

import numpy as np
import pandas as pd
from shapely.geometry import Polygon

from tools.thesis_main.analysis.audit_bilayout_precision import floor_gap, pixel_uv
from tools.thesis_main.analysis.analyze_uncertainty_handoff import historical_pair_ids, rho, user_bottom_order
from tools.thesis_main.analysis.prepare_uncertainty_visual_review import helpers, ROOT

REPRESENTATIONS = ('legacy_integer', 'pixel_center_integer', 'native_uv')
READINGS = ('serialized_adjacency', 'historical_pairmap_unaveraged')


def native_floor_polygon(uv):
    """Native UV in audit.footprint's axes, not the reflected floor_gap axes."""
    uv = np.asarray(uv, float)
    floor_gap(uv, uv)  # Reuse validation without changing adjacency.
    radius = 1 / np.tan(np.pi * (uv[:, 1] - .5))
    azimuth = 2 * np.pi * uv[:, 0]
    return Polygon(np.c_[-radius * np.sin(azimuth), radius * np.cos(azimuth)])


def evaluated(fn, value):
    try:
        return fn(value), 'computable'
    except (ValueError, IndexError, TypeError) as exc:
        return None, str(exc)


def captured(fn):
    """Retain numerical warnings as evidence, rather than discarding them."""
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always', RuntimeWarning)
        value = fn()
    return value, '; '.join(dict.fromkeys(str(w.message) for w in caught))


def comparison(audit, human, head_e, head_x):
    hp, hs = human
    ep, es = head_e
    xp, xs = head_x
    values, warning = captured(lambda: (
        audit.dp(hp, ep) if hp is not None and ep is not None else np.nan,
        audit.dp(hp, xp) if hp is not None and xp is not None else np.nan,
        audit.dp(ep, xp) if ep is not None and xp is not None else np.nan))
    de, dx, db = values
    both = np.isfinite(de) and np.isfinite(dx)
    return dict(human_status=hs, enclosed_status=es, extended_status=xs,
                comparison_status='computable' if both else 'not_computable',
                d_enclosed=de, d_extended=dx, d_bi=db,
                delta_enclosed_minus_extended=de-dx if both else np.nan,
                minimum_residual=min(de, dx) if both else np.nan,
                numeric_warning=warning)


def main(out):
    out.mkdir(parents=True, exist_ok=True)
    audit, _ = helpers()
    annotations, _, _, _, _, models, _, raw, _ = audit.load()
    assert annotations.canonical_annotation_id.is_unique
    assert not annotations.duplicated(['context_key', 'worker_id']).any()
    cache, model_rows, warning_rows = {}, [], []
    checked = 0
    for model in models:
        if model['model_family'] != 'Bi-Layout':
            continue
        image, head = model['image_id'], model['head']
        p = np.asarray(model['points_1024x512'], float)
        uv = np.loadtxt(io.StringIO(model['floor_uv_text']), ndmin=2)
        for representation in REPRESENTATIONS:
            fn, values = (native_floor_polygon, uv) if representation == 'native_uv' else (audit.footprint, p + (.5 if representation == 'pixel_center_integer' else 0))
            key = image, representation, head
            assert key not in cache
            cache[key], warning = captured(lambda: evaluated(fn, values))
            if warning:
                warning_rows.append(dict(image_id=image, head=head, representation=representation,
                                         step='model_polygon_reading', numeric_warning=warning,
                                         finite_bounded_result=cache[key][0] is not None))
        # This compares actual polygons in the SAME axes; matching model-model
        # IoUs alone would miss a reflection in human-model comparisons.
        actual, status = cache[image, 'pixel_center_integer', head]
        (independently_read, independent_status), warning = captured(lambda: evaluated(native_floor_polygon, pixel_uv(p[1::2])))
        if warning:
            warning_rows.append(dict(image_id=image, head=head, representation='pixel_center_integer',
                                     step='independent_polygon_reading', numeric_warning=warning,
                                     finite_bounded_result=independently_read is not None))
        assert (actual is None) == (independently_read is None), (image, status, independent_status)
        if actual is not None:
            self_gap, warning = captured(lambda: audit.dp(actual, independently_read))
            if warning:
                warning_rows.append(dict(image_id=image, head=head, representation='pixel_center_integer',
                                         step='same_axis_polygon_check', numeric_warning=warning,
                                         finite_bounded_result=np.isfinite(self_gap) and -1e-12 <= self_gap <= 1+1e-12))
            assert self_gap < 1e-10, image
            checked += 1
    for image in sorted({k[0] for k in cache}):
        for rep in REPRESENTATIONS:
            e, x = cache[image, rep, 'enclosed'], cache[image, rep, 'extended']
            gap, warning = captured(lambda: audit.dp(e[0], x[0]) if e[0] is not None and x[0] is not None else np.nan)
            if warning:
                warning_rows.append(dict(image_id=image, head='both', representation=rep,
                                         step='model_head_comparison', numeric_warning=warning,
                                         finite_bounded_result=np.isfinite(gap) and -1e-12 <= gap <= 1+1e-12))
            model_rows.append(dict(image_id=image, representation=rep,
                                   enclosed_status=e[1], extended_status=x[1],
                                   d_bi=gap, numeric_warning=warning))
    model_frame = pd.DataFrame(model_rows)
    model_frame.to_csv(out/'model_floor_comparisons.csv', index=False)
    rows, mapping_rows = [], []
    for record in annotations.to_dict('records'):
        identity = record['canonical_annotation_id']
        points = np.asarray(raw[identity]['points_1024x512'], float)
        metadata = {k: record[k] for k in ['canonical_annotation_id', 'context_key', 'image_id', 'worker_id', 'stage', 'block_index', 'raw_condition', 'building_id', 'current20_member']}
        for reading in READINGS:
            try:
                ids = list(range(len(points))) if reading == READINGS[0] else historical_pair_ids(points)
                human = evaluated(audit.footprint, points[ids])
            except ValueError as exc:
                ids, human = [], (None, str(exc))
            mapping_rows.append(dict(**metadata, reading=reading, raw_point_ids=json.dumps(ids), human_status=human[1], coordinates_changed=False, author_adjacency_verified=False))
            for rep in REPRESENTATIONS:
                rows.append(dict(**metadata, reading=reading, representation=rep,
                                 **comparison(audit, human, cache[record['image_id'], rep, 'enclosed'], cache[record['image_id'], rep, 'extended'])))
    frame = pd.DataFrame(rows)
    assert len(frame) == len(annotations)*len(READINGS)*len(REPRESENTATIONS)
    assert not frame.duplicated(['canonical_annotation_id', 'reading', 'representation']).any()
    valid = frame[frame.comparison_status=='computable']
    for column in ['d_enclosed', 'd_extended', 'd_bi', 'minimum_residual']:
        assert np.isfinite(valid[column]).all()
        assert valid[column].between(-1e-12, 1+1e-12).all()
    assert (valid.delta_enclosed_minus_extended.abs() <= valid.d_bi + 1e-10).all()
    frame.to_csv(out/'human_bi_comparisons.csv.gz', index=False)
    pd.DataFrame(mapping_rows).to_csv(out/'human_reading_maps.csv.gz', index=False)

    source = ROOT/'analysis_results/uncertainty_followup_analysis_20260908_v1'
    confirmations = json.loads((source/'confirmed_20260908/user_confirmations.json').read_text(encoding='utf-8'))
    derivatives = []
    for c in confirmations:
        points = np.asarray(c['raw_points'], float)
        ids = user_bottom_order(points, c['user_bottom_order'])
        assert ids == c['raw_point_ids']
        assert np.array_equal(points[ids], c['derived_points'])
        identity = c['canonical_annotation_id']
        if identity:
            # Percent*10.24 and percent/100*1024 differ at machine precision.
            assert np.allclose(points, raw[identity]['points_1024x512'], atol=1e-10, rtol=0)
            assert annotations.set_index('canonical_annotation_id').loc[identity, 'image_id'] == c['image_id']
        for rep in REPRESENTATIONS:
            derivatives.append(dict(case_id=c['case_id'], canonical_annotation_id=identity,
                                    annotation_id=c['annotation_id'], task_id=c['task_id'], source=c['source'], image_id=c['image_id'],
                                    source_kind='canonical_response' if identity else 'reference',
                                    reading='user_confirmed_order', representation=rep,
                                    raw_point_ids=json.dumps(ids), coordinates_changed=False,
                                    is_final_geometry_adjudication=False,
                                    **comparison(audit, evaluated(audit.footprint, points[ids]), cache[c['image_id'], rep, 'enclosed'], cache[c['image_id'], rep, 'extended'])))
    pd.DataFrame(derivatives).to_csv(out/'user_confirmed_derivatives.csv', index=False)
    for collection, step in [(rows, 'canonical_human_model_comparison'), (derivatives, 'confirmed_derivative_comparison')]:
        for r in collection:
            if r['numeric_warning']:
                distances = [r[k] for k in ['d_enclosed','d_extended','d_bi']]
                warning_rows.append(dict(image_id=r['image_id'], canonical_annotation_id=r.get('canonical_annotation_id'),
                                         case_id=r.get('case_id'), reading=r['reading'], representation=r['representation'],
                                         step=step, numeric_warning=r['numeric_warning'],
                                         finite_bounded_result=all(np.isfinite(v) and -1e-12 <= v <= 1+1e-12 for v in distances)))
    pd.DataFrame(warning_rows, columns=['image_id','canonical_annotation_id','case_id','head','reading','representation','step','numeric_warning','finite_bounded_result']).to_csv(out/'numeric_warnings.csv', index=False)
    # Fixed previous human-human measurements; all three head representations
    # use the same context denominator within each reading/stratum.
    contexts = pd.read_csv(source/'context_distances.csv')
    contexts = contexts[(contexts.metric=='floor') & (contexts.pool=='all_historical') & (contexts.cohort=='method_available')].copy()
    wide = model_frame.pivot(index='image_id', columns='representation', values='d_bi').reset_index()
    contexts = contexts.merge(wide, on='image_id', validate='many_to_one')
    ok = contexts.bi_distance.notna() & contexts.legacy_integer.notna()
    assert np.allclose(contexts.loc[ok, 'bi_distance'], contexts.loc[ok, 'legacy_integer'], atol=1e-12, rtol=0)
    contexts['common_computable'] = contexts[['human_distance', *REPRESENTATIONS]].notna().all(axis=1)
    contexts.to_csv(out/'context_precision_sensitivity.csv', index=False)
    associations = []
    for method, group in contexts.groupby('method'):
        strata = [('all', group)] + [(f'{s}|{c}', g) for (s,c), g in group.groupby(['stage','condition'])]
        for stratum, g in strata:
            for support in (2, 3, 5):
                z = g[g.common_computable & (g.calculable_support>=support)]
                for rep in REPRESENTATIONS:
                    associations.append(dict(reading=method, stratum=stratum, minimum_calculable_people=support,
                                             representation=rep, contexts=len(z), images=z.image_id.nunique(),
                                             buildings=z.building_id.nunique(), spearman_rho=rho(z[rep], z.human_distance)))
    pd.DataFrame(associations).to_csv(out/'descriptive_associations.csv', index=False)
    sensitivity = []
    for reading, group in frame.groupby('reading'):
        w = group.pivot(index='canonical_annotation_id', columns='representation', values=['d_enclosed','d_extended','delta_enclosed_minus_extended','minimum_residual'])
        common = w.dropna()
        for rep in REPRESENTATIONS[1:]:
            old, new = common['delta_enclosed_minus_extended']['legacy_integer'], common['delta_enclosed_minus_extended'][rep]
            opposite = old*new < 0
            sign_old = np.where(old.abs() <= 1e-12, 0, np.sign(old))
            sign_new = np.where(new.abs() <= 1e-12, 0, np.sign(new))
            amplitude = pd.concat([old.abs(),new.abs()], axis=1).max(axis=1)
            robust_opposite = sign_old*sign_new < 0
            sensitivity.append(dict(reading=reading, representation=rep, common_canonical=len(common),
                                    strict_preference_sign_changed=int((np.sign(old)!=np.sign(new)).sum()),
                                    old_exact_zero=int((old==0).sum()), new_exact_zero=int((new==0).sum()),
                                    opposing_nonzero_signs=int((old*new<0).sum()),
                                    numeric_zero_tolerance=1e-12,
                                    numeric_zero_old=int((sign_old==0).sum()), numeric_zero_new=int((sign_new==0).sum()),
                                    preference_sign_changed_with_numeric_zero=int((sign_old!=sign_new).sum()),
                                    opposing_nonzero_signs_with_numeric_zero=int(robust_opposite.sum()),
                                    opposing_sign_max_absolute_delta_median=float(amplitude[opposite].median()),
                                    opposing_sign_max_absolute_delta_p90=float(amplitude[opposite].quantile(.9)),
                                    numeric_opposing_sign_max_absolute_delta_median=float(amplitude[robust_opposite].median()),
                                    numeric_opposing_sign_max_absolute_delta_p90=float(amplitude[robust_opposite].quantile(.9)),
                                    max_absolute_delta_change=float((new-old).abs().max()),
                                    median_absolute_delta_change=float((new-old).abs().median())))
    pd.DataFrame(sensitivity).to_csv(out/'response_precision_sensitivity.csv', index=False)
    summary = frame.groupby(['reading','representation','comparison_status']).size().rename('rows').reset_index()
    summary.to_csv(out/'comparison_coverage.csv', index=False)
    qa = dict(canonical_rows=len(annotations), response_rows=len(frame), reading_maps=len(mapping_rows),
              model_images=model_frame.image_id.nunique(), same_axis_pixel_center_polygons_checked=checked,
              finite_bounded_comparison_rows_checked=len(valid), triangle_difference_bound_checked=True,
              numeric_warning_records=len(warning_rows),
              numeric_warning_images=len({r['image_id'] for r in warning_rows}),
              numeric_warning_steps=pd.Series([r['step'] for r in warning_rows], dtype=str).value_counts().to_dict(),
              numeric_warning_results_finite_bounded=all(r['finite_bounded_result'] for r in warning_rows),
              user_confirmed_canonical_derivatives=sum(r['source_kind']=='canonical_response' for r in derivatives),
              user_confirmed_reference_derivatives=sum(r['source_kind']=='reference' for r in derivatives),
              human_coordinates_shifted=False, original_order_overwritten=False,
              semantic_worker_labels_created=False, significance_tests_performed=False)
    (out/'QA.json').write_text(json.dumps(qa, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(qa, ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    main(parser.parse_args().out)
