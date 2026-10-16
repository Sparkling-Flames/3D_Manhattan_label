"""组装只读图片统计/几何快照；补人计划由独立服务保存。"""
import csv
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

from tools.thesis_main.data_prep.consolidate_research_input import load_current_bundle
from tools.thesis_main.analysis.descriptive_pool_gate_20261015 import load_image_review_decisions
from .current_annotation_context_20261017 import load_scored_context

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / 'research/statistics/annotation_gallery_20261017'
METRICS = ('B8L2', 'D10', 'WQ', 'A10', 'IoU3D100')


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def read_csv(path):
    return list(csv.DictReader(path.open(encoding='utf-8-sig', newline='')))


def true(value):
    return value is True or value == 'True'


def quality_values(row):
    # OOS诊断以及未通过用途门的分数不进入正常质量展示。
    usable = true(row['quality_usable']) and row['condition'] != 'oos'
    return {key: float(row[key]) if usable and row.get(key) not in ('', None) else None for key in METRICS}


def quality_groups(annotations, labels):
    groups = defaultdict(list)
    for row in annotations:
        if row['quality_usable'] and row['condition'] != 'oos':
            assert row['target_binding_unique'] and row['target_id']
            groups[row['condition'], row['target_id']].append(row)
    result = []
    for (condition, target), rows in groups.items():
        group = dict(condition=condition, target_id=target, space_label=labels[target], n=len(rows))
        for metric in METRICS:
            values = [r['quality'][metric] for r in rows if r['quality'][metric] is not None]
            if metric in ('B8L2','D10'):assert len(values)==len(rows), 'shared metric denominator drift'
            group[metric] = sum(values) / len(values) if values else None
        result.append(group)
    return result


def worker_counts(rows):
    raw = {r['worker_id'] for r in rows}
    kept = {r['worker_id'] for r in rows if r['retained']}
    removed = {r['worker_id'] for r in rows if not r['retained']}
    return dict(raw_people=len(raw), removed_people=len(removed), fully_removed_people=len(raw - kept))


def scene_info(row, detail=None):
    status=row['doorway_status']
    labels={'difficult':'门洞交界 · 难标','annotatable':'门洞交界 · 可标','suspected_user_review':'疑似门洞交界 · 待核','not_recorded':'门洞情况未记录','none':'未见门洞交界'}
    return dict(raw=row['scene'],doorway_status=status,doorway_label=labels.get(status,'门洞交界 · '+status),conditional_difficulty=(detail or {}).get('conditional_difficulty',''),oos_subtype=row['oos_subtype'])


def scope_metadata(ref):
    return dict(user_candidate=ref['role'] in ('confirmed_scope','confirmed_space_candidate'),candidate_id=ref.get('candidate_id',''),scope_label=ref.get('space_label',''),note=ref.get('minimal_gap',''))


def routing_info(binding):
    evidence=binding.get('local_routing_evidence')
    if isinstance(evidence,str):evidence=json.loads(evidence) if evidence else None
    if not evidence:return None
    assert evidence['quality_or_height_used_for_route'] is False and evidence['true_intent_established'] is False
    if 'route_reason' not in evidence:
        return dict(version=evidence['version'],route_reason=evidence['status'],uncertainty=evidence['uncertainty'],
                    surviving_candidates=[],survivor_iou_gap=None)
    return {k:evidence[k] for k in ('version','route_reason','uncertainty','surviving_candidates','survivor_iou_gap')}


def apply_image_review(image,review):
    if not review:return
    image['image_review']=review
    if review['status']=='pending':
        image['flags']['current_pending']=True
        image['flags']['image_hold']=True
        image['notes'].append(f"人工确认待定（{review['date']}）：{review['reason']}")


def apply_new_image_difficulty(document,decisions):
    images={r['image_id']:r for r in document['images']}
    for decision in decisions:
        image=images[decision['image_id']]
        admitted=bool((image.get('new_batch') or {}).get('admitted'))
        image['difficulty']=dict(label=decision['difficulty'],qualifier=decision['qualifier'],exclusion='' if admitted else '新增标注尚未纳入分析',question='')
        image['difficulty_decision']=decision
        image['notes'].append(f"人工难度裁定（{decision['date']}）：{decision['difficulty']}（{decision['qualifier']}）；"+('新增作答已纳库存，质量按共同评分与用途限制展示。' if admitted else '新增标注仍待纳入分析。'))


