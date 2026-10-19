"""Recompute v2 local annotation clusters from audited frozen geometry.

python work_v2_20261019/clusters/build_clusters.py --repo repo_main_20261019
Outputs and resumable per-pool checkpoints stay in this script's directory.
"""
from __future__ import annotations
import argparse, collections, gzip, hashlib, itertools, json, math, os, platform, sys, time
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed
import numpy as np
import pandas as pd

HERE=Path(__file__).resolve().parent
BASE=HERE.parents[1]
DEFAULT_REPO=BASE/'repo_main_20261019'
sys.path.insert(0,str(DEFAULT_REPO))
sys.path.insert(0,str(BASE/'work_20261018/runtime_deps'))
from cluster_core import bound_cyclic_distance, affinity_partition, complete_link, objective, DISTANCE_VERSION

def clean(x):
    if isinstance(x,dict): return {str(k):clean(v) for k,v in x.items()}
    if isinstance(x,(list,tuple,np.ndarray)): return [clean(v) for v in x]
    if isinstance(x,(np.integer,)): return int(x)
    if isinstance(x,(np.bool_,)): return bool(x)
    if isinstance(x,(float,np.floating)): return float(x) if np.isfinite(x) else None
    return x

def write_json(path,data):
    path=Path(path); path.parent.mkdir(parents=True,exist_ok=True)
    text=json.dumps(clean(data),ensure_ascii=False,allow_nan=False,separators=(',',':'))
    if path.suffix=='.gz':
        with gzip.open(path,'wt',encoding='utf-8') as f:f.write(text)
    else:path.write_text(text+'\n',encoding='utf-8')

def read_json(path):
    with (gzip.open(path,'rt',encoding='utf-8') if str(path).endswith('.gz') else open(path,encoding='utf-8')) as f:return json.load(f)

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def membership_map(groups,n):
    out={}
    for g in groups:
        members=frozenset(g)
        for i in g:out[i]=members
    assert len(out)==n
    return out

