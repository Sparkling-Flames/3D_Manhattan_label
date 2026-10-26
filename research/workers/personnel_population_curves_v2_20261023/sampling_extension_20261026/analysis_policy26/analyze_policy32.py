"""Historical policy precision: old16, independent new16, pooled32.

Keeps the adopted latest-main phase support, intersecting with all new comparison
batches where needed. Each path bootstrap uses one complete paired natural/policy
base across k. Missing fixed k/image invalidates a draw; it is not renormalized.
The four policy roles are the historical V3 roles, not DSTRUCT/RFUSE.
"""
from __future__ import annotations
import argparse, csv, gzip, hashlib, io, json, os, sys, warnings
from pathlib import Path
for _v in ("OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "OMP_NUM_THREADS"):
    os.environ[_v] = "1"
import numpy as np
import pandas as pd
import adopted_policy_functions_20261025 as F

VERSIONS = ["old16", "new16", "pooled32"]
DEFAULT_SEED = 2026102603
EXTRA = ["endpoint_state", "actual_consensus_failure", "output_generated_unscorable",
         "reference_unavailable", "score_status", "order_status", "geometry_status",
         "policy_deferred", "complete_evaluable", "connection_available", "below_four"]
WANTED = list(dict.fromkeys(F.META + F.FIELDS + EXTRA + ["path_id", "base_path_id", "policy", "k",
    "team_key", "source_time_known_n", "time_source_kinds", "time_source_kinds_json", "new_index", "stage"]))
ADOPTED_METRICS = list(F.METRICS)
STATE_FIELDS = ['actual_consensus_failure', 'output_generated_unscorable', 'reference_unavailable', 'other_unscored']
F.FIELDS += STATE_FIELDS
F.METRICS += [s+'_delta' for s in STATE_FIELDS]
_adopted_statistics = F.statistics

def statistics(n,p):
    return np.concatenate([_adopted_statistics(n,p),np.stack([np.mean(p[s]-n[s],axis=1) for s in STATE_FIELDS],axis=-1)],axis=-1)

F.statistics = statistics

def save(df, path):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    payload=df.to_csv(index=False).encode('utf-8')
    if path.suffix=='.gz':payload=gzip.compress(payload,compresslevel=5,mtime=0)
    atomic_bytes(path,payload)
    op=gzip.open if path.suffix=='.gz' else open
    with op(path,'rt',encoding='utf-8-sig',newline='') as f:
        reader=csv.reader(f);fields=next(reader);count=0
        for row in reader:
            assert len(row)==len(fields),(str(path),count)
            count+=1
    assert count==len(df),(str(path),count,len(df))

def atomic_bytes(path,payload):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_name(path.name+'.writing');fd=os.open(tmp,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o644)
    try:
        data=memoryview(payload);offset=0
        while offset<len(data):
            n=os.write(fd,data[offset:offset+1048576])
            if n<=0:raise IOError('zero write')
            offset+=n
        os.fsync(fd)
    finally:os.close(fd)
    tmp.replace(path)

def base_paths(base):
    population = base / "repo/research/workers/personnel_population_curves_v2_20261023"
    return population, population / "sampling_precision_20261025"

def prepare_old(base):
    population, prior = base_paths(base)
    out = base / "analysis_policy26/inputs_old16"; out.mkdir(parents=True, exist_ok=True)
    meta = pd.read_csv(prior / "local_audit/policy/COMMON_IMAGES.csv")
    assert len(meta) == 157 and meta.building.nunique() == 22
    sources = [("old8", population/"stability_rebuilt_20261023/inputs/PREFIX_VALUES_COMPACT.csv.gz"),
               ("prior_new8", base/"inputs_cache26/precision25/NEW_PREFIX_VALUES_COMPACT.csv.gz")]
    pieces = []
    for batch, source in sources:
        for d in pd.read_csv(source, usecols=lambda c: c in WANTED, chunksize=80000, low_memory=False):
            d = d[d.pool_id.isin(meta.pool_id)].copy()
            if not d.empty:
                d["legacy_batch"] = batch; pieces.append(d)
    all_data = pd.concat(pieces, ignore_index=True)
    scalar_wanted = ["team_key", "time_source_kinds", "time_source_kinds_json", "score_status"] + F.COMPONENTS
    scalars = pd.read_csv(base/"inputs_cache26/ENDPOINT_SCALARS_20261023.csv.gz",
                          usecols=lambda c: c in scalar_wanted, low_memory=False).set_index("team_key")
    assert scalars.index.is_unique
    for col in scalar_wanted:
        if col == "team_key" or col not in scalars: continue
        values = all_data.team_key.map(scalars[col])
        all_data[col] = all_data[col].fillna(values) if col in all_data else values
    counts = []
    for pid, d in all_data.groupby("pool_id", sort=True):
        pieces = []
        for legacy, g in d.groupby("legacy_batch"):
            bases = sorted(set.intersection(*[set(g.loc[g.policy.eq(p), "base_path_id"]) for p in F.POLICIES]))
            assert len(bases) == 8, (pid, legacy, len(bases))
            use = g[g.base_path_id.isin(bases) & g.policy.isin(F.POLICIES+["natural_random"])].copy()
            assert not use.duplicated(["policy", "base_path_id", "k"]).any()
            pieces.append(use)
        use = pd.concat(pieces, ignore_index=True)
        save(use, out/(pid+".csv.gz"))
        counts.append(dict(pool_id=pid, rows=len(use), bases=use.base_path_id.nunique()))
    save(meta, base/"analysis_policy26/COMMON_IMAGES.csv")
    save(pd.DataFrame(counts), base/"analysis_policy26/OLD16_CACHE_COUNTS.csv")
    print(json.dumps(dict(action="prepare_old", pools=len(counts), rows=sum(x['rows'] for x in counts))), flush=True)

def legalize(data):
    data = data.copy()
    if "time_source_kinds" not in data:
        data["time_source_kinds"] = data.get("time_source_kinds_json", "")
    elif "time_source_kinds_json" in data:
        data["time_source_kinds"] = data.time_source_kinds.fillna(data.time_source_kinds_json)
    data["labor_kind"] = data.time_source_kinds.map(F.labor_kind)
    known = (data.source_time_known_n == data.k) & (data.source_time_total_seconds > 0) & data.labor_kind.ne("")
    data.loc[~known, "source_time_total_seconds"] = np.nan
    data["labor_kind_code"] = pd.Categorical(data.labor_kind).codes
    # Map inherited raw statuses into the same explicit distinctions as new native
    # exports. The adopted broader failure_delta is retained under its old name.
    q = np.isfinite(pd.to_numeric(data.B8L2,errors='raise'))
    status = data.score_status.fillna('')
    active = data.k.ne(2) & ~q
    data['actual_consensus_failure'] = active & status.isin(['fusion_exception','below_four','no_connection'])
    data['output_generated_unscorable'] = active & status.isin(['measurement_exception','invalid_floor','invalid_full_geometry'])
    data['reference_unavailable'] = active & status.isin(['floor_only_reference','missing_reference'])
    data['other_unscored'] = active & ~(data.actual_consensus_failure | data.output_generated_unscorable | data.reference_unavailable)
    for c in F.FIELDS:
        data[c] = pd.to_numeric(data[c], errors="raise")
    return data

def input_for_pool(base, pid):
    newfile = base/"new_endpoints26/stage1/prefix_values"/(pid+".csv.gz")
    if not newfile.exists(): return None
    old = pd.read_csv(base/"analysis_policy26/inputs_old16"/(pid+".csv.gz"), low_memory=False)
    old["analysis_source"] = "old16"
    new = pd.read_csv(newfile, usecols=lambda c: c in WANTED, low_memory=False)
    new = new[(new.new_index >= 0) & (new.new_index < 16) & new.policy.isin(F.POLICIES+["natural_random"])].copy()
    new["analysis_source"] = "new16"; new["legacy_batch"] = "new16"
    data = legalize(pd.concat([old, new], ignore_index=True))
    for src, d in data.groupby("analysis_source"):
        bases = set.intersection(*[set(d.loc[d.policy.eq(p), "base_path_id"]) for p in F.POLICIES])
        assert len(bases) == 16, (pid, src, len(bases))
    return data

def resamples(bases, mapping, rng, replicates):
    # Stratified complete-path resampling. Retain old8/new8/new16 allocations.
    result = []
    for group in sorted(set(mapping[b] for b in bases)):
        idx = np.array([i for i, b in enumerate(bases) if mapping[b] == group])
        result.append(idx[rng.integers(len(idx), size=(replicates, len(idx)))])
    return np.concatenate(result, axis=1)

def analyze_pool(base, row, legacy_support, replicates, seed):
    pid = row.pool_id
    out = base/"analysis_policy26/parts"/pid
    if (out/"RECEIPT.json").exists():
        with np.load(out/'PATH_BOOTSTRAP_CACHE.npz') as existing:
            if all(existing[pol+'__'+ver+'__point'].shape==(len(F.PHASES),len(F.METRICS)) for pol in F.POLICIES for ver in VERSIONS):return True
    data = input_for_pool(base, pid)
    if data is None: return False
    out.mkdir(parents=True, exist_ok=True)
    ks = np.arange(1, int(row.pool_n)+1); masks = F.phase_masks(ks, int(row.pool_n))
    image_rows = []; k_rows=[]; support_rows=[]; event_rows=[]; statuses=[]
    arrays = {}; stable_pool = int(hashlib.sha256(pid.encode()).hexdigest()[:8],16)
    for pi, policy in enumerate(F.POLICIES):
        matrices = {}; values={}; boot_values={}; base_lists={}; groups={}
        for vi, version in enumerate(VERSIONS):
            use = data if version == "pooled32" else data[data.analysis_source.eq(version)]
            bases = sorted(set.intersection(*[set(use.loc[use.policy.eq(p), "base_path_id"]) for p in F.POLICIES]))
            assert len(bases) == (32 if version == "pooled32" else 16)
            n=F.matrices(use[use.policy.eq("natural_random")],bases,ks)
            p=F.matrices(use[use.policy.eq(policy)],bases,ks)
            matrices[version]=(n,p);base_lists[version]=bases
            values[version]=F.statistics({c:a[None] for c,a in n.items()},{c:a[None] for c,a in p.items()})[0]
            groupmap=use.drop_duplicates("base_path_id").set_index("base_path_id").legacy_batch.to_dict()
            rng=np.random.default_rng(np.random.SeedSequence([seed,stable_pool,vi]))
            draw=resamples(bases,groupmap,rng,replicates)
            boot_values[version]=np.concatenate([
                F.statistics({c:a[ix] for c,a in n.items()},{c:a[ix] for c,a in p.items()})
                for ix in np.array_split(draw, max(1, int(np.ceil(replicates/200))))],axis=0)
            valid=np.isfinite(n['B8L2']) & np.isfinite(p['B8L2'])
            qt=valid & (n['source_time_total_seconds']>0) & (p['source_time_total_seconds']>0) & (n['labor_kind_code']==p['labor_kind_code'])
            for j,k in enumerate(ks):
                qdraw=boot_values[version][:,j,0]
                lo,hi=F.interval(qdraw)
                finite_qdraw=qdraw[np.isfinite(qdraw)]
                k_rows.append(dict(**row.to_dict(),version=version,policy=policy,k=int(k),base_paths=len(bases),both_Q_paths=int(valid[:,j].sum()),
                    legal_QT_paths=int(qt[:,j].sum()),Q_path_lo=lo,Q_path_hi=hi,Q_path_se=(np.std(finite_qdraw,ddof=1) if len(finite_qdraw)>1 else np.nan),
                    Q_path_valid_replicates=int(np.isfinite(qdraw).sum()),**dict(zip(F.METRICS,values[version][j]))))
            if version != 'pooled32':
                ef=[c for c in ['pool_id','base_path_id','k','team_key','B8L2','D10','source_time_total_seconds','labor_kind']+EXTRA if c in use]
                natural=use[use.policy.eq('natural_random') & use.base_path_id.isin(bases)][ef]
                target=use[use.policy.eq(policy) & use.base_path_id.isin(bases)][ef]
                events=natural.merge(target,on=['pool_id','base_path_id','k'],suffixes=('_natural','_policy'),validate='one_to_one')
                events.insert(0,'version',version);events.insert(1,'policy',policy);event_rows.append(events)
        common=F.common_k_mask(np.stack([values[v] for v in VERSIONS]))
        for version in VERSIONS:
            point=np.full((len(F.PHASES),len(F.METRICS)),np.nan)
            boot=np.full((replicates,len(F.PHASES),len(F.METRICS)),np.nan,dtype=np.float32)
            for ph,phase in enumerate(F.PHASES):
                for mi,metric in enumerate(F.METRICS):
                    if metric in ADOPTED_METRICS:
                        source=legacy_support.loc[(pid,policy,phase,metric)]
                        legacy_k=set(int(x) for x in str(source.fixed_k_list).split('|') if x and x!='nan')
                        legacy=np.array([int(k) in legacy_k for k in ks])
                    else:
                        legacy=masks[ph] & (ks!=2)
                    keep=legacy & common[:,mi] & masks[ph]
                    point[ph,mi]=F.fixed_mean(values[version][:,mi],keep,0)
                    boot[:,ph,mi]=F.fixed_mean(boot_values[version][:,:,mi],keep,1)
                    support_rows.append(dict(pool_id=pid,image=row.image,policy=policy,version=version,phase=phase,metric=metric,
                        candidate_k=int(masks[ph].sum()),adopted_old16_k=int(legacy.sum()),matched_k=int(keep.sum()),
                        lost_k=int((legacy & ~keep).sum()),matched_k_list='|'.join(map(str,ks[keep])),point=point[ph,mi],
                        valid_bootstraps=int(np.isfinite(boot[:,ph,mi]).sum()),invalid_bootstraps=int((~np.isfinite(boot[:,ph,mi])).sum())))
                image_rows.append(dict(**row.to_dict(),version=version,policy=policy,phase=phase,base_paths=len(base_lists[version]),
                    **dict(zip(F.METRICS,point[ph]))))
            arrays[policy+'__'+version+'__point']=point
            arrays[policy+'__'+version+'__boot']=boot
    save(pd.DataFrame(k_rows),out/'POLICY_IMAGE_K.csv.gz')
    save(pd.DataFrame(image_rows),out/'POLICY_IMAGE_PHASE.csv')
    save(pd.DataFrame(support_rows),out/'FIXED_SUPPORT.csv.gz')
    save(pd.concat(event_rows,ignore_index=True),out/'EXACT_PAIRED_EVENTS.csv.gz')
    # NPZ is only a bounded analysis cache; final output uses tables and reproducible seed.
    buf=io.BytesIO();np.savez_compressed(buf,**arrays);atomic_bytes(out/'PATH_BOOTSTRAP_CACHE.npz',buf.getvalue())
    with np.load(out/'PATH_BOOTSTRAP_CACHE.npz') as check:
        for key in arrays:assert np.array_equal(check[key],arrays[key],equal_nan=True)
    receipt=dict(pool_id=pid,policies=F.POLICIES,versions=VERSIONS,bootstrap_replicates=replicates,seed=seed,
       k_rows=len(k_rows),phase_rows=len(image_rows),paired_events=sum(len(x) for x in event_rows),
       support='latest-main legacy old8/new8 common-k support intersected with old16/new16/pooled32 finite k',
       complete=True)
    (out/'RECEIPT.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
    return True

def aggregate(base,meta,replicates,seed):
    out=base/'analysis_policy26/results';out.mkdir(parents=True,exist_ok=True)
    allrows=[]
    for pi,policy in enumerate(F.POLICIES):
        for vi,version in enumerate(VERSIONS):
            points=[];boots=[]
            for row in meta.itertuples():
                with np.load(base/'analysis_policy26/parts'/row.pool_id/'PATH_BOOTSTRAP_CACHE.npz') as arr:
                    points.append(arr[policy+'__'+version+'__point']);boots.append(arr[policy+'__'+version+'__boot'])
            points=np.stack(points);boots=np.stack(boots)
            rows=F.aggregate(points,boots,meta,version,policy,np.random.default_rng(np.random.SeedSequence([seed,999,pi,vi])),replicates)
            for r in rows:r['version']=r.pop('batch')
            allrows.extend(rows)
    summary=pd.DataFrame(allrows);save(summary,out/'POLICY_PRECISION_SUMMARY.csv')
    for name in ['POLICY_IMAGE_K.csv.gz','POLICY_IMAGE_PHASE.csv','FIXED_SUPPORT.csv.gz','EXACT_PAIRED_EVENTS.csv.gz']:
        # 157 bounded parts; event table under 1M rows.
        frames=[pd.read_csv(base/'analysis_policy26/parts'/pid/name,low_memory=False) for pid in meta.pool_id]
        save(pd.concat(frames,ignore_index=True),out/name)
    early=summary[(summary.phase=='early_3_to_half')&(summary.difficulty=='全部')&(summary.weighting=='image_equal')]
    save(early,out/'KEY_EARLY_RESULTS.csv')
    print(early[early.metric.isin(['paired_Q_delta','failure_delta','labor_ratio_legal','QT_paired_Q_delta'])].to_string(index=False),flush=True)
    (out/'RECEIPT.json').write_text(json.dumps(dict(completed=True,images=len(meta),buildings=int(meta.building.nunique()),
        replicates=replicates,seed=seed,versions=VERSIONS,new_fusion_called_by_analysis=False,policy_labels='historical V3_BEHAVIOR/V3_JOINT_QT; not DSTRUCT/RFUSE',
        support='fixed latest-main adopted k intersected across compared batches; fixed eligible images per metric; inestimable path draw remains missing',
        weighting=['image_equal','building_equal'],building_resampling='whole buildings of fixed per-image point estimates, separate from path Monte Carlo'),ensure_ascii=False,indent=2)+'\n')

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--base',type=Path,required=True);ap.add_argument('--prepare-old',action='store_true')
    ap.add_argument('--replicates',type=int,default=2000);ap.add_argument('--seed',type=int,default=DEFAULT_SEED)
    ap.add_argument('--only-pool');ap.add_argument('--aggregate',action='store_true');args=ap.parse_args();base=args.base.resolve()
    if args.prepare_old:prepare_old(base);return
    _,prior=base_paths(base);meta=pd.read_csv(base/'analysis_policy26/COMMON_IMAGES.csv')
    support=pd.read_csv(prior/'local_audit/policy/FIXED_K_SUPPORT.csv.gz',keep_default_na=False)
    support=support[support.batch.eq('combined16')].set_index(['pool_id','policy','phase','metric']);assert support.index.is_unique
    done=0
    for i,row in meta.iterrows():
        if args.only_pool and row.pool_id!=args.only_pool:continue
        if analyze_pool(base,row,support,args.replicates,args.seed):
            done+=1;print(json.dumps(dict(policy_pool_complete=row.pool_id,done=done)),flush=True)
    if args.aggregate:
        assert all((base/'analysis_policy26/parts'/pid/'RECEIPT.json').exists() for pid in meta.pool_id)
        aggregate(base,meta,args.replicates,args.seed)

if __name__=='__main__':main()
