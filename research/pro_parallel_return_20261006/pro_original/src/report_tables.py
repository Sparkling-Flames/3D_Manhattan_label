"""Reporting extracts only: no new geometry, person selection, or replay."""
from pathlib import Path
import json
import pandas as pd
from analyze import SPECIAL, DETAIL


def write_tables(source, result_dir):
    source, rd = Path(source), Path(result_dir)
    summaries = {r['image']: r for r in json.loads((rd/'case_summary.json').read_text())}
    endpoints = pd.read_csv(rd/'endpoint_metrics.csv')
    local = pd.read_csv(rd/'local_diagnostics.csv')
    a, b = [], []
    for e in endpoints.to_dict('records'):
        s = summaries[e['image']]
        if e['image'] in SPECIAL:
            a.append(dict(image=e['image'], n=e['n'], condition='manual', room=s['room'],
                method=e['method'], reference=e['version'], R=s['raw_R'],
                pairwise_iou_median=s['pairwise_iou_median'],
                pairwise_boundary_mean_h=s['pairwise_boundary_mean_h'], iou=e['iou'],
                omission_percent=100*e['omission_ref'], extension_percent=100*e['extension_ref'],
                quality_eligibility='unchanged_special_scene_not_primary_quality'))
        else:
            q = local[(local.image==e['image']) & (local.object==e['method'])].iloc[0]
            b.append(dict(image=e['image'], n=e['n'], method=e['method'], reference=e['version'],
                iou=e['iou'], mean_individual_D=e['individual_mean_error_ref'], all_D=e['error_ref'],
                omission_percent=100*e['omission_ref'], extension_percent=100*e['extension_ref'],
                diagnostic_source=q.source_record, local_patch_h2=q.patch_area_h2,
                local_patch_output_coverage=q.patch_covered_fraction, local_path_mean_h=q.path_mean_h))
    pd.DataFrame(a).to_csv(rd/'table_A_special.csv', index=False)
    pd.DataFrame(b).to_csv(rd/'table_B_detail.csv', index=False)
    curves = pd.read_csv(source/'uniform_curves.csv')
    curves[curves.image.isin(DETAIL) & curves.k.isin([1,8,24])].to_csv(
        rd/'reused_B_counts_1_8_24.csv', index=False)
