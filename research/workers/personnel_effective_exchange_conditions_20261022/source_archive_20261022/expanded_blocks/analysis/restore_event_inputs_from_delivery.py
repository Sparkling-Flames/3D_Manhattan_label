"""Restore per-cell analysis inputs from immutable delivered event chunks.

Only CSV/gzip read/write; no fusion/scoring. Original completion receipts stay
unchanged. Rebuilt bytes receive a new receipt and SHA rather than masquerading
as the old gzip. Delivery files keep raw CSV values, including failures/blanks.
"""
from __future__ import annotations
from pathlib import Path
import argparse,csv,gzip,hashlib,io,json,os,sys,time
HERE=Path(__file__).resolve().parent
EX=HERE.parent;DELIVERY=EX.parent/'delivery/expanded_events'
DEFAULT_OUTPUT=HERE/'rebuilt_event_inputs'

def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()

def write_json(path,value):
    path.parent.mkdir(parents=True,exist_ok=True);tmp=path.with_name(path.name+'.tmp')
    with tmp.open('w',encoding='utf-8') as f:
        json.dump(value,f,ensure_ascii=False,sort_keys=True,indent=2);f.flush();os.fsync(f.fileno())
    tmp.replace(path)

def verify_values(original,rebuilt):
    n=0;extra=set()
    with gzip.open(original,'rt',encoding='utf-8-sig',newline='') as a,gzip.open(rebuilt,'rt',encoding='utf-8-sig',newline='') as b:
        left=csv.DictReader(a);right=csv.DictReader(b)
        extra=set(right.fieldnames)-set(left.fieldnames)
        assert set(left.fieldnames)<=set(right.fieldnames)
        for x in left:
            y=next(right)
            assert x['event_id']==y['event_id'],('event_order',n)
            assert all(x[k]==y[k] for k in x),('changed_cell_value',x['event_id'])
            assert all(y[k]=='' for k in extra),('nonempty_added_column',x['event_id'])
            n+=1
        assert next(right,None) is None
    return dict(rows_compared=n,all_original_CSV_cell_strings_identical=True,added_blank_columns=sorted(extra))

class Sink:
    def __init__(self,folder,fields,source,chunk_receipt):
        self.folder=folder;folder.mkdir(parents=True,exist_ok=True)
        self.dest=folder/'EVENTS_COMPLETE.csv.gz';self.tmp=self.dest.with_name(self.dest.name+'.tmp')
        self.raw=self.tmp.open('wb')
        self.gz=gzip.GzipFile(filename='',fileobj=self.raw,mode='wb',compresslevel=5,mtime=0)
        self.text=io.TextIOWrapper(self.gz,encoding='utf-8-sig',newline='')
        self.writer=csv.DictWriter(self.text,fieldnames=fields,lineterminator='\n')
        self.writer.writeheader();self.fields=fields;self.rows=0;self.ids=set()
        self.source=source;self.chunk_receipt=chunk_receipt
    def append(self,row):
        assert row['event_id'] not in self.ids
        self.ids.add(row['event_id']);self.writer.writerow(row);self.rows+=1
    def finish(self,verify_original=False):
        self.text.flush();self.text.close();self.raw.flush();os.fsync(self.raw.fileno());self.raw.close()
        assert self.rows==self.source['rows']
        ids=set();count=0
        with gzip.open(self.tmp,'rt',encoding='utf-8-sig',newline='') as f:
            r=csv.reader(f);header=next(r);assert header==self.fields
            ix=header.index('event_id')
            for row in r:
                assert len(row)==len(header)
                assert row[ix] not in ids;ids.add(row[ix]);count+=1
        assert count==self.rows and ids==self.ids
        self.tmp.replace(self.dest)
        original=EX/'results'/self.source['cell_id']/'EVENTS_COMPLETE.csv.gz'
        compare=verify_values(original,self.dest) if verify_original and original.exists() else None
        receipt=dict(status='rebuilt_from_delivered_raw_CSV',cell_id=self.source['cell_id'],rows=self.rows,
          columns=len(self.fields),path=str(self.dest),sha256=sha(self.dest),bytes=self.dest.stat().st_size,
          original_event_gzip_sha256=self.source['sha256'],delivered_chunk_id=self.chunk_receipt['chunk_id'],
          delivered_chunk_sha256=self.chunk_receipt['sha256'],EOF_verified=True,unique_event_ids=len(ids),
          original_gzip_byte_identity_claimed=False,original_value_verification=compare,
          preserved='all delivered cell strings, full columns, exact event ids, missing values and failures',
          native_fusion_calls=0,scoring_calls=0)
        write_json(self.folder/'REBUILD_RECEIPT.json',receipt)
        return receipt

