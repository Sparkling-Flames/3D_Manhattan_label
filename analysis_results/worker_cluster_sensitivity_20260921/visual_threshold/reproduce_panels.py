"""Regenerate the eight selected threshold-audit panels; no semantic decisions are inferred."""
from pathlib import Path
import base64
import io
import json
import re
import sys

import numpy as np
import pandas as pd
from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).resolve().parent
REPO = OUT.parents[2]
PACKAGE = REPO / 'analysis_results/panorama_research_received_20260921'
SOURCE = PACKAGE / 'local_recompute/source_work'
FOUNDATION = REPO / 'analysis_results/panorama_studio_20260907_v3'
sys.path.insert(0, str(PACKAGE / 'original_package/code'))
import common as c


def image_ids(obj):
    if isinstance(obj, dict):
        return {obj[k] for k in ['image_id', 'code'] if k in obj and isinstance(obj[k], str)}.union(*(image_ids(v) for v in obj.values()))
    if isinstance(obj, list):
        return set().union(*(image_ids(v) for v in obj))
    return set()


def main():
    c.configure(SOURCE)
    _, records, views, _, _ = c.load()
    results = PACKAGE / 'original_package/results'
    pairs = pd.read_csv(results / 'pair_diagnostics.csv.gz')
    members = pd.read_csv(results / 'current_memberships.csv')
    for method in ['complete', 'representative']:
        labels = members[members.method == method].set_index('id').label
        pairs[method + '_same'] = pairs.a_id.map(labels) == pairs.b_id.map(labels)
    summaries = json.JSONDecoder().raw_decode((FOUNDATION / 'history_data.js').read_text(encoding='utf8').split('push(...', 1)[1])[0]
    lookup = {s['image_id']: s for s in summaries}
    seen = set()
    evidence_paths = [
        SOURCE / 'analysis_results/clustering_release_local_20260920/current/inputs/key39_source.json',
        SOURCE / 'analysis_results/clustering_release_local_20260920/current/inputs/pilot_evidence.json',
        SOURCE / 'analysis_results/clustering_release_local_20260920/current/inputs/new_six_evidence.json',
        SOURCE / 'analysis_results/local_point_clustering_20260920/evidence/review_manifest_16.json',
        SOURCE / 'analysis_results/local_point_clustering_20260920/evidence/latest_decisions.json',
        REPO / 'analysis_results/cluster_review_extra_20260919/evidence.json',
    ]
    for path in evidence_paths:
        seen |= image_ids(json.loads(path.read_text(encoding='utf-8-sig')))
    seen |= {iid for iid, v in views.items() if v['code'] in seen}
    seen = seen.intersection(views)
    pairs = pairs[pairs.image_id.isin(lookup)].copy()
    # This specifically adjudicated image is reference evidence, never a new review case.
    pairs = pairs[pairs.code != 'uNb9QFRL6hY-21'].copy()
    pairs['previous_development_image'] = pairs.image_id.isin(seen)
    pairs['threshold_gap'] = abs(pairs.fixed_max - 25.6)
    rules = [
        ('just_below', (pairs.fixed_max <= 25.6) & (pairs.fixed_max >= 24), 2, 'threshold_gap', True),
        ('just_above', (pairs.fixed_max > 25.6) & (pairs.fixed_max <= 27.2), 2, 'threshold_gap', True),
        ('complete_near_split', (pairs.fixed_max <= 25.6) & ~pairs.complete_same, 1, 'fixed_max', True),
        ('representative_far_join', (pairs.fixed_max > 25.6) & pairs.representative_same, 1, 'fixed_max', False),
        ('different_count_partial', ~pairs.same_count & (pairs.partial_matching_fraction >= .75), 1, 'partial_matching_fraction', False),
        ('free_correspondence_flip', (pairs.fixed_max > 25.6) & (pairs.free_max <= 25.6), 1, 'fixed_max', False),
    ]
    cases, chosen = [], set()
    for reason, mask, count, sort, ascending in rules:
        candidates = pairs[mask & ~pairs.image_id.isin(chosen)].sort_values(
            ['previous_development_image', sort, 'code', 'a_id', 'b_id'], ascending=[True, ascending, True, True, True])
        for _, row in candidates.drop_duplicates('image_id').head(count).iterrows():
            item = c.clean(row.to_dict())
            item.update(case_number=len(cases) + 1, selection_reason=reason,
                        selection_order=f'not previous development, {sort} {"ascending" if ascending else "descending"}, code, ids',
                        candidate_pair_count=len(candidates), prior_user_decisions_overridden=False)
            view = views[item['image_id']]
            item['partitions_recomputed'] = {}
            ia, ib = [view['ids'].index(item[k]) for k in ['a_id', 'b_id']]
            for method in ['complete', 'representative']:
                lab, centers = c.part(view['d'], view['ids'], method, 25.6)
                assert bool(lab[ia] == lab[ib]) == item[method + '_same']
                ga, gb = np.flatnonzero(lab == lab[ia]), np.flatnonzero(lab == lab[ib])
                cross = view['d'][np.ix_(ga, gb)]
                wa, wb = np.unravel_index(cross.argmax(), cross.shape)
                item['partitions_recomputed'][method] = dict(
                    labels_by_id=dict(zip(view['ids'], map(int, lab))),
                    centers=centers,
                    between_selected_clusters_max=float(cross.max()),
                    between_selected_clusters_max_ids=[view['ids'][ga[wa]], view['ids'][gb[wb]]],
                    member_distances_to_selected=[dict(id=cid, worker=view['workers'][j],
                        to_a=float(view['d'][ia, j]), to_b=float(view['d'][ib, j]))
                        for j, cid in enumerate(view['ids'])])
            rows = {r['canonical_annotation_id']: r for r in view['rows']}
            item['annotations'] = []
            for key in ['a_id', 'b_id']:
                rec = records[item[key]]
                row = rows[item[key]]
                # The frozen view contains two explicit historical/new provenance schemas.
                identity = (dict(annotation=row['raw_annotation_id'], project=row['project_id'],
                    task=row['runtime_task_id'], source=row['raw_export_path'])
                    if 'raw_annotation_id' in row else row['provenance'])
                item['annotations'].append(dict(canonical_id=item[key], worker=row['worker_id'],
                    raw_annotation_id=identity['annotation'], project_id=identity['project'],
                    runtime_task_id=identity['task'], raw_export_path=identity['source'],
                    points_1024x512=rec['p'].tolist(), pairs_effective_1based=(rec['links'] + 1).tolist(),
                    imputed_point=row['imputed_point']))
            if item['same_count']:
                assert np.isclose(view['d'][ia, ib], item['fixed_max'], atol=1e-9)
                item['pair_compatible_at_px'] = {str(t): item['fixed_max'] <= t for t in [25.5, 25.6, 25.7]}
            cases.append(item)
            chosen.add(item['image_id'])
    assert len(cases) == len(chosen) == 8
    assert not any(a['imputed_point'] for x in cases for a in x['annotations'])
    OUT.mkdir(exist_ok=True, parents=True)
    (OUT / 'cases.json').write_text(json.dumps(dict(threshold_px=25.6, image_space=[1024, 512],
        panel_note='Points and verified within-answer vertical pairs only; no inferred wall adjacency. Labels use effective source point indices.',
        development_evidence_paths=[str(p.relative_to(REPO)) for p in evidence_paths],
        development_image_count=len(seen), cases=cases), ensure_ascii=False, indent=2) + '\n', encoding='utf8')
    font = ImageFont.truetype('C:/Windows/Fonts/arial.ttf', 17)
    for item in cases:
        raw = (FOUNDATION / lookup[item['image_id']]['history_script']).read_text(encoding='utf8')
        encoded = re.search(r'\{const image="data:image/[^;]+;base64,([^"]+)"', raw).group(1)
        bg = Image.open(io.BytesIO(base64.b64decode(encoded))).convert('RGB').resize((1024, 512))
        canvas = Image.new('RGB', (1024, 1540), 'white')
        painted = []
        for side, a in enumerate(item['annotations']):
            color = '#ff5030' if side == 0 else '#00c7ff'
            im = bg.copy()
            d = ImageDraw.Draw(im)
            points = np.asarray(a['points_1024x512'])
            for pair_index, indices in enumerate(a['pairs_effective_1based'], 1):
                p, q = points[np.asarray(indices) - 1]
                if abs(p[0] - q[0]) < 512:
                    d.line([tuple(p), tuple(q)], fill=color, width=1)
                for role, point_index in zip(['T', 'B'], indices):
                    x, y = points[point_index - 1]
                    d.ellipse((x - 4, y - 4, x + 4, y + 4), fill=color, outline='black', width=1)
                    d.text((max(0, min(x + 5, 912)), max(0, y - 20)), f'{role}{pair_index}/p{point_index}',
                           fill=color, font=font, stroke_width=1, stroke_fill='black')
            painted.append(im)
            canvas.paste(im, (0, side * 560 + 48))
            d = ImageDraw.Draw(canvas)
            d.text((8, side * 560 + 5), f"{item['case_number']}. {item['code']} {item['selection_reason']} | {a['worker']} ann={a['raw_annotation_id']}", fill='black', font=font)
            d.text((8, side * 560 + 27), f"fixed={item['fixed_max']} | complete_same={item['complete_same']} | representative_same={item['representative_same']}", fill='black', font=font)
        # Repeated x tiles make the zoom seam-safe; crop centers on the fixed bottleneck.
        if item['same_count']:
            a = item['annotations'][0]
            center = a['points_1024x512'][int(item['bottleneck_a_raw_point']) - 1]
        else:
            a, b = item['annotations']
            p, q = np.asarray(a['points_1024x512']), np.asarray(b['points_1024x512'])
            dx = abs((p[:, None, 0] - q[None, :, 0] + 512) % 1024 - 512)
            dy = abs(p[:, None, 1] - q[None, :, 1])
            center = p[np.hypot(dx, dy).min(1).argmax()]
        x, y = map(int, center)
        y0 = max(0, min(y - 100, 312))
        for side, im in enumerate(painted):
            tiled = Image.new('RGB', (3072, 512))
            for j in range(3):
                tiled.paste(im, (j * 1024, 0))
            zoom = tiled.crop((x + 1024 - 128, y0, x + 1024 + 128, y0 + 200)).resize((512, 400))
            canvas.paste(zoom, (side * 512, 1140))
        d = ImageDraw.Draw(canvas)
        d.text((8, 1120), '2x local zoom, identical crop on both answers; full panels above establish scope.', fill='black', font=font)
        canvas.save(OUT / f'tmp_{item["case_number"]:02}_{item["code"]}.png')
    print(json.dumps([dict(case=x['case_number'], code=x['code'], reason=x['selection_reason'], a=x['a_worker'], b=x['b_worker'],
        fixed=x['fixed_max'], free=x['free_max'], previous=x['previous_development_image']) for x in cases], ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
