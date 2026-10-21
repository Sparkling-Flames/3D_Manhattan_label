"""Direct-download endpoint shards and exact request/result key index.

The four study stages retain separate identities. All failed fusion endpoints
remain rows. This reads existing endpoints only; it never re-runs fusion.
"""
from __future__ import annotations
import collections,csv,gzip,hashlib,io,json,os
from pathlib import Path
import pandas as pd
from multin_design import HERE,ROOT,OLD,gs,sha,write_csv

STAGES=[('MAIN','BATCH_PLAN.csv','ALL_BATCHES_COMPLETE.json'),('LARGE','LARGE_BLOCK_BATCH_PLAN.csv','LARGE_BLOCK_BATCHES_COMPLETE.json'),('F01','F01_BATCH_PLAN.csv','F01_CAPACITY_BATCHES_COMPLETE.json'),('PURE','PURE_BATCH_PLAN.csv','PURE_BLOCK_BATCHES_COMPLETE.json')]
OUT=HERE/'delivery'

def rows(path):
    with gzip.open(path,'rt',encoding='utf-8-sig',newline='') as f:
        yield from csv.DictReader(f)

class GzipCsv:
    """Bounded CSV buffers, complete gzip members, one durable publication write.

    Keep only compressed chunks until finish. The published tables are already
    split by stage/condition (and large events by direct-download shard), so this
    avoids a giant uncompressed frame while preventing a partly flushed export
    from being mistaken for a complete temporary file in the shared runtime.
    """
    def __init__(self,path,fields,key='team_key'):
        self.path=path;self.tmp=path.with_name(path.name+'.tmp');path.parent.mkdir(parents=True,exist_ok=True)
        self.fields=fields;self.key=key;self.compressed=[];self.buf=[];self.count=0;self.keys=set();self.first=True
    def add(self,row):
        key=row[self.key]
        if key in self.keys:raise ValueError(('duplicate publication key',self.path,key))
        self.keys.add(key);self.buf.append(row);self.count+=1
        if len(self.buf)>=2000:self.flush()
    def flush(self):
        if not self.buf:return
        with io.StringIO(newline='') as stream:
            w=csv.DictWriter(stream,fieldnames=self.fields,extrasaction='ignore')
            if self.first:w.writeheader()
            w.writerows(self.buf);data=stream.getvalue().encode('utf-8-sig' if self.first else 'utf-8')
        self.compressed.append(gzip.compress(data,compresslevel=5,mtime=0));self.first=False;self.buf=[]
    def finish(self,expected):
        self.flush();packed=b''.join(self.compressed)
        with open(self.tmp,'wb') as f:
            if f.write(packed)!=len(packed):raise IOError('short final publication write')
            f.flush();os.fsync(f.fileno())
        self.compressed=[];del packed;seen=set();count=0
        with gzip.open(self.tmp,'rt',encoding='utf-8-sig',newline='') as f:
            reader=csv.reader(f);head=next(reader);ii=head.index(self.key)
            for row in reader:
                if len(row)!=len(head) or row[ii] in seen:raise ValueError(('ragged or duplicate',self.path,count))
                seen.add(row[ii]);count+=1
        if seen!=set(expected) or count!=self.count:raise ValueError(('request-result coverage mismatch',self.path,len(seen),len(expected),count,self.count))
        self.tmp.replace(self.path)
        receipt=dict(path=str(self.path.relative_to(HERE)),rows=count,columns=len(self.fields),bytes=self.path.stat().st_size,sha256=sha(self.path),exact_key_sha256=hashlib.sha256('\n'.join(sorted(seen)).encode()).hexdigest(),gzip_EOF_verified=True,unique_keys=True)
        gs.save(self.path.with_suffix('.json'),receipt);return receipt

