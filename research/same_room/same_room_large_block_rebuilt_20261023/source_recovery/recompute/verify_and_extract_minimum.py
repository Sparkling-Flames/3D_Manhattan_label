#!/usr/bin/env python3
"""Read actual original bytes; extract one complete already-recorded path.

No fusion, scoring, sampling, classification, or effect estimation occurs here.
"""
import csv, gzip, hashlib, io, json
from pathlib import Path

ROOT=Path(__file__).resolve().parent
POP=ROOT/'population_existing_originals'
CASE=POP/'cases/UwV83HsGsw3-12'
OUT=ROOT/'minimum_complete_population_path'
OUT.mkdir(exist_ok=True)

def rows(p):
    data=gzip.decompress(p.read_bytes()) if p.suffix=='.gz' else p.read_bytes()
    reader=csv.DictReader(io.StringIO(data.decode('utf-8-sig'),newline=''))
    rec=list(reader)
    assert all(None not in r for r in rec),p
    return reader.fieldnames,rec

def save_rows(p,fields,data):
    with p.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(data)

of,orders=rows(POP/'design/EXACT_ORDER_DESIGN.csv.gz')
sf,scalars=rows(CASE/'PATH_SCALARS.csv')
geom=json.loads(gzip.decompress((CASE/'CASE_GEOMETRY.json.gz').read_bytes()))
pid=geom['case']['path_id'];pool_id=geom['pool']['pool_id']
order=[r for r in orders if r['path_id']==pid]
assert len(order)==1 and order[0]['pool_id']==pool_id
workers=order[0]['worker_order'].split('|');N=len(workers)
assert N==28 and len(set(workers))==N
path=sorted([r for r in scalars if r['path_id']==pid],key=lambda r:int(r['k']))
assert len(path)==N and [int(r['k']) for r in path]==list(range(1,N+1))
assert set(geom['states'])=={str(k) for k in range(1,N+1)}
raw={r['worker_id']:r for r in geom['pool']['records']}
assert set(raw)==set(workers)
links=[]
for r in path:
    k=int(r['k']);selected=set(workers[:k]);state=geom['states'][str(k)]
    assert selected==set(r['member_workers'].split('|'))
    assert state['n']==k
    assert {a['worker'] for a in state['assignments']}==selected
    assert {raw[w]['object_id'] for w in selected}==set(r['member_object_ids'].split('|'))
    key=pool_id+'__'+hashlib.sha256(json.dumps(sorted(selected),sort_keys=True,separators=(',',':')).encode()).hexdigest()[:20]
    assert key==r['team_key']
    links.append(dict(path_id=pid,pool_id=pool_id,k=k,team_key=key,
       exact_order_source='population_existing_originals/design/EXACT_ORDER_DESIGN.csv.gz',
       scalar_source='population_existing_originals/cases/UwV83HsGsw3-12/PATH_SCALARS.csv',
       geometry_source='population_existing_originals/cases/UwV83HsGsw3-12/CASE_GEOMETRY.json.gz',
       geometry_pointer='/states/'+str(k),
       member_workers='|'.join(sorted(selected)),
       ordered_workers='|'.join(workers[:k]),
       object_ids='|'.join(sorted(raw[w]['object_id'] for w in selected)),
       reference_id=r['reference_id'],
       raw_pool_pointer='/pool',
       status='exact_extraction_from_existing_population_originals_not_large_block_ABC'))
save_rows(OUT/'EXACT_ORDER.csv',of,order)
save_rows(OUT/'PATH_SCALARS.csv',sf,path)
save_rows(OUT/'PREFIX_LINKS.csv',list(links[0]),links)

vf,votes=rows(CASE/'CASE_VOTES.csv')
keys={r['team_key'] for r in path}
assert all(v['path_id']==pid and v['team_key'] in keys for v in votes)
events=rows(CASE/'CASE_EVENTS.csv')[1]
assert all(e['path_id']==pid for e in events)

read_manifest=[]
for root in [POP,ROOT/'reusable_frozen_inputs']:
    if not root.exists():continue
    for f in sorted(root.rglob('*')):
        if not f.is_file():continue
        rawbytes=f.read_bytes();assert len(rawbytes)>0,f
        rec=dict(path=f.relative_to(ROOT).as_posix(),bytes=len(rawbytes),sha256=hashlib.sha256(rawbytes).hexdigest(),read_to_eof=True)
        plain=gzip.decompress(rawbytes) if f.suffix=='.gz' else rawbytes
        if f.name.endswith('.csv') or f.name.endswith('.csv.gz'):
            fields,data=rows(f);rec.update(rows=len(data),fields=fields)
        elif f.name.endswith('.json') or f.name.endswith('.json.gz'):
            j=json.loads(plain.decode('utf-8-sig'));rec.update(json_type=type(j).__name__,top_level_length=len(j) if isinstance(j,(list,dict)) else None)
        read_manifest.append(rec)
receipt=dict(status='passed',operation='zero_fusion_exact_extraction_and_link_check',
 source_commit='e92abe8631d7f01dc192ee796b46f295ece37a6d',
 total_exact_orders=len(orders),natural_paths=sum(r['policy']=='natural_random' for r in orders),
 pool_count=len({r['pool_id'] for r in orders}),
 selected_path_id=pid,selected_pool=pool_id,
 selected_prefixes=N,scalar_original_rows=len(scalars),scalar_original_paths=len({r['path_id'] for r in scalars}),
 geometry_complete_for_selected_path=True,geometry_claim_for_other_3_legacy_paths=False,
 all_selected_member_prefixes_match=True,all_selected_object_ids_match=True,
 all_selected_team_keys_match=True,selected_vote_rows=len(votes),selected_event_rows=len(events),
 raw_records=len(raw),geometry_states=len(geom['states']),
 new_fusion=0,new_scoring=0,new_designs=0,bootstrap_runs=0,
 files=read_manifest)
(ROOT/'READ_AND_LINK_RECEIPT.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:v for k,v in receipt.items() if k!='files'},ensure_ascii=False))
