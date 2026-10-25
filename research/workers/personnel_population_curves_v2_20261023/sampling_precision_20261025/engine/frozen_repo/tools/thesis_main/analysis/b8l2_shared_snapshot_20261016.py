"""只消费冻结v6输入，实算原B8L2并交付各模块共用的有资格评分。"""
import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from .descriptive_statistics_current_20261015 import (
    ROOT, QUALITY_METRICS, build_tables, rebuild_metric_tables, write,
)
from .scope_quality_scoring_20261016 import scoring_engine, score_task
from .b8l2_shared_descriptive_20261016 import add_b8l2_descriptive_tables

OUT = ROOT/'research/statistics/b8l2_shared_v6_20261016'
VERSION = 'b8l2_shared_v6_20261016_v1'
HOLDS = ['same_target_quality_hold','latest_step_reference_pending','original_holdout','same_target_unconfirmed']


def quality_reasons(row, binding, reference, difficulty):
    reasons = list(row['pool_analysis_exclusion_reasons']) if not row['pool_analysis_eligible'] else []
    if not binding['person_quality_restriction_clear']:
        reasons.append('inherited_person_or_answer_restriction')
    if not binding['chosen_target_id']:
        reasons.append('space_binding_not_unique')
    if not binding['score_input_eligible']:
        reasons.append('annotation_geometry_unavailable_or_inapplicable')
    if not reference or not reference['full_reference_available']:
        reasons.append('reference_not_full')
    if reference and not reference['current_target']:
        reasons.append('bound_other_admitted_space')
    if difficulty['difficulty_analysis_exclusion'] == 'user_reported_issue_pending':
        reasons.append('current_image_issue_pending')
    reasons.extend('legacy:'+key for key in HOLDS if row.get(key) in (True,'True'))
    return sorted(set(reasons))


