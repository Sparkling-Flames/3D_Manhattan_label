#!/usr/bin/env python3
"""Equivalent grouped-mask execution engine for the frozen response analysis.

No statistical changes: import original feature, centering, weights, descriptive
variance, output and summary functions. Only reuse X/weights/norms/Gram across
outcomes with exactly the same train and target masks, and use several RHSs.

Validation outputs default to this directory. Production use requires explicit
`run --out <original output dir>` and is intended after original runner stops.
"""
from __future__ import annotations
import os
for _k in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[_k] = '1'
import argparse
import hashlib
import importlib.util
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
V3 = HERE.parents[1]
ORIGINAL = V3 / 'response/analyze_responses.py'
EXPECTED_ORIGINAL_SHA = '20d6e3e7bff7bbff21cb703915557d6c364050a2141370de8767d79a613088aa'
spec = importlib.util.spec_from_file_location('frozen_response_analysis', ORIGINAL)
orig = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(orig)
assert orig.sha(ORIGINAL) == EXPECTED_ORIGINAL_SHA, 'Frozen source changed; do not silently adapt.'


def load_main_panels(condition):
    """Original load contract restricted to matching main batch expressions.

    Original completed analyses had only batch_* expressions. Later f01_* and
    other supplements can repeat main team keys; they are outside PANELS.csv
    and its main score inventory. Restrict geometries to the exact same batch
    names that supply the scores, rather than merging unrelated inventories.
    All remaining operations are unchanged from frozen `orig.load`.
    """
    panels = pd.read_csv(orig.COMP/'PANELS.csv')
    panels = panels[panels.condition.eq(condition)].copy()
    teams = pd.read_csv(orig.COMP/'DESIGN_TEAMS.csv.gz', usecols=['team_key', 'member_workers'])
    mem = pd.read_csv(orig.COMP/'PANEL_MEMBERSHIP.csv.gz', usecols=['panel_id', 'team_key'])
    frame = mem.merge(panels, on='panel_id', validate='many_to_one').merge(teams, on='team_key', validate='many_to_one')
    frame = frame[frame.condition.eq(condition)].copy()
    need, scores, geos = set(frame.team_key), [], []
    score_batches = []
    for p in sorted((orig.COMP/'batches').glob('batch_*/ENDPOINT_SCALARS.csv.gz')):
        if not (p.parent/'COMPLETION.json').exists():
            continue
        score_batches.append(p.parent.name)
        d = pd.read_csv(p, low_memory=False)
        d = d[d.team_key.isin(need)]
        if len(d):
            scores.append(d)
    for batch in score_batches:
        p = orig.HERE/'geometry_batches'/f'{batch}_EXPRESSION.csv.gz'
        if not p.exists():
            continue
        d = pd.read_csv(p)
        d = d[d.team_key.isin(need)]
        if len(d):
            geos.append(d)
    scores = pd.concat(scores, ignore_index=True)
    assert not scores.team_key.duplicated().any()
    assert set(scores.team_key) == need, ('unfinished', len(need-set(scores.team_key)))
    g = pd.concat(geos, ignore_index=True)
    assert not g.team_key.duplicated().any()
    assert set(g.team_key) == need
    scores['failure'] = (~scores.complete_evaluable.astype(bool)).astype(float)
    scores['log_geometry_area'] = np.log(scores.geometry_area_h2.where(scores.geometry_area_h2.gt(0)))
    ok = scores.source_time_known_n.eq(scores.k) & scores.source_time_total_seconds.gt(0) & scores.time_source_kinds.fillna('').ne('') & ~scores.time_source_kinds.fillna('').str.contains('|', regex=False)
    scores['log_source_time'] = np.log(scores.source_time_total_seconds.where(ok))
    scores = scores.merge(g, on='team_key', validate='one_to_one')
    for c in orig.YCOLS:
        if c not in scores:
            scores[c] = np.nan
    frame = frame.merge(scores[['team_key']+orig.YCOLS], on='team_key', validate='many_to_one').reset_index(drop=True)
    assert frame.groupby('panel_id').size().eq(924).all()
    roster = sorted({w for ss in frame.member_workers for w in ss.split('|')})
    ix = {w: i for i, w in enumerate(roster)}
    count = np.zeros((len(frame), len(roster)), dtype=np.uint8)
    for i, ss in enumerate(frame.member_workers):
        for w in ss.split('|'):
            count[i, ix[w]] = 1
    assert np.array_equal(count.sum(axis=1), frame.n)
    return frame, panels, roster, count


