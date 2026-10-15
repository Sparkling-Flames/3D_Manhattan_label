"""CURRENT难度、来源池至少3真人及当前参考下的新版统计；保留旧快照。"""
import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from ..data_prep.consolidate_research_input import load_current_bundle
from .descriptive_inventory_20261015 import load_inventory
from .descriptive_pool_gate_20261015 import build_pool_gate, RULE, RULE_VERSION
from .descriptive_reference_audit_20261015 import audit_references
from .descriptive_same_room_20261015 import build_same_room_tables
from .descriptive_statistics_20261015 import ROOT, describe

OUT = ROOT/'research/statistics/descriptive_statistics_current_20261015'
OLD = ROOT/'research/statistics/descriptive_statistics_20261015'
POINTER = ROOT/'analysis_results/image_difficulty_full_review_20261010/CURRENT.json'
QUALITY_METRICS = ['WQ','A10','B8L2','IoU3D100','iou_2d','S_bottom_deg','dir','Hmean','Hcenter']
METRICS = QUALITY_METRICS + ['active_time_seconds', 'target_matched_time_seconds']


def truth(values):
    return values.isin([True, 'True'])


def apply_metric_gates(records):
    """人数/旧限制/参考逐层相交；旧数值只进入历史字段，不换标签复用。"""
    result = records.copy()
    legacy_hold = pd.Series(False, index=result.index)
    for key in ['same_target_quality_hold','latest_step_reference_pending','original_holdout','same_target_unconfirmed']:
        legacy_hold |= truth(result[key])
    role_allowed = result.role.isin(['manual_development_candidate','semi_secondary_candidate'])
    result['legacy_quality_restriction_clear'] = role_allowed & ~legacy_hold
    result['current_quality_eligible'] = (result.pool_analysis_eligible & result.reuse_full_quality &
                                          result.legacy_quality_restriction_clear)
    for metric in QUALITY_METRICS:
        result['historical_'+metric] = pd.to_numeric(result[metric], errors='raise')
        result[metric] = result['historical_'+metric].where(result.current_quality_eligible)
    result['source_active_time_seconds'] = result.active_time_seconds
    result['active_time_seconds'] = result.active_time_seconds.where(result.pool_analysis_eligible)
    # 新空间或修订目标的逐作答匹配未知，不能把采集时旧任务耗时当作新目标耗时。
    target_time = result.current_quality_eligible
    result['target_matched_time_seconds'] = result.active_time_seconds.where(target_time)
    result['target_time_interpretation'] = np.where(target_time, 'audited_current_reference_and_legacy_restrictions_clear',
                                                   'current_target_comparability_not_established')
    return result


def summarize(panels, dimensions):
    output=[]
    for panel_name, panel in panels.items():
        groups = panel.groupby(dimensions, dropna=False, sort=True) if dimensions else [((),panel)]
        for keys, cell in groups:
            keys = keys if isinstance(keys,tuple) else (keys,)
            output.extend(dict(panel=panel_name, **dict(zip(dimensions,keys)), **describe(cell,metric))
                          for metric in METRICS)
    return pd.DataFrame(output)


