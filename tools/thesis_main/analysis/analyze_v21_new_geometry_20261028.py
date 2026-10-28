"""新空间同人数团队间几何V；旧池几何和成员未变，直接复用旧V。"""
import importlib.util
import itertools
import json
import sys
from concurrent.futures import ProcessPoolExecutor
import pandas as pd
from .rebuild_v21_20261028 import ROOT, OUT, read
from .prepare_v21_natural_inputs_20261028 import PRIOR, TARGET as INPUT
from .prepare_v21_new_space_curves_20261028 import load_rows
from .fuse_v21_new_pools_20261028 import TARGET as NEW, adapter

TARGET=OUT/'new_space_geometry'


def core():
    sys.path.insert(0,str(PRIOR/'analysis_geometry'))
    import geometry_sampling_precision
    return geometry_sampling_precision


def process(pool):
    pid=pool['pool_id'];destination=TARGET/(pid+'.csv')
    if destination.exists():return pid
    native=adapter();engine=native.Engine(full_state=False)
    spec=importlib.util.spec_from_file_location('v21_V_features',ROOT/'research/workers/personnel_population_curves_v2_20261023/code/run_prefix_endpoints.py')
    prefix=importlib.util.module_from_spec(spec);spec.loader.exec_module(prefix)
    rows=load_rows(NEW/pid,pool,prefix,engine.fr)
    paths=pd.read_csv(INPUT/(pid+'.csv.gz'),usecols=['team_key','k','path_id'])
    method=core();out=[]
    for k,g in paths.groupby('k'):
        keys=g.sort_values('path_id').team_key.tolist();assert len(keys)==256
        matrices=method.distance_matrices(keys,rows)
        for metric,matrix in matrices.items():
            summary,_=method.ustat(matrix)
            out.append(dict(**{c:pool['meta'][c] for c in ['pool_id','image','image_id','building','condition','layer','difficulty','pool_n']},
                k=int(k),metric=metric,cohort='new_space256',estimator='conditional_ratio_U_over_distinct_sample_paths',
                **summary,data_release='v2.1'))
    pd.DataFrame(out).to_csv(destination,index=False,encoding='utf-8-sig')
    return pid


def main():
    TARGET.mkdir(exist_ok=True)
    ids={r['pool_id'] for r in read(OUT/'pools/DEPENDENCIES.json') if r['action']=='new_or_changed_pool'}
    pools=[p for p in read(OUT/'pools/INPUT_SNAPSHOT.json')['images'] if p['pool_id'] in ids]
    assert all((INPUT/(p['pool_id']+'.csv.gz')).exists() for p in pools)
    with ProcessPoolExecutor(max_workers=2) as executor:
        for i,pid in enumerate(executor.map(process,pools),1):print('new geometry V',i,'/',len(pools),pid,flush=True)
    pd.concat([pd.read_csv(TARGET/(p['pool_id']+'.csv')) for p in pools],ignore_index=True).to_csv(
        TARGET/'NEW_SPACE_GEOMETRY_CURVES.csv.gz',index=False,encoding='utf-8-sig')
    (TARGET/'CHECKS.json').write_text(json.dumps(dict(pools=len(pools),paths_per_pool=256,
        old_V_reused_reason='原池成员及融合几何逐项不变；V为团队间距离，不依赖参考',
        new_fusion=0,method='冻结distance_matrices与ustat，保留重复团队零距离和无效尝试'),ensure_ascii=False,indent=2),encoding='utf-8')


if __name__=='__main__':main()
