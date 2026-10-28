"""按冻结成员恢复同房缺失几何；与旧参考分数逐池抽样核对。"""
import copy
import gzip
import json
import math
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
from .rebuild_v21_20261028 import ROOT, OUT, read
from .recover_v21_composition_20261028 import process
from .fuse_v21_new_pools_20261028 import adapter

TARGET = OUT / 'same_room_geometry_recovery'


def main():
    TARGET.mkdir(exist_ok=True)
    pools = {p['pool_id']:p for p in read(OUT/'pools/INPUT_SNAPSHOT.json')['images']}
    groups = defaultdict(list)
    with gzip.open(OUT/'same_room_endpoint_rescore/MISSING_GEOMETRY.jsonl.gz','rt',encoding='utf-8') as f:
        for line in f:
            r=json.loads(line); old=r['original_metrics']
            r['member_workers']='|'.join(r['member_workers'])
            for field in ['nodes','B8L2','D10']:
                r[field]=float(old[field]) if old.get(field) not in (None,'') else None
            groups[r['pool_id']].append(r)
    parity_path=TARGET/'ENGINE_PARITY.json'
    if not parity_path.exists():
        refs={r['target_id']:r for r in read(ROOT/'research/quality/quality_workers_v2_20261019/reference_catalog.json')}
        native=adapter(); checks=[]
        for pid, rows in groups.items():
            old=next(r for r in rows if r['B8L2'] is not None)
            pool=copy.deepcopy(pools[pid]);pool['reference']=refs[pool['meta']['reference_id']]
            with native.Engine(full_state=False) as engine:
                row=engine.evaluate(pool,old['member_workers'].split('|'))
            assert row['team_key']==old['team_key']
            assert set(row['member_object_ids'])==set(old['member_object_ids'].split('|'))
            assert row['nodes']==old['nodes']
            errors={c:abs(row[c]-old[c]) for c in ['B8L2','D10']}
            assert max(errors.values())<1e-8,(pid,errors)
            checks.append(dict(pool_id=pid,team_key=row['team_key'],errors=errors,identity_verified=True))
        parity_path.write_text(json.dumps(checks,indent=2),encoding='utf-8')
    checks=read(parity_path)
    assert {r['pool_id'] for r in checks}==set(groups)
    assert all(r['identity_verified'] and max(r['errors'].values())<1e-8 for r in checks)
    with ProcessPoolExecutor(max_workers=2) as executor:
        results=list(executor.map(process,[(pools[pid],rows,str(TARGET)) for pid,rows in groups.items()]))
    assert all(r['complete'] for r in results)
    (TARGET/'CHECKS.json').write_text(json.dumps(dict(pools=results,teams=sum(len(g) for g in groups.values()),complete=True),indent=2),encoding='utf-8')


if __name__=='__main__':main()
