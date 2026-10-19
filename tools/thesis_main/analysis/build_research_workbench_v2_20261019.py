"""将 v2 实际统计与最终几何接入已有离线研究台；不重评分或融合。"""
import gzip
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd

from .build_research_workbench_20261017 import write

ROOT = Path(__file__).resolve().parents[3]
PAGE = ROOT / 'research/statistics/research_explorer_v1_r2_20261017'
STATS = ROOT / 'research/statistics/v2_integrated_analysis_20261019'
EVIDENCE = ROOT / 'research/statistics/v2_evidence_audit_20261019'
QUALITY = ROOT / 'research/quality/quality_workers_v2_20261019'
INPUT = ROOT / 'research/data/releases/v2/analysis_input'
SNAPSHOT = 'v2_integrated_analysis_20261019'
SAME_ROOM = ROOT / 'research/same_room/same_room_v2_prediction_20261019'


def read(path):
    raw = gzip.decompress(path.read_bytes()) if path.suffix == '.gz' else path.read_bytes()
    return json.loads(raw.decode('utf-8-sig'))


def load_same_room_prediction(source):
    tables = {}
    for filename, columns in read(source / 'FIELD_CONTRACT.json')['tables'].items():
        frame = pd.read_csv(source / filename)
        if list(frame.columns) != columns:
            raise ValueError('same-room display schema drift: ' + filename)
        rows = frame.astype(object).where(frame.notna(), None).to_dict('records')
        for row in rows:
            if 'source_image' in row:
                row.update(image_a=row['source_image'], image_b=row['target_image'])
            if 'image_a' in row:
                row['condition'] = 'manual'
        tables['same_room_prediction__' + Path(filename).stem] = rows
    return tables


def validate_objects(objects, scores):
    annotations = {o['object_id']: o for o in objects if o['object_kind'] == 'annotation'}
    score_map = {r['object_id']: r for r in scores}
    if len(score_map) != len(scores):
        raise ValueError('duplicate score object')
    if annotations.keys() != score_map.keys():
        raise ValueError('annotation inventory mismatch')
    for key, obj in annotations.items():
        if obj['image_id'] != score_map[key]['image_id']:
            raise ValueError('object image mismatch: ' + key)
    return annotations, score_map


def pack_annotation(obj, score, reference_ids):
    target = score.get('rescore_target_id') or score.get('reference_id') or score.get('chosen_target_id')
    if target and target not in reference_ids:
        raise ValueError('missing image reference: ' + target)
    return dict(object_id=obj['object_id'], worker_id=obj['worker_id'], condition=obj['condition'],
                retained=obj['cleaning_disposition'] == 'retained', target_id=target,
                points=obj.get('points_1024x512'), raw_points=obj.get('original_export_points'),
                before_preprocessing_points=obj.get('before_preprocessing_points'),
                ring_confirmed=obj.get('ring_confirmed', False), order_status=obj.get('order_status'),
                geometry_compatible=True, geometry_binding_reasons=[],
                quality_usable=score['quality_usable'],
                quality={k: score.get(k) for k in ('B8L2', 'D10', 'IoU3D100')},
                calculation_status=score.get('calculation_status', score.get('calculation_class', score.get('full_score_state'))),
                quality_exclusion_reasons=score.get('quality_exclusion_reasons', []))


def display_table(out, name, rows, source):
    columns = list(dict.fromkeys(k for r in rows for k in r))
    parts = []
    for start in range(0, len(rows), 2000):
        path = f'tables/{name}_{start // 2000}.json'
        write(out / path, dict(columns=columns, rows=[[r.get(k) for k in columns] for r in rows[start:start+2000]]))
        parts.append(dict(path=path))
    return dict(id=name, row_count=len(rows), columns=columns, parts=parts, path=source)


