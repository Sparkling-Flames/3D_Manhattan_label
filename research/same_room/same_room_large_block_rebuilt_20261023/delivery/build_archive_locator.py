"""Map every saved scalar row to its actually assigned geometry delivery ZIP."""
import argparse,csv,gzip,hashlib,json
from pathlib import Path

def main(root):
    root=Path(root);parts=json.loads((root/'delivery/GEOMETRY_PACKAGE_ASSIGNMENTS.json').read_text())
    lookup={}
    for part in parts:
        for f in part['files']:
            k=f['geometry_relative'];assert k not in lookup
            lookup[k]=(part['archive_name'],f['rows'],f['geometry_sha256'])
    out=root/'native_endpoints/ENDPOINT_ARCHIVE_LOCATOR.csv.gz';counts={};seen=set();n=0
    fields=['team_key','pool_id','image','image_id','condition','reference_id','reference_version',
            'geometry_archive','geometry_shard','geometry_line_1based','geometry_state_pointer','geometry_shard_sha256']
    with gzip.open(root/'native_endpoints/ENDPOINT_SCALARS.csv.gz','rt',encoding='utf-8-sig',newline='') as src,\
         gzip.open(out,'wt',encoding='utf-8',newline='') as dst:
        r=csv.DictReader(src);w=csv.DictWriter(dst,fieldnames=fields);w.writeheader()
        for row in r:
            key=row['team_key'];assert key not in seen;seen.add(key)
            g=row['geometry_shard'];arc,rows,sha=lookup[g]
            line=int(row['geometry_line_1based']);assert 1<=line<=rows
            counts[g]=counts.get(g,0)+1
            x={k:row[k] for k in fields if k in row}
            x.update(geometry_archive=arc,geometry_shard_sha256=sha)
            w.writerow(x);n+=1
    assert set(counts)==set(lookup)
    assert all(counts[g]==lookup[g][1] for g in lookup)
    h=hashlib.file_digest(out.open('rb'),'sha256').hexdigest()
    receipt={'locator_rows':n,'unique_teams':len(seen),'geometry_shards':len(lookup),'geometry_delivery_parts':len(parts),
      'all_scalar_geometry_pointers_assigned_once':True,'csv_sha256':h,
      'source':'closed final scalar gzip and actual geometry package assignments',
      'source_directory_fields':'historic absolute source paths in package plans are provenance only; resolve geometry_shard relative to native_endpoints'}
    (root/'native_endpoints/ARCHIVE_LOCATOR_RECEIPT.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(receipt,ensure_ascii=False),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',required=True);a=p.parse_args();main(a.root)
