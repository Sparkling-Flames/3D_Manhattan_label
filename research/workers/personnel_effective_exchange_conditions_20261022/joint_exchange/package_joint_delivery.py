"""Collect complete deduplicated evidence and validate publishable CSV EOFs.

No fitting, endpoint generation or event recomputation. Work copies are excluded.
"""
from __future__ import annotations
from joint_design import *
import csv
import sys


def run():
    refs=pd.read_csv(HERE/'ALL_USED_TEAM_REFERENCES.csv.gz',dtype=str,keep_default_na=False)
    required=set(refs.team_key);scalars={};geometries={}
    for stage in ['native','cached','cross']:
        for condition in ['manual','semi']:
            folder=HERE/'results'/stage/condition
            for kind,target in [('SCALARS',scalars),('GEOMETRY',geometries)]:
                for chunk in pd.read_csv(folder/f'ENDPOINT_{kind}.csv.gz',dtype=str,keep_default_na=False,chunksize=5000):
                    for r in chunk.to_dict('records'):
                        k=r['team_key'];assert k in required
                        if k in target:
                            if kind=='SCALARS':
                                for field in ['B8L2','D10','nodes']:
                                    assert r.get(field)==target[k].get(field),(k,field)
                            else:assert r['geometry_json']==target[k]['geometry_json'],k
                        else:target[k]=r
    assert set(scalars)==set(geometries)==required
    write(HERE/'ALL_USED_ENDPOINT_SCALARS.csv.gz',pd.DataFrame([scalars[k] for k in sorted(scalars)]))
    write(HERE/'ALL_USED_ENDPOINT_GEOMETRY.csv.gz',pd.DataFrame([geometries[k] for k in sorted(geometries)]))
    save(HERE/'DEDUPLICATED_ENDPOINT_RECEIPT.json',dict(status='complete',unique_team_endpoints=len(required),source='completed evaluation subsets; exact duplicate scalar/geometry equality checked',geometry_missing_endpoints=sum(not r['geometry_json'] for r in geometries.values()),scalar_sha256=sha(HERE/'ALL_USED_ENDPOINT_SCALARS.csv.gz'),geometry_sha256=sha(HERE/'ALL_USED_ENDPOINT_GEOMETRY.csv.gz'),original_sources='ALL_USED_TEAM_REFERENCES.csv.gz; ENDPOINT_SOURCE_FILES.csv',new_fusion_calls=0))
    # Add the packager itself to the frozen code manifest without rescan of
    # source endpoint archives. No input or analysis code changes here.
    dp=HERE/'INPUT_AND_CODE_DEPENDENCIES.csv';deps=pd.read_csv(dp)
    for f in sorted(HERE.glob('*.py')):
        key=str(f.relative_to(ROOT));deps=deps[~deps.file.eq(key)]
        deps=pd.concat([deps,pd.DataFrame([dict(file=key,bytes=f.stat().st_size,sha256=sha(f),purpose='new_topic_code')])],ignore_index=True)
    write(dp,deps)
    for name in ['MANUAL_NATIVE_REPORT_RECEIPT.json','SEMI_NATIVE_REPORT_RECEIPT.json']:
        rp=HERE/name;receipt=json.loads(rp.read_text())
        for item in receipt['files']:
            f=HERE/item['file'];item.update(bytes=f.stat().st_size,sha256=sha(f))
        save(rp,receipt)
    files=[f for f in HERE.iterdir() if f.is_file() and not f.name.endswith(('.tmp','.zip')) and f.name not in {'DELIVERY_MANIFEST.csv','DELIVERY_RECEIPT.json'}]
    files+=list((HERE/'summaries').rglob('*.csv'))+list((HERE/'summaries').rglob('*.csv.gz'))+list((HERE/'summaries').rglob('*.json'))
    files+=[f for f in (HERE/'figures').iterdir() if f.is_file()]
    for stage in ['native','cached','cross']:
        for condition in ['manual','semi']:
            files += [HERE/'results'/stage/condition/x for x in ['ENDPOINT_SOURCES.csv','POOL_RESULTS.csv','COMPLETION.json']]
    records=[];csv.field_size_limit(sys.maxsize)
    for f in sorted(set(files)):
        rel=str(f.relative_to(HERE));row=dict(file=rel,bytes=f.stat().st_size,sha256=sha(f),rows='',columns='',primary_key='',duplicate_primary_keys='',csv_eof_verified='')
        if f.name.endswith(('.csv','.csv.gz')):
            opener=gzip.open if f.suffix=='.gz' else open
            with opener(f,'rt',encoding='utf-8-sig',newline='') as stream:
                reader=csv.reader(stream);header=next(reader);n=0;seen=set();duplicate=0
                if 'event_id' in header:pk=['event_id']
                elif 'team_key' in header:pk=['team_key']
                elif 'physical_set_id' in header:pk=['physical_set_id']
                elif 'common_anchor_id' in header and 'method_id' in header:pk=['common_anchor_id','method_id']
                else:pk=[]
                inds=[header.index(k) for k in pk]
                for r in reader:
                    assert len(r)==len(header),(rel,n,len(r),len(header));n+=1
                    if pk:
                        key=tuple(r[i] for i in inds);duplicate+=key in seen;seen.add(key)
                row.update(rows=n,columns=len(header),primary_key='|'.join(pk),duplicate_primary_keys=duplicate if pk else '',csv_eof_verified=True)
        records.append(row)
    manifest=pd.DataFrame(records);write(HERE/'DELIVERY_MANIFEST.csv',manifest)
    save(HERE/'DELIVERY_RECEIPT.json',dict(status='complete',files=len(manifest),total_bytes=int(manifest.bytes.sum()),csv_files_eof_validated=int(manifest.csv_eof_verified.eq(True).sum()),event_files=manifest[manifest.file.str.endswith('_EVENTS_COMPLETE.csv.gz')][['file','rows','columns','primary_key','duplicate_primary_keys','sha256']].to_dict('records'),deduplicated_endpoints=len(required),excluded='results per-pool working shards, duplicated endpoint subsets, all .tmp files, old whole-cache archives, environments and images',manifest_sha256=sha(HERE/'DELIVERY_MANIFEST.csv')))
    print((HERE/'DELIVERY_RECEIPT.json').read_text())


if __name__=='__main__':run()
