"""固定同房面板与测量距离，只替换分区，复用已审计的Pro同房计算。"""
import argparse
import importlib.util
import json
from pathlib import Path
import shutil
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / 'analysis_results/room_partition_comparison_20260922'
KEYS = ['variant', 'cut', 'metric', 'kind', 'image_id']


def align_predictions(old, new):
    z = old.merge(new, on=KEYS, how='outer', suffixes=('_old', '_new'), indicator=True, validate='one_to_one')
    if not z['_merge'].eq('both').all():
        raise ValueError('两种方法的目标面板不一致')
    for field in ['building', 'family', 'N', 'source_codes', 'source_N', 'outcome_exposed']:
        if not z[field+'_old'].equals(z[field+'_new']):
            raise ValueError('两种方法的同房来源或评价条件不一致：' + field)
    return z.drop(columns='_merge')


def main(package):
    OUT.mkdir(parents=True, exist_ok=True)
    sys.path.insert(0, str(package / 'code'))
    import core as c

    def module(name):
        spec = importlib.util.spec_from_file_location(name, package / 'code' / (name+'.py'))
        obj = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(obj)
        return obj

    rooms, candidate = module('07_rooms_and_collection'), module('02_partition')
    baseline = pd.read_csv(package / 'results/room_predictions_new.csv')
    baseline = baseline[(baseline.variant == 'raw') & (baseline.cut == 25.6)].copy()
    work = package / 'room_candidate_results'
    if work.exists():
        raise FileExistsError(work)
    work.mkdir()
    shutil.copyfile(package / 'results/distance_variants.json.gz', work / 'distance_variants.json.gz')
    c.OUT = work
    rooms.SPECS = [('raw', 25.6)]
    cache = {}
    certificates = []

    def partition(d, ids, method='complete', cut=25.6):
        if method != 'complete' or cut != 25.6:
            raise ValueError('本对照只替换原始25.6完整链接')
        key = (tuple(ids), np.round(d, 8).tobytes())
        if key not in cache:
            labels, info = candidate.affinity_partition(d, ids, cut, 'quadratic', time_limit=10)
            if labels is None or not info['certified']:
                raise RuntimeError('候选求解未获最优证书：' + str(info))
            cache[key] = labels
            certificates.append(dict(ids=list(ids), labels=labels.tolist(), **info))
        return cache[key], []

    c.part = partition
    rooms.main()
    new = pd.read_csv(work / 'room_predictions_new.csv')
    paired = align_predictions(baseline, new)
    invariant = paired[paired.metric == 'pair_disagreement']
    for field in ['value', 'prediction', 'outside_baseline', 'otherroom_baseline']:
        np.testing.assert_allclose(invariant[field+'_old'], invariant[field+'_new'], rtol=0, atol=0, equal_nan=True)
    rows = []
    for (metric, kind), z in paired.groupby(['metric', 'kind']):
        for shared in [False, True]:
            assert z.otherroom_baseline_old.notna().equals(z.otherroom_baseline_new.notna())
            zz = z[z.otherroom_baseline_old.notna()] if shared else z
            if zz.empty:
                continue
            columns = [f'error_{e}_{side}' for e in ['prediction', 'outside_baseline', 'otherroom_baseline'] for side in ['old', 'new']]
            b = zz.groupby(['building_old', 'family_old'])[columns].mean().groupby('building_old').mean()
            delta = b.error_prediction_new - b.error_prediction_old
            gain_delta = (b.error_outside_baseline_new-b.error_prediction_new) - (b.error_outside_baseline_old-b.error_prediction_old)
            rng = np.random.default_rng(c.SEED)
            ci = np.quantile(rng.choice(delta.to_numpy(), (3000, len(b)), replace=True).mean(1), [.025, .975])
            row = dict(metric=metric, kind=kind, same_panel_otherroom=shared, images=len(zz),
                families=zz.family_old.nunique(), buildings=len(b),
                target_changed=int((abs(zz.value_new-zz.value_old) > 1e-12).sum()),
                source_prediction_changed=int((abs(zz.prediction_new-zz.prediction_old) > 1e-12).sum()),
                MAE_delta_new_minus_old=delta.mean(), delta_conditional_low=ci[0], delta_conditional_high=ci[1],
                same_room_gain_delta=gain_delta.mean())
            for side in ['old', 'new']:
                row.update({f'{field}_{side}': b[f'error_{name}_{side}'].mean() for field, name in
                    [('MAE', 'prediction'), ('outside_MAE', 'outside_baseline'), ('otherroom_MAE', 'otherroom_baseline')]})
            rows.append(row)
    summary = pd.DataFrame(rows)
    paired.to_csv(OUT / 'paired_predictions.csv', index=False)
    summary.to_csv(OUT / 'summary.csv', index=False)
    for name in ['room_summary_new.json', 'room_matched_n8_current_consensus.csv']:
        shutil.copyfile(work / name, OUT / ('candidate_' + name))
    (OUT / 'candidate_solutions.json').write_text(json.dumps(certificates, ensure_ascii=False, indent=2), encoding='utf8')
    manifest = dict(source='analysis_results/cluster_validation_received_20260922/Pro原始返回.zip',
        points='已确认有效点；没有新增共享x规整', cut=25.6,
        baseline='完整链接', candidate='两两直径约束＋二次亲近度全局分区',
        solved_partitions=len(cache), all_certified=True, paired_rows=len(paired),
        pair_disagreement_unchanged=True,
        limitations='预测目标是分歧/支持结构，不是稳定人数。簇指标的目标值随算法改变，MAE不是对同一个独立真值的算法准确率比较。区间是固定预测上的条件建筑重采样。')
    (OUT / 'MANIFEST.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+'\n', encoding='utf8')
    print(summary[~summary.same_panel_otherroom].to_string(index=False))
    print(json.dumps(manifest, ensure_ascii=False))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--package', type=Path, required=True)
    args = p.parse_args()
    main(args.package.resolve())