def attach_new_batch(document, batch):
    by_id = {image['image_id']: image for image in document['images']}
    admitted=set(document.get('admitted_source_ids',[]))
    batch_records=batch.get('records',[])
    code_map = {}
    for row in read_csv(ROOT / 'research/same_room/same_room_b8l2_v6_20261016/relation_coverage.csv'):
        for side in ('a', 'b'):
            code_map[row['image_' + side]] = row['code_' + side]
    for row in batch['images']:
        image_id = row['image_id']
        if image_id not in by_id:
            thumb = f'data/mp3d_layout/img_v/{image_id}.jpg'
            originals = [ROOT / f'data/mp3d_layout/{split}/img/{image_id}.png' for split in ('train', 'valid', 'test') if (ROOT / f'data/mp3d_layout/{split}/img/{image_id}.png').is_file()]
            assert len(originals) == 1 and (ROOT / thumb).is_file(), image_id
            image = dict(image_id=image_id, image_code=code_map.get(image_id, image_id), building_id=image_id.split('_')[0], thumbnail_path=thumb, original_path=originals[0].relative_to(ROOT).as_posix(), thumbnail_url=f'/photo/{quote(image_id)}?kind=thumb', original_url=f'/photo/{quote(image_id)}?kind=original', difficulty=dict(label='未评定', exclusion='尚未纳入分析', question=''), scene=scene_info(dict(scene='未接入',doorway_status='not_recorded',oos_subtype='not_recorded')), counts={key: 0 for key in document['images'][0]['counts']}, flags={key: False for key in document['images'][0]['flags']}, quality_groups=[], spaces=[], multiple_spaces=False, space_notice='新图尚未纳入分析，目标空间及参考尚未接入', notes=['仅新增待纳入；不属于原259图统计口径', '新增批次只登记人数与份数；标注几何尚未接入此详情'], annotations=[], references=[], new_batch_only=True)
            document['images'].append(image)
            by_id[image_id] = image
        source_ids={r['source_id'] for r in batch_records if r['image_id']==image_id}
        image_admitted=bool(source_ids) and source_ids<=admitted
        if source_ids & admitted and not image_admitted: raise ValueError('partially_admitted_gallery_image')
        annotations=[a for a in by_id[image_id].get('annotations',[]) if a.get('new_batch')]
        scored=sum(a['calculation_status']=='full_computed' for a in annotations)
        qualified=sum(a['quality_usable'] for a in annotations)
        floor_only=sum(a['calculation_status']=='floor_only_computed' for a in annotations)
        by_id[image_id]['new_batch'] = dict(records=row['n_submitted_records'], people=row['n_people'], raw_records=row['n_raw_records'], admitted=image_admitted,
            scored_records=scored,quality_records=qualified,floor_only_records=floor_only,full_restricted_records=scored-qualified,
            limited_records=row['n_submitted_records']-qualified if image_admitted else row['n_submitted_records'],
            note=f'新增批次来源标记；已计入当前库存，不重复加人数或份数；完整分{scored}份，质量可用{qualified}份；仅底面{floor_only}份、完整但用途受限{scored-qualified}份' if image_admitted else '新增中文标注，暂不纳入分析；人数为新批源账号去重，与正式库存分开；身份及审核证据见接入台账')
    document['summary'].update(display_images=len(document['images']), new_batch_images=batch['checks']['image_count'], new_batch_records=batch['checks']['submitted_records'], new_batch_only_images=sum(bool(i.get('new_batch_only')) for i in document['images']),new_batch_admitted_records=len(admitted))
    for field in ('scored_records','quality_records','limited_records','floor_only_records','full_restricted_records'):
        document['summary']['new_batch_'+field]=sum(i['new_batch'][field] for i in document['images'] if i.get('new_batch') and i['new_batch']['admitted'])
    document['images'].sort(key=lambda image: image['image_code'])