def rebuild_metric_tables(tables):
    """按已更新record_audit重建描述统计；不改门槛、不重新评分、不写文件。"""
    audit=tables['record_audit']
    pools=tables['source_pools']
    analysis=audit[audit.pool_analysis_eligible].copy()
    assert not analysis.duplicated(['image_id','condition','worker_id']).any(), 'resolve duplicate canonical responses before empirical summaries'
    ordinary=analysis[analysis.ordinary_difficulty_eligible]
    special=analysis[~analysis.ordinary_difficulty_eligible]
    panels={}
    for name,frame in [('ordinary',ordinary),('special',special)]:
        for condition in ['manual','semi','oos']:
            cell=frame[frame.condition.eq(condition)]
            if len(cell):panels[name+'_'+condition]=cell
    tables.update(analysis_records=analysis,
        quality_records=analysis[analysis.current_quality_eligible], overview=summarize(panels,[]))
    old_members=tables['historical_panel_changes'].set_index('object_id')
    comparison=audit[['object_id','image_id','image_code','worker_id','condition','pool_source_workers',
        'pool_analysis_eligible','ordinary_difficulty_eligible','current_quality_eligible',
        'pool_analysis_exclusion_reasons','reference_audit_reasons','legacy_quality_restriction_clear']].copy()
    comparison['historical_target_836']=comparison.object_id.map(old_members.historical_target_836)
    comparison['historical_worker_931']=comparison.object_id.map(old_members.historical_worker_931)
    comparison['current_manual_ordinary_quality']=(comparison.condition.eq('manual') &
        comparison.current_quality_eligible & comparison.ordinary_difficulty_eligible)
    comparison['target_panel_change']=np.select(
        [comparison.historical_target_836 & comparison.current_manual_ordinary_quality,
         comparison.historical_target_836 & ~comparison.current_manual_ordinary_quality,
         ~comparison.historical_target_836 & comparison.current_manual_ordinary_quality],
        ['retained','removed','added'],default='outside_both_target_panels')
    tables['historical_panel_changes']=comparison
    for key,dimensions in [('by_difficulty',['difficulty_class']),('by_worker',['worker_id']),
        ('by_building',['building_id']),('by_condition',['condition']),('by_scene',['scene','doorway_status','oos_subtype'])]:
        tables[key]=summarize(panels if key!='by_difficulty' else {k:v for k,v in panels.items() if k.startswith('ordinary_')},dimensions)
    tables['population_distribution']=pools.groupby(['condition','n_effective_workers','pool_analysis_eligible',
        'ordinary_difficulty_eligible'],dropna=False).size().rename('n_source_pools').reset_index()
    intersections=pools[pools.n_annotation_records>0].copy()
    intersections['reason_combination']=intersections.pool_exclusion_reasons.map(lambda x:'|'.join(x) or 'none')
    tables['exclusion_intersections']=intersections.groupby(['condition','reason_combination'],dropna=False).agg(
        n_source_pools=('image_id','size'),n_records=('n_annotation_records','sum')).reset_index()
    coverage=[]
    for (image,condition),cell in analysis.groupby(['image_id','condition']):
        for metric in METRICS:
            coverage.append(dict(image_id=image,image_code=cell.image_code.iloc[0],condition=condition,
                n_pool_workers=int(cell.pool_source_workers.iloc[0]), **describe(cell,metric)))
    tables['metric_coverage']=pd.DataFrame(coverage)
    peers=[]
    for (condition,image,reference),cell in tables['quality_records'].groupby(['condition','image_id','reference_id']):
        for metric in ['WQ','A10','B8L2']:
            for _,row in cell.iterrows():
                others=cell[cell.worker_id.ne(row.worker_id)][metric].dropna()
                peers.append(dict(object_id=row.object_id,worker_id=row.worker_id,image_id=image,
                    condition=condition,reference_id=reference,metric=metric,n_peers=len(others),
                    value=row[metric],peer_mean=others.mean(),difference=row[metric]-others.mean()))
    tables['peer_comparisons']=pd.DataFrame(peers)
    # 来源池合格不要求图对共同人员也>=3；共同人数逐指标另报。
    manual=ordinary[ordinary.condition.eq('manual')].copy()
    assert not manual.duplicated(['image_id','worker_id']).any()
    manual=manual.assign(object_uid=manual.object_id,iou_3d=manual.IoU3D100/100)
    room=build_same_room_tables(manual.replace({np.nan:None}).to_dict('records'))
    tables['same_room_relations']=pd.DataFrame(room['same_room_relations'])
    tables['same_room_pairs']=pd.DataFrame(room['same_room_pair_metrics'])
    tables['same_room_worker_pairs']=pd.DataFrame(room['same_room_worker_pairs'])
    scores=[]
    for name,panel in panels.items():
        for other in ['A10','B8L2','IoU3D100']:
            cell=panel.dropna(subset=['WQ',other]).copy();cell['difference']=cell[other]-cell.WQ
            scores.append(dict(panel=name,comparison=other+'-WQ',**describe(cell,'difference')))
    tables['algorithm_comparisons']=pd.DataFrame(scores)


