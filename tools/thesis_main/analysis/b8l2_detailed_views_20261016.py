"""补齐固定v6的人员、图片、场景与关系组查阅，不重评分或修改资格。"""
import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from .b8l2_detail_summary_20261016 import grouped_summary, summarize_group, METRICS

ROOT=Path(__file__).resolve().parents[3]
SOURCE=ROOT/'research/statistics/b8l2_usage_v6_20261016'
VERSION='b8l2_detailed_views_20261016_v2'


def cell_status(summary):
    return 'no_observations' if not summary['n_inventory_records'] else (
        'observed_no_analyzed_source' if not summary['n_source_records'] else
        'analyzed_source_no_quality' if not summary['B8L2_n'] else 'quality_available')


def inventory_overview(records,by):
    output=[]
    for identity,frame in records.groupby(by,sort=True):
        accepted=frame[frame.pool_analysis_eligible]
        reasons=sorted({r for values in frame.pool_analysis_exclusion_reasons for r in values})
        quality_reasons=sorted({r for values in frame.quality_exclusion_reasons for r in values})
        row=dict(zip(by if isinstance(by,list) else [by],identity if isinstance(identity,tuple) else (identity,)))
        row.update(n_inventory_records=len(frame),n_inventory_images=frame.image_id.nunique(),
            n_inventory_workers=frame.worker_id.nunique(),n_source_records=len(accepted),
            n_source_images=accepted.image_id.nunique(),n_source_workers=accepted.worker_id.nunique(),
            n_quality_records=int(frame.B8L2.notna().sum()),n_excluded_records=len(frame)-len(accepted),
            n_inventory_usable_time=int(frame.source_active_time_seconds.notna().sum()),
            n_source_time=int(frame.active_time_seconds.notna().sum()),
            n_target_time=int(frame.target_matched_time_seconds.notna().sum()),
            conditions='|'.join(sorted(frame.condition.unique())),source_exclusion_reasons=reasons,
            quality_exclusion_reasons=quality_reasons,lookup_table='record_lookup.csv')
        for condition in ['manual','semi','oos']:
            cell=frame[frame.condition.eq(condition)]
            row['inventory_'+condition]=len(cell)
            row['source_'+condition]=int(cell.pool_analysis_eligible.sum())
            row['quality_'+condition]=int(cell.B8L2.notna().sum())
        output.append(row)
    return pd.DataFrame(output)


def build_detail_tables(records,bundle,*,adoption=None):
    from .b8l2_room_descriptions_20261016 import build_room_descriptions
    records=records.copy()
    assert records.object_id.nunique()==len(records)
    assert records.loc[~records.pool_analysis_eligible,list(METRICS)].isna().all().all()
    records['comparison_stratum']=np.where(records.ordinary_difficulty_eligible,
        'ordinary_'+records.difficulty_class,np.where(records.pool_analysis_eligible,
        'special_or_pending','inventory_excluded'))
    tables=dict(worker_inventory=inventory_overview(records,'worker_id'),
        image_inventory=inventory_overview(records,['image_id','image_code']),
        worker_condition_stats=grouped_summary(records,['worker_id','condition','analysis_layer']),
        image_condition_stats=grouped_summary(records,['image_id','image_code','condition']))
    contexts=records[['image_id','difficulty_class','current_target_id','difficulty_analysis_eligible',
        'difficulty_analysis_exclusion','doorway_status','oos_subtype','scene']].drop_duplicates()
    tables['image_inventory']=tables['image_inventory'].merge(contexts,on='image_id',validate='one_to_one')
    worker_difficulty=[]
    axes=[]
    for (worker,condition),frame in records.groupby(['worker_id','condition'],sort=True):
        for level in ['ordinary_简单','ordinary_中等','ordinary_困难','special_or_pending','inventory_excluded']:
            summary=summarize_group(frame[frame.comparison_stratum.eq(level)])
            worker_difficulty.append(dict(worker_id=worker,condition=condition,comparison_stratum=level,
                cell_status=cell_status(summary),**summary))
        for layer,layer_frame in frame.groupby('analysis_layer',sort=True):
            for axis,levels in [('doorway_status',['none','annotatable','difficult','suspected_user_review','not_recorded']),
                ('oos_subtype',['not_oos','nonorthogonal_annotatable','subtype_not_resolved','suspected_user_review','not_recorded']),
                ('scene',sorted(layer_frame.scene.unique()))]:
                unknown=set(layer_frame[axis].unique())-set(levels)
                assert not unknown,(axis,unknown)
                for level in levels:
                    summary=summarize_group(layer_frame[layer_frame[axis].eq(level)])
                    axes.append(dict(worker_id=worker,condition=condition,analysis_layer=layer,axis=axis,level=level,
                        cell_status=cell_status(summary),**summary))
    tables['worker_difficulty']=pd.DataFrame(worker_difficulty)
    tables['worker_special_axes']=pd.DataFrame(axes)
    tables['difficulty_overview']=grouped_summary(records,['condition','comparison_stratum'])
    tables['time_quality_focus']=tables['worker_difficulty'].copy()
    lookup=['object_id','image_id','image_code','worker_id','condition','difficulty_class',
        'analysis_layer','comparison_stratum','pool_analysis_eligible','current_quality_eligible','quality_use',
        'pool_source_workers','B8L2','active_time_seconds','target_matched_time_seconds','source_active_time_seconds',
        'time_status','target_time_interpretation','pool_analysis_exclusion_reasons','quality_exclusion_reasons',
        'doorway_status','oos_subtype','scene','current_target_id','reference_id','reference_version','input_version','B8L2_version']
    lookup += [c for c in ['usage_version','previous_usage_quality_eligible','quality_usable',
        'is_doorway','is_oos','scene_bucket','calculation_status','full_score_state',
        'input_geometry_status','full_input_available','floor_input_available','target_binding_unique',
        'reference_full_available','diagnostic_B8L2','diagnostic_WQ','diagnostic_A10',
        'diagnostic_IoU3D100','diagnostic_iou_2d','diagnostic_floor_iou','purpose_bypass'] if c in records]
    tables['record_lookup']=records[lookup]
    tables.update({k:v if isinstance(v,pd.DataFrame) else pd.DataFrame(v)
        for k,v in build_room_descriptions(records,bundle,adoption=adoption).items()})
    return tables


