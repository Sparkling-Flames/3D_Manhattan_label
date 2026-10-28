"""复用原统计定义，更新全库存质量上下文、同房比较和描述性人员画像。"""
import copy
import gzip
import json
import types
from pathlib import Path
import numpy as np
import pandas as pd
from . import v2_integrated_statistics_20261019 as native
from .rebuild_v21_20261028 import ROOT,OUT,read
from .scope_quality_scoring_20261016 import scoring_engine,score_task
from .quality_b8l2_d10_20261017 import dual_scores
from .v2_evidence_audit_20261019 import attribution,measurement_evidence

TARGET=OUT/'descriptive_statistics'
PRIOR=native.OUT


def write(path,value):
    native.write(path,native.public_value(value))


def update_semi(records,quality,refs):
    """只复算有已核实初始化和同一最终作答的成对评分。"""
    cache_path=TARGET/'INITIAL_MEASUREMENTS.jsonl'
    cached={}
    if cache_path.exists():
        for line in cache_path.read_text(encoding='utf8').splitlines():
            r=json.loads(line);cached[r['task']['object_id']]=r
    counts=dict(reused=0,recomputed=0,qualified=0,worker_attributable=0,native_measurement_records=0,inherited_exact_records=0)
    with scoring_engine() as (engine,models),cache_path.open('a',encoding='utf8') as log:
        for index,row in records[records.condition.eq('semi')].iterrows():
            q=quality[row.object_id];s=copy.deepcopy(row.semi_evidence)
            if not s.get('current_final_comparable'):continue
            ref=refs.get(q['chosen_target_id'])
            task=dict(object_id=q['object_id'],image_id=q['image_id'],worker_id=q['worker_id'],condition='semi',
                current_target_id=q['chosen_target_id'],reference_version=ref['reference_version'] if ref else None,
                annotation_points=s['initialization_points'],reference_points=ref['points_1024x512'] if ref else None,
                reference_full_available=bool(ref and ref['full_reference_available']))
            hit=cached.get(q['object_id'])
            if hit and hit['task']==task:m=hit['result'];counts['reused']+=1
            else:
                old=s.get('historical_paired_scores') or {}
                same=(s.get('paired_scores_current_adopted') and old.get('reference_id')==q['reference_id']
                    and old.get('reference_version')==q['reference_version']
                    and all(pd.notna(old.get('final_'+k)) and abs(float(old['final_'+k])-q['diagnostic_'+k])<1e-9 for k in ['B8L2','D10']))
                if same and s.get('current_initial_scores'):
                    m=dict(s['current_initial_scores'],score_status='complete');counts['reused']+=1
                else:
                    m=score_task(task,engine,models)
                    if m['score_status']=='complete':m.update(dual_scores(m,models))
                    counts['recomputed']+=1
                log.write(json.dumps(dict(task=task,result=m),ensure_ascii=False,allow_nan=False)+'\n');log.flush()
            counts['native_measurement_records' if 'metric_engine' in m else 'inherited_exact_records']+=1
            aligned=m['score_status']=='complete' and q['score_status']=='complete'
            old=s.get('historical_paired_scores') or {}
            attributable=aligned and old.get('worker_gain_attributable_under_current_view') in [True,'True','true']
            s.update(paired_scores_current_adopted=aligned,current_qualified_gain_available=bool(aligned and q['quality_usable']),
                worker_attributable_gain_available=bool(attributable and q['quality_usable']),data_release='v2.1')
            for field in ['current_initial_scores','current_project_gain','current_worker_attributable_gain']:s[field]=None
            if aligned:
                s['current_initial_scores']={k:m[k] for k in ['B8L2','D10','IoU3D100']}
                s['current_project_gain']={k:q.get('diagnostic_'+k,q.get(k))-m[k] for k in ['B8L2','D10','IoU3D100']}
                if attributable:s['current_worker_attributable_gain']=s['current_project_gain'].copy()
            records.at[index,'semi_evidence']=s
            records.at[index,'semi_current_gain_available']=s['current_qualified_gain_available']
            for k in ['B8L2','D10','IoU3D100']:
                for col,field in [('semi_initial_','current_initial_scores'),('semi_project_gain_','current_project_gain'),('semi_worker_gain_','current_worker_attributable_gain')]:
                    records.at[index,col+k]=(s.get(field) or {}).get(k)
            counts['qualified']+=int(s['current_qualified_gain_available']);counts['worker_attributable']+=int(s['worker_attributable_gain_available'])
    return counts


