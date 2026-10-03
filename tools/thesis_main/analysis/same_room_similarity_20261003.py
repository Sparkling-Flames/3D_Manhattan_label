"""在各自相机坐标内计量，比较同房视角的共同人员画像；不跨视角叠加区域。"""
from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path

import numpy as np
from scipy.stats import rankdata
from shapely.geometry import Polygon

from tools.thesis_main.analysis.lee_tile_stage1_20261002 import region_iou, write_csv, write_json

ROOT = Path(__file__).resolve().parents[3]
EXPANDED = ROOT / 'analysis_results/lee_expanded_20261003'
REGISTRY = ROOT / 'analysis_results/research_input_20260929/final_review/同房分类_原始完整记录.json'
OUT = ROOT / 'analysis_results/same_room_similarity_20261003'


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def relation_index(candidates):
    """直接记录的图对；不以传递闭包构造新的确认关系。"""
    result = {}
    for c in candidates:
        for pair in combinations(sorted(c['image_ids']), 2):
            row = result.setdefault(pair, dict(tier='candidate_unconfirmed', candidates=[], evidence=[]))
            row['candidates'].append(c['candidate_id'])
            row['evidence'].append({k: c[k] for k in ('candidate_id', 'physical_same_supported',
                'comparable_for_prediction', 'oos_pending', 'review_state')})
            confirmed = (c['physical_same_supported'] and c['comparable_for_prediction']
                         and not c['oos_pending'] and c['review_state'] == 'explicit_confirmed')
            if confirmed:
                row['tier'] = 'confirmed_comparable'
            elif c['physical_same_supported'] and row['tier'] != 'confirmed_comparable':
                row['tier'] = 'supported_other'
    return result


def correlation(a, b):
    if len(a) < 2 or np.ptp(a) == 0 or np.ptp(b) == 0:
        return None
    return float(np.corrcoef(rankdata(a), rankdata(b))[0, 1])


def compare_profiles(a, b):
    people = sorted(a.keys() & b.keys())
    x, y = [np.array([d[w] for w in people]) for d in (a, b)]
    return dict(n_common=len(people), common_workers=people,
                worker_iou_spearman=correlation(x, y),
                common_mean_iou_a=float(np.mean(x)) if len(x) else None,
                common_mean_iou_b=float(np.mean(y)) if len(y) else None,
                common_mean_iou_gap=float(abs(np.mean(x) - np.mean(y))) if len(x) else None)


def mean(rows, key):
    values = [r[key] for r in rows if r[key] is not None]
    return float(np.mean(values)) if values else None


