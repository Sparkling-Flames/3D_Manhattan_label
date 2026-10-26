"""Map a pinned main checkout and restore only required previous result tables.

No cloning, fusion, scoring, classification or repo mutation is performed. Large
files are reused after complete readback, or reconstructed from the committed
manifests. Every output is closed frequently and parsed through gzip EOF.
"""
from __future__ import annotations
from pathlib import Path
import argparse,csv,gzip,hashlib,io,json,os,subprocess,time
from execute_extension import savejson,sha
from assemble_scalar_table import append_closed

COMMIT='b9bcec809fbaec8ab055931a1abb7baa5db44dac'
POP=Path('research/workers/personnel_population_curves_v2_20261023')
PRECISION=POP/'sampling_precision_20261025'
OLD_SCALAR_SHA='f1f3719e16326c0dd8c48e1fc7594f27eeab8aac6e2aaf7e5f23ac9befdf850a'

def truncate_closed(path):
    path.parent.mkdir(parents=True,exist_ok=True);fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o644);os.close(fd)

def canonical_update(h,r):h.update(json.dumps(r,ensure_ascii=False,separators=(',',':')).encode()+b'\n')
def key_update(h,key):h.update(str(key).encode()+b'\n')

def validate_table(path,spec=None,rows=None,compressed_sha=None):
    kind=spec['kind'] if spec else 'csv';n=0;h=hashlib.sha256();kh=hashlib.sha256();fields=None
    with gzip.open(path,'rt',encoding='utf-8-sig',newline='') as f:
        if kind=='csv':
            reader=csv.reader(f);fields=next(reader)
            if spec:assert fields==spec['columns'],str(path)
            ki=fields.index('team_key') if 'team_key' in fields else None
        else:reader=(json.loads(line) for line in f)
        for r in reader:
            if kind=='csv':
                assert len(r)==len(fields),(str(path),n)
                key=r[ki] if ki is not None else ''
            else:
                if fields is None:fields=list(r)
                assert list(r)==spec['columns'];key=r['team_key']
            if spec:canonical_update(h,r);key_update(kh,key)
            n+=1
    if spec:
        assert n==spec['rows'] and h.hexdigest()==spec['semantic_sha256'],str(path)
        assert kh.hexdigest()==spec['ordered_team_key_sha256'],str(path)
    if rows is not None:assert n==rows,(str(path),n,rows)
    actual_sha=sha(path)
    if compressed_sha:assert actual_sha==compressed_sha,str(path)
    return dict(file=str(path),rows=n,columns=len(fields or []),compressed_sha256=actual_sha,
        semantic_sha256=h.hexdigest() if spec else None,all_gzip_CSV_or_JSONL_read_to_EOF=True)

def restore_bytes(source,entry,target,expected_rows=318816,expected_sha=OLD_SCALAR_SHA):
    if target.exists():return dict(validate_table(target,rows=expected_rows,compressed_sha=expected_sha),action='reused_complete_target')
    full=source/entry['path']
    if full.exists():
        receipt=validate_table(full,rows=expected_rows,compressed_sha=expected_sha);target.parent.mkdir(parents=True,exist_ok=True);target.symlink_to(full.resolve());return dict(receipt,logical_file=str(target),action='linked_complete_source')
    missing=[str(source/p['path']) for p in entry['parts'] if not(source/p['path']).exists()]
    if missing:raise FileNotFoundError('Missing committed byte parts: '+json.dumps(missing,ensure_ascii=False))
    temp=target.with_name(target.name+'.restoring');truncate_closed(temp);total=0
    for item in entry['parts']:
        p=source/item['path'];assert p.stat().st_size==item['bytes'],str(p)
        with p.open('rb') as f:
            for block in iter(lambda:f.read(1024*1024),b''):append_closed(temp,block);total+=len(block)
    assert total==entry['bytes'];r=validate_table(temp,rows=expected_rows,compressed_sha=expected_sha);temp.replace(target);r.update(file=str(target),action='restored_committed_byte_parts');return r

