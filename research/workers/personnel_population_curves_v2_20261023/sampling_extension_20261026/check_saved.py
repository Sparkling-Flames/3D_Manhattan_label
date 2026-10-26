"""Check archive sizes, saved-table EOF/schema and pointer readability; no hashes or analysis."""
import json
from collections import Counter
import read_saved as saved


def main():
    source = list(saved.csv_rows(saved.BASE/'LOCAL_SOURCE_FILES.csv'))
    for row in source:
        path = saved.resolve(row['archive_path'])
        if path.stat().st_size != int(row['bytes']):
            raise ValueError('Archived size differs: '+str(path))
    tables = []
    for alias, spec in saved.ACCESS['tables'].items():
        count=0;selected=0;cohorts=Counter()
        for row in saved.rows(alias,defaults=False):
            count+=1
            selected+=all(row[k]==str(v) for k,v in spec['default_filters'].items())
            if 'cohort' in row:cohorts[row['cohort']]+=1
            elif 'version' in row:cohorts[row['version']]+=1
        if not count or not selected:
            raise ValueError('Empty required interface: '+alias)
        tables.append(dict(alias=alias,rows=count,default_rows=selected,cohorts=dict(cohorts),read_to_EOF=True))
        print(alias,count,'rows;',selected,'default rows',flush=True)
    shards=list(saved.rows('endpoint_shards'))
    counts=Counter()
    for shard in shards:
        counts[shard['stage']]+=int(shard['rows'])
        for key in ('scalar_file','geometry_file','full_state_file'):
            if shard[key] and not saved.resolve(shard[key],saved.BASE).is_file():
                raise FileNotFoundError(shard[key])
    assert len(shards)==5914 and counts=={'1':784140,'2':572517},counts
    checked=[]
    for stage in ('1','2'):
        part=[s for s in shards if s['stage']==stage]
        for index in (0,len(part)//2,len(part)-1):
            row=next(saved.csv_rows(saved.resolve(part[index]['scalar_file'],saved.BASE)))
            saved.geometry(row);checked.append(row['team_key'])
    prior=saved.ROOT/'research/workers/personnel_population_curves_v2_20261023/sampling_precision_20261025/new_endpoints'
    reused=json.loads((prior/'TABLE_SHARD_MANIFEST.json').read_text(encoding='utf-8'))
    prior_parts=0
    for dataset in reused['datasets']:
        for item in dataset['parts']:
            assert (prior/item['file']).stat().st_size==item['compressed_bytes']
            prior_parts+=1
    receipt=dict(schema='population256_local_readability_check_v1',source_member_records=len(source),
                 unique_source_paths=len({r['archive_path'] for r in source}),source_sizes_verified=True,
                 saved_tables=tables,endpoint_shards=len(shards),new_endpoint_rows=sum(counts.values()),
                 endpoint_rows_by_stage=dict(counts),geometry_pointer_samples=checked,
                 existing_prior_logical_parts=prior_parts,no_old_data_copies=True,no_extra_hashes=True,
                 no_fusion_scoring_classification=True,scope='Archive-byte sizes, complete saved-interface CSV/gzip reads and six scalar/geometry identity pointers; not a new scientific recomputation or all geometry-body verification.')
    (saved.BASE/'READ_ACCESS_CHECK.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')


if __name__=='__main__':
    main()
