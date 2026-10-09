"""GT结构粗分类：固定点对数与声明实心墙自遮挡；场景及参考例外独立。"""
from collections import Counter
import json

from .research_artifact_io import ROOT, read_csv, write_csv, write_json
from .difficulty_features_20261009 import FEATURE_SOURCE
from .difficulty_strata_20261009 import INVENTORY, REVIEWS, EVIDENCE, merge_scene_reviews, classify_scene
from .gt_order_visibility_20261009 import audit_object
from tools.thesis_main.data_prep.consolidate_research_input import load_current_bundle

OUT = ROOT / 'analysis_results/objective_difficulty_20261009/structure_classification'
BASE = OUT.parent
SCHEMA = 'difficulty_gt_structure_20261009_v1'


def classify_structure(pair_count, geometry_status, hidden_count):
    if not isinstance(pair_count, int) or isinstance(pair_count, bool) or pair_count < 4:
        return '待定', 'pair_count_outside_rule'
    if geometry_status != 'valid_camera_inside':
        return '待定', geometry_status
    if hidden_count is None:
        return '待定', 'occlusion_unavailable'
    if not isinstance(hidden_count, int) or not 0 <= hidden_count <= pair_count:
        raise ValueError('invalid_hidden_count')
    return ('困难' if hidden_count else '简单' if pair_count == 4 else '中等'), ''


def apply_exception(raw_class, geometry_reason, exception):
    if exception:
        status = exception['status']
        if status not in ('confirmed_unannotatable', 'user_analysis_hold', 'reference_pending'):
            raise ValueError('unknown_applicability_exception:' + status)
        return ('不适用' if status == 'confirmed_unannotatable' else '待定'), status, exception['reason']
    if geometry_reason:
        return '待定', 'geometry_pending', geometry_reason
    return raw_class, 'applicable', ''


def select_reference(image, objects, prefer_revision):
    refs = image['references']
    key = 'gt_manual_revision' if prefer_revision and 'gt_manual_revision' in refs else 'gt_original'
    obj = objects[refs[key]]
    if obj['object_kind'] != key:
        raise ValueError('gt_reference_kind_mismatch:' + refs[key])
    return obj


def image_review_evidence(objects):
    evidence = []
    for obj in objects:
        review = obj.get('review_evidence', {})
        for key in ('semantic_image_evidence', 'coverage_review'):
            record = review.get(key)
            if record:
                entry = dict(evidence_kind=key, record=record)
                if not any(e['evidence_kind'] == key and e['record'] == record for e in evidence):
                    evidence.append(dict(entry, source_object_id=obj['object_id'],
                        bundle_source='analysis_results/research_input_20260929/preprocessed_source.json'))
        comment = review.get('image_traits', {}).get('comment')
        if comment and not any(e['record'].get('comment') == comment for e in evidence):
            evidence.append(dict(evidence_kind='image_traits_comment', record=dict(comment=comment),
                                 source_object_id=obj['object_id'],
                                 bundle_source='analysis_results/research_input_20260929/preprocessed_source.json'))
    return evidence


def explicit_exception(evidence):
    for entry in evidence:
        if entry['evidence_kind'] != 'semantic_image_evidence':
            continue
        record = entry['record']
        if (record.get('semantic_status') == 'all_analysis_hold_by_user'
                or record.get('reason') == '本次图片补审；pRb-16按原话暂缓全部分析'):
            return dict(status='user_analysis_hold', reason=record.get('summary') or record['reason'],
                        source=record['source'], source_object_id=entry['source_object_id'],
                        evidence_type='current_resolved_semantic_decision', record=record)
    return None


def scene_evidence(row, evidence):
    stratum = classify_scene(row)
    nonorthogonal = row['stable_nonorthogonal']
    tags = sorted({tag for e in evidence for tag in e['record'].get('tags', [])})
    return dict(scene_stratum=stratum,
        scene_review_status='explicit_not_oos_and_no_doorway' if stratum == 'clear' else
                            'unflagged_not_certified_normal' if stratum == 'unflagged' else
                            'special_or_pending_keep_source_status',
        oos_status=row['oos_status'], oos_source=row['oos_source'],
        oos_subtype='nonorthogonal_annotatable' if nonorthogonal else
                    'not_recorded' if row['oos_status'] == 'not_recorded' else
                    'not_oos' if row['oos_status'] == 'not_oos' else 'subtype_not_resolved',
        oos_subtype_source='corrected_inventory.stable_nonorthogonal' if nonorthogonal else '',
        doorway_status=row['doorway_status'], doorway_source=row['doorway_source'],
        doorway_annotation_source=row['doorway_annotation_source'],
        annotatability_status='nonorthogonal_annotatable' if nonorthogonal else
                             'doorway_annotatable' if row['doorway_status'] == 'annotatable' else
                             'not_explicitly_resolved',
        stable_nonorthogonal=nonorthogonal, source_image_tags=tags,
        latest_scene_note=row['latest_scene_note'])


