#!/usr/bin/env python3
"""Build / read complete delivery archives, including nested compressed tables.

Validation is performed on bytes read from the ZIP, not its source directory.
The same command is used after persistent-download round trips.
"""
from pathlib import Path
import argparse, csv, gzip, hashlib, io, json, zipfile

def check_zip(path):
    path=Path(path);records=[]
    with zipfile.ZipFile(path) as z:
        for entry in z.infolist():
            if entry.is_dir():continue
            h=hashlib.sha256();nbytes=0
            with z.open(entry) as f:
                while True:
                    b=f.read(1024*1024)
                    if not b:break
                    h.update(b);nbytes+=len(b)
            r=dict(member=entry.filename,bytes=nbytes,sha256=h.hexdigest(),crc_read_to_eof=True)
            name=entry.filename.lower()
            if name.endswith(('.csv','.csv.gz')):
                with z.open(entry) as stream:
                    binary=gzip.GzipFile(fileobj=stream) if name.endswith('.gz') else stream
                    with io.TextIOWrapper(binary,encoding='utf-8-sig',newline='') as txt:
                        reader=csv.reader(txt);header=next(reader);count=0
                        for row in reader:
                            if len(row)!=len(header):raise ValueError((entry.filename,count+2,len(row),len(header)))
                            count+=1
                    r.update(rows=count,fields=header,inner_read_to_eof=True)
            elif name.endswith(('.jsonl','.jsonl.gz')):
                with z.open(entry) as stream:
                    binary=gzip.GzipFile(fileobj=stream) if name.endswith('.gz') else stream
                    with io.TextIOWrapper(binary,encoding='utf-8-sig') as txt:
                        count=0;first_keys=None
                        for line in txt:
                            obj=json.loads(line);count+=1
                            if first_keys is None:first_keys=sorted(obj) if isinstance(obj,dict) else []
                    r.update(rows=count,first_record_fields=first_keys,inner_read_to_eof=True)
            elif name.endswith(('.json','.json.gz')):
                with z.open(entry) as stream:
                    binary=gzip.GzipFile(fileobj=stream) if name.endswith('.gz') else stream
                    with io.TextIOWrapper(binary,encoding='utf-8-sig') as txt:
                        obj=json.load(txt)
                    r.update(json_type=type(obj).__name__,inner_read_to_eof=True)
            elif name.endswith('.gz'):
                with z.open(entry) as stream,gzip.GzipFile(fileobj=stream) as f:
                    size=0
                    while True:
                        b=f.read(1024*1024)
                        if not b:break
                        size+=len(b)
                r.update(inner_bytes=size,inner_read_to_eof=True)
            records.append(r)
    return dict(archive=str(path.resolve()),archive_bytes=path.stat().st_size,
        archive_sha256=hashlib.file_digest(path.open('rb'),'sha256').hexdigest(),
        files=len(records),all_members_read_to_eof=True,records=records)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--zip',type=Path,required=True)
    ap.add_argument('--receipt',type=Path,required=True);ap.add_argument('--file-list',type=Path)
    ap.add_argument('--root',type=Path);ap.add_argument('--archive-prefix',default='')
    a=ap.parse_args()
    if a.file_list:
        paths=[line.strip() for line in a.file_list.read_text().splitlines() if line.strip()]
        a.zip.parent.mkdir(parents=True,exist_ok=True)
        with zipfile.ZipFile(a.zip,'w',allowZip64=True) as z:
            for relative in paths:
                p=a.root/relative
                if not p.is_file():raise FileNotFoundError(p)
                compression=zipfile.ZIP_STORED if p.suffix in ['.gz','.zip','.png','.pdf'] else zipfile.ZIP_DEFLATED
                z.write(p,str(Path(a.archive_prefix)/relative),compress_type=compression)
    result=check_zip(a.zip);a.receipt.parent.mkdir(parents=True,exist_ok=True)
    a.receipt.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k!='records'},ensure_ascii=False))

if __name__=='__main__':main()
