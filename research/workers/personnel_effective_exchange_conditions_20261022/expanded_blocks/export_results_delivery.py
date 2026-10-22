#!/usr/bin/env python3
"""Commit independently readable full event chunks as registered cells finish.

This is an export only: no scoring, fusion, row selection or numerical edits.
Every column and every failure row in EVENTS_COMPLETE is retained. The chunk
plan is determined by the frozen registration, never by observed effects.
"""
from __future__ import annotations
import argparse, collections, csv, gzip, hashlib, json, os, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE.parent / 'delivery' / 'expanded_events'

def sha(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for b in iter(lambda:f.read(1048576),b''): h.update(b)
    return h.hexdigest()

def json_save(path,obj):
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_name(path.name+'.tmp')
    with tmp.open('w',encoding='utf-8') as f:
        json.dump(obj,f,ensure_ascii=False,indent=2); f.flush(); os.fsync(f.fileno())
    os.replace(tmp,path)

def csv_save(path,rows):
    keys=list(dict.fromkeys(k for r in rows for k in r))
    tmp=path.with_name(path.name+'.tmp')
    with tmp.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=keys);w.writeheader();w.writerows(rows)
        f.flush();os.fsync(f.fileno())
    os.replace(tmp,path)

def plan(limit):
    reg=list(csv.DictReader((HERE/'REGISTERED_EVENT_PARTS.csv').open(encoding='utf-8-sig')))
    groups=collections.defaultdict(list)
    for r in reg: groups[(r['method_id'],int(r['n']),int(r['m']))].append(r)
    plans=[]
    for (method,n,m),rows in sorted(groups.items()):
        chunks=[];chunk=[];count=0
        for r in sorted(rows,key=lambda r:(r['building'],r['image'],r['cell_id'])):
            nr=int(r['events'])
            if chunk and count+nr>limit: chunks.append(chunk);chunk=[];count=0
            chunk.append(r);count+=nr
        if chunk:chunks.append(chunk)
        for i,chunk in enumerate(chunks,1):
            plans.append(dict(chunk_id=f'EXPAND_{method}_n{n}_m{m}_part{i:02d}',
                method_id=method,n=n,m=m,expected_events=sum(int(r['events']) for r in chunk),
                cells=[r['cell_id'] for r in chunk]))
    result=dict(registration_sha256=sha(HERE/'REGISTERED_EVENT_PARTS.csv'),
        max_target_rows=limit,expected_cells=len(reg),expected_events=sum(int(r['events']) for r in reg),
        chunks=plans,all_columns_preserved=True,all_failures_preserved=True)
    dest=OUT/'CHUNK_PLAN.json'
    if dest.exists():assert json.load(dest.open())==result,'Frozen export plan mismatch'
    else:json_save(dest,result)
    return result

def export_one(p):
    dest=OUT/(p['chunk_id']+'_EVENTS_COMPLETE.csv.gz')
    rec=OUT/(p['chunk_id']+'_COMPLETION.json')
    if rec.exists():return json.load(rec.open())
    sources=[];cols=[]
    for cell in p['cells']:
        c=HERE/'results'/cell/'COMPLETION.json'
        if not c.exists():return None
        d=json.load(c.open());assert d['missing_events']==0
        src=c.parent/'EVENTS_COMPLETE.csv.gz'
        assert sha(src)==d['event_result']['sha256'],str(src)
        with gzip.open(src,'rt',encoding='utf-8-sig',newline='') as f:
            cols.extend(x for x in next(csv.reader(f)) if x not in cols)
        sources.append(dict(cell_id=cell,path=str(src),rows=d['exported_events'],sha256=sha(src)))
    tmp=dest.with_name(dest.name+'.tmp');ids=set();rows=0
    with gzip.open(tmp,'wt',encoding='utf-8-sig',newline='',compresslevel=2) as f:
        w=csv.DictWriter(f,fieldnames=cols);w.writeheader()
        for source in sources:
            count=0
            with gzip.open(source['path'],'rt',encoding='utf-8-sig',newline='') as g:
                for row in csv.DictReader(g):
                    assert row['event_id'] not in ids,('duplicate',row['event_id'])
                    ids.add(row['event_id']);w.writerow(row);rows+=1;count+=1
            assert count==source['rows']
    with tmp.open('rb') as f:os.fsync(f.fileno())
    assert rows==p['expected_events']
    # A single bounded read verifies gzip EOF and the actual written row width.
    checked=0
    with gzip.open(tmp,'rt',encoding='utf-8-sig',newline='') as f:
        r=csv.reader(f);assert next(r)==cols
        for row in r:assert len(row)==len(cols);checked+=1
    assert checked==rows
    os.replace(tmp,dest)
    receipt=dict(**p,status='complete',path=str(dest),rows=rows,columns=len(cols),
        bytes=dest.stat().st_size,sha256=sha(dest),unique_event_ids=len(ids),sources=sources,
        all_columns_preserved=True,all_failure_rows_preserved=True,native_fusion_calls=0,scoring_calls=0)
    json_save(rec,receipt)
    print(json.dumps({k:v for k,v in receipt.items() if k not in ['sources','cells']},ensure_ascii=False),flush=True)
    return receipt

def run(limit,watch):
    p=plan(limit)
    while True:
        done=[]
        for chunk in p['chunks']:
            r=export_one(chunk)
            if r is not None:done.append(r)
        rows=[{k:v for k,v in r.items() if k not in ['sources','cells']} for r in done]
        if rows:csv_save(OUT/'EVENT_FILES_INDEX.csv',rows)
        json_save(OUT/'DELIVERY_PROGRESS.json',dict(expected_chunks=len(p['chunks']),complete_chunks=len(done),
            expected_cells=p['expected_cells'],complete_cells=sum(len(r['cells']) for r in done),
            expected_events=p['expected_events'],exported_events=sum(r['rows'] for r in done),
            missing_events=p['expected_events']-sum(r['rows'] for r in done),
            complete=len(done)==len(p['chunks']),underlying_data_version='v2'))
        if len(done)==len(p['chunks']) or not watch:break
        time.sleep(15)

if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--max-rows',type=int,default=20000)
    a.add_argument('--watch',action='store_true');args=a.parse_args();run(args.max_rows,args.watch)
