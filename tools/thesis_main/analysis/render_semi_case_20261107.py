"""Render archived initialization and raw edits; preserve every submitted point."""
from pathlib import Path
import json
import sys
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from PIL import Image

ROOT = Path(__file__).resolve().parents[3]
PAPER = ROOT / 'docs/thesis_main/论文提纲_LaTeX_20261028'
WORK = ROOT / 'docs/thesis_main/论文写作工作资料'
PROPOSALS = ROOT / 'analysis_results/uncertainty_cloud_inputs_20260906_v1/facts/proposal_response.csv.gz'
EVIDENCE = ROOT / 'research/workers/worker_v1_pro_integration_20261017'
OPPORTUNITIES = ROOT / 'research/workers/personnel_profiles_composition_20261020/source/tables/profiles/semi_error_opportunity_index.csv'
PHOTO = ROOT / 'data/mp3d_layout/test/img/Z6MFQCViBuw_fbef2c9afec642c88d01cf09c90aec12.png'
UNCHANGED = 'eb2fd1fd3f466605'
EDITED = '1f8fe248fb55c43e'
BASE = '#007d91'
EXTRA = '#d16a24'
# Wider source-pixel windows preserve room context instead of enlarging 92 x 52 pixels.
CROP_X = (320, 420)
CROP_Y = ((180, 115), (345, 280))
plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 8,
                     'axes.titlesize': 8.5, 'axes.labelsize': 8,
                     'xtick.labelsize': 7, 'ytick.labelsize': 7,
                     'pdf.fonttype': 42, 'axes.linewidth': .6})


def load_case():
    proposals = pd.read_csv(PROPOSALS).set_index('canonical_annotation_id')
    evidence = pd.read_csv(EVIDENCE / 'initialization_evidence.csv').set_index('object_id')
    corrections = pd.read_csv(EVIDENCE / 'semi_correction_evidence.csv').set_index('object_id')
    ids = pd.read_csv(PAPER / 'annotator_id_mapping.csv').set_index('source_worker_id')['paper_annotator_id']
    initial = np.array(json.loads(proposals.loc[UNCHANGED, 'initial_points_json']))
    finals = {}
    for oid in [UNCHANGED, EDITED]:
        row = proposals.loc[oid]
        assert np.array_equal(initial, np.array(json.loads(row.initial_points_json)))
        final = np.array(json.loads(row.final_points_json))
        ev = evidence.loc[oid]
        assert ev.initialization_source_verified and corrections.loc[oid, 'confirmed_initialization_error_opportunity']
        # Check archived raw task output, rather than a subsequently repaired layout.
        tasks = json.loads((ROOT / ev.runtime_source).read_text(encoding='utf-8-sig'))
        task = next(t for t in tasks if t['id'] == ev.runtime_task)
        answer = next(a for a in task['annotations'] if a['id'] == ev.runtime_annotation)
        raw = np.array([[r['value']['x'] * 10.24, r['value']['y'] * 5.12]
                        for r in answer['result'] if r.get('type') == 'keypointlabels'])
        assert np.allclose(final, raw, atol=1e-9, rtol=0)
        imports = json.loads(ev.import_paths)
        found = []
        for path in imports:
            for t in json.loads((ROOT / path).read_text(encoding='utf-8-sig')):
                if str(t.get('data', {}).get('base_task_id') or t.get('data', {}).get('image_id')) == row.image_id:
                    for pred in t.get('predictions', []):
                        found.append(np.array([[r['value']['x'] * 10.24, r['value']['y'] * 5.12]
                                               for r in pred.get('result', []) if r.get('type') == 'keypointlabels']))
        assert found and all(p.shape == initial.shape and np.allclose(p, initial, atol=1e-9, rtol=0) for p in found)
        finals[oid] = {'points': final, 'worker': ev.worker_id, 'paper_id': ids[ev.worker_id],
                       'task': int(ev.runtime_task), 'annotation': int(ev.runtime_annotation),
                       'runtime_source': ev.runtime_source, 'imports': imports}
    assert np.array_equal(initial, finals[UNCHANGED]['points'])
    assert np.array_equal(np.delete(initial, [4, 5], axis=0), finals[EDITED]['points'])
    opp = pd.read_csv(OPPORTUNITIES)
    counts = {c: int(opp[c].eq(True).sum()) for c in
              ['semi_confirmed_error_opportunity', 'semi_known_error_unchanged',
               'semi_reported_error_opportunity', 'semi_reported_known_error_unchanged']}
    assert list(counts.values()) == [156, 25, 284, 45], counts
    return initial, finals, counts


