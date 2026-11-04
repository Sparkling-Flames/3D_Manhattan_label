"""Input-only, fixed-seed DSTRUCT C1/C3 50% strict ABC supplement.

No scores, labor values, or endpoint outcomes are consulted for selection.
The 8/4 study uses every feasible direction/pool. The 6/3 study uses only
the shared 36-pool domain and four disjoint class blocks at each shared D.
"""
from __future__ import annotations
import collections, datetime, gzip, hashlib, itertools, json, random
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[5]
OUT = Path(__file__).resolve().parents[1]
SEED = 20261104013
COMMIT = '48a2fc6aedd51cd701b1bce06c02bd3ef92ec75b'
POOL_PATH = ROOT/'research/data/releases/v2.1/pools/INPUT_SNAPSHOT.json'
LABEL_PATH = ROOT/'research/workers/current_class_interpretation_20261104/basis/WORKER_LABELS_ALL_LOBO.csv.gz'
RAW_PATH = ROOT/'research/data/releases/v2.1/admitted_space_extension/image_difficulty_20261030/classification/RAW_TARGET_RESPONSE_RECORDS.csv.gz'
METHOD = 'TARGET_DSTRUCT_K3'

def digest(x):
    return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def rng(*args): return random.Random(int(digest([SEED,*args])[:16],16))
def key(pid,ws): return pid+'__'+digest(sorted(ws))[:20]

def write_json(path,x):
    path=Path(path); path.parent.mkdir(parents=True,exist_ok=True)
    b=json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False).encode()
    if path.suffix=='.gz': b=gzip.compress(b,mtime=0)
    path.write_bytes(b)

def csv(path,df):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    b=df.to_csv(index=False).encode('utf-8-sig')
    if path.suffix=='.gz':b=gzip.compress(b,mtime=0)
    path.write_bytes(b)

