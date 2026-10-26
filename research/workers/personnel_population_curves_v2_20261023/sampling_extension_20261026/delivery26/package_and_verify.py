"""Build selected repository-relative files and read every ZIP member to EOF.

The same verifier is applied again to bytes downloaded after saving. It validates
inner gzip CRC/footer, CSV widths, JSONL parseability, row counts and member hashes.
No source-only directory inspection is treated as ZIP verification.
"""
from __future__ import annotations
import argparse, csv, gzip, hashlib, io, json, zipfile
from pathlib import Path

def inspect_member(zf, name):
    raw_sha=hashlib.sha256()
    with zf.open(name) as f:
        while block:=f.read(1024*1024):raw_sha.update(block)
    result=dict(path=name,bytes=zf.getinfo(name).file_size,sha256=raw_sha.hexdigest())
    if name.endswith(('.csv','.csv.gz')):
        with zf.open(name) as f:
            binary=gzip.GzipFile(fileobj=f) if name.endswith('.gz') else f
            with io.TextIOWrapper(binary,encoding='utf-8-sig',newline='') as t:
                r=csv.reader(t);fields=next(r,None);rows=0;first=None;last=None;key_sha=hashlib.sha256()
                pos=fields.index('team_key') if fields and 'team_key' in fields else None
                for row in r:
                    if len(row)!=len(fields):raise ValueError(f'CSV width {name} row {rows+1}: {len(row)} != {len(fields)}')
                    if pos is not None:
                        value=row[pos];first=first or value;last=value;key_sha.update((value+'\n').encode())
                    rows+=1
        result.update(format='csv',rows=rows,fields=fields,first_team_key=first,last_team_key=last,
                      ordered_team_key_sha256=key_sha.hexdigest() if pos is not None else None)
    elif name.endswith(('.jsonl','.jsonl.gz')):
        with zf.open(name) as f:
            binary=gzip.GzipFile(fileobj=f) if name.endswith('.gz') else f
            with io.TextIOWrapper(binary,encoding='utf-8-sig') as t:
                rows=0;fields=set();key_sha=hashlib.sha256();first=None;last=None
                for line in t:
                    if not line.strip():raise ValueError('Empty JSONL line '+name)
                    obj=json.loads(line);fields.update(obj);rows+=1
                    if 'team_key' in obj:
                        value=obj['team_key'];first=first or value;last=value;key_sha.update((value+'\n').encode())
        result.update(format='jsonl',rows=rows,fields=sorted(fields),first_team_key=first,last_team_key=last,ordered_team_key_sha256=key_sha.hexdigest())
    elif name.endswith(('.json','.json.gz')):
        with zf.open(name) as f:
            binary=gzip.GzipFile(fileobj=f) if name.endswith('.gz') else f
            with io.TextIOWrapper(binary,encoding='utf-8-sig') as t:obj=json.load(t)
        result.update(format='json',top_type=type(obj).__name__)
    elif name.endswith('.gz'):
        with zf.open(name) as f:
            with gzip.GzipFile(fileobj=f) as inner:
                while inner.read(1024*1024):pass
        result['format']='other_gzip'
    return result

def verify(path, receipt, expected=None):
    path=Path(path);receipt=Path(receipt)
    with path.open('rb') as f:sha=hashlib.file_digest(f,'sha256').hexdigest()
    if expected:
        prior=json.loads(Path(expected).read_text())
        assert prior['zip_sha256']==sha,('download bytes changed',path)
    with zipfile.ZipFile(path) as zf:
        names=zf.namelist();assert len(names)==len(set(names))
        assert all(not n.startswith('/') and '..' not in Path(n).parts for n in names)
        members=[inspect_member(zf,n) for n in names if not n.endswith('/')]
    byname={r['path']:r for r in members};linked_parts=0
    for name,s in byname.items():
        if name.endswith('.scalars.csv.gz'):
            geometry=name.replace('.scalars.csv.gz','.geometry_compact.jsonl.gz')
            if geometry in byname:
                g=byname[geometry]
                assert s['rows']==g['rows'] and s['ordered_team_key_sha256']==g['ordered_team_key_sha256'],('scalar/geometry association',name)
                linked_parts+=1
    if expected:
        assert members==prior['members'],('download inner content changed',path)
    obj=dict(zip_name=path.name,zip_bytes=path.stat().st_size,zip_sha256=sha,
             files=len(members),csv_rows=sum(m.get('rows',0) for m in members if m.get('format')=='csv'),
             jsonl_rows=sum(m.get('rows',0) for m in members if m.get('format')=='jsonl'),
             every_member_read_to_EOF=True,inner_gzip_read_to_EOF=True,members=members)
    obj['scalar_geometry_parts_linked']=linked_parts
    receipt.parent.mkdir(parents=True,exist_ok=True);receipt.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v for k,v in obj.items() if k!='members'},ensure_ascii=False),flush=True)
    return obj

def build(base,selection,output,prefix):
    base=Path(base);output=Path(output);output.parent.mkdir(parents=True,exist_ok=True)
    entries=[]
    for value in json.loads(Path(selection).read_text())['paths']:
        p=base/value
        if not p.is_file():raise FileNotFoundError(p)
        entries.append((p, str(Path(prefix)/value)))
    temporary=output.with_suffix(output.suffix+'.writing')
    with zipfile.ZipFile(temporary,'w',allowZip64=True) as zf:
        for p,arc in entries:
            zf.write(p,arc,compress_type=zipfile.ZIP_STORED if p.suffix in ('.gz','.zip','.png','.jpg','.npz') else zipfile.ZIP_DEFLATED,
                     compresslevel=None if p.suffix in ('.gz','.zip','.png','.jpg','.npz') else 6)
    temporary.replace(output)

def main():
    ap=argparse.ArgumentParser();sub=ap.add_subparsers(dest='action',required=True)
    b=sub.add_parser('build');b.add_argument('--base',type=Path,required=True);b.add_argument('--selection',type=Path,required=True)
    b.add_argument('--output',type=Path,required=True);b.add_argument('--prefix',required=True);b.add_argument('--receipt',type=Path,required=True)
    v=sub.add_parser('verify');v.add_argument('--zip',type=Path,required=True);v.add_argument('--receipt',type=Path,required=True);v.add_argument('--expected',type=Path)
    a=ap.parse_args()
    if a.action=='build':build(a.base,a.selection,a.output,a.prefix);verify(a.output,a.receipt)
    else:verify(a.zip,a.receipt,a.expected)

if __name__=='__main__':main()