def fit_building(frame, roster, count, source, condition, domain, build):
    started = time.monotonic()
    xp, models, names, valid, blocks, phi = orig.feature_matrix(roster, count, frame, build, source, domain)
    target = valid & frame.building.eq(build).to_numpy()
    train = valid & ~frame.building.eq(build).to_numpy()
    ft = frame.loc[target].reset_index(drop=True)
    xx = xp[target]
    ct = count[target]
    cv = dict(condition=condition, domain=domain, building=build,
              valid_target_rows=int(target.sum()), target_panels=ft.panel_id.nunique(),
              all_target_rows=int(frame.building.eq(build).sum()),
              valid_train_rows=int(train.sum()), known_workers=int((phi.sum(axis=1) != 0).sum()))
    if not target.any() or not train.any():
        return [], [], [], cv, dict(seconds=time.monotonic()-started, has_results=False)
    desc = orig.describe(ft, ct, phi, blocks, condition, domain, build)
    del ct, phi

    # Equality is exact at the row-mask level. Panel >=2 exclusions are then
    # identical within a group; there is no union/imputation of outcome support.
    masks = {}
    for outcome in orig.YCOLS:
        tr = train & frame[outcome].notna().to_numpy()
        te = ft[outcome].notna().to_numpy()
        key = (tr.tobytes(), te.tobytes())
        if key not in masks:
            masks[key] = dict(tr=tr, te=te, outcomes=[])
        masks[key]['outcomes'].append(outcome)

    b_rows, b_fits, diagnostics = [], [], []
    for mask_id, mask in enumerate(masks.values()):
        tr, te, outcomes = mask['tr'], mask['te'], mask['outcomes']
        a = frame.loc[tr].copy()
        train_positions = np.flatnonzero(tr)
        enough = a.groupby('panel_id').panel_id.transform('size').ge(2).to_numpy()
        a = a.loc[enough]
        train_positions = train_positions[enough]
        z = ft.loc[te].copy()
        target_positions = np.flatnonzero(te)
        enough = z.groupby('panel_id').panel_id.transform('size').ge(2).to_numpy()
        z = z.loc[enough]
        target_positions = target_positions[enough]
        if len(a) < 2 or len(z) < 2 or a.building.nunique() < 3:
            diagnostics.append(dict(mask_id=mask_id, outcomes=outcomes, skipped=True,
                                    train_rows=len(a), target_rows=len(z)))
            continue
        co, _ = pd.factorize(a.panel_id)
        tc, _ = pd.factorize(z.panel_id)
        # Use original center (including its summation order). Fortran order
        # then matches the contiguous-column norm used by original xa[:,ix].
        raw_xa = orig.center(xp[train_positions], co)
        raw_xz = orig.center(xx[target_positions], tc)
        xa = np.array(raw_xa, order='F', copy=True)
        xz = np.array(raw_xz, order='F', copy=True)
        ya = np.column_stack([orig.center(a[o].to_numpy(), co) for o in outcomes])
        yz = np.column_stack([orig.center(z[o].to_numpy(), tc) for o in outcomes])
        w = orig.weights(a)
        scale = np.sqrt((xa * xa * w[:, None]).sum(axis=0))
        active = scale > 1e-10
        scale = np.where(active, scale, 1.)
        xa /= scale
        xa[:, ~active] = 0
        xz /= scale
        xz[:, ~active] = 0
        weighted = xa * w[:, None]
        gram = weighted.T @ xa
        rhs = weighted.T @ ya
        del weighted, xa
        groups = z.groupby('panel_id', sort=False).indices
        train_buildings = a.building.nunique()
        diagnostics.append(dict(mask_id=mask_id, outcomes=outcomes, skipped=False,
                                train_rows=len(a), target_rows=len(z),
                                train_buildings=int(train_buildings), all_features=len(names),
                                active_features=int(active.sum())))
        fallback_pairs = []
        for model, ix in models.items():
            coef = np.linalg.solve(gram[np.ix_(ix, ix)] + orig.RIDGE * np.eye(len(ix)), rhs[ix, :])
            pred = xz[:, ix] @ coef
            for col, outcome in enumerate(outcomes):
                # The original per-panel R² is intentionally retained even
                # when its denominator is near zero. At |R²|>1e5, harmless
                # multi-RHS/BLAS rounding can exceed absolute 1e-8 in R².
                # Re-run only that model/outcome using original scalar-RHS
                # arithmetic. No statistical threshold/metric is modified.
                sensitive = False
                for ii in groups.values():
                    base_var = float(np.mean(yz[ii, col] ** 2))
                    model_mse = float(np.mean((yz[ii, col] - pred[ii, col]) ** 2))
                    if base_var > 1e-12 and model_mse / base_var > 1e5:
                        sensitive = True
                        break
                fit_coef = coef[:, col] / scale[ix]
                if sensitive:
                    v = raw_xa[:, ix]
                    sc = np.sqrt((v*v*w[:, None]).sum(axis=0))
                    ac = sc > 1e-10
                    sc = np.where(ac, sc, 1.)
                    v = v/sc
                    v[:, ~ac] = 0
                    single_y = np.ascontiguousarray(ya[:, col])
                    single_coef = np.linalg.solve((v*w[:, None]).T@v + orig.RIDGE*np.eye(len(ix)),
                                                  (v*w[:, None]).T@single_y)
                    tx = raw_xz[:, ix]/sc
                    tx[:, ~ac] = 0
                    pred[:, col] = tx@single_coef
                    fit_coef = single_coef/sc
                    fallback_pairs.append({'model': model, 'outcome': outcome})
                    del v, tx, single_y, single_coef
                for panel, ii in groups.items():
                    first = z.iloc[ii[0]]
                    base = {k: first[k] for k in ['panel_id', 'pool_id', 'image', 'building', 'condition',
                                                   'difficulty', 'source_domain', 'n']}
                    baseline = float(np.mean(yz[ii, col] ** 2))
                    mse = float(np.mean((yz[ii, col] - pred[ii, col]) ** 2))
                    b_rows.append(dict(base, domain=domain, model=model, outcome=outcome,
                                       teams=len(ii), mse=mse, baseline_mse=baseline,
                                       response_r2=1-mse/baseline if baseline > 1e-12 else np.nan,
                                       mae=float(np.mean(np.abs(yz[ii, col] - pred[ii, col]))),
                                       train_teams=len(a), train_buildings=train_buildings,
                                       active_features=int(active[ix].sum())))
                b_fits.append(dict(condition=condition, domain=domain, heldout_building=build,
                                   outcome=outcome, model=model, ridge=orig.RIDGE,
                                   predictors='|'.join(names[i] for i in ix),
                                   coefficients=json.dumps(fit_coef.tolist()),
                                   train_teams=len(a), train_buildings=train_buildings))
        diagnostics[-1]['original_scalar_rhs_roundoff_fallback'] = fallback_pairs
        del a, z, ya, yz, xz, raw_xa, raw_xz, gram, rhs
    # Preserve original outcome->model->target-panel order for exact interfaces.
    order_y = {v: k for k, v in enumerate(orig.YCOLS)}
    order_m = {v: k for k, v in enumerate(models)}
    panel_order = {v: k for k, v in enumerate(ft.panel_id.unique())}
    b_rows.sort(key=lambda r: (order_y[r['outcome']], order_m[r['model']], panel_order[r['panel_id']]))
    b_fits.sort(key=lambda r: (order_y[r['outcome']], order_m[r['model']]))
    timing = dict(seconds=time.monotonic()-started, has_results=True,
                  outcome_count=len(orig.YCOLS), mask_groups=len(masks), models=len(models),
                  features=len(names), masks=diagnostics)
    return b_rows, desc, b_fits, cv, timing


