"""把当前角色的实际路径与端点接合；非执行的两人策略点保留延期身份。"""
import gzip
import importlib.util
import json
import sys
import numpy as np
import pandas as pd
from .rebuild_v21_20261028 import OUT,read
from .prepare_v21_natural_inputs_20261028 import EXT

TARGET=OUT/'current_policy_inputs'


def main():
    assert read(OUT/'current_policy_endpoints/CHECKS.json')['non_k2_complete']
    TARGET.mkdir(exist_ok=True)
    scalar=pd.read_csv(OUT/'current_policy_endpoints/REUSED_SCALARS.csv.gz',low_memory=False)
    rows=[]
    for path in (OUT/'current_policy_endpoints').rglob('part_*.jsonl.gz'):
        with gzip.open(path,'rt',encoding='utf8') as f:
            for line in f:
                r=json.loads(line);row={k:v for k,v in r.items() if not isinstance(v,(list,dict))}
                for field in ['member_workers','member_object_ids']:row[field]='|'.join(r[field])
                row['floor_turn5_n']=r.get('fusion_turn_n');row['floor_redundant5_n']=r.get('fusion_redundancy_n');rows.append(row)
    if rows:scalar=pd.concat([scalar,pd.DataFrame(rows)],ignore_index=True)
    assert scalar.team_key.is_unique
    deferred=read(OUT/'current_policy_endpoints/K2_REQUESTS_PENDING_SUPPLEMENT.json')
    if deferred:
        missing=pd.DataFrame([dict(team_key=r['team_key'],pool_id=r['pool_id'],member_workers='|'.join(r['worker_ids']),k=2,score_status='policy_deferred_k2',policy_deferred=True,complete_evaluable=False) for r in deferred])
        scalar=pd.concat([scalar,missing],ignore_index=True)
    links=pd.read_csv(OUT/'current_policy_design/PREFIX_LINKS.csv.gz');orders=pd.read_csv(OUT/'current_policy_design/ORDERS.csv.gz')
    assert set(links.team_key)==set(scalar.team_key)
    scalar['policy_deferred']=scalar.k.eq(2)
    scalar['score_available']=scalar.B8L2.notna()
    scalar['score_failure_nonpolicy']=~scalar.score_available&scalar.k.ne(2)
    scalar['incomplete_nonpolicy']=~scalar.complete_evaluable.fillna(False).astype(bool)&scalar.k.ne(2)
    spec=importlib.util.spec_from_file_location('v21_policy_blocks',EXT/'engine26/derive_frozen_blocks.py');blocks=importlib.util.module_from_spec(spec);spec.loader.exec_module(blocks)
    scalar=scalar.drop(columns=[c for c in scalar if c in blocks.BLOCKS or c=='B8_formula_residual'])
    scalar=blocks.add_blocks_frame(scalar)
    residual=scalar.B8_formula_residual.abs().dropna();assert residual.empty or residual.max()<1e-8
    scalar=scalar.drop(columns=[c for c in orders if c in scalar and c not in ['pool_id','team_key','k']])
    for pid,g in links.groupby('pool_id'):
        s=scalar[scalar.pool_id.eq(pid)]
        values=g.merge(s.drop(columns=['pool_id','k']),on='team_key',validate='many_to_one')
        meta=orders[orders.pool_id.eq(pid)].drop(columns=[c for c in g if c!='path_id' and c in orders])
        values=values.merge(meta,on='path_id',validate='many_to_one')
        assert not values.duplicated(['policy','base_path_id','k']).any()
        values.to_csv(TARGET/(pid+'.csv.gz'),index=False,encoding='utf-8-sig')
    (TARGET/'CHECKS.json').write_text(json.dumps(dict(data_release='v2.1',pools=links.pool_id.nunique(),prefixes=len(links),unique_teams=len(scalar),all_non_k2_executed=True,policy_k2='kept_deferred_separate_from_natural_k2_supplement',component_formula_max_residual=float(residual.max()) if len(residual) else None),indent=2),encoding='utf8')


if __name__=='__main__':main()
