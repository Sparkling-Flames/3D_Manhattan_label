"""Composition-level summaries for the seven frozen mixed-team challenges.

Read final event metrics; no fusion, target relabelling, or criterion changes.
Exact vectors include zero counts and explicitly outside_group background.
Within evidence deduplicates unordered actual A/B team pairs. Endpoint quality
deduplicates actual A/B teams, and never borrows the changed-composition C arm.
"""
from __future__ import annotations
import argparse, collections, hashlib, json, math, os, sys
from pathlib import Path
for key in ['OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS']:os.environ[key]='1'
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[3]
OUT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'interchangeability_20261020/code'))
from design_history_panel import read,write
from design_blocks import labels_from
from summarize_blocks import csv_write

PATHS={
 'discovery':(ROOT/'interchangeability_20261020/mixed_challenge/discovery_requests.json.gz',ROOT/'interchangeability_20261020/mixed_challenge/discovery_metrics/event_metrics.csv.gz'),
 'assessment':(OUT/'assessment_requests.json.gz',OUT/'assessment_metrics/event_metrics.csv.gz')}
LABELS=[ROOT/'interchangeability_20261020/forward/worker_labels.csv.gz',ROOT/'interchangeability_20261020/reverse/mixed_fit/worker_labels.csv.gz']
CRITERIA=['joint_stable_'+s for s in ['strict','main','wide']]+['geometry_noQ_'+s for s in ['strict','main','wide']]+['geometry_shape_'+s for s in ['strict','main','wide']]
WITHIN_CONT=['abs_B8L2_change','floor_jaccard_difference','structure_bound_cyclic_deg','node_count_difference','mean_height_prism_pair_iou','bottom_y_absdiff_deg_p95','bottom_y_absdiff_deg_max','top_y_absdiff_deg_p95','top_y_absdiff_deg_max','wall_coverage_symmetric_min_main','true_corner_F1_main','boundary_total_height_abs_logratio_p95']
WITHIN_METRICS=['within_'+x for x in CRITERIA+WITHIN_CONT]+['within_both_complete','within_bad_Q_gt5','within_bad_Q_gt10','within_failed_any','within_stable_lowQ_lt50','within_geometry_shape_main_and_prism_proxy_iou_lt_095','within_different_original_nodes_shape_main_passes']
CONTRAST_METRICS=['within_'+x for x in CRITERIA]+['cross_'+x for x in CRITERIA]+['gap_'+x for x in CRITERIA]+['cross_'+x for x in WITHIN_CONT]+['net_B8L2_change','net_D10_change','net_floor_jaccard_difference','net_Q_improve_gt2','net_Q_worsen_gt2','net_complete_lost','net_complete_restored','net_omission_delta','net_extension_delta','net_diag_wall_coverage_05_delta','net_diag_corner_recall_05_delta','net_IoU3D100_delta','net_nodes_delta','net_new_n_delta','cross_minus_within_history_Q','within_bad_Q_gt5','within_bad_Q_gt10','within_failed_any','B_complete','C_complete','B_B8L2','C_B8L2']

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def vector(d,classes):return '|'.join(f'{cl}:{d.get(cl,0)}' for cl in classes+['outside_group'])
def keypair(a,b):return '|'.join(sorted([a,b]))
def finite(x):return x is not None and not isinstance(x,str) and math.isfinite(float(x))

