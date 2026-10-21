"""Checkpointed exhaustive evaluation of the frozen finite n20 panel.

Plans, endpoint input index, per-pool pair caches, and <=20000-row verified
result shards bound RAM and preserve every finished portion. No fusion/scoring.
"""
from __future__ import annotations
import argparse,collections,csv,gc,gzip,hashlib,json,os,sqlite3,time
from pathlib import Path
import pandas as pd
from event_kernel import evaluate_one
from evaluate_n20_abc import HERE,STUDY,available_sources,typed,gs,read_csv,save_csv,save_json,sha
from atomic_checkpoint_io import save_csv

def iter_csv(p):
    op=gzip.open if str(p).endswith('.gz') else open
    with op(p,'rt',encoding='utf-8-sig',newline='') as f:yield from csv.DictReader(f)

def prepare(condition,max_rows=20000):
    folder=HERE/('checkpointed_'+condition);folder.mkdir(exist_ok=True)
    target=folder/'PLAN_RECEIPT.json'
    if target.exists():return json.loads(target.read_text())
    design=HERE/('design_'+condition)/'MATCHED_ABC_EVENTS.csv.gz'
    groups=collections.defaultdict(list);keys=set()
    for r in iter_csv(design):
        groups[(r['building'],r['pool_id'])].append(r)
        keys.update(r['team_'+a] for a in 'ABC')
    rows=[];details=[];total_pairs=0;total_events=0
    inputs=folder/'event_inputs';inputs.mkdir(exist_ok=True)
    for (building,pool),events in sorted(groups.items()):
        pairs={(r['team_'+a],r['team_'+b]) for r in events for a,b in [('A','B'),('A','C'),('B','C')]}
        total_pairs+=len(pairs);total_events+=len(events)
        details.append(dict(building=building,pool_id=pool,events=len(events),unique_oriented_geometry_pairs=len(pairs)))
        for start in range(0,len(events),max_rows):
            subset=events[start:start+max_rows];part=len(rows)+1;name=f'part_{part:04d}'
            result=save_csv(inputs/(name+'.csv.gz'),subset,key='event_id')
            rows.append(dict(part=name,building=building,pool_id=pool,events=len(subset),input_path=result['path'],input_sha256=result['sha256']))
    plan=save_csv(folder/'CHECKPOINT_PLAN.csv',rows)
    scale=save_csv(folder/'POOL_PAIR_SCALE.csv',details)
    save_json(folder/'NEEDED_TEAM_KEYS.json',sorted(keys))
    receipt=dict(condition=condition,events=total_events,pools=len(groups),buildings=len({k[0] for k in groups}),
      max_events_per_shard=max_rows,shards=len(rows),needed_endpoint_keys=len(keys),unique_oriented_geometry_pairs=total_pairs,
      design_sha256=sha(design),all_finite_registered_panel_events_retained=True,uses_outcomes_to_plan=False,
      processing_order='building, pool_id; frozen design order within each pool',outputs=[plan,scale])
    save_json(target,receipt);print(json.dumps(receipt),flush=True);return receipt

def build_index(folder):
    keys=set(json.loads((folder/'NEEDED_TEAM_KEYS.json').read_text()))
    db=sqlite3.connect(folder/'endpoint_index.sqlite')
    db.execute('CREATE TABLE IF NOT EXISTS endpoints (team_key TEXT PRIMARY KEY, scalars TEXT, geometry TEXT)')
    db.execute('CREATE TABLE IF NOT EXISTS sources (path TEXT PRIMARY KEY, sha256 TEXT NOT NULL)')
    sources=[]
    for scalar,geometry in available_sources():
        rel=str(scalar.relative_to(STUDY));seen=db.execute('SELECT sha256 FROM sources WHERE path=?',(rel,)).fetchone()
        hs=sha(scalar);hg=sha(geometry)
        sources.extend([dict(path=rel,sha256=hs),dict(path=str(geometry.relative_to(STUDY)),sha256=hg)])
        if seen:
            assert seen[0]==hs,'completed upstream input changed'
            assert db.execute('SELECT sha256 FROM sources WHERE path=?',(str(geometry.relative_to(STUDY)),)).fetchone()[0]==hg
            continue
        with db:
            for r in iter_csv(scalar):
                if r['team_key'] in keys:db.execute('INSERT OR REPLACE INTO endpoints (team_key,scalars) VALUES (?,?)',(r['team_key'],json.dumps(r,separators=(',',':'))))
            for r in iter_csv(geometry):
                if r['team_key'] in keys:
                    old=db.execute('SELECT scalars FROM endpoints WHERE team_key=?',(r['team_key'],)).fetchone()
                    assert old is not None
                    assert json.loads(old[0])['member_workers']==r['member_workers']
                    db.execute('UPDATE endpoints SET geometry=? WHERE team_key=?',(r['geometry_json'] or 'null',r['team_key']))
            db.executemany('INSERT INTO sources VALUES (?,?)',[(rel,hs),(str(geometry.relative_to(STUDY)),hg)])
        print(json.dumps({'indexed_source':rel,'needed_endpoints_available':db.execute('SELECT COUNT(*) FROM endpoints WHERE geometry IS NOT NULL').fetchone()[0]}),flush=True)
    available=db.execute('SELECT COUNT(*) FROM endpoints WHERE geometry IS NOT NULL').fetchone()[0]
    save_json(folder/'INDEX_RECEIPT.json',dict(needed=len(keys),available=available,sources=sources,index_is_reproducible_temporary_cache=True))
    return db,sources