def main(out=OUT):
    out = Path(out)
    if out.exists():
        raise FileExistsError(out)
    out.mkdir(parents=True)
    registry = read(REGISTRY)
    relations = relation_index(registry['candidates'])
    images = {i['code']: i for i in read(EXPANDED / 'input.json')['images']}
    rosters = read(EXPANDED / 'rosters.json')
    profiles, pair_distances, singles = {}, {}, []
    # Fixed roster comes from the completed A-line; no eligibility is recomputed here.
    for roster in rosters:
        code = roster['image']
        image = images[code]
        records = {r['id']: r for r in image['annotations']}
        polygons = {records[r]['worker']: Polygon(records[r]['footprint']) for r in roster['record_ids']}
        assert len(polygons) == len(roster['record_ids'])
        gt = Polygon(next(r['footprint'] for r in image['references'] if r['version'] == 'original'))
        assert gt.is_valid and gt.area > 0
        assert all(p.is_valid and p.area > 0 for p in polygons.values())
        profiles[code] = {w: region_iou(p, gt) for w, p in polygons.items()}
        pair_distances[code] = {tuple(sorted((a, b))): 1 - region_iou(polygons[a], polygons[b])
                               for a, b in combinations(polygons, 2)}
        for w, value in profiles[code].items():
            singles.append(dict(image=code, worker=w, original_gt_iou=value))
    pairs = []
    for a, b in combinations(sorted(profiles), 2):
        if images[a]['building'] != images[b]['building']:
            continue
        relation = relations.get(tuple(sorted((images[a]['image_id'], images[b]['image_id']))),
                                 dict(tier='same_building_no_room_evidence', candidates=[]))
        row = dict(image_a=a, image_b=b, building=images[a]['building'],
                   relation=relation['tier'], candidate_ids=';'.join(relation['candidates']),
                   n_a=len(profiles[a]), n_b=len(profiles[b]), **compare_profiles(profiles[a], profiles[b]))
        workers = row.pop('common_workers')
        row['common_workers'] = ';'.join(workers)
        keys = list(combinations(workers, 2))
        da, db = [np.array([pair_distances[i][k] for k in keys]) for i in (a, b)]
        row.update(pair_disagreement_spearman=correlation(da, db),
                   common_pair_disagreement_a=float(np.mean(da)) if len(da) else None,
                   common_pair_disagreement_b=float(np.mean(db)) if len(db) else None,
                   common_pair_disagreement_gap=float(abs(np.mean(da) - np.mean(db))) if len(da) else None)
        pairs.append(row)
    metrics = ('worker_iou_spearman', 'common_mean_iou_gap',
               'pair_disagreement_spearman', 'common_pair_disagreement_gap')
    by_building = []
    for minimum in (4, 8):
        for building in sorted({r['building'] for r in pairs}):
            for tier in sorted({r['relation'] for r in pairs}):
                subset = [r for r in pairs if r['building'] == building and r['relation'] == tier
                          and r['n_common'] >= minimum]
                if subset:
                    by_building.append(dict(min_common=minimum, building=building, relation=tier,
                        pairs=len(subset), images=len({r[k] for r in subset for k in ('image_a', 'image_b')}),
                        **{k: mean(subset, k) for k in metrics}))
    comparisons = []
    for minimum in (4, 8):
        for building in sorted({r['building'] for r in pairs}):
            confirmed = [r for r in pairs if r['building'] == building
                         and r['relation'] == 'confirmed_comparable' and r['n_common'] >= minimum]
            if not confirmed:
                continue
            anchors = {r[k] for r in confirmed for k in ('image_a', 'image_b')}
            controls = [r for r in pairs if r['building'] == building
                        and r['relation'] == 'same_building_no_room_evidence' and r['n_common'] >= minimum
                        and (r['image_a'] in anchors or r['image_b'] in anchors)]
            if not controls:
                continue
            comparisons.append(dict(min_common=minimum, building=building,
                confirmed_pairs=len(confirmed), control_pairs=len(controls),
                **{k + '_confirmed': mean(confirmed, k) for k in metrics},
                **{k + '_control': mean(controls, k) for k in metrics}))
    summary = dict(
        status='descriptive_completed', input_images=len(images), completed_rosters=len(rosters),
        individual_answers=len(singles), registry_candidates=len(registry['candidates']),
        registry_supported_candidates=sum(c['physical_same_supported'] for c in registry['candidates']),
        registry_confirmed_comparable_candidates=sum(c['physical_same_supported'] and
            c['comparable_for_prediction'] and not c['oos_pending'] and
            c['review_state'] == 'explicit_confirmed' for c in registry['candidates']),
        same_building_pairs=len(pairs), all_pair_relations=dict(Counter(r['relation'] for r in pairs)),
        panels=[], matched_buildings=[])
    for minimum in (4, 8):
        for tier in sorted({r['relation'] for r in pairs}):
            subset = [r for r in pairs if r['relation'] == tier and r['n_common'] >= minimum]
            if not subset:
                continue
            builds = [r for r in by_building if r['min_common'] == minimum and r['relation'] == tier]
            summary['panels'].append(dict(min_common=minimum, relation=tier, pairs=len(subset),
                images=len({r[k] for r in subset for k in ('image_a', 'image_b')}), buildings=len(builds),
                positive_worker_correlations=sum(r['worker_iou_spearman'] is not None and
                    r['worker_iou_spearman'] > 0 for r in subset),
                **{k + '_pair_equal': mean(subset, k) for k in metrics},
                **{k + '_building_equal': mean(builds, k) for k in metrics}))
        builds = [r for r in comparisons if r['min_common'] == minimum]
        summary['matched_buildings'].append(dict(min_common=minimum, buildings=len(builds),
            **{k + '_' + group: mean(builds, k + '_' + group)
               for k in metrics for group in ('confirmed', 'control')}))
    write_csv(out / 'individual_iou.csv', singles)
    write_csv(out / 'image_pairs.csv', pairs)
    write_csv(out / 'by_building.csv', by_building)
    write_csv(out / 'same_building_controls.csv', comparisons)
    write_json(out / 'summary.json', summary)
    write_json(out / 'relation_evidence.json', [dict(image_a=a, image_b=b, **r)
        for (a, b), r in relations.items() if a in {i['image_id'] for i in images.values()}
        and b in {i['image_id'] for i in images.values()}])
    present = {i['image_id'] for i in images.values()}
    write_json(out / 'relation_overlap_audit.json', [dict(image_a=a, image_b=b,
        both_in_current_panel=a in present and b in present, **r)
        for (a, b), r in relations.items() if len(r['evidence']) > 1])
    write_json(out / 'field_contract.json', dict(
        schema='same_room_similarity_descriptive_v1', sources=[str(REGISTRY.relative_to(ROOT)),
            str((EXPANDED / 'input.json').relative_to(ROOT)), str((EXPANDED / 'rosters.json').relative_to(ROOT))],
        coordinate_rule='Polygons compared only within the same image and camera frame.',
        relation_rule='Direct recorded pairs only; no transitive closure; no evidence is not confirmed different room.',
        population='Existing completed A-line Manual/main_candidate rosters, no merged votes or eligibility changes.',
        metrics=dict(worker_iou_spearman='Spearman of original-GT IoU for identical common workers.',
            common_mean_iou_gap='Absolute difference of common-worker mean IoU across the two images.',
            pair_disagreement_spearman='Spearman of within-image 1-IoU for the same unordered worker pairs.',
            common_pair_disagreement_gap='Absolute difference of mean within-image pair 1-IoU.'),
        missing='Empty correlation denotes constant vector or fewer than two values; n_common preserved.',
        aggregation='Pair equal and building equal shown separately; pairs share images/workers and are not independent.',
        bounds='Exact descriptive geometry, no new significance/CI or generalization claims; no new consensus curves.'))
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, default=OUT, help='New output directory; existing paths are rejected.')
    main(parser.parse_args().out)
