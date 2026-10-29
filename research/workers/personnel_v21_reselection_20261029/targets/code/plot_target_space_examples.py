#!/usr/bin/env python3
"""Plot exact frozen target references; these are BEV plans, not photo reviews."""
import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

from frozen_geometry_traits import reference_traits

ap = argparse.ArgumentParser()
ap.add_argument('--repo', type=Path, required=True)
ap.add_argument('--fallback-source', type=Path)
ap.add_argument('--out', type=Path, required=True)
args = ap.parse_args()
base = Path('research/data/releases/v2.1')
pools = []
for path, kind in [(base / 'pools/INPUT_SNAPSHOT.json', 'Primary'),
                   (base / 'admitted_space_extension/pools/INPUT_SNAPSHOT.json', 'Other')]:
    file = args.repo / path
    if not file.exists():
        file = args.fallback_source / path
    pools.extend((kind, p) for p in json.loads(file.read_text())['images'])
images = ['B6ByNegPMKs-37', 'UwV83HsGsw3-10', 'wc2JMjhGNzB-26', 'uNb9QFRL6hY-88']
colors = ['#1b4965', '#d06b2c', '#5c9270', '#ae4e7c']
fig, axes = plt.subplots(2, 2, figsize=(12.8, 10.3))
for ax, image in zip(axes.flat, images):
    selected = [(kind, p) for kind, p in pools if p['meta']['image'] == image and p['meta']['condition'] == 'manual']
    for j, (kind, p) in enumerate(selected):
        ref = p['reference']; floor = np.asarray(ref['floor_xz_h'])
        traits = reference_traits(floor)
        closed = np.vstack([floor, floor[0]])
        tid = ref['target_id']
        name = 'Space C' if ':space_c:' in tid else 'Space D' if ':space_d:' in tid else 'Other MP3D' if kind == 'Other' else 'Primary'
        ax.plot(closed[:, 0], closed[:, 1], marker='o', markersize=3.3,
                color=colors[j], lw=2 if kind == 'Primary' else 1.8,
                linestyle='-' if kind == 'Primary' else '--',
                label=f"{name}: N={p['meta']['pool_n']}, turn={traits['ref_turn5']}, H={traits['ref_H']}, short={traits['ref_short_edges']}")
    ax.scatter([0], [0], marker='*', s=110, c='#161c20', zorder=9)
    ax.set_title(image, fontsize=12.5, loc='left', weight='bold')
    ax.set_aspect('equal', adjustable='datalim')
    ax.set_xlabel('x / camera height'); ax.set_ylabel('z / camera height')
    ax.grid(alpha=.17)
    ax.legend(fontsize=8.3, loc='best', framealpha=.9)
fig.suptitle('Same photograph, different admitted target spaces', fontsize=17, weight='bold', y=.99)
fig.text(.5, .012, 'Frozen v2.1 references. Star = camera. H = boundary-model self-occlusion; no photo visibility claim.\n'
         'Teams and quality references stay within each target; formal difficulty is not inherited across spaces.',
         ha='center', fontsize=10, color='#42484d')
fig.tight_layout(rect=[0, .06, 1, .96])
args.out.parent.mkdir(parents=True, exist_ok=True)
fig.savefig(args.out, dpi=170, facecolor='white')
plt.close(fig)
print(args.out)
