"""固定137图全员点对融合：公开探索参数，完整失败分母，GT仅事后评价。"""
from __future__ import annotations

from collections import Counter
import csv
import json
from pathlib import Path

import numpy as np
from shapely.geometry import Polygon

from .lee_tile_stage1_20261002 import ROOT, METHODS, write_json
from .global_pair_consensus_20261004 import build_global_pair_consensuses
from .erp_region_demo_20261003 import aggregate_records

SOURCE=ROOT/'analysis_results/lee_expanded_20261003'
OUT=ROOT/'analysis_results/global_pair_consensus_20261004'


def reference_metrics(candidate, references):
    """只对合法声明足迹评分，不修复几何；上边没有被此分数验证。"""
    points=candidate.get('footprint')
    if points is None or len(points)<3:
        return {}
    polygon=Polygon(points)
    if not polygon.is_valid or polygon.area<=0:
        return {}
    scores={}
    for ref in references:
        if ref['footprint'] is None:
            continue
        gt=Polygon(ref['footprint'])
        if not gt.is_valid or gt.area<=0:
            raise ValueError('invalid_fixed_reference:'+ref['version'])
        iou=polygon.intersection(gt).area/polygon.union(gt).area
        delta=polygon.centroid.distance(gt.centroid)
        scores[ref['version']]=dict(iou=iou,centroid_h=delta,
            centroid_normalized=delta/np.sqrt(gt.area))
    return scores


def summarize_rows(rows):
    summary=[]
    for threshold in (2.5,5.,10.):
        for method in METHODS:
            selected=[r for r in rows if r['threshold_deg']==threshold and r['method']==method]
            scored=[r for r in selected if 'original' in r['reference_metrics']]
            paired=[r for r in selected if 'point_minus_lee_iou' in r]
            complete=[r for r in paired if r['status']!='unavailable']
            summary.append(dict(threshold_deg=threshold,method=method,attempted_images=len(selected),
                status_counts=dict(Counter(r['status'] for r in selected)),scored_original_images=len(scored),
                original_iou_mean=float(np.mean([r['reference_metrics']['original']['iou'] for r in scored])) if scored else None,
                paired_lee_images=len(paired),
                paired_point_minus_lee_iou_mean=float(np.mean([r['point_minus_lee_iou'] for r in paired])) if paired else None,
                complete_candidate_paired_n=len(complete),
                complete_candidate_point_minus_lee_iou_mean=float(np.mean([r['point_minus_lee_iou'] for r in complete])) if complete else None,
                note='Conditional description on matching computable images, not failure-adjusted method superiority. Floor-only scores may exist when top/layout is unavailable; complete_candidate fields exclude those cases.'))
    return summary