def pack_resources(scores, evidence):
    context=read(ROOT/'research/workers/pro_personnel_v2_20261019/analysis_context.json.gz')
    frozen_objects=[dict(object_id=r['object_id'],object_kind='annotation',image_id=r['image_id'],
                         worker_id=r['worker_id'],condition=r['condition'],cleaning_disposition=r['cleaning_disposition'],
                         points_1024x512=r['points_1024x512'],original_export_points=r['original_points'],
                         before_preprocessing_points=r['received_processed_points'],
                         ring_confirmed=r['coordinate_evidence']['ring_confirmed'],order_status=r['coordinate_evidence']['order_status']) for r in evidence]
    objects, score_map = validate_objects(frozen_objects, scores)
    difficulty = {r['image_id']: r for r in context['difficulty_records']}
    refs, annotations = defaultdict(list), defaultdict(list)
    for ref in context['reference_catalog']:
        refs[ref['image_id']].append(ref)
    for obj in objects.values():
        annotations[obj['image_id']].append(obj)
    images = []
    for number, (image_id, d) in enumerate(difficulty.items()):
        reference_ids = {r['target_id'] for r in refs[image_id]}
        answers = [pack_annotation(o, score_map[o['object_id']], reference_ids) for o in annotations[image_id]]
        references = [dict(target_id=r['target_id'], label=f"{i+1} · {r['reference_version']}" + (' · 当前' if r['current_target'] else ''),
                           points=r['points_1024x512'], floor=r['floor_xz_h'], current=r['current_target'],
                           reference_full_available=r['full_reference_available']) for i,r in enumerate(refs[image_id])]
        photo_candidates = [(ROOT / d['photo']).resolve()] if d.get('photo') else []
        photo_candidates += [ROOT/f'data/mp3d_layout/img_v/{image_id}.jpg',
                             ROOT/f'research/workers/pro_personnel_v2_20261019/previews/{image_id}.jpg']
        photo = next((p for p in photo_candidates if p.is_file()), None)
        retained = [a for a in answers if a['retained']]
        flags = dict(gt_uncertain=d.get('reference_status')=='uncertain',current_pending=bool(d.get('difficulty_analysis_exclusion')))
        flags.update(oos=any(score_map[a['object_id']].get('is_oos') is True for a in answers),
                     gt_problem=bool(d.get('gt_error_excluded')), image_hold=any(r.get('image_analysis_blocked') for r in refs[image_id]))
        packed = dict(image_id=image_id, image_code=d['image'], building_id=image_id.split('_')[0],
                      difficulty=dict(label=d['current_class'], exclusion=d.get('difficulty_analysis_exclusion')),
                      scene=dict(raw=d['scene'], doorway_status=d['doorway_status'], oos_subtype=d['oos_subtype']),
                      flags=flags, notes=[d.get('evidence',''), d.get('applicability_note','')],
                      spaces=[dict(r, user_candidate=not r['target_id'].startswith('gt:')) for r in references],
                      multiple_spaces=len(references)>1, references=references, annotations=answers,
                      photo='../../../'+photo.relative_to(ROOT).as_posix() if photo else None,
                      photo_status='available' if photo else 'missing',
                      counts=dict(retained_people=len({a['worker_id'] for a in retained}),
                                  retained_records=len(retained), raw_records=len(answers),
                                  quality_records=sum(a['quality_usable'] for a in answers)))
        # Coordinate arrays are in the per-image file only, not repeated in the index.
        packed['spaces'] = [{k:v for k,v in r.items() if k not in ('points','floor')} for r in packed['spaces']]
        path = f'images/{number}.json'
        write(PAGE / 'v2-resources' / path, packed)
        images.append(dict({k:v for k,v in packed.items() if k not in ('references','annotations')}, detail=path))
    assert sum(i['counts']['raw_records'] for i in images) == len(scores)
    summary = dict(raw_records=len(scores), images=len(images), quality_records=sum(r['quality_usable'] for r in scores),
                   retained_people=len({r['worker_id'] for r in scores if r['cleaning_disposition']=='retained'}))
    write(PAGE / 'v2-resources/index.json', dict(schema='research_workbench_display_v1', data_release='v2',
          snapshot_id=SNAPSHOT, built_at=datetime.now(timezone.utc).isoformat(), images=images, pools=[],
          image_summary=summary, geometry_binding_mismatches=0, gallery_score_context=dict(data_release='v2',primary_metric='B8L2',parallel_metric='D10',n1_applied=False),
          fusion_revision='v2_not_run; v1 results available via version selector', dependencies=[],
          historical_offline_files=0, supplement_plan=None))
    return summary


