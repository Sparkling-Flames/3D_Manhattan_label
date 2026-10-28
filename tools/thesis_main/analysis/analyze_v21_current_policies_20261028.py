"""当前楼外角色：复用原成对整路径统计、共同人数点和独立建筑bootstrap。"""
import argparse
import importlib.util
import json
import sys
import types
from pathlib import Path
import numpy as np
import pandas as pd
from .rebuild_v21_20261028 import OUT,read
from .prepare_v21_natural_inputs_20261028 import EXT,PRIOR

SOURCE=EXT/'analysis_policy26'
TARGET=OUT/'current_policy_results'


def atomic_binary(path,payload):
    # Windows CRT默认文本模式会破坏gzip/npz字节；原统计计算保持。
    path=Path(path);temporary=path.with_name(path.name+'.writing')
    temporary.write_bytes(payload);temporary.replace(path)


def native_module(added=False):
    sys.path.insert(0,str(SOURCE))
    spec=importlib.util.spec_from_file_location('adopted_policy_functions_20261025',SOURCE/'adopted_policy_functions_20261025.py')
    f=importlib.util.module_from_spec(spec);spec.loader.exec_module(f);sys.modules[spec.name]=f
    path=SOURCE/'analyze_policy32.py';code=path.read_text(encoding='utf8')
    if added:
        for old,new in [('old16','added_first16'),('new16','added_second16'),('pooled32','added32')]:code=code.replace(old,new)
    module=types.ModuleType('v21_policy_statistics');module.__file__=str(path)
    exec(compile(code,str(path),'exec'),module.__dict__)
    module.atomic_bytes=atomic_binary
    return module


def main(cohort):
    assert (OUT/'current_policy_inputs/CHECKS.json').exists()
    added=cohort=='added_reference32';native=native_module(added);F=native.F
    capacity=pd.read_csv(OUT/'current_policy_design/POOL_ROLE_CAPACITY.csv')
    orders=pd.read_csv(OUT/'current_policy_design/ORDERS.csv.gz')
    allowed=set(capacity[capacity.eligible].groupby('pool_id').size().loc[lambda x:x==4].index)
    requested=orders[orders.base_batch.eq('added32' if added else 'new16')].drop_duplicates('pool_id')
    meta=requested[requested.pool_id.isin(allowed)&requested.layer.eq('ordinary_manual')][F.META].sort_values('pool_id').reset_index(drop=True)
    out=TARGET/cohort;(out/'analysis_policy26').mkdir(parents=True,exist_ok=True)
    requested.assign(all_four_current_roles=requested.pool_id.isin(allowed)).to_csv(out/'CAPACITY_COHORT.csv',index=False,encoding='utf-8-sig')
    meta.to_csv(out/'analysis_policy26/COMMON_IMAGES.csv',index=False,encoding='utf-8-sig')
    def inputs(base,pid):
        d=pd.read_csv(OUT/'current_policy_inputs'/(pid+'.csv.gz'),low_memory=False)
        if added:
            d=d[d.base_batch.eq('added32')].copy();idx=d.base_path_id.str.rsplit('__new256_',n=1).str[-1].astype(int)
            d['analysis_source']=np.where(idx<16,'added_first16','added_second16');d['legacy_batch']=d.analysis_source
        else:
            d=d[d.base_batch.isin(['old8','prior_new8','new16'])].copy()
            d['analysis_source']=np.where(d.base_batch.eq('new16'),'new16','old16');d['legacy_batch']=d.base_batch
        return native.legalize(d)
    native.input_for_pool=inputs
    if added:
        support=[]
        for r in meta.itertuples():
            ks=np.arange(1,int(r.pool_n)+1);masks=F.phase_masks(ks,int(r.pool_n))
            for policy in F.POLICIES:
                for phase,mask in zip(F.PHASES,masks):
                    for metric in native.ADOPTED_METRICS:support.append(dict(pool_id=r.pool_id,policy=policy,phase=phase,metric=metric,fixed_k_list='|'.join(map(str,ks[mask]))))
        support=pd.DataFrame(support).set_index(['pool_id','policy','phase','metric'])
    else:
        support=pd.read_csv(PRIOR/'local_audit/policy/FIXED_K_SUPPORT.csv.gz',keep_default_na=False)
        support=support[support.batch.eq('combined16')].set_index(['pool_id','policy','phase','metric'])
    for i,row in meta.iterrows():
        assert native.analyze_pool(out,row,support,2000,native.DEFAULT_SEED)
        part=out/'analysis_policy26/parts'/row.pool_id
        per_k=pd.read_csv(part/'POLICY_IMAGE_K.csv.gz')
        per_k['execution_status']=np.where(per_k.k.eq(2),'not_executed_policy_k2','executed')
        per_k.loc[per_k.k.eq(2),F.METRICS]=np.nan
        native.save(per_k,part/'POLICY_IMAGE_K.csv.gz')
        receipt=read(part/'RECEIPT.json');receipt.update(data_release='v2.1',current_LOBO_roles=True)
        if added:receipt['support']='newly adopted references; fixed phase k intersected across first16/second16/added32'
        (part/'RECEIPT.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf8')
        print(cohort,i+1,'/',len(meta),row.pool_id,flush=True)
    native.aggregate(out,meta,2000,native.DEFAULT_SEED)
    p=out/'analysis_policy26/results/RECEIPT.json';r=read(p)
    r.update(data_release='v2.1',policy_labels='current v2.1 LOBO V3_BEHAVIOR/V3_JOINT_QT; not DSTRUCT/RFUSE',cohort=cohort)
    if added:r['support']='new-reference cohort, fixed phase k intersected across first16/second16/added32; separate from original cohort'
    p.write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf8')
    receipt=dict(data_release='v2.1',cohort=cohort,images=len(meta),buildings=meta.building.nunique(),candidate_images=len(requested),current_labels=True,actual_orders='saved_base_orders_prioritized_by_current_LOBO_roles',versions=native.VERSIONS,all_four_roles_common_support=True,k2='excluded_from_original_policy_phase_definitions',bootstrap=2000)
    (out/'CHECKS.json').write_text(json.dumps(receipt,indent=2),encoding='utf8')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('cohort',choices=['original_common32','added_reference32']);main(p.parse_args().cohort)
