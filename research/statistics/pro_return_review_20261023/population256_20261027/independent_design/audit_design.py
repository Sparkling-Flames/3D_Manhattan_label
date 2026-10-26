import csv, gzip, hashlib, io, json, zipfile, time, math
from collections import Counter, defaultdict
from pathlib import Path
import argparse
import numpy as np

ROOT=Path(__file__).resolve().parent
parser=argparse.ArgumentParser()
parser.add_argument('--downloads',type=Path,required=True)
args=parser.parse_args()
DOWNLOADS=args.downloads
PREFIX='research/workers/personnel_population_curves_v2_20261023/sampling_extension_20261026/'

def rows(z, name):
    with z.open(name) as raw, gzip.GzipFile(fileobj=raw) as gz, io.TextIOWrapper(gz, encoding='utf-8-sig', newline='') as text:
        yield from csv.DictReader(text)

def team(pid, members):
    # This digest is the published team identity algorithm, not file hashing.
    raw=json.dumps(sorted(members),sort_keys=True,separators=(',',':')).encode()
    return pid+'__'+hashlib.sha256(raw).hexdigest()[:20]

started=time.time()
design=zipfile.ZipFile(DOWNLOADS/'HOHONET_20261026_S01_exact_design.zip')
data=[zipfile.ZipFile(p) for p in sorted(DOWNLOADS.glob('HOHONET_20261026_DATA_S[12]_*.zip'))]
by_pool=defaultdict(list)
for z in data:
    for n in z.namelist():
        if n.endswith('.scalars.csv.gz'):
            by_pool[n.split('/parts/')[1].split('/')[0]].append((z,n))

