"""Make independently readable CSV/JSONL gzip shards, with complete row ledgers.

CSV field strings and row order are preserved.  Each CSV shard has its own
complete header.  These are logical row partitions, never truncated gzip bytes.
"""
from pathlib import Path
import argparse,csv,gzip,hashlib,io,itertools,json,shutil


def sha_file(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()


def canonical_update(h,row):
    h.update(json.dumps(row,ensure_ascii=False,separators=(',',':')).encode('utf-8')+b'\n')


def key_update(h,key):h.update(str(key).encode('utf-8')+b'\n')


def validate_part(path,kind,fields,expected):
    h=hashlib.sha256();kh=hashlib.sha256();n=0;first=last=None
    with gzip.open(path,'rt',encoding='utf-8-sig',newline='') as f:
        if kind=='csv':
            reader=csv.reader(f);assert next(reader)==fields
            ki=fields.index('team_key')
            for row in reader:
                assert len(row)==len(fields)
                canonical_update(h,row);key=row[ki];key_update(kh,key)
                first=key if first is None else first;last=key;n+=1
        else:
            for line in f:
                row=json.loads(line);assert list(row)==fields
                canonical_update(h,row);key=row['team_key'];key_update(kh,key)
                first=key if first is None else first;last=key;n+=1
    assert n==expected['rows'] and h.hexdigest()==expected['semantic_sha256']
    assert kh.hexdigest()==expected['ordered_team_key_sha256']
    return dict(actual_rows=n,read_to_gzip_eof=True,field_count=len(fields),
                actual_first_team_key=first,actual_last_team_key=last)


def partition(source,directory,rows_per_part,limit_mib,requested_rows=None):
    requested_rows=rows_per_part if requested_rows is None else requested_rows
    kind='csv' if source.name.endswith('.csv.gz') else 'jsonl'
    stem=source.name.removesuffix('.csv.gz').removesuffix('.jsonl.gz')
    target=directory/'table_shards'/stem
    temp=target.with_name(target.name+'.building')
    if temp.exists():shutil.rmtree(temp)
    temp.mkdir(parents=True)
    parts=[];total=0;globalh=hashlib.sha256();globalkey=hashlib.sha256();fields=None
    with gzip.open(source,'rt',encoding='utf-8-sig',newline='') as stream:
        if kind=='csv':
            reader=csv.reader(stream);fields=next(reader);ki=fields.index('team_key')
        else:reader=(json.loads(line) for line in stream)
        for number in itertools.count(1):
            firstrow=next(reader,None)
            if firstrow is None:break
            if fields is None:fields=list(firstrow)
            path=temp/f'part_{number:03d}.{kind}.gz'
            h=hashlib.sha256();kh=hashlib.sha256();partn=0;first=last=None
            with path.open('wb') as raw:
                with gzip.GzipFile(fileobj=raw,mode='wb',compresslevel=5,mtime=0) as z:
                    with io.TextIOWrapper(z,encoding='utf-8',newline='') as out:
                        if kind=='csv':writer=csv.writer(out,lineterminator='\n');writer.writerow(fields)
                        for row in itertools.chain([firstrow],itertools.islice(reader,rows_per_part-1)):
                            if kind=='csv':
                                assert len(row)==len(fields);writer.writerow(row);key=row[ki]
                            else:
                                assert list(row)==fields
                                out.write(json.dumps(row,ensure_ascii=False,separators=(',',':'),allow_nan=False)+'\n');key=row['team_key']
                            canonical_update(h,row);canonical_update(globalh,row)
                            key_update(kh,key);key_update(globalkey,key)
                            first=key if first is None else first;last=key;partn+=1
            if path.stat().st_size>limit_mib*2**20:
                shutil.rmtree(temp)
                if rows_per_part==1:raise ValueError('One row exceeds size limit')
                return partition(source,directory,max(1,rows_per_part//2),limit_mib,requested_rows)
            item=dict(file=str((target/path.name).relative_to(directory)),rows=partn,
                columns=fields,field_count=len(fields),compressed_bytes=path.stat().st_size,
                sha256=sha_file(path),semantic_sha256=h.hexdigest(),
                ordered_team_key_sha256=kh.hexdigest(),source_row_start_1based=total+1,
                source_row_end_1based=total+partn,first_team_key=first,last_team_key=last)
            item['validation']=validate_part(path,kind,fields,item)
            parts.append(item);total+=partn
    if target.exists():shutil.rmtree(target)
    temp.rename(target)
    return dict(source_filename=source.name,kind=kind,source_compressed_sha256=sha_file(source),
        source_compressed_bytes=source.stat().st_size,rows=total,columns=fields,field_count=len(fields),
        semantic_sha256=globalh.hexdigest(),ordered_team_key_sha256=globalkey.hexdigest(),
        requested_rows_per_part=requested_rows,actual_rows_per_part=rows_per_part,
        maximum_part_bytes=max(p['compressed_bytes'] for p in parts),parts=parts,
        source_gzip_read_to_eof=True,all_shard_gzip_read_to_eof=True,
        reconstruction='CSV field strings and row order, or JSON object values and row order, are exact; gzip byte identity is not required.')


def main():
    p=argparse.ArgumentParser();p.add_argument('--directory',type=Path,required=True)
    p.add_argument('--rows',type=int,default=60000);p.add_argument('--limit-mib',type=float,default=90)
    a=p.parse_args();specs=['NEW_ENDPOINT_SCALARS.csv.gz','NEW_ENDPOINT_GEOMETRY_COMPACT.jsonl.gz']
    prefix=a.directory/'NEW_PREFIX_VALUES_COMPACT.csv.gz'
    if prefix.stat().st_size>a.limit_mib*2**20:specs.append(prefix.name)
    datasets=[]
    for name in specs:
        d=partition(a.directory/name,a.directory,a.rows,a.limit_mib);datasets.append(d)
        print(json.dumps({k:v for k,v in d.items() if k not in ('parts','columns')},ensure_ascii=False),flush=True)
    manifest=dict(schema='population_precision_table_shards_v1',datasets=datasets,
        not_sharded_files=[] if prefix.name in specs else [dict(file=prefix.name,compressed_bytes=prefix.stat().st_size,sha256=sha_file(prefix),reason='under 90 MiB; full gzip retained')],
        note='Each listed shard is an entire readable gzip stream; no byte truncation. Restore with engine/restore_table_shards.py.')
    temp=a.directory/'TABLE_SHARD_MANIFEST.json.tmp'
    temp.write_text(json.dumps(manifest,ensure_ascii=False,indent=2));temp.replace(a.directory/'TABLE_SHARD_MANIFEST.json')


if __name__=='__main__':main()
