"""Allowlisted public projection of the integrated review; never changes eligibility."""
import argparse
from collections import Counter
import json
from pathlib import Path

from tools.thesis_main.analysis.research_round_20260929 import validate_panel, write_json


def project(source):
    objects=source['objects']
    workers={w:f'P{i:03d}' for i,w in enumerate(sorted({o['worker_id'] for o in objects if o['object_kind']=='annotation'}),1)}
    ids={o['object_id']:f'R{i:05d}' for i,o in enumerate(sorted(objects,key=lambda o:o['object_id']),1)}
    images=[]
    for im in source['images']:
        row=dict(code=im['image_code'],building=im['building_id'],room=im['room_id'],
                 population=im['population'],scene={k:(im[k] if im['annotations'] else None) for k in ('oos_status','doorway_status','coverage')},
                 annotations=[],references=[])
        for o in objects:
            if o['image_code']!=im['image_code']:continue
            r=dict(id=ids[o['object_id']],points=o['points_1024x512'],order_status=o['order_status'],
                   geometry_status=o['geometry']['status'],geometry_issues=o['geometry']['issues'],
                   source_point_indices=o['ordered_source_point_indices'],
                   source_point_labels=o['ordered_source_point_labels'],
                   preprocessing_status=o['preprocessing_status'],ring_confirmed=o['ring_confirmed'])
            if o['object_kind']=='annotation':
                gate=o['main_consensus_gate']['status']
                r.update(worker=workers[o['worker_id']],condition=o['condition'],cleaning=o['cleaning_disposition'],
                         independent=o['independent_vote_eligible'],independence_reasons=o['independent_vote_reasons'],
                         consensus_eligible=gate in ('main_candidate','oos_doorway_exploratory','stable_nonorthogonal_separate'),
                         quality_candidate=o['main_quality_gate']['status']=='candidate_pending_geometry',
                         main_quality_gate=o['main_quality_gate'],main_consensus_gate=o['main_consensus_gate'],
                         scene_category=o['scene_category'],borrowed_points=bool(o['borrowed_point_provenance']))
                row['annotations'].append(r)
            else:
                r['version']={'gt_original':'original','gt_manual_revision':'manual_revision'}[o['object_kind']]
                row['references'].append(r)
        images.append(row)
    panel=dict(schema='layout_research_panel_v1',source_manifest=dict(
        source_entry='analysis_results/research_input_20260929/preprocessed_source.json',
        source_schema=source['schema'],contract_version=source['contract_version'],
        coordinate_frame=source['coordinate_frame'],preprocessing=source['preprocessing'],
        object_counts=dict(Counter(o['object_kind'] for o in objects)),
        consensus_inclusion='Upstream main_candidate, oos_doorway_exploratory and stable_nonorthogonal_separate; report separately',
        privacy='New participant and record aliases; no raw IDs, comments, photographs, task URLs or private mappings'),images=images)
    validate_panel(panel)
    assert sum(len(i['annotations'])+len(i['references']) for i in images)==len(objects)
    return panel,dict(workers=workers,records=ids)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--private-map',type=Path,required=True)
    a=p.parse_args();panel,mapping=project(json.loads(a.input.read_text(encoding='utf-8')))
    a.out.parent.mkdir(parents=True,exist_ok=True);a.private_map.parent.mkdir(parents=True,exist_ok=True)
    write_json(a.out,panel);write_json(a.private_map,mapping)