def save_building(out, build, result):
    rows, desc, fits, cv, timing = result
    bp = out / 'building_batches'
    if timing['has_results']:
        orig.save(pd.DataFrame(rows), bp / f'{build}_PREDICTION.csv.gz')
        orig.save(pd.DataFrame(desc), bp / f'{build}_DECOMPOSITION.csv.gz')
        orig.save(pd.DataFrame(fits), bp / f'{build}_MODELS.csv.gz')
    orig.js(bp / f'{build}_COMPLETE.json',
            dict(code_sha256=EXPECTED_ORIGINAL_SHA, execution_engine_sha256=orig.sha(Path(__file__)),
                 execution_engine='grouped_exact_masks_full_gram_multiple_rhs',
                 support=cv, has_results=timing['has_results'], execution=timing))


def compare_frames(reference, actual, keys, tol, json_arrays=()):
    a, b = reference.sort_values(keys).reset_index(drop=True), actual.sort_values(keys).reset_index(drop=True)
    assert a.columns.tolist() == b.columns.tolist(), ('columns', a.columns.tolist(), b.columns.tolist())
    assert a.shape == b.shape, ('shape', a.shape, b.shape)
    differences, max_error = [], 0.
    for c in a:
        if c in json_arrays:
            aa = [np.asarray(json.loads(v), float) for v in a[c]]
            bb = [np.asarray(json.loads(v), float) for v in b[c]]
            assert all(x.shape == y.shape for x, y in zip(aa, bb)), ('array_shape', c)
            error = max((float(np.max(np.abs(x-y))) if len(x) else 0. for x, y in zip(aa, bb)), default=0.)
            assert all(np.array_equal(np.isnan(x), np.isnan(y)) for x, y in zip(aa, bb)), ('nan_pattern', c)
            ok = error <= tol
        elif pd.api.types.is_numeric_dtype(a[c]) and pd.api.types.is_numeric_dtype(b[c]):
            av, bv = a[c].to_numpy(float), b[c].to_numpy(float)
            assert np.array_equal(np.isnan(av), np.isnan(bv)), ('nan_pattern', c)
            finite = np.isfinite(av) & np.isfinite(bv)
            assert np.array_equal(np.isinf(av), np.isinf(bv)), ('inf_pattern', c)
            error = float(np.max(np.abs(av[finite]-bv[finite]))) if finite.any() else 0.
            ok = error <= tol
        else:
            error = 0.
            ok = a[c].fillna('__NA__').astype(str).equals(b[c].fillna('__NA__').astype(str))
        max_error = max(max_error, error)
        differences.append(dict(column=c, max_abs_error=error, equal_within_tolerance=bool(ok)))
        assert ok, ('not_equivalent', c, error, tol)
    return dict(rows=len(a), columns=len(a.columns), max_abs_error=max_error, columns_checked=differences)