def process_pool(arg):
    pool,out,source_sha=arg
    from tools.thesis_main.analysis.research_round_20260929 import reconstruct
    from shapely.geometry import Polygon
    meta=pool['meta']; pid=pool['pool_id']; out=Path(out)
    checkpoint=out/'checkpoints'/(pid+'.json.gz')
    if checkpoint.exists():
        old=read_json(checkpoint)
        if old.get('input_sha256')==source_sha:return pid,'cached',old
        raise ValueError('Changed input under existing checkpoint '+pid)
    rr=sorted(pool['records'],key=lambda x:(x['worker_id'],x['object_id']))
    n=len(rr); common=dict(pool_id=pid,image_id=meta['image_id'],image_code=meta['image'],
                          building_id=meta['building'],condition=meta['condition'],layer=meta['layer'],
                          difficulty=meta['difficulty'],reference_id=meta['reference_id'],reference_version=meta['reference_version'],N=n)
    points=[np.asarray(r['points'],float) for r in rr]
    geom=[reconstruct(r,coordinate_convention='continuous') for r in rr]
    polys=[]
    for g in geom:
        p=Polygon(g['floor']) if g['floor'] is not None else None
        polys.append(p if p is not None and p.is_valid and p.area>0 else None)
    matrix=np.full((n,n),np.nan); np.fill_diagonal(matrix,0.)
    pairrows=[]; recordrows=[]
    for i,r in enumerate(rr):
        g=geom[i]; h=g['heights']
        recordrows.append(dict(**common,object_id=r['object_id'],worker_id=r['worker_id'],origin=r['origin'],
            B8L2=r['B8L2'],D10=r['D10'],source_time_seconds=r['source_time_seconds'],
            target_time_seconds=r['target_time_seconds'],time_source_kind=r['time_source_kind'],
            pair_count=len(points[i])//2,ring_confirmed=r['ring_confirmed'],order_status=r['order_status'],
            geometry_status=g['status'],geometry_reason=g['reason'],
            floor_available=polys[i] is not None,mean_height=None if h is None else float(np.mean(h)),
            minimum_bottom_depression_deg=float(np.min(points[i][1::2,1]/512*180-90)),
            frozen_points_sha256=hashlib.sha256(np.asarray(points[i],dtype='<f8').tobytes()).hexdigest()))
    for i,j in itertools.combinations(range(n),2):
        d=bound_cyclic_distance(points[i],points[j])
        # Every pair is also checked in the opposite direction; declared ring is unchanged.
        rev=bound_cyclic_distance(points[j],points[i],diagnostics=False)
        assert d['available']==rev['available']
        if d['available']:
            assert abs(d['distance_deg']-rev['distance_deg'])<1e-10
            matrix[i,j]=matrix[j,i]=d['distance_deg']
        poly_a,poly_b=polys[i],polys[j]; floor_iou=None; prism_iou=None; hlog=None; maxr=None
        if poly_a is not None and poly_b is not None:
            inter=poly_a.intersection(poly_b).area; union=poly_a.area+poly_b.area-inter
            floor_iou=float(inter/union)
            ha,hb=geom[i]['heights'],geom[j]['heights']
            if ha is not None and hb is not None and min(np.mean(ha),np.mean(hb))>0:
                hm_a,hm_b=float(np.mean(ha)),float(np.mean(hb)); shared=inter*min(hm_a,hm_b)
                prism_iou=shared/(poly_a.area*hm_a+poly_b.area*hm_b-shared)
                hlog=abs(math.log(hm_a/hm_b))
        if d['available'] and geom[i]['floor'] is not None and geom[j]['floor'] is not None:
            fa,fb=geom[i]['floor'],geom[j]['floor']; jx=(np.arange(len(fa))+d['shift_a_to_b'])%len(fa)
            rad_a=np.linalg.norm(fa,axis=1);rad_b=np.linalg.norm(fb[jx],axis=1)
            if (rad_a>0).all() and (rad_b>0).all():maxr=float(np.max(abs(np.log(rad_a/rad_b))))
        pairrows.append(dict(**common,object_id_a=rr[i]['object_id'],object_id_b=rr[j]['object_id'],
            worker_id_a=rr[i]['worker_id'],worker_id_b=rr[j]['worker_id'],index_a=i,index_b=j,
            **d,floor_iou=floor_iou,prism_3d_iou=prism_iou,mean_height_abs_log_ratio=hlog,
            max_matched_radius_abs_log_ratio=maxr,
            raw_Q_abs_difference=abs(rr[i]['B8L2']-rr[j]['B8L2']),
            ring_confirmed_a=rr[i]['ring_confirmed'],ring_confirmed_b=rr[j]['ring_confirmed']))
    counts=[len(p)//2 for p in points]
    assignments=[]; summaries=[]; group_rows=[]; solver_rows=[]; payloads=[]
    for cut in [9.,12.]:
        groups=[]; complete=[]; statuses=[]; complete_order_stable=True; altern_affected=set()
        for count in sorted(set(counts)):
            ids=[i for i,c in enumerate(counts) if c==count];sub=matrix[np.ix_(ids,ids)]
            assert np.isfinite(sub).all()
            gg,ss=affinity_partition(sub,cut,60.,alternate_check=True)
            cc=complete_link(sub,cut); cr=complete_link(sub[::-1,::-1],cut)
            mapped_cr=[[len(ids)-1-k for k in g] for g in cr]
            complete_order_stable &= {frozenset(g) for g in cc}=={frozenset(g) for g in mapped_cr}
            groups.extend([[ids[k] for k in g] for g in gg]);complete.extend([[ids[k] for k in g] for g in cc])
            for s in ss:
                component=s.pop('local_indices'); affected=s.get('alternative_affected_members')
                if affected is not None:altern_affected.update(ids[component[k]] for k in affected)
                z=dict(**common,threshold_deg=cut,pair_count=count,member_object_ids='|'.join(rr[ids[k]]['object_id'] for k in component),**s)
                z['alternative_affected_members']=None if affected is None else '|'.join(rr[ids[component[k]]]['object_id'] for k in affected)
                statuses.append(z);solver_rows.append(z)
        groups.sort(key=lambda g:tuple(rr[i]['object_id'] for i in g));complete.sort(key=lambda g:tuple(rr[i]['object_id'] for i in g))
        opt=all(s['optimal'] for s in statuses)
        val=objective(matrix,groups,cut); val_c=objective(matrix,complete,cut)
        if opt:assert val>=val_c-1e-7
        a_map,c_map=membership_map(groups,n),membership_map(complete,n)
        for method,gg in [('affinity',groups),('complete',complete)]:
            for gid,g in enumerate(gg,1):
                cluster_id=f'{pid}|{method}|{int(cut)}|C{gid:02d}'
                sub=matrix[np.ix_(g,g)];medoid=g[int(np.argmin(sub.sum(axis=1)))]
                row=dict(**common,method=method,threshold_deg=cut,cluster_id=cluster_id,local_cluster_id=gid,
                    size=len(g),pair_count=counts[g[0]],diameter_deg=float(np.max(sub)),
                    workers='|'.join(rr[i]['worker_id'] for i in g),object_ids='|'.join(rr[i]['object_id'] for i in g),
                    medoid_object_id=rr[medoid]['object_id'],mean_B8L2=float(np.mean([rr[i]['B8L2'] for i in g])),
                    min_B8L2=float(np.min([rr[i]['B8L2'] for i in g])),max_B8L2=float(np.max([rr[i]['B8L2'] for i in g])),
                    source_time_n=sum(rr[i]['source_time_seconds'] is not None for i in g),
                    source_time_mean=float(np.mean([rr[i]['source_time_seconds'] for i in g if rr[i]['source_time_seconds'] is not None])) if any(rr[i]['source_time_seconds'] is not None for i in g) else None,
                    frozen_reference_same_for_all=True,solver_optimal=opt if method=='affinity' else None)
                group_rows.append(row)
                for i in g:
                    close_neighbors=[j for j in range(n) if j!=i and counts[j]==counts[i] and matrix[i,j]<=cut]
                    assignments.append(dict(**common,object_id=rr[i]['object_id'],worker_id=rr[i]['worker_id'],
                        origin=rr[i]['origin'],pair_count=counts[i],B8L2=rr[i]['B8L2'],D10=rr[i]['D10'],
                        method=method,threshold_deg=cut,cluster_id=cluster_id,local_cluster_id=gid,
                        cluster_size=len(g),cluster_diameter_deg=float(np.max(sub)),
                        singleton=len(g)==1,close_neighbors=len(close_neighbors),
                        forced_singleton=len(close_neighbors)==0,method_membership_same=a_map[i]==c_map[i],
                        alternative_optimum_affected=i in altern_affected,
                        complete_reverse_input_partition_same=complete_order_stable,
                        solver_optimal=opt if method=='affinity' else None))
            summaries.append(dict(**common,method=method,threshold_deg=cut,cluster_count=len(gg),
                singletons=sum(len(g)==1 for g in gg),singleton_mass=sum(len(g)==1 for g in gg)/n,
                largest_cluster=max(map(len,gg)),largest_share=max(map(len,gg))/n,
                sizes='|'.join(map(str,sorted(map(len,gg),reverse=True))),
                objective=objective(matrix,gg,cut),all_optimal=opt if method=='affinity' else None,
                complete_reverse_input_partition_same=complete_order_stable,
                method_affected_members=sum(a_map[i]!=c_map[i] for i in range(n))))
        payloads.append(dict(threshold_deg=cut,affinity=[[rr[i]['object_id'] for i in g] for g in groups],
                             complete=[[rr[i]['object_id'] for i in g] for g in complete],solver_optimal=opt))
        lab={i:k for k,g in enumerate(groups) for i in g}
        labc={i:k for k,g in enumerate(complete) for i in g}
        for r in pairrows:
            i,j=r['index_a'],r['index_b'];r[f'same_affinity_{int(cut)}']=lab[i]==lab[j];r[f'same_complete_{int(cut)}']=labc[i]==labc[j]
    payload=dict(input_sha256=source_sha,meta=common,records=recordrows,pairs=pairrows,assignments=assignments,
                 summaries=summaries,groups=group_rows,solvers=solver_rows,partitions=payloads,
                 geometries=[dict(object_id=r['object_id'],worker_id=r['worker_id'],points=r['points'],
                    floor=geom[i]['floor'],heights=geom[i]['heights'],geometry_status=geom[i]['status'],geometry_reason=geom[i]['reason']) for i,r in enumerate(rr)])
    write_json(checkpoint,payload)
    return pid,'computed',payload

def main():
    ap=argparse.ArgumentParser(__doc__);ap.add_argument('--repo',type=Path,default=DEFAULT_REPO)
    ap.add_argument('--snapshot',type=Path,default=HERE.parent/'fusion/INPUT_SNAPSHOT.json.gz')
    ap.add_argument('--out',type=Path,default=HERE);ap.add_argument('--jobs',type=int,default=3)
    args=ap.parse_args();args.out.mkdir(parents=True,exist_ok=True)
    sys.path.insert(0,str(args.repo.resolve()))
    input_sha=sha(args.snapshot); doc=read_json(args.snapshot); pools=doc['images']
    evidence_path=args.repo/'research/statistics/v2_evidence_audit_20261019/records.json.gz'
    evidence=read_json(evidence_path)['records'];emap={r['object_id']:r for r in evidence}
    seen=set()
    for p in pools:
        ids=set()
        for r in p['records']:
            e=emap[r['object_id']]; assert e['quality_usable'] and e['independent_vote_eligible']
            assert r['worker_id']==e['worker_id'] and p['meta']['image_id']==e['image_id']
            assert p['meta']['reference_id']==e['reference_id'] and p['meta']['reference_version']==e['reference_version']
            np.testing.assert_array_equal(np.asarray(r['points']),np.asarray(e['points_1024x512']))
            assert r['object_id'] not in seen and r['worker_id'] not in ids
            seen.add(r['object_id']);ids.add(r['worker_id'])
    assert seen=={r['object_id'] for r in evidence if r['quality_usable']}
    del evidence,emap
    write_json(args.out/'INPUT_CHECKS.json',dict(main_commit=doc['git_commit'],snapshot_sha256=input_sha,
        evidence_sha256=sha(evidence_path),records_exactly_equal=len(seen),pool_count=len(pools),
        source_qualification_preserved=True,declared_geometry_unchanged=True,design_sha256=sha(HERE/'DESIGN.json')))
    allout=[]; started=time.monotonic()
    with ProcessPoolExecutor(max_workers=args.jobs) as ex:
        futures=[ex.submit(process_pool,(p,str(args.out),input_sha)) for p in pools]
        for i,f in enumerate(as_completed(futures),1):
            pid,status,result=f.result();allout.append(result)
            if i%5==0 or i==len(futures): print(json.dumps(dict(done=i,total=len(futures),pool_id=pid,state=status,seconds=round(time.monotonic()-started,1))),flush=True)
    allout.sort(key=lambda p:p['meta']['pool_id'])
    for key,name in [('records','records_geometry'),('pairs','pair_distances'),('assignments','assignments'),
                     ('summaries','pool_summary'),('groups','cluster_summary'),('solvers','solver_status')]:
        rows=[r for p in allout for r in p[key]]
        path=args.out/(name+('.csv.gz' if key=='pairs' else '.csv'))
        pd.DataFrame(rows).to_csv(path,index=False)
    write_json(args.out/'CLUSTER_API.json.gz',dict(schema='v2_local_clusters_9_12_20261019_r1',input_sha256=input_sha,
               distance_version=DISTANCE_VERSION,pools=[dict(meta=p['meta'],partitions=p['partitions'],geometries=p['geometries']) for p in allout]))
    solvers=[s for p in allout for s in p['solvers']]
    summary=dict(pools=len(allout),records=sum(len(p['records']) for p in allout),pairs=sum(len(p['pairs']) for p in allout),
        buildings=len({p['meta']['building_id'] for p in allout}),ordinary_pools=sum(p['meta']['layer']=='ordinary_manual' for p in allout),
        ordinary_records=sum(len(p['records']) for p in allout if p['meta']['layer']=='ordinary_manual'),
        milp_components=sum(s['method']=='binary_pair_transitivity_milp' for s in solvers),
        nonoptimal_components=sum(not s['optimal'] for s in solvers),
        fallback_components=sum(s['no_incumbent_complete_fallback'] for s in solvers),
        elapsed_seconds=time.monotonic()-started,python=platform.python_version(),numpy=np.__version__,
        code_sha256={p.name:sha(p) for p in HERE.glob('*.py')},input_sha256=input_sha,main_commit=doc['git_commit'])
    write_json(args.out/'RUN_RECEIPT.json',summary);print(json.dumps(summary,ensure_ascii=False,indent=2),flush=True)

if __name__=='__main__':main()
