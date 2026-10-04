"""Fixed five-source, one-pair deletion pilot. No GT, matching, fitting or source edits."""
import argparse
import json
from pathlib import Path

import numpy as np
from shapely.geometry import LineString, Point, Polygon

from tools.thesis_main.analysis.layout_reliability_20261005.arc_consensus import (
    Ring, Unsupported, paired_wall_proxy,
)
from tools.thesis_main.analysis.research_round_20260929 import reconstruct

ROOT = Path(__file__).resolve().parents[3]
ARCHIVE = ROOT/'research/layout_reliability_20261005/pro_original'
SELECTION = {'rPc6DW4iMge-06': ['R00020','R01518','R01557'],
             'uNb9QFRL6hY-67': ['R02928','R02929']}


def delete_pair(record, index):
    n = len(record['points'])//2
    if n < 4 or not 0 <= index < n:
        raise ValueError('deletion_requires_at_least_four_pairs_and_valid_index')
    keep = [i for i in range(n) if i != index]
    out = dict(id=f"{record['id']}:delete:{index}", source_record_id=record['id'],
        points=[record['points'][2*i+j][:] for i in keep for j in (0,1)],
        ring_confirmed=False, order_status='generated_source_subsequence_unreviewed',
        evidence_kind='generated_hypothesis', voting_role='not_a_person_vote')
    for key, stride in [('source_pair_indices',1),('source_point_indices',2),('source_point_labels',2)]:
        out[key] = [record[key][stride*i+j] for i in keep for j in range(stride)]
    return out


def distance_to_segment(p, a, b):
    edge = b-a
    if np.dot(edge, edge) <= 1e-24:
        return float(np.linalg.norm(p-a))
    t = np.clip(np.dot(p-a, edge)/np.dot(edge, edge), 0, 1)
    return float(np.linalg.norm(p-(a+t*edge)))


def encoding_matches(candidate, roster):
    a = np.asarray(candidate['points']).reshape(-1,2,2)
    matches = []
    for r in roster:
        b = np.asarray(r['points']).reshape(-1,2,2)
        if a.shape == b.shape and any(np.allclose(a,np.roll(order,k,axis=0),atol=1e-9,rtol=0)
                for order in (b,b[::-1]) for k in range(len(b))):
            matches.append(r['id'])
    return matches


def enumerate_source(record, roster, heading_deg):
    top, bottom = paired_wall_proxy(record)
    floor = bottom[:,[0,2]]; n = len(floor); source_poly = Polygon(floor)
    observations = []
    for r in roster:
        t,b = paired_wall_proxy(r)
        observations.append((r['id'],np.stack([t,b],axis=1)))
    rows = []
    for index in [None]+list(range(n)):
        keep = list(range(n)) if index is None else [i for i in range(n) if i!=index]
        if index is None:
            candidate = {k:record[k] for k in ('id','points','source_pair_indices','source_point_indices','source_point_labels','ring_confirmed','order_status')}
        else:
            candidate = delete_pair(record,index)
        p = floor[keep]; poly = Polygon(p)
        valid = bool(poly.is_valid and poly.area > 1e-12)
        row = dict(id=f"{record['id']}:original" if index is None else candidate['id'],
            source_record=record['id'], source_worker=record['worker'], candidate=candidate,
            removed_pair_index=index, removed_source_pair_index=None if index is None else record['source_pair_indices'][index],
            pair_count=len(keep), polygon_valid=valid, camera_inside=bool(valid and poly.contains(Point(0,0))),
            floor_path_to_shortcut_max_h=0., top_proxy_path_to_shortcut_max_h=0.,
            new_connection=None, exact_endpoint_edge_donors=[],
            exact_observed_encoding_ids=encoding_matches(candidate,roster),
            support_interpretation='strict whole encoding and endpoint equality only; no inherited or semantic votes')
        if index is not None:
            prev,nxt = (index-1)%n,(index+1)%n
            row.update(floor_path_to_shortcut_max_h=distance_to_segment(bottom[index],bottom[prev],bottom[nxt]),
                top_proxy_path_to_shortcut_max_h=distance_to_segment(top[index],top[prev],top[nxt]),
                new_connection=dict(source_pair_indices=[record['source_pair_indices'][prev],record['source_pair_indices'][nxt]],
                    replaced_source_edges=[[record['source_pair_indices'][prev],record['source_pair_indices'][index]],
                                           [record['source_pair_indices'][index],record['source_pair_indices'][nxt]]]))
            bridge = LineString(floor[[prev,nxt]])
            # No buffer is used to invent support for nearby but different edges.
            row['bridge_not_on_source_boundary_h'] = float(bridge.difference(source_poly.boundary).length)
            endpoints = np.stack([top,bottom],axis=1)[[prev,nxt]]
            for rid, vertices in observations:
                if any(np.allclose(endpoints,vertices[[j,(j+1)%len(vertices)]],rtol=0,atol=1e-9)
                       or np.allclose(endpoints[::-1],vertices[[j,(j+1)%len(vertices)]],rtol=0,atol=1e-9)
                       for j in range(len(vertices))):
                    row['exact_endpoint_edge_donors'].append(rid)
        else:
            row['bridge_not_on_source_boundary_h'] = 0.
        if valid:
            edges = np.roll(p,-1,axis=0)-p; lengths = np.linalg.norm(edges,axis=1)
            residual = abs((np.arctan2(edges[:,1],edges[:,0])-np.radians(heading_deg)+np.pi/4)%(np.pi/2)-np.pi/4)
            row.update(added_area_h2=float(poly.difference(source_poly).area),
                lost_area_h2=float(source_poly.difference(poly).area),
                source_bev_iou=float(poly.intersection(source_poly).area/poly.union(source_poly).area),
                direction_residual_deg=float(np.degrees(np.average(residual,weights=lengths))))
        else:
            row.update(added_area_h2=None,lost_area_h2=None,source_bev_iou=None,direction_residual_deg=None)
        try:
            Ring(candidate)
            row['single_valued_status'] = 'ok'
        except Unsupported as exc:
            row['single_valued_status'] = str(exc)
        rows.append(row)
    return rows


