"""原角点对应函数；复用原有有向团队对，缺失几何按确切成员恢复。"""
import gzip
import json
from collections import defaultdict
import pandas as pd
from .rebuild_v21_20261028 import ROOT,OUT,read
from .prepare_v21_same_room_analysis_20261028 import LARGE
from .fuse_v21_current_same_room_20261028 import TARGET as ENDPOINTS
from .recover_v21_composition_20261028 import process
from .measure_v21_current_exchange_20261028 import load

TARGET=OUT/'same_room_current_results/large/geometry'


def main():
    assert read(ENDPOINTS/'CHECKS.json')['complete']
    TARGET.mkdir(parents=True,exist_ok=True);(TARGET/'pools').mkdir(exist_ok=True)
    native=load(LARGE/'engine/compare_event_geometry.py','v21_room_corner')
    groups,schema,count=native.prepare(OUT/'same_room_current_large_design/STRICT_ABC_EVENTS.csv.gz')
    old=pd.read_csv(LARGE/'geometry/UNIQUE_GEOMETRY_COMPARISONS.csv.gz',low_memory=False)
    assert not old.duplicated(['team_key_from','team_key_to']).any()
    cache={(r['team_key_from'],r['team_key_to']):r for r in old.to_dict('records')}
    locator=pd.read_csv(LARGE/'native_endpoints/ENDPOINT_ARCHIVE_LOCATOR.csv.gz')
    scalars=pd.read_csv(OUT/'same_room_current_results/large/native/ENDPOINT_SCALARS.csv.gz',low_memory=False).set_index('team_key',drop=False)
    pools={p['pool_id']:p for p in read(OUT/'pools/INPUT_SNAPSHOT.json')['images']}
    recovery=OUT/'same_room_current_geometry_recovery';recovery.mkdir(exist_ok=True)
    checks=[];all_results=[]
    for pid,events in groups.items():
        dest=TARGET/'pools'/(pid+'.csv.gz');receipt=TARGET/'pools'/(pid+'.json')
        if receipt.exists():
            r=read(receipt);d=pd.read_csv(dest,low_memory=False);assert set(d.event_id)=={e['event_id'] for e in events} and len(d)==3*len(events)
            checks.append(r);all_results.append(d);continue
        pairs={(e[a],e[b]) for e in events for a,b in [('A','B'),('A','C'),('B','C')]}
        missing=pairs-cache.keys();needed={key for pair in missing for key in pair};teams={}
        for folder in [ENDPOINTS,recovery,OUT/'new_space_natural256',OUT/'composition_rescore',OUT/'same_room_geometry_recovery',OUT/'current_exchange_endpoints',OUT/'current_policy_endpoints']:
            for path in (folder/pid).glob('part_*.jsonl.gz'):
                with gzip.open(path,'rt',encoding='utf8') as f:
                    for line in f:
                        r=json.loads(line)
                        if r['team_key'] in needed:teams[r['team_key']]=r
        specs=locator[locator.team_key.isin(needed-teams.keys())]
        for rel,z in specs.groupby('geometry_shard'):
            path=LARGE/'native_endpoints'/rel
            if not path.exists():continue
            lines=dict(zip(z.geometry_line_1based,z.team_key))
            with gzip.open(path,'rt',encoding='utf8') as f:
                for n,line in enumerate(f,1):
                    if n in lines:
                        r=json.loads(line);assert r['team_key']==lines[n];teams[r['team_key']]=r
        unavailable=needed-teams.keys()
        if unavailable:
            req=scalars.loc[sorted(unavailable)].to_dict('records')
            for r in req:r['geometry_recovery']='missing_saved_geometry_for_new_direct_same_room_comparison'
            process((pools[pid],req,str(recovery)))
            for path in (recovery/pid).glob('part_*.jsonl.gz'):
                with gzip.open(path,'rt',encoding='utf8') as f:
                    for line in f:
                        r=json.loads(line)
                        if r['team_key'] in needed:teams[r['team_key']]=r
        assert needed<=teams.keys()
        for key,r in teams.items():
            expected=set(str(scalars.at[key,'member_workers']).split('|'))
            actual=r['member_workers'];actual=actual.split('|') if isinstance(actual,str) else actual
            assert set(actual)==expected and r['pool_id']==pid
            # 角点几何不依赖GT；同池旧缓存须使用当前参照身份，避免混用版本元数据。
            r['geometry_source_reference_version']=r.get('reference_version')
            r.update(reference_id=pools[pid]['meta']['reference_id'],reference_version=pools[pid]['meta']['reference_version'])
        for a,b in sorted(missing):
            r,_=native.corner.corner_compare(teams[a],teams[b])
            r.update(pool_id=pid,team_key_from=a,team_key_to=b,geometry_pair_key='GEOM_'+native.digest([pid,a,b])[:24]);cache[a,b]=r
        result=[]
        for event in events:
            meta={k:v for k,v in event.items() if k not in ['A','B','C']}
            for a,b in [('A','B'),('A','C'),('B','C')]:
                r=dict(cache[event[a],event[b]])
                r.update(reference_id=pools[pid]['meta']['reference_id'],reference_version=pools[pid]['meta']['reference_version'])
                result.append(dict(meta,comparison=a+b,**r))
        d=pd.DataFrame(result);d.to_csv(dest,index=False,encoding='utf-8-sig')
        r=dict(pool_id=pid,events_in_view=len(events),comparisons=len(d),ordered_pairs=len(pairs),reused_pairs=len(pairs)-len(missing),new_comparisons=len(missing),recovered_geometries=len(unavailable),complete=True)
        receipt.write_text(json.dumps(r,indent=2),encoding='utf8');checks.append(r);all_results.append(d);print(r,flush=True)
    merged=pd.concat(all_results,ignore_index=True);assert len(merged)==6*count and not merged.duplicated(['event_id','view','comparison']).any()
    merged.to_csv(TARGET/'EVENT_GEOMETRY_RESULTS.csv.gz',index=False,encoding='utf-8-sig')
    (TARGET/'CHECKS.json').write_text(json.dumps(dict(events=count,geometry_rows=len(merged),complete=True,pools=checks),indent=2),encoding='utf8')


if __name__=='__main__':main()