def load_phase(phase):
    manifest,metricfile=PATHS[phase]; data=read(manifest); maps=labels_from(LABELS)
    frame=pd.read_csv(metricfile); assert set(frame.event_id)=={e['event_id'] for e in data['events']}
    original=len(frame); exact={e['event_id']:e for e in data['events']}; extra=[]
    for e in data['events']:
        classes=sorted(set(maps[e['method_id'],e['domain']].values())); ca=e['A_counts']; cc=e['C_counts']
        allworkers=tuple(sorted(set(e['A_workers'])|set(e['B_workers'])|set(e['C_workers'])))
        abworkers=tuple(sorted(set(e['A_workers'])|set(e['B_workers'])))
        blockworkers=tuple(sorted(set(e['outgoing_workers'])|set(e['within_incoming'])|set(e['cross_incoming'])))
        extra.append(dict(event_id=e['event_id'],A_vector=vector(ca,classes),C_vector=vector(cc,classes),core_vector=vector(e['core_counts'],classes),outgoing_vector=vector(e['outgoing_counts'],classes),incoming_vector=vector(e['incoming_counts'],classes),known_classes_A=sum(ca.get(cl,0)>0 for cl in classes),known_classes_C=sum(cc.get(cl,0)>0 for cl in classes),outside_n=e['outside_background_n'],changed_class_labels_n=sum(ca.get(cl,0)!=cc.get(cl,0) for cl in classes),AB_pair=keypair(e['A_team_key'],e['B_team_key']),AC_pair=keypair(e['A_team_key'],e['C_team_key']),BC_pair=keypair(e['B_team_key'],e['C_team_key']),all_workers=allworkers,ab_workers=abworkers,block_workers=blockworkers,all_teams=tuple(e[x+'_team_key'] for x in 'ABC'),ab_teams=tuple(e[x+'_team_key'] for x in 'AB')))
    frame=frame.merge(pd.DataFrame(extra),on='event_id',validate='one_to_one')
    frame=frame.drop_duplicates(['method_id','domain','pool_id','A_team_key','B_team_key','C_team_key']).copy()
    frame['within_bad_Q_gt10']=frame.within_abs_B8L2_change.gt(10).where(frame.within_abs_B8L2_change.notna())
    frame['within_failed_any']=~frame.within_both_complete
    frame['within_stable_lowQ_lt50']=frame.within_joint_stable_main & frame.A_B8L2.lt(50) & frame.B_B8L2.lt(50)
    frame['within_min_Q']=frame[['A_B8L2','B_B8L2']].min(axis=1).where(frame[['A_B8L2','B_B8L2']].notna().all(axis=1))
    frame['C_is_pure_known']=frame.known_classes_C==1
    frame['outside_fraction']=frame.outside_n/frame.n
    frame['BC_turnover_fraction']=frame.B_to_C_actual_turnover/frame.n
    frame['category_slot_fraction']=frame.changed_category_slots/frame.n
    frame['n_band']=pd.cut(frame.n,[2,5,10,17,25,100],labels=['03-05','06-10','11-17','18-25','26+'])
    return frame,data,dict(phase=phase,requests_sha256=sha(manifest),metrics_sha256=sha(metricfile),raw_events=original,deduplicated_events=len(frame),removed_exact_triples=original-len(frame))

def support(group,within=False):
    def union(col):return len(set(w for vals in group[col] for w in vals))
    return dict(events=len(group),images=group.image.nunique(),pools=group.pool_id.nunique(),buildings=group.building.nunique(),AB_unique_pairs=group.AB_pair.nunique(),AC_unique_pairs=group.AC_pair.nunique() if not within else None,BC_unique_pairs=group.BC_pair.nunique() if not within else None,unique_teams=union('ab_teams' if within else 'all_teams'),workers=union('ab_workers' if within else 'all_workers'),replacement_workers=union('block_workers') if not within else None,n_min=int(group.n.min()),n_max=int(group.n.max()),m_min=int(group.m.min()),m_max=int(group.m.max()),BC_turnover_min=int(group.B_to_C_actual_turnover.min()) if not within else None,BC_turnover_max=int(group.B_to_C_actual_turnover.max()) if not within else None,changed_slots_min=int(group.changed_category_slots.min()) if not within else None,changed_slots_max=int(group.changed_category_slots.max()) if not within else None,outside_n_max=int(group.outside_n.max()))