def classify_reference(image, obj, scene, evidence, exception):
    try:
        geometry = audit_object(obj, image['population'])
    except ValueError as error:
        geometry = dict(pair_count=len(obj['points_1024x512']) // 2,
                        geometry_status=str(error), hidden_count=None,
                        hidden_vertices_1based=None, visibility=[])
    raw_class, geometry_reason = classify_structure(geometry['pair_count'], geometry['geometry_status'],
                                                   geometry['hidden_count'])
    label, status, reason = apply_exception(raw_class, geometry_reason, exception)
    blockers = [v for v in geometry['visibility'] if v['blockers']]
    return dict(image_id=image['image_id'], image=image['image_code'],
        building=image['building_id'], room=image['room_id'], population=image['population'],
        gt_object_id=obj['object_id'], gt_source=obj['source'], gt_version=obj['gt_version'],
        gt_order_status=obj['order_status'], gt_ring_confirmed=obj['ring_confirmed'],
        ordered_source_pair_indices=obj['ordered_source_pair_indices'],
        selected_gt_pair_count=geometry['pair_count'], geometry_status=geometry['geometry_status'],
        structural_occlusion=None if geometry['hidden_count'] is None else geometry['hidden_count'] > 0,
        hidden_pair_count=geometry['hidden_count'], hidden_pairs_1based=geometry['hidden_vertices_1based'],
        blocker_evidence=blockers, x_order_class=geometry.get('x_order_class'),
        raw_structure_class=raw_class, coarse_class=label, applicability_status=status,
        pending_or_inapplicable_reason=reason,
        exception_source=exception['source'] if exception else '',
        reference_evidence_status='reference_version_wording_unresolved_source_files_identified'
            if any(e['record'].get('semantic_status') == 'reference_version_wording_unresolved' for e in evidence)
            else 'source_identified_no_new_semantic_review',
        scene=scene, gt_evidence=image.get('gt_evidence', []), image_review_evidence=evidence)


def attach_auxiliary(rows):
    old_path = ROOT / FEATURE_SOURCE
    old = {r['image_id']: r for r in read_csv(old_path)} if old_path.exists() else {}
    expanded_path = BASE / 'd_model_expansion/supplement.csv'
    expanded = {r['image_id']: r for r in read_csv(expanded_path)} if expanded_path.exists() else {}
    historical_path = BASE / 'stratified/features_and_scores.csv'
    historical = {r['image_id']: r for r in read_csv(historical_path)} if historical_path.exists() else {}
    dino_path = BASE / 'dino_probe/features.csv'
    dino = {r['image_id']: r for r in read_csv(dino_path)} if dino_path.exists() else {}
    if set(old) & set(expanded):
        raise ValueError('frozen_supplement_must_not_replace_existing_values')
    for row in rows:
        iid = row['image_id']
        model = expanded.get(iid, old.get(iid))
        for key in ('d_model_feat_static', 'd_model_feat_local_max_static', 'static_model_risk_score'):
            row[key] = float(model[key]) if model and model[key] != '' else None
        row['d_model_source'] = str(expanded_path.relative_to(ROOT)).replace('\\', '/') if iid in expanded else FEATURE_SOURCE if iid in old else ''
        row['d_model_status'] = 'frozen_expansion' if iid in expanded else 'historical_frozen' if iid in old else 'missing'
        h = historical.get(iid)
        for key in ('hohonet_offline_pair_count', 'bilayout_floor_gap'):
            row[key] = float(h[key]) if h and h[key] else None
        row['auxiliary_history_status'] = 'historical_available' if h else 'missing'
        row['auxiliary_history_source'] = 'analysis_results/objective_difficulty_20261009/stratified/features_and_scores.csv' if h else ''
        row['dino_source'] = 'analysis_results/objective_difficulty_20261009/dino_probe/features.csv' if iid in dino else ''
        row['dino_horizontal_patch_dispersion'] = float(dino[iid]['dino_horizontal_patch_dispersion']) if iid in dino else None
        row['dino_status'] = 'historical_cached' if iid in dino else 'missing'
        row['auxiliary_role'] = 'diagnostic_only_not_used_in_classification'