def coverage_rows():
    return [dict(requirement=a,status=b,file=c,worksheet=d,limitation=e) for a,b,c,d,e in [
        ('每名库存人员，包括未分析人员','已做','worker_inventory.csv','01_27人库存','总览仅计数；质量/时间按condition另表，不跨条件混均分'),
        ('每名人员的质量与时间分布','已做','worker_condition_stats.csv','03_人员分条件','B8L2和两类秒分别n/mean/median/sd；任务组成不是纯能力'),
        ('每张图片，包括排除和未评分','已做','image_inventory.csv;image_condition_stats.csv','02_259图库存;04_图片分条件','保留全部259图与实际有记录条件'),
        ('简单/中等/困难/专项的人员差异','已做','worker_difficulty.csv','05_人员难度专项','只展开用户要求的四层及库存排除；无观察格n=0、均值留空'),
        ('人员×门洞可标性/OOS','已做','worker_special_axes.csv','06_人员特殊轴','未记录不当正常；轴可重叠，不跨轴相加'),
        ('时间均值/中位数/离散与实际质量时间共有n','已做','time_quality_focus.csv','07_质量时间共有','边际和共同有效集合分开，秒；不以lead_time补值'),
        ('每个物理房间的稳定唯一身份与总体','缺数据','ROOM_SEMANTICS.md;room_group_registry.csv','证据组登记','G来自候选编号，不是物理房间ID；不借传递闭包认证房间'),
        ('有证据的关系组/直接图对总体','已做','room_group_summary.csv;room_direct_pair_summary.csv','08_关系组总体;直接图对','组证据分层、可重叠；作答等权与视角等权分开'),
        ('人员×物理房间','缺数据','ROOM_SEMANTICS.md','证据组登记','缺完整可靠房间身份；下行交付可核查替代而非冒称已认证房间'),
        ('人员×关系组及逐视角贡献','已做','room_worker_groups.csv;room_group_views.csv','09_人员关系组;组视角贡献','不把多视角当独立人员，重叠组不能相加'),
        ('未有关系证据图片与组成员缺失定位','已做','room_unlinked_images.csv;room_group_registry.csv','未关联图片;证据组登记','缺关系不等于已确认不同房间'),
        ('原始库存对象排除/无评分定位','已做','record_lookup.csv','10_作答定位','3152唯一object_id，保留条件、源人数、排除原因、时间与版本'),
        ('e9-16简单但普通资格未开来源核对','已做','E9Z16_ELIGIBILITY_AUDIT.md','导读/说明','旧表示适用性问题被单向保留；本轮不径改冻结资格'),
        ('原图表与WQ/A10/IoU同集合对照','已做','../figures/FIGURES.md;../algorithm_comparisons.csv','原35页工作簿','本次补查阅表，不重评分、不重训人员或做新预测')]]


