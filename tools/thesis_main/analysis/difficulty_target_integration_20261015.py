"""接入固定难度目标与已有分数/融合快照；不重评分、不重运行融合。"""
import csv
import json
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from shapely.geometry import Polygon
from PIL import Image, ImageDraw

from .difficulty_coarse_closeout_20261014 import floor, same_floor
from .scope_difficulty_review_20261011 import floor_features
from .research_round_20260929 import prepare_record
from ..data_prep.consolidate_research_input import load_current_bundle
from ..data_prep.project_public_research_20260929 import project_bundle

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT/'research/difficulty_target_integration_20261015'
DROOT = ROOT/'analysis_results/difficulty_scope_preferred_20261011'
QROOT = ROOT/'research/quality_joint_closeout_review_20261015'
FROOT = ROOT/'research/wall_consensus_population_20261014'


def read(p):
    return json.loads(p.read_text(encoding='utf-8-sig'))


def csvread(p):
    with p.open(encoding='utf-8-sig',newline='') as f:
        return list(csv.DictReader(f))


def save(name, rows):
    assert rows, name
    with (OUT/name).open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)


def compare_floor(a,b):
    if same_floor(a,b):
        return 'same_vertices',0.
    pa,pb=Polygon(a),Polygon(b)
    if not pa.is_valid or not pb.is_valid or min(pa.area,pb.area)<=0:
        return 'uncomputable',None
    delta=pa.symmetric_difference(pb).area/max(pa.area,pb.area)
    return ('same_footprint' if delta<=1e-8 and pa.hausdorff_distance(pb)<=1e-8 else 'different_floor'),delta


def classify_use(r,relation,full_target,grade,new_scope):
    if new_scope or any(str(r.get(k,''))=='True' for k in
        ('same_target_quality_hold','latest_step_reference_pending')):
        return 'hold_scope_or_reference'
    if relation=='uncomputable':
        return 'hold_geometry'
    if relation=='different_floor':
        return 'image_only_different_target'
    if not full_target:
        return 'floor_only_target_equivalence'
    if grade in ('待复核','单列') or r['stage']!='ordinary':
        return 'separate_special_or_pending'
    if r['condition']!='manual' or r['role']!='manual_development_candidate':
        return 'separate_secondary_or_exception'
    return 'ordinary_same_target_conditional'


