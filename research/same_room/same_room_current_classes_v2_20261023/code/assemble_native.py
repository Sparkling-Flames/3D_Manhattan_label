"""Join the four independently readable native CSV gzip parts without parsing numbers."""
from pathlib import Path
import argparse, gzip, hashlib, json, os

def assemble(manifest, output):
    cfg=json.loads(manifest.read_text())
    checksum=hashlib.sha256(); rows=0; first_header=None
    output.parent.mkdir(parents=True,exist_ok=True)
    tmp=output.with_suffix(output.suffix+'.tmp')
    with gzip.GzipFile(filename=str(tmp),mode='wb',mtime=0) as target:
        for part in cfg['parts']:
            source=manifest.parent/part['file']
            raw=source.read_bytes()
            if hashlib.sha256(raw).hexdigest()!=part['sha256']:
                raise ValueError(f'Part checksum mismatch: {source}')
            data=gzip.decompress(raw); header,body=data.split(b'\n',1)
            if first_header is None:
                first_header=header;chunk=header+b'\n'+body
            else:
                if header!=first_header:raise ValueError('CSV headers differ')
                chunk=body
            target.write(chunk);checksum.update(chunk)
            rows+=part['rows']
    if checksum.hexdigest()!=cfg['uncompressed_sha256']:
        tmp.unlink(missing_ok=True)
        raise ValueError('Assembled CSV checksum mismatch')
    os.replace(tmp,output)
    print(json.dumps({'output':str(output),'rows':rows,'uncompressed_sha256':checksum.hexdigest(),'numeric_conversion':False}))

if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--manifest',type=Path,default=Path('results/native/PARTS_MANIFEST.json'))
    p.add_argument('--out',type=Path,default=Path('results/native/ENDPOINT_SCALARS.csv.gz'))
    a=p.parse_args();assemble(a.manifest,a.out)
