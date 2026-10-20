"""Combine saved small summaries without re-fusing or redoing pair metrics."""
from pathlib import Path
import collections,hashlib,json,sys
import pandas as pd
ROOT=Path(__file__).resolve().parents[3];HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'interchangeability_20261020/code'))
from design_history_panel import read,write
from summarize_blocks import csv_write

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def main():
    out=HERE/'both_effects';out.mkdir(exist_ok=True)
    completed=[];tables={}
    names=['ROUTE_CONTEXT.csv','N_M.csv.gz','SLOTS_TURNOVER.csv','DIFFICULTY.csv','BUILDING.csv','N_BAND.csv','SOURCE.csv','SOURCE_Q_SENSITIVITY.csv','WITHIN_EXACT_COMPOSITION.csv.gz','EXACT_COMPOSITION_CONTRAST.csv.gz','EVENT_EVIDENCE.csv.gz']
    for name in names:
        files=[HERE/(p+'_effects')/name for p in ['discovery','assessment']]
        d=pd.concat([pd.read_csv(f) for f in files],ignore_index=True);csv_write(d,out/name);tables[name]=d;completed.append(out/name)
    replication=[]
    for mode,filename,frozenfile,listkey,prioritykey in [
        ('VECTOR','WITHIN_EXACT_COMPOSITION.csv.gz','VECTOR_REPLICATION_FREEZE.json','all_eligible_vectors','display_priority_vectors'),
        ('CONTRAST','EXACT_COMPOSITION_CONTRAST.csv.gz','CONTRAST_REPLICATION_FREEZE.json','all_eligible_contrasts','display_priority_contrasts')]:
        d=tables[filename];frozen=read(HERE/frozenfile);keys=['method_id','domain','context_id','n','m','A_vector']+(['C_vector'] if mode=='CONTRAST' else [])
        disc=d[d.phase=='discovery'].drop(columns='phase');ass=d[d.phase=='assessment'].drop(columns='phase')
        merged=disc.merge(ass,on=keys,how='outer',suffixes=('_discovery','_assessment'),indicator=True)
        candidatekeys={tuple(r[k] for k in keys) for r in frozen[listkey]};prioritykeys={tuple(r[k] for k in keys) for r in frozen[prioritykey]}
        merged['frozen_discovery_eligible']=[tuple(r[k] for k in keys) in candidatekeys for _,r in merged.iterrows()]
        merged['frozen_display_priority']=[tuple(r[k] for k in keys) in prioritykeys for _,r in merged.iterrows()]
        p=out/('EXACT_'+mode+'_REPLICATION.csv.gz');csv_write(merged,p);completed.append(p)
        p=out/(mode+'_REPLICATION_PRIORITY.csv');csv_write(merged[merged.frozen_display_priority],p);completed.append(p)
        f=merged[merged.frozen_discovery_eligible]
        replication.append(dict(kind=mode,frozen_candidates=len(candidatekeys),observed_assessment_candidates=int((f._merge=='both').sum()),missing_assessment_candidates=int((f._merge!='both').sum()),priority_candidates=len(prioritykeys),priority_observed_assessment=int(((merged._merge=='both')&merged.frozen_display_priority).sum())))
    # Global physical-team support does not count the same team again merely
    # because it appeared under another classification or event.
    e=tables['EVENT_EVIDENCE.csv.gz'];armframes=[]
    for arm in 'ABC':
        x=e[['phase','pool_id','building','image',arm+'_team_key',arm+'_complete',arm+'_score_status',arm+'_geometry_reason',arm+'_B8L2']].rename(columns={arm+'_'+k:k for k in ['team_key','complete','score_status','geometry_reason','B8L2']});armframes.append(x)
    teams=pd.concat(armframes,ignore_index=True)
    check=teams.groupby(['phase','pool_id','team_key'],dropna=False)['B8L2'].agg(['min','max']);err=(check['max']-check['min']).abs().max();assert pd.isna(err) or err<=1e-10
    teams=teams.drop_duplicates(['phase','pool_id','team_key'])
    statuses=teams.groupby(['phase','complete','score_status','geometry_reason'],dropna=False).agg(distinct_teams=('team_key','nunique'),images=('image','nunique'),pools=('pool_id','nunique'),buildings=('building','nunique')).reset_index();csv_write(statuses,out/'ACTUAL_TEAM_STATUS.csv');completed.append(out/'ACTUAL_TEAM_STATUS.csv')
    rawledger=[]
    for phase,path in [('discovery',ROOT/'interchangeability_20261020/mixed_challenge/discovery_requests.json.gz'),('assessment',HERE/'assessment_requests.json.gz')]:
        for row in read(path)['ledger']:
            r=dict(row,phase=phase);r['class_capacities']=json.dumps(r['class_capacities'],sort_keys=True);r['draw_failures']=json.dumps(r['draw_failures'],sort_keys=True);rawledger.append(r)
    ledger=pd.DataFrame(rawledger);csv_write(ledger,out/'SEARCH_LEDGER.csv.gz');completed.append(out/'SEARCH_LEDGER.csv.gz')
    coverage=ledger.groupby(['phase','method_id','domain']).agg(pool_cells=('pool_id','size'),known_workers_min=('known_workers','min'),known_workers_max=('known_workers','max'),metadata_frame=('metadata_n_m_source_frame','sum'),whole_frame=('whole_frame','sum'),partial_frame=('partial_frame','sum'),selected_contexts=('selected_metadata_contexts','sum'),accepted_events=('accepted_events','sum')).reset_index();coverage['draw_failures']=coverage.selected_contexts-coverage.accepted_events
    csv_write(coverage,out/'SEARCH_COVERAGE.csv');completed.append(out/'SEARCH_COVERAGE.csv')
    byphase=[];allcrews=set()
    for phase,g in e.groupby('phase'):
        raw=read(ROOT/'interchangeability_20261020/mixed_challenge/discovery_requests.json.gz' if phase=='discovery' else HERE/'assessment_requests.json.gz')
        ws={w for x in raw['events'] for arm in 'ABC' for w in x[arm+'_workers']};crews={tuple(sorted(q['worker_ids'])) for q in raw['requests']};allcrews|=crews
        byphase.append(dict(phase=phase,raw_events=len(raw['events']),actual_triplets=len(g),unique_teams=len(teams[teams.phase==phase]),distinct_member_sets_across_pools=len(crews),images=g.image.nunique(),pools=g.pool_id.nunique(),buildings=g.building.nunique(),workers=len(ws),whole_events=int((g.context_id=='whole_team').sum()),partial_events=int((g.context_id!='whole_team').sum()),complete_unique_teams=int(teams[teams.phase==phase].complete.sum())))
    result=dict(schema='mixed_challenge_combined_small_tables_v1',phases=byphase,unique_teams_definition='pool_id plus exact member set; distinct_member_sets_across_pools also reported',distinct_member_sets_total=len(allcrews),vector_replication=replication,physical_team_duplicate_max_Q_error=None if pd.isna(err) else float(err),outputs={str(p.relative_to(ROOT)):dict(sha256=sha(p),bytes=p.stat().st_size) for p in completed},scope='Frozen seven routes and all events retained. Exact A/B/C duplicate excluded from effects only; original requests remain. Same-image team resamples are repeated measurements, not independent image count. Missing assessment exact vectors are shown; no surrogate n/ratio substituted.')
    write(out/'COMBINATION_RECEIPT.json',result);print(json.dumps({'phases':byphase,'replication':replication},ensure_ascii=False))

if __name__=='__main__':main()