def flat(row):
    return {k: json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v
            for k, v in dict(row, **row['scene']).items() if k != 'scene'}


def summary(rows):
    return dict(images=len(rows), buildings=len({r['building'] for r in rows}),
        rooms=len({r['room'] for r in rows if r['room']}),
        room_unknown_images=sum(not r['room'] for r in rows),
        raw_structure_classes=dict(Counter(r['raw_structure_class'] for r in rows)),
        delivered_classes=dict(Counter(r['coarse_class'] for r in rows)),
        pair_counts=dict(Counter(r['selected_gt_pair_count'] for r in rows)),
        structural_occlusion=sum(r['structural_occlusion'] is True for r in rows),
        gt_ring_confirmed=sum(r['gt_ring_confirmed'] for r in rows),
        applicability=dict(Counter(r['applicability_status'] for r in rows)))


def run():
    bundle = load_current_bundle()
    images = bundle['data']['images']
    by_image = {im['image_id']: im for im in images}
    if len(by_image) != len(images):
        raise ValueError('duplicate_image_identity')
    objects = {o['object_id']: o for o in bundle['data']['objects']}
    if len(objects) != len(bundle['data']['objects']):
        raise ValueError('duplicate_object_identity')
    image_objects = {iid: [] for iid in by_image}
    for obj in objects.values():
        image_objects[obj['image_id']].append(obj)
    inventory = json.loads((ROOT / INVENTORY).read_text(encoding='utf-8'))
    axes, scene_changes = merge_scene_reviews({r['image']: r for r in inventory['images']},
        [(p, json.loads((ROOT / p).read_text(encoding='utf-8-sig'))) for p in REVIEWS])
    selected, original, references, exceptions = [], [], [], []
    for im in sorted(images, key=lambda r: r['image_code']):
        evidence = image_review_evidence(image_objects[im['image_id']])
        exception = explicit_exception(evidence)
        if exception:
            exceptions.append(dict(image_id=im['image_id'], image=im['image_code'], **exception))
        if im['population'] == 'manual_gt_reference_only':
            scene = scene_evidence(dict(oos_status='not_recorded', doorway_status='not_recorded',
                oos_source='', doorway_source='', doorway_annotation_source='',
                stable_nonorthogonal=False, latest_scene_note=''), evidence)
            references.append(classify_reference(im, select_reference(im, objects, True), scene, evidence, exception))
        elif im['population'] == 'research_annotation_image':
            axis = axes[im['image_code']]
            if axis['image_id'] != im['image_id']:
                raise ValueError('scene_identity_mismatch:' + im['image_code'])
            scene = scene_evidence(axis, evidence)
            for key in EVIDENCE:
                scene[key] = axis[key]
            selected.append(classify_reference(im, select_reference(im, objects, True), scene, evidence, exception))
            original.append(classify_reference(im, select_reference(im, objects, False), scene, evidence, exception))
        else:
            raise ValueError('unexpected_population:' + im['population'])
    attach_auxiliary(selected)
    sensitivity = []
    for before, after in zip(original, selected):
        if before['image_id'] != after['image_id']:
            raise ValueError('sensitivity_identity_mismatch')
        if before['gt_object_id'] == after['gt_object_id']:
            continue
        sensitivity.append(dict(image_id=after['image_id'], image=after['image'],
            original_gt_object_id=before['gt_object_id'], selected_gt_object_id=after['gt_object_id'],
            original_gt_source=before['gt_source'], selected_gt_source=after['gt_source'],
            original_pair_count=before['selected_gt_pair_count'], selected_pair_count=after['selected_gt_pair_count'],
            pair_count_changed=before['selected_gt_pair_count'] != after['selected_gt_pair_count'],
            original_hidden_count=before['hidden_pair_count'], selected_hidden_count=after['hidden_pair_count'],
            original_raw_class=before['raw_structure_class'], selected_raw_class=after['raw_structure_class'],
            raw_class_changed=before['raw_structure_class'] != after['raw_structure_class'],
            original_delivered_class=before['coarse_class'], selected_delivered_class=after['coarse_class'],
            change_interpretation='reference_coordinates_scope_detail_and_order_may_change_not_an_order_only_intervention'))
    results = dict(schema=SCHEMA, selected=summary(selected), original=summary(original),
        reference_only=summary(references), revised_research_images=len(sensitivity),
        changed_raw_classes=sum(r['raw_class_changed'] for r in sensitivity),
        changed_pair_counts=sum(r['pair_count_changed'] for r in sensitivity),
        occlusion_to_none=[r['image'] for r in sensitivity if r['original_hidden_count'] > 0 and r['selected_hidden_count'] == 0],
        auxiliary_global_available=sum(r['d_model_feat_static'] is not None for r in selected))
    OUT.mkdir(parents=True, exist_ok=True)
    for name, rows in (('images', selected), ('original_gt_sensitivity', original),
                       ('reference_only', references), ('gt_version_changes', sensitivity)):
        write_csv(OUT / (name + '.csv'), [flat(r) if 'scene' in r else r for r in rows])
    write_json(OUT / 'images.json', selected)
    write_json(OUT / 'exceptions.json', exceptions)
    write_json(OUT / 'scene_review_changes.json', scene_changes)
    write_json(OUT / 'summary.json', results)
    write_json(OUT / 'field_contract.json', dict(schema=SCHEMA,
        input='analysis_results/research_input_20260929/manifest.json via load_current_bundle()',
        scene_sources=[INVENTORY, *REVIEWS],
        population='one row per research image; manual_gt_reference_only separately',
        main_table_columns=list(flat(selected[0])),
        selected_gt_pair_count='fixed reference count in the declared view of each file; original_gt_sensitivity.csv uses original GT count',
        reference_policy='view only: manual revision preferred, otherwise original; original sensitivity separate; formal GT policy unchanged',
        rule='4 pairs + no structural occlusion => 简单; >4 + none => 中等; any structural occlusion => 困难; invalid/missing geometry or <4 pairs => 待定',
        geometry='reuse gt_order_visibility_20261009.audit_object on live input; declared source ring, no sorting/repair; camera h=1, opaque solid vertical wall assumption',
        structural_occlusion='hidden_count > 0 from GT floor ray test: transverse intersection with nonincident edge interior before target; not RGB visibility or full-height occlusion. Endpoint/grazing contacts do not count.',
        hidden_pair_count='number of GT floor vertices meeting this ray test; not backward edges, full-height hidden pairs or physically unseen photographed corners',
        raw_structure_class='working GT structure class before applicability exceptions; not validated human difficulty',
        coarse_class='same working class unless explicit source-backed hold/reference pending => 待定 or confirmed unannotatable => 不适用',
        scene='OOS, doorway, nonorthogonal and annotatability remain independent; not_recorded does not certify normal or block geometry classification',
        indices='one-based final pair/edge positions; source pair indices remain zero-based',
        evidence='image-level review source preserved; annotation scope/comment/error marks do not automatically exclude',
        auxiliary='global, local and sqrt(global²+local²) independent frozen model signals; no involvement in structural rule; historical subjective labels not read for classification',
        limitations=['GT version, scope and detail choices affect grouping', 'opaque walls ignore openings, glass, furniture and RGB boundary visibility',
                     f"{results['selected']['images']-results['selected']['gt_ring_confirmed']} selected original rings unconfirmed; no full per-image human reannotation", 'not intrinsic image noise or causal worker/image decomposition']))
    write_report(results, sensitivity, exceptions)
    print(json.dumps(results, ensure_ascii=True))
    return results


