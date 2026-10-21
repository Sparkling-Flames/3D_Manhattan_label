"""Re-express complete saved previous-stage tables as directly downloadable gzip CSV.
No fusion, score or event is recomputed. Each batch closes and verifies before publishing.
"""
from pathlib import Path
import csv,gzip,hashlib,json,os,time
import pandas as pd
HERE=Path(__file__).resolve().parent
V3=HERE.parent
STUDY=V3.parent/'personnel_global_composition_20261021'
CONT=STUDY/'continuation_20261021'
OUT=HERE/'restored_full_tables'
OUT.mkdir(exist_ok=True)

def sha(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for b in iter(lambda:f.read(2**20),b''):h.update(b)
    return h.hexdigest()

def atomic_json(path,x):
    tmp=path.with_name(path.name+'.partial');tmp.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n');os.replace(tmp,path)

def merge(name,paths,expected_rows,key,union_fields=False):
    out=OUT/name; receipt=OUT/(name+'.receipt.json')
    if out.exists() and receipt.exists():
        x=json.loads(receipt.read_text());assert x['sha256']==sha(out);return x
    tmp=out.with_name(out.name+'.partial'); ids=set();header=None; n=0;inputs=[];start=time.monotonic()
    if union_fields:
        fields=set()
        for p in paths:
            with gzip.open(p,'rt',encoding='utf-8-sig',newline='') as f:fields.update(next(csv.reader(f)))
        header=sorted(fields)
    with open(tmp,'wb') as raw, gzip.GzipFile(filename='',mode='wb',fileobj=raw,mtime=0,compresslevel=4) as gz:
        import io
        stream=io.TextIOWrapper(gz,encoding='utf-8-sig',newline='');wr=csv.writer(stream,lineterminator='\n')
        if header is not None:wr.writerow(header);ki=header.index(key)
        for p in paths:
            count=0
            with gzip.open(p,'rt',encoding='utf-8-sig',newline='') as f:
                rd=csv.reader(f);h=next(rd)
                if header is None:header=h;wr.writerow(h);ki=h.index(key)
                elif not union_fields:assert h==header,(p,'header mismatch')
                take=[h.index(c) if c in h else None for c in header] if union_fields else None
                for row in rd:
                    if union_fields:
                        assert len(row)==len(h),(p,len(row),len(h));row=[row[j] if j is not None else '' for j in take]
                    assert len(row)==len(header),(p,len(row),len(header))
                    assert row[ki] not in ids,(p,row[ki],'duplicate key')
                    ids.add(row[ki]);wr.writerow(row);count+=1
            n+=count;inputs.append({'path':str(p),'rows':count,'bytes':p.stat().st_size,'sha256':sha(p)})
        stream.flush();stream.detach()
    assert n==expected_rows,(n,expected_rows)
    # Verify the gzip trailer and the complete exported key set before atomic publication.
    got=set();check=0
    with gzip.open(tmp,'rt',encoding='utf-8-sig',newline='') as f:
        rd=csv.reader(f);assert next(rd)==header
        for row in rd:
            assert len(row)==len(header);got.add(row[ki]);check+=1
    assert check==n and got==ids
    os.replace(tmp,out)
    x={'file':name,'absolute_path':str(out),'rows':n,'columns':len(header),'unique_key':key,'bytes':out.stat().st_size,'sha256':sha(out),'source_stage':'previous_n20_complete_results','computation':'format consolidation only; no fusion or score recomputation','inputs':inputs,'elapsed_seconds':time.monotonic()-start}
    atomic_json(receipt,x);print(json.dumps({k:x[k] for k in ['file','rows','columns','bytes','elapsed_seconds']},ensure_ascii=False),flush=True)
    return x

def main():
    import argparse
    ap=argparse.ArgumentParser();ap.add_argument('--batch');args=ap.parse_args()
    index=pd.read_csv(CONT/'n20_abc/final_summary/N20_MANUAL_RESULT_SHARD_INDEX.csv')
    allout=[]
    for batch,g in index.groupby('batch',sort=True):
        if args.batch and batch!=args.batch:continue
        paths=[CONT/'n20_abc'/v for v in g.event_file]
        allout.append(merge('N20_MANUAL_FULL_EVENTS_'+batch+'.csv.gz',paths,int(g.events.sum()),'event_id'))
        atomic_json(OUT/'RESTORE_PROGRESS.json',allout)
    if args.batch:return
    allout.append(merge('N20_SEMI_FULL_EVENTS.csv.gz',[CONT/'n20_abc/results_semi/N20_ABC_ALL_COMPONENT_EVENTS.csv.gz'],1517,'event_id'))
    for kind in ['SCALARS','GEOMETRY']:
        paths=[CONT/f'next_stage/batches/REUSED_ENDPOINT_{kind}.csv.gz']+sorted((CONT/'next_stage/batches').glob(f'batch_*/ENDPOINT_{kind}.csv.gz'))
        allout.append(merge(f'N20_ALL_144642_ENDPOINT_{kind}.csv.gz',paths,144642,'team_key',union_fields=True))
    atomic_json(OUT/'RESTORE_PROGRESS.json',allout)
    pd.DataFrame([{k:v for k,v in x.items() if k!='inputs'} for x in allout]).to_csv(OUT/'DIRECT_TABLE_INDEX.csv',index=False,encoding='utf-8-sig')

if __name__=='__main__':main()
