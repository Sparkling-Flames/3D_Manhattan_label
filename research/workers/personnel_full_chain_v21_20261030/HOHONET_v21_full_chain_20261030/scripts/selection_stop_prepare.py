"""Frozen v2 selection/stopping designs, current v2.1 qualifications and history.

No target outcome is used to choose a team. The original algorithm, random seeds,
history support thresholds and directly adopted room relations are retained.
"""
from pathlib import Path
import os, json, gzip, hashlib, itertools, importlib.util
import numpy as np
import pandas as pd

STUDY=Path(__file__).resolve().parents[1]
WORK=STUDY.parent
OUT=STUDY/'stage05_selection_stop'
INP=OUT/'inputs'
SRC=STUDY/'source'
PORT=STUDY/'source'
OLD='research/same_room/same_room_profile_return_review_20261021/pro'
REPLAY='research/same_room/same_room_multiview_20261020'

def read(p):
    with (gzip.open(p,'rt',encoding='utf-8-sig') if str(p).endswith('.gz') else open(p,encoding='utf-8-sig')) as f:return json.load(f)
def digest(x,compact=False):return hashlib.sha256(json.dumps(x,sort_keys=True,**({'separators':(',',':')} if compact else {})).encode()).hexdigest()
def teamkey(pid,ws):return pid+'__'+digest(sorted(ws),True)[:20]
def save(name,obj):
    p=OUT/name;p.parent.mkdir(parents=True,exist_ok=True)
    if isinstance(obj,pd.DataFrame):obj.to_csv(p,index=False)
    else:p.write_text(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def native_pools():
    p=PORT/'research/data/releases/v2.1/pools/INPUT_SNAPSHOT.json'
    b=p.read_bytes();assert hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()=='fa42df06d5cf0990d5e3bbd99f68c9f517b349b9'
    return {x['pool_id']:x for x in read(p)['images']}

def history():
    old=pd.read_csv(PORT/'research/workers/personnel_profiles_composition_20261020/source/tables/profiles/record_index.csv.gz')
    q=pd.read_csv(SRC/'research/data/releases/v2.1/quality_inventory.csv').set_index('object_id')
    d=old.copy()
    fields=['quality_usable','quality_use','reference_id','reference_version','chosen_target_id','B8L2','D10','pool_analysis_eligible','source_pool_eligible','source_active_time_seconds']
    for field in fields:d[field]=d.object_id.map(q[field])
    assert d.object_id.is_unique and d[fields[:2]].notna().all().all()
    d['Q_panel']=d.quality_use.map({'ordinary_primary':'ordinary','doorway_quality':'doorway','special_conditional_only':'special'})
    d['task_key']=d[['image_id','condition','chosen_target_id','reference_version']].fillna('<missing>').astype(str).agg('|'.join,axis=1)
    d['time_task_key']=d[['task_key','origin','time_source_kind']].fillna('<missing>').astype(str).agg('|'.join,axis=1)
    good=d.quality_usable&d.chosen_target_id.notna()
    for metric in ('B8L2','D10'):
        d[metric+'_peer_recomputed']=np.nan;d[metric+'_rank_recomputed']=np.nan
        g=d.loc[good].groupby('task_key')[metric];n=g.transform('count');total=g.transform('sum')
        d.loc[good,metric+'_peer_recomputed']=d.loc[good,metric]-(total-d.loc[good,metric])/(n-1).replace(0,np.nan)
        d.loc[good,metric+'_rank_recomputed']=100*(g.rank(method='average')-1)/(n-1).replace(0,np.nan)
    t=d.pool_analysis_eligible&d.source_active_time_seconds.gt(0)&d.chosen_target_id.notna()
    d['log_source_time']=np.nan;d['log_time_peer_recomputed']=np.nan
    d.loc[t,'log_source_time']=np.log(d.loc[t,'source_active_time_seconds'])
    g=d.loc[t].groupby('time_task_key').log_source_time;n=g.transform('size');total=g.transform('sum')
    d.loc[t,'log_time_peer_recomputed']=d.loc[t,'log_source_time']-(total-d.loc[t,'log_source_time'])/(n-1).replace(0,np.nan)
    path=INP/'research/workers/personnel_profiles_composition_20261020/source/code/profiles/build_profiles.py'
    spec=importlib.util.spec_from_file_location('frozen_profile_history',path);mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    (OUT/'history').mkdir(exist_ok=True);h=mod.history_features(d,OUT/'history')
    frozen=pd.read_csv(INP/'research/workers/personnel_profiles_composition_20261020/tables/history_lobo.csv')
    key=['target_building','worker_id','condition','origin','panel']
    z=frozen.merge(h,on=key,suffixes=('_v2','_v21'),validate='one_to_one')
    for c in ['Q_peer','relative_time','n_quality_images','n_quality_buildings','n_time_images','n_time_buildings']:
        z['delta_'+c]=z[c+'_v21']-z[c+'_v2']
    save('history/HISTORY_CHANGE.csv.gz',z)
    save('history/HISTORY_RECORDS_CURRENT.csv.gz',d)
    save('history/HISTORY_CONTRACT.json',{'source':'original record-index panel, updated current quality/qualification/reference before recomputing leave-one-out peers','n_records':len(d),'n_history_rows':len(h),'quality_supported_changed':int((z.Q_supported_8images_3buildings_v2!=z.Q_supported_8images_3buildings_v21).sum()),'time_supported_changed':int((z.T_supported_8images_3buildings_v2!=z.T_supported_8images_3buildings_v21).sum()),'not_chronological':True,'target_building_excluded':True,'quality_peer_excludes_self':True,'time_source_kind_and_origin_separate':True,'history_thresholds':[8,3]})
    return frozen,h

def selection(oldhistory,newhistory,pools):
    oldpools={p['pool_id']:p for p in read(INP/'research/workers/pro_personnel_v2_archive_20261019/work_v2_20261019/fusion/INPUT_SNAPSHOT.json.gz')['images']}
    rels=read(SRC/'research/same_room/relation_adoption_20261016/relations.json')
    if isinstance(rels,dict):rels=rels.get('relations',rels.get('pairs'))
    byimage={}
    for p in oldpools.values():byimage.setdefault(p['meta']['image_id'],[]).append(p)
    hmaps=[]
    for h in [oldhistory,newhistory]:hmaps.append({(r.target_building,r.worker_id,r.condition,r.origin,r.panel):r._asdict() for r in h.itertuples(index=False)})
    rows=[];requests={};contexts=[];candidates=[]
    for rel in rels:
        if not rel.get('physical_adopted'):continue
        for pa,pb in itertools.product(byimage.get(rel['image_a'],[]),byimage.get(rel['image_b'],[])):
            ma=pa['meta'];mb=pb['meta']
            if ma['condition']!=mb['condition'] or ma['layer']!=mb['layer']:continue
            pairid='PAIR_'+digest([pa['pool_id'],pb['pool_id']])[:16]
            aa={r['worker_id']:r for r in pa['records']};bb={r['worker_id']:r for r in pb['records']}
            common=sorted(aa.keys()&bb.keys());panel='doorway' if ma['layer'].startswith('doorway') else 'ordinary'
            h0={w:hmaps[0].get((ma['building'],w,ma['condition'],aa[w]['origin'],panel),{}) for w in common}
            h1={w:hmaps[1].get((ma['building'],w,ma['condition'],aa[w]['origin'],panel),{}) for w in common}
            meta=dict(pair_id=pairid,group_ids='|'.join(rel.get('user_group_ids',[])),scope_comparable=rel.get('scope_comparable'),relation_tier=rel.get('tier'),condition=ma['condition'],building=ma['building'],layer=ma['layer'],image_a=ma['image'],image_b=mb['image'],pool_a=pa['pool_id'],pool_b=pb['pool_id'])
            for source,target in [(pa,pb),(pb,pa)]:
                sr={r['worker_id']:r for r in source['records']};curS=pools.get(source['pool_id']);curT=pools.get(target['pool_id'])
                if curS is None or curT is None:continue
                cs={r['worker_id']:r for r in curS['records']};ct={r['worker_id']:r for r in curT['records']}
                for domain in ['all','new','new_timed_history']:
                    avail=[w for w in common if h0[w].get('Q_supported_8images_3buildings') and np.isfinite(h0[w].get('Q_peer',np.nan)) and (domain=='all' or sr[w]['origin']=='new')]
                    if domain=='new_timed_history':avail=[w for w in avail if h0[w].get('T_supported_8images_3buildings') and np.isfinite(h0[w].get('relative_time',np.nan)) and sr[w].get('source_time_seconds') is not None and sr[w]['source_time_seconds']>0]
                    # Keep the original candidates fixed. Qualification failures are recorded, never silently replaced.
                    legal=[w for w in avail if w in cs and w in ct and h1[w].get('Q_supported_8images_3buildings') and np.isfinite(h1[w].get('Q_peer',np.nan))]
                    contexts.append(dict(meta,source_pool_id=source['pool_id'],target_pool_id=target['pool_id'],domain=domain,old_available=len(avail),current_legal=len(legal),lost_workers='|'.join(sorted(set(avail)-set(legal))),old_candidates='|'.join(avail),current_candidates='|'.join(legal)))
                    for version,hist,src in [('v2_fixed_selection_current_score',h0,sr),('v21_history_reselected_fixed_candidates',h1,cs)]:
                        own=avail if version.startswith('v2') and version!='v21_history_reselected_fixed_candidates' else legal
                        own=[w for w in own if w in cs and w in ct]
                        q={w:hist[w]['Q_peer'] for w in own};sq={w:src[w]['B8L2'] for w in own};half={w:.5*(q[w]+sq[w]) for w in own}
                        for w in own:candidates.append(dict(meta,version=version,source_pool_id=source['pool_id'],target_pool_id=target['pool_id'],domain=domain,worker_id=w,history_Q=q[w],source_Q=sq[w],history_T=hist[w].get('relative_time'),source_T=src[w].get('source_time_seconds'),history_quality_images=hist[w].get('n_quality_images'),history_quality_buildings=hist[w].get('n_quality_buildings')))
                        def best(vals,n):return sorted(sorted(own,key=lambda w:(-vals[w],w))[:n])
                        def fast(base,cost):
                            current=list(base);floor=np.mean([q[w] for w in base])-2
                            while True:
                                opts=[]
                                for old in current:
                                    for new in sorted(set(own)-set(current)):
                                        ws=sorted(set(current)-{old}|{new});avg=np.mean([q[w] for w in ws]);t=sum(cost[w] for w in ws)
                                        if avg>=floor and t<sum(cost[w] for w in current)-1e-9:opts.append((t,-avg,ws))
                                if not opts:break
                                current=min(opts)[2]
                            return current
                        for n in [3,4,5,6,7,9,13]:
                            if len(own)<=n:continue
                            teams={'outside_Q':best(q,n),'source_Q':best(sq,n),'half_Q':best(half,n)}
                            if domain=='new_timed_history':
                                teams['outside_Q_outside_T_fast']=fast(teams['outside_Q'],{w:hist[w]['relative_time'] for w in own})
                                teams['outside_Q_source_T_fast']=fast(teams['outside_Q'],{w:src[w]['source_time_seconds'] for w in own})
                            for rep in range(3):
                                rng=np.random.default_rng(int(digest([2026102143,[pairid,source['pool_id'],domain,n,rep]])[:16],16))
                                teams['random_'+str(rep)]=sorted(rng.choice(own,n,False).tolist())
                            for policy,ws in teams.items():
                                key=teamkey(target['pool_id'],ws)
                                requests.setdefault(key,dict(team_key=key,pool_id=target['pool_id'],member_workers='|'.join(ws),n=n,uses=[]))['uses'].append('selection')
                                rows.append(dict(meta,version=version,source_pool_id=source['pool_id'],source_image=source['meta']['image'],target_pool_id=target['pool_id'],target_image=target['meta']['image'],domain=domain,n=n,policy=policy,member_workers='|'.join(ws),available_workers=len(own),available_worker_ids='|'.join(own),team_key=key,history_Q_mean=np.mean([q[w] for w in ws]),source_Q_mean=np.mean([sq[w] for w in ws]),source_roster_activity_seconds=sum(sr[w]['source_time_seconds'] for w in own) if domain!='all' and all(sr[w].get('source_time_seconds') is not None for w in own) else np.nan))
    for r in requests.values():r['uses']='selection'
    save('design/SELECTION_DESIGN.csv.gz',pd.DataFrame(rows));save('design/CANDIDATE_HISTORY.csv.gz',pd.DataFrame(candidates).drop_duplicates());save('design/CONTEXT_QUALIFICATION.csv.gz',pd.DataFrame(contexts))
    primary=pd.DataFrame(rows);counts=primary.groupby(['version','condition','layer','scope_comparable','domain','n','policy']).agg(events=('team_key','size'),images=('target_image','nunique'),buildings=('building','nunique')).reset_index();save('design/DESIGN_COVERAGE.csv',counts)
    a=counts[(counts.version=='v2_fixed_selection_current_score')&(counts.layer=='ordinary_manual')&counts.scope_comparable&(counts.domain=='all')&(counts.n==5)&(counts.policy=='outside_Q')].iloc[0]
    assert [int(a[c]) for c in ['events','images','buildings']]==[242,64,12],a.to_dict()
    return requests

def stopping(pools,requests):
    oldpools={p['pool_id']:p for p in read(INP/REPLAY/'REPLAY_POOLS.json.gz')}
    nodes=pd.read_csv(INP/REPLAY/'replay_nodes.csv.gz',low_memory=False)
    compare=[];affected=[];verification=[]
    for pid,p in oldpools.items():
        cur=pools[pid];old={r['worker_id']:r for r in p['records']};new={r['worker_id']:r for r in cur['records']}
        used=nodes[nodes.pool_id==pid];workers=set(w for ws in used.member_workers for w in ws.split('|'))
        for w in workers:
            assert w in new and old[w]['object_id']==new[w]['object_id'] and old[w]['points']==new[w]['points'],(pid,w)
            assert old[w].get('source_time_seconds')==new[w].get('source_time_seconds'),(pid,w,'changed_recorded_labor')
        # Reference metadata can change without changed points; physical reference equality is decisive.
        same=p['reference']['points_1024x512']==cur['reference']['points_1024x512']
        compare.append(dict(pool_id=pid,image=p['meta']['image'],rows=len(used),used_members=len(workers),current_members_qualified=True,reference_geometry_same=same,old_reference=p['meta']['reference_id'],current_reference=cur['meta']['reference_id']))
        if not same:
            affected.append(pid)
            for row in used[used.k!=2].drop_duplicates('member_workers').itertuples():
                ws=sorted(row.member_workers.split('|'));key=teamkey(pid,ws)
                if key in requests:requests[key]['uses']+='|stopping_rescore'
                else:requests[key]=dict(team_key=key,pool_id=pid,member_workers='|'.join(ws),n=len(ws),uses='stopping_rescore')
    save('design/STOPPING_POOL_IDENTITY.csv',pd.DataFrame(compare))
    save('design/STOPPING_CONTRACT.json',{'original_nodes':len(nodes),'original_groups_with_results':nodes.group_id.nunique(),'original_unique_images':nodes.image_id.nunique(),'affected_pools':affected,'unchanged_members_qualified':True,'k2':'retain original deferred non-evaluation; not newly sorted or included in stopping choices','source_rule':'frozen original near-peak threshold and geometry-only topup; no target Q in choices','new_natural_orders':0})
    for r in requests.values():r['uses']='|'.join(sorted(set(r['uses'].split('|'))))
    save('design/ENDPOINT_REQUESTS.csv.gz',pd.DataFrame(requests.values()))
    print(json.dumps({'selection_and_stopping_unique_endpoints':len(requests),'affected_stopping_pools':affected}),flush=True)

if __name__=='__main__':
    OUT.mkdir(exist_ok=True);pools=native_pools();h0,h1=history();req=selection(h0,h1,pools);stopping(pools,req)