def build_tables():
    pointer=json.loads(POINTER.read_text(encoding='utf-8-sig'))
    details_path=(POINTER.parent/pointer['details']).resolve()
    difficulty=json.loads(details_path.read_text(encoding='utf-8-sig'))
    assert difficulty['version']==pointer['version']
    bundle=load_current_bundle()
    inventory=pd.DataFrame(load_inventory(bundle)).rename(columns={'record_id':'inventory_record_id'})
    old=pd.read_csv(OLD/'records.csv',dtype=str,keep_default_na=False)
    assert set(inventory.object_id)==set(old.object_id), 'new inventory needs explicit batch/source audit'
    pools,gates=build_pool_gate(bundle,difficulty['records'])
    images,bindings=audit_references(bundle,difficulty['records'],old.to_dict('records'))
    pools=pd.DataFrame(pools);images=pd.DataFrame(images);bindings=pd.DataFrame(bindings)
    extra=['record_id','reference_id','role','stage','score_version','use_panel','same_target_quality_hold',
           'latest_step_reference_pending','original_holdout','same_target_unconfirmed','personnel_barriers',
           'context_barriers','target_floor_relation','input_geometry_unchanged','reference_geometry_unchanged',
           'input_geometry_available','annotation_identity_unchanged','complete_target_coordinates_equal',
           'full_reference_compatible','existing_full_quality_available','reuse_full_quality',
           'quality_audit_status','reasons']+QUALITY_METRICS
    audit=inventory.merge(bindings[['object_id']+extra],on='object_id',validate='one_to_one')
    audit=audit.rename(columns={'use_panel':'historical_use_panel','reasons':'reference_audit_reasons'})
    gate_frame=pd.DataFrame(gates)
    assert len(gate_frame)==len(inventory)
    audit=audit.merge(gate_frame.drop(columns=['image_id','condition','worker_id']),on='object_id',validate='one_to_one')
    image_fields=[c for c in images if c not in audit or c=='image_id']
    audit=audit.merge(images[image_fields],on='image_id',validate='many_to_one')
    d={r['image_id']:r for r in difficulty['records']}
    for column, field in [('difficulty_class','current_class'),('doorway_status','doorway_status'),
                          ('oos_subtype','oos_subtype'),('scene','scene'),('review_disagreement','review_disagreement')]:
        images[column]=images.image_id.map(lambda i: d[i].get(field))
        audit[column]=audit.image_id.map(images.set_index('image_id')[column])
    audit['difficulty_version']=difficulty['version']
    audit=apply_metric_gates(audit)
    audit['analysis_layer']=np.where(audit.ordinary_difficulty_eligible,'ordinary_current',
        np.where(audit.pool_analysis_eligible,'special_or_pending_separate','held_inventory_only'))
    audit['use_panel']=audit.analysis_layer
    tables=dict(inventory_all=inventory,source_pools=pools,current_images=images,record_audit=audit,
        pending_people=pools[(pools.n_annotation_records>0)&~pools.pool_min3_pass],
        pending_rescore=audit[audit.existing_full_quality_available & ~audit.reuse_full_quality])
    old_members=old.set_index('object_id')
    historical=audit[['object_id']].copy()
    historical['historical_target_836']=historical.object_id.map(truth(old_members.in_target_836))
    historical['historical_worker_931']=historical.object_id.map(truth(old_members.in_worker_931))
    tables['historical_panel_changes']=historical
    rebuild_metric_tables(tables)
    analysis=tables['analysis_records']
    checks=dict(difficulty_version=difficulty['version'],source_pool_rule=RULE_VERSION,
        inventory_rows=len(inventory),inventory_images=inventory.image_id.nunique(),
        difficulty_candidates=sum(r['difficulty_analysis_eligible'] for r in difficulty['records']),
        new_space_images=int(images.new_space_target.sum()),all_target_sources_verified=bool(images.target_source_verified.all()),
        historical_quality_rows=int(audit.existing_full_quality_available.sum()),
        reusable_geometry_rows=int(audit.reuse_full_quality.sum()),pending_rescore_rows=len(tables['pending_rescore']),
        analysis_rows=len(analysis),quality_rows=len(tables['quality_records']),
        source_pool_min3=int(pools.pool_min3_pass.sum()),source_pool_after_image_gate=int(pools.pool_analysis_eligible.sum()),
        ordinary_source_pools=int(pools.ordinary_difficulty_eligible.sum()),formal_eligibility_changed=False,
        new_scores_computed=False,trajectory_k1_k2_removed=False,history_overwritten=False)
    assert analysis.pool_source_workers.ge(3).all()
    assert not analysis.gt_error_excluded.any()
    assert audit.loc[~audit.pool_analysis_eligible,'WQ'].isna().all()
    assert audit.loc[audit.new_space_target,'WQ'].isna().all()
    return tables,checks