def member_changes(current, previous):
    old=previous.set_index('object_id').to_dict('index')
    result=[]
    for row in current.to_dict('records'):
        prior=old.get(row['object_id'])
        eligible=bool(row['current_quality_eligible'])
        target_changed=bool(prior and prior['current_target_id'] != row['current_target_id'])
        reference_changed=bool(prior and eligible and prior['reference_id'] != row['reference_id'])
        score_changed=bool(prior and eligible and abs(float(prior['B8L2'])-row['B8L2'])>1e-8)
        result.append(dict(object_id=row['object_id'],
            image_code=row.get('image_code',''),worker_id=row.get('worker_id',''),condition=row.get('condition',''),
            membership_change='retained' if prior and eligible else 'removed' if prior else
                'added_new_score_coverage' if eligible else 'outside_both',
            previous_B8L2=float(prior['B8L2']) if prior else None,current_B8L2=row['B8L2'],
            previous_reference_id=prior['reference_id'] if prior else '',current_reference_id=row.get('reference_id',''),
            target_changed=target_changed,reference_changed=reference_changed,score_changed=score_changed,
            label_changed=bool(prior and prior['difficulty_class'] != row['difficulty_class']),
            previous_difficulty=prior['difficulty_class'] if prior else '',current_difficulty=row['difficulty_class'],
            delta_B8L2=row['B8L2']-float(prior['B8L2']) if prior and eligible else None,
            exclusion_reasons=row['quality_exclusion_reasons']))
    return pd.DataFrame(result)


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def run(out=OUT):
    fixed=read_json(out/'FROZEN_INPUTS.json')
    assert fixed['version']==VERSION
    inputs=out/'inputs'
    fixed.update(inventory=read_json(inputs/'inventory.json'),
        historical_records=pd.read_csv(inputs/'historical_records.csv',dtype=str,keep_default_na=False).to_dict('records'),
        historical_geometry=read_json(inputs/'historical_geometry.json'),reference_sources=read_json(inputs/'scope_sources.json'))
    tables,checks=build_tables(fixed)
    bundle,difficulty=fixed['bundle'],fixed['difficulty']
    references=read_json(inputs/'reference_catalog.json')
    binding=read_json(inputs/'binding_all.json')
    refs={r['target_id']:r for r in references}
    bindings={r['object_id']:r for r in binding['affected_records']}
    objects={r['object_id']:r for r in bundle['data']['objects']}
    images={r['image_id']:r for r in difficulty['records']}
    audit=tables['record_audit'].copy().set_index('object_id',drop=False)
    audit['quality_exclusion_reasons']=[[] for _ in range(len(audit))]
    audit['rescore_status']='not_queued'
    audit['rescore_reference_version']=''
    audit['reference_version']=''
    audit['rescore_target_id']=''
    audit['primary_metric']='B8L2'
    audit['B8L2_version']='WQ-B8L2-20261015'
    audit['input_version']=VERSION
    audit['snapshot_version']=VERSION
    audit['current_quality_eligible']=False
    audit[QUALITY_METRICS]=np.nan
    audit['target_matched_time_seconds']=np.nan
    audit['target_time_interpretation']='no_preexisting_audited_target_time'
    previous=pd.read_csv(inputs/'previous_quality_records.csv',keep_default_na=False)
    previous_analysis=pd.read_csv(inputs/'previous_analysis_records.csv',keep_default_na=False).set_index('object_id')
    tasks=[]
    for oid,row in audit.iterrows():
        choice=bindings[oid]
        ref=refs.get(choice['chosen_target_id'])
        reasons=quality_reasons(row,choice,ref,images[row.image_id])
        audit.at[oid,'quality_exclusion_reasons']=reasons
        audit.at[oid,'rescore_target_id']=choice['chosen_target_id']
        if ref:
            audit.at[oid,'rescore_reference_version']=ref['reference_version']
            audit.at[oid,'reference_version']=ref['reference_version']
        if reasons and reasons != ['bound_other_admitted_space']:
            continue
        tasks.append(dict(object_id=oid,image_id=row.image_id,worker_id=row.worker_id,condition=row.condition,
            current_target_id=ref['target_id'],reference_version=ref['reference_version'],
            annotation_points=objects[oid]['points_1024x512'],reference_points=ref['points_1024x512']))
    print(json.dumps(dict(difficulty=difficulty['version'],tasks=len(tasks)),ensure_ascii=False),flush=True)
    scores=[]
    with scoring_engine(inputs/'measurement_engine.zip',inputs/'working_models.py') as (engine,models):
        assert models.MODELS['B8L2'].version=='WQ-B8L2-20261015'
        parameters=vars(models.MODELS['B8L2'])
        assert [parameters[k] for k in ['direction_scale_deg','direction_cap','bottom_scale_squared_deg2',
            'global_height_scale','local_height_scale','pooling_order']]==[8.,1.5,32.,.8,.25,2.]
        (out/'MODEL_PARAMETERS.json').write_text(json.dumps(parameters,indent=2),encoding='utf-8')
        for index,task in enumerate(tasks):
            score=score_task(task,engine,models)
            score.update(input_version=VERSION,batch_id='existing_inventory_20261016',
                difficulty_version=difficulty['version'],primary_metric='B8L2')
            scores.append(score)
            oid=score['object_id']
            audit.at[oid,'rescore_status']=score['score_status']
            if score['score_status']=='complete' and not audit.at[oid,'quality_exclusion_reasons']:
                audit.at[oid,'current_quality_eligible']=True
                audit.at[oid,'reference_id']=score['current_target_id']
                audit.at[oid,'score_version']=json.dumps(score['score_versions'],ensure_ascii=False)
                audit.at[oid,'quality_audit_status']='recomputed_fixed_B8L2_current_reference'
                for metric in QUALITY_METRICS:
                    audit.at[oid,metric]=score[metric]
                if oid in previous_analysis.index:
                    prior=previous_analysis.loc[oid]
                    time=pd.to_numeric(prior.target_matched_time_seconds,errors='coerce')
                    if prior.current_target_id==score['current_target_id'] and pd.notna(time):
                        audit.at[oid,'target_matched_time_seconds']=time
                        audit.at[oid,'target_time_interpretation']='retained_preexisting_audited_same_target_time'
            elif score['score_status']!='complete':
                audit.at[oid,'quality_exclusion_reasons']=score['reasons']
            if (index+1)%100==0:
                print(f'fixed measurements {index+1}/{len(tasks)}',flush=True)
    audit=audit.reset_index(drop=True)
    audit['quality_use']=np.select([audit.current_quality_eligible & audit.ordinary_difficulty_eligible,
        audit.current_quality_eligible],['ordinary_primary','special_conditional_only'],default='not_qualified')
    audit['metric_applicability_note']=np.where(audit.quality_use.eq('special_conditional_only'),
        'conditional_measurement_only_not_representation_validation','fixed_existing_measurement_not_method_validation')
    assert audit.loc[~audit.current_quality_eligible,QUALITY_METRICS].isna().all().all()
    tables['record_audit']=audit
    tables['previous_quality_records']=previous
    tables['member_changes']=member_changes(audit,previous)
    for key,value in [('space_reference_catalog',references),('shared_bindings',binding['affected_records']),
        ('record_targets',binding['record_targets']),('image_spaces',binding['image_spaces']),('rescore_comparisons',scores)]:
        tables[key]=pd.DataFrame(value)
    affected_images={r['image_id'] for r in difficulty['records'] if r['selected']['role'] in ('confirmed_scope','user_revised_gt')}
    tables['affected_records']=pd.DataFrame([dict(bindings[r.object_id],
        current_quality_eligible=bool(r.current_quality_eligible),score_status=r.rescore_status,
        current_reference_full_available=refs[r.current_target_id]['full_reference_available'])
        for _,r in audit[audit.image_id.isin(affected_images)].iterrows()])
    tables['remaining_gaps']=audit[~audit.current_quality_eligible][['object_id','image_id','image_code','worker_id',
        'condition','current_target_id','rescore_target_id','pool_source_workers','quality_exclusion_reasons']].rename(
        columns={'rescore_target_id':'chosen_target_id','quality_exclusion_reasons':'remaining_reasons'})
    tables['remaining_gaps']['minimal_human_question']=tables['remaining_gaps'].remaining_reasons.map(
        lambda r:'确认原作答空间' if 'space_binding_not_unique' in r else '核对完整参考来源' if 'reference_not_full' in r else '')
    tables['pending_rescore']=audit[audit.existing_full_quality_available & ~audit.current_quality_eligible]
    tables['current_images']['difficulty_details_source']=str((out/'FROZEN_INPUTS.json').relative_to(ROOT))+'#/difficulty'
    for i,row in tables['current_images'].iterrows():
        ref=refs[row.current_target_id]
        tables['current_images'].at[i,'full_current_target_geometry_available']=ref['full_reference_available']
        tables['current_images'].at[i,'reference_status']=ref['status']
    audit['difficulty_details_source']=str((out/'FROZEN_INPUTS.json').relative_to(ROOT))+'#/difficulty'
    rebuild_metric_tables(tables,bundle=bundle)
    add_b8l2_descriptive_tables(tables)
    tables['shared_records']=audit.copy()
    changes=tables['member_changes']
    checks.update(snapshot_version=VERSION,primary_metric='B8L2',score_version='WQ-B8L2-20261015',
        source_snapshot='frozen FROZEN_INPUTS.json and inputs/*; no live CURRENT reads',
        new_scores_computed=True,score_tasks=len(tasks),complete_scores=sum(s['score_status']=='complete' for s in scores),
        previous_quality_rows=len(previous),quality_rows=len(tables['quality_records']),
        membership_changes=changes.membership_change.value_counts().to_dict(),
        retained_score_changes=int(changes.query("membership_change=='retained'").score_changed.sum()),
        retained_label_changes=int(changes.query("membership_change=='retained'").label_changed.sum()),
        ordinary_primary_quality_rows=int(audit.quality_use.eq('ordinary_primary').sum()),
        special_conditional_quality_rows=int(audit.quality_use.eq('special_conditional_only').sum()),
        analysis_rows=len(tables['analysis_records']),pending_rescore_rows=len(tables['pending_rescore']),
        inventory_usable_time_rows=int(tables['inventory_all'].active_time_seconds.notna().sum()),
        source_time_rows=int(tables['analysis_records'].active_time_seconds.notna().sum()),
        target_matched_time_rows=int(audit.target_matched_time_seconds.notna().sum()),
        affected_images=len(affected_images),affected_records=len(tables['affected_records']),
        current_confirmed_scope_references=sum(r['current_target'] and r['role']=='confirmed_scope' for r in references),
        complete_confirmed_scope_references=sum(r['current_target'] and r['role']=='confirmed_scope' and r['full_reference_available'] for r in references))
    write(tables,checks,out)
    contract=read_json(out/'FIELD_CONTRACT.json')
    contract.update(version=VERSION,snapshot_version=VERSION,input_version=VERSION,batch_id='existing_inventory_20261016',
        primary_metric='B8L2',difficulty_pointer='FROZEN_INPUTS.json#/difficulty_pointer',
        quality_eligibility='unique pre-score binding + full reference + candidate person/image/source-pool gates + all explicit holds; historical score coverage is not eligibility',
        primary_records='shared_records.csv',qualified_scores='quality_records.csv',
        applicability='quality_use separates ordinary_primary from special_conditional_only; computability does not override OOS or module-specific applicability holds',
        historical_comparison='inputs/previous_quality_records.csv; frozen v4, not latest input',
        time='seconds; source time unchanged; target matched time only retained from preexisting audited same-target rows',
        required_join=['object_id','image_id','worker_id','condition','reference_id','reference_version','input_version','B8L2_version'])
    (out/'FIELD_CONTRACT.json').write_text(json.dumps(contract,ensure_ascii=False,indent=2),encoding='utf-8')
    write_delivery(tables,checks,out)
    print(json.dumps(checks,ensure_ascii=False,indent=2),flush=True)
    return tables,checks


