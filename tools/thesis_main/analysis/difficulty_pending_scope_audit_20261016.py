"""只诊断已确认空间的源域越界，不改变参考资格或难度。"""
import json
from collections import Counter
from pathlib import Path

import numpy as np
from shapely.geometry import Point, Polygon
from shapely.ops import nearest_points

from .descriptive_reference_audit_20261015 import floor
from .difficulty_user_revision_20261015 import convert_original
from tools.label_studio.panorama_studio.geometry import project_pixel

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / 'research/difficulty/difficulty_b8l2_handoff_20261016'


def displacement(target, source):
    # 边上加密是诊断采样，不宣称为连续边界的严格最大值。
    maximum = 0.
    for a, b in zip(target, target[1:] + target[:1]):
        for t in np.linspace(0, 1, 101):
            p = Point(np.asarray(a) * (1-t) + np.asarray(b) * t)
            if source.covers(p):
                continue
            q = nearest_points(p, source)[1]
            uv = np.asarray(project_pixel([p.x, -1, p.y], 1024, 512))
            other = np.asarray(project_pixel([q.x, -1, q.y], 1024, 512))
            delta = np.abs(uv-other)
            delta[0] = min(delta[0], 1024-delta[0])
            maximum = max(maximum, float(np.linalg.norm(delta)))
    return maximum


def main():
    snapshot = json.loads((OUT/'difficulty_snapshot.json').read_text(encoding='utf-8'))
    refs = json.loads((OUT/'reference_catalog_snapshot.json').read_text(encoding='utf-8'))
    lookup = {r['target_id']: r for r in refs}
    images = {r['image_id']: r for r in snapshot['records']}
    rows = []
    for ref in refs:
        if not ref['current_target'] or ref['full_reference_available']:
            continue
        attempts = []
        target = ref['floor_xz_h']
        polygon = Polygon(target)
        for attempt in ref['evidence']['constructions']:
            if 'source_reference_id' in attempt:
                source = lookup[attempt['source_reference_id']]
            else:
                # v6两图构造记录只存源JSON；按同图原GT及逐值转换绑定，不猜测。
                matches = [r for r in refs if r['image_id'] == ref['image_id']
                           and r['reference_version'] == 'gt_original'
                           and r['points_1024x512'] == convert_original(attempt['source_plane']['source_json_geometry'])]
                assert len(matches) == 1
                source = matches[0]
            rounded = Polygon(source['floor_xz_h'])
            plane = attempt.get('source_plane')
            metric = dict(source_reference_id=source['target_id'],
                outside_area_h2=polygon.difference(rounded).area,
                outside_percent=100*polygon.difference(rounded).area/polygon.area,
                sampled_outside_displacement_px=displacement(target, rounded),
                original_json=None, unrounded_outside_area_h2=None,
                unrounded_sampled_outside_displacement_px=None)
            if plane:
                raw = plane['source_json_geometry']
                assert convert_original(raw) == source['points_1024x512']
                points = raw['layoutPoints']['points']
                radius = np.linalg.norm(np.asarray([p['xyz'] for p in points])[:, [0, 2]], axis=1)
                u = np.asarray([p['coords'][0] for p in points])*1024
                bottom = (.5 + np.arctan2(raw['cameraHeight'], radius)/np.pi)*512
                top = (.5 - np.arctan2(raw['layoutHeight']-raw['cameraHeight'], radius)/np.pi)*512
                precise = Polygon(floor(np.column_stack([np.repeat(u, 2), np.stack([top, bottom], axis=1).ravel()])))
                metric.update(original_json=plane['archive']+' :: '+plane['member'],
                    unrounded_outside_area_h2=polygon.difference(precise).area,
                    unrounded_sampled_outside_displacement_px=displacement(target, precise))
            attempts.append(metric)
        # 检查全部已有源；不选择使作答分数最高的参考。
        best = min(attempts, key=lambda a:a['sampled_outside_displacement_px'])
        px = best['sampled_outside_displacement_px']
        raw_px = best['unrounded_sampled_outside_displacement_px']
        category = ('仅数值/存储误差候选' if px <= .01 and raw_px is not None and raw_px <= .01
                    else '实际范围扩展（相对已有源域）' if px > 1 and raw_px is not None and raw_px > 1
                    else '其它/证据不足')
        image = images[ref['image_id']]
        rows.append(dict(image=image['image'], target_id=ref['target_id'], category=category,
            photo=image['photo'], card=image['card'], scope_sources=(ref['sources'] if 'sources' in ref else
                [dict(source='analysis_results/research_input_20260929/floor_scope_update_20261015.json',
                      receipt='analysis_results/research_input_20260929/scope_receipt_20261016.json', image_id=ref['image_id'])]),
            comparison=best, all_source_comparisons=attempts,
            scope_points_confirmed=True, full_reference_available=False))
    assert len(rows) == 29 and len({r['image'] for r in rows}) == 29
    assert displacement([[0,0],[1,0],[1,1],[0,1]], Polygon([[-1,-1],[2,-1],[2,2],[-1,2]])) == 0
    report = dict(version='pending_scope_diagnostic_20261016', counts=dict(Counter(r['category'] for r in rows)),
        scope_confirmation='统筹线程转述用户已看完43空间并确认点位处理；不包含顶界确认',
        diagnostic_only=True, labels_and_eligibility_unchanged=True, records=rows)
    (OUT/'pending_scope_audit.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8', newline='\n')
    lines = ['# 29张完整参考待核的逐图原因', '',
        '已确认41图43空间的点位处理，不再要求重复画范围。此处待核仅指完整三维参考；不改原B8L2、标签、坐标或资格。', '',
        '面积单位为相机高度平方(h²)，不是平方米；百分比为越界面积/新范围面积。位移为新边每段101点到源多边形最近点的ERP投影距离采样最大值（1024×512，考虑横向环缝），不是严格连续上界。', '',
        '另从源JSON的coords、xyz半径及cameraHeight重新执行既定转换但不保留两位小数，检验越界是否仍存在。与原JSON逐值转换相等检查通过后才进行比较，不直接把JSON的xyz轴当ERP坐标。', '',
        '诊断分组：两种源表示的采样位移均≤0.01像素，列为数值/存储误差候选；均>1像素列为相对已有源域的实际扩展；其余证据不足。0.01来自现有存储尺度，1像素只用于分开明显扩展；二者均不是参考准入阈值。候选不等于已证明唯一成因，扩展不等于用户范围错误。', '',
        '|图片|原因组|越界h²|占新范围%|原GT位移px|未舍入源位移px|未舍入越界h²|',
        '|---|---|---:|---:|---:|---:|---:|']
    for row in sorted(rows, key=lambda r:r['image']):
        m=row['comparison']
        lines.append(f"|[{row['image']}]({Path(row['photo']).as_posix()})|{row['category']}|{m['outside_area_h2']:.7g}|{m['outside_percent']:.5g}|{m['sampled_outside_displacement_px']:.6g}|{m['unrounded_sampled_outside_displacement_px']}|{m['unrounded_outside_area_h2']}|")
    lines += ['', '逐图全部源对象、回执路径、原JSON成员及原图链接见 [pending_scope_audit.json](pending_scope_audit.json)。未重新肉眼检查全部原图；本表结论是来源与几何差异诊断，不能认证照片中的天花板延续。', '', '分组数量：'+json.dumps(report['counts'],ensure_ascii=False)]
    (OUT/'PENDING_SCOPE_AUDIT.md').write_text('\n'.join(lines)+'\n', encoding='utf-8', newline='\n')
    print(json.dumps(report['counts'],ensure_ascii=False))


if __name__ == '__main__':
    main()
