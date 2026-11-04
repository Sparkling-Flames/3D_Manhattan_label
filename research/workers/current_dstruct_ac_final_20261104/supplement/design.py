"""Freeze a small current-label AC coverage supplement without outcome selection.

Only uncovered ordinary Manual pool/class-pair cells at existing 14/7 and 20/7
budgets are eligible. Scores, labor, reference coordinates and fusion states do
not participate in selection. Input records/reference are copied unchanged.
"""
from __future__ import annotations
import collections, datetime, gzip, hashlib, itertools, json, math, random
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
STUDY = OUT.parent
SEED = 202611041301
COMMIT = '48a2fc6aedd51cd701b1bce06c02bd3ef92ec75b'
METHOD = 'TARGET_DSTRUCT_K3'
POOL_PATH = ROOT/'research/data/releases/v2.1/pools/INPUT_SNAPSHOT.json'
LABEL_PATH = ROOT/'research/data/releases/v2.1/admitted_space_extension/image_difficulty_20261030/classification/LABELS_ALL_LOBO.csv.gz'
MISSING_PATH = STUDY/'audit/PRELIM_CORE_BUDGET_MISSING_POOLS.csv'

def digest(x):
    return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def key(pid,ws):return pid+'__'+digest(sorted(ws))[:20]
def rng(*args):return random.Random(int(digest([SEED,*args])[:16],16))
def csv(path,df):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    b=df.to_csv(index=False).encode('utf-8-sig')
    if path.suffix=='.gz':b=gzip.compress(b,mtime=0)
    path.write_bytes(b)
def write_json(path,x):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    b=json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False).encode()
    if path.suffix=='.gz':b=gzip.compress(b,mtime=0)
    path.write_bytes(b)

def choose_blocks(s,t,m,rr):
    """Uniform distinct X/Z choices; enumerate all if there are <= 16."""
    possible=math.comb(len(s),m)*math.comb(len(t),m)
    if possible<=16:
        blocks=list(itertools.product(itertools.combinations(s,m),itertools.combinations(t,m)))
        rr.shuffle(blocks)
    else:
        blocks=[];seen=set()
        while len(blocks)<16:
            b=(tuple(sorted(rr.sample(s,m))),tuple(sorted(rr.sample(t,m))))
            if b not in seen:blocks.append(b);seen.add(b)
    return possible,blocks

