"""Reaggregate saved evidence for external-review claims and multi-space coverage."""
import gzip
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / 'research/statistics/external_review_response_20261028'
POP = ROOT / 'research/workers/personnel_population_curves_v2_20261023'
SCOPE = ROOT / 'research/difficulty/difficulty_mechanisms_v2_20261020/scope_closeout_20261022'


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    checks = []

    def record(name, value, units, source):
        checks.append(dict(check=name, value=float(value), units=units, source=source))

    base = POP / 'sampling_extension_20261026/analysis_precision26/results_stage2'
    intervals = pd.read_csv(base / 'NATURAL_INTERVALS.csv.gz')
    display = pd.read_csv(base / 'HYBRID_POOLED256_DISPLAY_CURVES.csv.gz')
    assert set(display.cohort) == {'pooled256'} and display.pool_id.nunique() == 194
    z = intervals.query("cohort == 'pooled256' and layer == 'doorway_manual' and interval == '6_to_10'")
    assert len(z) == 17 and z.pool_id.is_unique
    for col in ['failure_delta', 'actual_consensus_failure_delta', 'output_unscoreable_delta']:
        record('doorway_6_10_' + col, 100*z[col].mean(), 'percentage_points', 'NATURAL_INTERVALS.csv.gz:' + col)
    np.testing.assert_allclose(z.failure_delta, z.actual_consensus_failure_delta + z.output_unscoreable_delta)
    np.testing.assert_allclose(100*z.actual_consensus_failure_delta.mean(), -13.534007352941177)

    tail = intervals.query("cohort == 'pooled256' and layer == 'ordinary_manual' and interval == '30_to_full'")
    for label, t in [('N_ge_30', tail), ('N_gt_30', tail[tail.pool_n > 30])]:
        record('30_full_' + label + '_images', len(t), 'images', 'NATURAL_INTERVALS.csv.gz')
        record('30_full_' + label + '_Q_images', t.marginal_Q_delta.count(), 'images', 'NATURAL_INTERVALS.csv.gz')
        record('30_full_' + label + '_Q_delta', t.marginal_Q_delta.mean(), 'Q_points', 'NATURAL_INTERVALS.csv.gz')
    old = pd.read_csv(POP / 'late_population_20261024/LATE_IMAGE_CHANGES.csv')
    old = old.query('k_from == 30 and k_to == 35 and cohort_min_n == 35')
    assert len(old) == 92 and old.Q_delta.count() == 91 and set(old.attempted_paths) == {24}
    record('old24_30_35_Q_delta', old.Q_delta.mean(), 'Q_points', 'late_population_20261024/LATE_IMAGE_CHANGES.csv')
    record('old24_30_35_positive', (old.Q_delta > 1e-10).sum(), 'images', 'late_population_20261024/LATE_IMAGE_CHANGES.csv')

    f = pd.read_csv(ROOT / 'research/fusion/fusion_common_panel_20261024/METHOD_ENDPOINTS.csv')
    f = f[f.layer.eq('ordinary_manual') & f.method.isin(['wall_auto', 'medoid'])]
    for n, g in f.groupby('n'):
        a = g.pivot(index='team_key', columns='method', values='B8L2')
        assert a.medoid.notna().all()
        valid = a.dropna()
        record(f'fusion_n{n}_common_Q_delta', (valid.wall_auto-valid.medoid).mean(), 'Q_points', 'METHOD_ENDPOINTS.csv')
        # This is an explicit zero-utility scenario, never a replacement for missing Q.
        record(f'fusion_n{n}_zero_utility_delta', (a.wall_auto.fillna(0)-a.medoid).mean(), 'utility_points', 'METHOD_ENDPOINTS.csv')

    c = pd.read_csv(ROOT / 'research/workers/personnel_classification_guide_20261025/sources/NEW_CLASS_DEFINITIONS_ALL_LOBO.csv.gz')
    c = c[c.method.eq('DSTRUCT_K3')]
    for x in c[c.heldout_building.eq('ALL')].itertuples():
        record('DSTRUCT_' + x.class_id + '_peer_Q_center', x.m_all_B8L2, 'peer_centered_Q_points', 'NEW_CLASS_DEFINITIONS_ALL_LOBO.csv.gz')
    w = c[c.heldout_building.ne('ALL')].pivot(index='heldout_building', columns='class_id', values='m_all_B8L2')
    assert len(w) == 22
    gap = w.C3-w.C2
    record('DSTRUCT_LOBO_C3_minus_C2_mean', gap.mean(), 'peer_centered_Q_points', 'NEW_CLASS_DEFINITIONS_ALL_LOBO.csv.gz')
    record('DSTRUCT_LOBO_C3_minus_C2_SD', gap.std(ddof=1), 'peer_centered_Q_points', 'NEW_CLASS_DEFINITIONS_ALL_LOBO.csv.gz')

    with gzip.open(ROOT / 'research/statistics/v2_evidence_audit_20261019/records.json.gz', 'rt', encoding='utf-8') as stream:
        raw = json.load(stream)['records']
    r = pd.DataFrame([dict(image_id=x['image_id'], quality=x['quality_usable'], retained=x['pool_analysis_eligible'],
                          allowed_n=len(x['binding_evidence']['allowed_target_ids'])) for x in raw])
    images = pd.read_csv(SCOPE / 'image_scope_support.csv')
    scopes = pd.read_csv(ROOT / 'research/data/scope_redundant_vertices_20261016/scope_summary.csv')
    pools = pd.read_csv(POP / 'design/ACTUAL_POOLS.csv')
    assert images.image_id.is_unique and pools.pool_id.is_unique
    assert set(display.pool_id).issubset(set(pools.pool_id))
    cohorts = {
        'confirmed_new_scope_41': set(scopes.image_id),
        'multiple_allowed_references_29': set(r.loc[r.allowed_n > 1, 'image_id']),
        'multiple_bound_references_29': set(images.loc[images.assigned_reference_count > 1, 'image_id']),
    }
    assert len(cohorts['confirmed_new_scope_41']) == 41
    counts = []
    for name, ids in cohorts.items():
        t = r[r.image_id.isin(ids)]
        q = pools[pools.image_id.isin(ids)]
        nat = q[q.pool_id.isin(display.pool_id)]
        counts.append(dict(cohort=name, images=len(ids), inventory_records=len(t), retained_records=int(t.retained.sum()),
                           retained_images=t[t.retained].image_id.nunique(), quality_records=int(t.quality.sum()),
                           quality_images=t[t.quality].image_id.nunique(), saved_pool_count=len(q),
                           manual256_images=nat.image_id.nunique(), manual256_N_ge_30_images=nat[nat.pool_n >= 30].image_id.nunique(),
                           semi_original_pools=int(q.condition.eq('semi').sum())))
    out = images[images.image_id.isin(cohorts['confirmed_new_scope_41'])].copy()
    for condition in ['manual', 'semi']:
        q = pools[pools.condition.eq(condition)].set_index('image_id')
        assert q.index.is_unique
        out[condition + '_pool_n'] = out.image_id.map(q.pool_n).astype('Int64')
    out['manual256_included'] = out.image_id.isin(set(pools[pools.pool_id.isin(display.pool_id)].image_id))
    assert out.manual256_included.sum() == 12
    assert out.loc[~out.manual256_included, 'target_full_status'].eq('unavailable').all()
    out.to_csv(OUT / 'MULTISPACE_41_COVERAGE.csv', index=False, encoding='utf-8-sig')
    pd.DataFrame(counts).to_csv(OUT / 'SCOPE_COUNTS.csv', index=False, encoding='utf-8-sig')
    pd.DataFrame(checks).to_csv(OUT / 'NUMERIC_CHECKS.csv', index=False, encoding='utf-8-sig')
    receipt = dict(date='2026-10-28', numeric_checks=len(checks), scope_images=len(out), manual256_scope_images=12,
                   new_fusions=0, new_scores=0, new_classification_fits=0,
                   scope='saved-table reaggregation and reference/member-pool linkage; not full raw fusion replay',
                   zero_utility='explicit alternative decision utility only; saved quality/state fields untouched')
    (OUT / 'CHECKS.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(receipt, ensure_ascii=False))


if __name__ == '__main__':
    main()