def aggregate(frame,columns,metrics,within=False):
    if frame.empty:return pd.DataFrame()
    f=frame.drop_duplicates(list(dict.fromkeys(columns+['phase','method_id','domain','context_id','pool_id','AB_pair']))) if within else frame
    metrics=[x for x in metrics if x in f]
    f=f.copy()
    for x in metrics:f[x]=pd.to_numeric(f[x],errors='coerce').astype(float)
    # Equal images/pools within buildings, equal buildings. No event replication
    # is interpreted as an independent image; conditional tables retain support.
    bypool=list(dict.fromkeys(columns+['building','pool_id']))
    bby=list(dict.fromkeys(columns+['building']))
    p=f.groupby(bypool,dropna=False,observed=True)[metrics].mean().reset_index()
    b=p.groupby(bby,dropna=False,observed=True)[metrics].mean().reset_index()
    means=b.groupby(columns,dropna=False,observed=True)[metrics].mean().add_suffix('_building_mean').reset_index()
    records=[]
    quantiles=['within_abs_B8L2_change','within_floor_jaccard_difference','within_min_Q'] if within else ['net_B8L2_change','net_D10_change','B_B8L2','C_B8L2','within_abs_B8L2_change']
    for keys,g in f.groupby(columns,dropna=False,observed=True,sort=True):
        if not isinstance(keys,tuple):keys=(keys,)
        row=dict(zip(columns,keys));row.update(support(g,within))
        for key in quantiles:
            v=pd.to_numeric(g[key],errors='coerce').dropna()
            row.update({key+'_finite_pairs':int(len(v)),key+'_pair_min':float(v.min()) if len(v) else None,key+'_pair_p10':float(v.quantile(.1)) if len(v) else None,key+'_pair_p90':float(v.quantile(.9)) if len(v) else None,key+'_pair_p95':float(v.quantile(.95)) if len(v) else None,key+'_pair_max':float(v.max()) if len(v) else None})
        row['both_complete_pairs']=int(g.within_both_complete.sum())
        if within:row['incomplete_pairs']=int((~g.within_both_complete.astype(bool)).sum())
        records.append(row)
    return pd.DataFrame(records).merge(means,on=columns,validate='one_to_one')

def endpoint_table(frame,columns):
    rows=[]
    fields=['complete','B8L2','D10','IoU3D100','nodes','omission','extension','diag_wall_coverage_05','diag_corner_recall_05','score_status','geometry_reason']
    for arm in 'AB':
        part=frame[list(dict.fromkeys(columns+['pool_id','image','building','event_id']))+[arm+'_team_key']+[arm+'_'+k for k in fields]].copy()
        part=part.rename(columns={arm+'_'+k:k for k in ['team_key']+fields});rows.append(part)
    teams=pd.concat(rows,ignore_index=True).drop_duplicates(columns+['pool_id','team_key'])
    metrics=[x for x in fields if x not in ['score_status','geometry_reason']]
    p=teams.groupby(list(dict.fromkeys(columns+['pool_id','building'])),dropna=False,observed=True)[metrics].mean().reset_index()
    b=p.groupby(list(dict.fromkeys(columns+['building'])),dropna=False,observed=True)[metrics].mean().reset_index()
    weighted=b.groupby(columns,dropna=False,observed=True)[metrics].mean().add_prefix('AB_team_').add_suffix('_building_mean').reset_index()
    rows=[]
    for keys,g in teams.groupby(columns,dropna=False,observed=True):
        if not isinstance(keys,tuple):keys=(keys,)
        row=dict(zip(columns,keys));q=g.B8L2.dropna()
        row.update(AB_distinct_endpoint_teams=len(g),AB_failed_endpoint_teams=int((~g.complete).sum()),AB_endpoint_Q_finite_n=int(len(q)),AB_endpoint_Q_min=float(q.min()) if len(q) else None,AB_endpoint_Q_p10=float(q.quantile(.1)) if len(q) else None,AB_endpoint_Q_p90=float(q.quantile(.9)) if len(q) else None)
        rows.append(row)
    return weighted.merge(pd.DataFrame(rows),on=columns)

