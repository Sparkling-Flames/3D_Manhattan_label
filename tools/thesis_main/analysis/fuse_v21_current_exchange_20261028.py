"""当前标签严格ABC：先复用已存同队结果，只融合新增实际成员集合。"""
import gzip
import io
import json
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
import pandas as pd
from .rebuild_v21_20261028 import ROOT,OUT,read
from .recover_v21_composition_20261028 import process
from .rescore_v21_discrimination_20261028 import BASE as AUDIT,SOURCES
from .prepare_v21_natural_inputs_20261028 import BASE,PRIOR,EXT
from .fuse_v21_new_pools_20261028 import adapter

TARGET=OUT/'current_exchange_endpoints'


def main():
    TARGET.mkdir(exist_ok=True)
    wanted={}
    for stage in ['confirm','reverse_confirm']:
        with gzip.open(OUT/f'current_exchange_design/design/{stage}/REQUESTS.json.gz','rt',encoding='utf8') as f:
            for r in json.load(f):
                if r['team_key'] in wanted:assert wanted[r['team_key']]==r
                wanted[r['team_key']]=r
    pools={p['pool_id']:p for p in read(OUT/'pools/INPUT_SNAPSHOT.json')['images']}
    cachepath=TARGET/'REUSED_ENDPOINTS.jsonl.gz'
    if not cachepath.exists():
        known={};patches={}
        for path in (OUT/'discrimination_endpoint_rescore/shards').glob('*.jsonl.gz'):
            with gzip.open(path,'rt',encoding='utf8') as f:
                for line in f:
                    r=json.loads(line)
                    if r['team_key'] in wanted:patches[r['team_key']]=r
        for folder in ['historical_population_rescore','population256_rescore']:
            for path in (OUT/folder).rglob('*.jsonl.gz'):
                with gzip.open(path,'rt',encoding='utf8') as f:
                    for line in f:
                        r=json.loads(line)
                        if r['team_key'] in wanted and r['team_key'] not in patches:patches[r['team_key']]=r
        affected={r['pool_id'] for r in read(OUT/'pools/DEPENDENCIES.json') if r['action']=='reuse_geometry_rescore'}
        for label,scalar,geometry in SOURCES:
            chunks=[]
            for c in pd.read_csv(AUDIT/scalar,chunksize=30000,low_memory=False):chunks.append(c[c.team_key.isin(wanted.keys()-known.keys())])
            d=pd.concat(chunks,ignore_index=True).set_index('team_key');selected=set(d.index)
            with gzip.open(AUDIT/geometry,'rt',encoding='utf8') as f:
                for g in json.load(f):
                    key=g['team_key']
                    if key not in selected:continue
                    r=d.loc[key].to_dict();r['team_key']=key;r['geometry']=g.get('geometry')
                    if r['pool_id'] in affected:
                        assert key in patches
                        patch=patches[key];r.update(patch['result'] or {});r.update(patch.get('reference_dependent_diagnostics',{}))
                    r['reuse_source']=geometry;known[key]=r
            print('reuse current exchange',label,len(known),flush=True)
        for folder in ['new_space_natural256','composition_rescore','same_room_geometry_recovery']:
            for path in (OUT/folder).rglob('*.jsonl.gz'):
                if path.name.startswith(('INPUT','REQUEST','MISSING')):continue
                with gzip.open(path,'rt',encoding='utf8') as f:
                    for line in f:
                        r=json.loads(line);key=r.get('team_key')
                        if key in wanted and key not in known and 'geometry' in r:
                            r['reuse_source']=str(path.relative_to(ROOT));known[key]=r
            print('reuse current exchange',folder,len(known),flush=True)
        # Population scalar indexes locate remaining exact identities before reading geometry.
        sources=[(io.BytesIO(b''.join(p.read_bytes() for p in sorted((BASE/'results').glob('ENDPOINT_SCALARS.csv.gz.part*')))),BASE/'results/ENDPOINT_GEOMETRY.json.gz')]
        for scalar in sorted((PRIOR/'new_endpoints/table_shards/NEW_ENDPOINT_SCALARS').glob('*.csv.gz')):
            geom=PRIOR/'new_endpoints/table_shards/NEW_ENDPOINT_GEOMETRY_COMPACT'/scalar.name.replace('.csv.gz','.jsonl.gz')
            sources.append((scalar,geom))
        index=pd.read_csv(EXT/'new_endpoints26/COMPLETE_NEW_ENDPOINT_SHARD_INDEX.csv.gz')
        for r in index[index.pool_id.isin({v['pool_id'] for k,v in wanted.items() if k not in known})].itertuples():sources.append((EXT/r.scalar_file,EXT/r.geometry_file))
        for scalar,geom in sources:
            hits=[]
            for d in pd.read_csv(scalar,compression='gzip',chunksize=30000,low_memory=False):
                hits.append(d[d.team_key.isin(wanted.keys()-known.keys())])
            df=pd.concat(hits,ignore_index=True).drop_duplicates('team_key',keep='last').set_index('team_key')
            if df.empty:continue
            assert geom.exists(),str(geom)
            with gzip.open(geom,'rt',encoding='utf8') as f:
                values=(json.loads(line) for line in f) if geom.name.endswith('.jsonl.gz') else iter(json.load(f))
                for g in values:
                    key=g['team_key']
                    if key not in df.index:continue
                    r=df.loc[key].to_dict();r['team_key']=key;r['geometry']=g.get('geometry');r['reuse_source']=str(geom.relative_to(ROOT));r['needs_rescore']=r['pool_id'] in affected;known[key]=r
        native=adapter()
        with native.Engine(full_state=False) as engine,gzip.open(cachepath.with_suffix('.writing'),'wt',encoding='utf8') as f:
            for key,r in sorted(known.items()):
                pool=pools[r['pool_id']];expected=sorted(wanted[key]['worker_ids'])
                members=r['member_workers'] if isinstance(r['member_workers'],list) else str(r['member_workers']).split('|')
                assert sorted(members)==expected
                r['member_workers']=members
                if r.get('needs_rescore'):
                    assert key in patches,(key,'missing current reference score')
                    patch=patches[key];r.update(patch['result'] or {})
                    for metric in ['B8L2','D10']:r[metric]=(patch['result'] or {}).get(metric)
                    r.update(patch.get('reference_dependent_diagnostics',{}))
                r=native.native.enrich(r,pool,engine.times,engine.sg,{})
                r.update(reference_id=pool['meta']['reference_id'],reference_version=pool['meta']['reference_version'],data_release='v2.1',geometry_reused=True)
                f.write(json.dumps(native.gs.clean(r),ensure_ascii=False,allow_nan=False)+'\n')
        cachepath.with_suffix('.writing').replace(cachepath)
    with gzip.open(cachepath,'rt',encoding='utf8') as f:reused={json.loads(line)['team_key'] for line in f}
    assert reused<=wanted.keys();groups=defaultdict(list)
    for key,r in wanted.items():
        if key not in reused:groups[r['pool_id']].append(dict(team_key=key,member_workers='|'.join(r['worker_ids']),geometry_recovery='new_team_selected_by_current_LOBO_labels'))
    (TARGET/'PLAN.json').write_text(json.dumps(dict(requested=len(wanted),reused=len(reused),new_native=len(wanted)-len(reused),pools=len(groups)),indent=2),encoding='utf8')
    with ProcessPoolExecutor(max_workers=2) as executor:
        results=list(executor.map(process,[(pools[pid],rows,str(TARGET)) for pid,rows in sorted(groups.items())]))
    assert all(r['complete'] for r in results)
    (TARGET/'CHECKS.json').write_text(json.dumps(dict(requested=len(wanted),reused=len(reused),native=len(wanted)-len(reused),complete=True,pools=results),indent=2),encoding='utf8')


if __name__=='__main__':main()
