#!/usr/bin/env python3
"""Build or verify the self-contained research ZIP using payload SHA256 manifests."""
from __future__ import annotations
import argparse, hashlib, io, json, os, stat, zipfile
from pathlib import Path, PurePosixPath
from PIL import Image
ROOT=Path(__file__).resolve().parent
MANIFEST='PACKAGE_MANIFEST.json'
def sha(b):return hashlib.sha256(b).hexdigest()
def dump(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
def selected(root):
    for p in sorted(root.rglob('*')):
        rel=p.relative_to(root)
        if not p.is_file() or p.is_symlink():continue
        if any(t in rel.parts for t in ['__pycache__','.git']) or p.suffix in ['.pyc','.pyo']:continue
        if rel.as_posix()==MANIFEST or p.name.endswith('_standalone.html'):continue
        yield p
def build(path):
    path=path.resolve()
    if path.is_relative_to(ROOT):raise ValueError('Archive must be outside its payload directory')
    files=list(selected(ROOT));rows=[]
    for p in files:
        b=p.read_bytes();rows.append(dict(path=p.relative_to(ROOT).as_posix(),bytes=len(b),sha256=sha(b)))
    m=dict(schema='complete_package_payload_manifest_v1',archive_root=ROOT.name,source_main_commit='fdfc8a51ad668c83172ca4a9cf0105f417dac61c',payload_count=len(rows),files=rows,exclusions=['manifest itself (archive SHA256 supplied externally)','__pycache__/ and .pyc/.pyo','.git/','review/*_standalone.html (standard HTML and original images included; rebuild with review/build_review.py)'])
    dump(ROOT/MANIFEST,m);path.parent.mkdir(parents=True,exist_ok=True)
    buffer=io.BytesIO()
    with zipfile.ZipFile(buffer,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6,allowZip64=True) as z:
        for p in files+[ROOT/MANIFEST]:z.write(p,ROOT.name+'/'+p.relative_to(ROOT).as_posix())
    content=buffer.getvalue();temporary=path.with_suffix('.zip.tmp')
    with temporary.open('wb') as f:
        f.write(content);f.flush();os.fsync(f.fileno())
    assert sha(temporary.read_bytes())==sha(content),'Archive write differs from complete in-memory bytes'
    temporary.replace(path)
    return verify(path)
def verify(path):
    with zipfile.ZipFile(path) as z:
        members=z.infolist();names=[x.filename for x in members]
        assert len(names)==len(set(names)),'duplicate archive member'
        for inf in members:
            p=PurePosixPath(inf.filename)
            assert not p.is_absolute() and '..' not in p.parts and '\\' not in inf.filename,'unsafe archive path'
            assert not stat.S_ISLNK(inf.external_attr>>16),'symlink archive member'
        bad=z.testzip();assert bad is None,('CRC failure',bad)
        manifests=[n for n in names if n.count('/')==1 and n.endswith('/'+MANIFEST)];assert len(manifests)==1
        manifest_name=manifests[0];m=json.loads(z.read(manifest_name));prefix=m['archive_root']+'/'
        expected={prefix+x['path'] for x in m['files']}|{manifest_name};assert set(names)==expected,'member set differs from manifest'
        pngs=0
        for r in m['files']:
            b=z.read(prefix+r['path']);assert len(b)==r['bytes'] and sha(b)==r['sha256'],r['path']
            if r['path'].lower().endswith('.png'):
                with Image.open(io.BytesIO(b)) as im:im.verify()
                with Image.open(io.BytesIO(b)) as im:im.load()
                pngs+=1
        # Independent nested calibration manifest: every frozen module payload remains intact.
        cm=json.loads(z.read(prefix+'calibration/FILE_MANIFEST.json'))
        for r in cm['files']:
            b=z.read(prefix+'calibration/'+r['path']);assert sha(b)==r['sha256'] and len(b)==r['bytes'],r['path']
    return dict(schema='verified_research_zip_v1',status='passed',archive_name=path.name,archive_bytes=path.stat().st_size,archive_sha256=sha(path.read_bytes()),manifest_sha256=sha(json.dumps(m,ensure_ascii=False,indent=2,allow_nan=False).encode()+b'\n'),payload_files=m['payload_count'],total_members=len(members),uncompressed_payload_bytes=sum(r['bytes'] for r in m['files']),all_crc_passed=True,exact_member_set=True,all_payload_sizes_and_sha256_passed=True,safe_paths_and_no_symlinks=True,calibration_nested_manifest_files_verified=len(cm['files']),png_files_fully_decoded=pngs,standalone_html_rebuildable_and_supplied_separately=True)
def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('mode',choices=['build','verify']);ap.add_argument('archive',type=Path);ap.add_argument('--report',type=Path);a=ap.parse_args()
    result=build(a.archive) if a.mode=='build' else verify(a.archive)
    if a.report:a.report.parent.mkdir(parents=True,exist_ok=True);dump(a.report,result)
    print(json.dumps(result,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
