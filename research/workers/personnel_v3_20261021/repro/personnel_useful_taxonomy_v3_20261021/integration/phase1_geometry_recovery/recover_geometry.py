#!/usr/bin/env python3
"""Recover saved phase-1 geometries without importing any fusion/scoring engine.

Read at most one original pool cache at a time, retain <=5000 export rows, save
complete in-memory-compressed gzip shards atomically with fsync, then concatenate
valid gzip members into one CSV stream. Source tables and caches are read-only.
"""
import collections, csv, gc, gzip, hashlib, io, json, math, os, resource, sqlite3, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
V3 = HERE.parents[1]
ROOT = V3.parents[2]
OLD = ROOT/'research/workers/personnel_global_composition_20261021'
COMP = OLD/'composition'
SCALARS = COMP/'TEAMS_SCALARS.csv.gz'
ABC = OLD/'continuation_20261021/event_repair/ABC_ENDPOINTS_REFERENCED.csv.gz'
FIELDS = ['team_key','pool_id','member_workers','k','score_status','complete_evaluable','geometry_json',
          'node_supports','minimum_support','reference_id','reference_version']
META = [c for c in FIELDS if c!='geometry_json']+['B8L2','D10']
CHUNK_SIZE = 5000
EXPECTED_ALL = 291904
EXPECTED_ABC = 38789
OUTPUT = HERE/'PHASE1_ALL_291904_ENDPOINT_GEOMETRY.csv.gz'
# The unchanged global_study.existing_cache source list. We do not call the
# function because it eagerly materializes every cached Python object at once.
TAX = ROOT/'research/workers/personnel_taxonomy_20261021'
LEGACY = [TAX/'fusion/TEAMS.json.gz',TAX/'fusion/NESTED_TEAMS.json.gz',
    TAX/'fusion/a2_specific/TEAMS.json.gz',TAX/'fusion/semi_position/TEAMS.json.gz',
    ROOT/'research/workers/personnel_interchangeability_followup_20261020/audit_corner/prior_teams.json.gz',
    ROOT/'research/workers/personnel_profiles_composition_20261020/source/claims/claim_teams.json.gz']

def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()

def sync_dir(path):
    fd=os.open(str(path),os.O_RDONLY)
    try:os.fsync(fd)
    finally:os.close(fd)