def validate(condition, domain, build, out, tol):
    start = time.monotonic()
    ref = orig.HERE / condition / domain / 'building_batches'
    checkpoint = ref / f'{build}_COMPLETE.json'
    metadata = json.loads(checkpoint.read_text())
    assert metadata['code_sha256'] == EXPECTED_ORIGINAL_SHA and metadata['has_results']
    frame, panels, roster, count = load_main_panels(condition)
    source = orig.inputs(condition)
    result = fit_building(frame, roster, count, source, condition, domain, build)
    save_building(out, build, result)
    rows, desc, fits, cv, timing = result
    assert cv == metadata['support'], ('support_changed', cv, metadata['support'])
    tables = {}
    specs = [('PREDICTION', ['panel_id', 'model', 'outcome'], ()),
             ('DECOMPOSITION', ['panel_id', 'method', 'outcome'], ()),
             ('MODELS', ['heldout_building', 'model', 'outcome'], ('coefficients',))]
    for name, keys, json_arrays in specs:
        original_path = ref / f'{build}_{name}.csv.gz'
        accelerated_path = out / 'building_batches' / f'{build}_{name}.csv.gz'
        original_frame, accelerated_frame = pd.read_csv(original_path), pd.read_csv(accelerated_path)
        checked = compare_frames(original_frame, accelerated_frame, keys, tol, json_arrays)
        checked.update(original_sha256=orig.sha(original_path), accelerated_sha256=orig.sha(accelerated_path))
        tables[name] = checked
    receipt = dict(status='equivalent_within_tolerance', condition=condition, domain=domain, building=build,
                   absolute_tolerance=tol, original_code_sha256=EXPECTED_ORIGINAL_SHA,
                   execution_engine_sha256=orig.sha(Path(__file__)), support=cv, tables=tables,
                   execution=timing, total_seconds=time.monotonic()-start,
                   fusion_calls=0, scoring_calls=0, reference_outputs_modified=False)
    orig.js(out / f'{build}_EQUIVALENCE_RECEIPT.json', receipt)
    print(json.dumps({k: v for k, v in receipt.items() if k not in ['tables', 'execution']}, ensure_ascii=False), flush=True)
    print(json.dumps({k: v['max_abs_error'] for k, v in tables.items()}), flush=True)


