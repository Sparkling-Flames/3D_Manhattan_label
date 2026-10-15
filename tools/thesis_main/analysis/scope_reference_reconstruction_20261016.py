"""按已确认空间和可追溯完整几何构造参考；不选择作答参考、不改原GT。"""
import argparse
import csv
import json
import zipfile
from collections import defaultdict
from pathlib import Path

import numpy as np
from shapely.geometry import Point, Polygon

from tools.label_studio.panorama_studio.geometry import project_pixel
from .descriptive_reference_audit_20261015 import ROOT, floor, scope_sources
from .difficulty_user_revision_20261015 import convert_original
from .descriptive_pool_gate_20261015 import IMAGE_CONSENSUS_HOLDS, IMAGE_QUALITY_HOLDS

PREPARED = 'research/quality_pro_joint_archive_20261013/source/routing/inputs/prepared_input.json'
ORIGINAL_LAYOUTS = Path('C:/Users/ASUS/Downloads/label_data.zip')
EPS = 1e-8  # 仅数值相等，不吸收像素舍入误差或人工矩形拟合差异。


def read_prepared():
    return json.loads((ROOT / PREPARED).read_text(encoding='utf-8'))


def geometry(points):
    p = np.asarray(points, float)
    bottom = floor(p)
    radius = np.linalg.norm(bottom, axis=1)
    heights = -radius * np.tan((p[::2,1]/512-.5)*np.pi)
    return dict(bottom3d=np.column_stack([bottom[:,0], -np.ones(len(bottom)), bottom[:,1]]).tolist(),
                top3d=np.column_stack([bottom[:,0], heights, bottom[:,1]]).tolist())


def source_planes(bundle):
    """原JSON显式单一layoutHeight；先证明其既定转换逐值等于原GT TXT。"""
    sources = {}
    with zipfile.ZipFile(ORIGINAL_LAYOUTS) as archive:
        for obj in bundle['data']['objects']:
            if obj['object_kind'] != 'gt_original':
                continue
            member = 'label_data/' + obj['image_id'] + '_label.json'
            raw = json.loads(archive.read(member))
            if convert_original(raw) != obj['points_1024x512']:
                raise ValueError('original JSON / live GT conversion mismatch: ' + obj['object_id'])
            height = float(raw['layoutHeight']) / float(raw['cameraHeight']) - 1
            if not np.isfinite(height) or height <= 0:
                raise ValueError('invalid explicit source ceiling height')
            sources[obj['object_id']] = dict(plane=[0.,0.,height], archive=str(ORIGINAL_LAYOUTS),
                member=member, cameraHeight=raw['cameraHeight'], layoutHeight=raw['layoutHeight'],
                original_json_conversion_equals_current_GT=True,
                source_json_geometry={key:raw[key] for key in ['cameraHeight','layoutHeight','layoutPoints']},
                source_model='source JSON explicitly declares one layoutHeight; not fitted from ERP or averaged heights')
    return sources


