"""Two fixed source/cross-connection figures; no fitting or semantic scoring."""
import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image

from tools.thesis_main.analysis.local_shortcut_projection_20261005 import ARCHIVE
from tools.thesis_main.analysis.layout_reliability_20261005.arc_consensus import paired_wall_proxy, project

ROOT = Path(__file__).resolve().parents[3]
CASES = [
    ('rPc6DW4iMge-06', 'R01557', 6, 'rPc6DW4iMge_186a32a1b7e34cb797731bfa78365db5'),
    ('uNb9QFRL6hY-67', 'R02928', 3, 'uNb9QFRL6hY_ca08ebfb2da647f68db41630637e400b'),
]


def projected_edge(a, b):
    # Positive endpoint rescaling preserves the projected straight-edge locus.
    u, v = a/np.linalg.norm(a), b/np.linalg.norm(b)
    return project((1-np.linspace(0, 1, 513)[:, None])*u + np.linspace(0, 1, 513)[:, None]*v)


def draw_edge(ax, a, b, **style):
    p = projected_edge(a, b)
    for part in np.split(p, np.flatnonzero(abs(np.diff(p[:, 0])) > 512)+1):
        ax.plot(part[:, 0], part[:, 1], **style)


def run(out):
    out.mkdir(parents=True, exist_ok=False)
    manifest = []
    for image, rid, source_index, image_id in CASES:
        roster = json.loads((ARCHIVE/'inputs'/f'{image}.json').read_text(encoding='utf-8'))['records']
        r = next(r for r in roster if r['id'] == rid)
        i = r['source_pair_indices'].index(source_index)
        j, k = (i-1) % (len(r['points'])//2), (i+1) % (len(r['points'])//2)
        q = np.asarray(r['points']).reshape(-1, 2, 2)
        top, bottom = paired_wall_proxy(r)
        png = ROOT/'data/mp3d_layout/test/img'/f'{image_id}.png'
        with Image.open(png) as im:
            size = im.size
            pixels = np.array(im)
        fig = plt.figure(figsize=(13, 11), layout='constrained')
        grid = fig.add_gridspec(3, 2, height_ratios=(1, 1, .9))
        raw = fig.add_subplot(grid[0, :]); full = fig.add_subplot(grid[1, :])
        zooms = [fig.add_subplot(grid[2, side]) for side in (0, 1)]
        for ax in [raw, full, *zooms]:
            # Input PNG is 2048x1024; annotations use continuous 1024x512.
            ax.imshow(pixels, extent=(0, 1024, 512, 0), interpolation='nearest')
            ax.set_xlim(0, 1024); ax.set_ylim(512, 0)
        raw.set_title(f'{image} / {rid}: original image (no GT)', fontsize=10); raw.axis('off')
        for xyz in (top, bottom):
            for e in range(len(xyz)):
                draw_edge(full, xyz[e], xyz[(e+1) % len(xyz)], color='white', alpha=.6, linewidth=.6)
        for ax in [full, *zooms]:
            for side, xyz in enumerate((top, bottom)):
                draw_edge(ax, xyz[j], xyz[i], color='#00e5ff', linewidth=1.8)
                draw_edge(ax, xyz[i], xyz[k], color='#00e5ff', linewidth=1.8)
                draw_edge(ax, xyz[j], xyz[k], color='#ff294f', linewidth=1.8, linestyle='--')
                ax.scatter(*q[[j, i, k], side].T, s=24, facecolor='#ffff66', edgecolor='black', zorder=5)
                for e in (j, i, k):
                    ax.annotate(str(r['source_pair_indices'][e]), q[e, side], xytext=(4, 4),
                                textcoords='offset points', color='black', fontsize=9,
                                bbox=dict(facecolor='white', alpha=.9, edgecolor='none', pad=1))
        full.set_title('Cyan: source path | red dashed: new edge | labels: source pair index', fontsize=9)
        for side, ax in enumerate(zooms):
            x, y = q[i, side]
            ax.set_xlim(x-65, x+65); ax.set_ylim(min(512, y+60), max(0, y-60))
            ax.set_title(('Upper' if side == 0 else 'Lower') + f' local window: removed pair {source_index}', fontsize=9)
            ax.set_xlabel('continuous x (1024-wide coordinates)')
        filename = f'{rid}_delete_source_{source_index}.png'
        fig.savefig(out/filename, dpi=160)
        plt.close(fig)
        assert np.allclose(project(top), q[:, 0], atol=1e-9, rtol=0)
        assert np.allclose(project(bottom), q[:, 1], atol=1e-9, rtol=0)
        manifest.append(dict(image=image, record=rid, removed_source_pair_index=source_index,
            kept_anchor_source_pair_indices=[r['source_pair_indices'][j],r['source_pair_indices'][k]],
            source_image=str(png.relative_to(ROOT)).replace('\\','/'), source_image_size=list(size),
            coordinates=[1024,512], figure=filename, endpoint_reprojection_check='passed',
            interpretation='projected declared edges; neither visibility nor physical adjacency certified'))
    (out/'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+'\n', encoding='utf-8', newline='\n')


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out', type=Path, required=True)
    run(p.parse_args().out)