def build_records():
    records,bundle,objects,oldrefs,oldbindings,_=native.load_records()
    old=records.copy(deep=True)
    quality=read(OUT/'quality_inventory.json');qm={r['object_id']:r for r in quality}
    refs=read(OUT/'reference_catalog.json');rm={r['target_id']:r for r in refs}
    difficulty={r['image_id']:r for r in read(OUT/'difficulty_records.json')['records']}
    bindings={r['object_id']:r for r in read(OUT/'reference_bindings.json')}
    assert set(qm)==set(records.object_id) and len(qm)==10439
    current=pd.DataFrame(quality).set_index('object_id').loc[records.object_id].reset_index()
    current['source_active_time_seconds']=pd.to_numeric(current.source_active_time_seconds)
    for field in set(current)&set(records):
        if records[field].dtype=='bool':
            assert current[field].isin([True,False,'True','False']).all(),field
            current[field]=current[field].map(lambda x:x in [True,'True'])
    for field in set(current)&set(records):
        if field in ['object_id','image_id','worker_id','condition','pool_analysis_eligible','source_pool_eligible','source_active_time_seconds']:
            assert records[field].equals(current[field]) or all((pd.isna(a) and pd.isna(b)) or a==b for a,b in zip(records[field],current[field])),field
        records[field]=current[field]
    for metric in native.QUALITY:
        if metric not in ['B8L2','D10']:records['diagnostic_'+metric]=current[metric]
        records[metric]=records[metric].where(records.quality_usable)
    with scoring_engine() as (engine,models):
        for metric in ['WQ','A10']:
            records['legacy_formula_'+metric+'_same_measurement']=[float(models.score(*[q[k] for k in ['iou_2d','S_bottom_deg','dir','Hmean','Hcenter']],models.MODELS[metric])) if q['quality_usable'] else np.nan for q in quality]
        prior_refs={r['target_id']:r for r in oldrefs}
        for i,row in records[records.score_status.ne('complete')].iterrows():
            ref=rm.get(row.chosen_target_id)
            if ref==prior_refs.get(row.chosen_target_id):continue
            m=measurement_evidence(objects[row.object_id],qm[row.object_id],bindings[row.object_id],ref,None,engine)
            records.at[i,'calculation_class']=m['calculation_class'];records.at[i,'diagnostic_floor_iou']=m['diagnostic_floor_iou']
    for i,row in records.iterrows():
        ref=rm.get(row.chosen_target_id);d=difficulty[row.image_id]
        records.at[i,'difficulty_class']=d['current_class']
        records.at[i,'current_target_id']=d['target_version']
        records.at[i,'difficulty_reference_match']=row.chosen_target_id==d['target_version']
        records.at[i,'difficulty_target_relation']='current_image_target' if row.chosen_target_id==d['target_version'] else 'other_or_unbound'
        records.at[i,'reference_points']=ref['points_1024x512'] if ref else None
        records.at[i,'reference_full_available']=bool(ref and ref['full_reference_available'])
        records.at[i,'binding_evidence']=bindings[row.object_id]
        previous=row.exclusion_attribution
        obj=dict(objects[row.object_id],cleaning_disposition=row.cleaning_disposition,geometry=dict(status=row.geometry_status),exclusion_reason=previous.get('user_exclusion_reason'))
        records.at[i,'exclusion_attribution']=attribution(obj,qm[row.object_id],dict(legacy_explicit_person_error_exclusion=previous['legacy_explicit_person_error'],historical_worker_exclusion=previous['historical_worker_exclusion']),previous.get('candidate_evidence') or {})
        if row.score_status=='complete':
            records.at[i,'calculation_class']='full';records.at[i,'diagnostic_floor_iou']=qm[row.object_id]['iou_2d']
    # 原始作答未更改；参考更新不改变原答之间的几何分歧。
    assert records.chosen_target_id.fillna('').equals(old.chosen_target_id.fillna(''))
    semi=update_semi(records,qm,rm)
    for field in [c for c in records if '_peer_' in c or c.endswith('_rank_percentile')]:records[field]=np.nan
    records=native.contextual_quality(records)
    records['data_release']='v2.1';records['score_version']='quality_workers_v21_20261028'
    records['analysis_revision']='v21_descriptive_statistics_20261029'
    records['frozen_task_evidence_pointer']=records.evidence_pointer
    records['evidence_pointer']=records.object_id.map(lambda oid:(TARGET/'tables.json').relative_to(ROOT).as_posix()+'#/tables/quality__shared_records/object_id='+oid)
    records['fusion_or_cluster_membership_status']='see_v21_pool_and_team_receipts_not_all_inventory_used'
    old_index=old.set_index('object_id')
    unchanged=records.object_id.isin([r['object_id'] for r in quality if r['reference_version']==old_index.loc[r['object_id'],'reference_version']])
    for metric in native.QUALITY:
        both=unchanged&old.quality_usable
        assert np.allclose(records.loc[both,metric],old.loc[both,metric],atol=1e-9,equal_nan=True),metric
    assert records.B8L2.notna().equals(records.quality_usable) and records.D10.notna().equals(records.quality_usable)
    return records,refs,semi