def make_tables(frame,out):
    out.mkdir(parents=True,exist_ok=True);base=['phase','method_id','domain','context_id'];written=[]
    for name,extra in [('ROUTE_CONTEXT',[]),('N_M',['n','m']),('SLOTS_TURNOVER',['changed_category_slots','B_to_C_actual_turnover']),('DIFFICULTY',['difficulty']),('BUILDING',['building']),('N_BAND',['n_band']),('SOURCE',['matching','actual_source_match'])]:
        cols=base+extra
        contrast=aggregate(frame,cols,CONTRAST_METRICS)
        within=aggregate(frame,cols,WITHIN_METRICS,True)
        within=within.rename(columns={c:'dedup_'+c for c in within if c not in cols})
        table=contrast.merge(within,on=cols,how='outer').merge(endpoint_table(frame,cols),on=cols,how='left')
        target=out/(name+'.csv.gz' if len(table)>500 else name+'.csv');csv_write(table,target);written.append(target)
    qsub=[]
    for label,f in [('all',frame),('actual_source_match',frame[frame.actual_source_match]),('source_and_Qclose3',frame[frame.actual_source_match&frame.all_blocks_history_Q_close3])]:
        tab=aggregate(f,base,CONTRAST_METRICS+['all_blocks_history_Q_close3']);tab['subset']=label;qsub.append(tab)
    csv_write(pd.concat(qsub,ignore_index=True),out/'SOURCE_Q_SENSITIVITY.csv');written.append(out/'SOURCE_Q_SENSITIVITY.csv')
    vcols=base+['n','m','A_vector']
    within=aggregate(frame,vcols,WITHIN_METRICS,True).merge(endpoint_table(frame,vcols),on=vcols,how='left')
    csv_write(within,out/'WITHIN_EXACT_COMPOSITION.csv.gz');written.append(out/'WITHIN_EXACT_COMPOSITION.csv.gz')
    contrast=aggregate(frame,base+['n','m','A_vector','C_vector'],CONTRAST_METRICS)
    csv_write(contrast,out/'EXACT_COMPOSITION_CONTRAST.csv.gz');written.append(out/'EXACT_COMPOSITION_CONTRAST.csv.gz')
    # Compact, exact event key permits join to requests and full final metrics.
    eventcols=base+['event_id','pool_id','building','image','difficulty','n','m','matching','actual_source_match','A_vector','C_vector','core_vector','outgoing_vector','incoming_vector','outside_n','known_classes_A','known_classes_C','changed_category_slots','changed_class_labels_n','B_to_C_actual_turnover','A_team_key','B_team_key','C_team_key']+[a+'_'+x for a in 'ABC' for x in ['complete','B8L2','D10','nodes','score_status','geometry_reason']]+list(dict.fromkeys(WITHIN_METRICS+CONTRAST_METRICS))
    csv_write(frame[list(dict.fromkeys(eventcols))],out/'EVENT_EVIDENCE.csv.gz');written.append(out/'EVENT_EVIDENCE.csv.gz')
    return written,within,contrast

