"""冻结首轮分数，补齐特殊场景独立轴、适用性及留建筑不一致案例。"""
from collections import Counter
import json

import numpy as np

from .research_artifact_io import ROOT, read_csv, write_csv, write_json
from .difficulty_features_20261009 import extract_features, SCORE_FEATURES
from .difficulty_score_20261009 import score_features, load_comparison_metadata, rank_metrics, LABELS

PARENT = ROOT / 'analysis_results/objective_difficulty_20261009'
OUT = PARENT / 'stratified'
INVENTORY = 'analysis_results/review_source_audit_20261004/corrected_inventory/input.json'
REVIEWS = ('analysis_results/difficulty_consensus_20261006/user_review.json',
           'analysis_results/difficulty_full_20261007/updated/human_review.json')
EVIDENCE = ('stable_nonorthogonal', 'scope_explicit_tag', 'scope_existing_ledger',
            'scope_comment_candidate', 'gt_substantive_error_mark',
            'gt_detail_omission_mark', 'gt_uncertainty_explicit_tag', 'review_coverage')


def merge_scene_reviews(original, payloads):
    result = {k: dict(v, oos_source=INVENTORY, doorway_source=INVENTORY,
                      doorway_annotation_source=INVENTORY if v['doorway_status'] in ('difficult', 'annotatable') else '',
                      latest_scene_note='') for k, v in original.items()}
    changes = []
    for source, payload in payloads:
        for decision in payload['decisions']:
            if not decision['updated_at']:
                continue
            code = decision['image_code']
            row = result[code]
            if decision['image_id'] != row['image_id']:
                raise ValueError('scene_review_identity_mismatch:' + code)
            for axis, key in (('oos_status', 'oos'), ('doorway_status', 'doorway')):
                value = decision[key]
                if not value:
                    continue
                if value not in ('是', '否', '不确定'):
                    raise ValueError('unknown_scene_review_value:' + code + ':' + key)
                if axis == 'oos_status':
                    new = {'是': 'confirmed', '否': 'not_oos', '不确定': 'pending'}[value]
                elif value == '是':
                    # “是门洞”本身没有声明困难或不可标；已有可标性判断保留。
                    new = row[axis] if row[axis] in ('difficult', 'annotatable') else 'present_unknown'
                else:
                    new = {'否': 'none', '不确定': 'pending'}[value]
                if new != row[axis]:
                    changes.append(dict(image=code, axis=axis, previous=row[axis], current=new,
                                        source=source, updated_at=decision['updated_at']))
                row[axis] = new
                row[key + '_source'] = source
                if axis == 'doorway_status' and new not in ('difficult', 'annotatable'):
                    row['doorway_annotation_source'] = ''
            row['latest_scene_note'] = decision['note']
    return result, changes


def classify_scene(row):
    oos, door = row['oos_status'], row['doorway_status']
    if oos not in ('confirmed', 'pending', 'not_oos', 'not_recorded'):
        raise ValueError('unknown_oos_status:' + oos)
    if door not in ('difficult', 'annotatable', 'present_unknown', 'pending', 'none', 'not_recorded'):
        raise ValueError('unknown_doorway_status:' + door)
    present = door in ('difficult', 'annotatable', 'present_unknown')
    if oos == 'confirmed':
        return 'oos_and_doorway' if present else 'oos'
    if oos == 'pending':
        return 'oos_pending'
    if present:
        return 'doorway_' + door
    if door == 'pending':
        return 'doorway_pending'
    return 'clear' if (oos, door) == ('not_oos', 'none') else 'unflagged'


def attach_applicability(rows):
    output = []
    for row in rows:
        stratum = classify_scene(row)
        ordinary = stratum in ('clear', 'unflagged')
        output.append(dict(row, scene_stratum=stratum,
            scene_review_status='explicit_not_oos_and_no_doorway' if stratum == 'clear' else
                                'unflagged_not_certified_normal' if stratum == 'unflagged' else
                                'special_or_pending_keep_original_annotatability',
            calibration_panel='ordinary_historical_panel' if ordinary else 'special_diagnostic_only',
            score_interpretation='ordinary_model_proxy_not_validated_intrinsic_difficulty' if ordinary else
                                 'special_model_proxy_not_validated_human_difficulty',
            subjective_calibrated_candidate_score=row['subjective_calibrated_candidate_score'] if ordinary else None,
            candidate_status='ordinary_subjective_candidate_not_deployed' if ordinary else
                             'not_calibrated_for_this_stratum_not_unannotatable'))
    return output