def reconstruct_scope(target_floor, source_points, ceiling_plane=None):
    """严格恒等范围复用完整原环；严格内裁切只用源明确声明的顶平面。"""
    target, source = Polygon(target_floor), Polygon(floor(source_points))
    if not target.is_valid or not source.is_valid or min(target.area, source.area) <= 0:
        raise ValueError('invalid target/source polygon')
    outside = target.difference(source).area
    base = dict(full_reference_available=False, points_1024x512=None, geometry=None,
        outside_source_area_h2=float(outside), method='unresolved', minimal_gap='',
        introduced_scope_edges=[], vertex_sources=[], physical_wall_asserted=False)
    equivalent = target.symmetric_difference(source).area <= EPS and target.hausdorff_distance(source) <= EPS
    if equivalent:
        return dict(base, full_reference_available=True, points_1024x512=source_points,
            geometry=geometry(source_points), method='identical_footprint_existing_full_geometry',
            vertex_sources=[dict(source_pair_index=i) for i in range(len(source_points)//2)])
    if outside > EPS:
        return dict(base, method='intersection_only_diagnostic', minimal_gap='confirmed_polygon_extends_beyond_complete_source_domain',
            diagnostic_intersection_geometry=target.intersection(source).__geo_interface__)
    if ceiling_plane is None:
        return dict(base, minimal_gap='explicit_ceiling_plane_missing_for_new_scope_boundary')
    a,b,c = ceiling_plane
    points, top, vertices, introduced = [], [], [], []
    original_floor = np.asarray(source.exterior.coords)[:-1]
    for i, (x,z) in enumerate(target_floor):
        height = a*x+b*z+c
        if not np.isfinite(height) or height <= 0:
            return dict(base, minimal_gap='declared_source_ceiling_not_above_camera_on_target')
        points += [project_pixel([x,height,z],1024,512), project_pixel([x,-1,z],1024,512)]
        top.append([x,height,z])
        index = np.flatnonzero(np.linalg.norm(original_floor-[x,z],axis=1) <= EPS)
        vertices.append(dict(target_vertex_index=i, source_pair_index=int(index[0]) if len(index) else None,
                             constraint='explicit_source_ceiling_plane'))
        start, end = np.asarray(target_floor[i]), np.asarray(target_floor[(i+1)%len(target_floor)])
        if source.boundary.distance(Point(*(start+end)/2)) > EPS:
            introduced.append(i)
    return dict(base, full_reference_available=True, points_1024x512=points,
        geometry=dict(bottom3d=[[x,-1,z] for x,z in target_floor],top3d=top),
        method='contained_vertical_cut_explicit_source_ceiling_plane', vertex_sources=vertices,
        introduced_scope_edges=introduced,
        construction='V={(x,y,z):(x,z) in source footprint,-1<=y<=a*x+b*z+c}; selected=V intersect vertical(P); P subset source footprint')


def build_reference_catalog(bundle, difficulty_records):
    difficulty = {row['image_id']: row for row in difficulty_records}
    objects = {obj['object_id']: obj for obj in bundle['data']['objects']}
    sources, planes, prepared = scope_sources(bundle), source_planes(bundle), read_prepared()
    by_image, holds = defaultdict(list), defaultdict(set)
    for obj in objects.values():
        if obj['object_kind'] != 'annotation':
            by_image[obj['image_id']].append(obj)
        for field, statuses in [('main_consensus_gate',IMAGE_CONSENSUS_HOLDS),('main_quality_gate',IMAGE_QUALITY_HOLDS)]:
            if obj.get(field,{}).get('status') in statuses:
                holds[obj['image_id']].add(field + ':' + obj[field]['status'])
    for image in bundle['research']['images']:
        if image.get('gt_substantive_error_mark'):
            holds[image['image_id']].add('historical_gt_substantive_error')
    for row in difficulty_records:
        if row.get('gt_error_excluded'):
            holds[row['image_id']].add('current_gt_error_unresolved')
        if row.get('difficulty_analysis_exclusion') == 'target_scope_unresolved':
            holds[row['image_id']].add('current_target_scope_unresolved')
    catalog = {}

    def register(target_id, image_id, role, fp, points, source, **extra):
        row = dict(target_id=target_id, image_id=image_id, image_code=difficulty[image_id]['image'],
            reference_version='scope_reference_reconstruction_20261016_v1', current_target=False,
            role=role, version_alias=False, is_admitted_space_candidate=False,
            full_reference_available=points is not None, points_1024x512=points, floor_xz_h=fp,
            geometry=geometry(points) if points is not None else None,
            status='existing_full_geometry' if points is not None else 'pending_full_geometry',
            method='existing_explicit_reference' if points is not None else 'pending',
            source_reference_ids=[target_id] if points is not None else [], sources=[source], evidence={},
            minimal_gap='' if points is not None else 'complete_top_geometry_not_bound',
            image_analysis_blocked=bool(holds[image_id]), image_analysis_hold_reasons=sorted(holds[image_id]))
        row.update(extra)
        catalog[target_id] = row
        return row

    for image_id, references in by_image.items():
        if image_id not in difficulty:
            continue
        for obj in references:
            register(obj['object_id'], image_id, 'original_GT_version' if obj['object_kind']=='gt_original' else 'manual_GT_version',
                floor(obj['points_1024x512']).tolist(), obj['points_1024x512'],
                dict(source='current formal loader', object_id=obj['object_id'], source_path=obj['source']),
                version_alias=True, reference_version=obj.get('gt_version', obj['object_kind']))
    for image in prepared['candidate_images']:
        image_id = image['image_id']
        if image_id not in difficulty:
            continue
        for candidate in image['candidates']:
            target_id = candidate['reference_object_id']
            points = candidate['points_1024x512']
            if target_id in objects and points is not None and points != objects[target_id]['points_1024x512']:
                raise ValueError('prepared candidate / live full-reference drift: ' + target_id)
            row = catalog.get(target_id)
            if row is None:
                row = register(target_id,image_id,'confirmed_space_candidate',candidate['floor_xz_h'],points,
                    dict(source=PREPARED,candidate_id=candidate['candidate_id']))
            row.update(is_admitted_space_candidate=bool(candidate['admitted_for_routing']),
                candidate_id=candidate['candidate_id'], candidate_role=candidate['candidate_kind'],
                space_label=candidate['space_label'],aliases=candidate.get('aliases',[]),
                registered_candidate_restriction=candidate.get('restriction'),
                candidate_confirmation=candidate.get('human_confirmation_source'))
    for image_id, current in difficulty.items():
        target_id, selected = current['target_version'], current['selected']
        previous = catalog.get(target_id)
        if previous and previous['full_reference_available']:
            if (Polygon(previous['floor_xz_h']).symmetric_difference(Polygon(selected['floor'])).area > EPS or
                    Polygon(previous['floor_xz_h']).hausdorff_distance(Polygon(selected['floor'])) > EPS):
                raise ValueError('same current target ID has conflicting floor geometry: ' + target_id)
            row = previous
            row.update(current_target=True,is_admitted_space_candidate=True,role=selected['role'])
            continue
        provenance = sources.get(target_id)
        if not provenance or provenance['image_id'] != image_id or Polygon(provenance['floor']).hausdorff_distance(Polygon(selected['floor'])) > EPS:
            raise ValueError('current target provenance unavailable or mismatched: ' + target_id)
        row = register(target_id,image_id,selected['role'],selected['floor'],provenance.get('points'),
            dict(source=provenance['source'],pointer=provenance['pointer'],receipt=provenance['receipt']),
            current_target=True,is_admitted_space_candidate=True)
        if previous:
            for key in ['candidate_id','candidate_role','space_label','aliases','registered_candidate_restriction','candidate_confirmation']:
                if key in previous:
                    row[key]=previous[key]
        if provenance.get('points'):
            row.update(status='explicit_user_revised_full_reference',method='user_supplied_surviving_full_pairs',
                       reference_version='user_GT_revision_20261015')
            continue
        attempts = []
        for obj in by_image[image_id]:
            plane = planes.get(obj['object_id'])
            result = reconstruct_scope(selected['floor'],obj['points_1024x512'],plane['plane'] if plane else None)
            attempts.append(dict(source_reference_id=obj['object_id'],source_plane=plane,result=result))
        available = [attempt for attempt in attempts if attempt['result']['full_reference_available']]
        exact = [attempt for attempt in available if attempt['result']['method']=='identical_footprint_existing_full_geometry']
        eligible = exact or available
        row['evidence'] = dict(constructions=attempts, scope_semantics='whole_space_vertical_boundary',
            scoring_does_not_certify_physical_cut_walls=True)
        if eligible and all(np.array_equal(np.asarray(attempt['result']['points_1024x512']),
                                           np.asarray(eligible[0]['result']['points_1024x512'])) for attempt in eligible):
            chosen = eligible[0]
            row.update(chosen['result'],status='deterministically_available_full_reference',
                       source_reference_ids=[attempt['source_reference_id'] for attempt in eligible],
                       reference_version='whole_space_deterministic_reference_20261016_v1')
        else:
            row['minimal_gap'] = ('conflicting_existing_complete_references_require_explicit_binding' if eligible else
                                  '|'.join(sorted({attempt['result']['minimal_gap'] for attempt in attempts})))
    # 两图交接明确旧GT保留且新空间为additional candidate；其余新范围不据“有旧GT”扩充合法空间。
    for provenance in sources.values():
        if provenance['source'] == 'research/quality/quality_scope_model_handoff_20261015/TWO_IMAGE_SCOPE_DELTA.json':
            for obj in by_image[provenance['image_id']]:
                if obj['object_kind'] == 'gt_original':
                    catalog[obj['object_id']].update(is_admitted_space_candidate=True,
                        candidate_admission_source=provenance['source'] + provenance['pointer'],
                        candidate_admission_basis='handoff explicitly retains original GT and adds confirmed space as comparison candidate')
    return list(catalog.values())


def write_catalog(catalog,out):
    out.mkdir(parents=True,exist_ok=True)
    (out/'reference_catalog.json').write_text(json.dumps(dict(version='scope_reference_catalog_20261016_v1',
        references=catalog),ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
    fields=['target_id','image_id','image_code','reference_version','current_target','role','version_alias',
            'is_admitted_space_candidate','full_reference_available','status','method','source_reference_ids',
            'minimal_gap','image_analysis_blocked','image_analysis_hold_reasons']
    with (out/'reference_catalog.csv').open('w',encoding='utf-8-sig',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader()
        for row in catalog:
            writer.writerow({key:json.dumps(row[key],ensure_ascii=False) if isinstance(row[key],list) else row[key] for key in fields})


if __name__ == '__main__':
    from ..data_prep.consolidate_research_input import load_current_bundle
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,default=ROOT/'research/data/scope_quality_rescore_20261016/references')
    args=parser.parse_args()
    pointer=ROOT/'analysis_results/image_difficulty_full_review_20261010/CURRENT.json'
    details=json.loads(pointer.read_text(encoding='utf-8'))
    difficulty=json.loads((pointer.parent/details['details']).resolve().read_text(encoding='utf-8'))
    refs=build_reference_catalog(load_current_bundle(),difficulty['records']);write_catalog(refs,args.out)
    print(json.dumps(dict(references=len(refs),current_targets=sum(row['current_target'] for row in refs),
        complete_current=sum(row['current_target'] and row['full_reference_available'] for row in refs)),ensure_ascii=False))
