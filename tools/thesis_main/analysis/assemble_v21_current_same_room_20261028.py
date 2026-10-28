"""同房当前设计接合；实际成员、旧支持与新增支持分别保留。"""
import gzip
import json
import pandas as pd
from .rebuild_v21_20261028 import OUT,read
from .fuse_v21_current_same_room_20261028 import TARGET,requests
from .fuse_v21_new_pools_20261028 import adapter


def main():
    assert read(TARGET/'CHECKS.json')['complete']
    wanted=requests();d=pd.read_csv(TARGET/'REUSED_SCALARS.csv.gz',low_memory=False);rows=[];native=adapter()
    for path in TARGET.rglob('part_*.jsonl.gz'):
        with gzip.open(path,'rt',encoding='utf8') as f:
            for line in f:rows.append(native.native.scalar_row(json.loads(line)))
    d=pd.concat([d,pd.DataFrame(rows)],ignore_index=True)
    assert d.team_key.is_unique and set(d.team_key)==set(wanted)
    pools={p['pool_id']:p for p in read(OUT/'pools/INPUT_SNAPSHOT.json')['images']}
    for field in ['reference_id','reference_version','difficulty']:d[field]=d.pool_id.map({pid:p['meta'][field] for pid,p in pools.items()})
    d['reference_nodes']=d.pool_id.map({pid:len(p['reference']['points_1024x512'])//2 for pid,p in pools.items()})
    d['reference_node_shortfall']=(d.reference_nodes-d.nodes).clip(lower=0)
    d['data_release']='v2.1'
    with gzip.open(OUT/'same_room_current_extended_design/REQUESTS.json.gz','rt',encoding='utf8') as f:finite={r['team_key'] for r in json.load(f)}
    large=set(pd.read_csv(OUT/'same_room_current_large_design/ENDPOINT_REQUESTS.csv.gz',usecols=['team_key']).team_key)
    for name,keys in [('finite',finite),('large',large)]:
        folder=OUT/'same_room_current_results'/name/'native';folder.mkdir(parents=True,exist_ok=True)
        z=d[d.team_key.isin(keys)].copy();assert len(z)==len(keys)
        z.to_csv(folder/'ENDPOINT_SCALARS.csv.gz',index=False,encoding='utf-8-sig')
        if name=='finite':
            (folder/'pools').mkdir(exist_ok=True)
            for pid,g in z.groupby('pool_id'):
                with gzip.open(folder/'pools'/(pid+'.json.gz'),'wt',encoding='utf8') as f:json.dump(dict(pool_id=pid,teams=g.astype(object).where(pd.notna(g),None).to_dict('records')),f,ensure_ascii=False,allow_nan=False)
    (OUT/'same_room_current_results/INPUT_CHECKS.json').write_text(json.dumps(dict(data_release='v2.1',unique_teams=len(d),finite_teams=len(finite),large_teams=len(large),requests_exactly_covered=True),indent=2),encoding='utf8')


if __name__=='__main__':main()
