"""Draw enclosure choices from the complete doorway model floor geometry."""
from pathlib import Path
import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon

HERE = Path(__file__).resolve().parent
OUT = HERE.parents[1] / 'panels/fig15'


def main():
    data = json.loads((HERE / 'target_inputs.json').read_text(encoding='utf-8'))
    targets = {r['name']: r for r in data['targets']}
    assert set(targets) == {'Space 1', 'Space 2', 'Whole'}
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 8,
                         'pdf.fonttype': 42, 'svg.fonttype': 'none'})
    def plan(row):
        points = np.asarray(row['vertices'])
        assert points.ndim == 2 and points.shape[1] == 2 and np.isfinite(points).all()
        angle = np.radians(data['rotation_degrees'])
        rotation = np.array([[np.cos(angle), -np.sin(angle)], [np.sin(angle), np.cos(angle)]])
        return (points - np.asarray(data['camera'])) @ rotation.T
    whole = plan(targets['Whole'])
    for name, color, slug in [('Space 1', '#0072B2', 'space1'),
                              ('Space 2', '#D55E00', 'space2'),
                              ('Whole', '#009E73', 'whole')]:
        row = targets[name]
        points = plan(row)
        assert len(row['closure_edges']) == (0 if name == 'Whole' else 1)
        fig, ax = plt.subplots(figsize=(2.0, 1.45))
        fig.subplots_adjust(left=.03, right=.98, bottom=.04, top=.98)
        ax.plot(*np.vstack([whole, whole[0]]).T, color='#9aa1a6', ls=':', lw=1)
        ax.add_patch(Polygon(points, facecolor=color, alpha=.12, edgecolor='none'))
        ax.plot(*np.vstack([points, points[0]]).T, color=color, lw=1.4)
        for i in row['closure_edges']:
            edge = points[[i, (i+1) % len(points)]]
            ax.plot(*edge.T, color='#20252a', lw=1.5, ls='--', zorder=4)
        ax.plot(0, 0, 'o', mfc='white', mec='white', ms=8, zorder=5)
        ax.plot(0, 0, 'o', mfc='white', mec='#20252a', ms=5, mew=.9, zorder=6)
        ax.plot(0, 0, 'o', color='#20252a', ms=1.7, zorder=7)
        ax.annotate('Camera', (0,0), (.02,.6), textcoords='figure fraction', fontsize=7,
                    arrowprops={'arrowstyle':'-', 'lw':.6, 'shrinkB':5}, ha='left')
        ax.set(xlim=(whole[:,0].min()-.7,whole[:,0].max()+.5),
               ylim=(whole[:,1].min()-.4,whole[:,1].max()+.4), aspect='equal')
        ax.axis('off')
        for ext in ('pdf','svg','png'):
            fig.savefig(OUT / f'target_{slug}.{ext}', dpi=400)
        plt.close(fig)


if __name__ == '__main__':
    main()
