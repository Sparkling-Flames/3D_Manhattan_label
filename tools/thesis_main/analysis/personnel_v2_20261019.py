"""v2描述性细类：Q、T、难度及独立的Semi/scope证据，不构造综合分。"""
import json
from pathlib import Path
import pandas as pd
from .quality_workers_v2_20261019 import ROOT, OUT as QUALITY, INPUT, read, write
from .worker_difficulty_profiles_20261018 import add_relative, preferences, LABELS

OUT=ROOT/'research/workers/personnel_v2_20261019'
PAGE=ROOT/'research/statistics/research_explorer_v1_r2_20261017'

def qclass(rank,n,buildings):
    if n<6 or buildings<3 or pd.isna(rank):return '证据不足'
    return '高' if rank>=2/3 else '中' if rank>=1/3 else '低'

def tclass(seconds,n,fast=60,slow=180):
    if n<6 or pd.isna(seconds):return '证据不足'
    return '快' if seconds<fast else '慢' if seconds>=slow else '中'

def records(frame):return json.loads(frame.to_json(orient='records',force_ascii=False))

def scope_response(value):
    if isinstance(value,list):value=value[0] if len(value)==1 else None
    return {'in_scope':'in','out_of_scope':'out'}.get(value)

def error_opportunity(value):
    return isinstance(value,dict) and value.get('error_specific_outcome') in (
        'unknown_after_edit','known_error_retained_unchanged')

def audited_scope_counts(rows):
    evidence=[r['scope_evidence'] for r in rows if r['cleaning_disposition']=='retained']
    judged=[r for r in evidence if r['judgement_opportunity']]
    return dict(scope_judged_n=len(judged),scope_correct_n=sum(r['correct'] is True for r in judged),
        scope_confirmed_oos_n=sum(r.get('compatible_gold')=='out_of_scope' for r in judged),
        scope_confirmed_in_n=sum(r.get('compatible_gold')=='in_scope' for r in judged),
        scope_out_n=sum(r['response']=='out_of_scope' for r in evidence),
        scope_response_n=sum(r['response'] in ('in_scope','out_of_scope') for r in evidence))

