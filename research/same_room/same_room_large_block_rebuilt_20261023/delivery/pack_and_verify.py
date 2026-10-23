"""Create an atomic delivery ZIP and read every archived CSV/gzip to EOF.

Input JSON: {output, receipt, entries:[{source, archive_path}], expected_rows:{}}
Directories are expanded by callers, so the manifest lists actual files only.
Already-compressed files are stored without a second compression layer.
"""
from __future__ import annotations
import argparse,csv,gzip,hashlib,io,json,os,sys,zipfile
from pathlib import Path
csv.field_size_limit(sys.maxsize)

def sha_file(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda:f.read(2**20),b''):h.update(chunk)
    return h.hexdigest()

def verify_zip(path, expected_rows=None):
    expected_rows=expected_rows or {}
    receipt={'archive':str(path),'archive_bytes':Path(path).stat().st_size,
             'archive_sha256':sha_file(path),'verification':'actual archive contents read to EOF',
             'files':[]}
    with zipfile.ZipFile(path) as z:
        names=z.namelist()
        if len(names)!=len(set(names)):raise ValueError('duplicate archive names')
        for info in z.infolist():
            if info.is_dir():continue
            name=info.filename;h=hashlib.sha256();n=0
            with z.open(info) as f:
                for chunk in iter(lambda:f.read(2**20),b''):h.update(chunk);n+=len(chunk)
            if n!=info.file_size:raise ValueError(f'wrong archive length: {name}')
            r={'path':name,'bytes':n,'sha256':h.hexdigest()}
            lower=name.lower()
            if lower.endswith(('.csv','.csv.gz','.tsv','.tsv.gz')):
                with z.open(info) as raw:
                    data=gzip.GzipFile(fileobj=raw) if lower.endswith('.gz') else raw
                    with io.TextIOWrapper(data,encoding='utf-8-sig',newline='') as text:
                        reader=csv.reader(text,delimiter='\t' if '.tsv' in lower else ',')
                        header=next(reader,None);count=0
                        if header is None:raise ValueError(f'empty table: {name}')
                        if len(set(header))!=len(header):raise ValueError(f'duplicate table fields: {name}')
                        for row in reader:
                            count+=1
                            if len(row)!=len(header):raise ValueError(f'wrong width {name} row {count}')
                r.update(rows=count,fields=header,eof=True)
                if name in expected_rows and count!=int(expected_rows[name]):
                    raise ValueError(f'wrong row count {name}: {count} != {expected_rows[name]}')
            elif lower.endswith(('.jsonl','.jsonl.gz','.ndjson','.ndjson.gz')):
                with z.open(info) as raw:
                    data=gzip.GzipFile(fileobj=raw) if lower.endswith('.gz') else raw
                    with io.TextIOWrapper(data,encoding='utf-8-sig') as text:
                        count=0
                        for line in text:
                            if not line.strip():continue
                            obj=json.loads(line);count+=1
                r.update(rows=count,jsonl_to_eof=True)
                if name in expected_rows and count!=int(expected_rows[name]):
                    raise ValueError(f'wrong jsonl count {name}')
            elif lower.endswith(('.json','.json.gz')):
                with z.open(info) as raw:
                    data=gzip.GzipFile(fileobj=raw) if lower.endswith('.gz') else raw
                    with io.TextIOWrapper(data,encoding='utf-8-sig') as text:obj=json.load(text)
                r['json_to_eof']=True
            elif lower.endswith('.gz'):
                total=0
                with z.open(info) as raw,gzip.GzipFile(fileobj=raw) as data:
                    for chunk in iter(lambda:data.read(2**20),b''):total+=len(chunk)
                r.update(gzip_to_eof=True,uncompressed_bytes=total)
            receipt['files'].append(r)
    receipt['file_count']=len(receipt['files'])
    receipt['verified']=True
    return receipt

def main(config):
    c=json.loads(Path(config).read_text());out=Path(c['output']);out.parent.mkdir(parents=True,exist_ok=True)
    partial=out.with_name(out.name+'.writing')
    entries=c['entries'];seen=set()
    with zipfile.ZipFile(partial,'w',allowZip64=True,compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for entry in entries:
            source=Path(entry['source']);name=entry['archive_path']
            if name in seen:raise ValueError(f'duplicate requested path {name}')
            seen.add(name)
            if not source.is_file():raise FileNotFoundError(source)
            if name.startswith('/') or '..' in Path(name).parts:raise ValueError('unsafe relative path')
            stored=source.suffix.lower() in {'.gz','.zip','.png','.jpg','.jpeg','.pdf','.webp'}
            z.write(source,name,compress_type=zipfile.ZIP_STORED if stored else zipfile.ZIP_DEFLATED)
    # Closing ZIP precedes verification and atomic rename. An unfinished file
    # never replaces the current deliverable.
    result=verify_zip(partial,c.get('expected_rows'))
    os.replace(partial,out)
    result['archive']=str(out)
    result['source_manifest']=str(config)
    rp=Path(c['receipt']);rp.parent.mkdir(parents=True,exist_ok=True)
    rp.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='files'},ensure_ascii=False),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('config');a=p.parse_args();main(a.config)