def main():
    OUT.mkdir(exist_ok=True)
    b=load_current_bundle()
    with zipfile.ZipFile(QROOT/'pro_closeout_delta.zip') as z:
        old=json.loads(z.read('source/historical_current_formal_loader_data.json'))
    assert b['data']==old, 'live loader changed since scoring: inspect source before using scores'
    objects={r['object_id']:r for r in b['data']['objects']}
    projected,aliases=project_bundle(b)
    projected_records={r['id']:r for im in projected['images'] for r in im['annotations']}
    alias_to_object={alias:oid for oid,alias in aliases['records'].items()}
    doc=read(DROOT/'current_259.json');ds={r['image_id']:r for r in doc['records']}
    joint=csvread(QROOT/'JOINT_COMPARISON_1145.csv')
    assert len(joint)==len({r['record_id'] for r in joint})==1145
    delta=read(ROOT/'research/quality_scope_model_handoff_20261015/TWO_IMAGE_SCOPE_DELTA.json')['records']
    new_scopes={r['image_id']:r for r in delta}
    output=[]
    for r in joint:
        d=ds[r['image_id']];ref=objects[r['reference_id']];obj=objects[r['object_id']]
        assert alias_to_object[r['record_id']]==r['object_id']
        assert obj['image_id']==ref['image_id']==d['image_id']
        assert obj['worker_id']==r['worker_id'] and obj['condition']==r['condition']
        rel,area=compare_floor(d['selected']['floor'],floor(ref['points_1024x512']))
        same_id=r['reference_id']==d['target_version']
        full_target=same_id and not d['top_boundary_pending'] and rel in ('same_vertices','same_footprint')
        use=classify_use(r,rel,full_target,d['current_class'],r['image_id'] in new_scopes)
        output.append(dict(r,difficulty_version=doc['version'],difficulty_class=d['current_class'],
            difficulty_target_id=d['target_version'],difficulty_top_pending=bool(d['top_boundary_pending']),
            reference_id_equal=same_id,target_floor_relation=rel,relative_area_difference=area,
            quality_geometry_matches_live_snapshot=True,score_version='WQ-LS08-20261014',
            new_scope_binding_pending=r['image_id'] in new_scopes,use_panel=use,
            source_points_and_reference_checked=True,formal_eligibility_granted_by_this_audit=False,
            live_quality_gate=json.dumps(obj.get('main_quality_gate'),ensure_ascii=False),
            live_consensus_gate=json.dumps(obj.get('main_consensus_gate'),ensure_ascii=False)))
    save('quality_bindings_1145.csv',output)
    save('ordinary_same_target_panel.csv',[r for r in output if r['use_panel']=='ordinary_same_target_conditional'])
    save('limited_or_unmatched.csv',[r for r in output if r['use_panel']!='ordinary_same_target_conditional'])
    save('different_id_audit_95.csv',[r for r in output if not r['reference_id_equal']])
    # 保留已批准的新底面为新目标条目，不把旧目标的难度或完整Q移过去。
    newrows=[]
    for r in delta:
        d=ds[r['image_id']];f=floor_features(r['new_floor_polygon_xz_h'])
        newrows.append(dict(image=r['image_code'],image_id=r['image_id'],old_target=d['target_version'],
            old_class=d['current_class'],new_target=r['new_floor_candidate_id'],new_floor=r['new_floor_polygon_xz_h'],
            features=f,conditional_difficulty='简单',classification_basis='two_image_target_specific_photo_review',
            evidence=('确认范围只保留直走道，墙面延续与端部停止边可定位，不再要求恢复近墙背后分支。'
                      if r['image_code']=='B6ByNegPMKs-37' else '确认四转折底面以可见门边和墙线确定停止位置，柜体局部遮脚不造成未知分支。'),
            top_boundary_pending=True,answer_to_candidate_assignments=r['answer_to_candidate_assignments'],
            source='research/quality_scope_model_handoff_20261015/TWO_IMAGE_SCOPE_DELTA.json',
            use='new_target_floor_only_not_applied_to_old_scores'))
    (OUT/'new_target_addendum.json').write_text(json.dumps(dict(version='difficulty_target_addendum_20261015',records=newrows),ensure_ascii=False,indent=2),encoding='utf-8')
    for r in newrows:
        im=Image.open(ds[r['image_id']]['photo']).convert('RGB').resize((1024,512));draw=ImageDraw.Draw(im)
        for i,(x,z) in enumerate(r['new_floor']):
            u=(np.arctan2(x,-z)/(2*np.pi)+.5)*1024
            v=(np.arctan2(1,np.hypot(x,z))/np.pi+.5)*512
            draw.ellipse((u-5,v-5,u+5,v+5),fill='cyan',outline='black')
            draw.text((u+6,v),str(i+1),fill='cyan',stroke_width=1,stroke_fill='black')
        im.save(OUT/(r['image']+'_new_floor.jpg'),quality=93)
    snap=read(FROOT/'input_snapshot.json');fusion=[];pool_bindings=[]
    for im in snap['images']:
        d=ds[im['image_id']]
        assert im['difficulty_version']==doc['version'] and im['difficulty']['target_version']==d['target_version']
        for r in im['records']:
            obj=objects[alias_to_object[r['id']]]
            prepared=prepare_record(dict(projected_records[r['id']],source_pair_indices=obj['ordered_source_pair_indices']))
            equal=np.array_equal(np.asarray(r['points']),np.asarray(prepared['points']))
            pool_bindings.append(dict(image=im['image'],record_id=r['id'],object_id=obj['object_id'],
                public_worker=r['worker'],worker_id=obj['worker_id'],condition=obj['condition'],
                points_equal_live=equal,source_snapshot='research/wall_consensus_population_20261014/input_snapshot.json',
                raw_object_points_equal_snapshot=np.array_equal(np.asarray(r['points']),np.asarray(obj['points_1024x512'])),
                preparation='project_bundle + prepare_record with current source_pair_indices',
                live_consensus_gate=json.dumps(obj['main_consensus_gate'],ensure_ascii=False)))
        for ref in im['references']:
            oid=alias_to_object.get(ref['id'],ref['id'])
            points_current=None if ref.get('points') is None else np.array_equal(np.asarray(ref['points']),np.asarray(objects[oid]['points_1024x512']))
            rel,area=compare_floor(d['selected']['floor'],ref['floor'])
            fusion.append(dict(image=im['image'],image_id=im['image_id'],reference_kind=ref['version'],
                reference_record_id=ref['id'],reference_object_id=oid,difficulty_target_id=d['target_version'],
                difficulty_version=doc['version'],difficulty_class=d['current_class'],floor_relation=rel,
                relative_area_difference=area,reference_points_equal_live=points_current,
                full_target_match=bool(points_current and oid==d['target_version'] and not d['top_boundary_pending'] and rel!='different_floor'),
                bottom_target_match=rel in ('same_vertices','same_footprint'),
                reference_hold=im['reference_hold'],score_version='not_scored_here',
                use='full_reference_available' if points_current and oid==d['target_version'] and not d['top_boundary_pending'] else 'floor_only_or_other_target'))
    assert all(r['points_equal_live'] for r in pool_bindings),'fusion source points changed'
    save('fusion_reference_bindings.csv',fusion);save('fusion_pool_bindings.csv',pool_bindings)
    member_maps={im['image']:{r['worker']:r['id'] for r in im['records']} for im in snap['images']}
    observation_bindings=[]
    bycode={r['image']:r for r in ds.values()}
    for r in csvread(FROOT/'observations.csv'):
        d=bycode[r['image']]
        ids=[member_maps[r['image']][w] for w in r['subset'].split('|')]
        assert len(ids)==int(r['k'])
        observation_bindings.append(dict(r,member_record_ids='|'.join(ids),condition='manual',
            difficulty_class=d['current_class'],difficulty_target_id=d['target_version'],difficulty_version=doc['version'],
            score_version='existing_floor_metrics_not_WQ',source='research/wall_consensus_population_20261014/observations.csv'))
    save('fusion_observation_bindings.csv',observation_bindings)
    # 已发表的同目标底面轨迹只作带分母描述，不新运行融合或推断WQ。
    curves=[]
    for r in csvread(FROOT/'by_image_k.csv'):
        d=bycode[r['image']]
        curves.append(dict(image=r['image'],image_id=d['image_id'],difficulty_class=d['current_class'],
            difficulty_target_id=d['target_version'],difficulty_version=doc['version'],
            panel=r['panel'],k=r['k'],paths=r['paths'],evaluated=r['difficulty_selected_floor__iou_n'],
            floor_iou_mean=r['difficulty_selected_floor__iou_mean'],
            completeness=r['complete_floor_evaluable_mean'],metric='existing_bottom_iou_not_WQ',
            source='research/wall_consensus_population_20261014/by_image_k.csv'))
    save('fusion_same_target_floor_curves.csv',curves)
    grouped=defaultdict(list)
    for r in curves:
        grouped[('available_12',r['difficulty_class'],r['k'])].append(r)
        if r['panel']=='common24x10':
            grouped[('fixed_common_10',r['difficulty_class'],r['k'])].append(r)
    strata=[]
    for (scope,grade,k),rs in sorted(grouped.items(),key=lambda x:(x[0][0],x[0][1],int(x[0][2]))):
        valid=[r for r in rs if int(r['evaluated'])>0 and r['floor_iou_mean']]
        strata.append(dict(panel_scope=scope,difficulty_class=grade,k=k,images=len(rs),evaluable_images=len(valid),
            paths=sum(int(r['paths']) for r in rs),evaluated=sum(int(r['evaluated']) for r in rs),
            image_equal_mean_iou=float(np.mean([float(r['floor_iou_mean']) for r in valid])) if valid else '',
            image_equal_completeness=float(np.mean([float(r['completeness']) for r in rs])),
            images_in_cell='|'.join(r['image'] for r in rs)))
    save('fusion_floor_difficulty_description.csv',strata)
    summary=dict(schema='difficulty_target_integration_20261015_v1',difficulty_version=doc['version'],
        current_loader_equals_quality_scoring_snapshot=True,loader_manifest=b['manifest'],
        quality_update=b.get('quality_update'),quality_records=len(output),quality_images=len({r['image_id'] for r in output}),
        same_id=sum(r['reference_id_equal'] for r in output),relations=dict(Counter(r['target_floor_relation'] for r in output)),
        panels=dict(Counter(r['use_panel'] for r in output)),
        same_target_panel_images=len({r['image_id'] for r in output if r['use_panel']=='ordinary_same_target_conditional'}),
        different_id_relations=dict(Counter(r['target_floor_relation'] for r in output if not r['reference_id_equal'])),
        fusion_images=len(snap['images']),fusion_reference_rows=len(fusion),fusion_pool_records=len(pool_bindings),
        fusion_full_target_images=len({r['image'] for r in fusion if r['full_target_match']}),
        fusion_observations=len(observation_bindings),
        fusion_incomplete_floor_observations=sum(r['complete_floor_evaluable']!='True' for r in observation_bindings),
        fusion_source_geometry_unchanged=True,classification_overwritten=False,quality_or_fusion_recomputed=False)
    (OUT/'CHECKS.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in summary.items() if k not in ('loader_manifest','quality_update')},ensure_ascii=False))


if __name__=='__main__':
    main()