def strata_summary(rows, holdout):
    groups = [('scene_stratum', k, [r for r in rows if r['scene_stratum'] == k])
              for k in sorted({r['scene_stratum'] for r in rows})]
    for axis in ('oos_status', 'doorway_status'):
        groups += [(axis, k, [r for r in rows if r[axis] == k]) for k in sorted({r[axis] for r in rows})]
    summary, metrics = [], []
    for axis, group, members in groups:
        complete = [r for r in members if r['baseline_score'] is not None]
        counts = dict(axis=axis, group=group, images=len(members),
                      buildings=len({r['building'] for r in members}), complete=len(complete),
                      labelled_complete=sum(r['subjective_label'] in LABELS for r in complete))
        for feature in SCORE_FEATURES:
            for panel, subset in (('feature_available', members), ('common_complete', complete)):
                values = [r[feature] for r in subset if r[feature] is not None]
                q = np.quantile(values, [.25, .5, .75]).tolist() if values else [None]*3
                summary.append(dict(counts, feature=feature, panel=panel, available=len(values),
                                    q25=q[0], median=q[1], q75=q[2]))
        for panel in sorted({r['calibration_panel'] for r in members}):
            labelled = [r for r in complete if r['subjective_label'] in LABELS and r['calibration_panel'] == panel]
            ordinary = panel == 'ordinary_historical_panel'
            for field in ('baseline_score', 'calibrated_score') if ordinary else ('baseline_score',):
                if ordinary:
                    selected = [holdout[r['image']] for r in labelled]
                    scores = [r[field] for r in selected]
                    targets = [r['label'] for r in selected]
                else:
                    scores = [r['baseline_score'] for r in labelled]
                    targets = [LABELS[r['subjective_label']] for r in labelled]
                metrics.append(dict(axis=axis, group=group, score=field, evaluation_panel=panel,
                    **rank_metrics(scores, targets), labelled_buildings=len({r['building'] for r in labelled}),
                    evaluation='subset_of_historical_building_holdout_not_refit' if ordinary else
                               'special_descriptive_only_not_independent_validation'))
    return summary, metrics


