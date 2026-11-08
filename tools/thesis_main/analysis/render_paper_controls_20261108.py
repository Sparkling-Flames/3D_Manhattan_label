"""Compose publication-width controls from unchanged archived coordinates and scores."""
from pathlib import Path
import io
import json
import zipfile
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import fitz
from render_controlled_geometry_figures_20261107 import SOURCE, OUT, project, draw_geometry

ROOT = Path(__file__).resolve().parents[3]
PAPER = ROOT / 'docs/thesis_main/论文提纲_LaTeX_20261028'


def main():
    with zipfile.ZipFile(SOURCE) as z:
        frame = pd.read_csv(io.BytesIO(z.read('q_iou_eight_cases/results_all.csv')))
        geometries = json.loads(z.read('q_iou_eight_cases/geometries.json'))
    assert len(frame) == len(geometries) == 66
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 8,
                         'axes.labelsize': 8, 'axes.titlesize': 8,
                         'xtick.labelsize': 8, 'ytick.labelsize': 8, 'pdf.fonttype': 42})
    for case, name, labels in [
        ('C2', 'height_control', ['Reference', 'Opposite shifts: ±20%']),
        ('C4', 'collinear_control', ['4 point pairs', '16 point pairs'])]:
        data = frame[frame.case == case].sort_values('amount')
        gs = [g for g in geometries if g['case'] == case]
        selected = [gs[0], next(g for g in gs if g['amount'] == (.2 if case == 'C2' else 12))]
        if case == 'C4':
            assert np.ptp(data.Q) < 1e-8
            assert data.candidate_nodes.tolist() == [4, 5, 8, 16]
        pts = np.vstack([v for g in selected for kind in ['reference', 'candidate'] for v in project(g[kind])])
        low, high = pts.min(0), pts.max(0)
        pad = (high-low)*.08
        limits = ((low[0]-pad[0], high[0]+pad[0]), (low[1]-pad[1], high[1]+pad[1]))
        fig = plt.figure(figsize=(3.45, 2.95))
        grid = fig.add_gridspec(2, 2, height_ratios=[1, 1], left=.17,
                               right=.97, bottom=.34, top=.94, hspace=.5, wspace=.15)
        for i, (g, label) in enumerate(zip(selected, labels)):
            ax = fig.add_subplot(grid[0, i])
            draw_geometry(ax, g, True, limits)
            ax.set_title(f'({chr(97+i)}) {label}', fontsize=8)
        ax = fig.add_subplot(grid[1, :])
        x = data.amount*100 if case == 'C2' else data.candidate_nodes
        ax.plot(x, data.Q, 'o-', color='#267788', ms=3, lw=1, label='Geometric quality Q')
        ax.plot(x, data.prism_iou100, 's--', color='#c16a32', ms=3, lw=1,
                label='Corner-mean prism IoU × 100')
        ax.set(xlabel='Opposite height shift (%)' if case == 'C2' else 'Number of point pairs',
               ylabel='Index value', ylim=(0,105) if case == 'C2' else (60,105))
        if case == 'C4': ax.set_xticks([4,5,8,16])
        ax.grid(alpha=.15); ax.spines[['top','right']].set_visible(False)
        fig.legend(*ax.get_legend_handles_labels(), loc='lower center', frameon=False,
                   bbox_to_anchor=(.5,.015), fontsize=8)
        fig.savefig(PAPER/'figures'/f'{name}.pdf')
        fig.savefig(OUT/f'{name}_single_column.png', dpi=220)
        plt.close(fig)
    supplement = fitz.open()
    page = supplement.new_page()
    page.insert_textbox(fitz.Rect(50,50,545,790),
        'Supplement A: Controlled geometric perturbations\n\n'
        'Eight families, 66 archived configurations\n\n'
        'S1 / C1: Uniform ceiling-height changes\n'
        'S2 / C2: Balanced local height changes\n'
        'S3 / C3: Concentrated versus distributed height errors\n'
        'S4 / C4: Collinear resampling of unchanged geometry\n'
        'S5 / C5: Shear versus translation\n'
        'S6 / C6: Near-wall versus far-wall displacement\n'
        'S7 / C7: Omission of a narrow alcove\n'
        'S8 / C8: Non-orthogonal reference geometry\n\n'
        'Coordinates and scores are reproduced from the archived controls without '
        'rescoring or geometric correction. Points show all supplied configurations; '
        'lines connect observations. IoU is multiplied by 100; Q and IoU remain '
        'different indices. Dimensions are specified in each panel.\n\n'
        'The prism baseline uses the arithmetic mean of corner heights. It is '
        'distinct from volume IoU of a variable-height solid. C2 additionally '
        'shows the analytic volume IoU of its planar tilted top. C4 additionally '
        'shows the perimeter-weighted-height prism comparison. Added point pairs '
        'subdivide existing straight boundaries rather than creating new turns.\n\n'
        'C8 diagnoses the task representation: Q includes a direction requirement '
        'as well as reference-relative measurements. It is not an in-domain '
        'accuracy comparison. These controls test measurement response, not human preference.',
        fontsize=11)
    source = fitz.open(OUT/'controlled_geometry.pdf')
    assert len(source) == 8
    supplement.insert_pdf(source)
    for i in range(1, len(supplement)):
        page = supplement[i]
        page.insert_text((24, page.rect.height-12), f'Figure S{i} (control C{i})', fontsize=9)
    supplement.save(PAPER/'supplement_geometry.pdf')
    print('Two single-column figures and nine-page Supplement A written; 66 archived configurations retained.')


if __name__ == '__main__':
    main()
