"""Draw the two author-selected screening examples from frozen geometry."""
import csv
import gzip
import json
import math
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patheffects as pe
from matplotlib.patches import Rectangle
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT / 'research/data/doorway_review_20261030'
PAPER = ROOT / 'docs/thesis_main/论文提纲_LaTeX_20261028'
BLUE, ORANGE = '#0072B2', '#E69F00'


def projected_rings(points):
    bottom, top = [], []
    for (u, v), (ub, vb) in zip(points[::2], points[1::2]):
        radius = 1 / math.tan((vb / 512 - .5) * math.pi)
        angle = (ub / 1024 - .5) * math.tau
        bottom.append([radius * math.sin(angle), -1, -radius * math.cos(angle)])
        angle = (u / 1024 - .5) * math.tau
        top.append([radius * math.sin(angle), radius * math.tan((.5 - v / 512) * math.pi), -radius * math.cos(angle)])
    for ring in [bottom, top]:
        for a, b in zip(ring, ring[1:] + ring[:1]):
            xyz = np.array(a)[None, :] * (1 - np.linspace(0, 1, 200)[:, None]) + np.array(b)[None, :] * np.linspace(0, 1, 200)[:, None]
            x, y, z = xyz.T
            uv = np.column_stack(((np.arctan2(x, -z) / math.tau + .5) * 1024,
                                  (.5 - np.arctan2(y, np.hypot(x, z)) / math.pi) * 512))
            # Break the drawing at the panorama seam, preserving the saved ring.
            uv[np.r_[False, np.abs(np.diff(uv[:, 0])) > 512]] = np.nan
            yield uv


def main():
    review = BASE / 'expanded_visual_review_20261031'
    rows = json.loads((review / 'REVIEW_INPUT.json').read_text(encoding='utf-8'))
    ledger = {r['object_id']: r for r in json.loads((review / 'FINAL_SCREENING_LEDGER.json').read_text(encoding='utf-8'))['records']}
    cases = {r['image']: r for r in json.loads((BASE / 'data.js').read_text(encoding='utf-8').split('=', 1)[1][:-1])['cases']}
    frozen = ROOT / 'research/fusion/doorway_population_v21_20261031/HOHONET_doorway_v21_20261031/stage04_computation/design/FROZEN_RECORDS.json.gz'
    records = json.loads(gzip.decompress(frozen.read_bytes()))
    with (PAPER / 'annotator_id_mapping.csv').open(encoding='utf-8-sig', newline='') as f:
        aliases = {r['source_worker_id']: r['paper_annotator_id'] for r in csv.DictReader(f)}
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 8, 'pdf.fonttype': 42})
    fig, axes = plt.subplots(2, 2, figsize=(7.2, 4.3), gridspec_kw={'height_ratios': [1, 1.3]})
    specs = [(447, 'W102', 'B6ByNegPMKs-43', (180, 550, 45, 465), 'Crossing connections near the doorway'),
             (472, 'W114', 'b8cTxDM8gDG-08', (190, 530, 45, 495), 'Near and distant boundary points connected')]
    for col, (index, worker, image, box, description) in enumerate(specs):
        row = rows[index]
        assert (row['worker'], row['image']) == (worker, image)
        assert ledger[row['object_id']]['eligibility'] == '排除'
        points = np.asarray(records[row['object_id']]['points'], dtype=float)
        assert points.shape == ((10 if col == 0 else 8), 2) and np.isfinite(points).all()
        photo = Image.open((BASE / cases[image]['photo']).resolve()).convert('RGB')
        curves = list(projected_rings(points))
        assert len(curves) == len(points)
        expected = []
        for ring in [points[1::2], points[::2]]:
            expected.extend(zip(ring, np.roll(ring, -1, axis=0)))
        for curve, endpoints in zip(curves, expected):
            np.testing.assert_allclose(curve[[0, -1]], endpoints, atol=1e-8)
        for ax in axes[:, col]:
            ax.imshow(photo, extent=(0, 1024, 512, 0))
            for curve in curves:
                ax.plot(curve[:, 0], curve[:, 1], color=BLUE, lw=1.1, path_effects=[pe.Stroke(linewidth=1.8, foreground='white'), pe.Normal()])
            for pair in points.reshape(-1, 2, 2):
                ax.plot(pair[:, 0], pair[:, 1], color=BLUE, lw=.8)
            ax.scatter(points[:, 0], points[:, 1], s=9, color=ORANGE, edgecolor='white', linewidth=.35, zorder=4)
            ax.set_axis_off()
        x0, x1, y0, y1 = box
        axes[0, col].add_patch(Rectangle((x0, y0), x1-x0, y1-y0, fill=False, edgecolor=ORANGE, linestyle='--', lw=1))
        axes[0, col].set(xlim=(0, 1024), ylim=(512, 0))
        axes[0, col].set_title(f'({chr(97+col)}) {image} / {aliases[worker]}', loc='left', fontsize=8)
        axes[1, col].set(xlim=(x0, x1), ylim=(y1, y0))
        axes[1, col].set_title(f'({chr(99+col)}) {description}', fontsize=8, pad=6)
        print(f'{worker} -> {aliases[worker]}: {row["object_id"]}; {len(points)//2} pairs; excluded')
    fig.subplots_adjust(left=.015, right=.985, top=.94, bottom=.015, wspace=.08, hspace=.20)
    fig.savefig(PAPER / 'figures/doorway_screening_examples.pdf', dpi=300)
    plt.close(fig)


if __name__ == '__main__':
    main()