def main():
    if (OUT/'DESIGN.json').exists():
        raise RuntimeError('Frozen design exists. Do not overwrite after effects are available.')
    missing=pd.read_csv(MISSING_PATH).sort_values(['pool_id','pair','n','m'])
    assert len(missing)==22 and missing.pool_id.nunique()==7
    assert set(zip(missing.n,missing.m))=={(14,7),(20,7)}
    allp=json.loads(POOL_PATH.read_text())['images']
    pools={p['pool_id']:p for p in allp if p['pool_id'] in set(missing.pool_id)}
    labels=pd.read_csv(LABEL_PATH)
    labels=labels[(labels.method==METHOD)&(labels.heldout_building!='ALL')&labels.known.eq(True)]
    assert not labels.duplicated(['heldout_building','worker_id']).any()
    lm={(r.heldout_building,r.worker_id):r.class_id for r in labels.itertuples()}
    events=[];requests={};blocks_out=[];audits=[];times=[]
    for pid,pool in sorted(pools.items()):
        mt=pool['meta'];assert mt['condition']=='manual' and mt['layer']=='ordinary_manual'
        ws=[r['worker_id'] for r in pool['records']]
        assert len(ws)==len(set(ws))
        for r in pool['records']:
            pp=np.asarray(r['points']);assert np.isfinite(pp).all()
            assert np.array_equal(pp[::2,0],pp[1::2,0])
            times.append(dict(pool_id=pid,worker_id=r['worker_id'],object_id=r['object_id'],source_active_time_seconds=r['source_time_seconds'],
                              target_matched_time_seconds=r['target_time_seconds'],time_source_kind=r['time_source_kind']))
        audits.append(dict(pool_id=pid,image=mt['image'],input_pool_sha256=digest(pool),reference_id=mt['reference_id'],reference_version=mt['reference_version'],
                           records=len(ws),original_shared_x_verified=True,member_duplicate_count=0))
    for cell in missing.itertuples():
        p=pools[cell.pool_id];mt=p['meta'];n=int(cell.n);m=int(cell.m)
        allw=sorted(r['worker_id'] for r in p['records'])
        cm={w:lm.get((mt['building'],w),'unknown') for w in allw}
        assert set(allw)==set(cell.workers.split('|'))
        s,t=cell.pair.split('_');sg=sorted(w for w in allw if cm[w]==s);tg=sorted(w for w in allw if cm[w]==t)
        assert len(sg)>=m and len(tg)>=m and len(allw)>=n+m
        assert mt['reference_id']==cell.reference_id and mt['reference_version']==cell.reference_version
        rr=rng(cell.pool_id,cell.pair,n,m)
        possible,blocks=choose_blocks(sg,tg,m,rr)
        bnum=len(blocks)
        for bi,(xx,zz) in enumerate(blocks):
            X=list(xx);Z=list(zz);remaining=sorted(set(allw)-set(X+Z))
            desired=32//bnum+(bi<32%bnum)
            total_D=math.comb(len(remaining),n-m);desired=min(desired,total_D)
            if total_D<=desired:
                ds=list(itertools.combinations(remaining,n-m));rr.shuffle(ds)
            else:
                ds=[];seen=set()
                while len(ds)<desired:
                    d=tuple(sorted(rr.sample(remaining,n-m)))
                    if d not in seen:ds.append(d);seen.add(d)
            bid='ACG_BLOCK_'+digest([cell.pool_id,n,m,X,Z])[:20]
            blocks_out.append(dict(pool_id=cell.pool_id,pair=cell.pair,n=n,m=m,block_id=bid,X='|'.join(X),Z='|'.join(Z),
                                   possible_XZ_blocks=possible,selected_XZ_blocks=bnum,possible_D_count=total_D,selected_D_count=len(ds)))
            for di,dd in enumerate(ds):
                D=list(dd);A=sorted(D+X);C=sorted(D+Z)
                assert len(A)==n and len(C)==n and set(A)&set(C)==set(D)
                assert not set(D)&set(X+Z) and not set(X)&set(Z)
                event=dict(event_id='ACG_'+digest([cell.pool_id,n,m,D,X,Z])[:24],study='current_capacity_gap_supplement',
                           source_family='current_capacity_gap_supplement',method=METHOD,direction=s+'_to_'+t,current_direction=s+'_to_'+t,
                           source_class=s,target_class=t,pair=cell.pair,n=n,m=m,replacement_fraction=m/n,pool_id=cell.pool_id,
                           image=mt['image'],image_id=mt['image_id'],building=mt['building'],scope='primary',condition='manual',layer='ordinary_manual',
                           reference_id=mt['reference_id'],reference_version=mt['reference_version'],difficulty=mt['difficulty'],
                           D='|'.join(D),X='|'.join(X),Z='|'.join(Z),D_class_vector=json.dumps(dict(collections.Counter(cm[w] for w in D)),sort_keys=True),
                           D_C1=sum(cm[w]=='C1' for w in D),D_C2=sum(cm[w]=='C2' for w in D),D_C3=sum(cm[w]=='C3' for w in D),D_unknown=sum(cm[w]=='unknown' for w in D),
                           block_id=bid,background_id=bid+'_D'+str(di+1),sampling_identity='uniform_XZ_blocks_then_uniform_mixed_D_in_uncovered_cell')
                for arm,ws in [('A',A),('C',C)]:
                    tk=key(cell.pool_id,ws);event[arm+'_team_key']=tk;event[arm+'_workers']='|'.join(ws)
                    own=[r for r in p['records'] if r['worker_id'] in ws]
                    row=dict(team_key=tk,pool_id=cell.pool_id,image=mt['image'],building=mt['building'],n=n,member_workers='|'.join(ws),
                             member_object_ids='|'.join(sorted(r['object_id'] for r in own)),reference_id=mt['reference_id'],reference_version=mt['reference_version'],
                             input_pool_sha256=digest(p),input_selected_records_sha256=digest(own))
                    if tk in requests:assert row==requests[tk]
                    requests[tk]=row
                event['physical_pair_key']='ACG_PAIR_'+digest([cell.pool_id,sorted([event['A_team_key'],event['C_team_key']])])[:24]
                events.append(event)
    ev=pd.DataFrame(events);req=pd.DataFrame(list(requests.values()))
    assert not ev.event_id.duplicated().any() and not ev.physical_pair_key.duplicated().any()
    assert not req.team_key.duplicated().any()
    for p,df in [('EVENTS.csv.gz',ev),('REQUESTS.csv.gz',req.sort_values(['pool_id','team_key'])),('BLOCKS.csv.gz',pd.DataFrame(blocks_out)),
                 ('MISSING_CAPACITY_CELLS.csv',missing),('SOURCE_AUDIT.csv',pd.DataFrame(audits)),('inputs/CURRENT_TIME_INDEX.csv.gz',pd.DataFrame(times)),
                 ('inputs/LOBO_LABELS.csv.gz',labels)]:csv(OUT/p,df)
    write_json(OUT/'inputs/SELECTED_POOLS.json.gz',dict(data_release='v2.1',source=str(POOL_PATH.relative_to(ROOT)),images=[pools[x] for x in sorted(pools)]))
    spec=dict(frozen_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),source_commit=COMMIT,seed=SEED,
              source_files={str(p.relative_to(ROOT)):sha(p) for p in [POOL_PATH,LABEL_PATH,MISSING_PATH]},
              reason='Current-label legal historical generic-AC coverage absent in these 22 existing-core-budget cells; no outcome-driven inclusion',
              budgets=[[14,7],[20,7]],eligible_cells=len(missing),unique_pool_class_pairs=missing[['pool_id','pair']].drop_duplicates().shape[0],
              images=missing.image.nunique(),buildings=missing.building.nunique(),
              selection='At most 16 distinct uniform X/Z block pairs; all pairs when finite space <=16. Allocate a total target of 32 distinct backgrounds/physical pairs equally across selected blocks. D is uniform from all remaining people, with mixed classes allowed. Independently seeded by pool,pair,n,m.',
              no_selection_use_of=['Q','T','reference geometry','fusion state','expected direction'],
              method_events=len(ev),physical_pairs=ev.physical_pair_key.nunique(),unique_requested_teams=len(req),
              counts=ev.groupby(['pair','n','m']).agg(events=('event_id','size'),images=('image','nunique'),buildings=('building','nunique')).reset_index().to_dict('records'),
              aggregation='Backgrounds within X/Z block, blocks within image; paired-event mean is identical when D allocation is equal. Report supplemental images alone; any expanded-cohort analysis keeps legacy/current-gap sources explicit.',
              existing_endpoint_reuse='Exact key and input/reference identity checked before new evaluation. No replacement of frozen requests after effects.',
              design_sha256={p.name:sha(p) for p in sorted(OUT.glob('*.csv*'))})
    write_json(OUT/'DESIGN.json',spec)
    print(json.dumps({k:spec[k] for k in ['frozen_utc','seed','eligible_cells','images','buildings','method_events','unique_requested_teams','counts']},ensure_ascii=False))

if __name__=='__main__':main()