def build(bundle=None,inventory=None):
    inventory = read_json(ROOT / 'research/statistics/annotation_counts_20261017/tables.json') if inventory is None else inventory
    image_reviews=load_image_review_decisions()
    bundle=load_current_bundle() if bundle is None else bundle
    context=load_scored_context(bundle)
    admitted_objects={r['object_id'] for r in bundle.get('batch_admission',{}).get('records',[])}
    scores = {r['object_id']: r for r in context['quality_records']}
    bindings = {r['object_id']: r for r in context['binding_records']}
    votes = {r['object_id']: r for key in ('retained_annotations', 'removed_annotations') for r in inventory[key]}
    objects = {r['object_id']: r for r in bundle['data']['objects'] if r['object_kind'] == 'annotation'}
    assert objects.keys() == votes.keys() == scores.keys() == bindings.keys()
    refs = defaultdict(list)
    catalog = context['reference_catalog']
    for ref in catalog:
        refs[ref['image_id']].append(ref)
    difficulty = context['difficulty_records']
    difficulty = {r.get('image_id', r.get('image')): r for r in difficulty}
    images = []
    for count in inventory['image_counts']:
        image_id = count['image_id']
        original = Path(difficulty[image_id]['photo']).resolve().relative_to(ROOT).as_posix()
        thumb = f'data/mp3d_layout/img_v/{image_id}.jpg'
        assert (ROOT / original).is_file() and (ROOT / thumb).is_file(), image_id
        references = []
        labels = {}
        for index, ref in enumerate(refs[image_id], 1):
            role = ref['role']
            title = {'selected_gt': '原GT', 'original_GT_version': '历史GT', 'confirmed_scope': '确认空间', 'confirmed_space_candidate': '确认候选空间', 'user_revised_gt': '修订GT', 'manual_GT_version': '历史人工参考'}.get(role, role)
            scope_label=ref.get('space_label','')
            label = f'{index} · {title}' + (f' · 范围{scope_label}' if scope_label else '') + ('（当前）' if ref['current_target'] else '')
            labels[ref['target_id']] = label
            references.append(dict(target_id=ref['target_id'], label=label, current=ref['current_target'], full_reference_available=ref['full_reference_available'], points=ref.get('points_1024x512'), floor=ref.get('floor_xz_h'), **scope_metadata(ref)))
        annotations = []
        for vote in (r for r in votes.values() if r['image_id'] == image_id):
            oid = vote['object_id']; obj = objects[oid]; score = scores[oid]; binding = bindings[oid]
            unique = true(binding['target_binding_unique'])
            points = obj.get('points_1024x512')
            annotations.append(dict(object_id=oid, worker_id=vote['worker_id'], condition=vote['condition'], retained=true(vote['pool_vote_eligible']), removal_group=vote.get('removal_group', ''), quality_usable=true(score['quality_usable']) and score['condition'] != 'oos', quality=quality_values(score),
                diagnostic_B8L2=float(score['diagnostic_B8L2']) if score.get('diagnostic_B8L2') not in ('',None) else None,
                diagnostic_D10=float(score['diagnostic_D10']) if score.get('diagnostic_D10') not in ('',None) else None,
                quality_exclusion_reasons=json.loads(score['quality_exclusion_reasons']) if isinstance(score['quality_exclusion_reasons'],str) else score['quality_exclusion_reasons'],
                binding_status=binding['binding_status'],routing=routing_info(binding),
                new_batch=oid in admitted_objects, calculation_status=score['calculation_status'], target_id=binding['chosen_target_id'] if unique else None, target_binding_unique=unique, points=points, raw_points=obj.get('original_export_points'), points_basis='已预处理上下点对' if points else '原始散点；配对与环序未确认', geometry_status=obj.get('geometry', {}).get('status', ''), exclusion_reasons=vote['pool_vote_exclusion_reasons']))
        spaces = []
        for ref in references:
            bound = [r for r in annotations if r['target_id'] == ref['target_id']]
            spaces.append(dict(target_id=ref['target_id'], label=ref['label'], current=ref['current'], reference_full_available=ref['full_reference_available'], n_bound_retained=sum(r['retained'] for r in bound), n_bound_raw=len(bound), **{key:ref[key] for key in ('user_candidate','candidate_id','scope_label','note')}))
        pending = count['n_retained_target_pending']
        notices = []
        if len(spaces) > 1:
            notices.append('存在多个空间/参考版本；质量按绑定版本分列，版本不同不一定代表空间范围不同')
        if pending:
            notices.append(f'{pending}份保留作答的目标空间待绑定')
        if any(a['routing'] for a in annotations):
            notices.append('部分作答按局部结构或底面接近归属；保留几何路由的不确定性，不代表人工确认其真实意图或质量合格')
        if not count['reference_full_available']:
            notices.append('当前空间缺完整三维参考，未补造未知顶界')
        c = dict(retained_people=count['n_retained_workers'], retained_records=count['n_retained_records'], removed_records=count['n_removed_records'], manual_people=count['n_manual_workers'], semi_people=count['n_semi_workers'], oos_people=count['n_oos_workers'], user_excluded_records=count['n_user_excluded_records'], pending_records=count['n_pending_records'], nonindependent_records=count['n_nonindependent_or_other_hold_records'], **worker_counts(annotations))
        flags = dict(gt_problem=count['gt_reference_problem'], gt_uncertain=count['gt_uncertainty'], gt_detail_omission=count['gt_detail_omission'], image_hold=count['image_analysis_hold'], current_pending=count['current_issue_pending'], applicability_pending=count['applicability_pending'], oos=count['oos_quality_diagnostic_only'], no_retained=count['no_retained_annotations'])
        notes = [str(count[k]) for k in ('image_comment', 'difficulty_question', 'later_reference_status') if count[k]]
        notes += count['image_hold_reasons'] + count['gt_issue_types']
        prior=difficulty[image_id].get('external_review') or {}
        if prior.get('scope'):
            notes.append(f"既有人工复核回执（{prior.get('updated_at','日期未记录')}）：{prior['scope']}；该历史备注不自动等同当前整图排除。")
        images.append(dict(image_id=image_id, image_code=count['image_code'], building_id=count['building_id'], thumbnail_path=thumb, original_path=original, thumbnail_url=f'/photo/{quote(image_id)}?kind=thumb', original_url=f'/photo/{quote(image_id)}?kind=original', difficulty=dict(label=count['difficulty_class'], exclusion=count['difficulty_exclusion'], question=count['difficulty_question']), scene=scene_info(count,difficulty[image_id]), counts=c, quality_groups=quality_groups(annotations, labels), spaces=spaces, multiple_spaces=len(spaces) > 1, space_notice='；'.join(notices), flags=flags, notes=notes, annotations=annotations, references=references, new_batch=None))
    for image in images:apply_image_review(image,image_reviews.get(image['image_id']))
    summary = dict(images=len(images), raw_records=len(objects), retained_records=sum(i['counts']['retained_records'] for i in images), retained_people=len({r['worker_id'] for i in images for r in i['annotations'] if r['retained']}), removed_records=sum(i['counts']['removed_records'] for i in images), quality_records=sum(g['n'] for i in images for g in i['quality_groups']))
    assert summary['raw_records']==summary['retained_records']+summary['removed_records']
    assert summary['images']==len({o['image_id'] for o in objects.values()})
    assert summary['quality_records']==sum(true(r['quality_usable']) and r['condition']!='oos' for r in scores.values())
    summary.update(user_scope_images=sum(any(r['user_candidate'] for r in i['references']) for i in images),user_scope_candidates=sum(r['user_candidate'] for i in images for r in i['references']))
    return dict(version='annotation_gallery_20261017_v2', generated_at=datetime.now(timezone.utc).isoformat(), summary=summary, images=images,admitted_source_ids=context['admitted_source_ids'],batch_admission_version=context['admission_version'],
        score_context_version=context['score_context_version'],primary_metric='B8L2',parallel_metric='D10',historical_metrics=['WQ','A10'])


def main():
    document = build()
    attach_new_batch(document, read_json(OUT / 'new_batch.json'))
    decisions=read_json(ROOT/'research/data/image_review_decisions_20261017/decisions.json')
    apply_new_image_difficulty(document,decisions['new_batch_difficulty_decisions'])
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'gallery.json').write_text(json.dumps(document, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    print(json.dumps(document['summary'], ensure_ascii=False))


if __name__ == '__main__':
    main()
