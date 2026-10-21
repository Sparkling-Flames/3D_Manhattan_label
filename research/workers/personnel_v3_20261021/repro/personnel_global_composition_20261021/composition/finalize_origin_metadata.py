"""Correct only endpoint-origin strings using exact source indexes.

54 early benchmark rows predated explicit runtime provenance and inherited a
historical-cache fallback. Numerical values, member keys and geometry are not
altered. CSV values are streamed as strings, avoiding numerical round trips.
"""
from __future__ import annotations
import collections,csv as csv_module
from global_study import *
from run_endpoints import benchmark_keys,classify_endpoint_origin


def main():
    full,partial,_=existing_cache();history=set(gzip.open(OUT/'HISTORICAL_TEAM_KEYS.txt.gz','rt').read().splitlines());benchmarked=benchmark_keys()
    counts=collections.Counter();corrections=[];pools=set();total=0
    target=OUT/'TEAMS_SCALARS.csv.gz';tmp=target.with_name(target.name+'.tmp')
    with gzip.open(target,'rt',encoding='utf-8-sig',newline='') as src,gzip.open(tmp,'wt',encoding='utf-8-sig',newline='',compresslevel=5) as dest:
        reader=csv_module.DictReader(src);writer=csv_module.DictWriter(dest,fieldnames=reader.fieldnames,lineterminator='\n');writer.writeheader()
        for row in reader:
            key=row['team_key'];origin=classify_endpoint_origin(key,full,partial,history,benchmarked)
            if row['endpoint_origin']!=origin:
                corrections.append(dict(team_key=key,pool_id=row['pool_id'],previous_origin=row['endpoint_origin'],correct_origin=origin));pools.add(row['pool_id'])
                row['endpoint_origin']=origin
            counts[origin]+=1;total+=1;writer.writerow(row)
    if total!=291904:raise ValueError(('unexpected final scope',total))
    tmp.replace(target)
    # Keep recovery shards in agreement without re-enriching any geometry.
    for pid in sorted(pools):
        path=OUT/'runtime/scalars'/(pid+'.csv.gz');temp=path.with_name(path.name+'.tmp')
        with gzip.open(path,'rt',encoding='utf-8-sig',newline='') as src,gzip.open(temp,'wt',encoding='utf-8-sig',newline='',compresslevel=5) as dest:
            reader=csv_module.DictReader(src);writer=csv_module.DictWriter(dest,fieldnames=reader.fieldnames,lineterminator='\n');writer.writeheader()
            for row in reader:
                row['endpoint_origin']=classify_endpoint_origin(row['team_key'],full,partial,history,benchmarked);writer.writerow(row)
        temp.replace(path)
    prior=read(OUT/'ENDPOINT_COMPLETION.json');backup=OUT/'runtime/ENDPOINT_COMPLETION_PRE_ORIGIN_REPAIR.json'
    if not backup.exists():save(backup,prior)
    prior['endpoint_origin_counts']=dict(counts);prior['origin_metadata_corrections']=len(corrections);save(OUT/'ENDPOINT_COMPLETION.json',prior)
    csv(OUT/'ORIGIN_METADATA_CORRECTIONS.csv',pd.DataFrame(corrections))
    save(OUT/'ORIGIN_METADATA_RECEIPT.json',dict(corrected_rows=len(corrections),total_rows=total,affected_pools=len(pools),
        endpoint_origin_counts=dict(counts),new_actual_member_sets=counts['new_endpoint_this_round']+counts['new_benchmark_this_round'],
        numerical_fields_changed=0,member_sets_changed=0,native_geometry_changed=0,fusion_calls=0,geometry_diagnostic_calls=0,
        reason='Early benchmark rows lacked explicit provenance. Exact historical/full/scalar/benchmark indexes replace the historical fallback string; two benchmark sets overlap recovered historical requests, the other 52 are new benchmark sets.'))
    print(json.dumps(dict(corrected_rows=len(corrections),total_rows=total,endpoint_origin_counts=dict(counts))),flush=True)


if __name__=='__main__':main()
