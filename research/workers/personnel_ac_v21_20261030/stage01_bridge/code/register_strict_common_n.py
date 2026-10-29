"""Direct-AC bridge at already registered strict-ABC n/m, without new ABC.

The bridge reads capacity/identity files and strict design cells only. It reuses
up to eight exact X/Z blocks from the final ordinary-Manual AC registration and
the same neutral-members-0 background prefix. No endpoint result is read.
"""
from pathlib import Path
from collections import Counter,defaultdict
import argparse,csv,gzip,hashlib,importlib.util,json,math,shutil,time
import pandas as pd

BASE=Path(__file__).resolve().parents[2]
OUT=Path(__file__).resolve().parents[1]
CAP=BASE/'stage01_capacity'
COMMIT='ec0973ad46fcfa64d3cdbedfeeef1fee180c4cff'
MAX_BLOCKS=8

def rows(path):
    opener=gzip.open if path.name.endswith('.gz') else open
    with opener(path,'rt',encoding='utf-8-sig',newline='') as stream:
        yield from csv.DictReader(stream)
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def write_json(x,path):path.write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def write_csv(records,path):
    records=list(records)
    if not records:return
    opener=gzip.open if path.name.endswith('.gz') else open
    with opener(path,'wt',encoding='utf-8-sig',newline='') as stream:
        w=csv.DictWriter(stream,fieldnames=list(records[0]));w.writeheader();w.writerows(records)

