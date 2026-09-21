"""接收24图用户审核，核对阈值约束和上下点x偏差；不修改点集。"""
from collections import Counter
import json
from pathlib import Path
import shutil
import sys

import numpy as np

from tools.thesis_main.analysis.paired_split_research.release_review import validate_review

ROOT = Path(__file__).resolve().parents[3]
SCREEN = ROOT / 'analysis_results/cluster_screen_20260921'
OUT = ROOT / 'analysis_results/cluster_screen_reviewed_20260922'
INPUT = OUT / '用户审核_原始.json'
PACKAGE = ROOT / 'analysis_results/panorama_research_received_20260921'


def relation_target(decision):
    if decision['defer']:
        return None
    return {'同一表达，可同簇': True, '不同表达，应分开': False}.get(decision['relation'])


def x_gap_percent(points, links):
    dx = points[links[:, 0], 0] - points[links[:, 1], 0]
    return abs((dx + 512) % 1024 - 512) / 1024 * 100


def main():
    read = lambda p: json.loads(p.read_text(encoding='utf-8-sig'))
    manifest, review = read(SCREEN / 'REVIEW_MANIFEST.json'), read(INPUT)
    cases = manifest['cases']
    answers = validate_review(review, manifest['binding'], [c['key'] for c in cases],
                              {c['key']: c['decision_options'] for c in cases})
    assert len(answers) == len(cases) == 24
    OUT.mkdir(parents=True, exist_ok=True)
    received = OUT / '用户审核_原始.json'
    if received.exists() and received.read_bytes() != INPUT.read_bytes():
        raise ValueError('已有不同审核版本，需另存新版本，不覆盖原件')
    if INPUT.resolve() != received.resolve():
        shutil.copyfile(INPUT, received)
    sys.path.insert(0, str(PACKAGE / 'original_package/code'))
    import common as c
    c.configure(PACKAGE / 'local_recompute/source_work')
    _, records, views, registry, _ = c.load()
    meta = {r['image_id']: r for r in registry['images']}
    comparisons, receipts = [], []
    cuts = [12.8, 6*1024/360, 25.6, 12*1024/360, 51.2]
    for i, case in enumerate(cases, 1):
        decision = answers[case['key']]; target = relation_target(decision)
        selection = case['research_notes']['selection']; v = views[selection['image_id']]
        ia, ib = [v['ids'].index(selection[k]) for k in ('a_id', 'b_id')]
        gt = (ROOT / meta[v['image_id']]['path']).parent.parent / 'label_cor' / (v['image_id'] + '.txt')
        item = dict(case=i, code=case['code'], image_id=v['image_id'], original_decision=decision,
                    target_same=target, fixed_max_px=float(v['d'][ia, ib]),
                    workers=[v['workers'][ia], v['workers'][ib]], ids=[v['ids'][ia], v['ids'][ib]],
                    gt_path=str(gt.relative_to(ROOT)), gt_exists=gt.exists(),
                    gt_semantic_comparability='not_adjudicated',
                    pairing_x_gap_percent={v['ids'][j]:x_gap_percent(records[v['ids'][j]]['p'], records[v['ids'][j]]['links']).tolist() for j in (ia, ib)})
        if gt.exists():
            points = np.loadtxt(gt, ndmin=2)
            assert points.shape[1] == 2 and len(points) % 2 == 0 and np.isfinite(points).all()
            item['gt_point_count'] = len(points)
        receipts.append(item)
        for cut in cuts:
            for kind in ('complete', 'representative'):
                labels, _ = c.part(v['d'], v['ids'], kind, cut)
                same = bool(labels[ia] == labels[ib])
                comparisons.append(dict(case=i, code=case['code'], method=kind, cut=cut,
                    target_same=target, same_cluster=same, pair_near=bool(v['d'][ia, ib] <= cut),
                    matches=None if target is None else same == target))
    stats = []
    for cut in cuts:
        for kind in ('complete', 'representative'):
            rows = [r for r in comparisons if r['method'] == kind and r['cut'] == cut and r['target_same'] is not None]
            stats.append(dict(method=kind, cut=cut, decided=len(rows), matches=sum(r['matches'] for r in rows),
                split_user_same=sum(r['target_same'] and not r['same_cluster'] for r in rows),
                joined_user_different=sum(not r['target_same'] and r['same_cluster'] for r in rows)))
    gaps = []; per_response = []
    for v in views.values():
        for cid in v['ids']:
            r = records[cid]; dx = x_gap_percent(r['p'], r['links']); gaps.extend(dx)
            per_response.append(dict(id=cid, image_id=v['image_id'], worker=r['row']['worker_id'],
                                     x_gap_percent=dx.tolist(), max_gap_percent=float(dx.max())))
    same = [r for r in receipts if r['target_same'] is True]
    different = [r for r in receipts if r['target_same'] is False]
    max_same = max(same, key=lambda r:r['fixed_max_px'])
    min_different = min(different, key=lambda r:r['fixed_max_px'])
    summary = dict(decisions=len(answers), counts=Counter(d['relation'] for d in answers.values()),
        binding_validated=True, original_bytes_preserved=received.read_bytes() == INPUT.read_bytes(),
        maximum_user_same=dict(case=max_same['case'], code=max_same['code'], distance=max_same['fixed_max_px']),
        minimum_user_different=dict(case=min_different['case'], code=min_different['code'], distance=min_different['fixed_max_px']),
        no_scalar_distance_cut_satisfies_all=max_same['fixed_max_px'] >= min_different['fixed_max_px'],
        development_constraint_checks=stats, gt_available=sum(r['gt_exists'] for r in receipts),
        x_gap=dict(unit='0–100百分比坐标的百分点；左右接缝取短距离', responses=len(per_response), pairs=len(gaps),
                   quantiles=dict(zip(['p50', 'p90', 'p95', 'p99', 'max'], np.quantile(gaps, [.5,.9,.95,.99,1]).tolist())),
                   pairs_above_0_2_percent=int(sum(x > .2 for x in gaps)),
                   responses_above_0_2_percent=sum(r['max_gap_percent'] > .2 for r in per_response)),
        limitations='目的性开发案例，非总体准确率；3项暂不能判断不计错。未以审核优化阈值；未修正坐标；GT只核查资产存在和格式。')
    for name, value in [('逐项接收.json', receipts), ('阈值核对.json', comparisons), ('上下点x偏差.json', per_response), ('SUMMARY.json', summary)]:
        (OUT / name).write_text(json.dumps(c.clean(value), ensure_ascii=False, indent=2, allow_nan=False), encoding='utf8')
    print(json.dumps(c.clean(summary), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, default=INPUT)
    parser.add_argument('--output', type=Path, default=OUT)
    args = parser.parse_args()
    INPUT, OUT = args.input, args.output
    main()
