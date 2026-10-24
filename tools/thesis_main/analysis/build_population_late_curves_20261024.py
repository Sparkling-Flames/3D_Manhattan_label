"""从既有自然前缀扩展固定图片人数曲线；不新增融合、评分或类别。"""
from pathlib import Path
import json
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT / 'research/workers/personnel_population_curves_v2_20261023'
OUT = BASE / 'late_population_20261024'
META = ['pool_id', 'image', 'building', 'difficulty', 'pool_n']
METRICS = ['Q', 'D10', 'P10', 'SD', 'V', 'failure', 'unavailable']


def image_curves(prefix, geometry):
    d = prefix.loc[prefix.policy.eq('natural_random') & prefix.layer.eq('ordinary_manual') & prefix.k.ge(1)].copy()
    assert not d.duplicated(['pool_id', 'path_id', 'k']).any()
    assert d.score_available.eq(d.B8L2.notna()).all()
    paused = d.loc[d.k.eq(2)]
    assert paused.policy_deferred.all() and paused.B8L2.isna().all()
    assert not paused.score_failure_nonpolicy.any()
    d['unavailable'] = ~d.score_available
    out = d.groupby(META + ['k'], sort=True).agg(
        attempts=('path_id', 'size'), unique_teams=('team_key', 'nunique'),
        scorable=('B8L2', 'count'), Q=('B8L2', 'mean'), D10=('D10', 'mean'),
        P10=('B8L2', lambda s: s.quantile(.1)), SD=('B8L2', 'std'),
        failure=('score_failure_nonpolicy', 'mean'), unavailable=('unavailable', 'mean'),
        policy_deferred=('policy_deferred', 'mean'),
    ).reset_index()
    v = geometry.loc[geometry.policy.eq('natural_random') & geometry.layer.eq('ordinary_manual') & geometry.k.ge(1),
                     ['pool_id', 'k', 'V_floor_mean', 'V_floor_valid_pairs', 'geometry_valid_paths',
                      'member_variation_estimable', 'full_pool_endpoint']]
    out = out.merge(v, on=['pool_id', 'k'], validate='one_to_one', how='left', indicator=True)
    assert out._merge.eq('both').all()
    out = out.drop(columns='_merge').rename(columns={'V_floor_mean': 'V', 'V_floor_valid_pairs': 'V_pairs'})
    # 同一个满员团队的重复路径不产生可估计的成员差异；缺失几何仍为缺失。
    full = out.k.eq(out.pool_n)
    assert out.loc[full, 'unique_teams'].eq(1).all()
    assert out.loc[full, 'SD'].dropna().abs().lt(1e-10).all()
    out.loc[full & out.SD.notna(), 'SD'] = 0.0
    return out, d


def fixed_cohorts(images):
    rows = []
    for minimum in [20, 30, 35]:
        eligible = images.loc[images.pool_n.ge(minimum)].copy()
        curve = eligible.loc[eligible.k.le(minimum)].copy()
        curve['stage'] = curve.k.astype(str)
        full = eligible.loc[eligible.k.eq(eligible.pool_n)].copy()
        full['stage'] = 'full'
        panel = pd.concat([curve, full], ignore_index=True)
        panel['cohort_min_n'] = minimum
        rows.append(panel)
    return pd.concat(rows, ignore_index=True)


def with_all_difficulties(frame):
    return pd.concat([frame, frame.assign(difficulty='全部')], ignore_index=True)


def summarize_curves(panel):
    rows = []
    for keys, g in with_all_difficulties(panel).groupby(['cohort_min_n', 'difficulty', 'stage'], sort=False):
        row = dict(zip(['cohort_min_n', 'difficulty', 'stage'], keys))
        row.update(k=np.nan if keys[2] == 'full' else int(keys[2]),
                   images=len(g), buildings=g.building.nunique(), actual_n_min=g.k.min(), actual_n_max=g.k.max(),
                   attempts=g.attempts.sum(), scorable=g.scorable.sum(), unique_team_image_units=g.unique_teams.sum(),
                   V_pairs=g.V_pairs.sum(min_count=1), geometry_valid_paths=g.geometry_valid_paths.sum(),
                   policy_deferred=g.policy_deferred.mean())
        for metric in METRICS:
            row[metric] = g[metric].mean()
            row[metric + '_images'] = g[metric].count()
            row[metric + '_building_equal'] = g.groupby('building')[metric].mean().mean()
        rows.append(row)
    return pd.DataFrame(rows)


