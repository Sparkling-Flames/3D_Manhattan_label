"""Verify exact design -> scalars -> full state -> events using CLOSED ZIPs.

The geometry is streamed from the actual delivered ZIPs. No source-directory
file is substituted for a packaged file. Counts derive from the saved design,
not from the old missing experiment or a report's numerical claims.
"""
from __future__ import annotations
import argparse,csv,gzip,hashlib,io,json,math,sys,zipfile
from pathlib import Path
csv.field_size_limit(sys.maxsize)
PREFIX='research/same_room/same_room_large_block_rebuilt_20261023/'

def table(z,name):
    with z.open(name) as raw:
        stream=gzip.GzipFile(fileobj=raw) if name.endswith('.gz') else raw
        with io.TextIOWrapper(stream,encoding='utf-8-sig',newline='') as text:
            yield from csv.DictReader(text)

def people(x):
    return tuple(sorted(v for v in x.split('|') if v))

def boolean(x):
    return str(x).lower() in {'true','1'}

def number(x):
    return None if str(x).strip().lower() in {'','nan','none','null'} else float(x)

def same_number(a,b):
    return (a is None and b is None) or (a is not None and b is not None and math.isclose(a,b,rel_tol=0,abs_tol=1e-10))

def digest(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for b in iter(lambda:f.read(2**20),b''):h.update(b)
    return h.hexdigest()

def main(config):
    c=json.loads(Path(config).read_text())
    req={};events={};scalars={};scalar_q={};geom_seen=set();archives=[]
    with zipfile.ZipFile(c['design_archive']) as z:
        for r in table(z,PREFIX+'design/ENDPOINT_REQUESTS.csv.gz'):
            k=r['team_key'];assert k not in req,k
            req[k]=(r['pool_id'],people(r['member_workers']),people(r['member_object_ids']),int(r['n']))
        for r in table(z,PREFIX+'design/STRICT_ABC_EVENTS.csv.gz'):
            eid=r['event_id'];assert eid not in events,eid
            blocks=[set(people(r[k+'_members'])) for k in ['D','X','Y','Z']]
            d,x,y,zz=blocks;m=int(r['m']);n=int(r['n'])
            assert len(x)==len(y)==len(zz)==m and len(d)+m==n
            assert sum(map(len,blocks))==len(set.union(*blocks))
            keys=[]
            for view in ['a','b']:
                for role,block in [('A',x),('B',y),('C',zz)]:
                    k=r[f'team_{role}_{view}'];keys.append(k)
                    assert k in req and req[k][0]==r['pool_id_'+view]
                    assert req[k][1]==tuple(sorted(d|block)) and req[k][3]==n
            events[eid]=tuple(keys)
    for archive in c['scalar_archives']:
        with zipfile.ZipFile(archive) as z:
            names=[n for n in z.namelist() if '/native_endpoints/ENDPOINT_SCALARS' in n and n.endswith('.csv.gz')]
            assert names,archive
            for name in names:
                for r in table(z,name):
                    k=r['team_key'];assert k in req and k not in scalars,k
                    assert (r['pool_id'],people(r['member_workers']),people(r['member_object_ids']),int(r['k']))==req[k]
                    scalars[k]=(r['geometry_shard'],int(r['geometry_line_1based']),
                                r['score_status'],boolean(r['complete_evaluable']),boolean(r['score_available']))
                    scalar_q[k]=number(r['B8L2'])
    assert set(scalars)==set(req)
    geometry_parts=[]
    for archive in c['geometry_archives']:
        count=0;shards=0
        with zipfile.ZipFile(archive) as z:
            for name in z.namelist():
                if not name.endswith('.geometry_state.jsonl.gz'):continue
                shards+=1;rel=name.split('/native_endpoints/',1)[1]
                with z.open(name) as raw,gzip.GzipFile(fileobj=raw) as gz,io.TextIOWrapper(gz,encoding='utf-8') as text:
                    for line_i,line in enumerate(text,1):
                        r=json.loads(line);k=r['team_key']
                        assert k in scalars and k not in geom_seen,k
                        assert r['geometry_shard']==rel and r['geometry_line_1based']==line_i
                        assert scalars[k]==(rel,line_i,r['score_status'],bool(r['complete_evaluable']),bool(r['score_available']))
                        assert req[k]==(r['pool_id'],tuple(sorted(r['member_workers'])),tuple(sorted(r['member_object_ids'])),int(r['k']))
                        assert 'full_state' in r and 'geometry' in r
                        geom_seen.add(k);count+=1
        geometry_parts.append({'archive':str(archive),'shards':shards,'states':count})
        print('Verified geometry',Path(archive).name,count,flush=True)
    assert geom_seen==set(req)
    result_events=set();comparisons=set();max_q_difference=0.0
    with zipfile.ZipFile(c['event_archive']) as z:
        for r in table(z,PREFIX+'results/EVENT_Q_STRUCTURE_EFFECTS.csv.gz'):
            eid=r['event_id'];assert eid in events and eid not in result_events
            keys=tuple(r[f'team_{role}_{view}'] for view in ['a','b'] for role in ['A','B','C'])
            assert keys==events[eid];result_events.add(eid)
            for view_i,view in enumerate(['a','b']):
                for role_i,role in enumerate(['A','B','C']):
                    team=keys[view_i*3+role_i]
                    value=number(r[f'Q_{role}_{view}'])
                    assert same_number(value,scalar_q[team]),(eid,team,'Q')
                    if value is not None:max_q_difference=max(max_q_difference,abs(value-scalar_q[team]))
                    assert boolean(r[f'complete_{role}_{view}'])==scalars[team][3],(eid,team,'complete')
            assert boolean(r['Q_common6'])==all(scalar_q[k] is not None for k in keys)
            assert boolean(r['complete6'])==all(scalars[k][3] for k in keys)
        for r in table(z,PREFIX+'geometry/EVENT_GEOMETRY_RESULTS.csv.gz'):
            k=(r['event_id'],r['view'],r['comparison'])
            assert k[0] in events and k[1] in ['a','b'] and k[2] in ['AB','AC','BC']
            assert k not in comparisons;comparisons.add(k)
            offset=0 if k[1]=='a' else 3
            left,right=[events[k[0]][offset+'ABC'.index(arm)] for arm in k[2]]
            assert (r['team_key_from'],r['team_key_to'])==(left,right),k
            assert r['pool_id']==req[left][0]==req[right][0],k
            for side,team in [('from',left),('to',right)]:
                pointer=scalars[team][0]+'#L'+str(scalars[team][1])
                assert r['geometry_state_pointer_'+side]==pointer,(k,side)
    assert result_events==set(events) and len(comparisons)==6*len(events)
    for archive in [c['design_archive'],*c['scalar_archives'],c['event_archive'],*c['geometry_archives']]:
        archives.append({'path':str(archive),'bytes':Path(archive).stat().st_size,'sha256':digest(archive)})
    receipt={'verified':True,'verification_source':'actual closed delivery ZIPs, all relevant CSV/gzip/JSONL read through EOF',
        'exact_abc_events':len(events),'unique_requests':len(req),'complete_scalar_rows':len(scalars),
        'full_geometry_states':len(geom_seen),'event_result_rows':len(result_events),'event_geometry_comparisons':len(comparisons),
        'all_strict_blocks_and_six_team_members_match':True,'all_object_ids_pool_ids_and_geometry_pointers_match':True,
        'all_endpoint_statuses_match_packaged_full_states':True,'no_duplicate_geometry_states':True,
        'all_event_arm_q_and_completeness_match_packaged_scalars':True,
        'event_arm_q_max_absolute_csv_roundtrip_difference':max_q_difference,
        'all_event_geometry_arm_keys_pools_and_pointers_match':True,
        'geometry_parts':geometry_parts,'archives':archives}
    Path(c['output']).write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v for k,v in receipt.items() if k not in ['geometry_parts','archives']},ensure_ascii=False),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('config');a=p.parse_args();main(a.config)
