"""Freeze exact v2.1 target-separated replacement teams from an explicit cell list.

Reads labels, capacity cells and optionally prior identities; never reads target
quality. Existing blocks are reused only if they are truly legal under the
current fold labels. Equal member endpoints are registered once across methods.
"""
from __future__ import annotations
import argparse,collections,csv,gzip,hashlib,itertools,json,math,random,shutil,os
from pathlib import Path
from capacity_space import read_json,read_labels,truth,canonical_hash,capacities,exact_counts,write_csv

SEED=2026102907
COMMIT='a476461d7ede8db95da43de4139e612c05e618bc'

def key(pid,ws):return pid+'__'+canonical_hash(sorted(ws))[:20]
def members(x):return sorted(x if isinstance(x,list) else (str(x).split('|') if x else []))
def write_json(path,obj):
    p=Path(path);p.parent.mkdir(parents=True,exist_ok=True);b=json.dumps(obj,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
    temp=p.with_name(p.name+'.tmp')
    with temp.open('wb') as f:
        f.write(gzip.compress(b,mtime=0) if p.suffix=='.gz' else b);f.flush();os.fsync(f.fileno())
    temp.replace(p)
def partition_id(groups):return canonical_hash(sorted(sorted(v) for v in groups.values()))[:24]
def class_vector(ws,groups):return '|'.join(f'{c}:{len(set(ws)&set(v))}' for c,v in sorted(groups.items()))
def rng(*parts):return random.Random(int(canonical_hash([SEED,*parts])[:16],16))
def block_sig(x,y,z):return tuple(sorted([tuple(x),tuple(y)])),tuple(z)

def select_blocks(cell,groups,pid,old,blocks):
    s,t,m=cell['source_class'],cell['target_class'],int(cell['m']);S=set(groups[s]);T=set(groups[t]);found=[];seen=set()
    # Cross-method existing identities are permissible only after current-label
    # checks. An old method's class name is never taken as evidence of legality.
    for e in old:
        x,y,z=(members(e.get(k)) for k in ('X','Y','Z'))
        if len(x)!=m or len(y)!=m or len(z)!=m:continue
        if not(set(x)<=S and set(y)<=S and set(z)<=T):continue
        if len(set(x+y+z))!=3*m:continue
        sig=block_sig(x,y,z)
        if sig not in seen:found.append((x,y,z,'existing_members_revalidated',e.get('event_id','')));seen.add(sig)
        if len(found)>=blocks:return found
    R=rng('XYZ',pid,sorted(S),sorted(T),m)
    maximum=math.comb(len(S),m)*math.comb(len(S)-m,m)*math.comb(len(T),m)//2
    for attempt in range(max(50,blocks*50)):
        xy=R.sample(sorted(S),2*m);x,y=sorted(xy[:m]),sorted(xy[m:]);z=sorted(R.sample(sorted(T),m));sig=block_sig(x,y,z)
        if sig not in seen:found.append((x,y,z,'new_seeded_blocks',''));seen.add(sig)
        if len(found)>=min(blocks,maximum):break
    return found

def make_event(pool,cell,groups,x,y,z,d,block,background,origin,oldid,design='strict_disjoint_ABC'):
    meta=pool['meta'];pid=pool['pool_id'];s,t=cell['source_class'],cell['target_class'];m=int(cell['m']);n=int(cell['n'])
    pieces=[set(q) for q in [d,x,y,z]]
    assert all(not(a&b) for a,b in itertools.combinations(pieces,2))
    assert len(x)==len(y)==len(z)==m and len(d)==n-m
    assert set(x+y)<=set(groups[s]) and set(z)<=set(groups[t])
    allws={r['worker_id'] for r in pool['records']};assert set(d+x+y+z)<=allws
    teams={'A':sorted(d+x),'B':sorted(d+y),'C':sorted(d+z)}
    actual={a+b:len(set(teams[a])-set(teams[b])) for a,b in [('A','B'),('A','C'),('B','C')]}
    assert set(actual.values())=={m}
    e=dict(pool_id=pid,image=meta['image'],building=meta['building'],condition=meta['condition'],layer=meta['layer'],difficulty=meta.get('difficulty'),
           reference_id=meta['reference_id'],reference_version=meta['reference_version'],analysis_scope=meta.get('analysis_scope','primary_target'),
           method=cell['method'],heldout_building=meta['building'],source_class=s,target_class=t,n=n,m=m,pool_n=len(allws),
           design=design,selection_phase=cell.get('selection_phase','v21_internal_exploration'),
           event_id=canonical_hash([pid,cell['method'],s,t,n,m,d,x,y,z])[:24],
           background_id=canonical_hash([pid,d])[:20],block_id=canonical_hash([pid,x,y,z])[:20],
           method_partition_id=partition_id(groups),block_replicate=block,background_replicate=background,
           background_target_n=len(set(d)&set(groups[t])),background_source_n=len(set(d)&set(groups[s])),background_unknown_n=len(set(d)&set(groups.get('unknown',[]))),
           D='|'.join(d),X='|'.join(x),Y='|'.join(y),Z='|'.join(z),
           replacement_fraction=m/n,source_capacity=len(groups[s]),target_capacity=len(groups[t]),
           source_candidate_fraction=m/len(groups[s]),target_candidate_fraction=m/len(groups[t]),
           source_A_seat_fraction=m/(m+len(set(d)&set(groups[s]))),target_C_seat_fraction=m/(m+len(set(d)&set(groups[t]))),
           actual_m_AB=actual['AB'],actual_m_AC=actual['AC'],actual_m_BC=actual['BC'],seat_net_change_l1=2*m,
           block_origin=origin,reused_identity_event_id=oldid,data_release='v2.1')
    for arm,ws in teams.items():
        e[arm+'_team_key']=key(pid,ws);e[arm+'_members']='|'.join(ws);e[arm+'_class_vector']=class_vector(ws,groups)
    assert e['A_class_vector']==e['B_class_vector']
    return e,teams

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--pools',nargs='+',required=True);ap.add_argument('--labels',required=True)
    ap.add_argument('--cells',required=True);ap.add_argument('--output',required=True);ap.add_argument('--condition',default='manual')
    ap.add_argument('--blocks',type=int,default=1);ap.add_argument('--backgrounds',type=int,default=1)
    ap.add_argument('--reuse-events',nargs='*',default=[]);ap.add_argument('--background-levels',default='low,mid,high')
    a=ap.parse_args();out=Path(a.output);out.mkdir(parents=True,exist_ok=True)
    labels=read_labels(a.labels);cells=read_labels(a.cells);pools={p['pool_id']:p for fn in a.pools for p in read_json(fn)['images']}
    lookup=collections.defaultdict(list)
    for r in labels:
        if r.get('heldout_building')=='ALL':continue
        if r.get('condition',a.condition) not in ('',a.condition,'joint','both'):continue
        lookup[r['method'],r['heldout_building']].append(r)
    old=collections.defaultdict(list)
    for path in a.reuse_events:
        for r in read_labels(path):
            if r.get('design') not in ('strict_disjoint_ABC','strict_ABC'):continue
            old[r['pool_id'],int(float(r['n'])),int(float(r['m']))].append(r)
    # Persist immutable formation inputs before constructing or scoring a team.
    frozen=dict(commit=COMMIT,data_release='v2.1',seed=SEED,
        labels_sha256=hashlib.sha256(Path(a.labels).read_bytes()).hexdigest(),cells_sha256=hashlib.sha256(Path(a.cells).read_bytes()).hexdigest(),
        label_path=str(Path(a.labels).resolve()),cells_path=str(Path(a.cells).resolve()),blocks=a.blocks,backgrounds=a.backgrounds,
        background_levels=a.background_levels,score_blind_registration=True,old_event_inputs=a.reuse_events,
        pool_fingerprints={pid:canonical_hash(p) for pid,p in pools.items() if pid in {r['pool_id'] for r in cells}})
    write_json(out/'FROZEN_REGISTRATION_INPUTS.json',frozen)
    seen=set();requests={};events=[];coverage=[];perpool=collections.defaultdict(list)
    for c in cells:perpool[c['pool_id']].append(c)
    for pid,cc in sorted(perpool.items()):
        pool=pools[pid];meta=pool['meta'];assert meta['condition']==a.condition;ws=sorted(r['worker_id'] for r in pool['records']);pe=[];pool_fingerprint=frozen['pool_fingerprints'][pid]
        for cell in cc:
            n,m=int(cell['n']),int(cell['m']);groups=capacities(pool,lookup[cell['method'],meta['building']]);s,t=cell['source_class'],cell['target_class']
            counts=exact_counts(len(ws),len(groups[s]),len(groups[t]),n,m);assert counts['strict_ABC'],cell
            blocks=select_blocks(cell,groups,pid,old[pid,n,m],a.blocks);before=len(pe);bgseen=set()
            for bi,(x,y,z,origin,oldid) in enumerate(blocks):
                rest=sorted(set(ws)-set(x+y+z));rt=sorted(set(rest)&set(groups[t]));ro=sorted(set(rest)-set(groups[t]));d=n-m
                lo=max(0,d-len(ro));hi=min(d,len(rt));levels={'low':lo,'mid':(lo+hi)//2,'high':hi}
                selected_levels=sorted(set(levels.values())) if a.background_levels=='balanced' else sorted({levels[k] for k in a.background_levels.split(',')})
                if a.background_levels=='balanced':
                    # One target-background stratum per cell, balanced by a
                    # label-partition/size hash rather than by target outcomes.
                    selected_levels=[selected_levels[int(canonical_hash([pid,partition_id(groups),groups[s],groups[t],n,m])[:12],16)%len(selected_levels)]]
                for target_n in selected_levels:
                    for bg in range(a.backgrounds):
                        R=rng('D',pid,x,y,z,bg);tr=rt.copy();oth=ro.copy();R.shuffle(tr);R.shuffle(oth)
                        D=sorted(tr[:target_n]+oth[:d-target_n]);matched_old_id=oldid
                        # Reuse an entire old D/X/Y/Z only when its identities
                        # and current target-background count satisfy this cell.
                        exact_old=[]
                        if origin=='existing_members_revalidated':
                            for old_event in old[pid,n,m]:
                                if block_sig(members(old_event.get('X')),members(old_event.get('Y')),members(old_event.get('Z')))!=block_sig(x,y,z):continue
                                candidate_D=members(old_event.get('D'))
                                if len(candidate_D)!=d or not set(candidate_D)<=set(rest):continue
                                if len(set(candidate_D)&set(rt))!=target_n:continue
                                if candidate_D not in [v[0] for v in exact_old]:exact_old.append((candidate_D,old_event.get('event_id','')))
                            if bg<len(exact_old):D,matched_old_id=exact_old[bg]
                        e,teams=make_event(pool,cell,groups,x,y,z,D,bi,bg,origin,matched_old_id)
                        e['entire_DXYZ_reused']=bool(exact_old and bg<len(exact_old))
                        if e['event_id'] in seen:continue
                        seen.add(e['event_id']);pe.append(e);bgseen.add(e['background_id'])
                        for arm,ww in teams.items():
                            k=e[arm+'_team_key'];requests[k]=dict(team_key=k,pool_id=pid,n=n,member_workers='|'.join(ww),input_pool_sha256=pool_fingerprint)
            coverage.append(dict(cell,registered_events=len(pe)-before,registered_distinct_XYZ=len(blocks),registered_backgrounds=len(bgseen),
                requested_XYZ=a.blocks,requested_D_per_level=a.backgrounds,**counts))
        events.extend(pe);write_csv(out/'event_shards'/(pid+'.csv.gz'),pe)
        write_json(out/'REGISTRATION_PROGRESS.json',dict(pools_completed=len(list((out/'event_shards').glob('*.csv.gz'))),events=len(events),unique_teams=len(requests)))
    write_csv(out/'EVENTS_EXACT.csv.gz',events);write_csv(out/'REQUESTS.csv.gz',requests.values());write_csv(out/'REGISTERED_COVERAGE.csv.gz',coverage)
    write_json(out/'DESIGN.json',dict(frozen,registered_cells=len(coverage),events=len(events),unique_teams=len(requests),pools=len(perpool),
         strict_ABC_identity_checks_passed=True,member_combinations_exhausted=False,
         distinct_endpoints_counted_once=True,reused_block_event_count=sum(e['block_origin']=='existing_members_revalidated' for e in events)))
    print(json.dumps(dict(events=len(events),unique_teams=len(requests),pools=len(perpool),cells=len(coverage))),flush=True)

if __name__=='__main__':main()
