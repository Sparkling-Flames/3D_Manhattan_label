"""Save already-completed pool shards, excluding pools persisted in prior batches."""
import argparse,gzip,hashlib,io,json,os,zipfile
from pathlib import Path
import pandas as pd

def main():
    p=argparse.ArgumentParser();p.add_argument('--work',required=True);p.add_argument('--file',required=True)
    p.add_argument('--manifest',required=True);p.add_argument('--exclude',action='append',default=[])
    p.add_argument('--take',type=int,default=60);a=p.parse_args();work=Path(a.work);target=Path(a.file)
    excluded=set()
    for f in a.exclude:
        excluded.update(r['pool_id'] for r in json.loads(Path(f).read_text())['by_pool'])
    progress=json.loads((work/'results/RUN_PROGRESS.json').read_text())
    candidates=[r for r in progress['by_pool'] if r['pool_id'] not in excluded]
    keys=set();selected=[];pending_saved_tail=[]
    for r in candidates:
        with gzip.open(work/'results/endpoints'/(r['pool_id']+'.json.gz'),'rt') as f:v=json.load(f)
        if len(v['teams'])!=r['requests']:
            pending_saved_tail.append(dict(pool_id=r['pool_id'],requested=r['requests'],saved=len(v['teams'])))
            continue
        selected.append(r)
        keys.update(t['team_key'] for t in v['teams'])
        if len(selected)==a.take:break
    if len(selected)<a.take:raise RuntimeError(f'Only {len(selected)} fully saved new pools; need {a.take}')
    attached=(work/'results/HISTORICAL_GEOMETRY_ATTACHMENT.json').exists()
    manifest=dict(source_commit='72a44e80c344975962e1071bd54d894dd86bb4b4',data_release='v2',
        stage='incremental completed-pool checkpoint; not final balanced analysis',
        pools=len(selected),endpoint_rows=sum(r['requests'] for r in selected),
        new_native=sum(r['new_native'] for r in selected),by_pool=selected,
        excluded_prior_manifests=a.exclude,all_registered_orders_complete=False,
        skipped_pending_saved_tail=pending_saved_tail,
        geometry_attachment_completed=attached,
        note=('Frozen outputs with recovered geometry and named B8 explanation blocks attached; no extra geometry cache copied.' if attached else 'Raw frozen outputs; final recovered geometry attachment and named B8 explanation blocks are separate aggregation steps.'))
    target.parent.mkdir(parents=True,exist_ok=True);tmp=target.with_name(target.name+'.tmp')
    with zipfile.ZipFile(tmp,'w',compression=zipfile.ZIP_STORED,allowZip64=True) as z:
        for r in selected:
            name=r['pool_id']+'.json.gz';z.write(work/'results/endpoints'/name,'endpoints/'+name)
        geo=[]
        for name in ([] if attached else ['HISTORICAL_ENDPOINT_GEOMETRY.csv.gz','SAME_ROOM_RESTORED_GEOMETRY.csv.gz','LATER_CACHE_GEOMETRY.csv.gz']):
            d=pd.read_csv(work/'reuse'/name,keep_default_na=False);d=d[d.team_key.isin(keys)]
            if len(d):
                z.writestr('recovered_geometry/'+name,gzip.compress(d.to_csv(index=False).encode('utf-8-sig'),compresslevel=3,mtime=0))
            geo.append(dict(file=name,rows=len(d)))
        manifest['historical_geometry']=geo
        z.writestr('CHECKPOINT.json',json.dumps(manifest,ensure_ascii=False,indent=2))
    with tmp.open('rb') as f:os.fsync(f.fileno())
    tmp.replace(target)
    with zipfile.ZipFile(target) as z:assert z.testzip() is None
    manifest.update(file=str(target.resolve()),bytes=target.stat().st_size,
        sha256=hashlib.sha256(target.read_bytes()).hexdigest())
    Path(a.manifest).write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
    print(json.dumps({k:v for k,v in manifest.items() if k not in ['by_pool','historical_geometry']},ensure_ascii=False))

if __name__=='__main__':main()