def main():
    if (OUT/'design/DESIGN.json').exists():
        raise RuntimeError('Design is frozen; do not overwrite after outcomes become available.')
    pools=json.loads(POOL_PATH.read_text())['images']
    pools={p['pool_id']:p for p in pools if p['meta']['condition']=='manual' and p['meta']['layer']=='ordinary_manual'}
    labels=pd.read_csv(LABEL_PATH)
    labels=labels[(labels.method==METHOD)&(labels.heldout_building!='ALL')&labels.known.eq(True)]
    assert not labels.duplicated(['heldout_building','worker_id']).any()
    lm={(r.heldout_building,r.worker_id):r.class_id for r in labels.itertuples()}
    raw=pd.read_csv(RAW_PATH,low_memory=False)
    raw=raw[(raw.scope=='primary')&(raw.layer=='ordinary_manual')&(raw.condition=='manual')]
    assert set(raw.pool_id)==set(pools) and len(pools)==206
    meta={pid:g.iloc[0] for pid,g in raw.groupby('pool_id')}
    capacities=[];source_audit=[];classmaps={};groups={}
    for pid,p in sorted(pools.items()):
        q=raw[raw.pool_id==pid];m=p['meta'];workers=sorted(r['worker_id'] for r in p['records'])
        assert len(workers)==len(set(workers)) and set(workers)==set(q.worker_id)
        cm={w:lm.get((m['building'],w),'unknown') for w in workers};classmaps[pid]=cm
        gg={c:sorted(w for w in workers if cm[w]==c) for c in ('C1','C2','C3','unknown')};groups[pid]=gg
        for r in p['records']:
            z=q[q.object_id==r['object_id']];assert len(z)==1
            z=z.iloc[0];pp=np.asarray(r['points'])
            assert len(pp)%2==0 and np.isfinite(pp).all()
            assert np.array_equal(pp[::2,0],pp[1::2,0]), (pid,r['object_id'],'unshared x')
            assert z.reference_id==m['reference_id'] and z.reference_version==m['reference_version']
            a,b=r['source_time_seconds'],z.source_active_time_seconds
            assert (a is None and pd.isna(b)) or np.isclose(a,b,rtol=0,atol=1e-9)
            assert r['time_source_kind']==z.time_source
        row=dict(pool_id=pid,image=m['image'],building=m['building'],reference_id=m['reference_id'],reference_version=m['reference_version'],
                 official_difficulty=meta[pid].official_difficulty,scene=meta[pid].scene,pool_n=len(workers),**{c:len(ws) for c,ws in gg.items()})
        for mm in range(1,9):
            for s,t in [('C1','C3'),('C3','C1')]:row[f'feasible_{2*mm}_{mm}_{s}_to_{t}']=len(gg[s])>=2*mm and len(gg[t])>=mm and len(workers)>=4*mm
        row['paired_6_3']=len(gg['C1'])>=6 and len(gg['C3'])>=6 and len(workers)>=15
        capacities.append(row)
        source_audit.append(dict(pool_id=pid,pool_sha256=digest(p),workers=len(workers),worker_set_matches_current_raw=True,
                                 all_input_vertical_pairs_share_x=True,raw_time_values_and_kinds_match=True,reference_binding_matches=True))
    cap=pd.DataFrame(capacities)
    events=[];requests={};bundles=[]
    def add_event(pid,study,s,t,m,D,X,Y,Z,bundle,block,bg,target_slot):
        p=pools[pid];mt=p['meta'];cm=classmaps[pid];n=2*m
        sets=list(map(set,(D,X,Y,Z)))
        assert all(len(z)==m for z in sets)
        assert all(not a&b for a,b in itertools.combinations(sets,2))
        assert all(cm[w]==s for w in X+Y) and all(cm[w]==t for w in Z)
        assert set().union(*sets)<=set(cm)
        A=sorted(D+X);B=sorted(D+Y);C=sorted(D+Z)
        assert all(len(a)==n for a in (A,B,C))
        assert all(len(set(a)^set(b))==2*m for a,b in itertools.combinations((A,B,C),2))
        e=dict(study=study,method=METHOD,direction=s+'_to_'+t,source_class=s,target_class=t,n=n,m=m,replacement_fraction=.5,
               pool_id=pid,image=mt['image'],image_id=mt['image_id'],building=mt['building'],reference_id=mt['reference_id'],reference_version=mt['reference_version'],
               official_difficulty=meta[pid].official_difficulty,scene=meta[pid].scene,geometric_challenge=meta[pid].geometric_challenge,
               structural_condition=meta[pid].structural_condition,bundle_id=bundle,block_id=block,background_id=bg,target_slot=target_slot,
               D='|'.join(D),X='|'.join(X),Y='|'.join(Y),Z='|'.join(Z),
               D_class_vector=json.dumps(dict(collections.Counter(cm[w] for w in D)),sort_keys=True))
        for arm,ws in zip('ABC',(A,B,C)):
            tk=key(pid,ws);e[arm+'_team_key']=tk;e[arm+'_workers']='|'.join(ws)
            e[arm+'_class_vector']=json.dumps(dict(collections.Counter(cm[w] for w in ws)),sort_keys=True)
            rr=dict(team_key=tk,pool_id=pid,image=mt['image'],building=mt['building'],n=n,member_workers='|'.join(ws),
                    member_object_ids='|'.join(sorted(r['object_id'] for r in p['records'] if r['worker_id'] in ws)),
                    reference_id=mt['reference_id'],reference_version=mt['reference_version'],input_pool_sha256=digest(p))
            if tk in requests:assert requests[tk]==rr
            requests[tk]=rr
        assert e['A_class_vector']==e['B_class_vector']
        e['event_id']='C13_'+digest([study,pid,s,t,n,m,D,X,Y,Z])[:24]
        events.append(e)
    for row in capacities:
        pid=row['pool_id'];gg=groups[pid];allw=sorted(classmaps[pid])
        for s,t in [('C1','C3'),('C3','C1')]:
            if not row[f'feasible_8_4_{s}_to_{t}']:continue
            m=4;rr=rng('main_8_4',pid,s,t);seen=set();bb=0
            while bb<16:
                xy=rr.sample(gg[s],2*m);X=sorted(xy[:m]);Y=sorted(xy[m:]);Z=sorted(rr.sample(gg[t],m))
                sig=digest([sorted([X,Y]),Z])
                if sig in seen:continue
                seen.add(sig);block='B84_'+digest([pid,s,t,sig])[:18]
                remaining=sorted(set(allw)-set(X+Y+Z));ds=[]
                while len(ds)<2:
                    D=sorted(rr.sample(remaining,m))
                    if D not in ds:ds.append(D)
                for jj,D in enumerate(ds):
                    bg=f'{block}_D{jj+1}';add_event(pid,'main_8_4',s,t,m,D,X,Y,Z,block,block,bg,1)
                bb+=1
        if row['paired_6_3']:
            m=3;rr=rng('paired_6_3',pid);seen=set();bb=0
            while bb<8:
                a=rr.sample(gg['C1'],2*m);b=rr.sample(gg['C3'],2*m)
                P,Q,R,S=[sorted(x) for x in (a[:m],a[m:],b[:m],b[m:])]
                sig=digest([sorted([P,Q]),sorted([R,S])])
                if sig in seen:continue
                seen.add(sig);block='B63_'+digest([pid,sig])[:18]
                remaining=sorted(set(allw)-set(P+Q+R+S));ds=[]
                while len(ds)<2:
                    D=sorted(rr.sample(remaining,m))
                    if D not in ds:ds.append(D)
                for jj,D in enumerate(ds):
                    bg=f'{block}_D{jj+1}';bundle=bg
                    for s,t,X,Y,zs in [('C1','C3',P,Q,[R,S]),('C3','C1',R,S,[P,Q])]:
                        for zz,Z in enumerate(zs):add_event(pid,'paired_6_3',s,t,m,D,X,Y,Z,bundle,block,bg,zz+1)
                    bundles.append(dict(bundle_id=bundle,block_id=block,background_id=bg,pool_id=pid,image=row['image'],building=row['building'],
                                        D='|'.join(D),P='|'.join(P),Q='|'.join(Q),R='|'.join(R),S='|'.join(S),
                                        P_team_key=key(pid,D+P),Q_team_key=key(pid,D+Q),R_team_key=key(pid,D+R),S_team_key=key(pid,D+S)))
                bb+=1
    ev=pd.DataFrame(events);req=pd.DataFrame(list(requests.values()))
    assert not ev.event_id.duplicated().any() and not req.team_key.duplicated().any()
    selected=set(req.pool_id);selected_pools=[pools[x] for x in sorted(selected)]
    times=[dict(object_id=r['object_id'],source_active_time_seconds=r['source_time_seconds'],target_matched_time_seconds=r['target_time_seconds'],
                time_source_kind=r['time_source_kind'],pool_id=p['pool_id'],worker_id=r['worker_id']) for p in selected_pools for r in p['records']]
    assert len({r['object_id'] for r in times})==len(times)
    csv(OUT/'design/POOL_CAPACITY.csv.gz',cap)
    csv(OUT/'design/SOURCE_AUDIT.csv.gz',pd.DataFrame(source_audit))
    csv(OUT/'design/EVENTS.csv.gz',ev)
    csv(OUT/'design/REQUESTS.csv.gz',req.sort_values(['pool_id','team_key']))
    csv(OUT/'design/PAIRED_BUNDLES.csv.gz',pd.DataFrame(bundles))
    csv(OUT/'inputs/CURRENT_TIME_INDEX.csv.gz',pd.DataFrame(times))
    csv(OUT/'inputs/LOBO_LABELS.csv.gz',labels)
    csv(OUT/'inputs/POOL_CONTEXT.csv.gz',raw.drop_duplicates('pool_id')[['pool_id','official_difficulty','geometric_challenge','structural_condition','ref_turn5','ref_H','ref_short_edges']])
    write_json(OUT/'inputs/SELECTED_POOLS.json.gz',dict(data_release='v2.1',source=str(POOL_PATH.relative_to(ROOT)),images=selected_pools))
    counts=ev.groupby(['study','direction']).agg(events=('event_id','size'),pools=('pool_id','nunique'),buildings=('building','nunique')).reset_index()
    spec=dict(frozen_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),source_commit=COMMIT,method=METHOD,seed=SEED,
              source_files={str(p.relative_to(ROOT)):sha(p) for p in [POOL_PATH,LABEL_PATH,RAW_PATH]},
              main=dict(n=8,m=4,all_feasible_ordinary_manual_primary_pools=True,XYZ_blocks_per_pool_direction=16,backgrounds_per_block=2,
                        sampling='Uniform independent source 2m and target m draws; unordered X/Y deduplicated; D drawn uniformly without replacement from remaining workers; two distinct D per block'),
              common=dict(n=6,m=3,common_domain='C1>=6,C3>=6,N>=15',four_block_bundles_per_pool=8,backgrounds_per_bundle=2,
                          ABC_per_background=4,shared_endpoints_per_background=4,
                          sampling='Two disjoint C1 blocks P/Q and two disjoint C3 blocks R/S; D uniform from remaining after all four blocks; two target choices per direction'),
              selection_does_not_read=['Q','T','fusion status','geometry outcomes','manual-order status'],
              weighting='Average target slot at shared D (6/3), then D within block, then blocks within image; image-equal main estimate; building-equal and building-cluster bootstrap sensitivity',
              main_method='Unmodified automatic fusion and Q scoring; exact approved-manual identity hits reported separately only',
              support='Missing Q stays missing; strict W/GA/GS use all three Q-valid endpoints; shared-direction paired6/3 comparison additionally requires all four endpoints',
              budget_pre_fusion=counts.to_dict('records'),unique_requested_endpoints=len(req),selected_pools=len(selected),
              design_files={str(p.relative_to(OUT)):sha(p) for p in sorted((OUT/'design').glob('*.csv.gz'))},
              no_outcome_adaptive_replication=True,classification_refit=False,coordinate_edits=False)
    write_json(OUT/'design/DESIGN.json',spec)
    print(json.dumps(spec,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
