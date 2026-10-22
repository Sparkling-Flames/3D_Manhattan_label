"""Exact de-duplicated configuration/member coverage across expansion cells.

This is a metadata/request-only calculation. A cell is a direction/n/m; the
canonical unit is actual known-worker domain + taxonomy/tier + n + class vector.
Counts preserve arbitrary-size integers as decimal strings. No fusion is run.
"""
from __future__ import annotations
import os
for k in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS']:os.environ[k]='1'
from pathlib import Path
import collections,json,math,sys,time
import pandas as pd
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from analyze_expanded_results import EX,save_csv,save_json,digest,sha
REPO=EX.parents[3]

def vector(value):
    d={c:int(n) for c,n in (v.rsplit(':',1) for v in str(value).split('|'))}
    return '|'.join(f'{c}:{n}' for c,n in sorted(d.items()) if n)

def main():
    started=time.time()
    cells=pd.read_csv(EX/'REGISTERED_EVENT_PARTS.csv',keep_default_na=False)
    panels=pd.read_csv(EX/'REGISTERED_MEMBER_PANELS.csv.gz',keep_default_na=False)
    config=pd.read_csv(EX/'CLASS_CONFIG_MEMBER_COVERAGE.csv.gz',dtype=str,keep_default_na=False)
    meta={}
    for cell,g in panels.groupby('cell_id'):
        assert g[['pool_id','method_id','tier','condition','n','N','unknown_workers']].drop_duplicates().shape[0]==1
        r=g.iloc[0].to_dict()
        excluded='|'.join(sorted(w for w in r['unknown_workers'].split('|') if w))
        # The frozen pool identifies the exact eligible worker universe;
        # excluding this exact set identifies the actual known-worker domain.
        domain=digest([r['pool_id'],excluded])[:24]
        meta[cell]={k:r[k] for k in ['pool_id','method_id','tier','condition','n','N','layer','image','building']}
        meta[cell].update(domain_id=domain,unknown_workers=excluded,source_domain='all_formal_label_known')
    rows={};lookup={}
    for r in config.to_dict('records'):
        m=meta[r['cell_id']];vec=vector(r['class_counts'])
        key=(m['domain_id'],m['method_id'],m['tier'],int(m['n']),vec)
        cid=digest(list(key))[:24]
        if cid not in rows:
            rows[cid]=dict(m,canonical_configuration_id=cid,class_counts=vec,
                possible_member_sets=int(r['possible_member_sets']),cells=set(),m_values=set(),teams=set())
        dest=rows[cid]
        assert dest['possible_member_sets']==int(r['possible_member_sets']),(cid,'changed_theoretical_capacity')
        assert dest['N']==m['N'] and dest['unknown_workers']==m['unknown_workers']
        dest['cells'].add(r['cell_id']);dest['m_values'].add(int(r['m']))
        lookup[(r['cell_id'],vec)]=cid
    for j,part in enumerate(cells.to_dict('records')):
        r=pd.read_csv(REPO/part['path'],usecols=['team_A','team_B','team_C','A_counts','B_counts','C_counts'],dtype=str)
        assert len(r)==int(part['events'])
        for arm in 'ABC':
            for vec,g in r.groupby(arm+'_counts'):
                cid=lookup[(part['cell_id'],vector(vec))]
                rows[cid]['teams'].update(g['team_'+arm])
        if (j+1)%50==0:
            save_json('CANONICAL_COVERAGE_PROGRESS.json',dict(completed_cells=j+1,registered_cells=len(cells),native_calls=0))
    output=[];teamindex=[]
    for cid,r in sorted(rows.items()):
        teams=sorted(r.pop('teams'));cellids=sorted(r.pop('cells'));ms=sorted(r.pop('m_values'))
        possible=r.pop('possible_member_sets');assert len(teams)<=possible
        r.update(possible_member_sets=str(possible),registered_member_sets=len(teams),missing_member_sets=str(possible-len(teams)),
          configuration_covered=bool(teams),all_members_covered=len(teams)==possible,
          originating_cell_ids='|'.join(cellids),originating_cells=len(cellids),actual_m_values='|'.join(map(str,ms)),
          registered_member_key_sha256=digest(teams))
        output.append(r)
        teamindex.extend(dict(canonical_configuration_id=cid,domain_id=r['domain_id'],team_key=t) for t in teams)
    table=pd.DataFrame(output);keys=pd.DataFrame(teamindex)
    assert not keys.duplicated(['canonical_configuration_id','team_key']).any()
    all_requested=set(pd.read_csv(EX/'ALL_TEAMS_REGISTERED.csv.gz',usecols=['team_key']).team_key)
    assert set(keys.team_key)==all_requested
    files=[save_csv('CANONICAL_CONFIGURATION_MEMBER_COVERAGE.csv.gz',table),
           save_csv('CANONICAL_CONFIGURATION_TEAM_INDEX.csv.gz',keys)]
    domains=[]
    for key,g in table.groupby(['domain_id','method_id','tier','n']):
        member=set(keys.loc[keys.canonical_configuration_id.isin(g.canonical_configuration_id),'team_key'])
        assert sum(g.registered_member_sets)==len(member),'vectors in a fixed taxonomy/domain/n must partition teams'
        eligible=math.comb(int(g.N.iloc[0]),int(key[3]))
        condition_union=sum(int(v) for v in g.possible_member_sets)
        assert condition_union<=eligible
        r=g.iloc[0]
        domains.append(dict(domain_id=key[0],method_id=key[1],tier=key[2],n=int(key[3]),pool_id=r.pool_id,
          image=r.image,building=r.building,condition=r.condition,layer=r.layer,known_domain_n=int(r.N),
          feasible_configurations_in_registered_condition_union=len(g),covered_configurations=int(g.configuration_covered.sum()),
          all_members_complete_configurations=int(g.all_members_covered.sum()),
          possible_members_in_registered_condition_union=str(condition_union),
          registered_unique_member_sets=len(member),missing_members_in_registered_condition_union=str(condition_union-len(member)),
          all_known_domain_n_member_sets=str(eligible),uncovered_all_known_domain_n_member_sets=str(eligible-len(member)),
          actual_m_values='|'.join(sorted(set('|'.join(g.actual_m_values).split('|')),key=int))))
    domain=pd.DataFrame(domains);files.append(save_csv('CANONICAL_DOMAIN_N_COVERAGE.csv',domain))
    summary=[]
    for group,g in domain.groupby(['condition','layer','method_id','tier','n']):
        theory=sum(int(v) for v in g.possible_members_in_registered_condition_union)
        eligible=sum(int(v) for v in g.all_known_domain_n_member_sets)
        got=int(g.registered_unique_member_sets.sum())
        summary.append(dict(zip(['condition','layer','method_id','tier','n'],group),
          actual_worker_domains=g.domain_id.nunique(),images=g.image.nunique(),buildings=g.building.nunique(),
          feasible_configurations_in_registered_condition_union=int(g.feasible_configurations_in_registered_condition_union.sum()),
          covered_configurations=int(g.covered_configurations.sum()),
          all_members_complete_configurations=int(g.all_members_complete_configurations.sum()),
          possible_members_in_registered_condition_union=str(theory),registered_unique_member_sets=got,
          missing_members_in_registered_condition_union=str(theory-got),
          all_known_domain_n_member_sets=str(eligible),uncovered_all_known_domain_n_member_sets=str(eligible-got)))
    files.append(save_csv('CANONICAL_COVERAGE_SUMMARY.csv',pd.DataFrame(summary)))
    result=dict(status='complete',underlying_data_version='v2',registered_cells=len(cells),
      summed_cell_configurations=len(config),canonical_configurations=len(table),
      covered_canonical_configurations=int(table.configuration_covered.sum()),
      unique_requested_endpoints=len(all_requested),taxonomy_domain_team_associations=len(keys),
      native_calls=0,scoring_calls=0,seconds=time.time()-started,files=files,
      input_class_configuration_sha256=sha(EX/'CLASS_CONFIG_MEMBER_COVERAGE.csv.gz'),
      input_registration_sha256=sha(EX/'REGISTERED_EVENT_PARTS.csv'),
      domain_identity='frozen eligible pool_id plus exact unknown/excluded worker set; method/tier retained for label semantics',
      canonical_unit='actual domain + method + tier + n + nonzero class-count vector; n10 m5/m6 and repeated directions merged',
      condition_union='only vectors compatible with at least one registered directional n/m condition; not all conceivable vectors at n',
      cross_taxonomy_counts='method-specific counts are not summed as globally unique concrete teams; global unique requests separately asserted')
    save_json('CANONICAL_COVERAGE_COMPLETION.json',result)
    print(json.dumps({k:v for k,v in result.items() if k!='files'},ensure_ascii=False))

if __name__=='__main__':main()
