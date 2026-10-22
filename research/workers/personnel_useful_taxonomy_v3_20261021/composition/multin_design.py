"""Result-independent complete conditional member panels for personnel v3.

Every selected panel enumerates every C(12,6) member set; classes are attached
after registration. Full-pool configuration coverage is a separate denominator.
"""
from __future__ import annotations
import argparse, collections, gzip, hashlib, itertools, json, math, sys
from pathlib import Path
import pandas as pd

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
OLD=ROOT/'research/workers/personnel_global_composition_20261021'
CONT=OLD/'continuation_20261021'
sys.path.insert(0,str(OLD/'composition'))
import global_study as gs

SEED='personnel-v3-label-blind-complete-panels-20261021'

def h(*x): return gs.digest([SEED,*x])
def write_csv(path,d):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_name(path.name+'.tmp')
    d.to_csv(tmp,index=False,encoding='utf-8-sig',compression={'method':'gzip','mtime':0} if str(path).endswith('.gz') else None)
    tmp.replace(path)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def existing_scalar_paths():
    return [OLD/'composition/TEAMS_SCALARS.csv.gz', *sorted((CONT/'next_stage/batches').glob('batch_*/ENDPOINT_SCALARS.csv.gz'))]

def freeze():
    pools=gs.pool_lookup()
    candidates=[p for p in pools.values() if p['meta']['layer'] in ('ordinary_manual','ordinary_semi') and len(p['records'])>=20]
    chosen=[]
    for building in sorted({p['meta']['building'] for p in candidates if p['meta']['condition']=='manual'}):
        b=[p for p in candidates if p['meta']['condition']=='manual' and p['meta']['building']==building]
        simple=[p for p in b if p['meta']['difficulty']=='简单']
        complex_=[p for p in b if p['meta']['difficulty']!='简单']
        if simple: chosen.append(min(simple,key=lambda p:h('image',p['pool_id'])))
        if complex_:
            # All harder images are eligible, but prefer hard where available.
            hard=[p for p in complex_ if p['meta']['difficulty']=='困难']
            chosen.append(min(hard or complex_,key=lambda p:h('image',p['pool_id'])))
    chosen.extend(p for p in candidates if p['meta']['condition']=='semi')
    chosen.sort(key=lambda p:(p['meta']['condition'],p['meta']['building'],p['pool_id']))
    cached={};sources=[]
    for path in existing_scalar_paths():
        d=pd.read_csv(path,usecols=['team_key','pool_id','k'])
        cached.update({r.team_key:str(path.relative_to(ROOT)) for r in d.itertuples()})
        sources.append(dict(path=str(path.relative_to(ROOT)),rows=len(d),sha256=sha(path)))
    historical=set(gzip.open(OLD/'composition/HISTORICAL_TEAM_KEYS.txt.gz','rt').read().splitlines())
    teams={};panels=[];memberships=[];coverage=[]
    for p in chosen:
        pid=p['pool_id'];meta=p['meta'];workers=sorted(r['worker_id'] for r in p['records']);N=len(workers);poolhash=gs.digest(p)
        order=sorted(workers,key=lambda w:h('active-order',pid,w));first_variable=set(order[:12])
        new_workers=sorted(r['worker_id'] for r in p['records'] if r['origin']=='new')
        for panel_no in (1,2):
            # Panel two targets a compatible recorded-time source when possible.
            # Source is a pre-outcome design stratum, not a quality selection.
            domain=workers if panel_no==1 or len(new_workers)<20 else new_workers
            source_domain='all_formal' if domain is workers else 'new_only'
            second_order=sorted(domain,key=lambda w:(w in first_variable,h('active-order',pid,w)))
            variable=sorted(order[:12] if panel_no==1 else second_order[:12]);left=[w for w in domain if w not in variable]
            background_order=sorted(left,key=lambda w:h('background-order',pid,panel_no,w))
            for b in sorted({6,min(14,len(left)),len(left)}):
                background=sorted(background_order[:b]);n=b+6
                panel_id=pid+f'__v{panel_no}__n{n}'
                panel=dict(pool_id=pid,image=meta['image'],building=meta['building'],condition=meta['condition'],
                    difficulty=meta['difficulty'],layer=meta['layer'],eligible_pool_n=N,
                    variable_panel_no=panel_no,panel_id=panel_id,n=n,source_domain=source_domain,domain_pool_n=len(domain),domain_workers='|'.join(domain),variable_n=12,selected_variable_n=6,
                    background_n=b,background_workers='|'.join(background),variable_workers='|'.join(variable),
                    possible_member_sets=math.comb(12,6),domain_member_sets=str(math.comb(len(domain),n)),full_pool_member_sets=str(math.comb(N,n)),
                    exhaustive_conditional_members=True,exhaustive_full_pool_members=False)
                panels.append(panel)
                keys=[]
                for ss in itertools.combinations(variable,6):
                    members=sorted(background+list(ss));key=gs.team_key(pid,members);keys.append(key)
                    if key not in teams:
                        teams[key]=dict(team_key=key,pool_id=pid,image=meta['image'],building=meta['building'],condition=meta['condition'],difficulty=meta['difficulty'],layer=meta['layer'],n=n,
                            member_workers='|'.join(members),cached=key in cached,cache_scalar_source=cached.get(key,''),historical_583261_set_overlap=key in historical,
                            first_variable_panel_no=panel_no,pool_input_sha256=poolhash)
                    memberships.append(dict(panel_id=panel_id,pool_id=pid,team_key=key,n=n,variable_panel_no=panel_no,selected_variable_workers='|'.join(ss)))
                coverage.append(dict(panel,registered_sets=len(keys),cached_sets=sum(k in cached for k in keys),
                    required_sets=sum(k not in cached for k in keys),potential_max_replaced_m=6,
                    all_ordered_sequences=str(math.comb(12,6)*math.factorial(n)),full_pool_ordered_sequences=str(math.perm(N,n))))
    d=pd.DataFrame(teams.values()).sort_values(['first_variable_panel_no','condition','pool_id','n','team_key'])
    write_csv(HERE/'DESIGN_TEAMS.csv.gz',d);write_csv(HERE/'PANELS.csv',pd.DataFrame(panels));write_csv(HERE/'PANEL_MEMBERSHIP.csv.gz',pd.DataFrame(memberships));write_csv(HERE/'PANEL_COVERAGE.csv',pd.DataFrame(coverage))
    write_csv(HERE/'SELECTED_POOLS.csv',pd.DataFrame([dict(p['meta'],pool_input_sha256=gs.digest(p)) for p in chosen]))
    batchrows=[];counter=0
    # Complete the first variable panel over all selected pools before second.
    for panel_no in (1,2):
        for condition in ('semi','manual'):
            dd=d[(d.first_variable_panel_no==panel_no)&(d.condition==condition)]
            # Group complete pools until about 20k distinct endpoints. No pool
            # is split, so each batch exports a complete readable panel unit.
            chunks=[];current=[];size=0
            for pid,g in dd.groupby('pool_id',sort=True):
                if current and size+len(g)>22000:chunks.append(pd.concat(current));current=[];size=0
                current.append(g);size+=len(g)
            if current:chunks.append(pd.concat(current))
            for sub in chunks:
                counter+=1;bid=f'batch_{counter:03d}';folder=HERE/'batches'/bid
                write_csv(folder/'REQUESTS.csv.gz',sub)
                batchrows.append(dict(batch_id=bid,variable_panel_no=panel_no,condition=condition,pools=sub.pool_id.nunique(),requested=len(sub),cached=int(sub.cached.sum()),required=int((~sub.cached).sum()),request_sha256=sha(folder/'REQUESTS.csv.gz')))
    write_csv(HERE/'BATCH_PLAN.csv',pd.DataFrame(batchrows))
    receipt=dict(source_main='324dba44d0a82d9d64a62965f2e549ee05165417',old_fusion_input_source_commit='51b519f943b2dd3a4fb2f0198133ac5dd17209ab',status='frozen_before_new_endpoint_evaluation',seed=SEED,design_revision='v2_pre_endpoint_time_source_amendment',
      selection='ordinary eligible pools N>=20; Manual easy and difficult image per building selected by frozen metadata/hash; Semi all such pools; classes and target scores never used. First variable panel uses full formal pool; second uses new-source-only pool when Nnew>=20, otherwise full pool. Variable members in second panel preferentially differ from first.',
      selected_pools=len(chosen),conditions=dict(pd.Series([p['meta']['condition'] for p in chosen]).value_counts()),
      selected_images=len({p['meta']['image'] for p in chosen}),selected_buildings=len({p['meta']['building'] for p in chosen}),panels=len(panels),membership_rows=len(memberships),
      unique_teams=len(d),cached_unique=int(d.cached.sum()),new_native_required=int((~d.cached).sum()),
      historical_missing_geometry=int(((~d.cached)&d.historical_583261_set_overlap).sum()),new_against_history=int(((~d.cached)&(~d.historical_583261_set_overlap)).sum()),
      members_per_configuration='All 924 conditional sets in each panel; resulting class-cell replication is not capped',
      added_orders='Not enumerated; deterministic equivalent endpoints calculated once. Registered nested background paths are analyzed separately.',
      limitation='Complete conditional panels are not a census of the whole pool. A full team singleton contributes no member-variation evidence.',
      scoring='Existing native B8L2/D10 and all components unchanged; failed outputs retained',source_endpoint_indices=sources,batches=batchrows,
      output_hashes={p.name:sha(p) for p in [HERE/'DESIGN_TEAMS.csv.gz',HERE/'PANELS.csv',HERE/'PANEL_MEMBERSHIP.csv.gz',HERE/'PANEL_COVERAGE.csv',HERE/'SELECTED_POOLS.csv',HERE/'BATCH_PLAN.csv',Path(__file__)]})
    gs.save(HERE/'DESIGN_FREEZE.json',receipt)
    print(json.dumps(gs.clean({k:v for k,v in receipt.items() if k not in ['source_endpoint_indices','batches','output_hashes']}),ensure_ascii=False,indent=2))
    print(pd.DataFrame(batchrows).to_string(index=False))

if __name__=='__main__': freeze()
