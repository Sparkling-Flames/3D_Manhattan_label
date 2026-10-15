"""空间参考、原作答绑定和冻结评分分层审计，写入独立统计快照。"""
import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from ..data_prep.consolidate_research_input import load_current_bundle
from .descriptive_statistics_current_20261015 import (
    ROOT, POINTER, QUALITY_METRICS, build_tables, rebuild_metric_tables, write,
)
from .scope_reference_reconstruction_20261016 import build_reference_catalog
from .scope_quality_binding_20261016 import build_affected_records
from .scope_quality_scoring_20261016 import score_records

OUT = ROOT / 'research/data/scope_quality_rescore_20261016'
STATS = ROOT / 'research/statistics/descriptive_statistics_rescored_20261016'
VERSION = 'confirmed_scope_fixed_quality_rescore_20261016_v1'


def integrate_scores(audit, affected, scores, references):
    """只有当前目标、人员与图片门均合格的完整新评分进入统计；诊断另存。"""
    result = audit.copy().set_index('object_id', drop=False)
    refs = {r['target_id']: r for r in references}
    scored = {r['object_id']: r for r in scores}
    assert len(scored) == len(scores), 'multiple primary scores per answer'
    result['rescore_status'] = 'not_affected'
    result['rescore_reference_version'] = ''
    result['rescore_target_id'] = ''
    for row in affected:
        oid = row['object_id']
        score = scored.get(oid)
        target = row.get('chosen_target_id')
        ref = refs.get(target)
        status = score['score_status'] if score else row['binding_status']
        result.at[oid, 'rescore_status'] = status
        result.at[oid, 'rescore_target_id'] = target or ''
        result.at[oid, 'rescore_reference_version'] = ref['reference_version'] if ref else ''
        allowed = bool(score and score['score_status'] == 'complete' and ref['current_target']
            and row['person_quality_restriction_clear'] and row['pool_analysis_eligible'])
        # 受影响图的历史参考已被旧快照屏蔽；重算只解除明确解决的参考/绑定缺口。
        assert not bool(result.at[oid, 'current_quality_eligible'])
        result.at[oid, 'current_quality_eligible'] = allowed
        if allowed:
            for metric in QUALITY_METRICS:
                result.at[oid, metric] = score[metric]
            result.at[oid, 'reference_id'] = target
            result.at[oid, 'score_version'] = json.dumps(score['score_versions'], ensure_ascii=False)
            result.at[oid, 'quality_audit_status'] = 'recomputed_current_complete_reference'
            result.at[oid, 'reference_audit_reasons'] = ['new_reference_scored_without_annotation_change']
            result.at[oid, 'full_current_target_geometry_available'] = True
        # 事后重算质量不能证明采集时针对新空间完成任务；保留原始采集时间另列。
        result.at[oid, 'target_matched_time_seconds'] = np.nan
        result.at[oid, 'target_time_interpretation'] = 'rescore_does_not_establish_new_target_collection_time'
    assert not result.loc[~result.pool_analysis_eligible, QUALITY_METRICS].notna().any().any()
    return result.reset_index(drop=True)


def frame(rows):
    return pd.DataFrame(rows)


