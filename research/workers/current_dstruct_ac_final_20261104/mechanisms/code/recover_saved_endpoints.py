"""Recover exact saved legacy endpoints for a frozen diagnostic selection.

The old cache-plan order predicts a 100-row shard. Every prediction is verified
against the full team key; a miss triggers bounded scanning of that pool only.
No endpoint is re-created, scored, relabelled, or repaired by this script.
"""
from __future__ import annotations
import argparse,concurrent.futures,hashlib,json,math,os,time,urllib.parse,urllib.request
from collections import defaultdict
from pathlib import Path
import pandas as pd
from mechanism_core import ROOT,OUT,COMMIT,sha,read_json,iter_jsonl,save_csv,save_json,save_jsonl

PREFIX='research/workers/personnel_ac_v21_20261030/stage03_endpoints/pools/'
PLAN=ROOT/'research/workers/personnel_ac_v21_20261030/stage02_engine/cache_plan/REQUEST_IDENTITY_AND_REUSE.csv.gz'

def blob(b):return hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()

def fetch_one(item):
    path,meta=item;dest=ROOT/path;data=dest.read_bytes() if dest.exists() else None
    if data is None or (meta.get('sha') and blob(data)!=meta['sha']):
        url='https://raw.githubusercontent.com/Sparkling-Flames/3D_Manhattan_label/'+COMMIT+'/'+urllib.parse.quote(path,safe='/')
        for attempt in range(3):
            try:
                with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'HOHONET-current-DSTRUCT-AC-diagnostic'}),timeout=45) as r:data=r.read()
                break
            except Exception:
                if attempt==2:raise
                time.sleep(attempt+1)
        if meta.get('sha'):assert blob(data)==meta['sha'],('Pinned-source Git blob mismatch',path)
        dest.parent.mkdir(parents=True,exist_ok=True);tmp=dest.with_name(dest.name+'.download.'+str(os.getpid()));tmp.write_bytes(data);tmp.replace(dest)
    if meta.get('sha'):assert blob(data)==meta['sha']
    return path,dict(path=path,git_blob=blob(data),sha256=hashlib.sha256(data).hexdigest(),bytes=len(data),commit=COMMIT)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--selection',default=str(OUT/'DIAGNOSTIC_SAMPLE.csv.gz'));ap.add_argument('--jobs',type=int,default=12);args=ap.parse_args()
    selection=pd.read_csv(args.selection,keep_default_na=False,low_memory=False)
    wanted=set(selection.A_team_key)|set(selection.C_team_key)
    pools=set(selection.pool_id)
    cache=OUT/'source/SAVED_LEGACY_ENDPOINTS.jsonl.gz';origins_path=OUT/'source/SAVED_LEGACY_ENDPOINT_ORIGINS.csv'
    records={r['team_key']:r for r in iter_jsonl(cache)} if cache.exists() else {}
    origins=pd.read_csv(origins_path,keep_default_na=False).to_dict('records') if origins_path.exists() else []
    need=wanted-set(records)
    saved_index=OUT/'source/RECOVERY_SOURCE_PART_INDEX.json'
    # The delivery contains this bounded pinned-source tree index. No transient
    # working-directory service or external local FILE_INDEX is required.
    idx=read_json(saved_index)
    parts={p:meta for p,meta in idx.items() if p.startswith(PREFIX) and Path(p).parent.name in pools and p.endswith('.jsonl.gz')}
    old_idx=read_json(saved_index) if saved_index.exists() else {};old_idx.update(parts);save_json(saved_index,old_idx)
    assert all(any(Path(p).parent.name==pid for p in parts) for pid in pools)
    fetched={};visited=set();predictions=[];start=time.monotonic()
    def consume(paths):
        tasks=[(p,parts[p]) for p in sorted(set(paths)-visited)]
        with concurrent.futures.ThreadPoolExecutor(args.jobs) as executor:
            for path,receipt in executor.map(fetch_one,tasks):
                fetched[path]=receipt;visited.add(path)
                for line,row in enumerate(iter_jsonl(ROOT/path),1):
                    if row['team_key'] not in need:continue
                    key=row['team_key'];records[key]=row;need.remove(key)
                    origins.append(dict(team_key=key,pool_id=row['pool_id'],source_path=path,source_jsonl_line=line,source_sha256=receipt['sha256'],source_git_blob=receipt['git_blob'],source_commit=COMMIT))
    # If the compact saved cache was removed, its delivered provenance already
    # identifies every exact shard. Restore these before considering the old
    # request-plan prediction path, avoiding a 42 MB plan dependency.
    if need and origins:
        consume([r['source_path'] for r in origins if r['team_key'] in need])
    if need:
        assert PLAN.exists(),'Restore the pinned old request plan, or use the already delivered selected endpoint cache.'
        plan=pd.read_csv(PLAN,usecols=['pool_id','team_key','endpoint_acquisition'],keep_default_na=False)
        plan=plan[plan.pool_id.isin(pools)].copy()
        predicted=[]
        for pid,g in plan.groupby('pool_id',sort=True):
            reused=g[g.endpoint_acquisition.eq('reused_full')]
            remaining=g[~g.endpoint_acquisition.eq('reused_full')]
            offset=math.ceil(len(reused)/100)
            for index,key in enumerate(remaining.team_key):
                if key not in need:continue
                part=PREFIX+pid+f'/part_{offset+index//100+1:05d}.jsonl.gz'
                predictions.append(dict(team_key=key,predicted_source_path=part,request_position_nonreused=index,reused_rows=len(reused),algorithm='100-row archive partitions; exact team_key checked'))
                if part in parts:predicted.append(part)
            if set(reused.team_key)&need:
                predicted.extend(PREFIX+pid+f'/part_{i+1:05d}.jsonl.gz' for i in range(offset) if PREFIX+pid+f'/part_{i+1:05d}.jsonl.gz' in parts)
        consume(predicted)
        print(json.dumps(dict(stage='predicted_shards_checked',found=len(wanted)-len(need),requested=len(wanted),missing=len(need),files=len(visited))),flush=True)
        # Execution restarts can shift a partition boundary. Check neighboring
        # partitions, then the remaining partitions in only unresolved pools.
        if need:
            near=[]
            for r in predictions:
                if r['team_key'] not in need:continue
                p=Path(r['predicted_source_path']);i=int(p.name.split('_')[1].split('.')[0])
                near.extend(str(p.with_name(f'part_{j:05d}.jsonl.gz')) for j in [i-1,i+1] if j>=1 and str(p.with_name(f'part_{j:05d}.jsonl.gz')) in parts)
            consume(near)
        if need:
            missing_pools=set(plan[plan.team_key.isin(need)].pool_id)
            todo=[p for p in parts if Path(p).parent.name in missing_pools and p not in visited]
            consume(todo)
        assert not need,('Saved endpoints missing from source',sorted(need))
    assert wanted<=set(records)
    save_jsonl(cache,[records[k] for k in sorted(records)])
    origins=pd.DataFrame(origins).sort_values('team_key').drop_duplicates('team_key')
    assert set(origins.team_key)==set(records)
    save_csv(origins_path,origins)
    prior_manifest=OUT/'source/RECOVERY_FETCHED_FILES.csv'
    manifests=pd.read_csv(prior_manifest,keep_default_na=False).to_dict('records') if prior_manifest.exists() else []
    manifests.extend(fetched.values())
    if manifests:save_csv(prior_manifest,pd.DataFrame(manifests).sort_values('path').drop_duplicates('path',keep='last'))
    if predictions:save_csv(OUT/'source/PREDICTED_SHARD_LOCATIONS.csv',predictions)
    receipt=dict(selection_path=str(Path(args.selection).resolve().relative_to(ROOT)),selection_sha256=sha(args.selection),requested=len(wanted),available_saved_endpoints=len(records),
                 new_shards_read=len(visited),newly_recovered=len(fetched),seconds=time.monotonic()-start,all_requested_exact_team_keys_found=True,
                 selected_endpoint_cache_sha256=sha(cache),new_fusions=0,new_scores=0,new_physical_teams=0)
    save_json(OUT/'source/RECOVERY_RECEIPT.json',receipt);print(json.dumps(receipt,ensure_ascii=False),flush=True)

if __name__=='__main__':main()