def build():
    source_tables = read(STATS / 'tables.json.gz')['tables']
    tables = {k:v for k,v in source_tables.items() if k!='quality__shared_records'}
    evidence = read(EVIDENCE / 'records.json.gz')['records']
    # Heavy provenance and all coordinate stages remain in per-image details and the audit gzip.
    detail_fields = ('time_evidence','binding_evidence','coordinate_evidence','scope_evidence','semi_evidence',
                     'exclusion_attribution','review_evidence','comments','image_comments')
    light = []
    for r in evidence:
        row = {k:v for k,v in r.items() if not isinstance(v,(dict,list))}
        row.update(rescore_target_id=r['reference_id'], calculation_status=r['calculation_class'],
                   quality_exclusion_reasons=r['quality_exclusion_reasons'],
                   IoU3D100=r['IoU3D100'] if r['quality_usable'] else None, diagnostic_IoU3D100=r['IoU3D100'])
        row.update({k:(r['measurements'].get('same_reference_measurements') or {}).get(k)
                    for k in ('iou_2d','S_bottom_deg','dir','Hmean','Hcenter')})
        row.update(scope_response=r['scope_evidence']['response'], scope_opportunity=r['scope_evidence']['judgement_opportunity'],
                   scope_correct=r['scope_evidence']['correct'], time_source=r['time_evidence']['source_kind'])
        light.append(row)
    tables['quality__shared_records'] = light
    for filename, table_id in [('profiles','person_profiles_and_evidence'),('reliability','reliability'),
                               ('difficulty_preferences','difficulty_preferences')]:
        tables['workers__'+table_id]=source_tables['statistics__personnel_'+filename]
    scope, semi, exclusions = [], [], []
    for row in evidence:
        identity={k:row[k] for k in ('object_id','image_id','image_code','worker_id','condition','origin','reference_id','quality_usable')}
        scope.append(dict(identity, **{k:v for k,v in row['scope_evidence'].items() if not isinstance(v,(dict,list))}))
        exclusions.append(dict(identity,**{k:v for k,v in row['exclusion_attribution'].items() if not isinstance(v,(dict,list))}))
        if row['condition']=='semi':
            s=row['semi_evidence']
            entry=dict(identity,**{k:v for k,v in s.items() if not isinstance(v,(dict,list))})
            entry.update({f'initial_{k}':v for k,v in (s.get('current_initial_scores') or {}).items()})
            entry.update({f'worker_attributable_gain_{k}':v for k,v in (s.get('current_worker_attributable_gain') or {}).items()})
            semi.append(entry)
    tables.update(workers__scope_opportunities=scope,workers__semi_initialization_scores=semi,workers__exclusion_evidence=exclusions)
    tables.update(load_same_room_prediction(SAME_ROOM))
    metadata = [display_table(PAGE/'v2-data', name, rows, f'{STATS.relative_to(ROOT).as_posix()}/tables.json#{name}')
                for name, rows in tables.items()]
    next(t for t in metadata if t['id']=='quality__shared_records')['path'] = EVIDENCE.relative_to(ROOT).as_posix()+'/records.json.gz'
    for item in metadata:
        if item['id'].startswith('same_room_prediction__'):
            item['path'] = f'{SAME_ROOM.relative_to(ROOT).as_posix()}/{item["id"].split("__")[1]}.csv'
        elif item['id'].startswith('statistics__'):
            item['path'] = f'{STATS.relative_to(ROOT).as_posix()}/tables.json.gz#{item["id"]}'
        elif item['id'].startswith('workers__'):
            source = {'person_profiles_and_evidence':'profiles', 'reliability':'reliability',
                      'difficulty_preferences':'difficulty_preferences'}.get(item['id'].split('__')[1])
            item['path'] = (f'{STATS.relative_to(ROOT).as_posix()}/tables.json.gz#statistics__personnel_{source}'
                            if source else EVIDENCE.relative_to(ROOT).as_posix()+'/records.json.gz')
    coverage = read(STATS/'COVERAGE.json')
    tables['statistics__requirements_coverage']=coverage['requirements']
    metadata.append(display_table(PAGE/'v2-data','statistics__requirements_coverage',coverage['requirements'],
                                  STATS.relative_to(ROOT).as_posix()+'/COVERAGE.json'))
    modules={
        'data':[('作答明细','quality__shared_records'),('图片库存','statistics__image_inventory'),('人员库存','statistics__worker_inventory')],
        'workers':[('探索性Q/T/难度画像','workers__person_profiles_and_evidence'),('难度适应候选','workers__difficulty_preferences'),
                   ('逐人×难度','statistics__worker_difficulty'),('逐人×场景','statistics__worker_scene'),('独立行为证据','workers__reliability')],
        'quality':[('作答与几何分项','quality__shared_records'),('固定记录指标敏感性','statistics__fixed_record_metric_sensitivity')],
        'fusion':[('待实验人员池支持','statistics__independent_pool_inventory'),('当前原答分歧','statistics__raw_disagreement_summary')],
        'same_room':[(title, 'same_room_prediction__' + name) for title, name in [
                     ('v2预测与人数曲线','prediction_summary'),('逐建筑预测增益','prediction_gains'),
                     ('逐图对描述与资格','pair_descriptive'),('逐人逐次预测','predictions'),
                     ('门洞单列','doorway_separate'),('模型折与不支持原因','fold_models'),
                     ('预测覆盖','prediction_coverage'),('关系准入审计','relation_coverage')]] +
                    [('直接图对','statistics__direct_pair_summary'),('共同人员双侧明细','statistics__direct_pair_people'),
                     ('关系登记','statistics__room_registry'),('关系组成员','statistics__room_memberships'),('加权敏感性','statistics__room_weighting_sensitivity')],
        'time':[('Semi初始化与增益证据','workers__semi_initialization_scores'),('来源与同目标时间','quality__shared_records'),
                ('时间来源覆盖','statistics__time_provenance_coverage'),('scope裁定机会','workers__scope_opportunities')],
        'coverage':[('可计算与用途','statistics__calculation_coverage'),('逐图人数','statistics__image_inventory'),
                    ('逐人库存','statistics__worker_inventory'),('排除归因','workers__exclusion_evidence'),
                    ('重叠限制原因','statistics__exclusion_reason_hits'),('逐项需求覆盖','statistics__requirements_coverage')]
    }
    modules={key:[tab for tab in tabs if tab[1] in tables] for key,tabs in modules.items()}
    write(PAGE/'v2-data/index.json', dict(snapshot_id=SNAPSHOT, data_release='v2', tables=metadata,module_tabs=modules,
          documents=[dict(path='research/statistics/v2_integrated_analysis_20261019/COVERAGE.json',content=coverage),
                     dict(path=SAME_ROOM.relative_to(ROOT).as_posix()+'/CONSUMER_INTERFACE.json',content=read(SAME_ROOM/'CONSUMER_INTERFACE.json')),
                     dict(path='research/statistics/v2_evidence_audit_20261019/COVERAGE.json',content=read(EVIDENCE/'COVERAGE.json'))]))
    summary = pack_resources(light,evidence)
    by_object = {r['object_id']:r for r in evidence}
    resources = read(PAGE/'v2-resources/index.json')
    for item in resources['images']:
        path = PAGE/'v2-resources'/item['detail']
        image = read(path)
        for annotation in image['annotations']:
            row = by_object[annotation['object_id']]
            annotation['evidence'] = {k:row[k] for k in detail_fields}
        write(path,image)
    sections = [dict(title='v2 实际覆盖',finding=f"{summary['raw_records']}份库存，{summary['quality_records']}份主质量可用。",
               support='逐作答ID合并；诊断、正式质量、来源时间与同目标时间分别保留。',counterexample='人数增加不代表所有图均有35份正式质量。',
               tables=[dict(id='quality__shared_records',label='全部作答与证据')]),
               dict(title='两条人员研究方向',finding='Q×T×难度细类，以及从标法簇反向解释人员差异。',
               support='A人员分型及B独立替换验收已有结果；类别组合ABCD与ABCE的比较方案正在讨论，人数与配额尚未固定。',
               counterexample='不能在同一图上发现好组合、反调分类，再将同图结果称为验证。',tables=[]),
               dict(title='v1 与 v2 分开',finding='v1 已有的融合过程、9°/12°分簇与替换实验保留在 v1 入口。',
               support='v2分簇、组合与替换已有独立研究包；本页过程几何仍按各入口的实际接入状态解释。',
               counterexample='旧路径记录数量不是 v2 独立样本数，也不是 v2 实测融合结果。',tables=[]),
               dict(title='v2同房条件预测',finding='首轮Q/T预测与源视角人数实验已接入同房模块。',
               support='OOS排除、门洞单列；已知源视角评价下留建筑预测，人员分类暂不接入。',
               counterexample='尚无确认异房匹配对照；不同预测面板不能直接比较优劣。',
               tables=[dict(id='same_room_prediction__prediction_summary',label='预测汇总与人数曲线')])]
    write(PAGE/'v2-data/overview.json',dict(metadata=dict(snapshot_id=SNAPSHOT),sections=sections))
    print(json.dumps(dict(**summary,tables=len(metadata)),ensure_ascii=True))


if __name__ == '__main__':
    build()
