"""Canonical union of main and supplement class-configuration universes.

The key uses the method, tier, exact target pool, n and actual known worker
domain, not a source-domain nickname.  Set coverage is recomputed from keys;
counts from overlapping reports are never added.  Distinct worker domains can
still overlap, so domain denominators are not a global member-set total.
"""
from __future__ import annotations
import collections,json,math
import pandas as pd
from multin_design import HERE,gs,h,sha,write_csv,existing_scalar_paths
from design_matched_events import label_maps
from enumerate_class_configurations import vectors,counter_string
from consolidate_deliverables import GzipCsv
from supplement_configuration_census import STAGE_TEAMS

def run():
    out=HERE/'configuration_union';out.mkdir(exist_ok=True)
    maps,_=label_maps();panels=pd.read_csv(HERE/'PANELS.csv',keep_default_na=False)
    main_domains={(r.pool_id,r.source_domain):r.domain_workers.split('|') for r in panels.itertuples()}
    contexts={};aliases=[];universe=set();raw_main=raw_supplement=0
    def add(stage,r,workers):
        mapping,_=maps[(r['method_id'],r['tier'],r['condition'],r['building'])]
        workers=tuple(sorted(w for w in workers if w in mapping));universe.update(workers)
        key=(r['method_id'],r['tier'],r['pool_id'],int(r['n']),workers)
        did=h('canonical-personnel-domain',key)[:24]
        if did not in contexts:
            contexts[did]=dict(domain_id=did,method_id=r['method_id'],tier=r['tier'],pool_id=r['pool_id'],
              image=r['image'],building=r['building'],condition=r['condition'],difficulty=r['difficulty'],
              n=int(r['n']),workers=workers,mapping=mapping,aliases=set(),stages=set())
        contexts[did]['aliases'].add((stage,r['source_domain']));contexts[did]['stages'].add(stage)
        aliases.append(dict(canonical_domain_id=did,stage=stage,source_domain=r['source_domain'],
          method_id=r['method_id'],tier=r['tier'],pool_id=r['pool_id'],n=int(r['n']),known_domain_n=len(workers),
          known_domain_workers='|'.join(workers),feasible_configurations=int(r['feasible_known_configurations'] if stage=='MAIN' else r['feasible_class_configurations'])))
    for r in pd.read_csv(HERE/'configuration/DOMAIN_COVERAGE.csv',keep_default_na=False).to_dict('records'):
        add('MAIN',r,main_domains[(r['pool_id'],r['source_domain'])]);raw_main+=int(r['feasible_known_configurations'])
    for r in pd.read_csv(HERE/'configuration_supplement/SUPPLEMENT_DOMAIN_COVERAGE.csv',keep_default_na=False).to_dict('records'):
        add(r['stage'],r,r['domain_workers'].split('|'));raw_supplement+=int(r['feasible_class_configurations'])
    write_csv(out/'DOMAIN_ALIAS_MAP.csv.gz',pd.DataFrame(aliases))
    workers={w:i for i,w in enumerate(sorted(universe))}
    def mask(ws):
        ans=0
        for w in ws:
            if w not in workers:return None
            ans|=1<<workers[w]
        return ans
    wanted={(r['pool_id'],r['n']) for r in contexts.values()};teams=collections.defaultdict(dict)
    for path in existing_scalar_paths():
        for d in pd.read_csv(path,usecols=['team_key','pool_id','k','member_workers'],chunksize=40000):
            d=d[[pair in wanted for pair in zip(d.pool_id,d.k)]]
            for r in d.itertuples():
                mm=mask(r.member_workers.split('|'))
                if mm is None:continue
                key=(r.pool_id,int(r.k));old=teams[key].get(r.team_key)
                if old and old[0]!=mm:raise ValueError('cached set key conflict')
                teams[key][r.team_key]=(mm,True,old[2] if old else 0)
    stage_bit={stage:1<<i for i,stage in enumerate(STAGE_TEAMS)}
    all_v3_keys=set()
    for stage,path in STAGE_TEAMS.items():
        for d in pd.read_csv(HERE/path,usecols=['team_key','pool_id','n','member_workers'],chunksize=40000):
            for r in d.itertuples():
                all_v3_keys.add(r.team_key)
                if (r.pool_id,int(r.n)) not in wanted:continue
                mm=mask(r.member_workers.split('|'))
                if mm is None:continue
                key=(r.pool_id,int(r.n));old=teams[key].get(r.team_key)
                if old and old[0]!=mm:raise ValueError('registered set key conflict')
                teams[key][r.team_key]=(mm,old[1] if old else False,(old[2] if old else 0)|stage_bit[stage])
    meta_fields=['canonical_domain_id','method_id','tier','pool_id','image','building','condition','difficulty',
      'n','known_domain_n','known_domain_workers','stage_identities','domain_aliases']
    count_fields=['old_cached_members','MAIN_registered_members','LARGE_registered_members',
      'PURE_registered_members','F01_registered_members','any_v3_registered_members','cached_or_registered_members']
    fields=['canonical_configuration_id']+meta_fields+['class_counts','class_capacity','theoretical_members']+count_fields+[
      'uncovered_members','member_variation_available_in_v3','complete_member_census_after_requests']
    path=out/'ALL_CANONICAL_CONFIGURATIONS.csv.gz';writer=GzipCsv(path,fields,key='canonical_configuration_id')
    row_keys=set();domain_rows=[];main_canonical=supp_canonical=intersection=0
    # A diagnostic method union removes nested worker domains before summing
    # their member populations; it is separate from the table's domain census.
    for did,r in sorted(contexts.items()):
        ww=r['workers'];mapping=r['mapping'];classes=sorted({mapping[w] for w in ww});dm=mask(ww)
        cms=[mask([w for w in ww if mapping[w]==c]) for c in classes];cap=[v.bit_count() for v in cms]
        observed=collections.defaultdict(lambda:[0]*7)
        for key,(mm,old,stages) in teams[(r['pool_id'],r['n'])].items():
            if mm&~dm:continue
            cc=tuple((mm&cm).bit_count() for cm in cms);z=observed[cc]
            z[0]+=old
            for j,stage in enumerate(['MAIN','LARGE','PURE','F01'],1):z[j]+=bool(stages&stage_bit[stage])
            z[5]+=bool(stages);z[6]+=1
        meta={k:r[k] for k in ['method_id','tier','pool_id','image','building','condition','difficulty','n']}
        meta.update(canonical_domain_id=did,known_domain_n=len(ww),known_domain_workers='|'.join(ww),
          stage_identities='|'.join(sorted(r['stages'])),domain_aliases=json.dumps(sorted(r['aliases']),ensure_ascii=False,separators=(',',':')))
        configs=theoretical_total=0;totals=[0]*7;covered_cfg=0;v3_cfg=0
        for cc in vectors(cap,r['n']):
            total=math.prod(math.comb(c,k) for c,k in zip(cap,cc));values=observed.get(cc,[0]*7)
            if values[6]>total:raise ValueError('canonical set union exceeds configuration universe')
            cid=h('canonical-personnel-configuration',did,cc)[:24];row_keys.add(cid)
            writer.add(dict(meta,canonical_configuration_id=cid,class_counts=counter_string(classes,cc),
              class_capacity=counter_string(classes,cap),theoretical_members=str(total),
              **dict(zip(count_fields,values)),uncovered_members=str(total-values[6]),
              member_variation_available_in_v3=values[5]>1,complete_member_census_after_requests=values[6]==total))
            configs+=1;theoretical_total+=total;totals=[a+b for a,b in zip(totals,values)]
            covered_cfg+=values[6]>0;v3_cfg+=values[5]>0
        expected=math.comb(len(ww),r['n'])
        if theoretical_total!=expected:raise ValueError('canonical Vandermonde mismatch')
        has_main='MAIN' in r['stages'];has_supp=bool(r['stages']-{'MAIN'})
        main_canonical+=configs*has_main;supp_canonical+=configs*has_supp;intersection+=configs*(has_main and has_supp)
        domain_rows.append(dict(meta,feasible_configurations=configs,full_member_universe=str(expected),
          **dict(zip(count_fields,totals)),uncovered_members=str(expected-totals[6]),
          configurations_reached_by_cache_or_requests=covered_cfg,configurations_reached_by_v3=v3_cfg,
          complete_member_census_after_requests=totals[6]==expected and expected>0,
          singleton_member_space=expected==1,empty_feasible_space=expected==0))
    if len(row_keys)!=main_canonical+supp_canonical-intersection:raise ValueError('canonical union arithmetic mismatch')
    receipt=writer.finish(row_keys);write_csv(out/'CANONICAL_DOMAIN_COVERAGE.csv.gz',pd.DataFrame(domain_rows))
    agg=pd.DataFrame(domain_rows).groupby(['method_id','tier','condition'],as_index=False).agg(
       canonical_domains=('canonical_domain_id','size'),pools=('pool_id','nunique'),buildings=('building','nunique'),
       feasible_configurations=('feasible_configurations','sum'),
       configurations_reached_by_v3=('configurations_reached_by_v3','sum'),
       configurations_reached_by_cache_or_requests=('configurations_reached_by_cache_or_requests','sum'),
       empty_feasible_domains=('empty_feasible_space','sum'),complete_member_domains=('complete_member_census_after_requests','sum'))
    write_csv(out/'CANONICAL_METHOD_COVERAGE.csv',agg)
    final=dict(status='complete_registered_space',raw_main_configurations=raw_main,
      raw_supplement_configurations=raw_supplement,canonical_main_configurations=main_canonical,
      canonical_supplement_configurations=supp_canonical,canonical_main_supplement_intersection=intersection,
      canonical_union_configurations=len(row_keys),raw_domain_alias_records=len(aliases),
      canonical_domains=len(contexts),global_unique_v3_registered_team_keys=len(all_v3_keys),
      canonical_key_fields=['method_id','tier','pool_id','n','actual_known_workers'],
      aliases_deduplicated=True,all_counts_recomputed_from_actual_set_key_union=True,
      theoretical_big_integers_decimal_strings=True,all_vandermonde_checks=True,
      domain_universes_can_still_overlap=True,native_calls=0,files=[receipt]+[
       dict(path=str((out/f).relative_to(HERE)),bytes=(out/f).stat().st_size,sha256=sha(out/f))
       for f in ['DOMAIN_ALIAS_MAP.csv.gz','CANONICAL_DOMAIN_COVERAGE.csv.gz','CANONICAL_METHOD_COVERAGE.csv']])
    gs.save(out/'COMPLETION.json',final);print(json.dumps(final,ensure_ascii=False),flush=True)

if __name__=='__main__':run()
