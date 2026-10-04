"""Recompute only affected diagnostics into a new directory; no GT or refitting."""
import argparse
import json
from pathlib import Path

import pandas as pd

from tools.thesis_main.analysis.layout_reliability_20261005.arc_consensus import Ring, W, TAU, equal_coeff
from tools.thesis_main.analysis.layout_reliability_20261005.continuous_metrics import (
    height_envelope, height_envelope_audit, partitions, witness_and_provenance,
)

ROOT = Path(__file__).resolve().parents[3]
ARCHIVE = ROOT/'research/layout_reliability_20261005/pro_original'


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+'\n', encoding='utf-8', newline='\n')


def check_interval_donors(candidate, records, witness):
    rings = [Ring(candidate)]+[Ring(r) for r in records]
    checked = 0
    for lo, hi, cs in partitions(rings):
        for row in witness['below_bound_intervals']:
            left, right = max(lo, row['x_lo']/W*TAU), min(hi, row['x_hi']/W*TAU)
            if right-left < 1e-10:
                continue
            for side, key in enumerate(('top_source_curves', 'bottom_source_curves')):
                donors = [r['id'] for r, c in zip(records, cs[1:]) if equal_coeff(cs[0][side], c[side])]
                assert donors == row[key], (left, right, key, donors, row[key])
            checked += 1
    return checked


def run(out):
    out.mkdir(parents=True, exist_ok=False)
    rows, changed, intervals_checked = [], [], 0
    max_source_violation = 0.
    max_aggregate_difference = 0.
    for image in ('2t7WUuJeko7-06', '7y3sRwLe3Va-04'):
        records = read(ARCHIVE/'inputs'/f'{image}.json')['records']
        envelope = height_envelope(records)
        for r in records:
            max_source_violation = max(max_source_violation, height_envelope_audit(r, envelope)['height_envelope_violation_h'])
        losses = pd.read_csv(ARCHIVE/'results/compression'/f'{image}_losses.csv')
        for old_path in sorted((ARCHIVE/'results/compression').glob(f'{image}_*_witnesses.json')):
            name = old_path.name.removesuffix('_witnesses.json')
            if name.endswith('_exact'):
                fused = read(ARCHIVE/'results/construction'/f'{image}_exact.json')
                candidate = fused['methods'][fused['bev_mv50_complete_method']]
                old_height = None
            else:
                candidate = read(old_path.with_name(name+'.json'))
                old_row = losses[(losses.policy == candidate['compression_policy']) & (losses.epsilon_px == candidate['epsilon_px'])]
                assert len(old_row) == 1
                old_height = float(old_row.iloc[0].height_envelope_violation_h)
            before = read(old_path)
            after = witness_and_provenance(candidate, records, len(records)//2+1)
            after = json.loads(json.dumps(after))  # JSON object keys are strings.
            assert before.keys() == after.keys()
            for key, value in before.items():
                if key == 'below_bound_intervals':
                    continue
                if isinstance(value, dict):
                    assert value.keys() == after[key].keys()
                    delta = max(abs(value[k]-after[key][k]) for k in value)
                elif isinstance(value, (int, float)):
                    delta = abs(value-after[key])
                else:
                    assert value == after[key]
                    continue
                max_aggregate_difference = max(max_aggregate_difference, delta)
                assert delta < 1e-10, (name, key, delta)
            intervals_checked += check_interval_donors(candidate, records, after)
            labels = lambda w: [(r['witness_records'], r['top_source_curves'], r['bottom_source_curves']) for r in w['below_bound_intervals']]
            if labels(before) != labels(after):
                changed.append(old_path.name)
            write(out/old_path.name, after)
            height = height_envelope_audit(candidate, envelope)
            if old_height is not None:
                assert abs(height['height_envelope_violation_h']-old_height) < 1e-12
            rows.append(dict(candidate=name, old_height_violation_h=old_height,
                old_failure_intervals=len(before['below_bound_intervals']),
                corrected_failure_intervals=len(after['below_bound_intervals']), **height))
    assert max_source_violation < 1e-10
    summary = dict(schema='layout_reliability_repair_audit_v1', source=str(ARCHIVE.relative_to(ROOT)),
        source_rosters=[3,24], witnesses_recomputed=len(rows), compression_states=sum(r['old_height_violation_h'] is not None for r in rows),
        changed_witness_files=changed, interval_donor_checks=intervals_checked,
        max_source_self_envelope_violation_h=max_source_violation,
        aggregate_witness_statistics_equal_within_atol=1e-10,
        max_aggregate_absolute_difference=max_aggregate_difference,
        compressed_height_findings_unchanged=True,
        candidate_geometry_recomputed=False, gt_read=False, source_files_changed=False,
        results=rows)
    write(out/'summary.json', summary)
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    result = run(parser.parse_args().out)
    print(json.dumps({k:v for k,v in result.items() if k!='results'}, ensure_ascii=True))
