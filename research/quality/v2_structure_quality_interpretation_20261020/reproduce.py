"""v2结构质量小型诊断；只读取冻结输入，不修改资格、参考或评分。"""
from collections import defaultdict
from copy import deepcopy
from itertools import combinations
import gzip
import json
from math import pi, tan
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image

from tools.thesis_main.analysis.scope_quality_scoring_20261016 import scoring_engine, score_task

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
AUDIT = ROOT / 'research/statistics/v2_evidence_audit_20261019/records.json.gz'
CASES = ROOT / 'research/workers/personnel_composition_followup_20261019/STRUCTURE_CASES.json'
TEAMS = ROOT / 'research/workers/personnel_composition_followup_20261019/TEAMS.json.gz'
PAIR_IDS = ('v2:new:106360', 'v2:new:106376')
CONTROLS = (('v2:new:100738', 1), ('v2:new:101870', 0))


def xz(points):
    bottom = np.asarray(points[1::2], dtype=float)
    phi = (bottom[:, 1] / 512 - .5) * pi
    radius = 1 / np.tan(phi)
    azimuth = bottom[:, 0] / 1024 * 2 * pi
    return np.column_stack((-radius * np.sin(azimuth), radius * np.cos(azimuth)))


def task(row):
    ref = row['reference_evidence']
    return dict(object_id=row['object_id'], image_id=row['image_id'], worker_id=row['worker_id'],
                condition=row['condition'], current_target_id=ref['target_id'],
                reference_version=row['reference_version'], annotation_points=row['points_1024x512'],
                reference_points=ref['points_1024x512'], reference_full_available=True)


