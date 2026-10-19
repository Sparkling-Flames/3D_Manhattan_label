"""Independent implementation and historical-function audit; no source edits."""
from __future__ import annotations
import gzip,hashlib,itertools,json,sys,zipfile
import multiprocessing
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
import numpy as np
import pandas as pd
HERE=Path(__file__).resolve().parent;BASE=HERE.parents[1];REPO=BASE/'repo_main_20261019'
sys.path.insert(0,str(REPO));sys.path.insert(0,str(BASE/'work_20261018/runtime_deps'))
from cluster_core import affinity_partition,objective,bound_cyclic_distance
from tools.thesis_main.analysis.paired_split_research.study import angular,cyclic
from tools.thesis_main.analysis.build_cluster_review_20261018 import affinity_partition as main_affinity
from tools.thesis_main.analysis.audit_cluster_validation_return_20260922 import brute_affinity

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def source_partition(d,cut):
    # HiGHS has a process-wide scheduler.  Source default-thread and our fixed-
    # one-thread calls must use separate processes, not alternate schedulers.
    return main_affinity(d,cut)

def main():
    with gzip.open(HERE.parent/'fusion/INPUT_SNAPSHOT.json.gz','rt') as f:pools=json.load(f)['images']
    candidates=[]
    for p in pools:
        by={}
        for r in p['records']:by.setdefault(len(r['points']),[]).append(r)
        for count,rr in by.items():
            if len(rr)>=3:candidates.append((p['pool_id'],count,sorted(rr,key=lambda r:r['object_id'])[:8]))
    # Input-hash order; outcome values do not choose the audit sample.
    candidates.sort(key=lambda x:hashlib.sha256(json.dumps([x[0],x[1]]).encode()).hexdigest())
    checks=[];geometry=[]
    source_executor=ProcessPoolExecutor(max_workers=1,mp_context=multiprocessing.get_context('spawn'))
    for pid,count,rr in candidates[:24]:
        n=len(rr);d=np.zeros((n,n))
        for i,j in itertools.combinations(range(n),2):
            p,q=np.asarray(rr[i]['points']),np.asarray(rr[j]['points'])
            main_d=cyclic(np.maximum(angular(p[::2],q[::2]),angular(p[1::2],q[1::2])))[0]
            own=bound_cyclic_distance(p,q)['distance_deg'];assert own==main_d
            d[i,j]=d[j,i]=own
            rolled=np.roll(q.reshape(-1,2,2),1,axis=0).reshape(-1,2)
            shift_d=bound_cyclic_distance(p,rolled)['distance_deg'];assert abs(shift_d-own)<1e-10
            geometry.append(dict(pool_id=pid,object_id_a=rr[i]['object_id'],object_id_b=rr[j]['object_id'],distance=own,
                exact_source_function_error=own-main_d,cyclic_invariance_error=shift_d-own))
        for cut in [9.,12.]:
            group,status=affinity_partition(d,cut); source,info=source_executor.submit(source_partition,d,cut).result()
            brute,leaves=brute_affinity(d,cut)
            ours=objective(d,group,cut);main_score=objective(d,source,cut)
            assert all(s['optimal'] for s in status) and info['optimal']
            assert abs(ours-brute)<1e-7 and abs(main_score-brute)<1e-7
            checks.append(dict(pool_id=pid,N=n,pair_count=count//2,threshold_deg=cut,
                our_objective=ours,main_objective=main_score,brute_objective=brute,
                enumerated_feasible_partitions=leaves,our_error=ours-brute,main_error=main_score-brute))
    source_executor.shutdown()
    pd.DataFrame(checks).to_csv(HERE/'algorithm_objective_audit.csv',index=False)
    pd.DataFrame(geometry).to_csv(HERE/'distance_function_audit.csv',index=False)
    archive=REPO/'analysis_results/cluster_validation_received_20260922/Pro原始返回.zip'
    with zipfile.ZipFile(archive) as z:
        historic={k:hashlib.sha256(z.read(k)).hexdigest() for k in ['code/core.py','code/02_partition.py','code/01_measurement.py']}
    receipt=dict(main_commit='82c6164b0d4630de5316199c92aa405930973168',sampled_input_subpools=24,
        objective_comparisons=len(checks),all_feasible_partition_counts=sum(c['enumerated_feasible_partitions'] for c in checks),
        max_ours_vs_brute=max(abs(c['our_error']) for c in checks),max_main_vs_brute=max(abs(c['main_error']) for c in checks),
        exact_distance_comparisons=len(geometry),max_cyclic_invariance_error=max(abs(c['cyclic_invariance_error']) for c in geometry),
        historical_archive_sha256=sha(archive),historical_functions_sha256=historic,
        functions_sha256={str(p.relative_to(REPO)):sha(p) for p in [
            REPO/'tools/thesis_main/analysis/paired_split_research/study.py',
            REPO/'tools/thesis_main/analysis/worker_annotation_similarity_20261018.py',
            REPO/'tools/thesis_main/analysis/build_cluster_review_20261018.py',
            REPO/'tools/thesis_main/analysis/research_round_20260929.py']},
        historical_difference='September 25.6 is max wrapped ERP Euclidean pixel distance in declared pair order (cyclic only a separate sensitivity), rounded to 8 decimals; current primary uses bound common cyclic spherical endpoint degrees. Same quadratic affinity/transitivity objective does not transfer historical semantic/validation results.',
        audit_execution='Main source default-thread solver and fixed-one-thread study solver run in separate processes. An initial mixed-thread same-process audit encountered HiGHS scheduler Status 0 Not Set; no study pool was affected and no clustering objective changed.',
        uniqueness_limit='Alternative optimum probes use 1e-7 objective tolerance and only nonclique components N<=12; larger components unprobed, deterministic solver output is not proof of unique partition.')
    (HERE/'ALGORITHM_AUDIT.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(receipt,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