def atomic(path,raw):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);tmp=path.with_name(path.name+'.partial')
    with tmp.open('wb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
    os.replace(tmp,path);sync_dir(path.parent)

def jsonsave(path,x):
    atomic(path,(json.dumps(x,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False)+'\n').encode())

def csvbytes(rows,fields,header=True,bom=False):
    out=io.StringIO(newline='');w=csv.DictWriter(out,fieldnames=fields,lineterminator='\n')
    if header:w.writeheader()
    w.writerows(rows);return out.getvalue().encode('utf-8-sig' if bom else 'utf-8')

def csvrows(path):
    with gzip.open(path,'rt',encoding='utf-8-sig',newline='') if '.gz' in Path(path).suffixes else Path(path).open(encoding='utf-8-sig',newline='') as f:
        reader=csv.DictReader(f)
        yield from reader

def read_json(path):
    with gzip.open(path,'rt',encoding='utf-8') if str(path).endswith('.gz') else Path(path).open(encoding='utf-8') as f:return json.load(f)

def norm(x):
    if x is None:return ''
    if isinstance(x,list):return '|'.join(map(str,x))
    return str(x)

def row_export(row,expected):
    assert 'geometry' in row, ('missing_native_geometry_field',row['team_key'])
    ws=row['member_workers'];key=row['pool_id']+'__'+hashlib.sha256(json.dumps(sorted(ws),separators=(',',':')).encode()).hexdigest()[:20]
    assert key==row['team_key'] and len(set(ws))==int(row['k'])
    for field in META:
        actual=norm(row.get(field));want=expected.get(field,'')
        if field in ['k','minimum_support']:
            assert (actual==want) or (actual and want and float(actual)==float(want)),(key,field,actual,want)
        elif field in ['B8L2','D10']:
            assert (not actual and not want) or (actual and want and math.isclose(float(actual),float(want),rel_tol=1e-12,abs_tol=1e-10)),(key,field,actual,want)
        else: assert actual==want,(key,field,actual,want)
    gj=json.dumps(row['geometry'],ensure_ascii=False,separators=(',',':'),allow_nan=False)
    assert json.loads(gj)==row['geometry']
    r={f:row.get(f) for f in FIELDS};r.update(member_workers='|'.join(ws),
        node_supports='|'.join(map(str,row.get('node_supports',[]))),geometry_json=gj)
    return r

def main():
    started=time.monotonic();HERE.mkdir(parents=True,exist_ok=True);(HERE/'shards').mkdir(exist_ok=True)
    required=collections.defaultdict(set);full_rows=0
    # Some old per-pool *derived scalar* gzip files have incomplete footers.
    # The complete 291904-row canonical CSV is the authority. Keep its small
    # metadata selection on disk, not as 291904 native Python dictionaries.
    dbpath=HERE/'runtime_metadata.sqlite'
    if dbpath.exists():dbpath.unlink()
    db=sqlite3.connect(dbpath);db.execute('PRAGMA cache_size=-2048');db.execute('PRAGMA journal_mode=OFF')
    db.execute('CREATE TABLE meta (team_key TEXT PRIMARY KEY, pool_id TEXT, value TEXT)')
    batch=[]
    with gzip.open(SCALARS,'rt',encoding='utf-8-sig',newline='') as f:
        rr=csv.DictReader(f);scalar_field_count=len(rr.fieldnames);assert scalar_field_count==97
        for r in rr:
            assert r['team_key'] not in required[r['pool_id']]
            required[r['pool_id']].add(r['team_key']);full_rows+=1
            batch.append((r['team_key'],r['pool_id'],json.dumps({k:r.get(k,'') for k in META},separators=(',',':'))))
            if len(batch)==CHUNK_SIZE:db.executemany('INSERT INTO meta VALUES (?,?,?)',batch);batch=[]
    if batch:db.executemany('INSERT INTO meta VALUES (?,?,?)',batch)
    db.execute('CREATE INDEX meta_pool ON meta(pool_id)');db.commit();del batch
    assert full_rows==EXPECTED_ALL
    abc={r['team_key'] for r in csvrows(ABC)};assert len(abc)==EXPECTED_ABC
    target_keys=set().union(*required.values());assert abc<=target_keys
    indexes=list(csvrows(COMP/'ENDPOINT_SHARD_INDEX.csv'))
    assert {r['pool_id'] for r in indexes}==set(required)
    for x in indexes:assert len(required[x['pool_id']])==int(x['complete_endpoints'])
    input_receipt=dict(source_identity='phase1_personnel_global_composition_20261021_native_cache_reexport',
        scalar_source=str(SCALARS.relative_to(ROOT)),scalar_sha256=sha(SCALARS),scalar_rows=full_rows,scalar_fields=scalar_field_count,
        abc_source=str(ABC.relative_to(ROOT)),abc_sha256=sha(ABC),abc_unique_teams=len(abc),
        source_index=str((COMP/'ENDPOINT_SHARD_INDEX.csv').relative_to(ROOT)),source_index_sha256=sha(COMP/'ENDPOINT_SHARD_INDEX.csv'),
        source_contract=str((COMP/'global_study.py').relative_to(ROOT)),source_contract_sha256=sha(COMP/'global_study.py'),
        fusion_calls=0,scoring_calls=0,shard_max_rows=CHUNK_SIZE,geometry_schema=FIELDS)
    progress_path=HERE/'RECOVERY_PROGRESS.json';parts=[];pool_receipts=[];seen=set()
    if progress_path.exists():
        previous=read_json(progress_path);assert previous['input_receipt']==input_receipt
        parts=previous['shards'];pool_receipts=previous.get('pools',[])
        for part in parts:
            path=HERE/part['path'];assert sha(path)==part['sha256'];count=0
            for r in csvrows(path):
                assert r['team_key'] in target_keys and r['team_key'] not in seen;seen.add(r['team_key']);count+=1
            assert count==part['rows']
    def progress(stage):
        jsonsave(progress_path,dict(stage=stage,input_receipt=input_receipt,shards=parts,pools=pool_receipts,
            recovered_unique=len(seen),abc_recovered=len(abc&seen),peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss))
    progress('input_key_inventory_saved')
    def flush(rows,pid,source):
        if not rows:return
        assert len(rows)<=CHUNK_SIZE
        raw=csvbytes(rows,FIELDS,bom=True);z=gzip.compress(raw,compresslevel=5,mtime=0)
        assert gzip.decompress(z)==raw
        path=HERE/'shards'/f'part_{len(parts)+1:04d}_GEOMETRY.csv.gz';atomic(path,z)
        count=0
        for r in csvrows(path):
            assert r['team_key'] not in seen;seen.add(r['team_key']);count+=1
        assert count==len(rows)
        parts.append(dict(path=str(path.relative_to(HERE)),pool_id=pid,source=str(source.relative_to(ROOT)),rows=count,
            bytes=len(z),sha256=hashlib.sha256(z).hexdigest(),eof_crc_verified=True,header_included=True))
        progress('bounded_geometry_shards_saved')
    completed={r['pool_id'] for r in pool_receipts if not r['missing']}
    for ix,item in enumerate(sorted(indexes,key=lambda x:x['pool_id'])):
        pid=item['pool_id'];need=required[pid]
        expect={k:json.loads(value) for k,value in db.execute('SELECT team_key,value FROM meta WHERE pool_id=?',(pid,))}
        assert set(expect)==need
        if need<=seen:
            # A resumed early shard may have been checked against its original
            # per-pool scalar file. Reconfirm native metadata and Q against the
            # complete canonical scalar before treating it as recovered.
            source=COMP/item['geometry_shard'];payload=read_json(source)
            for row in payload['teams']:
                if row['team_key'] in need:row_export(row,expect[row['team_key']])
            del payload,expect;gc.collect();continue
        sources=[];cachepaths=[COMP/item['geometry_shard'],COMP/'runtime/priority_endpoints'/(pid+'.json.gz'),COMP/'benchmark_endpoints'/(pid+'.json.gz')]
        for source in cachepaths:
            if need<=seen:break
            if not source.exists():continue
            source_hash=sha(source)
            if source==cachepaths[0] and item.get('raw_cache_sha256'):assert source_hash==item['raw_cache_sha256']
            payload=read_json(source)
            if source==cachepaths[0]:
                assert payload['pool_id']==pid and payload['pool_input_sha256']==item['input_pool_sha256']
                assert payload['fusion_gap']==7.5
            rows=payload['teams'];buffer=[];used=0
            for row in rows:
                key=row['team_key']
                if key not in need or key in seen:continue
                buffer.append(row_export(row,expect[key]));used+=1
                if len(buffer)==CHUNK_SIZE:flush(buffer,pid,source);buffer=[]
            flush(buffer,pid,source)
            sources.append(dict(path=str(source.relative_to(ROOT)),sha256=source_hash,bytes=source.stat().st_size,
                native_rows=len(rows),recovered_rows=used,identity='phase1_saved_pool_cache'))
            del rows,payload,buffer;gc.collect()
        # Legacy fallback is activated only for actual missing keys, source by
        # source, and never runs global_study.existing_cache's eager aggregation.
        for source in LEGACY:
            if need<=seen:break
            if not source.exists():continue
            payload=read_json(source);rows=payload.values() if isinstance(payload,dict) else payload;buffer=[];used=0
            for row in rows:
                key=row.get('team_key')
                if key not in need or key in seen or 'geometry' not in row:continue
                buffer.append(row_export(row,expect[key]));used+=1
                if len(buffer)==CHUNK_SIZE:flush(buffer,pid,source);buffer=[]
            flush(buffer,pid,source)
            sources.append(dict(path=str(source.relative_to(ROOT)),sha256=sha(source),bytes=source.stat().st_size,
                recovered_rows=used,identity='unchanged_global_study_existing_cache_source'))
            del rows,payload,buffer;gc.collect()
        pool_receipts=[r for r in pool_receipts if r['pool_id']!=pid]
        pool_receipts.append(dict(pool_id=pid,required=len(need),recovered=len(need&seen),missing=len(need-seen),
            abc_required=len(abc&need),abc_recovered=len(abc&need&seen),sources=sources))
        progress('pool_complete' if need<=seen else 'pool_missing_geometry')
        if (ix+1)%20==0 or ix+1==len(indexes):
            print(json.dumps(dict(pools_processed=ix+1,pools_total=len(indexes),recovered_unique=len(seen),abc_recovered=len(abc&seen),
                peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,elapsed_seconds=round(time.monotonic()-started,1))),flush=True)
        del expect;gc.collect()
    missing=sorted(target_keys-seen)
    atomic(HERE/'MISSING_KEYS.csv',csvbytes([dict(team_key=k,abc_referenced=k in abc) for k in missing],['team_key','abc_referenced'],bom=True))
    # Concatenate self-contained gzip members. Only the first member carries a
    # CSV header/BOM; every source shard remains independently readable too.
    tmp=OUTPUT.with_name(OUTPUT.name+'.partial');full_parts=[]
    with tmp.open('wb') as out:
        for i,part in enumerate(parts):
            raw=gzip.decompress((HERE/part['path']).read_bytes())
            if i:raw=raw.split(b'\n',1)[1]
            z=gzip.compress(raw,compresslevel=5,mtime=0);offset=out.tell();out.write(z)
            full_parts.append(dict(gzip_member=i+1,start_byte=offset,bytes=len(z),rows=part['rows'],shard=part['path']))
        out.flush();os.fsync(out.fileno())
    verified=set();status=collections.Counter();null_geometry=0;unavailable_points=0;lastpool=None;expect={}
    # gzip consumes and validates every member's CRC and EOF during iteration.
    for r in csvrows(tmp):
        assert len(r)==len(FIELDS) and r['team_key'] not in verified and r['team_key'] in target_keys
        if r['pool_id']!=lastpool:
            lastpool=r['pool_id'];expect={k:json.loads(value) for k,value in db.execute('SELECT team_key,value FROM meta WHERE pool_id=?',(lastpool,))}
        for field in FIELDS:
            if field=='geometry_json':continue
            actual,want=r[field],expect[r['team_key']][field]
            assert actual==want or (field in ['k','minimum_support'] and actual and want and float(actual)==float(want)),(r['team_key'],field,actual,want)
        verified.add(r['team_key']);g=json.loads(r['geometry_json']);status[r['score_status']]+=1
        null_geometry+=g is None;unavailable_points+=g is None or g.get('points') is None
    assert verified==seen
    if not missing:assert verified==target_keys and abc<=verified
    os.replace(tmp,OUTPUT);sync_dir(HERE)
    atomic(HERE/'GEOMETRY_SHARD_INDEX.csv',csvbytes(parts,list(parts[0]) if parts else ['path'],bom=True))
    atomic(HERE/'GZIP_MEMBER_INDEX.csv',csvbytes(full_parts,list(full_parts[0]) if full_parts else ['gzip_member'],bom=True))
    atomic(HERE/'POOL_COVERAGE.csv',csvbytes([{k:v for k,v in r.items() if k!='sources'} for r in pool_receipts],
        ['pool_id','required','recovered','missing','abc_required','abc_recovered'],bom=True))
    source_rows=[dict(pool_id=p['pool_id'],**s) for p in pool_receipts for s in p['sources']]
    source_fields=['pool_id','path','sha256','bytes','native_rows','recovered_rows','identity']
    atomic(HERE/'SOURCE_CACHE_MANIFEST.csv',csvbytes(source_rows,source_fields,bom=True))
    result=dict(input_receipt,output=OUTPUT.name,rows=len(verified),fields=len(FIELDS),bytes=OUTPUT.stat().st_size,sha256=sha(OUTPUT),
        abc_referenced_recovered=len(abc&verified),abc_referenced_missing=len(abc-verified),missing_total=len(missing),
        source_pools=len(pool_receipts),source_caches=len(source_rows),standalone_shards=len(parts),gzip_members=len(full_parts),
        native_status_counts=dict(status),native_null_geometry_rows=null_geometry,native_geometry_without_points_rows=unavailable_points,
        all_keys_verified=True,all_gzip_crc_eof_verified=True,source_tables_unchanged=True,
        geometry_values_unchanged=True,scoring_values_checked_against_scalars=True,
        metadata_authority='complete canonical TEAMS_SCALARS.csv.gz; old per-pool derived scalar shards not required',
        peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,elapsed_seconds=round(time.monotonic()-started,3),
        stage='complete' if not missing else 'partial_existing_geometry_only')
    jsonsave(HERE/'RECOVERY_RECEIPT.json',result);progress(result['stage']);db.close();dbpath.unlink()
    print(json.dumps(result,ensure_ascii=False),flush=True)

if __name__=='__main__':main()