def load_pool(db,keys):
    teams={}
    for key in keys:
        row=db.execute('SELECT scalars,geometry FROM endpoints WHERE team_key=?',(key,)).fetchone()
        if row is None or row[1] is None:continue
        d=typed(json.loads(row[0]));d['geometry']=json.loads(row[1]);teams[key]=d
    return teams

def run(condition,max_parts=None,only_building=None,partition_count=1,partition_index=0,read_only_index=False):
    begin=time.monotonic();prepare(condition)
    folder=HERE/('checkpointed_'+condition);plan=read_csv(folder/'CHECKPOINT_PLAN.csv')
    if read_only_index:
        db=sqlite3.connect('file:'+str(folder/'endpoint_index.sqlite')+'?mode=ro',uri=True)
        sources=json.loads((folder/'INDEX_RECEIPT.json').read_text())['sources']
    else:db,sources=build_index(folder)
    # Deterministic load balancing uses only exact pre-outcome pair counts.
    scales=read_csv(folder/'POOL_PAIR_SCALE.csv');loads=[0]*partition_count;assignment={}
    for row in sorted(scales,key=lambda x:(-int(x['unique_oriented_geometry_pairs']),x['pool_id'])):
        bucket=min(range(partition_count),key=lambda i:(loads[i],i));assignment[row['pool_id']]=bucket
        loads[bucket]+=int(row['unique_oriented_geometry_pairs'])
    histories=pd.read_csv(STUDY/'multivariate/continuous_features_lobo.csv.gz')
    hist={(r.condition,r.heldout_building,r.worker_id):r for r in histories.itertuples()}
    _,_,sg,corner=gs.setup_engine()
    # Frozen full schema matches the independently completed Semi evaluator.
    with gzip.open(HERE/'results_semi/N20_ABC_ALL_COMPONENT_EVENTS.csv.gz','rt',encoding='utf-8-sig',newline='') as f:columns=next(csv.reader(f))
    active_pool=None;teams={};pairs={};signatures={};completed_now=0
    output=folder/'shards';output.mkdir(exist_ok=True)
    for item in plan:
        if only_building and item['building']!=only_building:continue
        if assignment[item['pool_id']]!=partition_index:continue
        part=item['part'];receipt_path=output/(part+'_RECEIPT.json')
        if receipt_path.exists():continue
        started=time.monotonic();events=read_csv(HERE/item['input_path'])
        assert len(events)==int(item['events']) and sha(HERE/item['input_path'])==item['input_sha256']
        if active_pool!=item['pool_id']:
            active_pool=item['pool_id'];pairs={};signatures={};gc.collect()
            all_pool_inputs=[x for x in plan if x['pool_id']==active_pool]
            keys={r['team_'+a] for p in all_pool_inputs for r in iter_csv(HERE/p['input_path']) for a in 'ABC'}
            teams=load_pool(db,keys)
            missing=keys-set(teams)
            if missing:
                save_json(output/(part+'_PENDING.json'),dict(part=part,pool_id=active_pool,missing_endpoint_keys=sorted(missing)))
                print(json.dumps({'part':part,'pending':len(missing)}),flush=True);active_pool=None;continue
        pair_before=len(pairs);out=[]
        for i,request in enumerate(events):
            r=evaluate_one(request,teams,pairs,signatures,hist,sg,corner,condition)
            assert set(r)<=set(columns),sorted(set(r)-set(columns))
            out.append(r)
            if (i+1)%1000==0:print(json.dumps({'part':part,'evaluated':i+1,'events':len(events),'unique_pairs_this_pool':len(pairs),'seconds':time.monotonic()-started}),flush=True)
        out_clean=({k:gs.clean(r.get(k)) for k in columns} for r in out)
        result=save_csv(output/(part+'_EVENTS.csv.gz'),out_clean,columns,key='event_id')
        assert [r['event_id'] for r in out]==[r['event_id'] for r in events]
        receipt=dict(part=part,condition=condition,building=item['building'],pool_id=active_pool,events=len(out),
          all_scored=sum(r['all_scored'] for r in out),all_complete=sum(r['all_complete'] for r in out),
          new_oriented_geometry_pairs=len(pairs)-pair_before,pool_cumulative_pairs=len(pairs),
          input_sha256=item['input_sha256'],code_sha256=sha(Path(__file__)),kernel_sha256=sha(HERE/'event_kernel.py'),
          partition_index=partition_index,partition_count=partition_count,
          seconds=time.monotonic()-started,events_per_second=len(out)/(time.monotonic()-started),
          fusion_calls=0,score_calls=0,output=result)
        save_json(receipt_path,receipt);print(json.dumps(receipt),flush=True)
        del out,out_clean;gc.collect();completed_now+=1
        if max_parts and completed_now>=max_parts:break
    db.close()
    print(json.dumps({'finished_this_run':completed_now,'seconds':time.monotonic()-begin}),flush=True)

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--condition',choices=['manual','semi'],required=True)
    ap.add_argument('--prepare-only',action='store_true');ap.add_argument('--max-parts',type=int);ap.add_argument('--building')
    ap.add_argument('--index-only',action='store_true');ap.add_argument('--read-only-index',action='store_true')
    ap.add_argument('--partition-count',type=int,default=1);ap.add_argument('--partition-index',type=int,default=0)
    a=ap.parse_args()
    if a.prepare_only:prepare(a.condition)
    elif a.index_only:
        prepare(a.condition);db,_=build_index(HERE/('checkpointed_'+a.condition));db.close()
    else:run(a.condition,a.max_parts,a.building,a.partition_count,a.partition_index,a.read_only_index)
