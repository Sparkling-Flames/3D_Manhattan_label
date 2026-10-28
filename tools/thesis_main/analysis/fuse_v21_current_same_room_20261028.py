"""合并同房请求；原团队直接复用当前评分，仅补新增实际成员集合。"""
import gzip
import json
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
import pandas as pd
from .rebuild_v21_20261028 import ROOT,OUT,read
from .prepare_v21_same_room_analysis_20261028 import TARGET as FROZEN
from .fuse_v21_new_pools_20261028 import adapter
from .recover_v21_composition_20261028 import process

TARGET=OUT/'current_same_room_endpoints'


def requests():
    with gzip.open(OUT/'same_room_current_extended_design/REQUESTS.json.gz','rt',encoding='utf8') as f:finite=json.load(f)
    wanted={r['team_key']:dict(pool_id=r['pool_id'],member_workers='|'.join(r['workers']),team_key=r['team_key']) for r in finite}
    for r in pd.read_csv(OUT/'same_room_current_large_design/ENDPOINT_REQUESTS.csv.gz',keep_default_na=False).to_dict('records'):
        if r['team_key'] in wanted:assert wanted[r['team_key']]['member_workers']==r['member_workers']
        wanted[r['team_key']]=dict(pool_id=r['pool_id'],member_workers=r['member_workers'],team_key=r['team_key'])
    return wanted


def main():
    TARGET.mkdir(exist_ok=True);wanted=requests()
    pools={p['pool_id']:p for p in read(OUT/'pools/INPUT_SNAPSHOT.json')['images']}
    cached=TARGET/'REUSED_SCALARS.csv.gz'
    if not cached.exists():
        frames=[]
        for name in ['current_classes','large_block']:
            d=pd.read_csv(FROZEN/name/'native/ENDPOINT_SCALARS.csv.gz',low_memory=False)
            frames.append(d[d.team_key.isin(wanted)])
        d=pd.concat(frames,ignore_index=True)
        for key,g in d[d.team_key.duplicated(keep=False)].groupby('team_key'):
            assert g.pool_id.nunique()==1 and g.member_workers.nunique()==1,key
            for field in ['B8L2','D10']:
                assert g[field].notna().nunique()==1 and (g[field].isna().all() or g[field].max()-g[field].min()<1e-8),(key,field)
        d=d.drop_duplicates('team_key',keep='last')
        known=set(d.team_key);frames=[d];native=adapter()
        for folder in ['new_space_natural256','composition_rescore','same_room_geometry_recovery','current_exchange_endpoints']:
            rows=[]
            for path in (OUT/folder).rglob('*.jsonl.gz'):
                with gzip.open(path,'rt',encoding='utf8') as f:
                    for line in f:
                        r=json.loads(line);key=r.get('team_key')
                        if key not in wanted or key in known:continue
                        assert 'geometry' in r and sorted(r['member_workers'])==wanted[key]['member_workers'].split('|')
                        r.update(native.expression(r['geometry']))
                        r['recorded_time_eligible']=bool(r.get('source_time_known_n')==r['k'] and (r.get('source_time_total_seconds') or 0)>0 and r.get('time_source_kinds') and '|' not in r['time_source_kinds'])
                        r['recorded_time_total_seconds']=r.get('source_time_total_seconds') if r['recorded_time_eligible'] else None
                        rows.append(native.native.scalar_row(r));known.add(key)
            if rows:frames.append(pd.DataFrame(rows))
            print('same-room reusable',folder,len(known),flush=True)
        d=pd.concat(frames,ignore_index=True);assert d.team_key.is_unique
        for r in d[['team_key','pool_id','member_workers']].itertuples():
            assert r.pool_id==wanted[r.team_key]['pool_id'] and sorted(r.member_workers.split('|'))==wanted[r.team_key]['member_workers'].split('|')
        d.to_csv(cached,index=False,encoding='utf-8-sig')
    reused=set(pd.read_csv(cached,usecols=['team_key']).team_key);groups=defaultdict(list)
    for key,r in wanted.items():
        if key not in reused:groups[r['pool_id']].append(dict(r,geometry_recovery='new_same_room_team_current_labels_or_new_reference_pair'))
    plan=dict(requested=len(wanted),reused=len(reused),new_native=len(wanted)-len(reused),pools=len(groups))
    (TARGET/'PLAN.json').write_text(json.dumps(plan,indent=2),encoding='utf8');print(plan,flush=True)
    with ProcessPoolExecutor(max_workers=2) as executor:
        results=list(executor.map(process,[(pools[pid],rows,str(TARGET)) for pid,rows in sorted(groups.items())]))
    assert all(r['complete'] for r in results)
    (TARGET/'CHECKS.json').write_text(json.dumps(dict(**plan,complete=True,pool_checks=results),indent=2),encoding='utf8')


if __name__=='__main__':main()