def freeze_vectors(within,contrast,out):
    target=OUT/'VECTOR_REPLICATION_FREEZE.json'
    if target.exists():return
    # Rules selected only from discovery; all qualifying vectors retained and
    # rank is explicit rather than disguising outcome selection as a blind test.
    eligible=within[(within.images>=3)&(within.buildings>=2)].copy()
    columns=['method_id','domain','context_id','n','m','A_vector']
    selected=[]
    for keys,g in eligible.groupby(['method_id','domain','context_id']):
        ranks=g.sort_values(['within_joint_stable_main_building_mean','AB_team_B8L2_building_mean','images','A_vector'],ascending=[False,False,False,True]).head(3)
        for _,r in ranks.iterrows():selected.append({k:r[k].item() if isinstance(r[k],np.generic) else r[k] for k in columns})
    candidates=[{k:r[k].item() if isinstance(r[k],np.generic) else r[k] for k in columns} for _,r in eligible.iterrows()]
    write(target,dict(schema='mixed_exact_composition_internal_replication_v1',discovery_requests_sha256=sha(PATHS['discovery'][0]),discovery_metrics_sha256=sha(PATHS['discovery'][1]),analysis_script_sha256=sha(__file__),assessment_scientific_outcomes_read_before_freeze=False,eligibility='Exact method/domain/context/n/m/A full vector represented on at least 3 discovery images and 2 buildings; all such vectors retained, with assessment capacity/missingness reported.',candidate_count=len(candidates),all_eligible_vectors=candidates,display_priority_rule='Top three per route/context ranked by discovery within joint main, then actual A/B endpoint mean Q, then image count and lexicographic vector. This is declared outcome-based discovery selection, not automatic pre-collection success.',display_priority_vectors=selected,criteria_unchanged=True,assessment_scope='The six fixed v2 assessment buildings, reused data; assessment labels are history-only and unchanged. New concrete teams are not new independent images.'))

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--phase',choices=['discovery','assessment','both'],required=True);a=ap.parse_args()
    phases=['discovery','assessment'] if a.phase=='both' else [a.phase]
    frames=[];receipts=[]
    for phase in phases:
        if phase=='assessment':assert (OUT/'VECTOR_REPLICATION_FREEZE.json').exists(),'Freeze discovery vector candidates before inspecting assessment metrics'
        frame,data,receipt=load_phase(phase);frames.append(frame);receipts.append(receipt)
    frame=pd.concat(frames,ignore_index=True);out=OUT/(a.phase+'_effects')
    written,within,contrast=make_tables(frame,out)
    if a.phase=='discovery':freeze_vectors(within,contrast,out)
    if a.phase=='both':
        columns=['method_id','domain','context_id','n','m','A_vector']
        d=within[within.phase=='discovery'].drop(columns='phase');v=within[within.phase=='assessment'].drop(columns='phase')
        repl=d.merge(v,on=columns,how='outer',suffixes=('_discovery','_assessment'),indicator=True)
        frozen=read(OUT/'VECTOR_REPLICATION_FREEZE.json');candidatekeys={tuple(r[x] for x in columns) for r in frozen['all_eligible_vectors']};prioritykeys={tuple(r[x] for x in columns) for r in frozen['display_priority_vectors']}
        repl['frozen_discovery_eligible']=[tuple(r[x] for x in columns) in candidatekeys for _,r in repl.iterrows()]
        repl['frozen_display_priority']=[tuple(r[x] for x in columns) in prioritykeys for _,r in repl.iterrows()]
        csv_write(repl,out/'EXACT_VECTOR_REPLICATION.csv.gz');written.append(out/'EXACT_VECTOR_REPLICATION.csv.gz')
    receipt=dict(schema='mixed_composition_independent_summary_v1',analysis_script_sha256=sha(__file__),phases=receipts,events=len(frame),images=int(frame.image.nunique()),pools=int(frame.pool_id.nunique()),buildings=int(frame.building.nunique()),methods=int(frame.method_id.nunique()),whole_team_events=int((frame.context_id=='whole_team').sum()),partial_events=int((frame.context_id!='whole_team').sum()),workers=len(set(w for a in frame.all_workers for w in a)),replacement_workers=len(set(w for a in frame.block_workers for w in a)),unique_teams=len(set(w for a in frame.all_teams for w in a)),outputs={str(p.relative_to(ROOT)):dict(sha256=sha(p),bytes=p.stat().st_size) for p in written},weighting='For event contrasts: deduplicate exact oriented A/B/C triples, then events within pool, pools/images within building, equal buildings. Within rates deduplicate actual unordered A/B pairs per route/context; A/B endpoint levels deduplicate actual A/B teams within the reported group. No C outcome enters within endpoint level/tail. Pair and endpoint p10/p90/max are descriptive empirical quantiles, not confidence limits.',missing='Failed/incomplete outcomes remain in all attempted pair/team denominators; absent Q is never zero. Finite score-pair and endpoint-team counts are separate. All requests n>=3.',interpretation='Whole and partial challenges separate; n/m/categorical slots/B->C actual turnover remain distinct. Seven methods fixed before discovery; exact vector priorities selected only on discovery and frozen before reading assessment. Both phases reuse v2.')
    write(out/'ANALYSIS_RECEIPT.json',receipt);print(json.dumps({k:receipt[k] for k in ['events','images','pools','buildings','methods','whole_team_events','partial_events','workers','unique_teams']},ensure_ascii=False))

if __name__=='__main__':main()