def run():
    OUT.mkdir(parents=True,exist_ok=True)
    inventory=read(QUALITY/'quality_inventory.json');allrows=pd.DataFrame(inventory)
    allrows['worker_scope_response']=allrows.worker_scope_response.map(scope_response)
    q=allrows[allrows.quality_usable].copy()
    q['difficulty']=q.current_class.map(LABELS).fillna('special_or_unrated')
    q['panel']=q.condition+'|'+q.quality_use
    q['context_key']=q[['image_id','condition','reference_id','reference_version']].apply(lambda r:json.dumps(r.tolist()),axis=1)
    assert not q.duplicated(['context_key','worker_id']).any()
    q=add_relative(q)
    q['source_active_time_seconds']=pd.to_numeric(q.source_active_time_seconds,errors='coerce')
    q.loc[q.source_active_time_seconds.le(0),'source_active_time_seconds']=float('nan')
    main=q[q.panel.eq('manual|ordinary_primary')];pref=preferences(main)
    profiles=[]
    for (panel,worker),g in q.groupby(['panel','worker_id']):
        for difficulty,part in [('all',g),*list(g.groupby('difficulty'))]:
            n=len(part);buildings=part.building_id.nunique();rank=part.B8L2_rank.mean()
            tm=part.source_active_time_seconds.median();tn=part.source_active_time_seconds.notna().sum()
            profiles.append(dict(panel=panel,worker_id=worker,difficulty=difficulty,n=n,buildings=int(buildings),
                B8L2_mean=part.B8L2.mean(),B8L2_p10=part.B8L2.quantile(.1),D10_mean=part.D10.mean(),
                relative_q=rank,relative_q_D10=part.D10_rank.mean(),peer_delta=part.B8L2_peer_delta.mean(),
                q_class=qclass(rank,n,buildings),q_class_D10=qclass(part.D10_rank.mean(),n,buildings),
                time_median=tm,time_n=int(tn),time_source=part.time_provenance.iloc[0],
                t_class=tclass(tm,tn),t_class_sensitivity=tclass(tm,tn,90,240)))
    p=pd.DataFrame(profiles)
    p['fine_class']=p.q_class+'Q × '+p.t_class+'T × '+p.difficulty
    reliability=[]
    evidence=read(ROOT/'research/statistics/v2_evidence_audit_20261019/records.json.gz')['records']
    by_worker={w:[r for r in evidence if r['worker_id']==w] for w in allrows.worker_id.unique()}
    for worker,g in allrows.groupby('worker_id'):
        retained=g[g.cleaning_disposition.eq('retained')]
        semi=[r for r in retained.semi_reported if error_opportunity(r)]
        old_semi=[r['semi_evidence'] for r in by_worker[worker] if r['cleaning_disposition']=='retained'
                  and r['semi_evidence'].get('confirmed_error_opportunity')]
        reliability.append(dict(worker_id=worker,semi_error_opportunities=len(semi),
            semi_known_error_unchanged=sum(r.get('known_error_unchanged') is True for r in semi),
            semi_edited_outcome_unknown=sum(r.get('error_specific_outcome')=='unknown_after_edit' for r in semi),
            semi_confirmed_error_opportunities=len(old_semi),
            semi_confirmed_error_unchanged=sum(r.get('known_error_unchanged') is True for r in old_semi),
            **audited_scope_counts(by_worker[worker])))
    reliability=pd.DataFrame(reliability)
    p=p.merge(reliability,on='worker_id',validate='many_to_one')
    p=p.merge(pref[['worker_id','B8L2_candidate','B8L2_hard_rank','B8L2_nonhard_rank','B8L2_advantage',
        'B8L2_leave_building_min','B8L2_leave_building_max']],on='worker_id',how='left',validate='many_to_one')
    for name,frame in [('records',q),('profiles',p),('difficulty_preferences',pref),('reliability',reliability)]:
        frame.to_csv(OUT/(name+'.csv'),index=False,encoding='utf-8-sig')
    groups=p[p.difficulty.eq('all')].groupby(['panel','fine_class']).agg(workers=('worker_id',list),n=('worker_id','size')).reset_index()
    groups.to_csv(OUT/'groups.csv',index=False,encoding='utf-8-sig')
    summary=dict(quality_rows=len(q),quality_images=q.image_id.nunique(),quality_workers=q.worker_id.nunique(),
        main_rows=len(main),main_workers=main.worker_id.nunique(),main_images=main.image_id.nunique(),
        difficulty_candidates=pref.B8L2_candidate.value_counts().to_dict(),
        classification='exploratory_descriptive_not_validated_worker_types',
        relative_q='Same image, condition and reference: (average ascending rank - 1)/(peer workers - 1); then worker mean.',
        thresholds='Exploratory Q thirds; support >=6 tasks, >=3 buildings. T median <60 / 60-180 / >=180 seconds; sensitivity 90/240.',
        semi='Known erroneous initialization unchanged / known erroneous initialization opportunities; edited is not proven corrected.',
        scope='Retained records with independently bound, semantically compatible historical task gold only. Image OOS tags are not person gold; response tendency separate.',
        caveats=['Time provenance differs between cohorts; source time is not necessarily target-matched time.',
                 'No v2 fusion or exchangeability claim; difficulty preferences are descriptive with leave-building stability ranges.'])
    write(OUT/'SUMMARY.json',summary)
    payload=dict(summary=summary,profiles=records(p),groups=records(groups),records=records(q),
        inventory=inventory,audit=read(QUALITY/'binding_audit.json'))
    # Only the seven pending new records need geometry review; keep the full audit separately.
    data=read(INPUT/'data.json.gz');objects={o['object_id']:o for o in data['objects']}
    refs=read(QUALITY/'reference_catalog.json');bindings={b['object_id']:b for b in read(QUALITY/'reference_bindings.json')}
    payload['reviews']=[dict(a,points=objects[a['object_id']]['points_1024x512'],
        references=[dict(name=r['target_id'],points=r['points_1024x512'],floor=r['floor_xz_h']) for r in refs
                    if r['target_id'] in bindings[a['object_id']]['allowed_target_ids']])
        for a in payload['audit'] if a['resolution']=='needs_geometry_or_target_review']
    difficulty={d['image_id']:d for d in read(QUALITY/'difficulty_records.json')}
    for r in payload['reviews']:
        photo=difficulty[objects[r['object_id']]['image_id']].get('photo')
        if photo:
            r['photo']='../../../'+Path(photo).relative_to(ROOT).as_posix()
    (PAGE/'personnel-v2-data.js').write_text('window.V2='+json.dumps(payload,ensure_ascii=False,allow_nan=False)+';\n',encoding='utf-8')
    scorepath=(QUALITY/'CROSS_MODULE_INPUTS.json').relative_to(ROOT).as_posix()
    for path in (INPUT/'manifest.json',INPUT.parent/'RELEASE.json',INPUT.parent.parent/'CURRENT.json'):
        status=read(path)
        status.update(analysis_status='quality_scored_personnel_exploratory_fusion_not_rerun',score_context=scorepath,
            personnel_summary=(OUT/'SUMMARY.json').relative_to(ROOT).as_posix())
        if 'status' in status:status['status']='quality_scored_personnel_exploratory'
        write(path,status)
    print(json.dumps(summary,ensure_ascii=True,indent=2))

if __name__=='__main__':run()