def write_report(results, changes, exceptions):
    s, o = results['selected'], results['original']
    lines = ['# 基于GT结构的粗分类：当前交付', '',
        '2026-10-09。仅使用固定GT点对数及声明实心墙结构自遮挡；这是已认可的工作粗分，不是已验证的人类难度或固有数据噪声。', '',
        '规则：4点对且无结构遮挡为简单；多于4点对且无结构遮挡为中等；存在结构遮挡为困难。无效几何／异常点数为待定，明确不可标为不适用，来源明确的用户暂停另列待定。', '',
        f"研究主表[images.csv](images.csv)完整{s['images']}图／{s['buildings']}建筑／{s['rooms']}已声明房间，{s['room_unknown_images']}图未记录房间，一图一行。修订优先查看，原GT[对照](original_gt_sensitivity.csv)独立保存；两份非研究GT参考另在[reference_only.csv](reference_only.csv)。正式GT评价政策及资格没有改变。", '',
        '|版本|原始结构简单|中等|困难|交付状态|', '|---|---:|---:|---:|---|',
        *[f"|{name}|{v['raw_structure_classes'].get('简单',0)}|{v['raw_structure_classes'].get('中等',0)}|{v['raw_structure_classes'].get('困难',0)}|{json.dumps(v['delivered_classes'],ensure_ascii=False)}|" for name,v in [('修订优先',s),('原GT',o)]], '',
        f"修订优先{s['gt_ring_confirmed']}份环序已有人工确认，其余{s['images']-s['gt_ring_confirmed']}份沿用原GT声明环。未知OOS／门洞不认证正常，也不阻塞几何粗分；非正交但可标与门洞可标性独立保留。现有GT错误、细节、范围标记不自动导致不适用。", '',
        '## 参考版本与例外', '',
        f"{len(changes)}张研究图有修订GT；{results['changed_pair_counts']}图点对数改变，{results['changed_raw_classes']}图结构类改变。10图有遮挡→无遮挡，全部同时改变点对数；不能写成‘只修正环序消除了遮挡’，不能据此判原GT环错。完整变化见[gt_version_changes.csv](gt_version_changes.csv)，保留坐标／范围／细节／连接共同改变的解释。", '',
        '|图片|原点对→修订点对|原结构类→修订结构类|', '|---|---|---|',
        *[f"|{r['image']}|{r['original_pair_count']}→{r['selected_pair_count']}|{r['original_raw_class']}→{r['selected_raw_class']}|" for r in changes if r['raw_class_changed']], '',
        '来源明确的例外见[exceptions.json](exceptions.json)；暂停研究不等于照片物理不可标。jtc-11暂停措辞是当前已裁决语义摘要，不冒称原始评论逐字原话；pRb-16保留原暂停评论。没有完整图级证据时不猜测不可标。yq-04旧参考措辞未决与已明确的源文件分别保存，不阻塞粗分；uNb-51外侧玻璃目标不可标与后来只标内侧的裁决均保留，不判整图不适用。', '',
        *[f"- {e['image']}：{e['status']}；{e['reason']}；来源`{e['source']}`。" for e in exceptions], '',
        '## 辅助模型及解释边界', '',
        f"当前主表global冻结d_model覆盖{results['auxiliary_global_available']}/{s['images']}图。global、local及其平方和开方分别保存；旧冻结补缺和有限比较见[d_model_expansion](../d_model_expansion/REPORT.md)。模型量不参与结构判类；缺失状态显式保存。旧risk_design_score_A另有组合定义，不能与global单项混称。DINO及布局模型历史结果保持独立。", '',
        'structural_occlusion／hidden_pair_count只定义为GT声明底面的横穿遮挡；全高度是否被挡是另外一个条件三维量。旧审计中本批259图的底面遮挡集合与全高度墙遮挡集合一致，定义仍不混用。实心不透明墙假设在玻璃、门洞、虚拟停止边处可能不成立。家具遮挡、边界弱对比和图像可见性尚未全量核查，简单标签也不证明图片容易。旧12图事实试点可用于之后核查，已取消作为全量粗分类的前置条件。GT版本改变结构类，不能把类别用于反向调共识或强制得到预期曲线。', '',
        '复算：`python -m tools.thesis_main.analysis.difficulty_structure_20261009`。字段、输入、索引及适用性含义见[field_contract.json](field_contract.json)。', '',
        '## 验证与交接', '',
        '边界测试覆盖结构规则、无效几何／异常点数、来源明确暂停、原／修订视图与未知房间；旧模型测试覆盖固定距离、复现门控和缺失／无效输入。数量、唯一身份、518行原／修订几何对照、163份原模型数值未变及文档引用检查见[verification.json](verification.json)。', '',
        '新增结构粗分与冻结补缺脚本／测试，两目录保存派生表和字段合同；现有难度入口、统一研究模型、数据说明、README索引及项目地图已同步。原导出、GT源坐标、环、资格、票权、正式GT政策和规范合同均未修改。未运行无关全仓测试、全量RGB可见性人审或checkpoint训练／选参历史审计；未产生临时截图。下一步可由后续任务按本表固定结构条件关联共识曲线，保留原GT敏感性及未知状态。', '']
    (OUT / 'REPORT.md').write_text('\n'.join(lines), encoding='utf-8')


if __name__ == '__main__':
    run()