def run():
    inventory = json.loads((ROOT/INVENTORY).read_text(encoding='utf-8'))
    original = {r['image']: r for r in inventory['images']}
    payloads = [(p, json.loads((ROOT/p).read_text(encoding='utf-8-sig'))) for p in REVIEWS]
    axes, changes = merge_scene_reviews(original, payloads)
    rows, complete = score_features(extract_features(), SCORE_FEATURES)
    metadata = load_comparison_metadata()
    parent = {r['image']: r for r in read_csv(PARENT/'features_and_scores.csv')}
    holdout = {r['image']: r for r in json.loads((PARENT/'holdout_predictions.json').read_text(encoding='utf-8'))}
    reference = json.loads((PARENT/'reference.json').read_text(encoding='utf-8'))
    frozen = {r['image']: r['values'] for r in reference['rows']}
    if set(complete) != set(frozen) or set(parent) != {r['image'] for r in rows}:
        raise ValueError('frozen_reference_inventory_changed_make_new_score_version')
    for row in rows:
        code = row['image']
        if code in complete and complete[code]['x'] != frozen[code]:
            raise ValueError('frozen_reference_feature_changed:' + code)
        old_score = float(parent[code]['baseline_score']) if parent[code]['baseline_score'] else None
        if row['baseline_score'] != old_score:
            raise ValueError('frozen_baseline_changed:' + code)
        row.update(metadata[code])
        row.update({k: axes[code][k] for k in ('oos_status', 'doorway_status', 'oos_source',
                    'doorway_source', 'doorway_annotation_source', 'latest_scene_note', *EVIDENCE)})
        candidate = parent[code]['subjective_calibrated_candidate_score']
        row['subjective_calibrated_candidate_score'] = float(candidate) if candidate else None
    rows = attach_applicability(rows)
    main = {r['image'] for r in rows if r['baseline_score'] is not None
            and r['calibration_panel'] == 'ordinary_historical_panel'}
    if main != set(holdout):
        raise ValueError('calibration_panel_changed_requires_new_building_holdout')
    by_image = {r['image']: r for r in rows}
    for code, prediction in holdout.items():
        if prediction['label'] != LABELS.get(by_image[code]['subjective_label']):
            raise ValueError('calibration_label_changed_requires_new_building_holdout:' + code)
    summaries, metrics = strata_summary(rows, holdout)
    review = []
    for code, prediction in holdout.items():
        if prediction['label'] is None:
            continue
        row = by_image[code]
        target = prediction['label']/2
        review.append(dict(image=code, building=row['building'], room=row['room'],
            scene_stratum=row['scene_stratum'], subjective_label=row['subjective_label'],
            subjective_source=row['subjective_source'], subjective_definition=row['subjective_definition'],
            oof_baseline=prediction['baseline_score'], oof_calibrated=prediction['calibrated_score'],
            baseline_residual=prediction['baseline_score']/100-target,
            calibrated_residual=prediction['calibrated_score']/100-target,
            baseline_absolute_residual=abs(prediction['baseline_score']/100-target),
            calibrated_absolute_residual=abs(prediction['calibrated_score']/100-target),
            **{k: row[k] for k in (*SCORE_FEATURES, *EVIDENCE)},
            use='仅核查概念和来源；不是新验证样本，不逐图改分或删图'))
    review.sort(key=lambda r: (-r['baseline_absolute_residual'], r['image']))
    special = [dict(r) for r in rows if r['calibration_panel'] != 'ordinary_historical_panel']
    OUT.mkdir(parents=True, exist_ok=True)
    csv_rows = [dict(r, provenance=json.dumps(r['provenance'], ensure_ascii=False, sort_keys=True)) for r in rows]
    write_csv(OUT/'features_and_scores.csv', csv_rows)
    write_csv(OUT/'scene_axis_changes.csv', changes)
    write_csv(OUT/'feature_strata.csv', summaries)
    write_csv(OUT/'subjective_strata.csv', metrics)
    write_csv(OUT/'review_candidates.csv', review)
    write_csv(OUT/'special_review_cases.csv', [dict(r, provenance=json.dumps(r['provenance'], ensure_ascii=False)) for r in special])
    from tools.thesis_main.data_prep.consolidate_research_input import load_current_bundle
    case_ids = {r['image'] for r in review[:3]} | {min(review, key=lambda r: r['baseline_residual'])['image']}
    case_evidence = [dict(image=r['image_code'], image_id=r['image_id'], image_comment=r['image_comment'],
                          comments=r['comments'], evidence='existing_comments_not_new_verdict')
                     for r in load_current_bundle()['research']['images'] if r['image_code'] in case_ids]
    write_json(OUT/'case_evidence.json', case_evidence)
    counts = dict(images=len(rows), complete=len(complete), ordinary_complete=len(main),
        ordinary_labelled=len(review), scene_strata=dict(Counter(r['scene_stratum'] for r in rows)),
        scored_strata=dict(Counter(r['scene_stratum'] for r in rows if r['baseline_score'] is not None)),
        oos=dict(Counter(r['oos_status'] for r in rows)), doorway=dict(Counter(r['doorway_status'] for r in rows)))
    contract = dict(schema='difficulty_strata_20261009_v2', parent=str(PARENT.relative_to(ROOT)),
        sources=[INVENTORY, *REVIEWS], counts=counts,
        baseline='继承首轮标签盲基线及156图冻结参照；逐图验证原特征、分数完全相同；不按场景加分',
        axes='独立oos_status与doorway_status；旧scene只为历史分组。最新非空逐轴覆盖，空白不撤销；变化单列。是门洞不能新推困难。',
        doorway_sources='doorway_source为最新门洞存在性状态来源；doorway_annotation_source另保留继承的难标/可标记录来源，两者不混同',
        clear='只有显式not_oos+none为clear；unflagged只是未标特殊，不认证正常或无歧义',
        applicability='特殊/待定图只保留模型代理诊断，主观校准分null；不意味着不可标或自动排除',
        calibration='冻结原136图/42标签留建筑预测，检查名单和标签不变；clear/unflagged子集只是诊断，不是各自重训',
        evidence='稳定非正交、范围标签/既有账本/评论候选和GT标记分别保留；false仅未见对应记录，GT标记不是版本裁决',
        distributions='同时输出各特征可用样本与共同完整样本分布；各轴分组存在重合，不能相加为图数',
        discordance='只用同折外层baseline/calibrated对标签0/.5/1的固定残差；主观等距编码是约定；个案用于解释不验证或逐图调分',
        validation='相关测试见评分说明；未运行模型，上游训练/参照库建筑独立性未核实')
    write_json(OUT/'field_contract.json', contract)
    write_json(OUT/'summary.json', counts)
    lines = ['# 图片难度：分层推进与适用性', '',
        '2026-10-09。沿客观评分→主观对比→不一致原因核查推进；OOS和门洞交界独立单列，不作为加分项。首轮结果保留，本目录为分层补充。', '',
        '## 当前实算', '', f"共{len(rows)}图，完整评分{len(complete)}图；原136图普通面板及42标签与首轮完全相同。原始特征和基线分数逐图核对未变。", '',
        '|分层|库存图数|完整评分图数|', '|---|---:|---:|']
    for key, n in counts['scene_strata'].items():
        lines.append(f"|{key}|{n}|{counts['scored_strata'].get(key, 0)}|")
    lines += ['', 'clear须显式非OOS且非门洞，unflagged仅为未标特殊。OOS与门洞交集不遗漏；可标门洞与难标门洞分别保留。OOS不等于不可标，四角输出不证明简单。', '',
        '## 主线的新安排', '',
        '1. 已完成：逐轴恢复场景及来源、覆盖和可用性，不按场景调高分数；特殊图校准候选留空。',
        '2. 已完成：按场景及两个原轴输出特征覆盖和分布，同时保留各自可用样本与共同完整面板；留建筑预测按clear/unflagged分开诊断。',
        f'3. 已完成：按外层标签盲基线残差导出{len(review)}图核查队列，校准残差另列，保留全部名单；特殊{len(special)}图另外导出，不与普通图混排。',
        '4. 已开始案例核查：最大基线残差前三图，加一张低估的困难图，既有原话见case_evidence.json；视觉观察和新增特征假设见CASE_REVIEW.md。个案不认证特征有效。',
        '5. 在新增指标定义和来源明确后，沿建筑留出比较增量；对门洞先澄清目标范围、对OOS先核查表示适配，再研究同一任务下难度。不用GT误差或人员不一致反向定义分数。', '',
        '## 文件及解释', '',
        '- `features_and_scores.csv`为全259图当前分层表；`scene_axis_changes.csv`是后审逐轴变化。',
        '- `feature_strata.csv`含覆盖/四分位；`subjective_strata.csv`中普通子集使用既有留建筑预测，特殊子集仅为描述性匹配，分数归一化参照不同，不能直接比较两类相关强弱。',
        '- `review_candidates.csv`保留外层分数与固定残差；`special_review_cases.csv`保留特殊/待定全部案例、缺失与已有语义证据。记录不代表新盲审。',
        '- [四图案例观察](CASE_REVIEW.md)区分本轮可见内容与既有审核解释；没有改源标签、场景或分数。',
        '- 不因GT标记判定参考不适用，不因范围评论认定存在确定歧义；未记录不作否定证据。历史标签口径混合，残差不是客观错误证明。',
        '- 上游模型强制约束、回退未知和建筑重合未知仍在。当前输出合同不改变项目协议、GT、资格或原分类。', '',
        '复算：`.venv/Scripts/python.exe -m tools.thesis_main.analysis.difficulty_strata_20261009`。', '']
    (OUT/'REPORT.md').write_text('\n'.join(lines), encoding='utf-8')
    print(json.dumps(counts, ensure_ascii=True))


if __name__ == '__main__':
    run()
