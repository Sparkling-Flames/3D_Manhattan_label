"""All feasible count vectors at newly registered large/pure/F01 n values.

This is exact combinatorial accounting, separate from event sampling.  Every
old cached and v3 registered member set is matched by canonical set key and
worker bitmask.  The four study identities are preserved and overlap counts
are explicit; their universes must not be summed as independent people/teams.
"""
from __future__ import annotations
import collections,json,math
import pandas as pd
from multin_design import HERE,gs,h,sha,write_csv,existing_scalar_paths
from design_matched_events import label_maps
from enumerate_class_configurations import vectors,counter_string
from consolidate_deliverables import GzipCsv

STAGE_TEAMS={'MAIN':'DESIGN_TEAMS.csv.gz','LARGE':'LARGE_BLOCK_TEAMS.csv.gz',
             'PURE':'PURE_BLOCK_TEAMS.csv.gz','F01':'F01_CAPACITY_TEAMS.csv.gz'}

def run():
    out=HERE/'configuration_supplement';out.mkdir(exist_ok=True)
    labels,sources=label_maps();panels=pd.read_csv(HERE/'PANELS.csv',keep_default_na=False)
    domains={(r.pool_id,r.source_domain):r.domain_workers.split('|') for r in panels.itertuples()}
    contexts={};universe=set()
    def add(stage,r,workers):
        key=(stage,r['pool_id'],r['source_domain'],r['method_id'],r['tier'],int(r['n']))
        workers=tuple(sorted(workers));universe.update(workers)
        if key in contexts:
            if contexts[key]['domain_workers']!=workers:raise ValueError('inconsistent registered source domain')
            return
        mapping,_=labels[(r['method_id'],r['tier'],r['condition'],r['building'])]
        known=tuple(w for w in workers if w in mapping)
        if known!=workers:raise ValueError('supplement contexts must have explicit wholly known domains')
        meta={k:r[k] for k in ['pool_id','image','building','condition','difficulty','source_domain','method_id','tier']}
        meta.update(stage=stage,n=int(r['n']),domain_workers=workers,classes=sorted({mapping[w] for w in workers}),mapping=mapping)
        contexts[key]=meta
    for r in pd.read_csv(HERE/'matched/LARGE_BLOCK_EVENTS.csv.gz',keep_default_na=False).to_dict('records'):
        add('LARGE',r,domains[(r['pool_id'],r['source_domain'])])
    for filename in ['PURE_BLOCK_MATCHED_EVENTS.csv.gz','PURE_BLOCK_CROSS_ONLY_EVENTS.csv.gz']:
        for r in pd.read_csv(HERE/'matched'/filename,keep_default_na=False).to_dict('records'):
            add('PURE',r,r['labelled_domain_workers'].split('|'))
    for r in pd.read_csv(HERE/'F01_PANELS.csv',keep_default_na=False).to_dict('records'):
        r.update(method_id='F01',tier='coarse');add('F01',r,r['domain_workers'].split('|'))
    # Bitmasks make domain membership/counting exact without a huge object
    # dataframe or redundant frozensets per team.
    worker_index={w:i for i,w in enumerate(sorted(universe))}
    def mask(ws):
        value=0
        for w in ws:
            if w not in worker_index:return None
            value|=1<<worker_index[w]
        return value
    wanted={(r['pool_id'],r['n']) for r in contexts.values()}
    teams=collections.defaultdict(dict);prior_rows=0
    # Value is (member mask, old exact-cache flag, registered-stage bitmask).
    for path in existing_scalar_paths():
        for d in pd.read_csv(path,usecols=['team_key','pool_id','k','member_workers'],chunksize=40000):
            d=d[[pair in wanted for pair in zip(d.pool_id,d.k)]]
            for r in d.itertuples():
                mm=mask(r.member_workers.split('|'))
                if mm is None:continue
                key=(r.pool_id,int(r.k));old=teams[key].get(r.team_key)
                if old and old[0]!=mm:raise ValueError('same key different cached workers')
                teams[key][r.team_key]=(mm,True,old[2] if old else 0);prior_rows+=1
    stage_bit={s:1<<i for i,s in enumerate(STAGE_TEAMS)}
    for stage,path in STAGE_TEAMS.items():
        for d in pd.read_csv(HERE/path,usecols=['team_key','pool_id','n','member_workers'],chunksize=40000):
            d=d[[pair in wanted for pair in zip(d.pool_id,d.n)]]
            for r in d.itertuples():
                mm=mask(r.member_workers.split('|'))
                if mm is None:continue
                key=(r.pool_id,int(r.n));old=teams[key].get(r.team_key)
                if old and old[0]!=mm:raise ValueError('same key different registered workers')
                teams[key][r.team_key]=(mm,old[1] if old else False,(old[2] if old else 0)|stage_bit[stage])
    fields=['configuration_id','stage','pool_id','image','building','condition','difficulty','source_domain',
      'method_id','tier','n','known_domain_n','domain_workers','class_counts','class_capacity',
      'theoretical_member_sets','old_cached_member_sets','registered_this_stage_member_sets',
      'registered_any_v3_stage_member_sets','cached_or_registered_member_sets','uncovered_member_sets',
      'old_cache_configuration_reached','this_stage_configuration_reached','any_v3_configuration_reached',
      'exhaustive_after_cached_and_registered','member_variation_available_this_stage']
    path=out/'ALL_SUPPLEMENT_DOMAIN_CONFIGURATIONS.csv.gz';writer=GzipCsv(path,fields,key='configuration_id')
    keys=set();coverage=[]
    for key,r in sorted(contexts.items()):
        workers=r['domain_workers'];classes=r['classes'];mapping=r['mapping'];dm=mask(workers)
        class_masks=[mask([w for w in workers if mapping[w]==c]) for c in classes]
        capacities=[m.bit_count() for m in class_masks]
        counts=collections.defaultdict(lambda:[0,0,0,0])
        for team,(mm,old,stages) in teams[(r['pool_id'],r['n'])].items():
            if mm & ~dm:continue
            cc=tuple((mm&m).bit_count() for m in class_masks)
            count=counts[cc];count[0]+=old;count[1]+=bool(stages&stage_bit[r['stage']]);count[2]+=bool(stages);count[3]+=1
        meta={k:r[k] for k in ['stage','pool_id','image','building','condition','difficulty','source_domain','method_id','tier','n']}
        cfgs=members=old_total=stage_total=v3_total=union_total=old_cfg=stage_cfg=v3_cfg=0
        for cc in vectors(capacities,r['n']):
            total=math.prod(math.comb(c,k) for c,k in zip(capacities,cc));old,current,v3,union=counts.get(cc,[0,0,0,0])
            if union>total:raise ValueError('member union exceeds exact finite space')
            cid=h('supplement-class-vector',key,cc)[:24];keys.add(cid)
            writer.add(dict(meta,configuration_id=cid,known_domain_n=len(workers),domain_workers='|'.join(workers),
              class_counts=counter_string(classes,cc),class_capacity=counter_string(classes,capacities),
              theoretical_member_sets=str(total),old_cached_member_sets=old,registered_this_stage_member_sets=current,
              registered_any_v3_stage_member_sets=v3,cached_or_registered_member_sets=union,uncovered_member_sets=str(total-union),
              old_cache_configuration_reached=old>0,this_stage_configuration_reached=current>0,any_v3_configuration_reached=v3>0,
              exhaustive_after_cached_and_registered=union==total,member_variation_available_this_stage=current>1))
            cfgs+=1;members+=total;old_total+=old;stage_total+=current;v3_total+=v3;union_total+=union
            old_cfg+=old>0;stage_cfg+=current>0;v3_cfg+=v3>0
        if members!=math.comb(len(workers),r['n']):raise ValueError('Vandermonde mismatch')
        coverage.append(dict(meta,known_domain_n=len(workers),domain_workers='|'.join(workers),
          class_capacity=counter_string(classes,capacities),feasible_class_configurations=cfgs,
          full_member_space=str(members),old_cached_member_sets=old_total,
          registered_this_stage_member_sets=stage_total,registered_any_v3_stage_member_sets=v3_total,
          cached_or_registered_member_sets=union_total,uncovered_member_sets=str(members-union_total),
          old_cache_configurations_reached=old_cfg,this_stage_configurations_reached=stage_cfg,
          any_v3_configurations_reached=v3_cfg,complete_finite_member_census=union_total==members,
          singleton_full_member_space=members==1))
    result=writer.finish(keys);write_csv(out/'SUPPLEMENT_DOMAIN_COVERAGE.csv',pd.DataFrame(coverage))
    summary=pd.DataFrame(coverage).groupby(['stage','method_id','tier','condition'],as_index=False).agg(
       domains=('n','size'),pools=('pool_id','nunique'),buildings=('building','nunique'),
       feasible_class_configurations=('feasible_class_configurations','sum'),
       this_stage_configurations_reached=('this_stage_configurations_reached','sum'),
       registered_this_stage_member_references=('registered_this_stage_member_sets','sum'),
       complete_member_domains=('complete_finite_member_census','sum'))
    write_csv(out/'SUPPLEMENT_METHOD_COVERAGE.csv',summary)
    receipt=dict(status='complete',contexts=len(contexts),all_feasible_configurations=len(keys),
      cached_rows_considered=prior_rows,unique_cache_or_registered_keys=sum(map(len,teams.values())),
      all_vector_counts_verified_by_vandermonde=True,all_big_integers_preserved_as_decimal_strings=True,
      stage_identity_preserved=True,source_domain_and_method_spaces_overlap=True,
      registered_does_not_imply_endpoint_score_success=True,native_calls=0,files=[result]+[
       dict(path=str((out/name).relative_to(HERE)),bytes=(out/name).stat().st_size,sha256=sha(out/name))
       for name in ['SUPPLEMENT_DOMAIN_COVERAGE.csv','SUPPLEMENT_METHOD_COVERAGE.csv']],
      label_sources={str(p):sha(p) for p in sources})
    gs.save(out/'COMPLETION.json',receipt);print(json.dumps(receipt,ensure_ascii=False),flush=True)

if __name__=='__main__':run()