def main(args):
    started=time.monotonic();source=BASE/'stage01_design_review'/args.source_registration
    source_receipt=json.loads((source/'DESIGN_REGISTRATION_RECEIPT.json').read_text())
    frozen=json.loads((source/'FROZEN_DESIGN_FILES.json').read_text())
    for fn in ['AC_EVENTS.csv.gz','DESIGN_LINKS.csv.gz','TEAM_REQUESTS.csv.gz']:
        assert sha(source/fn)==frozen['requested_outputs'][fn]['sha256'],fn
    strict_source=BASE/'stage05_funnel_bridge/inputs/STRICT_LARGE_CELLS.csv'
    strict=list(rows(strict_source));assert len(strict)==66
    assert all(r['method'] in ['TARGET_DSTRUCT_K3','V21_DSTRUCT_RAW3_K3'] and int(r['m']) in [9,10] for r in strict)
    local_strict=OUT/'STRICT_SOURCE_CELLS.csv'
    if local_strict.exists():assert local_strict.read_bytes()==strict_source.read_bytes()
    else:shutil.copyfile(strict_source,local_strict)
    module_source=BASE/'stage01_design_review/code/register_ac_population.py'
    frozen_module=OUT/'code/source_registration_module_frozen.py'
    if frozen_module.exists():assert frozen_module.read_bytes()==module_source.read_bytes()
    else:shutil.copyfile(module_source,frozen_module)
    spec=importlib.util.spec_from_file_location('frozen_ac_population_registration',frozen_module)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    pools={p['pool_id']:p for p in json.loads((CAP/'SCORE_BLIND_POOL_INPUTS.json').read_text())['pools']}
    pm=pd.read_csv(CAP/'POOL_METHOD_CAPACITY.csv.gz')
    method_groups={(r['method'],r['pool_id']):json.loads(r['class_members_json']) for r in pm.to_dict('records')}
    role_df=pd.read_csv(CAP/'FROZEN_ROLE_PARENT_MAP_ALL_LOBO.csv').fillna('')
    roles={(r['method'],r['heldout_building'],r['class_id']):r for r in role_df.to_dict('records')}
    wanted={(r['method'],r['pool_id'],int(r['m']),tuple(sorted([r['source_class'],r['target_class']]))) for r in strict}
    eligible={}
    for e in rows(source/'AC_EVENTS.csv.gz'):
        if e['method'] not in ['TARGET_DSTRUCT_K3','V21_DSTRUCT_RAW3_K3'] or not e['m']:continue
        key=(e['method'],e['pool_id'],int(e['m']),tuple(sorted([e['source_class'],e['target_class']])))
        if key not in wanted or 'A_equal_AC' not in e['design_family'].split('|'):continue
        eligible[e['event_id']]=e
    blocks=defaultdict(dict)
    for l in rows(source/'DESIGN_LINKS.csv.gz'):
        if l['design_family']!='A_equal_AC' or l['event_id'] not in eligible:continue
        e=eligible[l['event_id']];assert int(l['input_orientation_sign'])==1
        key=(e['method'],e['pool_id'],int(e['m']),tuple(sorted([e['source_class'],e['target_class']])))
        b=dict(block_id=l['block_id'],X=e['X_workers'].split('|'),Z=e['Z_workers'].split('|'),
            source_class=e['source_class'],target_class=e['target_class'],source_member_rep=l['member_rep'],
            source_sample_batch=l['sample_batch'],source_event_id=l['event_id'])
        assert module.digest([e['pool_id'],b['X'],b['Z']])[:24]==b['block_id']
        prior=blocks[key].get(b['block_id'])
        if prior:assert prior['X']==b['X'] and prior['Z']==b['Z']
        else:blocks[key][b['block_id']]=b
    assert set(blocks)==wanted,(len(blocks),len(wanted))
    # Use the same retained block subset at both strict n levels. When an
    # original class pair was enumerated above eight blocks, select a seeded
    # subset rather than the first lexicographic combinations.
    chosen={}
    for key,available in blocks.items():
        values=sorted(available.values(),key=lambda b:b['block_id'])
        if len(values)>MAX_BLOCKS:
            values=module.rng('strict_common_n_bridge_subsample',list(key)).sample(values,MAX_BLOCKS)
        chosen[key]=sorted(values,key=lambda b:(int(b['source_member_rep']),b['block_id']))
    out=OUT/args.name;out.mkdir(exist_ok=False)
    reg=module.Registry(pools,pm,roles)
    reg.fields['omissions'].update(['pool_id','method','design_family','n_A','n_C','A_workers','C_workers','A_team_key','C_team_key','reason','link_metadata'])
    cells=[];selection=[]
    for strict_cell in strict:
        method,pid=strict_cell['method'],strict_cell['pool_id'];n,m=int(strict_cell['n']),int(strict_cell['m'])
        pool=pools[pid];N=len(pool['workers']);groups=method_groups[method,pid];lookup={w:c for c,ws in groups.items() for w in ws}
        assert pool['scope']=='primary' and pool['meta']['layer']=='ordinary_manual' and pool['meta']['building']==strict_cell['building']
        assert len(groups[strict_cell['source_class']])==int(strict_cell['source_capacity']) and len(groups[strict_cell['target_class']])==int(strict_cell['target_capacity'])
        assert N==int(strict_cell['pool_n']) and N>=n+m and n>=m>=1
        key=(method,pid,m,tuple(sorted([strict_cell['source_class'],strict_cell['target_class']])))
        selected=chosen[key];s,t=selected[0]['source_class'],selected[0]['target_class']
        cellid=module.digest([method,pid,s,t,n,m])[:24]
        strict_sign=1 if strict_cell['source_class']==s else -1
        possible_xz=math.comb(len(groups[s]),m)*math.comb(len(groups[t]),m)
        before=reg.link_n
        for i,b in enumerate(selected):
            x,z=b['X'],b['Z'];assert len(x)==len(z)==m and set(x)<=set(groups[s]) and set(z)<=set(groups[t])
            remain=sorted(set(pool['workers'])-set(x)-set(z))
            paths=module.background_paths(remain,lookup,s,t,[pid,x,z])
            d=sorted(paths['neutral_members_0'][:n-m]);assert len(d)==n-m
            reg.event(pool,method,groups,d+x,d+z,'F_strict_common_n_bridge',cell_id=cellid,n=n,m=m,
                block_id=b['block_id'],background_id=module.digest([pid,d])[:24],background_profile='neutral_members_0',
                member_rep=i,background_rep=0,sample_batch=b['source_sample_batch'],
                possible_XZ_blocks=str(possible_xz),sampled_XZ_blocks=len(selected),possible_D_per_XZ=str(math.comb(N-2*m,n-m)),
                nested_background_path_id=module.digest([pid,x,z,'neutral_members_0'])[:24],
                at_pool_frontier=n==N-m,zero_background=n==m,
                bridge_strict_source_class=strict_cell['source_class'],bridge_strict_target_class=strict_cell['target_class'],
                bridge_strict_to_canonical_sign=strict_sign,bridge_source_event_id=b['source_event_id'],
                bridge_source_member_rep=b['source_member_rep'],bridge_source_registration=args.source_registration,
                bridge_reason='same_pool_target_n_m_role_conditions_as_already_registered_strict_ABC_without_new_ABC')
            selection.append(dict(pool_id=pid,method=method,n=n,m=m,strict_source_class=strict_cell['source_class'],
                strict_target_class=strict_cell['target_class'],canonical_source_class=s,canonical_target_class=t,
                strict_to_canonical_sign=strict_sign,block_id=b['block_id'],X_workers='|'.join(x),Z_workers='|'.join(z),
                D_workers='|'.join(d),available_v2_XZ_blocks=len(blocks[key]),bridge_selected_XZ_blocks=len(selected),
                source_event_id=b['source_event_id'],source_member_rep=b['source_member_rep'],source_sample_batch=b['source_sample_batch']))
        cells.append(dict(pool_id=pid,method=method,source_class=s,target_class=t,n=n,m=m,
            design_families='F_strict_common_n_bridge',cell_id=cellid,possible_XZ_blocks=str(possible_xz),
            registered_XZ_blocks=len(selected),possible_D_per_XZ=str(math.comb(N-2*m,n-m)),
            registration_links=reg.link_n-before,at_pool_frontier=n==N-m,intensive_background_anchor=False,
            strict_source_class=strict_cell['source_class'],strict_target_class=strict_cell['target_class'],
            strict_to_canonical_sign=strict_sign))
    assert len(cells)==66 and not len({c['cell_id'] for c in cells})<66
    reg.finish(out)
    write_csv(cells,out/'REGISTERED_AC_CELLS.csv.gz');write_csv(selection,out/'BLOCK_SELECTION_AND_BRIDGE_REASONS.csv.gz')
    overlap=[dict(physical_pair_id=k,methods='|'.join(sorted(v)),method_count=len(v)) for k,v in reg.physical_methods.items()]
    write_csv(overlap,out/'PHYSICAL_PAIR_METHOD_OVERLAP.csv.gz')
    existing_teams={t['team_key'] for t in rows(source/'TEAM_REQUESTS.csv.gz') if t['team_key'] in reg.teams}
    bridge_event_ids=set(reg.events);existing_events=set()
    for e in rows(source/'AC_EVENTS.csv.gz'):
        if e['event_id'] in bridge_event_ids:existing_events.add(e['event_id'])
    receipt=dict(source_commit=COMMIT,seed=module.SEED,design_status='registered_before_bridge_outcomes_not_executed',
        source_registration=args.source_registration,methods=sorted(reg.method_counts),method_events=len(reg.events),
        physical_pairs=len(reg.physical_methods),unique_teams=len(reg.teams),design_links=reg.link_n,registered_A_B_cells=len(cells),
        pools=len(reg.event_pools),by_scope=dict(reg.scope_counts),by_method=dict(reg.method_counts),family_links=dict(reg.counts),
        strict_registered_cells=66,max_XZ_blocks_per_cell=MAX_BLOCKS,XZ_subsample_rng_token='strict_common_n_bridge_subsample',
        same_selected_XZ_at_all_strict_n=True,same_v2_neutral_background_prefix=True,
        existing_v2_team_requests=len(existing_teams),team_requests_not_in_v2=len(reg.teams-existing_teams),
        existing_v2_method_events=len(existing_events),method_events_not_in_v2=len(bridge_event_ids-existing_events),
        no_B_or_strict_ABC_registered=True,target_image_quality_time_and_geometry_read=False,
        exact_strict_endpoints_are_not_assumed=True,strict_source_direction_retained_in_links=True,
        reason='Add only existing strict registered n at existing direct-AC XZ blocks so comparisons share pool, target, n, m and role direction.',
        source_registration_module_sha256=sha(frozen_module),
        outcome_blind_inputs=[dict(path=str(p.relative_to(BASE)),sha256=sha(p)) for p in [strict_source,CAP/'SCORE_BLIND_POOL_INPUTS.json',CAP/'POOL_METHOD_CAPACITY.csv.gz',CAP/'FROZEN_ROLE_PARENT_MAP_ALL_LOBO.csv',source/'AC_EVENTS.csv.gz',source/'DESIGN_LINKS.csv.gz',source/'TEAM_REQUESTS.csv.gz']],
        elapsed_seconds=time.monotonic()-started)
    write_json(receipt,out/'DESIGN_REGISTRATION_RECEIPT.json')
    checks=[]
    for p in sorted(out.glob('*.gz')):
        count=sum(1 for _ in rows(p));checks.append(dict(file=p.name,rows=count,sha256=sha(p)))
    write_json({'all_gzip_csv_fully_read':True,'files':checks},out/'READABILITY_RECEIPT.json')
    write_json({'requested_outputs':{p.name:{'bytes':p.stat().st_size,'sha256':sha(p)} for p in out.iterdir() if p.is_file()}},out/'FROZEN_DESIGN_FILES.json')
    print(json.dumps(receipt,ensure_ascii=False,indent=2),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source-registration',default='registered_v2');p.add_argument('--name',default='registered_bridge_v1');main(p.parse_args())
