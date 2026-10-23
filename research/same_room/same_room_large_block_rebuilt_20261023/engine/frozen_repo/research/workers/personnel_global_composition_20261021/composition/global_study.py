"""Whole-composition study, exact finite-population ledgers and native endpoints.

This module never changes records, eligibility, matching, voting, references or
scores. Endpoint keys are the repository's sorted-member-set keys. Class-vector
coverage and concrete-member coverage are recorded separately.
"""
from __future__ import annotations
import argparse,collections,gzip,hashlib,itertools,json,math,os,sys,time
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor,as_completed
for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):
    os.environ[key]='1'
sys.path.insert(0,'/tmp/hohonet_deps')
import numpy as np
import pandas as pd

OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[3]
FUSION=ROOT/'research/workers/pro_personnel_v2_archive_20261019/work_v2_20261019/fusion'
COMP=ROOT/'research/workers/personnel_interchangeability_20261020/analysis/composition'
CORNER=ROOT/'research/workers/personnel_interchangeability_followup_20261020/audit_corner'
TAX=ROOT/'research/workers/personnel_taxonomy_20261021'
SEED=2026102129
CACHE_PATHS=[
 TAX/'fusion/TEAMS.json.gz',TAX/'fusion/NESTED_TEAMS.json.gz',
 TAX/'fusion/a2_specific/TEAMS.json.gz',TAX/'fusion/semi_position/TEAMS.json.gz',
 CORNER/'prior_teams.json.gz',
 ROOT/'research/workers/personnel_profiles_composition_20261020/source/claims/claim_teams.json.gz']

def read(path):
    path=Path(path)
    with (gzip.open(path,'rt',encoding='utf8') if path.suffix=='.gz' else path.open(encoding='utf8')) as f:return json.load(f)

def clean(v):
    if isinstance(v,dict):return {str(k):clean(x) for k,x in v.items()}
    if isinstance(v,(list,tuple,np.ndarray)):return [clean(x) for x in v]
    if isinstance(v,np.generic):return clean(v.item())
    if isinstance(v,float) and not np.isfinite(v):return None
    return v