def write(tables,checks,out):
    prior=out/'FIELD_CONTRACT.json'
    if prior.exists():
        previous=json.loads(prior.read_text(encoding='utf-8'))
        if previous['difficulty_version']!=checks['difficulty_version'] or previous['pool_rule_version']!=checks['source_pool_rule']:
            raise ValueError('difficulty/pool rule changed: choose a new snapshot output directory')
    out.mkdir(parents=True,exist_ok=True)
    schema={}
    for name,frame in tables.items():
        output=frame.copy()
        for column in output:
            output[column]=output[column].map(lambda x:json.dumps(x,ensure_ascii=False) if isinstance(x,(dict,list,tuple)) else x)
        output.to_csv(out/(name+'.csv'),index=False,encoding='utf-8-sig')
        schema[name]=dict(rows=len(output),columns=list(output.columns))
    payload={key:json.loads(value.to_json(orient='records',force_ascii=False)) for key,value in tables.items()}
    (out/'tables.json').write_text(json.dumps(payload,ensure_ascii=False,allow_nan=False),encoding='utf-8')
    (out/'CHECKS.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2),encoding='utf-8')
    contract=dict(version='descriptive_statistics_current_20261015_v1',difficulty_pointer=str(POINTER.relative_to(ROOT)),
        difficulty_version=checks['difficulty_version'],pool_rule=RULE,pool_rule_version=RULE_VERSION,
        metrics=METRICS,score_versions={'WQ':'WQ-LS08-20261014','A10':'WQ-A10-20261015','B8L2':'WQ-B8L2-20261015'},
        iou_units={'IoU3D100':'0-100; mean-height prism','same_room_iou_3d':'0-1'},
        time_units='seconds; source collection time separate from unresolved new-target time',
        missing='blank/null never zero; historical_* are old-bound-reference numbers',
        quality_eligibility='pool >=3 + inherited image/person restrictions + same complete current reference + legacy quality barriers clear',
        source_pool_vs_metric='n_pool_workers is not n_valid metric workers; common workers separate',
        trajectory='qualified source pools keep existing k=1/2 observations',tables=schema)
    (out/'FIELD_CONTRACT.json').write_text(json.dumps(contract,ensure_ascii=False,indent=2),encoding='utf-8')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--out',type=Path,default=OUT)
    args=parser.parse_args();tables,checks=build_tables();write(tables,checks,args.out)
    from .descriptive_statistics_current_report_20261015 import write_report
    write_report(tables,checks,args.out)
    print(json.dumps(checks,ensure_ascii=False))