def run(out=OUT, stats_out=STATS):
    assert out.resolve() != stats_out.resolve()
    for path in [out/'CHECKS.json', stats_out/'FIELD_CONTRACT.json']:
        if path.exists():
            prior = json.loads(path.read_text(encoding='utf-8'))
            if prior.get('snapshot_version', prior.get('version')) != VERSION:
                raise ValueError('different snapshot: choose a new output directory')
    pointer = json.loads(POINTER.read_text(encoding='utf-8-sig'))
    difficulty = json.loads((POINTER.parent / pointer['details']).read_text(encoding='utf-8-sig'))
    bundle = load_current_bundle()
    references = build_reference_catalog(bundle, difficulty['records'])
    binding = build_affected_records(bundle, difficulty['records'], references)
    affected = binding['affected_records']
    objects = {o['object_id']: o for o in bundle['data']['objects']}
    refs = {r['target_id']: r for r in references}
    tasks = []
    for row in affected:
        ref = refs.get(row.get('chosen_target_id'))
        if not ref or not ref['full_reference_available'] or not row['score_input_eligible']:
            continue
        tasks.append(dict(object_id=row['object_id'], image_id=row['image_id'],
            worker_id=row['worker_id'], condition=row['condition'], current_target_id=ref['target_id'],
            reference_version=ref['reference_version'],
            annotation_points=objects[row['object_id']]['points_1024x512'],
            reference_points=ref['points_1024x512']))
    scores = score_records(tasks)
    for score in scores:
        score.update(input_version='formal_loader_snapshot_20261016',
            batch_id='existing_inventory_20261016',input_source_manifest='analysis_results/research_input_20260929/manifest.json')
    tables, checks = build_tables()
    baseline = tables['record_audit'].set_index('object_id')
    previous_pending = tables['pending_rescore'].copy()
    comparisons = []
    for score in scores:
        old = baseline.loc[score['object_id']]
        comparisons.append(dict(**score, image_code=old.image_code,
            historical_reference_id=old.reference_id,
            historical_score_version=old.score_version,
            **{'historical_'+m: old['historical_'+m] for m in QUALITY_METRICS},
            **{'delta_'+m: score[m]-old['historical_'+m]
               if score[m] is not None and pd.notna(old['historical_'+m]) else None for m in QUALITY_METRICS}))
    tables['record_audit'] = integrate_scores(tables['record_audit'], affected, scores, references)
    indexed_audit = tables['record_audit'].set_index('object_id')
    indexed_scores = {r['object_id']: r for r in scores}
    gaps = []
    for row in affected:
        ref = refs.get(row['chosen_target_id'])
        current = refs[row['current_target_id']]
        score = indexed_scores.get(row['object_id'])
        row.update(current_reference_full_available=current['full_reference_available'],
            chosen_reference_full_available=bool(ref and ref['full_reference_available']),
            score_status=score['score_status'] if score else 'not_computed',
            current_quality_eligible=bool(indexed_audit.at[row['object_id'], 'current_quality_eligible']))
        reasons = []
        if not row['chosen_target_id']:
            reasons.append('answer_space_binding_not_unique')
        if not (ref or current)['full_reference_available']:
            reasons.append((ref or current)['minimal_gap'])
        if not row['score_input_eligible']:
            reasons.append('original_annotation_geometry_unavailable_or_inapplicable')
        if not row['person_quality_restriction_clear']:
            reasons.append('inherited_person_or_answer_restriction')
        if not row['pool_analysis_eligible']:
            reasons.extend(row['pool_analysis_exclusion_reasons'])
        if score and score['score_status'] != 'complete':
            reasons.extend(score['reasons'])
        if reasons:
            gaps.append(dict(object_id=row['object_id'],image_id=row['image_id'],image_code=row['image_code'],
                worker_id=row['worker_id'],condition=row['condition'],
                chosen_target_id=row['chosen_target_id'],allowed_target_ids=row['allowed_target_ids'],
                reference_gap=(ref or current)['minimal_gap'],remaining_reasons=sorted(set(reasons)),
                minimal_human_question='请确认该原作答采用哪个已准入空间'
                    if not row['chosen_target_id'] else
                    '请确认超出完整源空间的部分或提供对应完整几何'
                    if not ref['full_reference_available'] else ''))
    for index, image in tables['current_images'].iterrows():
        ref = refs[image.current_target_id]
        tables['current_images'].at[index,'full_current_target_geometry_available'] = ref['full_reference_available']
        tables['current_images'].at[index,'reference_status'] = ref['status']
    rebuild_metric_tables(tables)
    tables['pending_rescore'] = tables['record_audit'][
        tables['record_audit'].existing_full_quality_available & ~tables['record_audit'].reuse_full_quality
        & ~tables['record_audit'].rescore_status.eq('complete')].copy()
    tables['space_reference_catalog'] = frame(references)
    tables['affected_records'] = frame(affected)
    tables['record_targets'] = frame(binding['record_targets'])
    tables['image_spaces'] = frame(binding['image_spaces'])
    tables['rescore_comparisons'] = frame(comparisons)
    tables['remaining_gaps'] = frame(gaps)
    checks.update(snapshot_version=VERSION, new_scores_computed=True,
        affected_images=len({r['image_id'] for r in affected}), affected_records=len(affected),
        score_tasks=len(tasks), complete_scores=sum(r['score_status']=='complete' for r in scores),
        previous_quality_rows=checks['quality_rows'], quality_rows=len(tables['quality_records']),
        pending_rescore_rows=len(tables['pending_rescore']),
        current_confirmed_scope_references=sum(r['current_target'] and r['role']=='confirmed_scope' for r in references),
        complete_confirmed_scope_references=sum(r['current_target'] and r['role']=='confirmed_scope'
            and r['full_reference_available'] for r in references),
        historical_pending_decomposition=previous_pending.groupby(['target_role','target_floor_relation']).size().to_dict())
    checks['historical_pending_decomposition'] = {
        '|'.join(k): v for k, v in checks['historical_pending_decomposition'].items()}
    checks['added_current_quality_rows'] = checks['quality_rows']-checks['previous_quality_rows']
    write(tables, checks, stats_out)
    out.mkdir(parents=True, exist_ok=True)
    (out/'INPUT_MANIFEST.json').write_text(json.dumps(dict(
        snapshot_version=VERSION,input_version='formal_loader_snapshot_20261016',
        source_manifest=bundle['manifest'],difficulty_pointer=pointer,
        reference_catalog='reference_catalog.json',annotation_geometry='unchanged full loader points_1024x512',
        score_models='research/quality/quality_ab_feedback_handoff_20261015/prior_AB/src/working_models.py',
        scoring_archive='research/quality/quality_joint_closeout_review_20261015/pro_closeout_delta.zip'),
        ensure_ascii=False,indent=2),encoding='utf-8')
    audit_tables = dict(reference_catalog=frame(references), affected_records=frame(affected),
        record_targets=frame(binding['record_targets']), image_spaces=frame(binding['image_spaces']),
        rescore_comparisons=frame(comparisons), remaining_gaps=frame(gaps), historical_pending_160=previous_pending)
    for key, data in audit_tables.items():
        data.to_json(out/(key+'.json'), orient='records', force_ascii=False, indent=2)
        for column in data:
            data[column] = data[column].map(lambda x: json.dumps(x, ensure_ascii=False)
                if isinstance(x,(dict,list,tuple)) else x)
        data.to_csv(out/(key+'.csv'), index=False, encoding='utf-8-sig')
    (out/'CHECKS.json').write_text(json.dumps(checks, ensure_ascii=False, indent=2), encoding='utf-8')
    contract = json.loads((stats_out/'FIELD_CONTRACT.json').read_text(encoding='utf-8'))
    contract.update(version=VERSION, reference_catalog=str((out/'reference_catalog.json').relative_to(ROOT)),
        quality_eligibility='unchanged source pool/image/person gates + unique pre-score binding + full declared reference; diagnostics separate',
        target_time='rescore does not establish new-target collection time')
    (stats_out/'FIELD_CONTRACT.json').write_text(json.dumps(contract, ensure_ascii=False, indent=2), encoding='utf-8')
    write_report(tables, checks, out, stats_out)
    return tables, checks