def save(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    b=json.dumps(clean(value),ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
    tmp=path.with_name(path.name+'.tmp');tmp.write_bytes(gzip.compress(b,compresslevel=5,mtime=0) if path.suffix=='.gz' else b);tmp.replace(path)

def csv(path,frame):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    frame.to_csv(path,index=False,encoding='utf-8-sig',compression={'method':'gzip','mtime':0} if path.suffix=='.gz' else None)

def digest(v):return hashlib.sha256(json.dumps(clean(v),sort_keys=True,separators=(',',':')).encode()).hexdigest()
def team_key(pid,workers):return pid+'__'+digest(sorted(workers))[:20]
def rng(v):return np.random.default_rng(int(digest([SEED,v])[:16],16))
def pool_lookup():return {p['pool_id']:p for p in read(FUSION/'INPUT_SNAPSHOT.json.gz')['images']}

def setup_engine():
    os.environ['PERSONNEL_V2_REPOSITORY']=str(ROOT)
    sys.path[:0]=[str(ROOT),str(FUSION),str(COMP),str(CORNER)]
    import fusion_engine as fe
    import fusion_runner as fr
    import summarize_grid as sg
    from corner_distance import corner_compare
    fr.FE=fe
    return fe,fr,sg,corner_compare

def existing_cache():
    full,partial={},{};ledger=[]
    for path in CACHE_PATHS:
        if not path.exists():
            ledger.append(dict(path=str(path.relative_to(ROOT)),status='not_materialized'));continue
        value=read(path);rows=list(value.values()) if isinstance(value,dict) else value
        nfull=0
        for row in rows:
            if 'team_key' not in row:continue
            key=team_key(row['pool_id'],row['member_workers'])
            if key!=row['team_key']:raise ValueError('noncanonical historical team key')
            if 'geometry' in row:
                if key in full and (full[key].get('B8L2'),full[key].get('nodes'))!=(row.get('B8L2'),row.get('nodes')):
                    raise ValueError('conflicting historical endpoint')
                full[key]=row;nfull+=1
            else:partial[key]=row
        ledger.append(dict(path=str(path.relative_to(ROOT)),status='loaded',rows=len(rows),complete_endpoint_rows=nfull,scalar_only_rows=len(rows)-nfull))
    return full,partial,ledger

def method_rows():
    """Use only target-building-excluded labels. New methods added explicitly."""
    source=TAX/'labels/lobo_labels.csv';d=pd.read_csv(source,keep_default_na=False);out=[]
    for r in d.to_dict('records'):
        common=dict(condition=r['condition'],heldout_building=r['heldout_building'],worker_id=r['worker_id'],label_source=str(source.relative_to(ROOT)))
        for method,col,tier,parent in [
          ('M_structure','primary_coarse_class','coarse','primary_coarse_class'),
          ('M_structure','primary_fine_class','fine','primary_coarse_class'),
          ('SP_scale','primary_coarse_class','coarse','primary_coarse_class'),
          ('SP_scale','primary_fine_class','fine','primary_coarse_class'),
          ('A2_relation','geometry_relation_class','single','geometry_relation_class')]:
            if method=='M_structure' and r['condition']!='manual':continue
            if method=='SP_scale' and r['condition']!='semi':continue
            cl=r[col]
            if cl in ('','unknown','unassigned','insufficient_evidence'):continue
            out.append(dict(common,method_id=method,tier=tier,class_id=cl,parent_class=r[parent]))
    for extra in [OUT.parent/'multivariate/labels_lobo.csv.gz',OUT.parent/'multivariate/same_source_candidate_labels.csv']:
        if extra.exists():
            e=pd.read_csv(extra,keep_default_na=False)
            for r in e.to_dict('records'):
                if r.get('heldout_building')=='ALL':continue
                if str(r.get('known',True)).lower() not in ('true','1'):continue
                common={k:r[k] for k in ('method_id','condition','heldout_building','worker_id')}
                for tier in ('coarse','fine'):
                    cl=r[tier+'_class']
                    if cl not in ('','unknown','unassigned','insufficient_evidence'):
                        out.append(dict(common,tier=tier,class_id=cl,parent_class=r['coarse_class'],label_source=str(extra.relative_to(ROOT))))
    ext=OUT/'legacy_composition_labels.csv'
    if ext.exists():out.extend(pd.read_csv(ext,keep_default_na=False).to_dict('records'))
    frame=pd.DataFrame(out)
    if frame.duplicated(['method_id','tier','condition','heldout_building','worker_id']).any():raise ValueError('duplicate label key')
    return frame

def method_maps():
    d=method_rows();maps={}
    for (method,tier,condition,building),g in d.groupby(['method_id','tier','condition','heldout_building']):
        maps[method,tier,condition,building]={r.worker_id:r.class_id for r in g.itertuples()}
    return maps

def count_vectors(capacities,n):
    cs=sorted(capacities)
    def rec(i,left,vals):
        if i==len(cs):
            if left==0:yield tuple(vals)
            return
        lo=max(0,left-sum(capacities[c] for c in cs[i+1:]));hi=min(left,capacities[cs[i]])
        for k in range(lo,hi+1):yield from rec(i+1,left-k,vals+[k])
    for vals in rec(0,n,[]):yield dict(zip(cs,vals))

def vector_coefficients(capacities):
    coef=[1]
    for size in capacities:
        updated=[0]*(len(coef)+size)
        for i,c in enumerate(coef):
            for j in range(size+1):updated[i+j]+=c
        coef=updated
    return coef

def canonical_counts(counts):return '|'.join(f'{c}:{n}' for c,n in sorted(counts.items()))

def inventory():
    pools=pool_lookup();full,partial,cache_ledger=existing_cache();maps=method_maps();rows=[];layer=[]
    full_by=collections.defaultdict(list);partial_by=collections.defaultdict(list)
    for row in full.values():full_by[row['pool_id']].append(row)
    for row in partial.values():partial_by[row['pool_id']].append(row)
    for p in pools.values():
        ws={r['worker_id'] for r in p['records']};N=len(ws);meta=p['meta']
        for n in range(1,N+1):
            layer.append(dict(meta,n=n,all_actual_member_sets=str(math.comb(N,n)),all_ordered_length_n_sequences=str(math.perm(N,n)),
                full_geometry_cache_sets=sum(r.get('k',len(r['member_workers']))==n and set(r['member_workers'])<=ws for r in full_by[p['pool_id']]),
                scalar_only_cache_sets=sum(len(r['member_workers'])==n and set(r['member_workers'])<=ws and r['team_key'] not in full for r in partial_by[p['pool_id']]),
                all_full_addition_orders=str(math.factorial(N)),all_n_endpoints_have_n_factorial_equivalent_orders=str(math.factorial(n))))
        for (method,tier,cond,bld),labels in maps.items():
            if (cond,bld)!=(meta['condition'],meta['building']):continue
            if method in ('Rnew2','F01') and meta['layer']!='ordinary_manual':continue
            members=ws&labels.keys();cap=collections.Counter(labels[w] for w in members);cnt=vector_coefficients(cap.values());U=len(members)
            for n in range(1,U+1):
                cache=[r for r in full_by[p['pool_id']] if len(r['member_workers'])==n and set(r['member_workers'])<=members]
                covered={canonical_counts({c:sum(labels[w]==c for w in r['member_workers']) for c in cap}) for r in cache}
                rows.append(dict(pool_id=p['pool_id'],image=meta['image'],building=bld,condition=cond,layer=meta['layer'],difficulty=meta['difficulty'],method_id=method,tier=tier,
                    eligible_pool_n=N,labelled_pool_n=U,unlabelled_pool_n=N-U,class_capacities=canonical_counts(cap),n=n,
                    feasible_class_vectors=cnt[n],all_actual_member_sets=str(math.comb(U,n)),all_ordered_sequences=str(math.perm(U,n)),
                    geometry_cache_sets=len(cache),geometry_cache_vectors=len(covered),uncomputed_actual_member_sets=str(math.comb(U,n)-len(cache)),
                    observed_member_variation_estimable=math.comb(U,n)>1,full_team_is_singleton=n==U))
    csv(OUT/'POOL_SIZE_UNIVERSE.csv',pd.DataFrame(layer));csv(OUT/'CLASS_VECTOR_UNIVERSE.csv',pd.DataFrame(rows));csv(OUT/'FROZEN_LABELS.csv',method_rows())
    totals={}
    for kind,pp in itertools.groupby(sorted(pools.values(),key=lambda p:p['meta']['layer']),lambda p:p['meta']['layer']):
        xx=list(pp);ns=[len(p['records']) for p in xx]
        totals[kind]=dict(pools=len(xx),all_nonempty_sets=str(sum(2**n-1 for n in ns)),all_sets_n_ge_15=str(sum(sum(math.comb(n,k) for k in range(15,n+1)) for n in ns)),
          exact_top_one_layers=sum(sum(math.comb(n,k) for k in range(max(1,n-1),n+1)) for n in ns),
          exact_top_two_layers=sum(sum(math.comb(n,k) for k in range(max(1,n-2),n+1)) for n in ns),
          exact_top_three_layers=sum(sum(math.comb(n,k) for k in range(max(1,n-3),n+1)) for n in ns))
    receipt=dict(pool_count=len(pools),full_geometry_cache_unique=len(full),scalar_cache_unique=len(partial),cache_sources=cache_ledger,universe_by_layer=totals,
       cache_boundary='Materialized endpoints only; historical computed-but-excluded caches are tracked separately, not presumed available.',
       interpretation='All class vectors, all concrete sets within vectors, and addition sequences are separate finite populations. Same deterministic set endpoint is evaluated once.')
    save(OUT/'UNIVERSE_RECEIPT.json',receipt);print(json.dumps(receipt,ensure_ascii=False),flush=True)

def benchmark():
    pools=list(pool_lookup().values());fe,fr,sg,corner=setup_engine();full,partial,_=existing_cache();out=[]
    selected=[]
    for layer in ('ordinary_manual','ordinary_semi','doorway_manual'):
        options=[p for p in pools if p['meta']['layer']==layer and len(p['records'])>=25]
        for difficulty in sorted({p['meta']['difficulty'] for p in options}):
            pp=[p for p in options if p['meta']['difficulty']==difficulty]
            selected.append(min(pp,key=lambda p:digest(['benchmark',p['pool_id']])))
    for p in selected:
        ws=sorted(r['worker_id'] for r in p['records']);N=len(ws);random=rng(['benchmark',p['pool_id']]);cache={};rows=[];start=time.monotonic()
        with fe.cached_matching(),fe.scoring_engine(fe.ENGINE/'measurement_engine.zip',fe.ENGINE/'working_models.py') as (engine,models):
            for n in sorted({max(15,N//2),min(20,N),N-2,N}):
                nteams=min(8,math.comb(N,n))
                sets={tuple(sorted(random.choice(ws,n,replace=False).tolist())) for _ in range(nteams*3)}
                for members in sorted(sets)[:nteams]:
                    row=fr.evaluate_one(p,members,engine,models,score_cache=cache);rows.append(row)
            existing=[r for r in full.values() if r['pool_id']==p['pool_id']]
            if existing:
                expected=sorted(existing,key=lambda r:r['team_key'])[0]
                got=fr.evaluate_one(p,expected['member_workers'],engine,models,score_cache=cache)
                for key in ('B8L2','D10'):
                    a,b=got.get(key),expected.get(key)
                    assert (a is None and b is None) or a is not None and b is not None and math.isclose(a,b,abs_tol=1e-7,rel_tol=1e-10),(key,a,b)
                rows.append(got)
        elapsed=time.monotonic()-start
        save(OUT/'benchmark_endpoints'/(p['pool_id']+'.json.gz'),dict(teams=rows))
        for row in rows:out.append(dict(pool_id=p['pool_id'],layer=p['meta']['layer'],difficulty=p['meta']['difficulty'],N=N,n=row['k'],fusion_seconds=row['fusion_seconds'],score_seconds=row.get('score_seconds'),score_status=row['score_status']))
        print(json.dumps(dict(pool_id=p['pool_id'],teams=len(rows),seconds=elapsed,per_second=len(rows)/elapsed)),flush=True)
    d=pd.DataFrame(out);csv(OUT/'THROUGHPUT.csv',d)
    v=dict(teams=len(d),native_fusion_seconds=float(d.fusion_seconds.sum()),scoring_seconds=float(d.score_seconds.sum()),median_total_seconds=float((d.fusion_seconds+d.score_seconds.fillna(0)).median()),p90_total_seconds=float((d.fusion_seconds+d.score_seconds.fillna(0)).quantile(.9)),jobs_capacity_proposed=6,checkpoint_endpoints_reused=True)
    save(OUT/'THROUGHPUT_RECEIPT.json',v);print(json.dumps(v),flush=True)

def main():
    p=argparse.ArgumentParser();p.add_argument('command',choices=['inventory','benchmark']);a=p.parse_args()
    {'inventory':inventory,'benchmark':benchmark}[a.command]()

if __name__=='__main__':main()