def draw():
    initial, finals, counts = load_case()
    snapshots = [initial.copy()] + [v['points'].copy() for v in finals.values()]
    photo = Image.open(PHOTO)
    assert photo.size == (2048, 1024), 'Use the registered full-resolution panorama, not the task JPEG.'
    fig = plt.figure(figsize=(7.2, 4.65))
    context = fig.add_axes([.06, .59, .49, .38])
    context.imshow(photo, extent=[0, 1024, 512, 0])
    for i, (top, bottom) in enumerate(zip(initial[::2], initial[1::2])):
        color = EXTRA if i == 2 else BASE
        context.plot(*np.vstack([top, bottom]).T, color=color, lw=.6)
        context.scatter(*np.vstack([top, bottom]).T, s=6, color=color, zorder=5)
    for high, low in CROP_Y:
        context.add_patch(Rectangle((CROP_X[0], low), CROP_X[1]-CROP_X[0], high-low,
                                    fill=False, ec='white', lw=.85))
    context.set(xlim=(0, 1024), ylim=(512, 0))
    context.axis('off')
    context.set_title('Shared panorama and initialization', loc='left', pad=3)

    stats = fig.add_axes([.60, .63, .37, .29])
    stats.set(xlim=(0, 100), ylim=(-.7, 1.7))
    for y, total, unchanged, label in [(1, 156, 25, 'Expert-confirmed errors'),
                                       (0, 284, 45, 'Reported errors')]:
        stats.barh(y, 100, height=.23, color='#e7edf0')
        stats.barh(y, 100 * unchanged / total, height=.23, color=EXTRA)
        stats.text(0, y + .22, label, fontsize=8)
        stats.text(100, y + .22, f'{unchanged}/{total}', ha='right', fontsize=8, weight='bold')
    stats.axis('off')
    stats.set_title('Unchanged submissions', loc='left', pad=5)
    stats.text(0, -.65, 'Separate opportunity sets', fontsize=7.5, color='#53636e')

    points_list = [initial, finals[UNCHANGED]['points'], finals[EDITED]['points']]
    titles = ['(a) Initialization · 5 pairs',
              f"(b) {finals[UNCHANGED]['paper_id']} unchanged · 5 pairs",
              f"(c) {finals[EDITED]['paper_id']} edited · 4 pairs"]
    for col, (points, title) in enumerate(zip(points_list, titles)):
        for row, (yrange, yloc) in enumerate(zip(CROP_Y, [.33, .07])):
            ax = fig.add_axes([.075 + .315 * col, yloc, .272, .205])
            # Crop directly from 2048 x 1024 input, then map to the unchanged annotation coordinates.
            box = (2*CROP_X[0], 2*yrange[1], 2*CROP_X[1], 2*yrange[0])
            crop = photo.crop(box)
            assert crop.size == (200, 130)
            ax.imshow(crop, extent=[*CROP_X, *yrange], interpolation='none')
            selected = points[row::2]
            colors = [EXTRA if np.isclose(p[0], initial[4, 0]) else BASE for p in selected]
            ax.scatter(*selected.T, s=19, c=colors, edgecolors='white', linewidths=.55, zorder=5)
            ax.set(xlim=CROP_X, ylim=yrange, xticks=[320, 350, 380, 410])
            ax.set_yticks([120, 145, 170] if row == 0 else [285, 310, 335])
            ax.tick_params(length=2, pad=2)
            if row == 0:
                ax.set_title(title, fontsize=8.2, pad=5)
                ax.set_xticklabels([])
            else:
                ax.set_xlabel('Panorama u (px)', labelpad=2)
            if col == 0:
                ax.set_ylabel(('Ceiling' if row == 0 else 'Floor') + ' v (px)', labelpad=3)
            else:
                ax.set_yticklabels([])
    for before, after in zip(snapshots, points_list):
        assert np.array_equal(before, after)
    out = PAPER / 'figures/semi_editing'
    for ext in ['pdf', 'png']:
        fig.savefig(out.with_suffix('.' + ext), dpi=300, bbox_inches='tight', pad_inches=.06)
    plt.close(fig)
    audit = {'case': 'Z6MFQCViBuw-10', 'case_image_id': 'Z6MFQCViBuw_fbef2c9afec642c88d01cf09c90aec12',
             'identity': 'frozen v2 study; exact initialization and raw v1 submissions',
             'photo': str(PHOTO.relative_to(ROOT)), 'photo_size_px': list(photo.size),
             'detail_source_size_px': [200, 130], 'detail_x_annotation_px': CROP_X,
             'detail_y_annotation_px': CROP_Y, 'image_processing': 'Source-pixel crop only; no AI restoration, sharpening, or resynthesis.',
             'counts': counts,
             'initial_points': initial.tolist(), 'submissions': {k: {**v, 'points': v['points'].tolist()} for k, v in finals.items()},
             'source_tables': [str(p.relative_to(ROOT)) for p in [PROPOSALS, EVIDENCE / 'initialization_evidence.csv',
                               EVIDENCE / 'semi_correction_evidence.csv', OPPORTUNITIES]],
             'checks': ['initializations identical across both submissions', 'initialization matches deployment import payload',
                        'final coordinates match raw runtime export', 'unchanged final equals initialization exactly',
                        'edited final removes only the added pair at u=369.144', 'drawing leaves input arrays unchanged'],
             'interpretation': 'Edited is an observable coordinate action, not a newly adjudicated successful correction.',
             'ring_note': 'No perimeter ring is reconstructed; exact point pairs alone are shown because native initialization ring is unconfirmed.'}
    (WORK / 'semi_editing_source.json').write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'figure': str(out), 'counts': counts, 'checks': 'passed'}, ensure_ascii=False))


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    draw()