def late_changes(panel, prefix):
    rows = []
    steps = {20: [('20', 'full')],
             30: [('20', '25'), ('25', '30'), ('20', '30'), ('30', 'full'), ('20', 'full')],
             35: [('20', '30'), ('30', '35'), ('20', '35')]}
    for minimum, pairs in steps.items():
        pairs = [('3', '6'), ('6', '10'), ('10', '20'), ('3', '20')] + pairs
        p = panel.loc[panel.cohort_min_n.eq(minimum)]
        for start, end in pairs:
            joined = p.loc[p.stage.eq(start)].merge(p.loc[p.stage.eq(end)], on=META, suffixes=('_from', '_to'), validate='one_to_one')
            assert len(joined) == p.pool_id.nunique()
            for r in joined.to_dict('records'):
                d = prefix.loc[prefix.pool_id.eq(r['pool_id'])]
                a = d.loc[d.k.eq(r['k_from'])].set_index('path_id')
                b = d.loc[d.k.eq(r['k_to'])].set_index('path_id').reindex(a.index)
                assert b.k.notna().all()
                good = a.B8L2.notna() & b.B8L2.notna()
                row = {k: r[k] for k in META}
                row.update(cohort_min_n=minimum, comparison=start + '_to_' + end,
                           k_from=r['k_from'], k_to=r['k_to'], attempted_paths=len(a),
                           paired_Q_paths=int(good.sum()), recovered_paths=int((a.B8L2.isna() & b.B8L2.notna()).sum()),
                           lost_paths=int((a.B8L2.notna() & b.B8L2.isna()).sum()),
                           both_unscorable_paths=int((a.B8L2.isna() & b.B8L2.isna()).sum()))
                for metric in METRICS:
                    row[metric + '_from'] = r[metric + '_from']
                    row[metric + '_to'] = r[metric + '_to']
                    row[metric + '_delta'] = r[metric + '_to'] - r[metric + '_from']
                row['paired_Q_from'] = a.loc[good, 'B8L2'].mean()
                row['paired_Q_to'] = b.loc[good, 'B8L2'].mean()
                row['paired_Q_delta'] = (b.loc[good, 'B8L2'] - a.loc[good, 'B8L2']).mean()
                rows.append(row)
    return pd.DataFrame(rows)


def summarize_changes(images):
    rows = []
    for keys, g in with_all_difficulties(images).groupby(['cohort_min_n', 'difficulty', 'comparison'], sort=False):
        for metric in METRICS + ['paired_Q']:
            valid = g[metric + '_delta'].notna()
            z = g.loc[valid]
            delta = z[metric + '_delta']
            row = dict(zip(['cohort_min_n', 'difficulty', 'comparison'], keys))
            row.update(metric=metric, cohort_images=len(g), common_images=len(z), buildings=z.building.nunique(),
                       from_mean=z[metric + '_from'].mean(), to_mean=z[metric + '_to'].mean(),
                       delta_mean=delta.mean(), delta_median=delta.median(),
                       delta_building_equal=z.groupby('building')[metric + '_delta'].mean().mean(),
                       positive_images=int(delta.gt(1e-9).sum()), negative_images=int(delta.lt(-1e-9).sum()),
                       zero_images=int(delta.abs().le(1e-9).sum()),
                       attempted_paths=g.attempted_paths.sum(), paired_Q_paths=g.paired_Q_paths.sum(),
                       recovered_paths=g.recovered_paths.sum(), lost_paths=g.lost_paths.sum(),
                       both_unscorable_paths=g.both_unscorable_paths.sum())
            rows.append(row)
    return pd.DataFrame(rows)


