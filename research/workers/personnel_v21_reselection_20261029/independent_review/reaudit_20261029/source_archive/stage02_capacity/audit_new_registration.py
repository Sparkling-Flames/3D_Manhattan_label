"""Independent checks of newly frozen ABC identities and matched n paths."""
from pathlib import Path
import collections, hashlib, itertools, json, os
import pandas as pd

ROOT=Path(__file__).resolve().parent.parent
REPO=ROOT/'repo'
NEW=ROOT/'HOHONET_v21_reaudit_20261029/stage03_new_abc'
OUT=ROOT/'audit_capacity/new_registration_audit'

def members(x):
    return set(str(x).split('|')) if pd.notna(x) and str(x) else set()

def team_key(pid, ws):
    h=hashlib.sha256(json.dumps(sorted(ws),sort_keys=True,separators=(',',':')).encode()).hexdigest()[:20]
    return pid+'__'+h

def atomic_csv(frame,path):
    tmp=path.with_name(path.name+'.writing')
    frame.to_csv(tmp,index=False,encoding='utf-8-sig',compression='gzip' if path.suffix=='.gz' else None)
    with tmp.open('rb') as f:os.fsync(f.fileno())
    tmp.replace(path)

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    pools={p['pool_id']:p for p in json.loads((REPO/'research/data/releases/v2.1/pools/INPUT_SNAPSHOT.json').read_text())['images']}
    e=pd.read_csv(NEW/'EVENTS_EXACT.csv.gz',low_memory=False)
    r=pd.read_csv(NEW/'REQUESTS.csv.gz')
    labels=pd.read_csv(NEW/'FROZEN_LABELS_ALL_LOBO.csv.gz',low_memory=False)
    labels=labels[labels.known.eq(True)&labels.heldout_building.ne('ALL')]
    lm=labels.set_index(['method','heldout_building','worker_id']).class_id.to_dict()
    old=pd.read_csv(ROOT/'audit_capacity/results/ALL_EXECUTED_EVENTS_Q_AND_IDENTITIES.csv.gz',low_memory=False)
    cells=pd.read_csv(NEW/'FROZEN_CELLS.csv',low_memory=False)
    omitted=pd.read_csv(NEW/'EXISTING_M7_CELLS_REUSED_NOT_RERUN.csv')
    issues=[]
    def check(ok,kind,identifier):
        if not ok:issues.append(dict(kind=kind,identifier=identifier))
    check(e.event_id.is_unique,'event_id_unique','ALL')
    check(r.team_key.is_unique,'request_team_unique','ALL')
    requested={row.team_key:row for row in r.itertuples()}
    for row in e.to_dict('records'):
        pid=row['pool_id']; p=pools[pid]; meta=p['meta']; eid=row['event_id']; allw={q['worker_id'] for q in p['records']}
        d,x,y,z=[members(row[c]) for c in ['D','X','Y','Z']]
        check(meta['layer']=='ordinary_manual' and row['scope']=='primary','scope_ordinary_primary',eid)
        check(row['building']==row['heldout_building']==meta['building'],'heldout_building_identity',eid)
        check(row['reference_id']==meta['reference_id'] and row['reference_version']==meta['reference_version'],'reference_identity',eid)
        check(len(d)==int(row['n'])-int(row['m']) and len(x)==len(y)==len(z)==int(row['m']),'block_cardinality',eid)
        check(all(not a&b for a,b in itertools.combinations([d,x,y,z],2)),'DXYZ_mutually_disjoint',eid)
        check(d|x|y|z <= allw,'real_pool_members',eid)
        check(all(lm.get((row['method'],row['building'],w))==row['source_class'] for w in x|y),'XY_same_source_fold_class',eid)
        check(all(lm.get((row['method'],row['building'],w))==row['target_class'] for w in z) and row['target_class']!=row['source_class'],'Z_distinct_target_fold_class',eid)
        for arm,block in [('A',x),('B',y),('C',z)]:
            expected=d|block; got=members(row[arm+'_members']); tk=row[arm+'_team_key']
            check(got==expected and len(got)==int(row['n']),'exact_team_members_'+arm,eid)
            check(tk==team_key(pid,expected),'team_hash_'+arm,eid)
            check(tk in requested,'request_exists_'+arm,eid)
            if tk in requested:
                req=requested[tk]
                check(req.pool_id==pid and req.n==row['n'] and members(req.member_workers)==expected,'request_identity_'+arm,eid)
        avec=collections.Counter(lm.get((row['method'],row['building'],w),'unknown') for w in d|x)
        bvec=collections.Counter(lm.get((row['method'],row['building'],w),'unknown') for w in d|y)
        check(avec==bvec,'AB_same_complete_class_composition',eid)
    check(set(r.team_key)==set(e.A_team_key)|set(e.B_team_key)|set(e.C_team_key),'exact_request_union','ALL')
    key=['method','pool_id','source_class','target_class','n','m']
    event_cells=set(map(tuple,e[key].to_numpy())); frozen_cells=set(map(tuple,cells[key].to_numpy()))
    check(event_cells==frozen_cells,'all_frozen_cells_registered','ALL')
    old_cells=set(map(tuple,old[old.design.eq('ABC')][key].to_numpy()))
    check(set(map(tuple,omitted[key].to_numpy()))<=old_cells,'omitted_m7_cells_truly_existing','ALL')
    m7_existing=e[e.m.eq(7)&~e.method.str.startswith('V21_')]
    check(not(set(map(tuple,m7_existing[key].to_numpy()))&old_cells),'new_old_method_m7_only_missing_cells','ALL')
    for k,g in e.groupby(key):
        sigs={(tuple(sorted((tuple(sorted(members(row.X))),tuple(sorted(members(row.Y)))))),tuple(sorted(members(row.Z)))) for row in g.itertuples()}
        check(len(sigs)==2,'two_distinct_XYZ',str(k))
        p=pools[k[1]]; allw={q['worker_id'] for q in p['records']}; method,b=k[0],p['meta']['building']; target=k[3]
        for _,bg in g.groupby('block_id'):
            br=bg.iloc[0]; consumed=members(br.X)|members(br.Y)|members(br.Z); rest=allw-consumed
            rt={w for w in rest if lm.get((method,b,w))==target}; ro=rest-rt;dsize=int(br.n-br.m)
            expected={max(0,dsize-len(ro)),min(dsize,len(rt))}
            actual={len(members(rr.D)&rt) for rr in bg.itertuples()}
            check(actual==expected,'low_high_target_background_levels',str(k))
    pairs=[]
    pathkeys=['method','pool_id','source_class','target_class','m','block_replicate','background_order']
    for k,g in e.groupby(pathkeys):
        for r0,r1 in itertools.combinations(g.sort_values('n').to_dict('records'),2):
            okay=(r0['X']==r1['X'] and r0['Y']==r1['Y'] and r0['Z']==r1['Z'] and members(r0['D'])<=members(r1['D']))
            check(okay,'fixed_XYZ_nested_D',str(k))
            pairs.append(dict(zip(pathkeys,k),n_small=int(r0['n']),n_large=int(r1['n']),event_small=r0['event_id'],event_large=r1['event_id'],
                              image=r0['image'],building=r0['building'],D_small=r0['D'],D_large=r1['D'],X=r0['X'],Y=r0['Y'],Z=r0['Z'],
                              identities_nested=okay))
    pairs=pd.DataFrame(pairs)
    atomic_csv(pairs,OUT/'INDEPENDENT_FIXED_XYZ_NESTED_N_PAIRS.csv.gz')
    pd.DataFrame(issues,columns=['kind','identifier']).to_csv(OUT/'VIOLATIONS.csv',index=False,encoding='utf-8-sig')
    e.groupby(['method','n','m']).agg(events=('event_id','nunique'),pools=('pool_id','nunique'),images=('image','nunique'),buildings=('building','nunique')).to_csv(OUT/'NEW_REGISTRATION_BY_METHOD_N_M.csv',encoding='utf-8-sig')
    if len(pairs):
        pairs.groupby(['method','n_small','n_large','m']).agg(pairs=('event_small','size'),pools=('pool_id','nunique'),images=('image','nunique'),buildings=('building','nunique')).to_csv(OUT/'NESTED_N_COVERAGE.csv',encoding='utf-8-sig')
    receipt=dict(events=len(e),requests=len(r),frozen_cells=len(cells),existing_m7_cells_not_rerun=len(omitted),
                 actual_XYZ_nested_n_pairs=len(pairs),violations=len(issues),all_event_identities_verified=not issues,
                 source_design=str(NEW),quality_outcomes_read=False,
                 check_scope='All registrations, pool/scope/reference, exact DXYZ and team/request identities, LOBO class membership, complete AB class composition, distinct blocks, feasible low/high target background levels, fixed XYZ and nested D across n, omitted existing m7 cells.')
    (OUT/'REGISTRATION_AUDIT.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2))
    print(json.dumps(receipt,ensure_ascii=False),flush=True)

if __name__=='__main__':main()
