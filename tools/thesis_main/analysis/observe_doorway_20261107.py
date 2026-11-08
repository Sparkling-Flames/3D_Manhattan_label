"""2t7-07 原图透视观察。复用已有球面投影，不读取 GT 建立空间。"""
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(Path(__file__).parent / 'visual_takeover_20260906'))
from render import perspective, m

OUT = ROOT / 'docs/thesis_main/论文写作工作资料/门洞实景观察_20261107'
SOURCES = {
    '07': '2t7WUuJeko7_53937db036374126830e0f1203b04ead',
    '08': '2t7WUuJeko7_5db6d45b905f458a8290e69ff3e8d820',
    '15': '2t7WUuJeko7_b72b7b78675f429a9f382a44e551cffc',
    '16': '2t7WUuJeko7_cc34e9176bfe47ebb23c58c165203134',
}
VIEWS = [
    ('07', 'hall', 0, 0, 85),
    ('07', 'bathroom_across_seam', 180, 0, 110),
    ('07', 'left_leaf_and_reveal', -80, 0, 80),
    ('07', 'right_jamb_and_cupboard', 83, 0, 80),
    ('07', 'overhead', 0, 65, 95),
    ('07', 'lower_doorway', 0, -58, 95),
    ('08', 'door_and_cupboard', 70, 0, 100),
    ('15', 'window_and_tub', -95, -20, 90),
    ('16', 'door_sink_tank', 0, -10, 100),
]


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    original = {}
    for number, image_id in SOURCES.items():
        path = ROOT / 'data/mp3d_layout/valid/img' / (image_id + '.png')
        original[number] = np.array(Image.open(path).convert('RGB'))
        assert original[number].shape == (1024, 2048, 3)
    # 校验复用投影的中心方位、接缝及原图中心采样，避免观察方位颠倒。
    uv = np.array([[0., 256.], [512., 256.], [768., 128.]])
    assert np.allclose(m.project(m.ray(uv)), uv, atol=1e-8)
    center, _ = perspective(original['07'], 0, w=901, h=651, fov=85)
    assert np.array_equal(np.array(center)[325, 450], original['07'][512, 1024])

    # 周期平移只把原图接缝移到画面中央，没有改变任何像素。
    rolled = np.roll(original['07'], 1024, axis=1)
    assert np.array_equal(np.roll(rolled, -1024, axis=1), original['07'])
    Image.fromarray(rolled).save(OUT / '07_bathroom_seam_unwrapped.png')
    records = []
    font = ImageFont.truetype('C:/Windows/Fonts/arial.ttf', 23)
    panels = []
    for number, name, yaw, pitch, fov in VIEWS:
        view, meta = perspective(original[number], yaw, pitch, w=900, h=650, fov=fov)
        file = f'{number}_{name}.png'
        view.save(OUT / file)
        records.append(dict(image_id=SOURCES[number], file=file, **meta))
        panel = Image.new('RGB', (920, 700), 'white')
        panel.paste(view, (10, 42))
        ImageDraw.Draw(panel).text((10, 8), f'{number} | {name.replace("_", " ")} | yaw {yaw}', font=font, fill='#263744')
        panels.append(panel)
    for name, indices, cols in [('07_observation', range(6), 2), ('same_room_views', range(6, 9), 3)]:
        indices = list(indices)
        canvas = Image.new('RGB', (920 * cols, 700 * ((len(indices) + cols - 1) // cols)), 'white')
        for i, ix in enumerate(indices):
            canvas.paste(panels[ix], ((i % cols) * 920, (i // cols) * 700))
        canvas.save(OUT / (name + '.png'))

    # GT仅作为二维观察对象；不连接成墙、不反投影为实体。
    gt_path = ROOT / 'data/mp3d_layout/valid/label_cor' / (SOURCES['07'] + '.txt')
    gt = np.loadtxt(gt_path).reshape(-1, 2, 2)
    assert gt.shape == (6, 2, 2)
    comparison = Image.new('RGB', (2048, 1130), 'white')
    comparison.paste(Image.fromarray(original['07']), (0, 55))
    draw = ImageDraw.Draw(comparison)
    label_font = ImageFont.truetype('C:/Windows/Fonts/arial.ttf', 28)
    draw.text((20, 12), '07 | Original panorama + six unchanged GT point pairs (2D comparison only)', font=label_font, fill='#263744')
    for i, pair in enumerate(gt):
        xy = pair * 2 + [0, 55]
        draw.line([tuple(p) for p in xy], fill='#f7ae38', width=3)
        for x, y in xy:
            draw.ellipse((x-7, y-7, x+7, y+7), fill='#f7ae38', outline='white', width=2)
        draw.text(tuple(xy[0]+[8, -32]), f'P{i+1}', font=label_font, fill='#f7ae38', stroke_width=2, stroke_fill='#192026')
    draw.rectangle((1440, 230, 1605, 910), outline='#00bcd4', width=5)
    draw.text((20, 1090), 'Cyan box: near right jamb/reveal; no GT point pair here. Box is not a measured floor endpoint.', font=label_font, fill='#263744')
    comparison.save(OUT / 'reference_points_only.png')
    (OUT / 'sources.json').write_text(json.dumps({
        'purpose': '原始照片的确定性透视观察；没有建模、补画、AI修复或GT几何输入。',
        'source_dimensions': [2048, 1024],
        'resampling': 'existing perspective(), cv2.INTER_LINEAR; output size adds no observed detail',
        'same_room_source': 'research/same_room/relation_adoption_20261016/original_groups.json#G004',
        'same_room_scope': '07门洞对照；08、15、16同房核心；未做位姿配准',
        'reference_comparison': {'source': gt_path.relative_to(ROOT).as_posix(), 'role': '2D point overlay only; not reconstruction geometry', 'point_pairs': 6, 'points_1024x512': gt.tolist()},
        'checks': ['projection roundtrip', 'center sample equals source pixel', 'four source dimensions', 'cyclic shift exactly reversible', 'six GT pairs overlaid without editing'],
        'views': records,
    }, ensure_ascii=False, indent=2), encoding='utf-8')
    print('9 perspective views, 2 observation sheets, seam view and 2D GT comparison saved; checks passed.')


if __name__ == '__main__':
    main()
