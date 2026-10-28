"""当前策略复用标量端点；仅对缺失成员集合运行原生融合。"""
import gzip
import io
import json
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
import pandas as pd
from .rebuild_v21_20261028 import OUT,read
from .prepare_v21_natural_inputs_20261028 import BASE,PRIOR,EXT,FIELDS,METRICS,overlay
from .recover_v21_composition_20261028 import process

TARGET=OUT/'current_policy_endpoints'
KEEP=list(dict.fromkeys(FIELDS+['time_source_kinds','time_source_kinds_json','score_available','score_failure_nonpolicy','incomplete_nonpolicy','B8_floor_block','B8_direction_block','B8_height_block']))


def main():
    TARGET.mkdir(exist_ok=True)
    with gzip.open(OUT/'current_policy_design/REQUESTS.json.gz','rt',encoding='utf8') as f:wanted={r['team_key']:r for r in json.load(f)}
    pools={p['pool_id']:p for p in read(OUT/'pools/INPUT_SNAPSHOT.json')['images']}
    cached=TARGET/'REUSED_SCALARS.csv.gz'
    if not cached.exists():
        frames=[];known=set();patches={}
        for folder in ['historical_population_rescore','population256_rescore']:
            for p in (OUT/folder).rglob('*.jsonl.gz'):
                with gzip.open(p,'rt',encoding='utf8') as f:
                    for line in f:
                        r=json.loads(line)
                        if r['team_key'] in wanted:
                            m=r['result'] or {};patches[r['team_key']]=dict(team_key=r['team_key'],**{c:m.get(c) for c in METRICS},score_status=m.get('score_status',r.get('original_score_status',r.get('original_endpoint_state'))))
        patch=pd.DataFrame(patches.values()).set_index('team_key')
        sources=[io.BytesIO(b''.join(p.read_bytes() for p in sorted((BASE/'results').glob('ENDPOINT_SCALARS.csv.gz.part*'))))]
        sources+=sorted((PRIOR/'new_endpoints/table_shards/NEW_ENDPOINT_SCALARS').glob('*.csv.gz'))
        index=pd.read_csv(EXT/'new_endpoints26/COMPLETE_NEW_ENDPOINT_SHARD_INDEX.csv.gz')
        sources += [EXT/p for p in index.scalar_file]
        for i,path in enumerate(sources):
            for d in pd.read_csv(path,compression='gzip',chunksize=50000,usecols=lambda c:c in KEEP,low_memory=False):
                d=d[d.team_key.isin(wanted)]
                if len(d):frames.append(d);known.update(d.team_key)
            if i%500==0:print('policy scalar sources',i,'/',len(sources),'known',len(known),flush=True)
        d=pd.concat(frames,ignore_index=True).drop_duplicates('team_key',keep='last')
        d=overlay(d,patch);frames=[d];del patches,patch
        # New-space natural curves already contain the same saved team metrics.
        deps={r['pool_id']:r for r in read(OUT/'pools/DEPENDENCIES.json')}
        for path in (OUT/'natural_inputs').glob('*.csv.gz'):
            if deps[path.name[:-7]]['action']!='new_or_changed_pool':continue
            z=pd.read_csv(path,usecols=lambda c:c in KEEP,low_memory=False)
            z=z[z.team_key.isin(wanted.keys()-known)].drop_duplicates('team_key')
            if len(z):frames.append(z);known.update(z.team_key)
        for folder in ['composition_rescore','same_room_geometry_recovery','current_exchange_endpoints']:
            rows=[]
            for path in (OUT/folder).rglob('*.jsonl.gz'):
                with gzip.open(path,'rt',encoding='utf8') as f:
                    for line in f:
                        r=json.loads(line);key=r.get('team_key')
                        if key in wanted and key not in known:
                            row={c:r.get(c) for c in KEEP};row['floor_turn5_n']=r.get('floor_turn5_n',r.get('fusion_turn_n'));row['floor_redundant5_n']=r.get('floor_redundant5_n',r.get('fusion_redundancy_n'))
                            for c in ['member_workers','member_object_ids']:
                                if isinstance(row[c],list):row[c]='|'.join(row[c])
                            rows.append(row);known.add(key)
            if rows:frames.append(pd.DataFrame(rows))
        d=pd.concat(frames,ignore_index=True);assert d.team_key.is_unique
        for r in d[['team_key','pool_id','member_workers','k']].itertuples():
            assert sorted(r.member_workers.split('|'))==wanted[r.team_key]['worker_ids'] and int(r.k)==len(wanted[r.team_key]['worker_ids'])
        # Source logs are unchanged; fill kind metadata directly from each actual member set.
        worker={pid:{r['worker_id']:r for r in p['records']} for pid,p in pools.items()}
        d['time_source_kinds']=['|'.join(sorted({worker[pid][w]['time_source_kind'] for w in wanted[key]['worker_ids'] if worker[pid][w]['source_time_seconds'] is not None})) for pid,key in d[['pool_id','team_key']].itertuples(index=False,name=None)]
        d['data_release']='v2.1';d.to_csv(cached,index=False,encoding='utf-8-sig')
    reused=set(pd.read_csv(cached,usecols=['team_key']).team_key)
    groups=defaultdict(list);deferred=[]
    for key,r in wanted.items():
        if key in reused:continue
        if len(r['worker_ids'])==2:deferred.append(r);continue
        groups[r['pool_id']].append(dict(team_key=key,member_workers='|'.join(r['worker_ids']),geometry_recovery='new_policy_team_selected_by_current_LOBO_roles'))
    (TARGET/'K2_REQUESTS_PENDING_SUPPLEMENT.json').write_text(json.dumps(deferred),encoding='utf8')
    plan=dict(requested=len(wanted),reused=len(reused),new_native=sum(map(len,groups.values())),k2_awaiting_supplement=len(deferred))
    (TARGET/'PLAN.json').write_text(json.dumps(plan,indent=2),encoding='utf8');print(json.dumps(plan),flush=True)
    with ProcessPoolExecutor(max_workers=2) as executor:
        results=list(executor.map(process,[(pools[pid],rows,str(TARGET)) for pid,rows in sorted(groups.items())]))
    assert all(r['complete'] for r in results)
    (TARGET/'CHECKS.json').write_text(json.dumps(dict(**plan,non_k2_complete=True,pools=results),indent=2),encoding='utf8')


if __name__=='__main__':main()