def markdown(frame,columns):
    lines=['|'+'|'.join(columns)+'|','|'+'|'.join(['---']*len(columns))+'|']
    for row in frame.to_dict('records'):
        values=[row[k] for k in columns]
        lines.append('|'+'|'.join('—' if pd.isna(v) else f'{v:.2f}' if isinstance(v,float) else str(v) for v in values)+'|')
    return '\n'.join(lines)


def write_delivery(tables,checks,out):
    base=str(out.relative_to(ROOT))
    qualified=tables['quality_records']
    counts=qualified.groupby(['condition','analysis_layer']).agg(records=('object_id','size'),
        images=('image_id','nunique'),workers=('worker_id','nunique'),B8L2_mean=('B8L2','mean'),
        IoU3D100_mean=('IoU3D100','mean')).reset_index()
    members=tables['member_changes']
    differences=tables['by_difficulty']
    differences=differences[differences.metric.isin(['B8L2','IoU3D100'])]
    manifest=dict(version=VERSION,status='adopted original B8L2 shared measured snapshot',
        input_version=VERSION,difficulty_version=checks['difficulty_version'],
        primary_metric='B8L2',score_version='WQ-B8L2-20261015',
        input_freeze=base+'/FROZEN_INPUTS.json',parameters=read_json(out/'MODEL_PARAMETERS.json'),
        recommended_qualified_scores=base+'/quality_records.csv',
        full_inventory_with_metric_eligibility=base+'/shared_records.csv',
        all_pre_score_bindings=base+'/shared_bindings.csv',
        source_pools=base+'/source_pools.csv',image_status=base+'/current_images.csv',
        reference_catalog=base+'/inputs/reference_catalog.json',
        measurement_engine=base+'/inputs/measurement_engine.zip',models=base+'/inputs/working_models.py',
        measured_values=base+'/rescore_comparisons.csv',changes=base+'/member_changes.csv',
        fields=base+'/FIELD_CONTRACT.json',direct_room_relations=base+'/same_room_relations.csv',
        supplementary_geometry_views=dict(
            package='research/data/scope_redundant_vertices_20261016/README.md',
            views='research/data/scope_redundant_vertices_20261016/scope_views.json',
            summary='research/data/scope_redundant_vertices_20261016/scope_summary.csv',
            used_for_this_snapshot_scoring=False,
            use='target_id-linked structural display/diagnostics only; exact and precision views distinct; never automatically replace frozen references or answers'),
        rules=dict(join=['object_id','image_id','worker_id','condition','reference_id','reference_version','input_version','B8L2_version'],
            conditions='separate manual/semi/oos; ordinary and special separate',
            applicability='filter quality_use: ordinary_primary or special_conditional_only; computable OOS index is not representation validation and does not override module-specific applicability holds',
            worker_analysis='qualified scores are descriptive inputs, not trained ability or a new worker taxonomy',
            fusion='use source pools and original unchanged points from frozen bundle; pool min3 does not remove eligible k1/k2 states',
            fusion_reference='target binding and full reference required for each evaluation; do not choose by final score',
            same_room='direct confirmed relation only, same condition and common worker; no transitive rooms',
            image_holds='all inherited image/person/GT gates remain; user_reported_issue_pending blocks current quality even if complete geometry exists',
            time='seconds; source active time separate; no lead_time; no new target time inferred by scoring',
            difficulty='human assisted coarse groups partly informed by responses; not independent validation',
            future_data='new people/images after current closure; this is the existing inventory only'),
        counts=checks,module_scope='shared measurement and descriptions; downstream modules own models, fusion trajectories and transfer experiments')
    (out/'CROSS_MODULE_INPUTS.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    report=f'''# B8L2共同评分与描述统计：固定v6（2026-10-16）

本次主线实际采用原版`WQ-B8L2-20261015`，不等待Pro的新模型或调参。输入固定为`{checks['difficulty_version']}`和既有3152份原作答；运行不再读取实时CURRENT，也不导入新人或新图片。模型方向尺度8、上限1.5，底边平方尺度32，高度尺度0.8/0.25，底面与方向L2组合；冻结测量未改变。

**本次完整测量{checks['complete_scores']}份，当前合格{checks['quality_rows']}份；旧v4的891份全部保留，新增731份是原库存首次完整评分覆盖。** 另2份人工指定其它合法空间只作诊断。旧891份同输入、同参考的B8L2在1e-8数值精度内不变；42份仅按v6改变分组。731不是新采集、提高分数或放宽人员门，也不是B8L2比WQ更好导致的“新增合格”。

{markdown(counts,['condition','analysis_layer','records','images','workers','B8L2_mean','IoU3D100_mean'])}

其中1575份为ordinary_primary，47份仅special_conditional_only。OOS几何可计算不等于表示适用性已验证；其它模块仍应保留自己的适用性暂停，不能因本表存在一个条件指数就强行开放其完整质量终点。

## 共同输入：下游应读哪份

[CROSS_MODULE_INPUTS.json](CROSS_MODULE_INPUTS.json)是本轮唯一共同交付清单，版本`{VERSION}`。默认读[quality_records.csv](quality_records.csv)取得合格评分；完整库存、空分与排除原因读[shared_records.csv](shared_records.csv)。按完整身份、输入/参考/算法版本连接，不把旧WQ列改名为B8L2，也不复制旧目标分数。

人员线按条件、用途层选择当前评分后自行重建画像与组合分析；这里的逐人均值不是能力类型。融合线同时读取source_pools与冻结原作答，先核人数与图片门，再核状态目标和完整参考；合格池内k=1/2节点可保留。没有为统计覆盖而改融合几何、阈值或已有成员。共同参考目录可算不代表每份作答都属于它；uNb-36保持当前质量待定，不能以完整GT替代问题裁决。

同房线只读直接关系并在同条件、共同人员内对照；本页同房描述不是新迁移或墙线融合研究。各模块不得把已完成的旧WQ模型/曲线直接称为新B8L2结果。

## 输入变化、样本变化和换指标分开

[输入变更审计](audit/INPUT_CHANGE_AUDIT.md)记录v4至v6的17张仅标签变化、2张目标变化、3张资格变化（可交叉），以及3441对象的身份、点序、既有门全部未变。S9-09与zsNo-13采用新目标，两图均只有明确标示的顶界外推预览，仍不计算完整评分；S9虽解除范围门，但仅1名有效真人。GT错误与旧排除继续优先。

[member_changes.csv](member_changes.csv)逐对象区分891保留、731首次评分覆盖及其余1530未进入。新增普通manual309、普通semi375；专项manual23为uNb-63的OOS条件记录，专项semi24为e9-16。后者当前粗类简单但v6普通资格标志仍为false，统计继承该标志单列，没有擅改上游标签或资格。专项不能合入普通难度均值。

WQ/A10/B8L2/同参考均高棱柱IoU均在本轮固定输入上实算保留。[algorithm_comparisons.csv](algorithm_comparisons.csv)展示同集合指标差异；新旧总体均值之差同时受新增覆盖和标签影响，不能归因于换公式。缺分不填0，OOS适用性及未决空间单列；IoU不是任意实体精确体积IoU，B8L2的D仍是自身方向规整性，未升级为参考结构正确性。

## 分层统计、时间与图簿

普通难度描述如下，分条件展示实际有效数和覆盖；标签是人工辅助粗类，部分参考过作答，均值分层不是独立验证，不要求顺序单调。

{markdown(differences,['panel','difficulty_class','metric','n_valid','n_missing','n_valid_images','mean','sd'])}

库存有可用原采集时间1949份，其中当前合格来源分析时间1750份；它们不是同一个分母。完整质量与来源时间共有1042份，已审计同目标质量/时间共有440份。新评分没有据采集时长推断新目标完成时间，也没有使用lead_time替代。source/time状态与秒单位逐行保留，time_coverage展示条件与层的真实覆盖。

- [B8L2共同评分工作簿](B8L2共同评分_描述统计.xlsx)：逐人、逐图、人员×难度、场景、建筑、同房、时间、成员变化和完整/缺失分母。
- [七组关键图及说明](figures/FIGURES.md)：B8L2为主，保留WQ/A10/IoU对照。
- [空间点位职责与冗余派生视图](../../data/scope_redundant_vertices_20261016/README.md)：补充显示/诊断资料，不参与本快照评分。按原target_id使用新环，不追加已被新目标排除的旧GT角点；严格等价与精度内近似分开，未知高度不生成完整点对视图。仅2份参考自比及1份真人作答已核验B8L2差值为0，不作全库不变性结论。
- [冻结参考与绑定审计](inputs/REFERENCE_BINDING_AUDIT.json)、[独立评分审计](audit/SCORING_AUDIT.md)。

43张受影响图的511份作答仍全部列在affected_records；3152份总绑定另列shared_bindings。41个确认新空间中12个具完整参考、29个仍待补，371份原作答尚无唯一空间绑定。小幅源域越界可能涉及坐标精度口径；诊断保留源JSON与ERP转换差异，未通过调容差、snap或外推来改变评分参考。

## 复现与边界

```powershell
python -m tools.thesis_main.analysis.b8l2_shared_snapshot_20261016 --snapshot-dir research/statistics/b8l2_shared_v6_20261016
```

现有目录已经固定FROZEN_INPUTS、库存/时间、历史比较、来源/参考绑定及模型/测量实现。本命令只消费这些固定资料；未来增量另起版本和目录。原始标注、GT、CURRENT、正式合同、评分参数和历史结果未覆盖；不推送、不启动采集。图簿用各自既有生成器，复现命令见图表说明及工作簿验证记录。
'''
    (out/'README.md').write_text(report,encoding='utf-8')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--snapshot-dir',type=Path,default=OUT)
    args=parser.parse_args()
    run(args.snapshot_dir)
