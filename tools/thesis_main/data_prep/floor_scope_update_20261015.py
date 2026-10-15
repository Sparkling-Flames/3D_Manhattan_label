"""校验显式接收的底面范围增量；不将其伪装为完整GT或修改作答。"""
import numpy as np
from shapely.geometry import Point, Polygon
import json
from pathlib import Path


def validate_update(update, data):
    if update['schema'] != 'confirmed_floor_scope_update_v1':
        raise ValueError('floor_scope_schema_mismatch')
    objects={r['object_id']:r for r in data['objects']}
    seen=set()
    for r in update['records']:
        if r['reference_id'] in seen:
            raise ValueError('duplicate_floor_scope_id')
        seen.add(r['reference_id'])
        source=objects[r['original_reference_id']]
        if source['image_id']!=r['image_id'] or source['points_1024x512']!=r['original_points_1024x512']:
            raise ValueError('floor_scope_source_mismatch')
        if r['floor_region_confirmed'] is not True or not r['confirmed_at'] or r['top_boundary_pending'] is not True or r['reference_ready'] is not False:
            raise ValueError('floor_scope_confirmation_or_completeness_mismatch')
        points=np.asarray(r['floor_xz_h'],dtype=float)
        if points.ndim!=2 or points.shape[1]!=2 or not np.isfinite(points).all():
            raise ValueError('floor_scope_invalid_coordinates')
        p=Polygon(points)
        if not p.is_valid or p.area<=0 or not p.contains(Point(0,0)):
            raise ValueError('floor_scope_invalid_polygon_or_camera')
    return dict(records=len(seen), status='passed', full_gt_created=False)


def receive():
    from .consolidate_research_input import load_current_bundle, ROOT, OUT
    receipt_path=Path('C:/Users/ASUS/Downloads/空间范围人工审核_2026-10-15(1).json')
    raw=receipt_path.read_bytes(); receipt=json.loads(raw.decode('utf-8-sig'))
    bundle=load_current_bundle()
    wanted={'pa4otMbVnkk-11','uNb9QFRL6hY-54'}
    records=[]
    for i,r in enumerate(receipt['records']):
        if r['image_code'] not in wanted:
            continue
        region=r['space_regions']['regions'][0]
        cv=region['confirmed_version']
        if len(r['space_regions']['regions'])!=1 or not region['floor_region_confirmed'] or not cv['floor_region_confirmed']:
            raise ValueError('expected one explicitly confirmed region')
        polygon=region['polygon']
        if polygon!=cv['polygon'] or polygon!=r['polygon']:
            raise ValueError('saved_and_confirmed_scope_differ')
        operations=cv['operations']
        if len(operations)!=1 or operations[0]['type']!='rectangle' or operations[0]['angle']!=0 or cv['cuts']:
            raise ValueError('unexpected scope editing operation; inspect before accepting')
        op=operations[0]; ax,az=op['a']; bx,bz=op['b']
        if polygon!=[[ax,az],[bx,az],[bx,bz],[ax,bz]]:
            raise ValueError('rectangle_operation_replay_mismatch')
        records.append(dict(image_id=r['image_id'],image_code=r['image_code'],
            reference_id='user_floor_20261015:'+r['image_code'],
            original_reference_id=r['editing_reference_object_id'],
            original_points_1024x512=r['editing_reference_points_1024x512'],
            floor_xz_h=polygon, floor_region_confirmed=True, top_boundary_pending=True,
            reference_ready=False, confirmed_at=cv['confirmed_at'],
            source_receipt='scope_receipt_20261015_1.json', source_pointer=f'/records/{i}/space_regions/regions/0',
            confirmed_snapshot=cv, answer_to_candidate_assignments=[]))
    if {r['image_code'] for r in records}!=wanted or len(records)!=2:
        raise ValueError('new_scope_population_mismatch')
    merged={r['image_id']:r for r in bundle['floor_scope_update']['records']}
    merged.update({r['image_id']:r for r in records})
    for r in merged.values():
        r['scope_semantics']='whole_space_vertical_boundary'
        r['space_scope_confirmed']=True
    update=dict(schema='confirmed_floor_scope_update_v1',revision='four_confirmed_space_scopes_20261015_v2',
        coordinate_frame=receipt['coordinate_frame'],records=list(merged.values()),
        scope_semantics='whole_space_vertical_boundary',
        semantics_source='user clarification 2026-10-15: entire space cut vertically, not floor only',
        import_policy='merge explicit new scope increments; do not replace historical whole-table states')
    validate_update(update,bundle['data'])
    (OUT/'scope_receipt_20261015_1.json').write_bytes(raw)
    (OUT/'floor_scope_update_20261015.json').write_text(json.dumps(update,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    manifest_path=OUT/'manifest.json';manifest=json.loads(manifest_path.read_text(encoding='utf-8-sig'))
    manifest['entrypoints']['floor_scope_update']='floor_scope_update_20261015.json'
    manifest_path.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    new=load_current_bundle()
    assert new['data']==bundle['data'] and new['research']==bundle['research'], 'baseline unexpectedly changed'
    assert len(new['floor_scope_update']['records'])==4
    print('已合并2图，主增量共4图：范围表示整个空间的竖向边界；原始对象与人员数据不变。')


if __name__=='__main__':
    receive()
