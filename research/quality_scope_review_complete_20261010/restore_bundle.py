#!/usr/bin/env python3
"""Verify, join and safely extract the portable research ZIP parts (stdlib only)."""
from pathlib import Path,PurePosixPath
import argparse,hashlib,json,os,sys,zipfile

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--verify-only',action='store_true',help='Check every part plus concatenated ZIP hash without writing anything.')
    p.add_argument('--output-dir',type=Path,help='Extraction parent; default: restored next to this script.')
    p.add_argument('--keep-zip',action='store_true',help='Keep assembled ZIP; default removes the newly assembled ZIP after successful extraction.')
    a=p.parse_args();root=Path(__file__).resolve().parent
    spec=json.loads((root/'ARCHIVE_PARTS.json').read_text(encoding='utf-8'));full=hashlib.sha256();size=0
    for item in spec['parts']:
        name=item['file'];part=(root/name).resolve()
        if root not in part.parents:raise SystemExit('Unsafe part path: '+name)
        if not part.is_file():raise SystemExit('Missing part: '+name)
        h=hashlib.sha256();n=0
        with part.open('rb') as f:
            for block in iter(lambda:f.read(1024*1024),b''):h.update(block);full.update(block);n+=len(block);size+=len(block)
        if n!=item['bytes'] or h.hexdigest()!=item['sha256']:raise SystemExit('Part hash/size mismatch: '+name)
    if size!=spec['archive']['bytes'] or full.hexdigest()!=spec['archive']['sha256']:raise SystemExit('Concatenated ZIP hash/size mismatch')
    print(f'PASS: {len(spec["parts"])} parts, {size} bytes, ZIP SHA256 {full.hexdigest()}')
    if a.verify_only:return
    dest=(a.output_dir or root/'restored').resolve();archive=root/(spec['archive']['file']+'.assembling')
    if archive.exists():raise SystemExit('Temporary archive already exists; inspect/remove it before retrying: '+str(archive))
    try:
        with archive.open('xb') as out:
            for item in spec['parts']:
                with (root/item['file']).open('rb') as source:
                    for block in iter(lambda:source.read(1024*1024),b''):out.write(block)
        with zipfile.ZipFile(archive) as z:
            bad=z.testzip()
            if bad:raise RuntimeError('ZIP CRC error: '+bad)
            for member in z.infolist():
                name=PurePosixPath(member.filename)
                if name.is_absolute() or '..' in name.parts or '\\' in member.filename:raise RuntimeError('Unsafe ZIP member: '+member.filename)
                target=(dest/member.filename).resolve()
                if dest not in target.parents:raise RuntimeError('ZIP path escapes output directory')
                if (member.external_attr>>16)&0o170000==0o120000:raise RuntimeError('ZIP symlinks are not permitted')
                if member.is_dir():target.mkdir(parents=True,exist_ok=True);continue
                raw=z.read(member)
                if target.exists():
                    if not target.is_file() or target.read_bytes()!=raw:raise RuntimeError('Refusing to overwrite different existing file: '+str(target))
                    continue
                target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(raw)
        if a.keep_zip:
            final=root/spec['archive']['file']
            if final.exists():raise RuntimeError('Refusing to overwrite existing assembled ZIP: '+str(final))
            archive.rename(final)
        else:archive.unlink()
    except Exception:
        # A partial ZIP may help diagnose interruption; never delete user data.
        raise
    print('Restored: '+str(dest/spec['archive']['root_directory']))
    print('Next: python '+str(dest/spec['archive']['root_directory']/'verify_delivery.py'))
if __name__=='__main__':main()
