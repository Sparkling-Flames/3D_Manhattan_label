"""按逐图判断采用水平顶面；代表点邻域取均值，保留底面及原有资格。"""
import argparse
import copy
import json
from pathlib import Path

import numpy as np
import pandas as pd
from .adopt_orthogonal_references_20261028 import OUT as BASE
from .orthogonal_scope_references_20261028 import ROOT, axis, floor, geometry, points_for

OUT = BASE / 'ceiling_adopted_20261028'
VERSION = 'user_ceiling_adopted_20261028'
TOLERANCE = 0.0002  # 相机高度归一化；本批分组在0.00015至0.001内不变。


def adjust(points, decision, note):
    before = np.asarray(points, float)
    heights = np.asarray(geometry(before)['top3d'])[:, 1]
    anchor = None
    if decision == 'adopt_flat_diagnostic':
        selected = np.arange(len(heights))
    elif decision == 'adopt_majority_height_plane':
        if not note.strip().isdigit() or not 1 <= int(note) <= len(heights):
            raise ValueError('代表点号必须为有效的一基点对编号')
        anchor = int(note) - 1
        selected = np.flatnonzero(abs(heights - heights[anchor]) <= TOLERANCE)
        # 新数据若无法清楚分组，应重新审查，不能悄悄依赖单一阈值。
        for tolerance in (0.00015, 0.001):
            if not np.array_equal(selected, np.flatnonzero(abs(heights - heights[anchor]) <= tolerance)):
                raise ValueError('代表点邻域对容差敏感，需要复核')
    else:
        raise ValueError('未支持的采用决定：' + str(decision))
    height = float(heights[selected].mean())
    if not np.isfinite(height) or height <= 0:
        raise ValueError('顶面必须位于相机上方')
    projected = np.asarray(points_for(floor(before), np.full(len(heights), height)))
    # 只替换顶部y，保留底部和全部x的原始数值。
    after = before.copy()
    after[::2, 1] = projected[::2, 1]
    np.testing.assert_allclose(np.asarray(geometry(after)['top3d'])[:, 1], height, atol=1e-10)
    return after.tolist(), dict(representative_pair_1based=None if anchor is None else anchor + 1,
        averaged_pairs_1based=(selected + 1).tolist(), adopted_height_h=height,
        group_height_range_h=float(np.ptp(heights[selected])),
        max_top_y_move_px=float(abs(after[::2, 1] - before[::2, 1]).max()))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--review', type=Path, default=OUT / 'USER_REVIEW.json')
    args = parser.parse_args()
    review = json.loads(args.review.read_text(encoding='utf-8'))
    assert review['schema'] == 'ceiling_review_20261028_v1'
    candidates = {r['target_id']: r for r in json.loads((BASE / 'ceiling_diagnostic/CANDIDATES.json').read_text(encoding='utf-8'))}
    catalog = json.loads((BASE / 'REFERENCE_CATALOG.json').read_text(encoding='utf-8'))
    by_id = {r['target_id']: r for r in catalog}
    expected = {tid for tid in candidates if by_id[tid]['current_target'] and not by_id[tid]['image_analysis_blocked'] and not by_id[tid]['image_analysis_hold_reasons']}
    records = review['records']
    assert len(records) == 30 and len({r['target_id'] for r in records}) == 30
    assert sum(r['decision'] == 'adopt_flat_diagnostic' for r in records) == 24
    assert sum(r['decision'] == 'adopt_majority_height_plane' for r in records) == 6
    assert {r['target_id'] for r in records} == expected
    updated = []; audit = []
    for r in records:
        c = candidates[r['target_id']]; ref = by_id[r['target_id']]
        assert r['image_id'] == ref['image_id'] and r['image'] == ref['image_code']
        assert r['baseline_points'] == c['baseline_points'] == ref['points_1024x512']
        assert r['flat_points'] == c['points_1024x512']
        points, info = adjust(r['baseline_points'], r['decision'], r['note'])
        if r['decision'] == 'adopt_flat_diagnostic':
            np.testing.assert_allclose(points, r['flat_points'], atol=1e-8)
        assert axis(floor(points))[1] < 1e-8
        item = copy.deepcopy(ref)
        item.update(points_1024x512=points, geometry=geometry(points), reference_version=VERSION,
            previous_reference_version=ref['reference_version'],
            ceiling_adoption=dict(decision=r['decision'], **info),
            adoption_receipt=(OUT / 'USER_ADOPTION_RECEIPT.json').relative_to(ROOT).as_posix(),
            score_status_for_reference_version='not_recomputed')
        by_id[r['target_id']] = item
        updated.append(item)
        audit.append(dict(image=r['image'], target_id=r['target_id'], decision=r['decision'], **info))
    OUT.mkdir(exist_ok=True)
    def write(name, value):
        (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    if (OUT / 'USER_REVIEW.json').exists():
        assert json.loads((OUT / 'USER_REVIEW.json').read_text(encoding='utf-8')) == review, '不能覆盖不同的人工回执'
    write('USER_REVIEW.json', review)
    write('USER_ADOPTION_RECEIPT.json', dict(version=VERSION, exported_at=review['exported_at'],
        clarification='我写的数字是你选项说明的:请备注代表点号',
        averaging_authorization='如果有微小的误差,你就平均一下',
        interpretation='代表点所在近同高组的三维顶高取算术均值；不要求严格多数。其余选择采用展示的全点均高。',
        height_basis='top_y与bottom_y共同推算；水平地面、相机高度归一化；当前底面固定，不归因于top或bottom单方误差。',
        tolerance_h=TOLERANCE, grouping_stable_tolerances_h=[0.00015, 0.001],
        base_catalog=(BASE / 'REFERENCE_CATALOG.json').relative_to(ROOT).as_posix(),
        records=30, all_vertex_mean=24, representative_group_mean=6))
    write('ADOPTED_REFERENCES.json', updated)
    write('REFERENCE_CATALOG.json', [by_id[r['target_id']] for r in catalog])
    write('CHECKS.json', dict(adopted=30, source_geometry_matches=True, floor_and_x_unchanged=True,
        all_flat_and_orthogonal=True, holds_and_current_target_unchanged=True,
        group_tolerance_sensitivity_passed=True, scores_recomputed=0,
        stale_score_targets=sorted(expected), score_policy='旧BOUND_SCORE_REUSE不代表这30个新版本的分数；待重算或核验缓存版本。'))
    pd.DataFrame(audit).to_csv(OUT / 'HEIGHT_CHANGES.csv', index=False, encoding='utf-8-sig')
    figure(updated, candidates)
    pointer = dict(version=VERSION, catalog=(OUT / 'REFERENCE_CATALOG.json').relative_to(ROOT).as_posix(),
        receipt=(OUT / 'USER_ADOPTION_RECEIPT.json').relative_to(ROOT).as_posix(),
        qualification='既有资格与冻结v2不变；30个新顶面版本未重算评分，不能使用旧BOUND_SCORE_REUSE作为其新分数。')
    (BASE.parent / 'CURRENT_REFERENCES.json').write_text(json.dumps(pointer, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(pd.DataFrame(audit)[['image', 'averaged_pairs_1based', 'adopted_height_h', 'max_top_y_move_px']].to_string(index=False))


def figure(updated, candidates):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from PIL import Image
    from tools.label_studio.panorama_studio.geometry import project_pixel
    plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'DejaVu Sans']
    selected = [r for r in updated if r['ceiling_adoption']['decision'] == 'adopt_majority_height_plane']
    fig, axes = plt.subplots(6, 2, figsize=(15, 19), layout='constrained', gridspec_kw={'width_ratios':[2.4,1]})
    for axs, r in zip(axes, selected):
        info = r['ceiling_adoption']
        axs[0].imshow(Image.open(ROOT/'data/mp3d_layout/img_v'/(r['image_id']+'.jpg')), extent=[0,1024,512,0])
        for points, color, label in [(candidates[r['target_id']]['baseline_points'], '#00aaaa', '修正前'), (r['points_1024x512'], '#ed3982', '已采用：代表点组均高')]:
            top = np.asarray(geometry(points)['top3d']); pixels = []
            for a, b in zip(top, np.roll(top,-1,axis=0)):
                pixels.extend(project_pixel(a*(1-t)+b*t,1024,512) for t in np.linspace(0,1,100))
            pixels = np.asarray(pixels); pixels[np.flatnonzero(abs(np.diff(pixels[:,0]))>512)+1] = np.nan
            axs[0].plot(pixels[:,0],pixels[:,1],color=color,lw=1.2,label=label)
            axs[1].plot(np.arange(1,len(top)+1),top[:,1],color=color,marker='o',ms=3,label=label)
        axs[0].set(xlim=(0,1024),ylim=(512,0),title=r['image_code']); axs[0].axis('off'); axs[0].legend(fontsize=8)
        axs[1].set(title='平均点号：'+','.join(map(str,info['averaged_pairs_1based'])),xlabel='点对编号',ylabel='相机以上顶高 / 相机高度')
        axs[1].grid(alpha=.2)
    fig.suptitle('用户确认代表点所在平面：近同高点取平均；bottom固定，top与bottom共同推算高度',fontsize=14)
    fig.savefig(OUT/'代表点平面_六图修正.png',dpi=115)
    plt.close(fig)


if __name__ == '__main__':
    main()