def restore_logical(source,spec,target,block_rows=1000):
    if target.exists():return dict(validate_table(target,spec),action='reused_complete_target')
    full=source/spec['source_filename']
    if full.exists():
        r=validate_table(full,spec);target.parent.mkdir(parents=True,exist_ok=True);target.symlink_to(full.resolve());r.update(logical_file=str(target),action='linked_complete_source');return r
    missing=[str(source/p['file']) for p in spec['parts'] if not(source/p['file']).exists()]
    if missing:raise FileNotFoundError('Missing committed logical row shards: '+json.dumps(missing,ensure_ascii=False))
    kind=spec['kind'];fields=spec['columns'];temp=target.with_name(target.name+'.restoring');truncate_closed(temp)
    whole=hashlib.sha256();wholekeys=hashlib.sha256();total=0;first=True;buffer=[]
    def flush():
        nonlocal first,buffer
        if not buffer:return
        if kind=='csv':
            s=io.StringIO(newline='');w=csv.writer(s,lineterminator='\n')
            if first:w.writerow(fields)
            w.writerows(buffer);raw=s.getvalue().encode('utf-8')
        else:raw=b''.join((json.dumps(r,ensure_ascii=False,separators=(',',':'),allow_nan=False)+'\n').encode() for r in buffer)
        append_closed(temp,gzip.compress(raw,compresslevel=4,mtime=0));first=False;buffer=[]
    for part in spec['parts']:
        p=source/part['file'];assert sha(p)==part['sha256'],str(p);ph=hashlib.sha256();pk=hashlib.sha256();pn=0
        with gzip.open(p,'rt',encoding='utf-8-sig',newline='') as f:
            if kind=='csv':reader=csv.reader(f);assert next(reader)==fields;ki=fields.index('team_key')
            else:reader=(json.loads(line) for line in f)
            for r in reader:
                if kind=='csv':assert len(r)==len(fields);key=r[ki]
                else:assert list(r)==fields;key=r['team_key']
                canonical_update(ph,r);canonical_update(whole,r);key_update(pk,key);key_update(wholekeys,key);pn+=1;total+=1;buffer.append(r)
                if len(buffer)>=block_rows:flush()
        assert pn==part['rows'] and ph.hexdigest()==part['semantic_sha256'] and pk.hexdigest()==part['ordered_team_key_sha256'],str(p)
    flush();assert total==spec['rows'] and whole.hexdigest()==spec['semantic_sha256'] and wholekeys.hexdigest()==spec['ordered_team_key_sha256']
    r=validate_table(temp,spec);temp.replace(target);r.update(file=str(target),action='restored_committed_logical_shards');return r

def map_directory(destination,target,equivalent_files=()):
    destination=Path(destination);target=Path(target).resolve()
    if destination.exists():
        if destination.resolve()==target:return dict(path=str(destination),target=str(target),action='existing_same_directory')
        if equivalent_files and all((destination/f).exists() and (target/f).exists() and sha(destination/f)==sha(target/f) for f in equivalent_files):
            return dict(path=str(destination),target=str(destination.resolve()),action='existing_equivalent_frozen_inputs_preserved')
        raise FileExistsError('Existing mapping differs; left untouched: '+str(destination))
    if destination.is_symlink():raise FileExistsError('Broken existing mapping left untouched: '+str(destination))
    destination.parent.mkdir(parents=True,exist_ok=True);destination.symlink_to(target,target_is_directory=True)
    return dict(path=str(destination),target=str(target),action='created_symlink_no_copy')

def setup(repo,study):
    repo=repo.resolve();study=study.resolve();study.mkdir(parents=True,exist_ok=True);t=time.monotonic()
    actual=subprocess.check_output(['git','-C',str(repo),'rev-parse','HEAD'],text=True).strip()
    if actual!=COMMIT:raise ValueError('Expected pinned main '+COMMIT+', found '+actual+'. Use a separate checkout at the recorded commit; this helper will not alter Git.')
    precision=repo/PRECISION
    maps=[map_directory(study/'repo',repo),map_directory(study/'prior_recovered'/PRECISION,precision,
        ('engine/native_population_runner.py','engine/FROZEN_PARAMETER_RECEIPT.json',
         'engine/frozen_repo/research/workers/pro_personnel_v2_archive_20261019/work_v2_20261019/fusion/INPUT_SNAPSHOT.json.gz'))]
    cache=study/'inputs_cache26';cache.mkdir(exist_ok=True);results=[];missing=[]
    main_manifest=json.loads((repo/POP/'LARGE_TABLE_STORAGE.json').read_text());entry=next(x for x in main_manifest['files'] if x['path']=='results/ENDPOINT_SCALARS.csv.gz')
    try:results.append(restore_bytes(repo/POP,entry,cache/'ENDPOINT_SCALARS_20261023.csv.gz'))
    except FileNotFoundError as exc:missing.append(str(exc))
    manifest_path=precision/'new_endpoints/TABLE_SHARD_MANIFEST.json';manifest=json.loads(manifest_path.read_text());out=cache/'precision25';out.mkdir(exist_ok=True)
    for spec in manifest['datasets']:
        try:results.append(restore_logical(manifest_path.parent,spec,out/spec['source_filename']))
        except FileNotFoundError as exc:missing.append(str(exc))
    receipt=dict(source_commit=actual,study=str(study),path_mappings=maps,tables=results,missing_input_files=missing,complete=not missing,
        no_repo_copy=True,no_repo_mutation=True,no_fusion_or_scoring=True,seconds=time.monotonic()-t,
        sparse_checkout_note='Files listed in the commit can be absent in a sparse checkout. Materialize only the exact listed paths, or supply already restored complete target tables; no missing table is fabricated.')
    savejson(study/'engine26/SETUP_FROM_MAIN_RECEIPT.json',receipt);return receipt

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--repo',type=Path,required=True);p.add_argument('--study',type=Path,required=True);a=p.parse_args();r=setup(a.repo,a.study);print(json.dumps(r,ensure_ascii=False,indent=2));raise SystemExit(0 if r['complete'] else 2)