def concatenate(sources,path,expected):
    # Previously frozen condition files are immutable checkpoints. A later
    # failure must never force rewriting already published endpoint tables.
    rp=path.with_suffix('.json');key_sha=hashlib.sha256('\n'.join(sorted(expected)).encode()).hexdigest()
    if path.exists() and rp.exists():
        prior=gs.read(rp)
        if (prior.get('rows')==len(expected) and prior.get('exact_key_sha256')==key_sha
            and prior.get('gzip_EOF_verified') and prior.get('unique_keys')
            and prior.get('sha256')==sha(path)):
            return prior
    fields=[]
    for src in sources:
        with gzip.open(src,'rt',encoding='utf-8-sig',newline='') as f:
            for col in next(csv.reader(f)):
                if col not in fields:fields.append(col)
    for attempt in range(1,4):
        writer=GzipCsv(path,fields)
        for source in sources:
            for row in rows(source):writer.add(row)
        try:
            result=writer.finish(expected)
            return result
        except (EOFError,ValueError) as error:
            # A verified source batch can be exported again after a truncated
            # unpublished temporary file. No endpoint or fusion is recomputed.
            # Duplicate keys/ragged source data are not recoverable by retry.
            if isinstance(error,ValueError) and 'request-result coverage mismatch' not in str(error):raise
            with open(OUT/'EXPORT_RECOVERY.jsonl','a') as log:
                log.write(json.dumps(dict(path=str(path.relative_to(HERE)),attempt=attempt,
                    error=str(error),source_batches=[str(s.relative_to(HERE)) for s in sources],
                    native_calls=0,recovery='discard unpublished temporary export and read immutable sources again'),ensure_ascii=False)+'\n')
                log.flush();os.fsync(log.fileno())
            if attempt==3:raise

def export_used_labels():
    from design_matched_events import label_maps,MAIN_METHODS
    maps,_=label_maps();legacy=gs.method_rows();legacy=legacy[legacy.method_id.isin(MAIN_METHODS)]
    source_lookup={}
    for r in legacy.to_dict('records'):
        source=r.get('label_source')
        if not isinstance(source,str) or not source:source=str((OLD/'composition/legacy_composition_labels.csv').relative_to(ROOT))
        source_lookup[(r['method_id'],r['tier'],r['condition'],r['heldout_building'],r['worker_id'])]=source
    new=str((HERE.parent/'taxonomy/ALL_METHOD_LABELS_LOBO.csv.gz').relative_to(ROOT));sources={};labels=[]
    for (method,tier,condition,building),(mapping,parents) in sorted(maps.items()):
        for worker,cl in sorted(mapping.items()):
            key=(method,tier,condition,building,worker);src=source_lookup.get(key,new)
            if src not in sources:sources[src]=sha(ROOT/src)
            scope='nested_building_excluded_v3_selection' if method.startswith('V3_') else 'historical_building_excluded_as_archived'
            if method in ['Rnew2','F01']:scope='historical_fixed_10_building_training_other_12_target_support'
            labels.append(dict(label_key='|'.join(key),method_id=method,tier=tier,condition=condition,
              heldout_building=building,worker_id=worker,class_id=cl,parent_class=parents[worker],
              label_source=src,label_source_sha256=sources[src],training_identity=scope,known=True))
    fields=list(labels[0]);target=OUT/'FROZEN_EVALUATION_LABELS.csv.gz';writer=GzipCsv(target,fields,key='label_key')
    for r in labels:writer.add(r)
    receipt=writer.finish({r['label_key'] for r in labels});receipt['sources']=sources;return receipt

