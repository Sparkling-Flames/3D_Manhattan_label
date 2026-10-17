"""Post-generation footprint IoU diagnostics against frozen public references.

Reference access happens only after samples have been saved. Original dataset
references can have disputed scope; these scores do not establish worker ability.
"""
import argparse
import collections
from pathlib import Path

import numpy as np
from shapely.geometry import Polygon

from tools.thesis_main.analysis import simulate_annotators as s1


def footprint(points):
    if s1.geometry_status(points) != 'basic_checks_passed_not_certified':
        raise ValueError('geometry_unavailable')
    bottom = s1.rays(points[1::2])
    floor = -bottom[:, (0, 2)] / bottom[:, 1, None]
    return Polygon(floor)


def footprint_iou(points, reference):
    a, b = footprint(points), footprint(reference)
    return float(a.intersection(b).area / a.union(b).area)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-dir', type=Path, required=True)
    parser.add_argument('--references', type=Path, default=s1.INPUT / 'references.jsonl')
    args = parser.parse_args()
    refs = {}
    for r in s1.read_jsonl(args.references):
        if r['source_role'] == 'public_dataset_import_reference':
            if r['image_id'] in refs and refs[r['image_id']]['points_1024x512'] != r['points_1024x512']:
                raise ValueError('Conflicting original references: ' + r['image_id'])
            refs[r['image_id']] = r
    rows = []
    for sample in s1.read_jsonl(args.run_dir / 'simulations.jsonl'):
        ref = refs.get(sample['image_id'])
        status, iou, angle = 'missing_reference', None, None
        if ref is not None:
            if s1.parsed(sample['points']) and s1.parsed(ref['points_1024x512']):
                angle = s1.distance(sample['points'], ref['points_1024x512'])
            try:
                footprint(ref['points_1024x512'])
            except ValueError:
                status = 'invalid_reference_geometry'
            else:
                try:
                    iou = footprint_iou(sample['points'], ref['points_1024x512'])
                    status = 'available'
                except ValueError:
                    status, iou = 'invalid_generated_geometry_scored_zero', 0.
        rows.append(dict(simulation_id=sample['simulation_id'], image_id=sample['image_id'],
            archetype=sample['archetype'], condition=sample['condition'], iou=iou,
            reference_distance_deg=angle, status=status,
            reference_id=ref['reference_id'] if ref else None,
            reference_quality_status=ref.get('reference_quality_status') if ref else None))
    s1.write_csv(args.run_dir / 'reference_evaluation.csv', rows)
    groups = collections.defaultdict(list)
    for r in rows:
        groups[(r['archetype'], r['condition'])].append(r)
    summary = []
    for (archetype, condition), group in sorted(groups.items()):
        values = [r['iou'] for r in group if r['iou'] is not None]
        angles = [r['reference_distance_deg'] for r in group if r['reference_distance_deg'] is not None]
        summary.append(dict(archetype=archetype, condition=condition, total=len(group),
            scored=len(values), unavailable=len(group) - len(values),
            mean_iou=float(np.mean(values)) if values else None,
            angular_scored=len(angles), mean_reference_distance_deg=float(np.mean(angles)) if angles else None))
    s1.write_csv(args.run_dir / 'reference_archetype_summary.csv', summary)
    s1.dump(args.run_dir / 'reference_evaluation_protocol.json', dict(
        reference_sha256=s1.digest(args.references),
        source_code_sha256=s1.digest(Path(__file__)),
        policy='original public dataset references; retrospective diagnostics only; no references used in generation',
        caveat='scope disputes can affect IoU; archetype names are exploratory'))


if __name__ == '__main__':
    main()
