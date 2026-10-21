"""Hash completed native shards without any fusion or scalar re-enrichment.

Semantic endpoint hashes cover required sets only, excluding elapsed runtime.
The raw file hash supports transfer integrity but need not reproduce across
machines because native endpoint rows contain timing measurements.
"""
from __future__ import annotations
import collections,importlib.metadata,platform
from global_study import *
from run_endpoints import pool_endpoints


def main():
    requests=read(OUT/'ENDPOINT_REQUESTS.json.gz')['requests']
    pools=pool_lookup();prior,_,_=existing_cache();fe,fr,_,_=setup_engine()
    by=collections.defaultdict(set)
    for r in requests:by[r['pool_id']].add(r['team_key'])
    old={r['pool_id']:r for r in pd.read_csv(OUT/'ENDPOINT_SHARD_INDEX.csv').to_dict('records')}
    fields=['pool_id','reference_id','reference_version','member_workers','member_object_ids',
            'k','nodes','complete_evaluable','geometry','minimum_support','node_supports',
            'ref_matched_nodes_5','ref_matched_nodes_9','ref_matched_edges_5','ref_matched_edges_9',*fr.SCORE_KEYS]
    rows=[]
    for pid,required in sorted(by.items()):
        base={k:r for k,r in prior.items() if r['pool_id']==pid}
        available=pool_endpoints(pid,base)
        if required-available.keys():raise ValueError(('incomplete pool',pid,len(required-available.keys())))
        raw=OUT/'runtime/endpoints'/(pid+'.json.gz')
        row=old[pid]
        row.update(input_pool_sha256=digest(pools[pid]),
            required_endpoint_semantic_sha256=digest([(k,{f:available[k].get(f) for f in fields}) for k in sorted(required)]),
            raw_cache_sha256=hashlib.sha256(raw.read_bytes()).hexdigest(),
            scalar_shard_sha256=hashlib.sha256((OUT/row['scalar_shard']).read_bytes()).hexdigest(),
            available_result_rows=len(required),semantic_hash_excludes_elapsed_timing=True,
            endpoint_status_scope='All computed endpoint results, including native failures; not a complete-evaluable-only count')
        rows.append(row)
    csv(OUT/'ENDPOINT_SHARD_INDEX.csv',pd.DataFrame(rows))
    files=['ENDPOINT_REQUESTS.json.gz','FROZEN_LABELS.csv','CONFIG_MEMBERSHIP.csv.gz','ABC_EVENTS.csv.gz',
           'TEAMS_SCALARS.csv.gz','ENDPOINT_COMPLETION.json','ENDPOINT_SHARD_INDEX.csv',
           'ABC_GEOMETRY.csv.gz','METHOD_EXECUTION_COVERAGE.csv','UNIVERSE_FINAL_COVERAGE.csv.gz']
    input_paths=[FUSION/'INPUT_SNAPSHOT.json.gz',FUSION/'fusion_engine.py',FUSION/'pool_io.py',
        COMP/'fusion_runner.py',COMP/'summarize_grid.py',COMP/'geometry_diagnostics.py',CORNER/'corner_distance.py',
        fe.ENGINE/'measurement_engine.zip',fe.ENGINE/'working_models.py',
        ROOT/'tools/thesis_main/analysis/consensus_delivery_20261008.py',
        ROOT/'tools/thesis_main/analysis/ring_correspondence_20261007.py',
        ROOT/'tools/thesis_main/analysis/wall_consensus_v1_process_20261017.py',
        ROOT/'tools/thesis_main/analysis/quality_b8l2_d10_20261017.py',
        ROOT/'research/workers/personnel_profiles_composition_20261020/source/tables/profiles/record_index.csv.gz']
    input_hashes={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in input_paths}
    save(OUT/'FINAL_ARTIFACT_HASHES.json',dict(
        input_commit='51b519f943b2dd3a4fb2f0198133ac5dd17209ab',
        files={name:hashlib.sha256((OUT/name).read_bytes()).hexdigest() for name in files if (OUT/name).exists()},
        frozen_input_files=input_hashes,
        code_files={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(OUT.glob('*.py'))},
        semantic_endpoint_fields=fields,
        semantic_hash_scope='Sorted required team keys and the listed native fields; excludes durations and new auxiliary enrichment.',
        raw_geometry_shards_in_delivery=False,
        recovery='run_endpoints.py consumes exact ENDPOINT_REQUESTS.json.gz and unchanged repository engine; geometry_events.py then reconstructs all registered comparisons.'))
    import shapely
    save(OUT/'ENVIRONMENT_RECEIPT.json',dict(python=platform.python_version(),numpy=np.__version__,pandas=pd.__version__,
        scipy=importlib.metadata.version('scipy'),shapely=shapely.__version__,
        fusion_gap=fe.WORKING_GAP,BLAS_threads=1,OMP_threads=1,MKL_threads=1,
        runtime_dependency_path='/tmp/hohonet_deps',native_wrapper_science_commit=fe.COMMIT,
        code_resolution_note='PERSONNEL_V2_REPOSITORY points to the latest-main checkout; original wrapper science-commit provenance is retained separately from checkout main.'))
    print(json.dumps(dict(pools=len(rows),required_endpoints=len(requests),fusion_evaluations=0)),flush=True)


if __name__=='__main__':main()