def personnel():
    path=Path(__file__).with_name('personnel_v2_20261019.py')
    source=path.read_text(encoding='utf8').split('    payload=dict(summary=summary')[0]+'\n'
    module=types.ModuleType('tools.thesis_main.analysis.v21_personnel');module.__package__='tools.thesis_main.analysis';module.__file__=str(path)
    exec(compile(source,str(path),'exec'),module.__dict__)
    module.QUALITY=OUT;module.OUT=OUT/'personnel_descriptive';module.run()
    summary=read(module.OUT/'SUMMARY.json');summary.update(data_release='v2.1',raw_evidence_reused=True)
    summary['caveats']=[s for s in summary['caveats'] if not s.startswith('No v2 fusion')]+['描述性画像不替代当前楼外人员分类；融合/换类证据见独立专题。']
    write(module.OUT/'SUMMARY.json',summary)
    return {f'personnel_{name}':pd.read_csv(module.OUT/(name+'.csv'),low_memory=False) for name in ['profiles','difficulty_preferences','groups','reliability']}


def score_comparison():
    previous=pd.DataFrame(read(ROOT/'research/quality/quality_workers_v2_20261019/quality_inventory.json'))
    current=pd.DataFrame(read(OUT/'quality_inventory.json'))
    z=previous[['object_id','quality_usable','B8L2','D10']].merge(current[['object_id','image_id','building_id','condition','quality_use','quality_usable','B8L2','D10']],on='object_id',suffixes=('_v2','_v21'),validate='one_to_one')
    z['support']=np.select([z.quality_usable_v2&z.quality_usable_v21,z.quality_usable_v21,z.quality_usable_v2],['common','added','removed'],default='unqualified')
    rows=[]
    for (support,condition,use),g in z[z.support.ne('unqualified')].groupby(['support','condition','quality_use']):
        row=dict(support=support,condition=condition,quality_use=use,records=len(g),images=g.image_id.nunique(),buildings=g.building_id.nunique())
        for metric in ['B8L2','D10']:
            row[metric+'_v2_record_mean']=g[metric+'_v2'].mean();row[metric+'_v21_record_mean']=g[metric+'_v21'].mean()
            row[metric+'_image_equal_delta']=g.assign(delta=g[metric+'_v21']-g[metric+'_v2']).groupby('image_id').delta.mean().mean()
        rows.append(row)
    pd.DataFrame(rows).to_csv(OUT/'QUALITY_COMMON_SUPPORT_COMPARISON.csv',index=False,encoding='utf-8-sig')
    write(OUT/'QUALITY_COMPARISON_CONTRACT.json',dict(data_release='v2.1',keys=['support','condition','quality_use'],unit='Q points on 0-100 scale; counts as named',
        support='common=both versions quality usable; added=current only; removed=old only; missing version scores remain missing',
        delta='per-record difference, mean within image, then equal-image mean within the listed support/condition/use',
        source_v2='research/quality/quality_workers_v2_20261019/quality_inventory.json',source_v21='quality_inventory.json'))