def main():
    with gzip.open(AUDIT, 'rt', encoding='utf-8') as stream:
        records = json.load(stream)['records']
    by_id = {r['object_id']: r for r in records}
    non_oos = [r for r in records if not r['is_oos']]
    primary = [r for r in non_oos if not r['is_doorway'] and r['condition'] == 'manual'
               and r['quality_use'] == 'ordinary_primary' and r['calculation_class'] == 'full']
    by_target = defaultdict(list)
    for r in primary:
        by_target[(r['image_code'], r['reference_id'])].append(r)
    matched = [(a, b) for group in by_target.values() for a, b in combinations(group, 2)
               if abs(a['IoU3D100'] - b['IoU3D100']) < 1]
    large_gap = [(a, b) for a, b in matched if abs(a['B8L2'] - b['B8L2']) > 20]
    a, b = (by_id[x] for x in PAIR_IDS)
    assert a['reference_id'] == b['reference_id'] and a['point_count'] == b['point_count'] == 12
    assert abs(a['IoU3D100'] - b['IoU3D100']) < 1

    with scoring_engine() as (engine, models):
        ablations = {}
        for r in (a, b):
            m = r['measurements']['same_reference_measurements']
            ablations[r['object_id']] = float(models.score(m['iou_2d'], m['S_bottom_deg'], 0,
                                                            m['Hmean'], m['Hcenter'], models.B))
        controls = []
        for oid, pair in CONTROLS:
            r = by_id[oid]
            y = r['points_1024x512'][2 * pair + 1][1]
            trials = []
            for dy in (-2, 0, 2):
                t = deepcopy(task(r))
                t['annotation_points'][2 * pair + 1][1] += dy
                s = score_task(t, engine, models)
                assert s['score_status'] == 'complete'
                trials.append(dict(dy_px=dy, B8L2=s['B8L2'], IoU3D100=s['IoU3D100'],
                                   floor_IoU=s['iou_2d'], direction_deg=s['dir']))
            assert abs(trials[1]['B8L2'] - r['B8L2']) < 1e-9
            radius = lambda yy: 1 / tan((yy / 512 - .5) * pi)
            controls.append(dict(object_id=oid, image=r['image_code'], pair_index=pair,
                                 original_bottom_y_px=y, radial_distance_h=[radius(y + d) for d in (-2, 0, 2)],
                                 trials=trials))

    with open(CASES, encoding='utf-8') as stream:
        fusion_cases = json.load(stream)['cases']
    with gzip.open(TEAMS, 'rt', encoding='utf-8') as stream:
        teams = json.load(stream)
    fusion = []
    for c in fusion_cases:
        arms = {}
        for arm, z in c['teams'].items():
            t = teams[z['key']]
            arms[arm] = {key: t[key] for key in ('nodes', 'B8L2', 'IoU3D100', 'iou_2d',
                        'S_bottom_deg', 'dir', 'Hmean', 'Hcenter', 'ref_node_recall_9', 'ref_edge_recall_9')}
        fusion.append(dict(case=c['case'], image=c['event']['image'], arms=arms))

    output = dict(source='research/statistics/v2_evidence_audit_20261019/records.json.gz',
                  non_oos_records=len(non_oos), non_oos_images=len({r['image_code'] for r in non_oos}),
                  doorway_records=sum(r['is_doorway'] for r in non_oos),
                  doorway_images=len({r['image_code'] for r in non_oos if r['is_doorway']}),
                  ordinary_manual_primary_records=len(primary),
                  ordinary_manual_primary_images=len({r['image_code'] for r in primary}),
                  matched_same_reference_pair_count=len(matched), large_gap_pair_count=len(large_gap),
                  large_gap_images=len({a['image_code'] for a, _ in large_gap}),
                  large_gap_buildings=len({a['building_id'] for a, _ in large_gap}),
                  large_gap_same_vertex_count=sum(a['point_count'] == b['point_count'] for a, b in large_gap),
                  spotlight={r['object_id']: dict(image=r['image_code'], worker=r['worker_id'],
                      B8L2=r['B8L2'], D10=r['D10'], IoU3D100=r['IoU3D100'],
                      components={k:r['measurements']['same_reference_measurements'][k]
                                  for k in ('iou_2d', 'S_bottom_deg', 'dir', 'Hmean', 'Hcenter')},
                      B8L2_direction_zero=ablations[r['object_id']]) for r in (a,b)},
                  control=controls, fusion=fusion)
    (OUT / 'FINDINGS.json').write_text(json.dumps(output, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

    fig, ax = plt.subplots(figsize=(7.5, 5.5))
    ax.scatter([r['IoU3D100'] for r in primary], [r['B8L2'] for r in primary], s=5, alpha=.13,
               color='#526982', rasterized=True)
    ax.plot([a['IoU3D100'], b['IoU3D100']], [a['B8L2'], b['B8L2']], '-o',
            color='#ca4a38', lw=2, ms=7)
    ax.annotate('same image, same reference\n6 vertices each',
                (b['IoU3D100'], b['B8L2']), xytext=(-180, -55), textcoords='offset points',
                arrowprops=dict(arrowstyle='->', color='#ca4a38'), fontsize=9)
    ax.set(xlabel='Stored IoU3D100 (mean-height prism proxy)', ylabel='B8L2',
           title='Ordinary Manual: 5,719 eligible annotations')
    ax.grid(alpha=.2); fig.tight_layout(); fig.savefig(OUT / 'score_vs_3d_proxy.png', dpi=170); plt.close(fig)

    photo = ROOT / 'data/mp3d_layout/test/img' / (a['image_id'] + '.png')
    fig = plt.figure(figsize=(12, 8))
    grid = fig.add_gridspec(2, 2, height_ratios=[1.25, 1])
    pano, crop, floor = fig.add_subplot(grid[0, :]), fig.add_subplot(grid[1, 0]), fig.add_subplot(grid[1, 1])
    with Image.open(photo) as im:
        backdrop = im.resize((1024, 512))
        pano.imshow(backdrop, extent=(0, 1024, 512, 0))
        crop.imshow(backdrop, extent=(0, 1024, 512, 0))
    for ax in (pano, crop):
        for row, label, color in ((a['reference_evidence'], 'GT', '#222222'), (a, 'W118', '#1874ba'), (b, 'W134', '#de6623')):
            pts = np.asarray(row['points_1024x512']).reshape(-1, 2, 2)
            ax.scatter(pts[:, 0, 0], pts[:, 0, 1], s=20, facecolors='none', edgecolors=color, label=label)
            ax.scatter(pts[:, 1, 0], pts[:, 1, 1], s=24, marker='v', color=color)
        ax.set(xlim=(0, 1024), ylim=(512, 0), xlabel='panorama x (px)', ylabel='y (px)')
    pano.set_title('yqstnuAEVhm-24: top circles, bottom triangles; same six corners')
    pano.legend(loc='lower right', ncol=3, framealpha=.85)
    crop.set(xlim=(395, 555), ylim=(455, 275), title='Local enlargement: left/front corner region')
    for row, label, color in ((a['reference_evidence'], 'GT', '#222222'), (a, 'W118', '#1874ba'), (b, 'W134', '#de6623')):
        xy = xz(row['points_1024x512']); xy = np.vstack((xy, xy[0]))
        floor.plot(xy[:, 0], xy[:, 1], '-o', color=color, ms=3, label=label)
    floor.plot(0, 0, marker='*', color='black', ms=9, label='camera')
    floor.set(aspect='equal', xlabel='floor x / camera height', ylabel='floor z / camera height',
              title='Normalized BEV, unaligned coordinates')
    floor.grid(alpha=.2); floor.tick_params(labelsize=8)
    fig.tight_layout(); fig.savefig(OUT / 'same_image_overlay.png', dpi=160); plt.close(fig)

    fig, ax = plt.subplots(figsize=(7.5, 4.5))
    for case, color in zip(controls, ('#1874ba', '#de6623')):
        ax.plot([t['dy_px'] for t in case['trials']], [t['B8L2'] for t in case['trials']],
                '-o', color=color, label=case['image'])
    ax.axvline(0, ls='--', color='gray', lw=1)
    ax.set(xlabel='Controlled change to one bottom y (px)', ylabel='Frozen B8L2',
           title='Two real input geometries; only one bottom point moved')
    ax.legend(); ax.grid(alpha=.2); fig.tight_layout()
    fig.savefig(OUT / 'bottom_y_control.png', dpi=170); plt.close(fig)


if __name__ == '__main__':
    main()
