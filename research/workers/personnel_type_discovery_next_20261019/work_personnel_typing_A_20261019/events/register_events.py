"""Freeze label-independent exact Pro replacement and new nested-even requests.

This file only selects frozen eligible real workers. It never imports class
discovery, scoring or fusion code and never reads team outcomes.
"""
from __future__ import annotations
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path
import argparse, csv, gzip, hashlib, io, json, math, os, uuid
import numpy as np

HERE = Path(__file__).resolve().parent
DEFAULT_NATIVE = HERE.parent / 'recovered' / 'work_v2_20261019' / 'fusion'
SEED = 20261019
KS = (8, 12, 16, 24)

def canonical(x):
    return json.dumps(x, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False)

def digest(x):
    return hashlib.sha256(canonical(x).encode()).hexdigest()

def file_sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def read(p):
    with (gzip.open(p, 'rt', encoding='utf-8') if str(p).endswith('.gz') else open(p, encoding='utf-8')) as f:
        return json.load(f)

def atomic(p, raw):
    p = Path(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    if p.exists():
        assert p.read_bytes() == raw, f'frozen output differs: {p}; use another version directory'
        return
    tmp = p.with_name(p.name + '.tmp.' + uuid.uuid4().hex)
    with tmp.open('wb') as f:
        f.write(raw); f.flush(); os.fsync(f.fileno())
    tmp.replace(p)

def save_json(p, value):
    raw = (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode()
    atomic(p, raw)

def save_gz(p, value):
    atomic(p, gzip.compress(canonical(value).encode(), compresslevel=6, mtime=0))

def save_csv_gz(p, rows):
    fields = list(dict.fromkeys(k for r in rows for k in r))
    buf = io.StringIO(newline='')
    w = csv.DictWriter(buf, fieldnames=fields)
    w.writeheader(); w.writerows(rows)
    raw = buf.getvalue().encode('utf-8-sig')
    atomic(p, gzip.compress(raw, compresslevel=6, mtime=0))

def seed_for(*parts):
    return int(digest([SEED, *parts])[:16], 16)

def subset_key(r, lookup):
    return '|'.join(sorted(lookup[w]['object_id'] for w in r['worker_ids']))

def meta_event(pool, panel, a, b, background, chain='', pair='', replicate=None):
    ma, mb = set(a['worker_ids']), set(b['worker_ids'])
    wa, wb = a['entrant_worker_id'], b['entrant_worker_id']
    assert wa < wb and ma - mb == {wa} and mb - ma == {wb}
    assert set(background) == ma & mb and len(background) == a['k']-1 == b['k']-1
    m = pool['meta']
    identity = [panel, pool['pool_id'], a['background_id'], wa, wb]
    return dict(event_id='Aevt_' + digest(identity)[:24], panel_id=panel,
                pool_id=pool['pool_id'], image_id=m['image_id'], image=m['image'],
                building=m['building'], condition=m['condition'], layer=m['layer'], difficulty=m['difficulty'],
                difficulty_aligned=m['difficulty_aligned'], reference_id=m['reference_id'], reference_version=m['reference_version'],
                k=a['k'], background_id=a['background_id'], background_members='|'.join(sorted(background)),
                background_order='|'.join(background), worker_a=wa, worker_b=wb,
                request_a=a['request_id'], request_b=b['request_id'],
                member_workers_a='|'.join(sorted(ma)), member_workers_b='|'.join(sorted(mb)),
                ordered_workers_a='|'.join(a['worker_ids']), ordered_workers_b='|'.join(b['worker_ids']),
                chain_id=chain, person_pair_id=pair, background_replicate=replicate,
                information_stage='historical_class_assignment_before_target_answer',
                event_selection_uses_target_geometry=False, event_selection_uses_classes=False)

def register(native, out):
    inp = read(native / 'INPUT_SNAPSHOT.json.gz')
    initial = read(native / 'REQUESTS_INITIAL.json.gz')
    inherited = read(native / 'DESIGN.json')
    assert file_sha(native/'INPUT_SNAPSHOT.json.gz') == inherited['input_snapshot_sha256']
    pools = {p['pool_id']:p for p in inp['images'] if p['meta']['layer']=='ordinary_manual'}
    assert len(pools)==177 and sum(len(p['records']) for p in pools.values())==5719
    legacy = [r for r in initial['requests'] if r['pool_id'] in pools and r['request_family']=='fixed_background']
    grouped = defaultdict(list)
    for r in legacy:
        grouped[r['background_id']].append(r)
    events=[]
    for bid,g in sorted(grouped.items()):
        for a,b in combinations(sorted(g,key=lambda r:r['entrant_worker_id']),2):
            events.append(meta_event(pools[a['pool_id']], 'Pro_exact_fixed_background_v1', a,b,a['background_worker_ids']))
    assert len(events)==270370 and len(legacy)==26290
    nested=[]; coverage=[]; chain_rows=[]
    for pid,pool in sorted(pools.items()):
        workers=sorted(r['worker_id'] for r in pool['records'])
        lookup={r['worker_id']:r for r in pool['records']}
        possible=list(combinations(workers,2))
        if len(workers)<min(KS)+1:
            for k in KS:
                coverage.append(dict(pool_id=pid,image_id=pool['meta']['image_id'],building=pool['meta']['building'],
                                     k=k,pool_n=len(workers),possible_pairs=len(possible),selected_pairs=0,
                                     backgrounds=0,events=0,reason='fewer_than_k_plus_one_real_workers'))
            continue
        rng=np.random.default_rng(seed_for('pair_sample',pid))
        chosen=sorted(possible[int(i)] for i in rng.choice(len(possible),size=min(12,len(possible)),replace=False))
        for wa,wb in chosen:
            pair='Apair_'+digest([pid,wa,wb])[:20]
            remaining=[w for w in workers if w not in (wa,wb)]
            for rep in range(2):
                order=[str(w) for w in np.random.default_rng(seed_for('background_order',pid,wa,wb,rep)).permutation(remaining)]
                chain='Achain_'+digest([pid,wa,wb,rep])[:24]
                k_available=[k for k in KS if len(order)>=k-1]
                chain_rows.append(dict(chain_id=chain,person_pair_id=pair,pool_id=pid,image_id=pool['meta']['image_id'],
                                       building=pool['meta']['building'],worker_a=wa,worker_b=wb,background_replicate=rep,
                                       background_full_order='|'.join(order),k_available='|'.join(map(str,k_available)),
                                       background_seed_decimal=str(seed_for('background_order',pid,wa,wb,rep))))
                for k in k_available:
                    bg=order[:k-1]
                    bid=chain+f'__k{k}'
                    sides=[]
                    for w in (wa,wb):
                        req=dict(request_id=bid+'__in_'+w,pool_id=pid,request_family='A_nested_even',
                                 strategy='uniform_person_pair_nested_background',k=k,background_id=bid,
                                 background_worker_ids=bg,entrant_worker_id=w,worker_ids=bg+[w],
                                 draw_id=rep,chain_id=chain,person_pair_id=pair,
                                 reference_id=pool['meta']['reference_id'],reference_version=pool['meta']['reference_version'],
                                 ordered_object_ids=[lookup[x]['object_id'] for x in bg+[w]],
                                 seed=seed_for('background_order',pid,wa,wb,rep))
                        nested.append(req);sides.append(req)
                    events.append(meta_event(pool,'A_nested_even_v1',*sides,bg,chain,pair,rep))
        for k in KS:
            supported=len(workers)>=k+1
            coverage.append(dict(pool_id=pid,image_id=pool['meta']['image_id'],building=pool['meta']['building'],
                                 k=k,pool_n=len(workers),possible_pairs=len(possible),selected_pairs=len(chosen) if supported else 0,
                                 backgrounds=2 if supported else 0,events=2*len(chosen) if supported else 0,
                                 reason='' if supported else 'fewer_than_k_plus_one_real_workers'))
    requests=legacy+nested
    assert len({r['request_id'] for r in requests})==len(requests)
    assert len({r['event_id'] for r in events})==len(events)
    byid={r['request_id']:r for r in requests}
    for e in events:
        a,b=byid[e['request_a']],byid[e['request_b']]
        assert a['pool_id']==b['pool_id']==e['pool_id'] and a['k']==b['k']==e['k']
    # Pilot: 100 unique real teams, stable hash order within difficulty x k,
    # selected round-robin over strata before any result is computed.
    unique={}
    for r in requests:
        pool=pools[r['pool_id']];lk={x['worker_id']:x for x in pool['records']}
        unique.setdefault((r['pool_id'],subset_key(r,lk)),r)
    strata=defaultdict(list)
    for r in unique.values():
        strata[(pools[r['pool_id']]['meta']['difficulty'],r['k'])].append(r)
    for key in strata:
        strata[key].sort(key=lambda r:digest(['timing_pilot',r['request_id']]))
    pilot=[];index=0
    while len(pilot)<min(100,len(unique)):
        for key in sorted(strata):
            if index<len(strata[key]):pilot.append(strata[key][index])
            if len(pilot)==min(100,len(unique)):break
        index+=1
    save_gz(out/'REQUESTS.json.gz',dict(schema='PartA_registered_requests_v1',data_release='v2',requests=requests))
    save_gz(out/'PILOT_REQUESTS_100.json.gz',dict(schema='PartA_timing_pilot_v1',data_release='v2',requests=pilot))
    save_csv_gz(out/'event_design.csv.gz',events)
    save_csv_gz(out/'nested_chains.csv.gz',chain_rows)
    save_csv_gz(out/'nested_coverage.csv.gz',coverage)
    membership=[dict(pool_id=pid,**{k:p['meta'][k] for k in ('image_id','image','building','condition','layer','difficulty','reference_id','reference_version')},
                     worker_id=r['worker_id'],object_id=r['object_id'],origin=r['origin'])
                for pid,p in sorted(pools.items()) for r in p['records']]
    save_csv_gz(out/'pool_members.csv.gz',membership)
    design=dict(design_id='PartA_common_events_v1',status='frozen_before_new_fusion_and_class_results',data_release='v2',
                github_main_commit='dafa73ac7d8ada9a7f5c0e483d695adcbd916550',native_source_commit=inp['git_commit'],
                seed=SEED,seed_derivation='SHA256 canonical JSON [20261019,family,pool,...] first16hex to numpy.default_rng',
                primary_scope='ordinary Manual quality-eligible independent real answers',k=list(KS),
                legacy_panel='Pro exact saved fixed backgrounds, all remaining-entrant pairs, no change to old request values',
                nested_panel='12 unordered worker pairs sampled uniformly without replacement per supported pool; 2 independent full background permutations per pair; prefixes k-1; no class or Q/geometry-based event selection',
                paired_orientation='lexicographic worker_a -> worker_b, signed outcome B-A',
                fusion=inherited['frozen_fusion'],tolerances=inherited['practical_tolerances'],
                strict=dict(q=1,floor=.02,angle=2),main=dict(q=2,floor=.05,angle=3),wide=dict(q=5,floor=.1,angle=5),
                failures='retain all attempts; no missing-value zero fill; joint stability false for failure, component outcomes remain unavailable',
                inference='retrospective building-heldout classes; building equal main; pool/image equal and event equal also shown',
                after_answer_conditionals=['target point count','target actual clusters','votes and connection state'],
                no_Dot_complete_reproduction=True,no_odd_even_extension=True,no_GitHub_mutation=True,
                n_requests=len(requests),n_unique_teams=len(unique),n_events=len(events),n_nested_chains=len(chain_rows),
                panel_events=dict(Counter(e['panel_id'] for e in events)),request_families=dict(Counter(r['request_family'] for r in requests)),
                n_pools_with_events=len({e['pool_id'] for e in events}),n_buildings_with_events=len({e['building'] for e in events}),
                support_nested_by_k={str(k):sum(p['meta']['pool_n']>=k+1 for p in pools.values()) for k in KS},
                inputs={f:file_sha(native/f) for f in ('INPUT_SNAPSHOT.json.gz','REQUESTS_INITIAL.json.gz','DESIGN.json')},
                method_hashes=inherited['functions_and_input_hashes'],
                registration_script_sha256=file_sha(__file__))
    save_json(out/'DESIGN.json',design)
    receipt=dict(design_sha256=file_sha(out/'DESIGN.json'),frozen_before_results=True,
                 files={p.name:dict(sha256=file_sha(p),bytes=p.stat().st_size) for p in [out/'REQUESTS.json.gz',out/'PILOT_REQUESTS_100.json.gz',out/'event_design.csv.gz',out/'nested_chains.csv.gz',out/'nested_coverage.csv.gz',out/'pool_members.csv.gz']},
                 n_requests=len(requests),n_unique_teams=len(unique),n_events=len(events),n_pilot_requests=len(pilot),
                 assertions=['legacy request values unchanged','event IDs unique','both teams share exact k-1 background','same replacement identities across nested k','all members real and distinct','same reference across endpoint pairs','no outcomes imported or read'])
    save_json(out/'REGISTRATION_RECEIPT.json',receipt)
    print(json.dumps({k:v for k,v in design.items() if k in ('n_requests','n_unique_teams','n_events','n_nested_chains','panel_events','support_nested_by_k')},ensure_ascii=False,indent=2))

if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--native',type=Path,default=DEFAULT_NATIVE)
    ap.add_argument('--out',type=Path,default=HERE)
    args=ap.parse_args();register(args.native.resolve(),args.out.resolve())