def run(chunk_id=None,cell_id=None,output=DEFAULT_OUTPUT,verify_original=False):
    plan=json.loads((DELIVERY/'CHUNK_PLAN.json').read_text())
    selected=[c for c in plan['chunks'] if (chunk_id is None or c['chunk_id']==chunk_id) and (cell_id is None or cell_id in c['cells'])]
    if not selected:raise ValueError('No registered chunk/cell matches the requested identifier')
    receipts=[];pending=[];started=time.time()
    for c in selected:
        marker=DELIVERY/(c['chunk_id']+'_COMPLETION.json')
        if not marker.exists():pending.append(c['chunk_id']);continue
        rec=json.loads(marker.read_text());assert rec['status']=='complete'
        src=DELIVERY/(c['chunk_id']+'_EVENTS_COMPLETE.csv.gz')
        assert sha(src)==rec['sha256'],('changed_delivery_chunk',c['chunk_id'])
        sources={s['cell_id']:s for s in rec['sources']};needs=set(sources) if cell_id is None else {cell_id}
        for cell in sorted(list(needs)):
            m=output/cell/'REBUILD_RECEIPT.json'
            if m.exists():
                old=json.loads(m.read_text())
                assert old['original_event_gzip_sha256']==sources[cell]['sha256']
                assert old['delivered_chunk_sha256']==rec['sha256']
                assert old['sha256']==sha(output/cell/'EVENTS_COMPLETE.csv.gz')
                receipts.append(old);needs.remove(cell)
        if not needs:continue
        seen=set();sink=None;current=None;total=0
        with gzip.open(src,'rt',encoding='utf-8-sig',newline='') as f:
            reader=csv.DictReader(f)
            for row in reader:
                total+=1;cell=row['cell_id'];assert cell in sources
                if cell!=current:
                    if sink:receipts.append(sink.finish(verify_original));sink=None
                    assert cell not in seen,'Delivery chunk must not split or interleave a cell'
                    seen.add(cell);current=cell
                    if cell in needs:sink=Sink(output/cell,reader.fieldnames,sources[cell],rec)
                if sink:sink.append(row)
            if sink:receipts.append(sink.finish(verify_original))
        assert total==rec['rows'] and seen==set(sources)
        print(json.dumps(dict(chunk_id=c['chunk_id'],restored_cells=len(needs),native_calls=0)),flush=True)
    result=dict(status='complete_requested_subset' if not pending else 'partial_delivery_not_ready',
      registered_delivery_chunks=len(plan['chunks']),requested_chunks=len(selected),pending_chunks=pending,
      restored_cells=len(receipts),restored_rows=sum(r['rows'] for r in receipts),
      expected_all_cells=plan['expected_cells'],expected_all_events=plan['expected_events'],
      output_directory=str(output),all_requested_cells_restored=not pending,
      all_registered_cells_restored=not pending and len(receipts)==plan['expected_cells'],
      input_chunk_plan_sha256=sha(DELIVERY/'CHUNK_PLAN.json'),native_fusion_calls=0,scoring_calls=0,seconds=time.time()-started,
      cell_receipts=[dict(cell_id=r['cell_id'],rows=r['rows'],sha256=r['sha256']) for r in receipts])
    write_json(output/'RESTORATION_COMPLETION.json',result)
    print(json.dumps({k:v for k,v in result.items() if k!='cell_receipts'},ensure_ascii=False))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--chunk');p.add_argument('--cell');p.add_argument('--output',type=Path,default=DEFAULT_OUTPUT)
    p.add_argument('--verify-against-original',action='store_true');a=p.parse_args()
    run(a.chunk,a.cell,a.output,a.verify_against_original)
