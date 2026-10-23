"""Assign completed, immutable native geometry shards to non-overlapping ZIPs.

This is checkpoint delivery, not a research selection. Every completed shard
is eventually assigned once; --final includes a smaller last part.
"""
import argparse,csv,json
from pathlib import Path

def main(base,deliver,chunk,final):
    base=Path(base).resolve();deliver=Path(deliver).resolve();deliver.mkdir(parents=True,exist_ok=True)
    state=base/'delivery/GEOMETRY_PACKAGE_ASSIGNMENTS.json'
    assigned=json.loads(state.read_text()) if state.exists() else []
    taken={f['geometry_relative'] for part in assigned for f in part['files']}
    candidates=[]
    for rp in sorted((base/'native_endpoints/parts').glob('*/part_*.receipt.json')):
        r=json.loads(rp.read_text());gp=rp.parent/r['geometry_file'];rel=str(gp.relative_to(base/'native_endpoints'))
        if rel in taken:continue
        if not gp.is_file() or gp.stat().st_size!=r['geometry_bytes']:raise ValueError(f'incomplete shard {gp}')
        candidates.append({'geometry_relative':rel,'geometry_source':str(gp),
          'receipt_source':str(rp),'receipt_relative':str(rp.relative_to(base/'native_endpoints')),
          'rows':r['rows'],'pool_id':r['pool_id'],'geometry_sha256':r['geometry_sha256'],
          'scalar_relative':str((rp.parent/r['scalar_file']).relative_to(base/'native_endpoints')),
          'scalar_sha256':r['scalar_sha256']})
    plans=[]
    while len(candidates)>=chunk or (final and candidates):
        files=candidates[:chunk];candidates=candidates[chunk:];i=len(assigned)+1
        name=f'HOHONET_R06_{i:02d}_完整融合几何票账.zip'
        idx=base/f'delivery/GEOMETRY_PART_{i:02d}_INDEX.csv'
        with idx.open('w',newline='') as h:
            w=csv.DictWriter(h,fieldnames=list(files[0]));w.writeheader();w.writerows(files)
        prefix='research/same_room/same_room_large_block_rebuilt_20261023'
        entries=[{'source':str(idx),'archive_path':f'{prefix}/delivery/{idx.name}'}];expected={}
        for f in files:
            g=f'{prefix}/native_endpoints/{f["geometry_relative"]}'
            entries.extend([{'source':f['geometry_source'],'archive_path':g},
                            {'source':f['receipt_source'],'archive_path':f'{prefix}/native_endpoints/{f["receipt_relative"]}'}])
            expected[g]=f['rows']
        manifest=base/f'delivery/GEOMETRY_PART_{i:02d}_PACK_MANIFEST.json'
        manifest.write_text(json.dumps({'output':str(deliver/name),
            'receipt':str(deliver/f'HOHONET_R06_{i:02d}_包内通读回执.json'),
            'entries':entries,'expected_rows':expected},ensure_ascii=False,indent=2)+'\n')
        rec={'part':i,'archive_name':name,'manifest':str(manifest),'rows':sum(f['rows'] for f in files),
             'compressed_geometry_bytes':sum(Path(f['geometry_source']).stat().st_size for f in files),
             'files':files}
        assigned.append(rec);plans.append({k:v for k,v in rec.items() if k!='files'})
    state.write_text(json.dumps(assigned,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'new_parts':plans,'unassigned_complete_shards':len(candidates)},ensure_ascii=False),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--base',required=True);p.add_argument('--deliver',required=True)
    p.add_argument('--chunk',type=int,default=100);p.add_argument('--final',action='store_true')
    a=p.parse_args();main(a.base,a.deliver,a.chunk,a.final)
