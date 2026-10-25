#!/usr/bin/env python3
"""Persist immutable, completed new endpoint geometry in bounded ZIP parts.

Each native receipt is committed after the scalar and JSONL gzip close. Only
such immutable geometry files are included. Packages are disjoint and the
index records which actual output shards each package contains.
"""
from pathlib import Path
import argparse, csv, hashlib, json, zipfile
from package_and_verify import check_zip

PREFIX='research/workers/personnel_population_curves_v2_20261023/sampling_precision_20261025'

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--root',type=Path,required=True)
    ap.add_argument('--target-mib',type=int,default=256);ap.add_argument('--flush',action='store_true')
    a=ap.parse_args();root=a.root;out=root/'deliverables';out.mkdir(exist_ok=True)
    index_path=out/'GEOMETRY_PACKAGE_INDEX.json'
    existing=json.loads(index_path.read_text()) if index_path.exists() else []
    done={r['relative_path'] for pack in existing for r in pack['shards']}
    pending=[]
    for p in sorted((root/'new_endpoints/parts').glob('*/*.receipt.json')):
        r=json.loads(p.read_text());geo=p.parent/r['geometry_file'];rel=str(geo.relative_to(root))
        if rel in done:continue
        if not geo.is_file() or geo.stat().st_size!=r['geometry_bytes']:raise ValueError(geo)
        pending.append(dict(relative_path=rel,pool_id=r['pool_id'],rows=r['rows'],bytes=r['geometry_bytes'],
            sha256=r['geometry_sha256'],reference_receipt=str(p.relative_to(root))))
    target=a.target_mib*1024**2
    if sum(x['bytes'] for x in pending)<target and not a.flush:
        print(json.dumps(dict(waiting=True,pending_shards=len(pending),pending_bytes=sum(x['bytes'] for x in pending))))
        return
    while pending and (a.flush or sum(x['bytes'] for x in pending)>=target):
        group=[];size=0
        while pending and (not group or size+pending[0]['bytes']<=target):
            r=pending.pop(0);group.append(r);size+=r['bytes']
        n=len(existing)+1;name=f'HOHONET_P03_geometry_{n:02d}.zip';zpath=out/name
        manifest=dict(archive=name,status='completed_new_native_geometry',shards=group,
            rows=sum(x['rows'] for x in group),geometry_bytes=size,
            archive_member_prefix=PREFIX,source_commit='40d0fe62dc62f6f6c12723af10195b7abb7bc9fe',
            note='New full native states only. Match NEW_ENDPOINT_SCALARS geometry_shard and line. Old endpoint dependencies remain in main; benchmark states are in P01.')
        with zipfile.ZipFile(zpath,'w',compression=zipfile.ZIP_STORED,allowZip64=True) as z:
            for r in group:z.write(root/r['relative_path'],str(Path(PREFIX)/r['relative_path']))
            z.writestr(str(Path(PREFIX)/'new_endpoints'/f'GEOMETRY_PART_{n:02d}_MANIFEST.json'),json.dumps(manifest,ensure_ascii=False,indent=2))
        checked=check_zip(zpath)
        if sum(r.get('rows',0) for r in checked['records'])!=manifest['rows']:raise ValueError('Geometry row count mismatch')
        manifest.update(archive_sha256=checked['archive_sha256'],archive_bytes=checked['archive_bytes'],zip_internal_read_to_eof=True)
        (out/f'P03_GEOMETRY_{n:02d}_ZIP_READ_RECEIPT.json').write_text(json.dumps(checked,ensure_ascii=False,indent=2))
        existing.append(manifest);index_path.write_text(json.dumps(existing,ensure_ascii=False,indent=2))
        print(json.dumps({k:v for k,v in manifest.items() if k!='shards'},ensure_ascii=False),flush=True)
        if not a.flush:break
    flat=[dict(archive=p['archive'],archive_sha256=p['archive_sha256'],**r) for p in existing for r in p['shards']]
    if flat:
        with (out/'GEOMETRY_PACKAGE_INDEX.csv').open('w',encoding='utf-8',newline='') as f:
            w=csv.DictWriter(f,fieldnames=list(flat[0]));w.writeheader();w.writerows(flat)

if __name__=='__main__':main()
