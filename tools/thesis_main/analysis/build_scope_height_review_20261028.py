"""Build nine-case offline height review; no answers or formal references are changed."""
import json
import os
from pathlib import Path
from shapely.geometry import Polygon
from .scope_reference_reconstruction_20261016 import geometry, floor
from tools.label_studio.panorama_studio.geometry import project_pixel
import numpy as np

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / 'research/data/scope_quality_rescore_20261016/vertical_cut_audit_20261028'
VIEWER = ROOT / 'research/statistics/research_explorer_v1_r2_20261017'
OBSERVATIONS = {
    'e9zR4mvMWw7-09': '餐厅上方可见下凸横梁，左右连通客厅和厨房。需要区分主顶面与梁底；候选线穿过虚拟裁切面时，不要求图上恰好有一条实体墙顶线。',
    'uNb9QFRL6hY-18': '浴室中央有凹入的装饰顶，窗边与通道上方也有局部造型。先看新范围的外延位置落在哪里，再判断原顶面高度能否沿用。',
    'uNb9QFRL6hY-26': '浴室与走道相接，中央装饰顶和门口上方的低边界需要区分。原GT底面的凹口也可能对应凸出的墙体，不能仅凭有顶高就当作正常裁切。',
    'uNb9QFRL6hY-41': '洗手台、窗边和通道处能看到不同的墙顶轮廓。照片中的曲线包含全景投影效果，曲线弯曲本身不能证明高度不同。',
    'uNb9QFRL6hY-54': '相连通道及房间入口可见低门头，远处还可见台阶。重点看确认范围与这些边界的关系，不把远处房间的顶面自动作为本范围顶面。',
    'uNb9QFRL6hY-59': '淋浴玻璃、窗边低边界和中央装饰顶同时可见。玻璃顶部不必等于房间天花板，需对照候选范围判断。',
    'uNb9QFRL6hY-66': '浴室中央装饰顶、窗侧及走道入口有不同轮廓。需要判断新增范围是否只涉及同一主顶面，还是覆盖梁或凸墙所在区域。',
    'uNb9QFRL6hY-67': '拍摄点位于淋浴区域附近，画面同时包含玻璃内外。请区分玻璃隔断顶部、墙顶和主天花板；必要时记录范围边界疑点。',
    'uNb9QFRL6hY-88': '浴室与通道相接，多处墙柱、门口和装饰顶可见。可切换俯视图核对外延位置，再决定是否沿用统一顶高。',
}


def build():
    candidates = json.loads((OUT / 'CANDIDATE_REFERENCES.json').read_text(encoding='utf-8'))
    refs = {r['target_id']: r for r in json.loads((ROOT / 'research/quality/quality_workers_v2_20261019/reference_catalog.json').read_text(encoding='utf-8'))}
    photos = {r['image']: r for r in json.loads((ROOT / 'research/difficulty/difficulty_scope_resolution_20261016/current_259.json').read_text(encoding='utf-8'))['records']}
    cases = []
    revision = json.loads((OUT / 'LATEST_E9Z_SCOPE_RECEIPT.json').read_text(encoding='utf-8'))
    for c in candidates:
        if c['image'] not in OBSERVATIONS:
            continue
        photo = Path(photos[c['image']]['photo'])
        assert photo.is_file(), photo
        source = refs[c['source_reference_id']]
        c = dict(c)
        if c['image'] == 'e9zR4mvMWw7-09':
            r = revision['record']
            assert r['image_id'] == photos[c['image']]['image_id']
            assert r['cropped_floor_xz_h'] == r['confirmed_version']['polygon']
            c['floor_xz_h'] = r['cropped_floor_xz_h']
            c['target_id'] += ':revised:' + revision['exported_at']
            aa, bb, cc = c['source_plane']['plane']
            c['points_1024x512'] = [pixel for x,z in c['floor_xz_h'] for pixel in
                [project_pixel([x,aa*x+bb*z+cc,z],1024,512),project_pixel([x,-1,z],1024,512)]]
            np.testing.assert_allclose(floor(c['points_1024x512']),c['floor_xz_h'],atol=1e-8)
        p, s = Polygon(c['floor_xz_h']), Polygon(source['floor_xz_h'])
        assert p.is_valid and p.area > 0
        cases.append(dict(image=c['image'], image_id=photos[c['image']]['image_id'],
            target_id=c['target_id'], source_reference_id=c['source_reference_id'],
            photo=Path(os.path.relpath(photo, OUT)).as_posix(), points=c['points_1024x512'],
            source_points=source['points_1024x512'], observation=OBSERVATIONS[c['image']],
            outside_percent=100*p.difference(s).area/p.area,
            user_confirmed_height=c['image'] != 'e9zR4mvMWw7-09',
            source_ceiling_h=c['source_plane']['plane'][2],
            source_floor=source['floor_xz_h'], target_floor=c['floor_xz_h'],
            outside_geometry=p.difference(s).__geo_interface__))
    assert len(cases) == 9 and {c['image'] for c in cases} == set(OBSERVATIONS)
    payload = dict(schema='scope_height_review_20261028_v2', revision=revision['exported_at'], cases=cases)
    (OUT / 'height-review-data.js').write_text('window.SCOPE_HEIGHT_DATA=' + json.dumps(payload, ensure_ascii=False, allow_nan=False) + ';\n', encoding='utf-8')
    prefix = Path(os.path.relpath(VIEWER, OUT)).as_posix()
    template = Path(__file__).with_suffix('.html').read_text(encoding='utf-8')
    for name in ['workbench.css', 'workbench-core.js', 'geometry-view.js']:
        assert (VIEWER / name).is_file()
    (OUT / 'height-review.html').write_text(template.replace('__VIEWER__', prefix), encoding='utf-8')
    print('9 cases; original images and viewer dependencies found; no prefilled decisions')


if __name__ == '__main__':
    build()