def main():
    TARGET.mkdir(exist_ok=True)
    records,refs,semi=build_records();print('current records',len(records),flush=True)
    # 原导出器保留表键、粒度和字段合同；停止在旧版全项目覆盖结论之前。
    path=Path(native.__file__);source=path.read_text(encoding='utf8')
    source=source[:source.index('    coverage=coverage_rows(tables,evidence_status)')]
    source=source.replace("data_release='v2'","data_release='v2.1'")
    export=types.ModuleType('tools.thesis_main.analysis.v21_statistics_export');export.__package__='tools.thesis_main.analysis';export.__file__=str(path)
    exec(compile(source,str(path),'exec'),export.__dict__);export.OUT=TARGET;export.VERSION='v21_descriptive_statistics_20261029'
    # base_tables按原CSV合同读取三个原因列表，避免把列表当缺失标量。
    for name in ['quality_input_blockers','quality_exclusion_reasons','measurement_reasons']:
        records[name]=records[name].map(lambda x:json.dumps(x,ensure_ascii=False) if isinstance(x,list) else x)
    display_refs=[dict(r,version_alias=r.get('version_alias')) for r in refs]
    tables=native.base_tables(records,display_refs);print('base tables',len(tables),flush=True)
    tables.update(native.room_tables(records));print('direct room tables',len(tables),flush=True)
    for name in ['raw_floor_record_status','raw_answer_pairs','raw_disagreement_summary']:
        tables[name]=pd.read_csv(PRIOR/(name+'.csv'),low_memory=False)
    tables.update(personnel())
    pools=pd.DataFrame(read(OUT/'pools/INPUT_SNAPSHOT.json')['images'])
    pool_keys={(r['meta']['image_id'],r['meta']['condition'],r['meta']['reference_id']) for r in pools.to_dict('records')}
    tables['target_pool_inventory']['fusion_experiment_run']=[(r.image_id,r.condition,r.chosen_target_id) in pool_keys for r in tables['target_pool_inventory'].itertuples()]
    tables['independent_pool_inventory']=tables['independent_pool_inventory'].rename(columns={'v2_fusion_run':'v21_fusion_run'})
    pool_images={(a,b) for a,b,c in pool_keys}
    tables['independent_pool_inventory']['v21_fusion_run']=[(r.image_id,r.condition) in pool_images for r in tables['independent_pool_inventory'].itertuples()]
    checks=dict(data_release='v2.1',inventory=len(records),quality=int(records.quality_usable.sum()),ordinary_manual=int((records.quality_usable&records.condition.eq('manual')&records.quality_use.eq('ordinary_primary')).sum()),
        semi_initialization=semi,raw_geometry_and_bindings_unchanged=True,raw_pair_geometry_reused=True,tables={k:len(v) for k,v in tables.items()})
    export.export_tables(tables,checks,'original_task_evidence_reused_current_reference_scores_and_initializations_updated')
    with (TARGET/'tables.json').open('rb') as src,gzip.open(TARGET/'tables.json.gz','wb') as dst:
        import shutil
        shutil.copyfileobj(src,dst)
    contract=read(TARGET/'FIELD_CONTRACT.json')
    write(TARGET/'CONSUMER_INTERFACE.json',dict(schema='v21_descriptive_statistics_consumer_v1',data_release='v2.1',status='computed',tables=[{k:v for k,v in item.items() if k!='fields'} for item in contract['tables'].values()],
        tables_json='tables.json',tables_gzip='tables.json.gz',field_contract='FIELD_CONTRACT.json',checks='CHECKS.json',
        source_quality='../quality_inventory.json',source_references='../reference_catalog.json',source_original_evidence=str(native.EVIDENCE.relative_to(ROOT)),
        raw_pair_source=str(PRIOR.relative_to(ROOT)),no_new_raw_annotation_or_fusion=True))
    write(TARGET/'CHECKS.json',checks);score_comparison();print(json.dumps(checks,ensure_ascii=False),flush=True)


if __name__=='__main__':main()