def select_policies(rows, budgets=(.01,.05,.1)):
    eligible = [r for r in rows if r['polygon_valid'] and r['camera_inside']]
    def best_ties(items, first, second):
        if not items:
            return []
        low = min(r[first] for r in items)
        items = [r for r in items if abs(r[first]-low)<1e-10]
        low = min(r[second] for r in items)
        return [r['id'] for r in items if abs(r[second]-low)<1e-10]
    result = {'direction_then_size':best_ties(eligible,'direction_residual_deg','pair_count')}
    for budget in budgets:
        feasible = [r for r in eligible if max(r['floor_path_to_shortcut_max_h'],r['top_proxy_path_to_shortcut_max_h']) <= budget+1e-10]
        result[f'path_budget_{budget:g}h'] = best_ties(feasible,'pair_count','direction_residual_deg')
    result['detail_protection'] = dict(status='not_run_missing_local_evidence')
    return result


def run(out):
    out.mkdir(parents=True,exist_ok=False)
    sources, candidates, policies = [], [], {}
    for image, ids in SELECTION.items():
        roster = json.loads((ARCHIVE/'inputs'/f'{image}.json').read_text(encoding='utf-8'))['records']
        for rid in ids:
            record = next(r for r in roster if r['id']==rid)
            assert record['ring_confirmed']
            heading = reconstruct(record)['metrics']['heading_frame_deg']
            rows = enumerate_source(record,roster,heading)
            for r in rows:
                r['image'] = image
            sources.append(dict(image=image,id=rid,worker=record['worker'],pair_count=len(record['points'])//2,
                fixed_source_heading_deg=heading,selection='confirmed BEV-valid source outside single-valued arc domain; not an error label'))
            candidates.extend(rows);policies[rid] = select_policies(rows)
    result = dict(schema='local_structure_deletion_pilot_v1',sources=sources,candidates=candidates,policies=policies,
        gt_read=False,source_mutation=False,limitations=['one deletion per existing ring; no multi-source reconstruction',
        'local geometric candidates are not validated physical walls','strict encoding matches are not semantic support',
        'path budgets are mechanism controls, not calibrated tolerances','Manhattan applicability is not certified'])
    assert len(candidates)==56
    (out/'results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,required=True)
    result = run(parser.parse_args().out)
    print(json.dumps(dict(sources=len(result['sources']),candidates=len(result['candidates']),policies=result['policies'])))