def main():
    OUT.mkdir(exist_ok=True)
    prefix = pd.read_csv(BASE / 'stability_rebuilt_20261023/inputs/PREFIX_VALUES_COMPACT.csv.gz')
    geometry = pd.read_csv(BASE / 'results/PREFIX_GEOMETRY_VARIATION.csv.gz')
    images, natural = image_curves(prefix, geometry)
    inventory = images[META].drop_duplicates()
    assert len(inventory) == inventory.image.nunique() == 177
    assert inventory.groupby('pool_id').size().eq(1).all()
    for _, g in images.groupby('pool_id'):
        assert set(g.k) == set(range(1, int(g.pool_n.iloc[0]) + 1))
    # 在旧共同域逐图核对，扩展人数不能改变旧前缀的统计定义。
    old = pd.read_csv(BASE / 'stability_rebuilt_20261023/results/NATURAL_IMAGE_CURVES_REBUILT.csv.gz')
    old = old.loc[old.layer.eq('ordinary_manual') & old.k.ge(3)]
    check = images.merge(old, on=['pool_id', 'k'], validate='one_to_one')
    for new, prior in [('Q','Q_mean'), ('D10','D10_mean'), ('P10','Q_p10'), ('SD','Q_sd_ddof1'),
                       ('failure','score_failure_nonpolicy_rate'), ('unavailable','score_unavailable_rate')]:
        np.testing.assert_allclose(check[new], check[prior], atol=1e-9, equal_nan=True)
    checkpoints = natural.loc[natural.pool_n.ge(20) & (natural.k.isin([1,2,3,6,10,20,25,30,35]) | natural.k.eq(natural.pool_n))]
    columns = ['team_key','B8L2','D10','score_available','score_failure_nonpolicy','image','condition']
    endpoints = pd.read_csv(BASE / 'results/ENDPOINT_SCALARS.csv.gz', usecols=columns, low_memory=False)
    linked = checkpoints.merge(endpoints, on='team_key', suffixes=('','_endpoint'), validate='many_to_one')
    assert len(linked) == len(checkpoints)
    for metric in ['B8L2','D10']:
        np.testing.assert_allclose(linked[metric], linked[metric+'_endpoint'], equal_nan=True, atol=1e-10)
    for field in ['score_available','score_failure_nonpolicy','image','condition']:
        assert linked[field].eq(linked[field+'_endpoint']).all(), field
    panel = fixed_cohorts(images)
    summary = summarize_curves(panel)
    changes = late_changes(panel, natural)
    comparisons = summarize_changes(changes)
    for name, frame in [('IMAGE_CURVES.csv.gz', images), ('POOL_INVENTORY.csv', inventory),
                        ('COHORT_IMAGES.csv', panel[['cohort_min_n'] + META].drop_duplicates()),
                        ('CURVE_SUMMARY.csv', summary), ('LATE_IMAGE_CHANGES.csv', changes),
                        ('LATE_COMPARISONS.csv', comparisons)]:
        frame.to_csv(OUT / name, index=False, encoding='utf-8-sig')
    receipt = dict(data_release='v2', ordinary_manual_pools=len(inventory),
                   curve_rows=len(images), previous_image_steps_verified=len(check),
                   original_scalar_checkpoint_paths=len(linked), original_scalar_unique_endpoints=linked.team_key.nunique(),
                   natural_prefix_rows=len(natural), new_fusion_runs=0, new_score_runs=0,
                   single_person_baseline=True, two_person_policy_deferred=True,
                   cohorts={str(n): int(inventory.pool_n.ge(n).sum()) for n in [20,30,35]},
                   full_pool_unique_teams_per_image=1,
                   fields='README.md', source_files=[
                       'stability_rebuilt_20261023/inputs/PREFIX_VALUES_COMPACT.csv.gz',
                       'results/PREFIX_GEOMETRY_VARIATION.csv.gz', 'results/ENDPOINT_SCALARS.csv.gz',
                       'stability_rebuilt_20261023/results/NATURAL_IMAGE_CURVES_REBUILT.csv.gz'])
    (OUT / 'VALIDATION.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(receipt, ensure_ascii=False))


if __name__ == '__main__':
    main()