def markdown_table(data, columns):
    lines = ['|'+'|'.join(columns)+'|', '|'+'|'.join(['---']*len(columns))+'|']
    for row in data.to_dict('records'):
        values = []
        for key in columns:
            value = row[key]
            values.append('—' if pd.isna(value) else f'{value:.2f}' if isinstance(value,float) else str(value))
        lines.append('|'+'|'.join(values)+'|')
    return '\n'.join(lines)


def write_report(tables, checks, out, stats_out):
    affected = tables['affected_records']
    quality = tables['quality_records']
    comparisons = tables['rescore_comparisons']
    counts = quality.groupby('condition').agg(records=('object_id','size'), images=('image_id','nunique'),
        workers=('worker_id','nunique')).reset_index()
    bindings = affected.groupby('binding_status').size().rename('作答数').reset_index()
    ready = tables['space_reference_catalog']
    ready = ready[ready.current_target & ready.image_id.isin(affected.image_id)]
    image_rows = ready[['image_code','role','full_reference_available','method','minimal_gap']].sort_values('image_code')
    report = f'''# 已确认空间与修订GT的质量重算（2026-10-16）

本次核验41图的全部506份现有作答：39图采用确认的新空间，另2图使用修订GT。旧160条只是1145份历史完整评分中的受影响子集：54条同底面但完整参考未核、96条底面改变、10条修订GT；不能将160当成全部受影响作答。

实际送入冻结引擎{checks['score_tasks']}份，完整计算{checks['complete_scores']}份。通过当前目标绑定、原图片/人员限制和来源池人数门后，新增{checks['added_current_quality_rows']}份当前质量，当前总数由807变为{checks['quality_rows']}。诊断可评分不授予统计资格；旧评分和参考身份保留在逐作答对照中。旧待处理160条中，仍有{checks['pending_rescore_rows']}条尚无绑定空间完整评分；已完成的61条包含59条新增当前质量与2条人工指定的其它合法空间。其余25条新增当前质量来自旧160条之外。所有506份的其它缺口另见remaining_gaps，两个分母不混用。

{markdown_table(counts, ['condition','records','images','workers'])}

## 参考及空间绑定

39图中12个新空间完整参考可确定：6个严格等价底面保留已有完整点对，6个在可信原空间内，使用原布局JSON已明确声明的顶平面完成整个空间的竖向裁切。源JSON既定转换与现有原GT逐值一致后才使用其顶平面，没有从IoU均高公式倒造顶界。另27个确认多边形部分超出可信源域，原域交集仅为诊断，不替代确认范围；需核对范围或补对应完整几何。两份修订GT保留原点对对应，均按唯一修订参考评价原完整作答。

原GT、手工GT的历史版本并不自动成为两个合法空间。仅继承既有审核准入的空间；人工指定优先，family A/B约束不擅自细化成A或B，多个合法目标仍未定者保持待绑定。没有按最高Q或最高全局IoU选空间，没有裁剪或修改作答。

{markdown_table(bindings, ['binding_status','作答数'])}

image_spaces按图片×空间×条件列出来源池人数与已绑定空间人数；同一人展开多个候选不会增加实际人数。主分析仍按图片×条件的有效人员池至少3人，GT错误、旧暂停和个别作答限制继续优先；每指标可用人数另报。

{markdown_table(image_rows, ['image_code','role','full_reference_available','method','minimal_gap'])}

## 固定评分与解释

WQ-LS08、A10、B8L2和现用均高棱柱IoU3D均复用已有冻结实现；各分项、公式版本、输入/参考身份保存在rescore_comparisons。三个历史控制复现至1e-8，未重新调参。参考自比的原方向惩罚也原样保留。IoU3D不是任意实体精确体积IoU；新增竖切边界不因此被断言为实体墙。

新旧参考不同的分数差只描述参考修订后的数值变化，不是作答改进，也不是算法优劣。新目标下的完整质量重算不证明采集时以该目标完成任务；原始有效操作时间单列，未据此补造新目标耗时。

## 交付与复现

- [更新后的完整统计、工作簿与关键图](../{stats_out.name}/README.md)
- [独立审计与逐层数量复算](INDEPENDENT_AUDIT.md)
- reference_catalog：每稳定目标一行，完整参考、参考版本、构造及原回执来源。
- affected_records：506原作答逐条状态；record_targets：候选展开，不作为作答分母。
- image_spaces：空间支持人数和来源人数分别列出；rescore_comparisons：实际冻结重算及历史对照。
- remaining_gaps：确切对象、未解决原因和最小人工问题；historical_pending_160保留旧子集身份。
- [后续批次及质量算法接入](EXTENSION_GUIDE.md)。

```powershell
python -m tools.thesis_main.analysis.scope_quality_rescore_20261016
```

输入为现有CURRENT及完整loader；输出为独立目录，原始标注、旧GT、难度v3、历史统计和已存在融合曲线均未覆盖。下游统计按新参考重建，不重跑融合实验。
'''
    (out/'README.md').write_text(report, encoding='utf-8')
    scope = quality[quality.rescore_status.eq('complete')]
    overview = tables['by_difficulty']
    overview = overview[overview.metric.isin(['WQ','A10','B8L2','IoU3D100'])]
    stats_report = f'''# 参考重算后的描述统计快照（2026-10-16）

本快照承接[上一版人数门与难度v3统计](../descriptive_statistics_current_20261015/README.md)，将实际完成的完整参考评分纳入；源库存3152份/259图、至少3人来源规则、GT及既有排除均未改变。

完整质量共{len(quality)}份，新增{len(scope)}份；条件及真实覆盖如下。全局807旧质量保留，新增可计算覆盖不表示总体质量改善。2834份可分析来源记录不等于完整质量数。

{markdown_table(counts, ['condition','records','images','workers'])}

普通难度的分条件描述统计如下；缺失不补0，类别间任务与人员组成不同，不据此声称因果差异或难度算法已验证。

{markdown_table(overview, ['panel','difficulty_class','metric','n_valid','mean','median','sd'])}

## 查阅

- [当前工作簿](现有研究数据描述统计_重评分口径.xlsx)
- [关键科研图](figures/FIGURES.md)
- [41图506份逐项审计、参考构造与冻结重算](../scope_quality_rescore_20261016/README.md)
- [后续新人、新数据及质量版本接入](../scope_quality_rescore_20261016/EXTENSION_GUIDE.md)

完整明细与字段合同落在本目录；所有人员、建筑、同房、难度及算法对照均从新逐条数值重建。仅重算完整质量，没有把新评分回填为旧采集目标耗时，也没有重跑原融合实验。IoU3D仍是现用均高棱柱口径。
'''
    (stats_out/'README.md').write_text(stats_report, encoding='utf-8')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, default=OUT)
    parser.add_argument('--stats-out', type=Path, default=STATS)
    args = parser.parse_args()
    _, checks = run(args.out, args.stats_out)
    print(json.dumps(checks, ensure_ascii=False, indent=2))