def run():
    data=json.loads((SOURCE/'source_input.json').read_text(encoding='utf-8'))
    if data['schema']!='lee_tile_stage1_input_v1':
        raise ValueError('input_schema_drift')
    images=data['images']
    old=json.loads((SOURCE/'input.json').read_text(encoding='utf-8'))
    comparable={r['code'] for r in old['images']}
    rosters={r['image']:r for r in json.loads((SOURCE/'rosters.json').read_text(encoding='utf-8'))}
    with (SOURCE/'image_curves.csv').open(encoding='utf-8-sig',newline='') as f:
        lee={(r['image'],r['method']):float(r['iou_mean']) for r in csv.DictReader(f)
             if r['version']=='original' and int(r['k'])==int(r['n'])}
    OUT.mkdir(parents=True,exist_ok=True)
    if (OUT/'primary_results.json').exists():
        raise ValueError('do_not_overwrite_completed_study')
    write_json(OUT/'design.json',dict(schema='global_pair_study_v1',status='started',
        input='analysis_results/lee_expanded_20261003/source_input.json',
        image_n=len(images),existing_lee_comparable_n=len(comparable),
        thresholds_deg=[2.5,5.,10.],default_threshold_deg=5.,methods=list(METHODS),
        primary='Each image uses all current independent records; no whole-annotation cluster selection.',
        geometry='New ring is an explicitly declared shared-x ordered exploratory estimate, not inherited confirmation. Source rings are unchanged; adjacency evidence reported separately.',
        scope='Full-pool prototype and sensitivity, not headcount curves, new quality total score, best-method selection or calibrated threshold.',
        sampling='No random subset sampling. All full-pool estimates are deterministic for the declared identity tie rule.',
        reference='GT only enters reference_metrics after consensus outputs exist. BEV IoU/centroid evaluate floor extent only.',
        failure='Any unavailable candidate stays in the attempted denominator. Previous Lee whole-pool failure remains identifiable.'))
    primary=[]; rows=[]; erp_rows=[]
    for image in images:
        # 与既有冻结Manual/main_candidate池完全相同；不依赖本轮方法成败筛人。
        records=sorted([r for r in image['annotations'] if r['independent'] and r['consensus_eligible']
            and r['condition']=='manual' and r['main_consensus_gate']['status']=='main_candidate'],key=lambda r:r['id'])
        if image['code'] in rosters and [r['id'] for r in records]!=rosters[image['code']]['record_ids']:
            raise ValueError('roster_identity_drift:'+image['code'])
        item=dict(image=image['code'],n=len(records),input_annotations=len(image['annotations']),
                  outside_fixed_stratum=len(image['annotations'])-len(records),building=image['building'],
                  previous_lee_comparable=image['code'] in comparable,methods={})
        for threshold in (2.5,5.,10.):
            results=build_global_pair_consensuses(records,threshold_deg=threshold)
            for method,result in results.items():
                candidate=result['candidate']
                scores=reference_metrics(candidate,image['references'])
                row=dict(image=image['code'],n=len(records),building=image['building'],
                    threshold_deg=threshold,method=method,status=candidate['status'],reason=candidate.get('reason'),
                    pair_count=len(candidate['points'])//2 if candidate.get('points') else 0,
                    identity_group_n=len(result['identity_groups']),
                    previous_lee_comparable=image['code'] in comparable,
                    reference_metrics=scores,ring_diagnostics=result['ring_diagnostics'],
                    points=candidate.get('points'),footprint=candidate.get('footprint'))
                if 'original' in scores and (image['code'],method) in lee:
                    row['point_minus_lee_iou']=scores['original']['iou']-lee[image['code'],method]
                rows.append(row)
                if threshold==5.:
                    item['methods'][method]=dict(result,reference_metrics=scores)
        erp=aggregate_records(records,samples=512)
        erp_rows.append(dict(image=image['code'],n=len(records),status=erp['status'],unsupported=erp['unsupported']))
        primary.append(item)
        print(f"{image['code']}: N={len(records)}, point={[v['candidate']['status'] for v in item['methods'].values()]}, ERP={erp['status']}",flush=True)
    summary=summarize_rows(rows)
    write_json(OUT/'primary_results.json',dict(schema='global_pair_primary_v1',threshold_deg=5.,images=primary))
    write_json(OUT/'sensitivity.json',rows)
    write_json(OUT/'erp_coverage.json',erp_rows)
    write_json(OUT/'summary.json',dict(results=summary,erp_status_counts=dict(Counter(r['status'] for r in erp_rows))))
    write_json(OUT/'field_contract.json',dict(schema='global_pair_study_v1',
        primary_results='137 full-pool images, candidate/support/source/ring diagnostics for both point voting rules at predefined 5 degrees.',
        sensitivity='All images x 3 predefined thresholds x 2 rules; every status retained; candidate points, footprint, ring diagnostics and post-hoc references. Nondefault identity assignments are reproduced from fixed inputs by the script.',
        metrics='BEV floor IoU, centroid distance in camera-height units and normalized by sqrt(reference area); not complete top/layout quality.',
        pairing='point_minus_lee_iou only on matching image/rule/full-pool original reference, with explicit computable denominator.',
        erp='Whole-group applicable status; one unsupported member blocks the group; no thinning.',
        shared_x='Only new consensus ring uses this declared baseline. No source points, pairs, rings, qualification or GT altered.'))
    plan=json.loads((OUT/'design.json').read_text(encoding='utf-8'));plan['status']='completed';write_json(OUT/'design.json',plan)
    return summary


if __name__=='__main__':
    run()