counts=Counter(); states=Counter(); stage_counts=Counter(); errors=[]; pool_results=[]; max_q_diff=0.0
seeds=set()
plan=list(csv.DictReader((ROOT.parent/'design26/POOL_SAMPLING_PLAN.csv').open(encoding='utf-8-sig')))
for pi,p in enumerate(plan,1):
    pid=p['pool_id']; N=int(p['pool_n'])
    orders={}; indexes=[]; unique_orders=set(); pc=Counter()
    order_name=PREFIX+'design26/orders_by_pool/'+pid+'.csv.gz'
    for r in rows(design,order_name):
        ws=r['worker_order'].split('|'); assert len(ws)==len(set(ws))==N
        assert r['workers']==r['worker_order']
        i=int(r['new_index']); sd=int(r['seed'])
        if r['policy']=='natural_random':
            raw=json.dumps(['population_wholecurve_precision_20261026',2026102601,pid,i],separators=(',',':')).encode()
            expected=int.from_bytes(hashlib.sha256(raw).digest()[:8],'little')
            assert sd==expected and sd not in seeds
            seeds.add(sd)
            assert np.random.default_rng(sd).permutation(sorted(ws)).tolist()==ws
            indexes.append(i); unique_orders.add(tuple(ws)); pc['natural_orders']+=1
            assert int(r['stage'])==(1 if i<104 else 2)
            assert abs(float(r['sampling_weight_new_batch'])-1/104)<1e-15
        else:
            base=r['base_worker_order'].split('|'); target=set(r['target_members'].split('|'))
            assert ws==[w for w in base if w in target]+[w for w in base if w not in target]
            assert i<16 and abs(float(r['sampling_weight_new_batch'])-1/16)<1e-15
            pc['policy_orders']+=1
        assert r['path_id'] not in orders
        orders[r['path_id']]=(ws,r)
    assert sorted(indexes)==list(range(208))
    assert pc['policy_orders']==(64 if p['policy_common_pool']=='True' else 0)
    deps={}
    dep_name=PREFIX+'design26/dependencies_by_pool/'+pid+'.csv.gz'
    for r in rows(design,dep_name):
        assert r['team_key'] not in deps
        ws=r['member_workers'].split('|'); k=int(r['k'])
        assert len(ws)==len(set(ws))==k and len(r['member_object_ids'].split('|'))==k
        assert r['team_key']==team(pid,ws)
        deps[r['team_key']]=r
    new_keys={key for key,r in deps.items() if r['endpoint_source']=='new_native_required_20261026'}
    occurrence=Counter(); prefix_keys=set(); seenlinks=set()
    for stage in [1,2]:
        name=PREFIX+f'design26/links_by_pool/stage{stage}/'+pid+'.csv.gz'
        for r in rows(design,name):
            k=int(r['k']); ws,orr=orders[r['path_id']]
            assert (r['path_id'],k) not in seenlinks; seenlinks.add((r['path_id'],k))
            assert r['team_key']==team(pid,ws[:k])
            assert r['entrant_worker']==ws[k-1]
            assert r['stage']==str(stage)==orr['stage']
            assert deps[r['team_key']]['member_workers']=='|'.join(sorted(ws[:k]))
            occurrence[r['team_key']]+=1; prefix_keys.add(r['team_key']); pc['prefixes']+=1
    assert len(seenlinks)==len(orders)*N and prefix_keys==set(deps)
    # Requests are checked against actual scalar rows, one pool at a time.
    request_keys=set()
    for stage in [1,2]:
        name=PREFIX+f'design26/requests_by_pool/stage{stage}/'+pid+'.csv.gz'
        if name not in design.namelist(): continue
        for r in rows(design,name):
            assert r['team_key'] not in request_keys
            request_keys.add(r['team_key'])
            d=deps[r['team_key']]
            assert {k:v for k,v in r.items() if k!='source_table'}=={k:v for k,v in d.items() if k!='source_table'}
    assert request_keys==new_keys
    seen=set()
    for z,n in by_pool[pid]:
        pc['scalar_shards']+=1
        for r in rows(z,n):
            key=r['team_key']; assert key not in seen and key in new_keys; seen.add(key)
            d=deps[key]
            for field in ['pool_id','image','image_id','condition','k','member_workers','member_object_ids','reference_id','reference_version']:
                assert r[field]==d[field],(key,field,r[field],d[field])
            assert r['condition']=='manual'
            assert r['underlying_data_version']=='v2'
            if r['endpoint_state']=='scored':
                assert r['B8L2']!='' and r['score_available']=='True' and r['actual_consensus_failure']=='False'
                iou=float(r['iou_2d'])
                f=1/iou-1+float(r['S_bottom_deg'])**2/32 if iou>0 else math.inf
                angle=float(r['dir'])**2
                h=(float(r['Hmean'])/.8)**2+(float(r['Hcenter'])/.25)**2
                for metric,scale in [('B8L2',64),('D10',100)]:
                    value=100/(1+math.hypot(f,1.5*angle/(angle+scale))+h)
                    diff=abs(value-float(r[metric]));max_q_diff=max(max_q_diff,diff)
                    assert diff<1e-8,(key,metric,diff)
                pc['scores_recalculated']+=1
                if iou==0: pc['scored_zero_iou']+=1
            if r['actual_consensus_failure']=='True': assert r['B8L2']==''
            if r['policy_deferred']=='True': assert int(r['k'])==2 and r['B8L2']==''
            states[r['endpoint_state']]+=1
            stage_counts[r['execution_stage']]+=1
            pc['scalars']+=1
    assert seen==new_keys
    pc['unique_teams']=len(deps);pc['reused']=len(deps)-len(new_keys)
    pc['unique_natural_orders']=len(unique_orders)
    pc['duplicated_natural_draws']=208-len(unique_orders)
    counts.update(pc)
    pool_results.append(dict(pool_id=pid,pool_n=N,**dict(pc)))
    if pi%10==0 or pi==len(plan): print(f'{pi}/{len(plan)} pools, {counts["scalars"]} scalars, {time.time()-started:.1f}s',flush=True)

assert counts['natural_orders']==40352
assert counts['policy_orders']==10048
assert counts['prefixes']==1644576
assert counts['unique_teams']==1396509
assert counts['scalars']==1356657
assert counts['reused']==39852
report=dict(pools=len(plan),data_zip_count=len(data),counts=dict(counts),states=dict(states),stage_counts=dict(stage_counts),max_B8L2_D10_difference=max_q_diff,seconds=time.time()-started,scope='Independently regenerated all seeds/permutations, every prefix membership, all dependency/request/scalar keys and identities; recomputed B8L2/D10 from stored component measurements; no native fusion rerun or geometry-body audit.')
(ROOT/'AUDIT_DESIGN_RESULTS.json').write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8')
fields=sorted(set().union(*(r.keys() for r in pool_results)))
with (ROOT/'AUDIT_POOL_COUNTS.csv').open('w',encoding='utf-8-sig',newline='') as f:
    wr=csv.DictWriter(f,fieldnames=fields);wr.writeheader();wr.writerows(pool_results)
print(json.dumps(report,indent=2,ensure_ascii=False))