def run():
    OUT.mkdir(exist_ok=True)
    for _,_,flag in STAGES:
        if not (HERE/flag).exists():raise RuntimeError('Wait for completed stage: '+flag)
    fields=['index_key','team_key','endpoint_stage','condition','pool_id','image','building','n','member_workers','batch_id','scalar_file','geometry_file','request_file','complete_evaluable','score_status','B8L2_available','endpoint_origin','request_cached','historical_583261_set_overlap','shared_key_with_prior_stage','canonical_stage','canonical_batch_id']
    index=GzipCsv(OUT/'ENDPOINT_KEY_INDEX.csv.gz',fields,key='index_key');index_keys=set();allkeys={};deliverables=[export_used_labels()];stage_rows=[];cache_origins=collections.Counter()
    for stage,plan_name,_ in STAGES:
        plan=pd.read_csv(HERE/plan_name);stage_all=set();per_condition=collections.defaultdict(list)
        for bid in plan.batch_id:
            folder=HERE/'batches'/bid;req=list(rows(folder/'REQUESTS.csv.gz'));request={r['team_key']:r for r in req}
            if len(request)!=len(req):raise ValueError('duplicate registered stage request')
            if stage_all&request.keys():raise ValueError('same stage endpoint appears in more than one batch')
            stage_all.update(request);condition=req[0]['condition'];per_condition[condition].append(bid)
            geometry={r['team_key']:hashlib.sha256(r['geometry_json'].encode()).hexdigest() for r in rows(folder/'ENDPOINT_GEOMETRY.csv.gz')}
            if geometry.keys()!=request.keys():raise ValueError('geometry request mismatch')
            values=set();states=collections.Counter();complete=0
            for r in rows(folder/'ENDPOINT_SCALARS.csv.gz'):
                key=r['team_key'];values.add(key);q=request[key];prior=allkeys.get(key);core=(r.get('B8L2'),r.get('D10'),r.get('nodes'),r.get('score_status'),geometry[key])
                if prior is not None and prior[2]!=core:raise ValueError(('conflicting deterministic endpoint across stages',key))
                if prior is None:allkeys[key]=(stage,bid,core)
                states[r['score_status']]+=1;complete+=r['complete_evaluable'].lower()=='true';cache_origins[r.get('endpoint_origin','')]+=1
                scalar=OUT/f'{stage}_{condition.upper()}_ENDPOINT_SCALARS.csv.gz';geo=OUT/f'{stage}_{condition.upper()}_ENDPOINT_GEOMETRY.csv.gz';ik=stage+'|'+key;index_keys.add(ik)
                index.add(dict(index_key=ik,team_key=key,endpoint_stage=stage,condition=condition,pool_id=q['pool_id'],image=q['image'],building=q['building'],n=q['n'],member_workers=q['member_workers'],batch_id=bid,scalar_file=str(scalar.relative_to(HERE)),geometry_file=str(geo.relative_to(HERE)),request_file=str((folder/'REQUESTS.csv.gz').relative_to(HERE)),complete_evaluable=r['complete_evaluable'],score_status=r['score_status'],B8L2_available=bool(r.get('B8L2')),endpoint_origin=r.get('endpoint_origin'),request_cached=q['cached'],historical_583261_set_overlap=q['historical_583261_set_overlap'],shared_key_with_prior_stage=prior is not None,canonical_stage=allkeys[key][0],canonical_batch_id=allkeys[key][1]))
            if values!=request.keys():raise ValueError('scalar request mismatch')
            stage_rows.append(dict(stage=stage,batch_id=bid,condition=condition,requested=len(request),result_rows=len(values),missing=0,complete=complete,failure=len(request)-complete,status_counts=json.dumps(dict(states),ensure_ascii=False),cached_requests=sum(q['cached'].lower()=='true' for q in req)))
        for condition,bids in per_condition.items():
            keys=set()
            for bid in bids:keys.update(r['team_key'] for r in rows(HERE/'batches'/bid/'REQUESTS.csv.gz'))
            for kind in ['SCALARS','GEOMETRY']:
                target=OUT/f'{stage}_{condition.upper()}_ENDPOINT_{kind}.csv.gz'
                rr=concatenate([HERE/'batches'/bid/f'ENDPOINT_{kind}.csv.gz' for bid in bids],target,keys);rr.update(stage=stage,condition=condition,kind=kind,batches=bids);deliverables.append(rr)
            gs.save(OUT/f'{stage}_{condition.upper()}_ENDPOINTS_COMPLETE.json',dict(status='complete',stage=stage,condition=condition,requested=len(keys),missing_results=0,files=[r for r in deliverables if r.get('stage')==stage and r.get('condition')==condition]))
            print(json.dumps(dict(stage=stage,condition=condition,endpoint_rows=len(keys),direct_shards_complete=True)),flush=True)
    deliverables.append(index.finish(index_keys));write_csv(OUT/'STAGE_BATCH_RESULT_COVERAGE.csv',pd.DataFrame(stage_rows))
    receipt=dict(status='complete',registered_stage_endpoint_references=len(index_keys),global_unique_endpoint_keys=len(allkeys),reused_key_references_across_stages=len(index_keys)-len(allkeys),missing_requested_endpoint_results=0,all_gzip_EOF_and_exact_keys_verified=True,failed_endpoints_retained=True,source_study_identities=['main_complete_conditional_panels','original_large_actual_m','F01_full_known_new_source_census','directed_pure_class_seat_blocks'],native_calls=0,origin_reference_counts=dict(cache_origins),files=deliverables)
    gs.save(OUT/'ENDPOINT_DELIVERY_MANIFEST.json',receipt);print(json.dumps({k:v for k,v in receipt.items() if k!='files'},ensure_ascii=False),flush=True)

if __name__=='__main__':run()
