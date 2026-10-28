"""复用原答表达，更新参考诊断与难度，按既有域/支持门槛重拟合楼外分类。"""
import importlib.util
import json
import numpy as np
import pandas as pd
from .rebuild_v21_20261028 import ROOT, OUT, read
from .difficulty_mechanisms_v2_20261020 import reference_traits
from .same_room_structure_transfer_20261020 import geometry_features

TARGET=OUT/'condition_classification'
CORE=ROOT/'analysis_results/personnel_exchange_discrimination_audit_20261025/unpacked/03/classifications/code/build_condition_response_classes.py'


def main():
    TARGET.mkdir(exist_ok=True)
    spec=importlib.util.spec_from_file_location('v21_condition_core',CORE);core=importlib.util.module_from_spec(spec);spec.loader.exec_module(core)
    expressions=pd.read_csv(ROOT/'research/workers/personnel_marking_patterns_20261020/record_expression.csv',low_memory=False).set_index('object_id')
    refs={r['target_id']:r for r in read(OUT/'reference_catalog.json')}
    quality={r['object_id']:r for r in read(OUT/'quality_inventory.json')}
    oldrefs={r['target_id']:r for r in read(ROOT/'research/quality/quality_workers_v2_20261019/reference_catalog.json')}
    olddiag=pd.read_csv(ROOT/'research/workers/personnel_mixture_comparison_20261022/difficulty/record_opportunity_index.csv.gz',low_memory=False).set_index('object_id')
    pools=read(OUT/'pools/INPUT_SNAPSHOT.json')['images'];raw=[];traits={}
    reused=changed=0
    for pool in pools:
        tid=pool['meta']['reference_id'];ref=refs[tid]
        if tid not in traits:traits[tid]=reference_traits(ref['floor_xz_h'])
        same=tid in oldrefs and ref['points_1024x512']==oldrefs[tid]['points_1024x512']
        for r in pool['records']:
            oid=r['object_id'];q=quality[oid];expr=expressions.loc[oid];t=traits[tid]
            fields=['unmatched_ref_9','unmatched_ref_12','bottom_bias_9','omission','extension','log_area_ratio']
            if same and oid in olddiag.index and olddiag.loc[oid,'reference_id']==tid:
                diag=olddiag.loc[oid,fields].to_dict();reused+=1
            else:
                diag=geometry_features(r['points'],ref['points_1024x512']);changed+=1
                if t['ref_geometry_status']!='valid_camera_inside':
                    diag.update({k:np.nan for k in fields})
            row=dict(object_id=oid,pool_id=pool['pool_id'],worker_id=r['worker_id'],condition=r['condition'],
                image_id=q['image_id'],image_code=q['image_code'],building=q['building_id'],origin=r['origin'],
                reference_id=tid,reference_version=ref['reference_version'],difficulty_coarse=q['current_class'],
                image_layer='doorway' if q['quality_use']=='doorway_quality' else 'non_doorway',
                pool_layer=pool['meta']['layer'],time_source=r['time_source_kind'],source_active_time_seconds=r['source_time_seconds'],
                B8L2=q['B8L2'],D10=q['D10'],turn_n=expr['pair_n']-expr['near_straight_nodes_5deg'],
                **{k:expr[k] for k in ['short_turn_edges','near_straight_nodes_5deg','log_area','log_height']},
                **{k:diag.get(k,np.nan) for k in fields},**t,
                **core.matched_boundary_features(r['points'],ref['points_1024x512']))
            raw.append(row)
    raw=pd.DataFrame(raw);assert raw.object_id.is_unique and len(raw)==8154
    raw['log_time']=np.log(raw.source_active_time_seconds.where(raw.source_active_time_seconds>0))
    for metric in core.BASE_METRICS:
        groups=['image_id','condition']+(['origin','time_source'] if metric=='log_time' else [])
        raw[metric+'_peer']=raw[metric]-raw.groupby(groups,dropna=False)[metric].transform('median')
    raw['history_eligible']=raw.image_layer.eq('non_doorway')&raw.difficulty_coarse.isin(['简单','中等','困难'])
    core.save_csv(raw,TARGET/'RAW_CONDITION_RESPONSE_RECORDS.csv.gz')
    roster=raw[['worker_id','origin']].drop_duplicates().sort_values('worker_id').reset_index(drop=True)
    for wid in ['W019','W026']:
        if wid not in set(roster.worker_id):roster.loc[len(roster)]=[wid,'v1']
    roster=roster.sort_values('worker_id').reset_index(drop=True)
    labels=[];history=[];centers=[];registrations=[];transforms={}
    for heldout in ['ALL']+sorted(raw.building.unique()):
        h=core.history(raw,roster,heldout);history.append(h)
        for family in core.FAMILIES:
            lab,center,registry,scale=core.fit_one(h,family)
            lab['underlying_data_version']='v2.1'
            labels.append(lab);centers.append(center);registrations.append(registry);transforms[heldout+':'+family]=scale
        print('condition classes',heldout,flush=True)
    lab=pd.concat(labels,ignore_index=True)
    core.save_csv(lab,TARGET/'LABELS_ALL_LOBO.csv.gz')
    core.save_csv(pd.concat(history,ignore_index=True),TARGET/'HISTORY_FEATURES_ALL_LOBO.csv.gz')
    core.save_csv(pd.concat(centers,ignore_index=True),TARGET/'CLASS_CENTERS.csv.gz')
    core.save_csv(pd.concat(registrations,ignore_index=True),TARGET/'CANDIDATE_REGISTRY.csv')
    core.save_json(transforms,TARGET/'TRANSFORMS.json')
    old=pd.read_csv(CORE.parents[3]/'01/classifications/NEW_METHOD_LABELS_ALL_LOBO.csv.gz')
    joined=lab.merge(old[['worker_id','heldout_building','method','class_id']],on=['worker_id','heldout_building','method'],how='outer',suffixes=('_v21','_v2'),indicator=True,validate='one_to_one')
    core.save_csv(joined,TARGET/'LABEL_COMPARISON.csv.gz')
    core.save_json(dict(data_release='v2.1',records=len(raw),eligible_history=int(raw.history_eligible.sum()),
        original_expression_reused=len(raw),reference_diagnostics_reused=reused,reference_diagnostics_recomputed=changed,
        no_target_building_training=True,models=list(lab.method.unique()),new_fusion=0),TARGET/'CHECKS.json')


if __name__=='__main__':main()