def run(source=SOURCE,*,out=None,adoption_manifest=None):
    source=source.resolve()
    out=(out or source/'details').resolve()
    if adoption_manifest:adoption_manifest=adoption_manifest.resolve()
    payload=json.loads((source/'tables.json').read_text(encoding='utf-8'))
    records=pd.DataFrame(payload['shared_records'])
    freeze_path=source/'FROZEN_INPUTS.json'
    if not freeze_path.exists():
        cross=json.loads((source/'CROSS_MODULE_INPUTS.json').read_text(encoding='utf-8'))
        freeze_path=ROOT/cross['input_freeze']
    fixed=json.loads(freeze_path.read_text(encoding='utf-8'))
    assert fixed['version']=='b8l2_shared_v6_20261016_v1'
    adoption=None
    if adoption_manifest:
        manifest=json.loads(adoption_manifest.read_text(encoding='utf-8'))
        assert manifest['status'] in ('ready_for_same_room_and_statistics_consumers','frozen_for_same_room_and_statistics_consumers')
        adoption=dict(version=manifest['version'],
            **{key:json.loads((ROOT/manifest[path]).read_text(encoding='utf-8'))
               for key,path in [('groups','original_groups'),('candidates','candidate_adoption'),('relations','relations')]})
        assert out.resolve()!=(source/'details').resolve(), 'preserve old strict relation tables separately'
    tables=build_detail_tables(records,fixed['bundle'],adoption=adoption)
    for name in ['record_reason_audit','worker_usage_summary','worker_primary_reasons',
        'worker_reason_hits','worker_scene_usage','scene_usage','worker_calculation_status','calculation_ledger']:
        if name in payload:
            tables[name]=pd.DataFrame(payload[name])
    tables['coverage_matrix']=pd.DataFrame(coverage_rows())
    if 'quality_usable' in records:
        assert not (records.is_oos & records.quality_usable).any()
        assert records.loc[records.is_oos,'B8L2'].isna().all()
        tables['coverage_matrix'].loc[tables['coverage_matrix'].requirement.eq('原图表与WQ/A10/IoU同集合对照'),
            ['file','worksheet','limitation']]=['../figures/FIGURES.md;../algorithm_comparisons.csv',
                '父级科研图/对照CSV','新用途版同集合比较；原35页工作簿保留为旧用途历史，不随本轮改写']
        extra=[('3152份实际计算状态与诊断值','calculation_ledger.csv','16_逐条计算状态',
                '未运行、输入不可算、待目标/参考及实测失败分开；OOS诊断不进入质量均值'),
               ('27人用途覆盖及排除比例','worker_usage_summary.csv','17_27人用途排除',
                '以各人全部提交为分母；质量不可用不删除合法时间'),
               ('门洞/OOS互斥场景覆盖','scene_usage.csv','18_场景计算覆盖',
                '门洞独有/OOS独有/两者/均未标记可相加；condition另轴'),
               ('互斥主原因与多重原因命中','worker_primary_reasons.csv;worker_reason_hits.csv',
                '19_互斥主原因;20_多重原因命中','主原因按公开优先级；多重原因不能相加为排除人数')]
        tables['coverage_matrix']=pd.concat([tables['coverage_matrix'],pd.DataFrame([
            dict(requirement=a,status='已做',file=b,worksheet=c,limitation=d) for a,b,c,d in extra])],ignore_index=True)
    if adoption:
        coverage=tables['coverage_matrix']
        coverage.loc[coverage.requirement.eq('每个物理房间的稳定唯一身份与总体'),
            ['requirement','status','file','worksheet','limitation']]=[
            '按已有人工分类的每房/工作分组总体','已做','room_group_summary.csv;user_original_group_summary.csv',
            '08_用户工作分组;21_人工原组总体','版本化工作分组足以统计；原组、拆分/合并单元分表，重叠不相加']
        coverage.loc[coverage.requirement.eq('人员×物理房间'),
            ['requirement','status','file','worksheet','limitation']]=[
            '人员×已有人工房间/工作分组','已做','room_worker_groups.csv;user_original_worker_groups.csv',
            '09_人员房间分组;22_人员人工原组','不以单独确认状态或全库物理ID作为门；实际否定/范围不同/争议仍分层']
        coverage.loc[coverage.requirement.eq('有证据的关系组/直接图对总体'),['worksheet','limitation']]=[
            '08_用户工作分组;14_采用关系图对','采用同房线程统一关系版本；原组直接边及明确合组，不作跨组传递']
        coverage.loc[coverage.requirement.eq('人员×关系组及逐视角贡献'),'worksheet']='09_人员房间分组;12_分组视角贡献'
        coverage.loc[coverage.requirement.eq('未有关系证据图片与组成员缺失定位'),'worksheet']='13_未关联图片;11_分类采用登记;23_人工原组登记'
    out.mkdir(exist_ok=True)
    columns={}
    for name,frame in tables.items():
        output=frame.copy()
        for column in output:
            output[column]=output[column].map(lambda x:json.dumps(x,ensure_ascii=False) if isinstance(x,(dict,list,tuple)) else x)
        output.to_csv(out/(name+'.csv'),index=False,encoding='utf-8-sig')
        columns[name]=dict(rows=len(frame),columns=list(frame.columns))
    (out/'tables.json').write_text(json.dumps({k:json.loads(v.to_json(orient='records',force_ascii=False))
        for k,v in tables.items()},ensure_ascii=False,allow_nan=False),encoding='utf-8')
    detail_version='b8l2_detailed_views_20261016_v3' if adoption else VERSION
    checks=dict(version=detail_version,input_version=fixed['version'],usage_version=records.usage_version.iloc[0] if 'usage_version' in records else None,difficulty_version=fixed['difficulty']['version'],
        inventory_records=len(records),inventory_workers=records.worker_id.nunique(),
        analyzed_workers=records[records.pool_analysis_eligible].worker_id.nunique(),
        inventory_images=records.image_id.nunique(),quality_rows=int(records.B8L2.notna().sum()),
        source_time_rows=int(records.active_time_seconds.notna().sum()),
        target_time_rows=int(records.target_matched_time_seconds.notna().sum()),
        quality_source_time_rows=int((records.B8L2.notna() & records.active_time_seconds.notna()).sum()),
        quality_target_time_rows=int((records.B8L2.notna() & records.target_matched_time_seconds.notna()).sum()),
        original_scores_or_gates_changed=False,new_physical_rooms_inferred=False,tables={k:len(v) for k,v in tables.items()})
    if adoption:
        checks.update(relation_adoption_version=adoption['version'],
            original_user_groups=len(adoption['groups']),all_user_groups_viewed=True,
            classified_working_groups=len(adoption['candidates']),direct_relation_pairs=len(adoption['relations']),
            stable_physical_room_id_required=False,review_status_used_as_gate=False,
            old_strict_snapshot=str((source/'details').relative_to(ROOT)))
        (out/'RELATION_ADOPTION_INPUTS.json').write_text(json.dumps(dict(manifest=manifest,**adoption),
            ensure_ascii=False),encoding='utf-8')
        archived=out/'relation_inputs';archived.mkdir(exist_ok=True)
        (archived/'CROSS_MODULE_RELATIONS.json').write_bytes(adoption_manifest.read_bytes())
        for key in ['original_groups','candidate_adoption','relations']:
            (archived/(key+'.json')).write_bytes((ROOT/manifest[key]).read_bytes())
    (out/'CHECKS.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2),encoding='utf-8')
    contract=dict(version=detail_version,input_version=fixed['version'],score_version='WQ-B8L2-20261015',
        metrics=METRICS,time_units='seconds',quality_mask='parent snapshot numeric masks; usage version read from CHECKS.json',
        n_inventory_records='all original annotations in slice, including excluded',
        n_source_records='parent pool_analysis_eligible; independent of metric coverage',
        n_quality_missing='source records minus nonmissing B8L2',
        missing='no observations: n=0, estimates null; no zero imputation',
        conditions='summarize manual/semi/oos separately; inventory-only overviews contain counts, not cross-condition means',
        weighting='*_mean: answers equally weighted; *_image_equal_mean: valid image means equally weighted, missing views not filled',
        dispersion='sample SD ddof=1; n<2 null; quartiles linear interpolation',
        common='quality_source_time_n and quality_target_time_n are actual nonmissing intersections, each with own B8L2/seconds estimates',
        axes='not_recorded is not absence; scene, doorway and OOS axes overlap and cannot be summed',
        room='candidate-derived groups and direct pairs preserve evidence; no transitive physical-room inference',
        tables=columns)
    if adoption:
        contract.update(relation_adoption_version=adoption['version'],
            relation_source=str(adoption_manifest.relative_to(ROOT)),
            room='existing complete user classifications and retained split/merge groups; status is provenance, no unique global physical ID gate',
            original_vs_subgroup='original group and working subgroup summaries are separate overlapping views, never additive',
            no_current_inventory='explicit n=0 summary with condition/analysis_layer=no_current_inventory; no metric imputation')
    (out/'FIELD_CONTRACT.json').write_text(json.dumps(contract,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(checks,ensure_ascii=False,indent=2))
    return tables,checks


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-dir',type=Path,default=SOURCE)
    parser.add_argument('--out-dir',type=Path)
    parser.add_argument('--relation-adoption',type=Path)
    args=parser.parse_args()
    run(args.source_dir,out=args.out_dir,adoption_manifest=args.relation_adoption)
