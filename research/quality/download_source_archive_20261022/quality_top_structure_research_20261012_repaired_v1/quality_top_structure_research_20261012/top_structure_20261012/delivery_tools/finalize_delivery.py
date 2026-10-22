#!/usr/bin/env python3
"""Create the final byte manifest and ZIP after fixed research is complete."""
from pathlib import Path
import argparse
import datetime as dt
import hashlib
import json
import zipfile


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--package-root',type=Path,required=True)
    parser.add_argument('--zip-path',type=Path,required=True)
    args=parser.parse_args()
    package=args.package_root.resolve(); output=args.zip_path.resolve()
    if package in output.parents:
        raise ValueError('ZIP must be outside the package directory.')
    scope=json.loads((package/'provenance/PACKAGE_SCOPE.json').read_text())
    assert scope['study_id']=='top_structure_20261012'
    manifest_path=package/'FILE_MANIFEST_SHA256.json'
    files=[p for p in sorted(package.rglob('*')) if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc' and p!=manifest_path]
    rows=[{'path':p.relative_to(package).as_posix(),'bytes':p.stat().st_size,'sha256':digest(p)} for p in files]
    manifest={'schema':'complete_delivery_bytes_v1','actual_utc':dt.datetime.now(dt.timezone.utc).isoformat(),'round_id':'20261012',
              'actual_main_sha':scope['actual_main_sha'],'file_count_excluding_this_manifest':len(rows),
              'bytes_excluding_this_manifest':sum(r['bytes'] for r in rows),
              'manifest_self_excluded':True,'files':rows}
    manifest_path.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    output.parent.mkdir(parents=True,exist_ok=True)
    if output.exists():
        raise FileExistsError('Choose a new ZIP path; final archives are not silently replaced.')
    with zipfile.ZipFile(output,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p in files+[manifest_path]:
            z.write(p,(Path(package.name)/p.relative_to(package)).as_posix())
    with zipfile.ZipFile(output) as z:
        assert z.testzip() is None
        assert len(z.infolist())==len(files)+1
        for row in rows:
            content=z.read((Path(package.name)/row['path']).as_posix())
            assert len(content)==row['bytes'] and hashlib.sha256(content).hexdigest()==row['sha256']
    result={'zip':str(output),'bytes':output.stat().st_size,'sha256':digest(output),'entries':len(files)+1,
            'all_member_crc_and_sha256_verified':True,'manifest_sha256':digest(manifest_path)}
    output.with_suffix('.manifest.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__':
    main()
