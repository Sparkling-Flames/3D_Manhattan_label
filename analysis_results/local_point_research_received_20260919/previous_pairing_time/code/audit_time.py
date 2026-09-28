"""Active-time feasibility audit and simple descriptive/held-out-person time baselines.
No lead-time substitution, no new collection, no causal or attentiveness claims.
Historical C1 task-worker cumulative timing is preserved exactly.
"""
import audit_geometry as a
from pathlib import Path
import json,ast,collections,itertools,hashlib,sys,warnings
import numpy as np,pandas as pd
from scipy.stats import spearmanr
R=a.ROOT; O=a.OUT; P=R/'sources/repo'
sys.path.insert(0,str(P))
from tools.thesis_main.analysis.quality_core.active_time import load_active_logs,lookup_active_log_entry

def truth(v):return str(v).lower()in ['true','1']
def num(v):
    try:return float(v)
    except:return np.nan

def corr(x,y):
    if len(x)<3 or np.ptp(x)<1e-10 or np.ptp(y)<1e-10:return np.nan
    return float(spearmanr(x,y).statistic)

def run(include_deviation=False):
    c1p=next(P.glob('analysis_results/c1_formal_audit_20260802_v16_final/*/c1_task_worker_active_time.csv'))
    cs=pd.read_csv(c1p,dtype=str,keep_default_na=False);c1={(r.project_id,r.runtime_task_id,r.worker_id):r for r in cs.itertuples()}
    assert len(c1)==len(cs)==780
    rawindex={};owners={};sources=[]
    for p in sorted({r['raw_export_path']for r in a.ROWS}):
        d=json.loads((P/p).read_text(encoding='utf-8-sig'));sources.append(dict(path=p,sha256=hashlib.sha256((P/p).read_bytes()).hexdigest()))
        for t in d:
            for ann in t.get('annotations',[]):
                rawindex[p,str(t['id']),str(ann['id'])]=(t,ann)
    for r in a.ROWS:
        _,project,task,worker,ann=r['raw_annotation_version_id'].split('|');owners[project,task,ann]=worker
    logs={}
    for stage,block,folder in [('P1','0','prescreen'),('C2-B','0','c2b'),('C2-A-RP','1','c2a_rp_block1_20260810'),('C2-A-RP','2','c2a_rp_block2_20260814')]:
        logs[stage,block]=load_active_logs(str(P/'active_logs'/folder),annotation_owner_map=owners)
    rr=[]
    for r in a.ROWS:
        if r['worker_id']in ['W019','W026']:continue
        e=r['evidence'];_,project,task,worker,ann=r['raw_annotation_version_id'].split('|')
        taskrow,annrow=rawindex[r['raw_export_path'],task,ann]
        owner=annrow.get('completed_by');owner=owner.get('id')if isinstance(owner,dict)else owner
        assert str(owner)==worker
        rawpoints=[[float(z['value']['x'])*1024/100,float(z['value']['y'])*512/100]for z in annrow.get('result',[])if z.get('type')=='keypointlabels']
        p=np.array(rawpoints,float).reshape(-1,2);p0=np.array(r['raw_points_1024x512'],float).reshape(-1,2)
        assert p.shape==p0.shape and np.allclose(p,p0,rtol=0,atol=1e-7,equal_nan=True)
        status=e['active_time_owner_valid_status'];sec=num(e.get('active_time_seconds'));formal=truth(e.get('time_active_time_formal_available'))
        complete=status=='owner_valid_complete'and formal and np.isfinite(sec)and sec>0
        sensitivity=status in ['owner_valid_complete','owner_valid_complete_with_deviation']and formal and np.isfinite(sec)and sec>0
        match='not_applicable';recomputed=np.nan;source_status='';extra={}
        if r['stage']=='C1':
            q=c1[project,task,worker];assert r['canonical_annotation_id']in ast.literal_eval(q.canonical_annotation_ids);assert q.base_task_id==r['image_id']
            recomputed=num(q.task_worker_active_seconds);match='frozen_C1_task_worker_table';source_status=q.timing_status
            extra=dict(c1_eligible=truth(q.task_worker_time_analysis_eligible),c1_partial=q.timing_status=='partial_session_coverage_excluded_from_speed',c1_session_count=num(q.session_count),c1_revision_count=num(q.revision_count),c1_cross_worker_events=num(q.cross_worker_selection_event_count))
        elif complete or sensitivity:
            q,match=lookup_active_log_entry(logs[r['stage'],r['block_index']],project,task,worker,ann)
            if q:recomputed=num(q['active_time_value'])
            source_status=e.get('time_timing_status','')
        matches=bool(np.isfinite(sec)and np.isfinite(recomputed)and abs(sec-recomputed)<1e-8)
        # Frozen source table is preferred even if a fresh loader differs: never overwrite durations.
        rec=dict(id=r['canonical_annotation_id'],image_id=r['image_id'],code=a.AUD.loc[r['canonical_annotation_id'],'code'],building=r['building_id'],worker=r['worker_id'],stage=r['stage'],block=r['block_index'],condition=r['raw_condition'],status=status,formal_available=formal,seconds=sec,strict_eligible=complete,deviation_sensitivity_eligible=sensitivity,source_match_kind=match,source_status=source_status,source_rederived_seconds=recomputed,source_seconds_match=matches,source_delta=recomputed-sec if np.isfinite(recomputed)and np.isfinite(sec)else np.nan,source_path=e.get('active_time_source_path',''),time_basis=e.get('time_timing_rule_version',''),lead_time_seconds=num(e.get('lead_time_seconds')),created_at=annrow.get('created_at'),updated_at=annrow.get('updated_at'),geometry_available=bool(a.AUD.loc[r['canonical_annotation_id'],'geometry_eligible']),raw_identity_and_points_match=True,**extra)
        rec['context']=rec['stage']+'|'+rec['block']+'|'+rec['condition'];rr.append(rec)
    df=pd.DataFrame(rr);df['log_seconds']=np.log(df.seconds.where(df.seconds>0));df['created_at']=pd.to_datetime(df.created_at,utc=True,errors='coerce');df['updated_at']=pd.to_datetime(df.updated_at,utc=True,errors='coerce')
    # Provenance qualification, not statistical trimming. Any nonmatching strict record is audited separately.
    df['analysis_eligible']=(df.deviation_sensitivity_eligible if include_deviation else df.strict_eligible) & df.source_seconds_match
    df.to_csv(O/'time_record_audit.csv',index=False)
    strict=df[df.analysis_eligible].copy()
    summaries=[]
    for key,g in strict.groupby(['stage','block','condition']):
        n=g.groupby('image_id').size()
        summaries.append(dict(stage=key[0],block=key[1],condition=key[2],records=len(g),images=g.image_id.nunique(),workers=g.worker.nunique(),median_sec=g.seconds.median(),p25_sec=g.seconds.quantile(.25),p75_sec=g.seconds.quantile(.75),image_units_ge3=int((n>=3).sum()),image_units_ge5=int((n>=5).sum()),image_units_ge8=int((n>=8).sum())))
    pd.DataFrame(summaries).to_csv(O/'time_descriptive_by_condition.csv',index=False)
    # Worker-speed baseline from OTHER buildings in SAME stage/block/condition.
    strict['speed_baseline']=np.nan;strict['speed_source_n']=0
    for _,idx in strict.groupby(['worker','context']).groups.items():
        g=strict.loc[idx]
        for building,ix in g.groupby('building').groups.items():
            train=g[g.building!=building]
            if len(train)>=5:
                strict.loc[ix,'speed_baseline']=train.log_seconds.median();strict.loc[ix,'speed_source_n']=len(train)
    strict['speed_adjusted_log_time']=strict.log_seconds-strict.speed_baseline
    strict.to_csv(O/'time_analysis_rows.csv',index=False)
    # Same-image held-out-person time: at least 4 other people, no target time used in prediction.
    predictions=[]
    for (iid,ctx),g0 in strict.groupby(['image_id','context']):
        g=g0[np.isfinite(g0.speed_baseline)];assert not g.worker.duplicated().any()
        if len(g)<5:continue
        for i,row in g.iterrows():
            peers=g.drop(index=i);offset=peers.speed_adjusted_log_time.median()
            predictions.append(dict(id=row.id,image_id=iid,code=row.code,building=row.building,context=ctx,worker=row.worker,N_peers=len(peers),observed_log_time=row.log_seconds,worker_baseline=row.speed_baseline,peer_image_adjusted_prediction=row.speed_baseline+offset,baseline_abs_log_error=abs(row.log_seconds-row.speed_baseline),peer_abs_log_error=abs(row.log_seconds-row.speed_baseline-offset),created_at=row.created_at,peer_after_target=int((peers.created_at>row.created_at).sum()),mode='retrospective_heldout_person_not_chronological'))
    pr=pd.DataFrame(predictions);pr.to_csv(O/'time_same_image_heldout_person.csv',index=False)
    predsummary=[]
    for ctx,g in pr.groupby('context'):
        agg=g.groupby(['image_id','building'])[['baseline_abs_log_error','peer_abs_log_error']].mean().reset_index()
        predsummary.append(dict(context=ctx,records=len(g),images=g.image_id.nunique(),buildings=g.building.nunique(),baseline_image_equal_MAE=agg.baseline_abs_log_error.mean(),with_peer_image_equal_MAE=agg.peer_abs_log_error.mean(),delta=agg.peer_abs_log_error.mean()-agg.baseline_abs_log_error.mean()))
    pd.DataFrame(predsummary).to_csv(O/'time_same_image_prediction_summary.csv',index=False)
    # Within-image association of time differences and pairing-free geometry differences.
    pp=pd.read_csv(a.OUT/'simple_pointset_pairwise.csv');lookup=strict.set_index('id');xp=[];assoc=[]
    for p in pp.itertuples():
        if p.id_a not in lookup.index or p.id_b not in lookup.index:continue
        x,y=lookup.loc[p.id_a],lookup.loc[p.id_b]
        if x.context!=y.context:continue
        xp.append(dict(image_id=p.image_id,code=p.code,building=x.building,context=x.context,id_a=p.id_a,id_b=p.id_b,worker_a=x.worker,worker_b=y.worker,geometry_ospa_deg=p.ospa30_deg,abs_log_time_gap=abs(x.log_seconds-y.log_seconds),abs_adjusted_time_gap=abs(x.speed_adjusted_log_time-y.speed_adjusted_log_time)))
    xdf=pd.DataFrame(xp);xdf.to_csv(O/'time_geometry_pairs.csv',index=False)
    for (iid,ctx),g in xdf.groupby(['image_id','context']):
        workers=set(g.worker_a)|set(g.worker_b)
        if len(workers)<5:continue
        v=g.dropna(subset=['abs_adjusted_time_gap']);vw=set(v.worker_a)|set(v.worker_b)
        assoc.append(dict(image_id=iid,code=g.iloc[0].code,building=g.iloc[0].building,context=ctx,people=len(workers),pairs=len(g),raw_spearman=corr(g.geometry_ospa_deg,g.abs_log_time_gap),adjusted_people=len(vw),adjusted_pairs=len(v),adjusted_spearman=corr(v.geometry_ospa_deg,v.abs_adjusted_time_gap)if len(vw)>=5 else np.nan))
    ad=pd.DataFrame(assoc);ad.to_csv(O/'time_geometry_image_associations.csv',index=False)
    # Use latest supported same-room GROUPS. Pair keys are de-duplicated; no transitive physical-room inference.
    inv=json.loads((P/'analysis_results/unassigned_room_inventory_20260915/全648图同房与分配明细.json').read_text());inv={r['image_id']:r for r in inv}
    bygroup=collections.defaultdict(set)
    for iid,r in inv.items():
        for group in r['supported_groups']:bygroup[group].add(iid)
    roompairs=collections.defaultdict(set)
    for group,iids in bygroup.items():
        for ia,ib in itertools.combinations(sorted(iids),2):roompairs[ia,ib].add(group)
    contexts={(iid,ctx):g.set_index('worker')for (iid,ctx),g in strict.groupby(['image_id','context'])}
    room=[];roomrows=[]
    for (ia,ib),tags in roompairs.items():
        for ctx in sorted(set(strict.context)):
            ga=contexts.get((ia,ctx));gb=contexts.get((ib,ctx))
            if ga is None or gb is None:continue
            common=sorted(set(ga.index)&set(gb.index));good=[w for w in common if np.isfinite(ga.loc[w,'speed_baseline'])and np.isfinite(gb.loc[w,'speed_baseline'])]
            if not common:continue
            xa=ga.loc[common];xb=gb.loc[common];dt=xb.log_seconds.to_numpy()-xa.log_seconds.to_numpy();ta=xa.created_at;tb=xb.created_at
            room.append(dict(image_a=ia,image_b=ib,code_a=inv[ia]['code'],code_b=inv[ib]['code'],building=ia.split('_')[0],context=ctx,supported_group_ids=';'.join(sorted(tags)),common_people=len(common),adjusted_people=len(good),raw_logtime_spearman=corr(xa.log_seconds,xb.log_seconds),adjusted_spearman=corr(ga.loc[good,'speed_adjusted_log_time'],gb.loc[good,'speed_adjusted_log_time'])if len(good)>=3 else np.nan,median_abs_logratio=float(np.median(abs(dt))),a_before_b=int((ta<tb).sum()),b_before_a=int((tb<ta).sum()),order_unknown=int((ta.isna()|tb.isna()|(ta==tb)).sum())))
            for w in common:
                x,y=ga.loc[w],gb.loc[w]
                roomrows.append(dict(image_a=ia,image_b=ib,code_a=inv[ia]['code'],code_b=inv[ib]['code'],group_ids=';'.join(sorted(tags)),building=ia.split('_')[0],context=ctx,worker=w,id_a=x.id,id_b=y.id,seconds_a=x.seconds,seconds_b=y.seconds,logtime_a=x.log_seconds,logtime_b=y.log_seconds,residual_a=x.speed_adjusted_log_time,residual_b=y.speed_adjusted_log_time,created_at_a=x.created_at,created_at_b=y.created_at,unknown_other_exposure=True))
    rdf=pd.DataFrame(room);rdf.to_csv(O/'time_same_room_pair_coverage.csv',index=False);pd.DataFrame(roomrows).to_csv(O/'time_same_room_person_pairs.csv',index=False)
    c1bytes=c1p.read_bytes();c1summary=json.loads(c1p.with_suffix('.summary.json').read_text());crlfhash=hashlib.sha256(c1bytes.replace(b'\r\n',b'\n').replace(b'\n',b'\r\n')).hexdigest()
    sourceaudit=dict(C1_summary_hash_matches_after_CRLF_restoration=crlfhash==c1summary['output_sha256'],C1_source_sha256=hashlib.sha256(c1p.read_bytes()).hexdigest(),C1_rows=len(cs),C1_all_seconds_equal=bool(df[df.stage=='C1'].apply(lambda r:(not np.isfinite(r.seconds)and not np.isfinite(r.source_rederived_seconds))or r.source_seconds_match,axis=1).all()),strict_candidate_rows=int(df.strict_eligible.sum()),strict_matches=int(df.loc[df.strict_eligible,'source_seconds_match'].sum()),mismatches=df.loc[df.strict_eligible & ~df.source_seconds_match,['id','stage','block','seconds','source_rederived_seconds','source_match_kind']].to_dict('records'))
    (O/'time_source_audit.json').write_text(json.dumps(a.old.safe_json(sourceaudit),ensure_ascii=False,indent=2))
    summary=dict(include_protocol_deviation=include_deviation,raw_after_worker_exclusions=len(df),statuses=df.status.value_counts().to_dict(),strict_candidate=int(df.strict_eligible.sum()),strict_source_verified=len(strict),deviation_extra=int(df.deviation_sensitivity_eligible.sum()-df.strict_eligible.sum()),raw_point_identity_checks=len(df),raw_sources=sources,source_audit=sourceaudit,strict_contexts=summaries,worker_baseline_available=int(strict.speed_baseline.notna().sum()),same_image_time_prediction=predsummary,time_geometry_by_context=ad.groupby('context').agg(images=('image_id','size'),raw_median_rho=('raw_spearman','median'),adjusted_n=('adjusted_spearman','count'),adjusted_median_rho=('adjusted_spearman','median')).reset_index().to_dict('records'),same_room_pair_units=len(rdf),same_room_unique_pairs=len(rdf[['image_a','image_b']].drop_duplicates()),same_room_common_ge3=int((rdf.common_people>=3).sum()),same_room_common_ge5=int((rdf.common_people>=5).sum()),same_room_common_ge8=int((rdf.common_people>=8).sum()),same_room_adjusted_ge5=int((rdf.adjusted_people>=5).sum()))
    (O/'time_summary.json').write_text(json.dumps(a.old.safe_json(summary),ensure_ascii=False,indent=2));print(json.dumps(a.old.safe_json(summary),ensure_ascii=False,indent=2))
if __name__=='__main__':
    deviation='--deviation' in sys.argv
    if deviation: O=O/'time_with_deviation';O.mkdir(exist_ok=True)
    run(deviation)
