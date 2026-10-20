"""Small A2-specific followup, after zero-cost relabelling; no outcome-selected teams."""
import argparse
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor,as_completed
import hashlib
import pandas as pd
import study as s
import relabel_a2

BASE=s.OUT
OUT=BASE/'a2_specific'


def labels():
    return {key:{w:{'coarse':c,'fine':c} for w,c in mapping.items()} for key,mapping in relabel_a2.maps().items()}


def prepare():
    pools=s.read(s.FUSION/'INPUT_SNAPSHOT.json.gz')['images'];maps=labels();selected=[]
    for condition in ['manual','semi']:
        groups=defaultdict(list)
        for p in pools:
            if p['meta']['layer']=='ordinary_'+condition and len(p['records'])>=7:groups[p['meta']['building']].append(p)
        chosen=sorted(groups,key=s.digest)[:12]
        for b in chosen:
            selected.append(min(groups[b],key=lambda p:(-len(p['records']),s.digest(p['pool_id']))))
    events=[];capacity=[]
    for p in selected:
        meta=p['meta'];lab=maps.get((meta['condition'],meta['building']),{})
        available=[r['worker_id'] for r in p['records'] if r['worker_id'] in lab]
        cs=sorted({lab[w]['coarse'] for w in available})
        for n,m in [(5,1),(9,2)]:
            for c in cs:
                for d in cs:
                    if c==d:continue
                    blocks,reason=s.draw_blocks(p,lab,'coarse',c,d,n,m,620)
                    row=dict(pool_id=p['pool_id'],image=meta['image'],building=meta['building'],condition=meta['condition'],
                             layer=meta['layer'],difficulty=meta['difficulty'],design_tier='coarse',n=n,m=m,repeat=0,
                             outgoing_class=c,incoming_class=d,reason=reason)
                    capacity.append(dict(row,feasible=blocks is not None))
                    if blocks is None:continue
                    e=dict(row,**blocks);e['event_id']='A2X_'+s.digest(e)[:22];s.validate(e,lab);events.append(e)
    s.save(OUT/'REQUESTS.json.gz',dict(events=events))
    s.csv(OUT/'CAPACITY.csv',pd.DataFrame(capacity));s.csv(OUT/'SELECTED_POOLS.csv',pd.DataFrame([p['meta'] for p in selected]))
    s.save(OUT/'REGISTRATION.json',dict(stage='A2-specific internal followup after B-design secondary relabelling',
        selection='max 12 hash-selected buildings per condition; largest eligible pool per building, hash tie-break',
        labels='A2 samecount-source-residual target-building-out class_id',
        label_sha256=hashlib.sha256((s.TAX/'route_a/worker_labels_lobo.csv').read_bytes()).hexdigest(),
        sizes=[{'n':5,'m':1},{'n':9,'m':2}],events=len(events),pools=len(selected),
        source='existing official quality-usable independent-voter snapshot, same-source-count disjoint exchanged blocks',
        boundary='New class-specific teams on the internal v2 image bank; not an external blind test',
        B8L2_primary=True,D10_sensitivity=True,fusion_unchanged=True))
    print('A2 registered',len(events),'ABC events',len(selected),'pools',flush=True)


def run(jobs):
    maps=labels();pools={p['pool_id']:p for p in s.read(s.FUSION/'INPUT_SNAPSHOT.json.gz')['images']}
    req=s.read(OUT/'REQUESTS.json.gz')['events'];group=defaultdict(list)
    for e in req:group[e['pool_id']].append(e)
    s.OUT=OUT
    receipts=[]
    with ProcessPoolExecutor(max_workers=jobs) as ex:
        fs=[]
        for pid,es in group.items():
            p=pools[pid];fs.append(ex.submit(s.run_pool,p,es,maps[p['meta']['condition'],p['meta']['building']]))
        for f in as_completed(fs):receipts.append(f.result());print(receipts[-1],flush=True)
    teams={};events=[]
    for pid in group:
        r=s.read(OUT/'runtime'/(pid+'.json.gz'));teams.update(r['teams']);events.extend(r['events'])
    s.save(OUT/'TEAMS.json.gz',teams);s.csv(OUT/'EVENTS.csv.gz',pd.DataFrame(events));s.save(OUT/'RUN_RECEIPT.json',dict(pools=receipts,teams=len(teams),events=len(events)))
    s.summarize_events()


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('stage',choices=['prepare','run']);ap.add_argument('--jobs',type=int,default=4);a=ap.parse_args()
    prepare() if a.stage=='prepare' else run(a.jobs)
