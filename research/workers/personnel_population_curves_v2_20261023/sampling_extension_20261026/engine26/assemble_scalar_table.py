"""Optional unified new scalar table, assembled with short closed append steps.

Pool shards remain authoritative. The unified logical filename in registered
requests resolves to this table, or to the same rows through the shard index.
Each gzip member has complete footer, and only the first member has a CSV header.
"""
from pathlib import Path
import argparse,csv,gzip,io,json,os,time
from execute_extension import readcsv,savejson,sha

def header(p):
    with gzip.open(p,'rt',encoding='utf-8-sig',newline='') as f:return next(csv.reader(f))

def append_closed(path,data):
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_APPEND,0o644)
    try:
        at=0;v=memoryview(data)
        while at<len(v):
            n=os.write(fd,v[at:at+1024*1024])
            if n<=0:raise IOError('Append made no progress')
            at+=n
        os.fsync(fd)
    finally:os.close(fd)

def run(base):
    t=time.monotonic();plan=list(csv.DictReader((base/'design26/POOL_SAMPLING_PLAN.csv').open(encoding='utf-8-sig')));parts={};fields=set()
    for p in plan:
        pid=p['pool_id'];parts[pid]=[]
        for stage in (1,2):
            folder=base/'new_endpoints26'/f'stage{stage}'/'parts'/pid
            assert (folder/'POOL_RECEIPT.json').exists(),('incomplete',pid,stage)
            for file in sorted(folder.glob('part_*.scalars.csv.gz')):parts[pid].append(file);fields.update(header(file))
    fields=sorted(fields);target=base/'new_endpoints26/NEW_ENDPOINT_SCALARS.csv.gz';temp=target.with_name(target.name+'.assembling')
    fd=os.open(temp,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o644);os.close(fd)
    first=True;n=0;poolcounts=[]
    for pid,files in sorted(parts.items()):
        rows={}
        for file in files:
            for r in readcsv(file):assert r['team_key'] not in rows;rows[r['team_key']]=r
        if not rows:continue
        s=io.StringIO(newline='');w=csv.DictWriter(s,fieldnames=fields,lineterminator='\n',extrasaction='raise')
        if first:w.writeheader()
        for key,r in sorted(rows.items()):w.writerow(r)
        data=s.getvalue().encode('utf-8-sig' if first else 'utf-8');first=False
        append_closed(temp,gzip.compress(data,compresslevel=4,mtime=0));n+=len(rows);poolcounts.append(dict(pool_id=pid,rows=len(rows)))
    expected=sum(int(p['stage1_new_endpoints'])+int(p['stage2_new_endpoints']) for p in plan);assert n==expected
    # Validate the actual assembled bytes, including every gzip footer.
    read_n=0;observed={}
    for r in readcsv(temp):read_n+=1;observed[r['pool_id']]=observed.get(r['pool_id'],0)+1
    assert read_n==n and observed=={r['pool_id']:r['rows'] for r in poolcounts}
    temp.replace(target);result=dict(file=str(target.relative_to(base)),rows=n,columns=fields,bytes=target.stat().st_size,sha256=sha(target),pool_counts=poolcounts,seconds=time.monotonic()-t,all_CSV_gzip_read_to_EOF=True,storage='concatenated complete gzip members, one CSV header',authoritative_shards_retained=True)
    savejson(base/'new_endpoints26/UNIFIED_SCALAR_RECEIPT.json',result);return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--base',type=Path,required=True);a=p.parse_args();r=run(a.base);print(json.dumps({k:v for k,v in r.items() if k not in ('pool_counts','columns')}))