def run(condition, domain, out, only_buildings=None, summarize=True):
    start = time.monotonic()
    out.mkdir(parents=True, exist_ok=True)
    frame, panels, roster, count = load_main_panels(condition)
    source = orig.inputs(condition)
    allrows, all_desc, cover, fits = [], [], [], []
    buildings = sorted(frame.building.unique())
    if only_buildings:
        buildings = [b for b in buildings if b in only_buildings]
        summarize = False
    for build in buildings:
        bp = out / 'building_batches' / build
        checkpoint = bp.with_name(build + '_COMPLETE.json')
        if checkpoint.exists():
            cached = json.loads(checkpoint.read_text())
            if cached.get('code_sha256') == EXPECTED_ORIGINAL_SHA:
                cover.append(cached['support'])
                if cached.get('has_results'):
                    for filename, dest in [('PREDICTION.csv.gz', allrows), ('DECOMPOSITION.csv.gz', all_desc), ('MODELS.csv.gz', fits)]:
                        dest.extend(pd.read_csv(bp.with_name(build + '_' + filename)).to_dict('records'))
                print(json.dumps(dict(building=build, resumed=True,
                                     prior_engine=cached.get('execution_engine', 'original_frozen_engine'))), flush=True)
                continue
        result = fit_building(frame, roster, count, source, condition, domain, build)
        save_building(out, build, result)
        br, bd, bf, cv, timing = result
        allrows.extend(br); all_desc.extend(bd); fits.extend(bf); cover.append(cv)
        print(json.dumps(dict(cv, seconds=timing['seconds'], mask_groups=timing.get('mask_groups'))), flush=True)
    if summarize:
        orig.save(pd.DataFrame(allrows), out / 'PANEL_PREDICTION.csv.gz')
        orig.save(pd.DataFrame(all_desc), out / 'PANEL_CONFIGURATION_DECOMPOSITION.csv.gz')
        orig.save(pd.DataFrame(cover), out / 'SUPPORT.csv')
        orig.save(pd.DataFrame(fits), out / 'FITTED_MODELS.csv.gz')
        orig.summarize(out)
    orig.js(out / 'EXECUTION_ENGINE_RECEIPT.json', dict(status='complete' if summarize else 'building_subset_complete',
        original_code_sha256=EXPECTED_ORIGINAL_SHA, execution_engine_sha256=orig.sha(Path(__file__)),
        original_checkpoint_reuse=True, statistical_method_changed=False, buildings=buildings,
        elapsed_seconds=time.monotonic()-start, fusion_calls=0, scoring_calls=0))


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('action', choices=['validate', 'run'])
    ap.add_argument('--condition', required=True, choices=['manual', 'semi'])
    ap.add_argument('--domain', required=True, choices=['geometry_common', 'qt_common'])
    ap.add_argument('--building')
    ap.add_argument('--out', type=Path)
    ap.add_argument('--tolerance', type=float, default=1e-8)
    args = ap.parse_args()
    if args.action == 'validate':
        if not args.building:
            ap.error('--building is required for validation')
        out = args.out or HERE / 'fast_validation' / args.condition / args.domain
        assert orig.HERE not in out.resolve().parents, 'Validation must not write original response outputs.'
        validate(args.condition, args.domain, args.building, out, args.tolerance)
    else:
        if args.out is None:
            ap.error('Production run needs explicit --out; stop original runner before writing same output.')
        run(args.condition, args.domain, args.out, [args.building] if args.building else None)
