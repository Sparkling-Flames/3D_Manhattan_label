"""重核既有259图结构计算；特殊场景评分与GT争议另列，不改源数据。"""
import csv
import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np
from shapely.geometry import LineString

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from tools.thesis_main.data_prep.consolidate_research_input import load_current_bundle
from tools.thesis_main.analysis.gt_order_visibility_20261009 import audit_object
from tools.thesis_main.analysis.difficulty_structure_20261009 import classify_structure

OUT = Path(__file__).parent
SOURCE = OUT.parent / 'structure_classification/images.csv'
FLAGS = ('scope_explicit_tag', 'scope_existing_ledger', 'scope_comment_candidate',
         'gt_substantive_error_mark', 'gt_detail_omission_mark', 'gt_uncertainty_explicit_tag')


def main():
    before = SOURCE.read_bytes()
    rows = list(csv.DictReader(before.decode('utf-8-sig').splitlines()))
    objects = {o['object_id']: o for o in load_current_bundle()['data']['objects']}
    feedback = json.loads((OUT / 'user_feedback_20261009.json').read_text(encoding='utf-8'))
    decisions = {r['image']: r for r in feedback['image_decisions']}
    output, mismatches, independent_mismatches = [], [], []
    for row in rows:
        g = audit_object(objects[row['gt_object_id']], row['population'])
        label, reason = classify_structure(g['pair_count'], g['geometry_status'], g['hidden_count'])
        same = (g['pair_count'] == int(row['selected_gt_pair_count'])
                and g['hidden_count'] == int(row['hidden_pair_count'])
                and label == row['raw_structure_class'])
        if not same:
            mismatches.append(row['image'])
        # 独立几何库交叉检查横穿；不重新排序或修复GT。
        xy = g['floor_xy']
        hidden = []
        if g['geometry_status'] == 'valid_camera_inside':
            for i, target in enumerate(xy):
                ray = LineString([(0, 0), target])
                if any(ray.crosses(LineString([a, xy[(j+1) % len(xy)]]))
                       for j, a in enumerate(xy) if i not in (j, (j+1) % len(xy))):
                    hidden.append(i+1)
            if hidden != g['hidden_vertices_1based']:
                independent_mismatches.append(row['image'])
        special = row['scene_stratum'] not in ('clear', 'unflagged')
        track = row['scene_stratum'] if special else 'ordinary_confirmed' if row['scene_stratum'] == 'clear' else 'ordinary_unflagged'
        status = 'separate_assessment_pending' if special else 'provisional_structure_proxy'
        if row['applicability_status'] != 'applicable':
            status = 'existing_hold_or_inapplicable'
        if row['image'] in decisions:
            status = decisions[row['image']]['difficulty_status']
        output.append(dict(image=row['image'], image_id=row['image_id'],
            gt_object_id=row['gt_object_id'], N=g['pair_count'], H=g['hidden_count'],
            raw_structure_class=label, existing_coarse_class=row['coarse_class'],
            numerical_recheck='match' if same else 'mismatch',
            independent_hidden_pairs=json.dumps(hidden), assessment_track=track,
            difficulty_status=status, separate_difficulty_score='',
            oos_subtype=row['oos_subtype'], doorway_status=row['doorway_status'],
            reference_issue='user_reported_gt_issue_pending' if row['image'] in decisions else 'not_newly_adjudicated',
            evidence_flags=';'.join(k for k in FLAGS if row[k] == 'True')))
    assert len(output) == len({r['image_id'] for r in output}) == 259
    assert not mismatches and not independent_mismatches, (mismatches, independent_mismatches)
    x8 = next(r for r in output if r['image'] == 'x8F5xyUWy9e-01')
    assert x8['difficulty_status'] == 'pending_reference_review' and x8['raw_structure_class'] == '困难'
    assert all(not r['separate_difficulty_score'] for r in output)
    assert SOURCE.read_bytes() == before
    with (OUT / 'score_recheck.csv').open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(output[0])); writer.writeheader(); writer.writerows(output)
    p = np.asarray(audit_object(objects[x8['gt_object_id']], 'research_annotation_image')['floor_xy'])
    a, b = np.roll(p, 1, axis=0)-p, np.roll(p, -1, axis=0)-p
    angles = np.degrees(np.arccos(np.clip((a*b).sum(axis=1) / np.linalg.norm(a, axis=1) / np.linalg.norm(b, axis=1), -1, 1)))
    summary = dict(images=259, numerical_mismatches=mismatches,
        independent_ray_mismatches=independent_mismatches,
        assessment_tracks=dict(Counter(r['assessment_track'] for r in output)),
        difficulty_status=dict(Counter(r['difficulty_status'] for r in output)),
        evidence_flag_counts={k: sum(r[k]=='True' for r in rows) for k in FLAGS},
        x8_01_smaller_edge_angles_degrees=angles.tolist(),
        x8_01_max_deviation_from_90_degrees=float(abs(angles-90).max()),
        boundary='Computational reproducibility is not GT correctness or human difficulty validation; flags are review leads, not automatic invalidity.')
    (OUT / 'score_recheck.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == '__main__':
    main()
