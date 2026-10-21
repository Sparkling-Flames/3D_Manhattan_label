"""Keep old phase identities and add actual v3 work, without inflating domain coverage."""
from pathlib import Path
import csv,gzip,hashlib,json
import pandas as pd

HERE=Path(__file__).resolve().parent;NEW=HERE.parent
OLD=NEW.parent/'personnel_global_composition_20261021';CONT=OLD/'continuation_20261021'

def write(d,p):
    tmp=p.with_name(p.name+'.partial');d.to_csv(tmp,index=False,encoding='utf-8-sig');tmp.replace(p)

def main():
    source=CONT/'integration/PHASE1_PHASE2_DOMAIN_SUBSET_COVERAGE_26x2.csv'
    d=pd.read_csv(source,keep_default_na=False)
    completed=set();receipts=[];stage_export_references=0
    for p in sorted((NEW/'composition/batches').glob('*/COMPLETION.json')):
        r=json.loads(p.read_text());sp=p.parent/'ENDPOINT_SCALARS.csv.gz'
        if r.get('status')!='complete' or not sp.is_file():continue
        kk=set(pd.read_csv(sp,usecols=['team_key']).team_key)
        stage_export_references+=len(kk)
        completed.update(kk);receipts.append({'batch_id':r['batch_id'],'teams':len(kk),'states':r['states'],'file':str(sp.relative_to(NEW))})
    frames=[]
    for name in ['PANEL_MATCHED_EVENTS','LARGE_BLOCK_EVENTS','PURE_BLOCK_MATCHED_EVENTS','PURE_BLOCK_CROSS_ONLY_EVENTS','LEGACY_PARTIAL_EVENTS']:
        p=NEW/'composition/matched'/f'{name}.csv.gz'
        if not p.exists():continue
        g=pd.read_csv(p,keep_default_na=False);g['registered_experiment']=name;frames.append(g)
    ev=pd.concat(frames,ignore_index=True)
    method_rows=[]
    for (condition,method,experiment),g in ev.groupby(['condition','method_id','registered_experiment']):
        arms=['team_'+a for a in 'ABC' if 'team_'+a in g and g['team_'+a].notna().any()]
        keys=set().union(*(set(g[c].dropna()) for c in arms))
        done=g[arms].isin(completed).all(axis=1)
        physical=g.physical_triple_id.dropna().nunique() if len(arms)==3 else 0
        m=g.m_AB if len(arms)==3 else g.m_AC
        method_rows.append(dict(condition=condition,method_id=method,registered_experiment=experiment,
          comparison_arms='ABC' if len(arms)==3 else 'AC',
          registered_events=len(g),complete_endpoint_available_events=int(done.sum()),unique_physical_triples=physical,
          distinct_referenced_teams=len(keys),completed_referenced_teams=len(keys&completed),images=g.image.nunique(),buildings=g.building.nunique(),
          min_n=g.n.min(),max_n=g.n.max(),min_actual_m=m.min(),max_actual_m=m.max(),
          fixed_parent_fine_events=int(g.within_parent_fine_change.eq(True).sum()),
          new_labels_fitted=method in ['V3_BEHAVIOR','V3_JOINT_QT']))
    f01=NEW/'composition/F01_CAPACITY_TEAMS.csv.gz'
    if f01.exists():
        g=pd.read_csv(f01,keep_default_na=False);kk=set(g.team_key)
        method_rows.append(dict(condition='manual',method_id='F01',registered_experiment='F01_COMPLETE_KNOWN_DOMAIN_MEMBERS',
          comparison_arms='finite_member_census',registered_events=0,complete_endpoint_available_events=0,unique_physical_triples=0,
          distinct_referenced_teams=len(kk),completed_referenced_teams=len(kk&completed),images=g.image.nunique(),buildings=g.building.nunique(),
          min_n=g.n.min(),max_n=g.n.max(),min_actual_m=None,max_actual_m=None,fixed_parent_fine_events=0,new_labels_fitted=False))
    m=pd.DataFrame(method_rows);write(m,HERE/'PHASE3_METHOD_EXPERIMENT_COVERAGE.csv')
    # CQT's C is structural opportunity; it is not the five-domain D (difficulty
    # adaptability). S in old QTDS likewise meant structure, not scope.
    mapping={('manual','Q+T'):['V3_JOINT_QT','F01'],('semi','Q+T'):['V3_JOINT_QT'],
             ('manual','Q+T+D'):['MV_QTD_manual_new'],('semi','Q+T+scope+Semi'):['MV_QTScopeSemi_semi_new']}
    canonical=lambda s:frozenset(s.split('+'))
    for i,r in d.iterrows():
        ids=[]
        for (condition,domains),methods in mapping.items():
            if condition==r.condition and canonical(domains)==canonical(r.domain_subset):ids=methods
        mm=m[m.condition.eq(r.condition)&m.method_id.isin(ids)]
        d.loc[i,'phase3_method_ids']='|'.join(sorted(mm.method_id.unique()))
        d.loc[i,'phase3_new_classification_domains']='Q+T plus separately declared structure' if 'V3_JOINT_QT' in ids else ''
        d.loc[i,'phase3_registered_event_references']=int(mm.registered_events.sum())
        d.loc[i,'phase3_completed_endpoint_event_references']=int(mm.complete_endpoint_available_events.sum())
        d.loc[i,'phase3_new_screen_of_this_domain_subset']=False
        done=bool(len(mm) and (mm.complete_endpoint_available_events==mm.registered_events).all() and (mm.completed_referenced_teams==mm.distinct_referenced_teams).all())
        d.loc[i,'phase3_status']=('actual_multin_and_block_endpoints_complete' if done else 'actual_multin_and_block_comparisons_in_progress') if len(mm) else 'historical_results_reused_no_new_deep_experiment'
        d.loc[i,'phase3_ABC_registered_event_references']=int(mm.loc[mm.comparison_arms.eq('ABC'),'registered_events'].sum())
        d.loc[i,'phase3_AC_registered_event_references']=int(mm.loc[mm.comparison_arms.eq('AC'),'registered_events'].sum())
        d.loc[i,'phase3_not_a_new_pure_five_domain_candidate']='V3_JOINT_QT also uses structure; F01 is population-conditioned' if r.domain_subset=='Q+T' else ''
        d.loc[i,'phase3_completed_count_meaning']='endpoint availability, not all complete-evaluable; failures remain in result tables'
    write(d,HERE/'PHASE1_PHASE2_PHASE3_DOMAIN_COVERAGE_26x2.csv')
    panels=pd.read_csv(NEW/'composition/PANELS.csv');teams=pd.read_csv(NEW/'composition/DESIGN_TEAMS.csv.gz',usecols=['team_key'])
    checkpoint=dict(latest_main='324dba44d0a82d9d64a62965f2e549ee05165417',domain_ledger_rows=len(d),
      historical_ledger_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),native_completed_unique=len(completed),stage_export_references=stage_export_references,
      registered_main_unique_teams=len(teams),completed_main_unique=len(set(teams.team_key)&completed),
      main_conditional_panels=len(panels),main_conditional_members_per_panel=924,main_membership_references=len(panels)*924,
      main_full_pool_exhaustion=False,registered_events=len(ev),completed_batches=receipts,
      note='No algorithm/K variants counted as different variable-domain subsets. No exact team endpoint counted twice.')
    (HERE/'COVERAGE_CHECKPOINT.json').write_text(json.dumps(checkpoint,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v for k,v in checkpoint.items() if k!='completed_batches'},ensure_ascii=False))

if __name__=='__main__':main()
